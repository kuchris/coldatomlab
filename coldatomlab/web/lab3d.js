"use strict";
(() => {
  const el = (id) => document.getElementById(`three-${id}`);
  const keys = [
    "n",
    "length",
    "dt",
    "atoms",
    "scattering_nm",
    "reference_hz",
    "fx_hz",
    "fy_hz",
    "fz_hz",
    "duration",
    "preparation_dt",
    ...Object.keys(Interferometry3D.defaults),
  ];
  const base = {
    ...Interferometry3D.defaults,
    n: 64,
    length: 24,
    dt: 0.004,
    atoms: 20000,
    scattering_nm: 5.3,
    reference_hz: 30,
    fx_hz: 30,
    fy_hz: 42,
    fz_hz: 21,
    duration: 2,
    preparation_dt: 0.002,
  };
  const presets = {
    interacting: base,
    gaussian: { ...base, n: 48, scattering_nm: 0 },
    tf: { ...base, n: 96, length: 48, atoms: 150000, duration: 3 },
    pair: {
      ...base,
      length: 32,
      experiment: "pair",
      scattering_nm: 0,
      duration: 3,
    },
    opposite: {
      ...base,
      length: 32,
      experiment: "pair",
      scattering_nm: 0,
      duration: 3,
      relative_phase: Math.PI,
    },
    sequence: { ...base, experiment: "sequence", atoms: 2000, dt: 0.006 },
    camera: {
      ...base,
      length: 32,
      experiment: "pair",
      scattering_nm: 0,
      atoms: 2000,
      duration: 3,
      relative_phase: 0.7,
    },
    reverse: {
      ...base,
      experiment: "sequence",
      atoms: 2000,
      dt: 0.006,
      hold_bias: -1,
    },
  };
  let snapshot = null,
    gpuRun = null,
    session = null,
    busy = false,
    running = false,
    dirty = false,
    renderer = null,
    view = "slices";
  let pinned = null;
  let generation = 0;
  const cameraPanel = new window.Camera3DPanel(
    el("results"),
    () => request("export"),
    (locked) => {
      busy = locked;
      controls();
    },
  );
  const scanPanel = new window.Scan3DPanel(el("results"), (locked) => {
    busy = locked;
    controls();
  });
  const f = (x, n = 3) => Number(x).toFixed(n);
  function controls() {
    cameraPanel.update(snapshot, running, busy, generation);
    scanPanel.update(running || busy);
    const experiment = el("experiment").value;
    for (const node of el("duration").closest("label").childNodes) {
      if (
        node.nodeType === Node.TEXT_NODE &&
        node.textContent.includes("duration")
      )
        node.textContent = `${experiment === "sequence" ? "Expansion" : "Evolution"} duration / ω₀⁻¹`;
    }
    const detail = el("separation").closest("details");
    detail.hidden = experiment === "single";
    detail.querySelector("summary").textContent =
      experiment === "pair"
        ? "Coherent pair settings"
        : "Split and hold settings";
    el("separation").closest(".pair").hidden = experiment !== "pair";
    for (const key of ["barrier_height", "split_time"])
      el(key).closest(".pair").hidden = experiment !== "sequence";
    el("hold_bias").closest("label").hidden = experiment !== "sequence";
    el("parameters").disabled = busy || running;
    el("prepare").disabled = busy || running;
    el("reset").disabled = !snapshot || busy || running;
    el("step").disabled =
      !snapshot ||
      busy ||
      running ||
      dirty ||
      snapshot.complete ||
      !!snapshot.warning;
    el("release").disabled =
      !snapshot ||
      busy ||
      running ||
      dirty ||
      snapshot.diagnostics.released ||
      snapshot.config.experiment !== "single" ||
      !!snapshot.warning;
    el("run").disabled =
      !snapshot ||
      (!running && (busy || dirty || snapshot.complete || !!snapshot.warning));
    el("export").disabled = !snapshot || busy || running;
    el("pin").disabled = !snapshot || busy || running;
    el("clear-pin").disabled = !pinned || busy || running;
    el("export-pair").disabled = !pinned || !snapshot || busy || running;
    el("run").textContent = running ? "Ⅱ Pause" : "▶ Run";
    el("status").textContent = running
      ? "Running"
      : busy
        ? "Working…"
        : dirty
          ? "Settings pending"
          : !snapshot
            ? "Not prepared"
            : snapshot.warning
              ? "Stopped"
              : snapshot.complete
                ? "Complete"
                : snapshot.diagnostics.steps
                  ? "Paused"
                  : "Ready";
  }
  async function request(action, extra = {}) {
    const engine =
      action === "prepare"
        ? el("engine").value
        : snapshot?.backend?.type || "cpu";
    if (engine === "webgpu") {
      if (action === "prepare") {
        const next = await window.GPUCloud3D.create(extra.config, (message) => {
          el("prepare-note").textContent = message;
        });
        gpuRun?.destroy();
        gpuRun = next;
      } else {
        if (!gpuRun) throw new Error("Prepare a WebGPU experiment first.");
        if (action === "export") return gpuRun.export();
        if (action === "step") await gpuRun.advance(extra.count ?? 8);
        if (action === "release") await gpuRun.release();
        if (action === "reset") await gpuRun.reset();
      }
      return gpuRun.snapshot();
    }
    const response = await fetch("/api3d", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, session, ...extra }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "3D request failed.");
    session = data.session;
    if (action === "prepare") {
      gpuRun?.destroy();
      gpuRun = null;
    }
    return data.result;
  }
  function error(err) {
    running = false;
    el("error").textContent = err.message;
    el("error").hidden = false;
  }
  function setConfig(c) {
    keys.forEach((k) => {
      el(k).value = c[k];
    });
  }
  async function action(name, extra = {}) {
    if (busy) return;
    busy = true;
    el("error").hidden = true;
    controls();
    if (name === "prepare")
      el("prepare-note").textContent =
        el("engine").value === "webgpu"
          ? "Preparing on your GPU… Setting up FFTs and the ground state."
          : "Preparing the 3D ground state… Large grids can take over a minute. Other pages remain available.";
    try {
      snapshot = await request(name, extra);
      if (name === "prepare" || name === "reset") {
        generation++;
        dirty = false;
        setConfig(snapshot.config);
        el("engine").value = snapshot.backend?.type || "cpu";
      }
      render();
      if (snapshot.complete || snapshot.warning) running = false;
    } catch (err) {
      error(err);
    } finally {
      busy = false;
      controls();
    }
  }
  async function tick() {
    if (!running) return;
    await action("step", { count: 8 });
    if (running) setTimeout(tick, 20);
  }
  function images() {
    if (!snapshot) return;
    const s = snapshot,
      arrays = s[view],
      n = s.config.n,
      a = s.scales.length_um;
    const factor = s.config.atoms / a ** (view === "slices" ? 3 : 2);
    const peak = Math.max(
      ...arrays.map((rows) => Math.max(...rows.map((row) => Math.max(...row)))),
    );
    const bounds = [s.x[0] * a, s.x.at(-1) * a];
    ["xy", "xz", "yz"].forEach((name, idx) => {
      const canvas = el(name),
        ctx = canvas.getContext("2d"),
        w = canvas.width,
        h = canvas.height;
      ctx.fillStyle = "#0e2028";
      ctx.fillRect(0, 0, w, h);
      const off = document.createElement("canvas");
      off.width = n;
      off.height = n;
      const oc = off.getContext("2d"),
        pixels = oc.createImageData(n, n);
      arrays[idx].forEach((row, y) =>
        row.forEach((p, x) => {
          const t = Math.max(0, p / peak),
            i = ((n - 1 - y) * n + x) * 4;
          pixels.data.set([14 + 70 * t, 32 + 184 * t, 40 + 179 * t, 255], i);
        }),
      );
      oc.putImageData(pixels, 0, 0);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(off, 43, 20, w - 60, h - 65);
      ctx.fillStyle = "#b2c8ce";
      ctx.font = "11px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(f(bounds[0], 1), 43, h - 28);
      ctx.textAlign = "right";
      ctx.fillText(f(bounds[1], 1), w - 17, h - 28);
      ctx.textAlign = "center";
      ctx.fillText(`${name[0]} / µm`, w / 2, h - 9);
      ctx.save();
      ctx.translate(15, h / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(
        `${name[1]} / µm  [${f(bounds[0], 1)}, ${f(bounds[1], 1)}]`,
        0,
        0,
      );
      ctx.restore();
      el(`${name}-label`).textContent =
        `${name.toUpperCase()} · ${view === "slices" ? ["z = 0", "y = 0", "x = 0"][idx] : ["integrated along z", "integrated along y", "integrated along x"][idx]}`;
    });
    el("image-note").textContent =
      `${view === "slices" ? "Central planes through the numerical volume" : "Ideal line-of-sight projections; no camera noise or optics"}. Shared linear color scale: 0–${f(peak * factor, 2)} atoms / ${view === "slices" ? "µm³" : "µm²"}. All views use the full ${n}³ solver grid.`;
  }
  function theory() {
    const s = snapshot,
      c = s.config,
      w = [c.fx_hz, c.fy_hz, c.fz_hz].map((v) => v / c.reference_hz);
    if (c.experiment !== "single") return [];
    const released = s.history.find((h) => h.released)?.steps;
    return s.tf
      ? s.tf.widths
      : s.history.map((h) => {
          const t =
            released === undefined
              ? 0
              : Math.max(0, (h.steps - released) * c.dt);
          return w.map((o) => Math.sqrt((1 + o * o * t * t) / (2 * o)));
        });
  }
  function historyPlot(ref) {
    const s = snapshot,
      canvas = el("width-history"),
      ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const left = 62,
      right = w - 24,
      top = 24,
      bottom = h - 40;
    const a = s.scales.length_um,
      tmax = Math.max(s.diagnostics.time, s.config.dt) * s.scales.time_ms;
    const ymax =
      1.15 * Math.max(...s.history.flatMap((d) => d.widths), ...ref.flat()) * a;
    ctx.font = "13px sans-serif";
    ctx.fillStyle = "#687887";
    ctx.strokeStyle = "#e5e9ee";
    for (let i = 0; i <= 4; i++) {
      const y = bottom - ((bottom - top) * i) / 4;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.fillText(f((ymax * i) / 4, 1), 16, y + 4);
      const x = left + ((right - left) * i) / 4;
      ctx.fillText(f((tmax * i) / 4, 2), x - 10, h - 18);
    }
    ctx.fillText("RMS / µm", 12, 14);
    ctx.fillText("time / ms", w - 90, h - 2);
    const colors = ["#3672dd", "#178e87", "#b58227"];
    for (let axis = 0; axis < 3; axis++)
      for (const theoretical of [false, true]) {
        if (theoretical && !ref.length) continue;
        ctx.strokeStyle = colors[axis];
        ctx.lineWidth = theoretical ? 1.8 : 2.4;
        ctx.setLineDash(theoretical ? [7, 5] : []);
        ctx.beginPath();
        s.history.forEach((d, i) => {
          const x =
            left + ((d.time * s.scales.time_ms) / tmax) * (right - left);
          const y =
            bottom -
            (((theoretical ? ref[i][axis] : d.widths[axis]) * a) / ymax) *
              (bottom - top);
          if (i) ctx.lineTo(x, y);
          else ctx.moveTo(x, y);
        });
        ctx.stroke();
      }
    ctx.setLineDash([]);
  }
  function render() {
    if (!snapshot) return;
    const s = snapshot,
      d = s.diagnostics,
      c = s.config,
      a = s.scales.length_um,
      p = s.preparation;
    const gpu = s.backend?.type === "webgpu";
    el("engine-note").textContent = gpu
      ? `Running in this browser · ${s.backend.adapter.vendor} ${s.backend.adapter.architecture} · complex float32. Real-time norm is not renormalized. No simulation server is used.`
      : "Running on the local CPU server · complex float64 reference.";
    el("surface-empty").hidden = true;
    el("results").hidden = false;
    if (!renderer) renderer = new window.DensitySurface3D(el("surface"));
    renderer.update(s, Number(el("iso").value) / 100);
    el("trap").textContent = d.released
      ? "All axes released"
      : c.experiment === "sequence"
        ? `${s.interferometry.stage} · trap + driven double well`
        : "Harmonic trap on · x / y / z";
    el("scene-units").textContent =
      `Box side ${f(c.length * a, 1)} µm · x / y / z`;
    el("render-note").textContent =
      `Numerical isodensity surface at ${f((renderer.level * c.atoms) / a ** 3, 2)} atoms / µm³. ${c.n}³ field → ${s.volume_n}³ ${s.volume_stride > 1 ? "block-averaged" : "rendering"} volume. Threshold is relative to the displayed volume peak; the box and scale stay fixed during expansion.`;
    el("time").textContent = f(d.time * s.scales.time_ms);
    ["x", "y", "z"].forEach((axis, i) => {
      el(`width-${axis}`).textContent = f(d.widths[i] * a);
    });
    el("norm").textContent = `Norm ${d.norm.toFixed(10)}`;
    el("energy").textContent =
      `Energy per atom / h ${f(d.energy * s.scales.energy_hz, 2)} Hz`;
    el("aspect").textContent =
      `Aspect x/z ${f(d.aspect_xz)} · y/z ${f(d.aspect_yz)}`;
    el("boundary").textContent =
      `Boundary probability ${(100 * d.edge_probability).toExponential(2)}%`;
    el("warning").hidden = !s.warning;
    el("warning").textContent = s.warning;
    el("prepare-note").textContent =
      `Prepared in ${f(p.elapsed_seconds, 1)} s. Parameter edits take effect on Prepare. Duration is measured from release, or from preparation while trapped.`;
    const ref = theory(),
      last = ref.at(-1);
    if (c.experiment === "single") {
      el("theory-title").textContent = s.tf
        ? "Absolute TF RMS / µm"
        : "Exact Gaussian RMS / µm";
      el("theory-table").innerHTML = ["x", "y", "z"]
        .map(
          (axis, i) =>
            `<tr><td>${axis}</td><td>${f(d.widths[i] * a, 4)}</td><td>${f(last[i] * a, 4)}</td><td>${f(100 * (d.widths[i] / last[i] - 1), 3)}%</td><td>${s.tf ? f(s.history[0].widths[i] * s.tf.scales.at(-1)[i] * a, 4) : "—"}</td></tr>`,
        )
        .join("");
      el("theory-note").textContent = s.tf
        ? `Castin–Dum Thomas–Fermi approximation: initial Ekin/Eint = ${f(s.tf_kinetic_ratio, 3)}, minimum µTF/(ℏωᵢ) = ${f((s.tf.chemical_potential / Math.max(c.fx_hz, c.fy_hz, c.fz_hz)) * c.reference_hz, 1)}. ${s.tf_kinetic_ratio > 0.1 ? "Kinetic energy is appreciable; TF is only a rough comparison here." : "Finite kinetic energy still causes physical differences from TF scaling."} Percentages compare with theory, not experimental data. Before release the reference stays at its initial width.`
        : "Exact noninteracting Gaussian reference (aₛ = 0). Width agreement tests free evolution; it is not experimental validation.";
      el("theory-note").textContent +=
        ` Reference aspect ratios: x/z ${f(last[0] / last[2])}, y/z ${f(last[1] / last[2])}. Numerical deviations: ${f(100 * (d.aspect_xz / (last[0] / last[2]) - 1), 2)}%, ${f(100 * (d.aspect_yz / (last[1] / last[2]) - 1), 2)}%.`;
    } else {
      el("theory-title").textContent = "Single-cloud theory";
      el("theory-table").innerHTML = ["x", "y", "z"]
        .map(
          (axis, i) =>
            `<tr><td>${axis}</td><td>${f(d.widths[i] * a, 4)}</td><td>—</td><td>—</td><td>—</td></tr>`,
        )
        .join("");
      el("theory-note").textContent =
        "Widths below are numerical. Single-cloud Gaussian and Castin–Dum width curves do not apply to this interferometer.";
      el("prepare-note").textContent =
        `Prepared in ${f(p.elapsed_seconds, 2)} s. ${c.experiment === "pair" ? "Coherent pair starts released; relative phase is right minus left." : "Run executes the entire sequence; release is automatic. Expansion duration starts after Hold."} Edits apply on Prepare.`;
    }
    el("performance").textContent =
      `${p.kind}; ${p.iterations} iterations at Δτ=${p.dt}; relative stationary residual ${p.relative_stationary_residual?.toExponential(2) ?? "not a stationary state"}. Preparation ${f(p.elapsed_seconds, 2)} s; last evolution batch ${f(s.last_batch_seconds, 3)} s. Persistent numerical arrays ${f(p.persistent_array_bytes / 1024 ** 2, 1)} MiB; excludes temporary FFT arrays, Python/JSON and browser memory. Rendering uses ${renderer.triangles.length} triangles.`;
    if (gpu)
      el("performance").textContent =
        `${p.kind}; ${p.iterations} iterations; preparation step ${p.dt}; stationary residual ${p.relative_stationary_residual?.toExponential(2) ?? "not a stationary state"}. Fresh setup + preparation ${f(p.elapsed_seconds, 3)} s (setup ${f(p.setup_seconds, 3)} s); last evolution batch ${f(s.last_batch_seconds, 3)} s. Explicit GPU/readback buffers ${f(p.persistent_array_bytes / 1024 ** 2, 1)} MiB; browser and driver memory excluded. Float32 stopping tolerance is 3e-6 iterate change; compare with the float64 CPU reference for quantitative work.`;
    const gas = d.peak_density * c.atoms * ((c.scattering_nm * 0.001) / a) ** 3;
    el("physical").textContent =
      `Norm-one convention; g₃D=${f(s.scales.interaction, 3)}; a₀=${f(a, 4)} µm; 1/ω₀=${f(s.scales.time_ms, 4)} ms. Current peak gas parameter n aₛ³=${gas.toExponential(2)}. Zero-temperature mean field with contact repulsion; no thermal cloud, losses or calibrated imaging. No transverse trap remains after release.`;
    images();
    historyPlot(ref);
    interferometer();
  }
  function profilePlot(id, series, unit) {
    const canvas = el(id);
    canvas.width = Math.max(
      280,
      Math.round(canvas.getBoundingClientRect().width),
    );
    const ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const xs = series.flatMap((s) => s.x),
      ys = series.flatMap((s) => s.y);
    const xmin = Math.min(...xs),
      xmax = Math.max(...xs),
      ymin = Math.min(0, ...ys),
      ymax = Math.max(...ys, ys.every((v) => v === 0) ? 1 : 1e-10) * 1.08;
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "#647585";
    ctx.fillText(unit, 52, 16);
    for (let i = 0; i <= 4; i++) {
      const y = 220 - i * 48;
      ctx.strokeStyle = "#e4e9ee";
      ctx.beginPath();
      ctx.moveTo(52, y);
      ctx.lineTo(w - 20, y);
      ctx.stroke();
      ctx.fillText(f(ymin + ((ymax - ymin) * i) / 4, 2), 2, y + 4);
      ctx.fillText(
        f(xmin + ((xmax - xmin) * i) / 4, 1),
        44 + ((w - 72) * i) / 4,
        242,
      );
    }
    ctx.fillText("x / µm", w - 65, 258);
    series.forEach((s, k) => {
      ctx.strokeStyle = k ? "#b58227" : "#3672dd";
      ctx.lineWidth = 2;
      ctx.setLineDash(k ? [6, 4] : []);
      ctx.beginPath();
      s.x.forEach((x, i) => {
        const px = 52 + ((x - xmin) / (xmax - xmin)) * (w - 72),
          py = 220 - ((s.y[i] - ymin) / (ymax - ymin)) * 192;
        i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      });
      ctx.stroke();
    });
    ctx.setLineDash([]);
  }
  function interferometer() {
    const s = snapshot,
      c = s.config,
      m = s.interferometry;
    el("interferometer").hidden = c.experiment === "single";
    if (c.experiment === "single") return;
    const t = s.scales.time_ms;
    el("timeline").textContent = m.stage_steps
      ? `${m.stage} · Split 0–${f(m.stage_steps[0] * c.dt * t, 2)} ms → Hold until ${f(m.stage_steps[1] * c.dt * t, 2)} ms → Expand until ${f(m.stage_steps[2] * c.dt * t, 2)} ms`
      : `${m.stage} · controlled coherent Gaussian pair`;
    el("interference-values").textContent =
      `Left ${f(100 * m.left_fraction, 2)}% · Right ${f(100 * m.right_fraction, 2)}% · Mirror phase ${m.mirror_phase === null ? "unavailable" : f(m.mirror_phase, 3) + " rad"} · Mirror coherence ${f(m.mirror_coherence, 3)} · Fringe spacing ${m.fringes.spacing === null ? "unavailable" : f(m.fringes.spacing * s.scales.length_um, 3) + " µm"} · Profile contrast ${m.fringes.contrast === null ? "unavailable" : f(m.fringes.contrast, 3)}`;
    const series = [s, ...(pinned ? [pinned.snapshot] : [])].map((v) => ({
      x: v.x.map((x) => x * v.scales.length_um),
      y: v.interferometry.profile.map(
        (y) => (y * v.config.atoms) / v.scales.length_um,
      ),
    }));
    profilePlot("line-profile", series, "atoms / µm");
    profilePlot(
      "potential-profile",
      [{ x: series[0].x, y: m.potential.map((y) => y * s.scales.energy_hz) }],
      "V / h · Hz",
    );
    el("fringe-note").textContent =
      m.fringes.reason +
      (s.diagnostics.released
        ? " All external potentials are zero after release."
        : "") +
      " " +
      (c.experiment === "pair" && s.diagnostics.time > 0
        ? `Finite-width phase period (theory): ${f(((2 * Math.PI * (1 + ((c.fx_hz / c.reference_hz) * s.diagnostics.time) ** 2)) / ((c.fx_hz / c.reference_hz) ** 2 * s.diagnostics.time * c.separation)) * s.scales.length_um, 3)} µm. Local peak spacing can differ because of the packet envelopes.`
        : "");
    el("pin-note").textContent = pinned
      ? `Pinned ${pinned.snapshot.config.experiment} at ${f(pinned.snapshot.diagnostics.time * pinned.snapshot.scales.time_ms, 2)} ms · bias ${pinned.snapshot.config.hold_bias} · pair phase ${f(pinned.snapshot.config.relative_phase, 3)} rad. Current ${f(s.diagnostics.time * t, 2)} ms. Shared physical axes; the pinned run is immutable.`
      : "Pin a paused run to compare the next experiment on shared physical axes.";
  }
  el("form").addEventListener("submit", (e) => {
    e.preventDefault();
    action("prepare", {
      config: Object.fromEntries(
        keys.map((k) => [
          k,
          k === "experiment" ? el(k).value : Number(el(k).value),
        ]),
      ),
    });
  });
  keys.forEach((k) =>
    el(k).addEventListener("input", () => {
      dirty = true;
      controls();
    }),
  );
  el("load").addEventListener("click", () => {
    const preset = el("preset").value;
    const selected = { ...presets[preset] };
    if (el("engine").value === "webgpu" && [48, 96].includes(selected.n))
      selected.n = selected.n === 48 ? 64 : 128;
    setConfig(selected);
    dirty = true;
    controls();
    el("preset-note").textContent =
      preset === "tf"
        ? "150,000 atoms, 96³ grid, full release. Preparation may take over a minute. TF remains an approximation; this is not a paper reproduction."
        : preset === "gaussian"
          ? "Interactions set to zero. Compare all three numerical widths with the exact free Gaussian solution."
          : "Repulsive Rb-87 gas. The three-axis field evolves numerically.";
    if (el("engine").value === "webgpu")
      el("preset-note").textContent =
        `WebGPU preset: ${selected.n}³, complex float32. All preparation and evolution run in your browser. TF is an approximate theory comparison, not a paper reproduction.`;
    if (selected.experiment !== "single")
      el("preset-note").textContent =
        selected.experiment === "pair"
          ? "Analytic coherent pair, zero interactions. Run to overlap the packets; compare phase 0 and π."
          : "One interacting condensate, a rising barrier, biased hold, then full release. Teaching settings inspired by Shin et al.; no apparatus reproduction. Run starts the sequence.";
  });
  el("engine").addEventListener("change", () => {
    dirty = true;
    controls();
    el("engine-note").textContent =
      el("engine").value === "webgpu"
        ? "WebGPU uses float32 and supports 32³ / 64³ / 128³. Load a preset or choose a supported grid, then Prepare. Hardware support is checked during preparation."
        : "CPU reference uses float64 on the local Python server. Prepare to apply this engine.";
  });
  el("release").addEventListener("click", () => action("release"));
  el("step").addEventListener("click", () => action("step", { count: 1 }));
  el("reset").addEventListener("click", () => action("reset"));
  el("run").addEventListener("click", () => {
    running = !running;
    controls();
    if (running && !busy) tick();
  });
  el("iso").addEventListener("input", () => {
    el("iso-value").textContent = `${el("iso").value}% of peak`;
    if (snapshot) render();
  });
  el("zoom").addEventListener("input", () => {
    if (renderer) {
      renderer.zoom = Number(el("zoom").value);
      renderer.draw();
    }
  });
  el("home").addEventListener("click", () => {
    el("zoom").value = 1;
    if (renderer) {
      renderer.zoom = 1;
      renderer.home();
    }
  });
  for (const mode of ["slices", "columns"])
    el(mode).addEventListener("click", () => {
      view = mode;
      for (const key of ["slices", "columns"]) {
        el(key).classList.toggle("selected", key === mode);
        el(key).setAttribute("aria-pressed", String(key === mode));
      }
      images();
    });
  el("export").addEventListener("click", async () => {
    busy = true;
    controls();
    try {
      const data = await request("export"),
        url = URL.createObjectURL(
          new Blob([JSON.stringify(data)], { type: "application/json" }),
        );
      const link = document.createElement("a");
      link.href = url;
      link.download = "coldatomlab-3d-run.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      error(err);
    } finally {
      busy = false;
      controls();
    }
  });
  function download(data, name) {
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(data)], { type: "application/json" }),
      ),
      link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  el("pin").addEventListener("click", async () => {
    busy = true;
    controls();
    try {
      const record = await request("export");
      pinned = { record, snapshot: structuredClone(snapshot) };
      interferometer();
    } catch (e) {
      error(e);
    } finally {
      busy = false;
      controls();
    }
  });
  el("clear-pin").addEventListener("click", () => {
    pinned = null;
    interferometer();
    controls();
  });
  el("export-pair").addEventListener("click", async () => {
    busy = true;
    controls();
    try {
      download(
        {
          schema: "coldatomlab-3d-comparison-v1",
          reference: pinned.record,
          current: await request("export"),
        },
        "coldatomlab-3d-comparison.json",
      );
    } catch (e) {
      error(e);
    } finally {
      busy = false;
      controls();
    }
  });
  window.showLab3D = () => {
    if (!renderer) renderer = new window.DensitySurface3D(el("surface"));
    controls();
  };
  window.addEventListener("resize", () => {
    if (snapshot) interferometer();
  });
  controls();
})();
