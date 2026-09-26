"use strict";
window.VortexGPU = class extends GPUCloud3D {
  static async create(input, progress = () => {}) {
    const c = VortexModel.validate(input),
      s = new VortexGPU();
    s.vortex = c;
    const a = Math.sqrt(
      6.62607015e-34 /
        (2 * Math.PI) /
        (1.443160895e-25 * 2 * Math.PI * c.radial_hz),
    );
    s.config = {
      ...Interferometry3D.defaults,
      n: c.n,
      length: c.length,
      dt: c.dt,
      atoms: c.atoms,
      scattering_nm: ((c.g * a) / (4 * Math.PI * c.atoms)) * 1e9,
      reference_hz: c.radial_hz,
      fx_hz: c.radial_hz,
      fy_hz: c.radial_hz,
      fz_hz: c.axial_hz,
      duration: Math.min(c.duration, 4),
      preparation_dt: 0.002,
      experiment: "single",
    };
    s.scales = GPUCloud3D.validate(s.config);
    s.units = {
      length_um: a * 1e6,
      time_ms: 1000 / (2 * Math.PI * c.radial_hz),
      energy_hz: c.radial_hz,
      circulation_um2_ms:
        2 * Math.PI * a * a * (2 * Math.PI * c.radial_hz) * 1e9,
    };
    try {
      if (!navigator.gpu)
        throw Error(
          "WebGPU unavailable. Use hardware-accelerated Chrome or Edge on HTTPS or localhost.",
        );
      const adapter = await navigator.gpu.requestAdapter({
        powerPreference: "high-performance",
      });
      if (!adapter || adapter.info.isFallbackAdapter)
        throw Error(
          "No hardware WebGPU adapter available. Enable browser hardware acceleration.",
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
      if (c.stationary && c.charge) {
        const seed = await s.readField();
        let norm = 0;
        for (let i = 0; i < s.count; i++) {
          const x = s.x[Math.floor(i / s.n ** 2)],
            y = s.x[Math.floor(i / s.n) % s.n];
          const re = seed[2 * i],
            im = seed[2 * i + 1];
          seed[2 * i] = re * x - im * c.charge * y;
          seed[2 * i + 1] = im * x + re * c.charge * y;
          norm += (seed[2 * i] ** 2 + seed[2 * i + 1] ** 2) * s.dx ** 3;
        }
        for (let i = 0; i < seed.length; i++) seed[i] /= Math.sqrt(norm);
        s.device.queue.writeBuffer(s.fields[s.index], 0, seed);
      }
      await s.prepare(progress);
      if (c.stationary && c.charge)
        s.preparation.kind =
          "WebGPU stationary centered C4 charge-sector vortex";
      const field = await s.readField();
      if (c.charge && !c.stationary) {
        let peak = 0,
          norm = 0;
        for (let i = 0; i < s.count; i++)
          peak = Math.max(peak, field[2 * i] ** 2 + field[2 * i + 1] ** 2);
        const xi = c.g ? 1 / Math.sqrt(2 * c.g * peak) : 0;
        for (let i = 0; i < s.count; i++) {
          const x = s.x[Math.floor(i / s.n ** 2)],
            y = s.x[Math.floor(i / s.n) % s.n],
            d = c.g ? Math.sqrt(x * x + y * y + xi * xi) : 1;
          const re = field[2 * i],
            im = field[2 * i + 1];
          field[2 * i] = (re * x - im * c.charge * y) / d;
          field[2 * i + 1] = (im * x + re * c.charge * y) / d;
          norm += (field[2 * i] ** 2 + field[2 * i + 1] ** 2) * s.dx ** 3;
        }
        for (let i = 0; i < field.length; i++) field[i] /= Math.sqrt(norm); // preparation only
      }
      s.preparation = {
        prepared_state: s.preparation,
        ground_state: c.stationary && c.charge ? null : s.preparation,
        kind:
          c.stationary && c.charge
            ? "Stationary centered C4 charge-sector vortex"
            : c.charge
              ? c.g
                ? "Prescribed interacting vortex imprint (not stationary)"
                : "Analytic oscillator vortex"
              : "Vortex-free oscillator / interacting ground state",
      };
      s.initial = field;
      await s.reset();
      if (s.history[0].edge_probability > 1e-5)
        throw Error(
          "Prepared cloud reaches the boundary. Increase box and grid together.",
        );
      return s;
    } catch (e) {
      s.destroy();
      throw e;
    }
  }
  drivenShader(num) {
    const c = this.vortex;
    return `fn driven(i:u32)->f32{let r=(vec3f(coords(i))-vec3f(f32(N)/2.))*DX;let t=ctl[3];let a=clamp(min(t/${num(c.ramp)},(${num(c.stir_time)}-t)/${num(c.ramp)}),0.,1.);let h=${num(c.height)}*pow(sin(1.57079632679*a),2.);let center=${num(c.radius)}*vec2f(cos(${num(c.omega)}*t),sin(${num(c.omega)}*t));let d=r.xy-center;return trap(i)+h*exp(-.5*dot(d,d)/${num(c.width * c.width)});}`;
  }
  async initialize() {
    await super.initialize();
    const code = `@group(0) @binding(0) var<storage,read> src:array<vec2f>;@group(0) @binding(1) var<storage,read_write> dst:array<vec2f>;@group(0) @binding(3) var<uniform> mode:vec4u;
    @compute @workgroup_size(256) fn derivative(@builtin(global_invocation_id) id:vec3u){let i=id.x;if(i>=${this.count}u){return;}let n=${this.n}u;let q=select((i/n)%n,i/(n*n),mode.x==0u);let k=f32(select(i32(q),i32(q)-i32(n),q>=n/2u))*${((2 * Math.PI) / this.config.length).toExponential(12)};dst[i]=vec2f(-src[i].y,src[i].x)*k;}`;
    const module = this.device.createShaderModule({ code });
    const errors = (await module.getCompilationInfo()).messages.filter(
      (m) => m.type === "error",
    );
    if (errors.length) throw Error(errors.map((m) => m.message).join("\n"));
    this.pipelines.derivative = await this.device.createComputePipelineAsync({
      layout: this.device.createPipelineLayout({
        bindGroupLayouts: [this.layout],
      }),
      compute: { module, entryPoint: "derivative" },
    });
    const projection = this.device.createShaderModule({
      code: `
      @group(0) @binding(0) var<storage,read> src:array<vec2f>;
      @group(0) @binding(1) var<storage,read_write> dst:array<vec2f>;
      @compute @workgroup_size(256) fn project(@builtin(global_invocation_id) id:vec3u){
        let at=id.x; if(at>=${this.count}u){return;}
        let n=${this.n}u; let x=at/(n*n); let y=(at/n)%n; let z=at%n;
        let nx=(n-x)%n; let ny=(n-y)%n;
        let a=src[at]; let b=src[(ny*n+x)*n+z];
        let c=src[(nx*n+ny)*n+z]; let d=src[(y*n+nx)*n+z];
        dst[at]=(a-c+${Number(this.vortex.charge).toFixed(1)}*vec2f(b.y-d.y,d.x-b.x))*.25;
      }`,
    });
    this.pipelines.project = await this.device.createComputePipelineAsync({
      layout: this.device.createPipelineLayout({
        bindGroupLayouts: [this.layout],
      }),
      compute: { module: projection, entryPoint: "project" },
    });
  }
  projectPreparation(encoder, pair, index, mode, groups) {
    if (!this.vortex.stationary || !this.vortex.charge) return index;
    this.dispatch(encoder, "project", pair, index, mode, groups);
    return 1 - index;
  }
  async derivative(axis) {
    const e = this.device.createCommandEncoder();
    e.copyBufferToBuffer(
      this.fields[this.index],
      0,
      this.analysis[0],
      0,
      this.count * 8,
    );
    let i = this.fft(e, this.analysis, 0);
    this.dispatch(
      e,
      "derivative",
      this.analysis,
      i,
      `fft${axis}0`,
      Math.ceil(this.count / 256),
    );
    i = 1 - i;
    i = this.fft(e, this.analysis, i, true);
    this.device.queue.submit([e.finish()]);
    return this.read(this.analysis[i]);
  }
  async release() {
    this.check();
    if (this.warning)
      throw Error("Resolve the stopping condition before release.");
    if (this.releaseStep === null) {
      this.releaseStep = this.steps;
      this.complete = false;
      await this.record();
    }
  }
  async advance(count = 20) {
    if (!Number.isInteger(count) || count < 1 || count > 20)
      throw Error("Step count must be 1–20.");
    const c = this.vortex;
    for (let k = 0; k < count && !this.complete && !this.warning; k++) {
      this.check();
      this.device.queue.writeBuffer(
        this.control,
        12,
        new Float32Array([(this.steps + 0.5) * c.dt]),
      );
      const e = this.device.createCommandEncoder();
      this.encodeStep(e);
      this.dispatch(
        e,
        "partial",
        this.fields,
        this.index,
        "held",
        Math.ceil(this.count / 256),
      );
      this.dispatch(e, "total", this.fields, this.index, "held", 1);
      this.device.queue.submit([e.finish()]);
      this.steps++;
      // Check every step; no real-time rescaling can hide drift.
      const [norm, , edge] = await this.read(this.control, this.controlRead);
      if (!Number.isFinite(norm) || Math.abs(norm - 1) > 0.001)
        this.warning = "Stopped: norm drift exceeds 0.001.";
      else if (!Number.isFinite(edge) || edge > 0.001)
        this.warning =
          "Stopped: boundary probability exceeds 0.001. Increase box and grid together.";
      this.complete =
        this.steps >=
        (this.releaseStep === null
          ? Math.round(c.duration / c.dt)
          : this.releaseStep + Math.round(c.tof_duration / c.dt));
    }
    await this.record();
  }
  async record() {
    const c = this.vortex,
      n = this.n,
      field = await this.readField(),
      kin = await this.kineticField(),
      gx = await this.derivative(0),
      gy = await this.derivative(1),
      dv = this.dx ** 3,
      band = Math.max(2, n / 16);
    const moment = [0, 0, 0],
      square = [0, 0, 0];
    let norm = 0,
      energy = 0,
      lz = 0,
      edge = 0;
    const [h, bx, by] = VortexModel.drive(c, this.steps * c.dt);
    for (let i = 0; i < this.count; i++) {
      const ix = Math.floor(i / n ** 2),
        iy = Math.floor(i / n) % n,
        iz = i % n,
        x = this.x[ix],
        y = this.x[iy],
        re = field[2 * i],
        im = field[2 * i + 1],
        p = re * re + im * im;
      const v =
        this.releaseStep !== null
          ? 0
          : this.trapAt(i) +
            h *
              Math.exp((-0.5 * ((x - bx) ** 2 + (y - by) ** 2)) / c.width ** 2);
      norm += p * dv;
      [x, y, this.x[iz]].forEach((v, a) => {
        moment[a] += v * p * dv;
        square[a] += v * v * p * dv;
      });
      energy +=
        (re * kin[2 * i] + im * kin[2 * i + 1] + v * p + 0.5 * c.g * p * p) *
        dv;
      lz +=
        (re * (x * gy[2 * i + 1] - y * gx[2 * i + 1]) -
          im * (x * gy[2 * i] - y * gx[2 * i])) *
        dv;
      if (
        ix < band ||
        iy < band ||
        iz < band ||
        ix >= n - band ||
        iy >= n - band ||
        iz >= n - band
      )
        edge += p * dv;
    }
    const d = {
      steps: this.steps,
      time: this.steps * c.dt,
      norm,
      energy,
      lz: lz / norm,
      edge_probability: edge,
      paper_core:
        c.stationary && c.charge && c.height === 0
          ? VortexModel.core(field, c)
          : null,
      widths: square.map((v, a) =>
        Math.sqrt(Math.max(0, v / norm - (moment[a] / norm) ** 2)),
      ),
      ...VortexModel.topology(field, c, gx, gy),
    };
    this.field = field;
    this.gx = gx;
    this.gy = gy;
    if (this.history.at(-1)?.steps === this.steps) this.history.pop();
    this.history.push(d);
    return d;
  }
  surface() {
    const m = Math.min(32, this.n),
      stride = this.n / m,
      volume = new Float32Array(m ** 3);
    for (let i = 0; i < m; i++)
      for (let j = 0; j < m; j++)
        for (let k = 0; k < m; k++) {
          const at =
            2 * ((i * stride * this.n + j * stride) * this.n + k * stride);
          volume[(i * m + j) * m + k] =
            this.field[at] ** 2 + this.field[at + 1] ** 2;
        }
    return {
      volume,
      volume_n: m,
      volume_centers: Array.from({ length: m }, (_, i) => this.x[i * stride]),
      config: this.vortex,
    };
  }
  export() {
    this.check();
    if (this.history.at(-1)?.steps !== this.steps)
      throw Error(
        "The last GPU step has no verified readback. Reset or prepare again before exporting.",
      );
    return {
      schema: "coldatomlab-vortex-v3",
      version: "0.18.0",
      release_step: this.releaseStep,
      array_order: "x,y,z interleaved real,imag",
      config: { ...this.vortex },
      scales: { ...this.units },
      backend: { kind: "WebGPU float32", ...this.adapter },
      preparation: structuredClone(this.preparation),
      steps: this.steps,
      initial: Array.from(this.initial),
      field: Array.from(this.field),
      history: structuredClone(this.history),
      warning: this.warning,
    };
  }
};
