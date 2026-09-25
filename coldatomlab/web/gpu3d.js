"use strict";

// WebGPU owns preparation and evolution. CPU JavaScript only assembles initial
// data, reduces downloaded diagnostics and integrates the independent TF ODE.
window.GPUCloud3D = class {
  static validate(c) {
    if (![32, 64, 128].includes(c.n))
      throw Error(
        "WebGPU supports 32³, 64³ or 128³. Choose a supported grid; no automatic grid substitution is applied.",
      );
    const limits = {
      length: [16, 64],
      dt: [0.0005, 0.01],
      atoms: [10, 300000],
      scattering_nm: [0, 10],
      reference_hz: [10, 100],
      fx_hz: [5, 200],
      fy_hz: [5, 200],
      fz_hz: [5, 200],
      duration: [0.1, 4],
      preparation_dt: [0.0005, 0.004],
    };
    for (const [k, [lo, hi]] of Object.entries(limits))
      if (
        typeof c[k] !== "number" ||
        !Number.isFinite(c[k]) ||
        c[k] < lo ||
        c[k] > hi
      )
        throw Error(`${k} must be between ${lo} and ${hi}.`);
    if (!Number.isInteger(c.atoms) || c.length / c.n > 0.5)
      throw Error("Use an integer atom number and grid spacing ≤ 0.5 a₀.");
    if (
      [c.fx_hz, c.fy_hz, c.fz_hz].some(
        (f) => f / c.reference_hz < 0.5 || f / c.reference_hz > 2,
      )
    )
      throw Error(
        "Each trap frequency must be 0.5–2 times the reference frequency.",
      );
    const a = Math.sqrt(
      6.62607015e-34 /
        (2 * Math.PI) /
        (1.443160895e-25 * 2 * Math.PI * c.reference_hz),
    );
    const scales = {
      length_um: a * 1e6,
      time_ms: 1000 / (2 * Math.PI * c.reference_hz),
      energy_hz: c.reference_hz,
      interaction: (4 * Math.PI * c.atoms * c.scattering_nm * 1e-9) / a,
      mass_kg: 1.443160895e-25,
    };
    if (scales.interaction > 8000)
      throw Error("Derived 3D interaction exceeds 8000.");
    return scales;
  }
  static async create(config, progress = () => {}) {
    const s = new GPUCloud3D();
    s.config = { ...config };
    s.scales = this.validate(config);
    const start = performance.now();
    try {
      if (!navigator.gpu)
        throw Error(
          "WebGPU is unavailable here. Open this page in a supported Chrome/Edge browser over HTTPS or localhost, or choose CPU reference.",
        );
      const adapter = await navigator.gpu.requestAdapter({
        powerPreference: "high-performance",
      });
      if (!adapter)
        throw Error(
          "No WebGPU adapter is available. Try hardware-accelerated Chrome/Edge, or choose CPU reference.",
        );
      if (adapter.info.isFallbackAdapter)
        throw Error(
          "Only a software WebGPU adapter is available; use CPU reference or a browser with hardware GPU acceleration.",
        );
      s.adapter = {
        vendor: adapter.info.vendor,
        architecture: adapter.info.architecture,
        description: adapter.info.description,
        fallback: adapter.info.isFallbackAdapter,
      };
      s.device = await adapter.requestDevice();
      s.device.lost.then((info) => {
        s.lost = info.message || "GPU device lost.";
      });
      s.device.addEventListener("uncapturederror", (event) => {
        s.lost = event.error.message;
      });
      await s.initialize();
      s.setupSeconds = (performance.now() - start) / 1000;
      await s.prepare(progress);
      s.preparation.elapsed_seconds = (performance.now() - start) / 1000;
      s.preparation.setup_seconds = s.setupSeconds;
      s.initial = await s.readField();
      s.preparation.persistent_array_bytes = s.buffers.reduce(
        (sum, b) => sum + b.size,
        0,
      );
      await s.reset();
      if (s.history[0].edge_probability > 1e-5)
        throw Error(
          "Prepared cloud is too close to the boundary; increase the box and grid together.",
        );
      return s;
    } catch (e) {
      s.destroy();
      throw e;
    }
  }
  check() {
    if (this.lost)
      throw Error(
        `WebGPU device unavailable: ${this.lost} Prepare again or choose CPU reference.`,
      );
  }
  destroy() {
    if (this.device) this.device.destroy();
  }
  buffer(size, usage, data) {
    const b = this.device.createBuffer({ size, usage });
    this.buffers.push(b);
    if (data) this.device.queue.writeBuffer(b, 0, data);
    return b;
  }
  async initialize() {
    const c = this.config,
      n = c.n;
    this.n = n;
    this.count = n ** 3;
    this.dx = c.length / n;
    this.g = this.scales.interaction;
    this.w = [c.fx_hz, c.fy_hz, c.fz_hz].map((f) => f / c.reference_hz);
    this.muTF = this.g
      ? 0.5 *
        ((15 * this.g * this.w.reduce((a, b) => a * b, 1)) / (4 * Math.PI)) **
          0.4
      : 0;
    this.x = Array.from({ length: n }, (_, i) => (i - n / 2) * this.dx);
    this.buffers = [];
    const storage =
      GPUBufferUsage.STORAGE |
      GPUBufferUsage.COPY_SRC |
      GPUBufferUsage.COPY_DST;
    this.fields = [
      this.buffer(this.count * 8, storage),
      this.buffer(this.count * 8, storage),
    ];
    this.index = 0;
    this.analysis = [
      this.buffer(this.count * 8, storage),
      this.buffer(this.count * 8, storage),
    ];
    this.control = this.buffer(
      32,
      storage,
      new Float32Array([1, this.muTF, 0, 0, 0, 0, 0, 0]),
    );
    this.partial = this.buffer(Math.ceil(this.count / 256) * 8, storage);
    const tw = new Float32Array(n);
    for (let i = 0; i < n / 2; i++) {
      tw[2 * i] = Math.cos((2 * Math.PI * i) / n);
      tw[2 * i + 1] = -Math.sin((2 * Math.PI * i) / n);
    }
    this.twiddle = this.buffer(n * 4, storage, tw);
    this.readback = this.buffer(
      this.count * 8,
      GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST,
    );
    this.controlRead = this.buffer(
      32,
      GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST,
    );
    this.modes = {};
    for (const [name, data] of Object.entries({
      imag: [0, 0, 0, 0],
      held: [1, 0, 0, 0],
      free: [1, 1, 0, 0],
      analysis: [2, 0, 0, 0],
      ...Object.fromEntries(
        [0, 1, 2].flatMap((a) =>
          [0, 1].map((inv) => [`fft${a}${inv}`, [a, inv, 0, 0]]),
        ),
      ),
    }))
      this.modes[name] = this.buffer(
        16,
        GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
        new Uint32Array(data),
      );
    this.layout = this.device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "read-only-storage" },
        },
        {
          binding: 1,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "storage" },
        },
        {
          binding: 2,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "storage" },
        },
        {
          binding: 3,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "uniform" },
        },
        {
          binding: 4,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "read-only-storage" },
        },
        {
          binding: 5,
          visibility: GPUShaderStage.COMPUTE,
          buffer: { type: "storage" },
        },
      ],
    });
    const num = (v) => Number(v).toExponential(12);
    const shader = `
const N:u32=${n}u; const TOTAL:u32=${this.count}u; const LOGN:u32=${Math.log2(n)}u;
const DX:f32=${num(this.dx)}; const DV:f32=${num(this.dx ** 3)};
const DT:f32=${num(c.dt)}; const TAU:f32=${num(c.preparation_dt)};
const G:f32=${num(this.g)}; const W:vec3f=vec3f(${this.w.map(num).join(",")});
const DK:f32=${num((2 * Math.PI) / c.length)};
@group(0) @binding(0) var<storage,read> src:array<vec2f>;
@group(0) @binding(1) var<storage,read_write> dst:array<vec2f>;
@group(0) @binding(2) var<storage,read_write> ctl:array<f32>;
@group(0) @binding(3) var<uniform> mode:vec4u;
@group(0) @binding(4) var<storage,read> tw:array<vec2f>;
@group(0) @binding(5) var<storage,read_write> sums:array<vec2f>;
fn multiply(a:vec2f,b:vec2f)->vec2f{return vec2f(a.x*b.x-a.y*b.y,a.x*b.y+a.y*b.x);}
fn coords(i:u32)->vec3u{return vec3u(i/(N*N),(i/N)%N,i%N);}
fn trap(i:u32)->f32{let r=(vec3f(coords(i))-vec3f(f32(N)/2.))*DX;return .5*dot(W*r,W*r);}
fn k2(i:u32)->f32{let q=coords(i);let k=vec3f(select(vec3i(q),vec3i(q)-vec3i(i32(N)),q>=vec3u(N/2u)))*DK;return dot(k,k);}
fn address(line:u32,t:u32)->u32{
 if(mode.x==0u){return t*N*N+(line/N)*N+line%N;}
 if(mode.x==1u){return (line/N)*N*N+t*N+line%N;}
 return line*N+t;
}
var<workgroup> lineData:array<vec2f,${n}>;
@compute @workgroup_size(${n})
fn fft(@builtin(workgroup_id) group:vec3u,@builtin(local_invocation_index) tid:u32){
 let rev=reverseBits(tid)>>(32u-LOGN);lineData[rev]=src[address(group.x,tid)];workgroupBarrier();
 for(var size=2u;size<=N;size*=2u){
  let half=size/2u;let j=tid%half;let first=(tid/size)*size+j;
  var phase=tw[j*(N/size)];if(mode.y==1u){phase.y=-phase.y;}
  let a=lineData[first];let b=multiply(phase,lineData[first+half]);
  let value=a+select(b,-b,(tid%size)>=half);
  workgroupBarrier();lineData[tid]=value;workgroupBarrier();
 }
 var value=lineData[tid];if(mode.y==1u){value/=f32(N);}
 let at=address(group.x,tid);dst[at]=value;
}
@compute @workgroup_size(256)
fn local(@builtin(global_invocation_id) id:vec3u){
 let i=id.x;if(i>=TOTAL){return;}let p=src[i];let density=dot(p,p);
 if(mode.x==0u){
  let v=trap(i)-ctl[1];let z=TAU*v;let ex=exp(-z);
  var ratio=TAU*(1.-z/2.+z*z/6.-z*z*z/24.+z*z*z*z/120.);
  if(abs(z)>.01){ratio=(1.-ex)/v;}
  dst[i]=p*sqrt(ex/(1.+G*density*ratio));
 }else{
  let v=select(trap(i),0.,mode.y==1u)+G*density;let angle=-.5*DT*v;
  dst[i]=multiply(p,vec2f(cos(angle),sin(angle)));
 }
}
@compute @workgroup_size(256)
fn kinetic(@builtin(global_invocation_id) id:vec3u){
 let i=id.x;if(i>=TOTAL){return;}
 let energy=.5*k2(i);
 if(mode.x==0u){dst[i]=src[i]*exp(-TAU*energy);}
 else if(mode.x==2u){dst[i]=src[i]*energy;}
 else{let angle=-DT*energy;dst[i]=multiply(src[i],vec2f(cos(angle),sin(angle)));}
}
var<workgroup> reduction:array<vec2f,256>;
@compute @workgroup_size(256)
fn partial(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) tid:u32,@builtin(workgroup_id) group:vec3u){
 var v=vec2f(0.);if(id.x<TOTAL){let p=dot(src[id.x],src[id.x])*DV;let q=coords(id.x);let band=max(2u,N/16u);v=vec2f(p,select(0.,p,any(q<vec3u(band))||any(q>=vec3u(N-band))));}
 reduction[tid]=v;workgroupBarrier();
 for(var stride=128u;stride>0u;stride/=2u){if(tid<stride){reduction[tid]+=reduction[tid+stride];}workgroupBarrier();}
 if(tid==0u){sums[group.x]=reduction[0];}
}
@compute @workgroup_size(256)
fn total(@builtin(local_invocation_index) tid:u32){
 var v=vec2f(0.);for(var i=tid;i<(TOTAL+255u)/256u;i+=256u){v+=sums[i];}
 reduction[tid]=v;workgroupBarrier();
 for(var stride=128u;stride>0u;stride/=2u){if(tid<stride){reduction[tid]+=reduction[tid+stride];}workgroupBarrier();}
 if(tid==0u){ctl[0]=reduction[0].x;ctl[2]=reduction[0].y;if(mode.x==0u){ctl[1]-=log(ctl[0])/(2.*TAU);}}
}
@compute @workgroup_size(256)
fn normalize(@builtin(global_invocation_id) id:vec3u){if(id.x<TOTAL){dst[id.x]=src[id.x]/sqrt(ctl[0]);}}
`;
    const module = this.device.createShaderModule({ code: shader });
    const info = await module.getCompilationInfo();
    const errors = info.messages.filter((m) => m.type === "error");
    if (errors.length) throw Error(errors.map((m) => m.message).join("\n"));
    const layout = this.device.createPipelineLayout({
      bindGroupLayouts: [this.layout],
    });
    this.pipelines = {};
    for (const entry of [
      "fft",
      "local",
      "kinetic",
      "partial",
      "total",
      "normalize",
    ])
      this.pipelines[entry] = await this.device.createComputePipelineAsync({
        layout,
        compute: { module, entryPoint: entry },
      });
    this.bindings = new Map();
    const initial = new Float32Array(this.count * 2);
    let norm = 0;
    for (let i = 0; i < this.count; i++) {
      const x = this.x[Math.floor(i / n ** 2)],
        y = this.x[Math.floor(i / n) % n],
        z = this.x[i % n];
      const trap =
        0.5 *
        ((this.w[0] * x) ** 2 + (this.w[1] * y) ** 2 + (this.w[2] * z) ** 2);
      const v = this.g
        ? Math.sqrt(Math.max(this.muTF - trap, 0) / this.g)
        : Math.exp(
            -0.5 * (this.w[0] * x * x + this.w[1] * y * y + this.w[2] * z * z),
          );
      initial[i * 2] = v;
      norm += v * v * this.dx ** 3;
    }
    const scale = 1 / Math.sqrt(norm);
    for (let i = 0; i < this.count; i++) initial[i * 2] *= scale;
    this.device.queue.writeBuffer(this.fields[0], 0, initial);
  }
  bind(pair, index, mode) {
    const key = `${pair === this.fields ? "field" : "analysis"}:${index}:${mode}`;
    if (!this.bindings.has(key))
      this.bindings.set(
        key,
        this.device.createBindGroup({
          layout: this.layout,
          entries: [
            pair[index],
            pair[1 - index],
            this.control,
            this.modes[mode],
            this.twiddle,
            this.partial,
          ].map((buffer, binding) => ({ binding, resource: { buffer } })),
        }),
      );
    return this.bindings.get(key);
  }
  dispatch(encoder, entry, pair, index, mode, count) {
    const pass = encoder.beginComputePass();
    pass.setPipeline(this.pipelines[entry]);
    pass.setBindGroup(0, this.bind(pair, index, mode));
    pass.dispatchWorkgroups(count);
    pass.end();
  }
  fft(encoder, pair, index, inverse = false) {
    for (let axis = 0; axis < 3; axis++) {
      this.dispatch(
        encoder,
        "fft",
        pair,
        index,
        `fft${axis}${Number(inverse)}`,
        this.n ** 2,
      );
      index = 1 - index;
    }
    return index;
  }
  encodeStep(encoder, imaginary = false) {
    const mode = imaginary
        ? "imag"
        : this.releaseStep === null
          ? "held"
          : "free",
      groups = Math.ceil(this.count / 256);
    let index = this.index;
    const pair = this.fields;
    this.dispatch(encoder, "local", pair, index, mode, groups);
    index = 1 - index;
    index = this.fft(encoder, pair, index);
    this.dispatch(encoder, "kinetic", pair, index, mode, groups);
    index = 1 - index;
    index = this.fft(encoder, pair, index, true);
    this.dispatch(encoder, "local", pair, index, mode, groups);
    index = 1 - index;
    if (imaginary) {
      this.dispatch(encoder, "partial", pair, index, mode, groups);
      this.dispatch(encoder, "total", pair, index, mode, 1);
      this.dispatch(encoder, "normalize", pair, index, mode, groups);
      index = 1 - index;
    }
    this.index = index;
  }
  async read(buffer, target = this.readback) {
    this.check();
    const encoder = this.device.createCommandEncoder();
    encoder.copyBufferToBuffer(buffer, 0, target, 0, buffer.size);
    this.device.queue.submit([encoder.finish()]);
    await target.mapAsync(GPUMapMode.READ);
    const values = new Float32Array(target.getMappedRange().slice(0));
    target.unmap();
    this.check();
    return values;
  }
  async readField() {
    return this.read(this.fields[this.index]);
  }
  async prepare(progress) {
    let previous = await this.readField(),
      change = 0,
      iterations = 0;
    if (this.g) {
      for (iterations = 50; iterations <= 6000; iterations += 50) {
        this.check();
        const encoder = this.device.createCommandEncoder();
        for (let k = 0; k < 50; k++) this.encodeStep(encoder, true);
        this.device.queue.submit([encoder.finish()]);
        const current = await this.readField();
        let delta = 0;
        for (let i = 0; i < current.length; i++)
          delta += (current[i] - previous[i]) ** 2;
        change = Math.sqrt(delta * this.dx ** 3);
        if (!Number.isFinite(change))
          throw Error("GPU preparation became non-finite.");
        progress(
          `Preparing on GPU · ${iterations} iterations · change ${change.toExponential(2)}`,
        );
        if (change < 3e-6) break;
        previous = current;
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      if (iterations > 6000)
        throw Error(
          "Single-precision GPU preparation did not converge. Choose CPU reference for this setting.",
        );
    }
    const field = await this.readField(),
      kinetic = await this.kineticField();
    let mu = 0,
      norm = 0;
    for (let i = 0; i < this.count; i++) {
      const p = field[i * 2] ** 2 + field[i * 2 + 1] ** 2;
      const v = this.trapAt(i) + this.g * p;
      mu +=
        (field[i * 2] * kinetic[i * 2] +
          field[i * 2 + 1] * kinetic[i * 2 + 1] +
          v * p) *
        this.dx ** 3;
      norm += p * this.dx ** 3;
    }
    mu /= norm;
    let residual = 0;
    for (let i = 0; i < this.count; i++) {
      const p = field[i * 2] ** 2 + field[i * 2 + 1] ** 2,
        v = this.trapAt(i) + this.g * p - mu;
      residual +=
        (kinetic[i * 2] + v * field[i * 2]) ** 2 +
        (kinetic[i * 2 + 1] + v * field[i * 2 + 1]) ** 2;
    }
    residual = Math.sqrt(residual * this.dx ** 3) / Math.abs(mu);
    if (!Number.isFinite(residual) || residual > 5e-4)
      throw Error(
        `GPU stationary residual ${residual.toExponential(2)} is too large; use CPU reference.`,
      );
    this.preparation = {
      kind: this.g
        ? "WebGPU float32 imaginary-time ground state"
        : "WebGPU float32 analytic oscillator",
      iterations,
      dt: this.config.preparation_dt,
      iterate_l2_change: change,
      relative_stationary_residual: residual,
      chemical_potential: mu,
    };
  }
  trapAt(i) {
    const n = this.n;
    return (
      0.5 *
      ((this.w[0] * this.x[Math.floor(i / n ** 2)]) ** 2 +
        (this.w[1] * this.x[Math.floor(i / n) % n]) ** 2 +
        (this.w[2] * this.x[i % n]) ** 2)
    );
  }
  async kineticField() {
    const encoder = this.device.createCommandEncoder();
    encoder.copyBufferToBuffer(
      this.fields[this.index],
      0,
      this.analysis[0],
      0,
      this.count * 8,
    );
    let index = this.fft(encoder, this.analysis, 0);
    this.dispatch(
      encoder,
      "kinetic",
      this.analysis,
      index,
      "analysis",
      Math.ceil(this.count / 256),
    );
    index = 1 - index;
    index = this.fft(encoder, this.analysis, index, true);
    this.device.queue.submit([encoder.finish()]);
    return this.read(this.analysis[index]);
  }
  async reset() {
    this.check();
    this.device.queue.writeBuffer(this.fields[0], 0, this.initial);
    this.index = 0;
    this.steps = 0;
    this.releaseStep = null;
    this.complete = false;
    this.warning = "";
    this.history = [];
    this.lastBatchSeconds = 0;
    await this.record();
  }
  async release() {
    if (this.releaseStep === null) {
      this.releaseStep = this.steps;
      this.complete = false;
      await this.record();
    }
  }
  async advance(count = 8) {
    if (!Number.isInteger(count) || count < 1 || count > 20)
      throw Error("Step count must be 1–20.");
    const started = performance.now();
    for (let k = 0; k < count && !this.complete && !this.warning; k++) {
      this.check();
      const encoder = this.device.createCommandEncoder();
      this.encodeStep(encoder);
      this.dispatch(
        encoder,
        "partial",
        this.fields,
        this.index,
        "free",
        Math.ceil(this.count / 256),
      );
      this.dispatch(encoder, "total", this.fields, this.index, "free", 1);
      this.device.queue.submit([encoder.finish()]);
      const control = await this.read(this.control, this.controlRead);
      this.steps++;
      if (!Number.isFinite(control[0]) || Math.abs(control[0] - 1) > 0.001)
        this.warning =
          "Single-precision norm drift exceeded 0.1%. Use CPU reference or a shorter run.";
      else if (control[2] > 0.001)
        this.warning =
          "Cloud reached the periodic boundary region. Increase the box and grid.";
      this.complete =
        this.steps - (this.releaseStep ?? 0) >=
        Math.round(this.config.duration / this.config.dt);
    }
    this.lastBatchSeconds = (performance.now() - started) / 1000;
    await this.record();
  }
  async record() {
    this.field = await this.readField();
    const h = await this.kineticField(),
      p = new Float64Array(this.count);
    let norm = 0,
      edge = 0,
      kinetic = 0,
      potential = 0,
      interaction = 0,
      peak = 0;
    const moment = [0, 0, 0],
      second = [0, 0, 0],
      n = this.n,
      dv = this.dx ** 3,
      band = Math.max(2, n / 16);
    for (let i = 0; i < this.count; i++) {
      const density = this.field[2 * i] ** 2 + this.field[2 * i + 1] ** 2;
      p[i] = density;
      peak = Math.max(peak, density);
      const mass = density * dv;
      norm += mass;
      const q = [Math.floor(i / n ** 2), Math.floor(i / n) % n, i % n];
      if (q.some((v) => v < band || v >= n - band)) edge += mass;
      for (let a = 0; a < 3; a++) {
        const x = this.x[q[a]];
        moment[a] += mass * x;
        second[a] += mass * x * x;
      }
      kinetic +=
        (this.field[2 * i] * h[2 * i] + this.field[2 * i + 1] * h[2 * i + 1]) *
        dv;
      if (this.releaseStep === null) potential += this.trapAt(i) * mass;
      interaction += 0.5 * this.g * density * mass;
    }
    const widths = second.map((v, i) =>
      Math.sqrt(Math.max(0, v / norm - (moment[i] / norm) ** 2)),
    );
    this.density = p;
    this.diagnostics = {
      time: this.steps * this.config.dt,
      steps: this.steps,
      norm,
      widths,
      aspect_xz: widths[0] / widths[2],
      aspect_yz: widths[1] / widths[2],
      energy: kinetic + potential + interaction,
      kinetic,
      potential,
      interaction_energy: interaction,
      edge_probability: edge,
      released: this.releaseStep !== null,
      peak_density: peak,
    };
    this.history.push(this.diagnostics);
  }
  reference() {
    if (!this.g) return null;
    const widths = this.w.map(
      (w) => Math.sqrt(2 * this.muTF) / (w * Math.sqrt(7)),
    );
    const rhs = (y) => [
      ...y.slice(3),
      ...this.w.map((w, i) => (w * w) / (y[i] * y[0] * y[1] * y[2])),
    ];
    let t = 0,
      y = [1, 1, 1, 0, 0, 0];
    const scales = [];
    for (const d of this.history) {
      const target =
        this.releaseStep === null
          ? 0
          : Math.max(0, (d.steps - this.releaseStep) * this.config.dt);
      while (t < target - 1e-12) {
        const dt = Math.min(0.005, target - t),
          a = rhs(y),
          b = rhs(y.map((v, i) => v + (dt * a[i]) / 2)),
          c = rhs(y.map((v, i) => v + (dt * b[i]) / 2)),
          e = rhs(y.map((v, i) => v + dt * c[i]));
        y = y.map((v, i) => v + (dt * (a[i] + 2 * b[i] + 2 * c[i] + e[i])) / 6);
        t += dt;
      }
      scales.push(y.slice(0, 3));
    }
    return {
      chemical_potential: this.muTF,
      initial_widths: widths,
      scales,
      widths: scales.map((b) => b.map((v, i) => v * widths[i])),
    };
  }
  snapshot() {
    const n = this.n,
      p = this.density,
      mid = n / 2,
      factor = n / 32,
      nv = 32;
    const slices = Array.from({ length: 3 }, () =>
        Array.from({ length: n }, () => Array(n).fill(0)),
      ),
      columns = Array.from({ length: 3 }, () =>
        Array.from({ length: n }, () => Array(n).fill(0)),
      ),
      volume = Array(nv ** 3).fill(0);
    for (let x = 0; x < n; x++)
      for (let y = 0; y < n; y++)
        for (let z = 0; z < n; z++) {
          const v = p[(x * n + y) * n + z];
          if (z === mid) slices[0][y][x] = v;
          if (y === mid) slices[1][z][x] = v;
          if (x === mid) slices[2][z][y] = v;
          columns[0][y][x] += v * this.dx;
          columns[1][z][x] += v * this.dx;
          columns[2][z][y] += v * this.dx;
          volume[
            (Math.floor(x / factor) * nv + Math.floor(y / factor)) * nv +
              Math.floor(z / factor)
          ] += v / factor ** 3;
        }
    const first = this.history[0];
    return {
      config: this.config,
      scales: this.scales,
      x: this.x,
      slices,
      columns,
      volume,
      volume_n: nv,
      volume_stride: factor,
      volume_centers: Array.from(
        { length: nv },
        (_, i) => this.x[i * factor] + ((factor - 1) * this.dx) / 2,
      ),
      diagnostics: this.diagnostics,
      history: this.history,
      tf: this.reference(),
      tf_kinetic_ratio:
        first.kinetic / Math.max(first.interaction_energy, 1e-30),
      preparation: this.preparation,
      warning: this.warning,
      complete: this.complete,
      last_batch_seconds: this.lastBatchSeconds,
      backend: {
        type: "webgpu",
        precision: "complex-f32",
        adapter: this.adapter,
      },
    };
  }
  export() {
    const n = this.n,
      real = [],
      imag = [];
    for (let x = 0; x < n; x++) {
      const r = [],
        im = [];
      for (let y = 0; y < n; y++) {
        const rr = [],
          ii = [];
        for (let z = 0; z < n; z++) {
          const i = ((x * n + y) * n + z) * 2;
          rr.push(this.field[i]);
          ii.push(this.field[i + 1]);
        }
        r.push(rr);
        im.push(ii);
      }
      real.push(r);
      imag.push(im);
    }
    return {
      schema: "coldatomlab-webgpu-3d-v1",
      version: "0.6.0",
      config: this.config,
      array_order: "x,y,z",
      wavefunction_normalization: "integral |psi|^2 dX dY dZ = 1",
      scales: this.scales,
      x: this.x,
      steps: this.steps,
      release_step: this.releaseStep,
      preparation: this.preparation,
      history: this.history,
      backend: {
        type: "webgpu",
        precision: "complex-f32",
        adapter: this.adapter,
      },
      psi_real: real,
      psi_imag: imag,
    };
  }
};
