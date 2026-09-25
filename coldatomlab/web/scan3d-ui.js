"use strict";
window.Scan3DPanel = class {
  constructor(before, lock) {
    this.lock = lock;
    this.runner = null;
    this.report = null;
    this.active = false;
    this.blocked = false;
    const panel = document.createElement("section");
    panel.className = "three-camera scan3d";
    panel.id = "scan3d-panel";
    panel.innerHTML = `<p class="eyebrow">AUTOMATED EXPERIMENT / WEBGPU</p>
    <h2>Measure a phase curve</h2><p class="three-note">Run a series of independent 3D experiments, photograph each frozen cloud, and compare the phase recovered from pixels. Your manual experiment stays in place.</p>
    <fieldset id="scan3d-settings"><div class="camera3d-controls">
    <label>Scan protocol<select id="scan3d-mode"><option value="phase">Known pair phase · calibration</option><option value="hold">Interacting split · hold time</option><option value="bias">Interacting split · hold bias</option></select></label>
    <label><span id="scan3d-start-label">First phase / rad</span><input id="scan3d-start" type="number" step="any" value="-2.4"></label>
    <label><span id="scan3d-end-label">Last phase / rad</span><input id="scan3d-end" type="number" step="any" value="2.4"></label>
    <label>Scan points<input id="scan3d-points" type="number" min="2" max="9" value="5"></label>
    <label>Exposures per point<input id="scan3d-repeats" type="number" min="1" max="20" value="5"></label>
    <label id="scan3d-hold-label" hidden>Fixed hold / ω₀⁻¹<input id="scan3d-hold" type="number" step="any" min="0" max="3" value="0.6"></label>
    <label id="scan3d-bias-label" hidden>Fixed bias / ℏω₀<input id="scan3d-bias" type="number" step="any" min="-5" max="5" value="1"></label>
    <label>Look along<select id="scan3d-axis"><option value="z">z → x / y image</option><option value="y">y → x / z image</option><option value="x">x → y / z image</option></select></label>
    <label>Optical FWHM / µm<input id="scan3d-fwhm" type="number" step="any" min="0" max="20" value="0"></label>
    <label>Probe I / Isat<input id="scan3d-saturation" type="number" step="any" min="0.001" max="10" value="1"></label>
    <label>Pulse / µs<input id="scan3d-exposure" type="number" step="any" min="0.1" max="100" value="5"></label>
    <label>Pixel binning<select id="scan3d-binning"><option>1</option><option>2</option><option>4</option></select></label>
    <label>First noise seed<input id="scan3d-seed" type="number" min="0" max="4294967295" step="1" value="17"></label>
    <label class="camera3d-noise"><input id="scan3d-noise" type="checkbox" checked> Photon &amp; read noise</label>
    <label class="camera3d-noise"><input id="scan3d-refine" type="checkbox"> Compare 64³ / 128³ · slower</label>
    </div><p id="scan3d-recipe" class="three-note"></p></fieldset>
    <div class="transport-buttons"><button id="scan3d-start-run" class="primary">Run scan</button><button id="scan3d-pause" disabled>Pause</button><button id="scan3d-cancel" disabled>Cancel</button><button id="scan3d-json" disabled>Export reproducible data</button><button id="scan3d-csv" disabled>Export CSV</button></div>
    <p id="scan3d-status" class="three-note" role="status">Ready for a fresh calibration scan. Requires hardware WebGPU.</p><p id="scan3d-error" class="error" role="alert" hidden></p>
    <div id="scan3d-results" hidden><p id="scan3d-summary" class="scan3d-summary"></p>
    <div class="camera3d-images"><figure><figcaption>Recovered phase / rad · circular mean ± detector scatter</figcaption><svg id="scan3d-phase-chart" viewBox="0 0 600 330" role="img" aria-label="Input parameter versus camera phase, ideal-image phase and phase guide"></svg></figure>
    <figure><figcaption>Phase differences / rad · auto-scaled, wrapped to ±π</figcaption><svg id="scan3d-error-chart" viewBox="0 0 600 330" role="img" aria-label="Camera minus ideal and ideal minus phase guide"></svg></figure></div>
    <p class="three-note">Blue circles: 64³ camera · purple circles: 128³ camera · outlined squares: ideal image · teal dashed line: input phase or isolated-well guide. Error chart: circles show camera − ideal; squares show ideal − guide. Points with no reliable phase appear as red crosses at the bottom, not as zero. Bars show circular standard deviation of valid exposures, not standard error or a confidence interval.</p>
    <div class="table-scroll"><table class="benchmark-table"><thead><tr><th>Parameter</th><th>Grid</th><th>Actual hold / ms</th><th>Valid / attempted</th><th>Failed</th><th>Mean phase / rad</th><th>Scatter / rad</th><th>Camera − ideal / rad</th><th>Ideal − guide / rad</th><th>Period / µm</th><th>Contrast</th></tr></thead><tbody id="scan3d-table"></tbody></table></div>
    <p id="scan3d-grid-note" class="three-note"></p><div class="table-scroll"><table class="benchmark-table"><thead><tr><th>128³ − 64³</th><th>Δ width x / %</th><th>Δ width y / %</th><th>Δ width z / %</th><th>Δ norm</th><th>Δ ideal-image phase / rad</th></tr></thead><tbody id="scan3d-grid-table"></tbody></table></div>
    <details><summary>Acquisition warnings and failed runs</summary><ul id="scan3d-warnings" class="three-note"></ul></details></div>
    <p class="three-note">Repeated exposures vary detector noise only; the condensate field is fixed. A circular mean is unavailable when its resultant is below 0.1. Fit failures can bias statistics of surviving images. The phase guide −bias × actual hold time assumes separated wells and neglects coupling and interaction imbalance. Interacting image phases need not follow it exactly.</p>
    <p class="three-note">Rb-87 teaching protocols inspired by <a href="https://arxiv.org/abs/cond-mat/0306305" target="_blank" rel="noopener">Shin et al. (2004)</a>; no reconstruction of their Na-23 apparatus. Gaussian optics, ideal two-level absorption, no recoil or finite-temperature phase fluctuations. <a href="model3d.html#scans" target="_blank" rel="noopener">Scan model and limits ↗</a></p>`;
    before.before(panel);
    this.el = (id) => document.getElementById(`scan3d-${id}`);
    this.el("mode").onchange = () => this.modeChanged();
    this.el("settings").oninput = () => this.preview();
    this.el("start-run").onclick = () => this.start();
    this.el("pause").onclick = () => {
      this.runner.paused = !this.runner.paused;
      this.el("pause").textContent = this.runner.paused ? "Resume" : "Pause";
      this.el("status").textContent = this.runner.paused
        ? "Pause requested; finishes the current preparation, step batch or exposure."
        : "Resuming scan…";
    };
    this.el("cancel").onclick = () => {
      this.runner.cancelled = true;
      this.runner.paused = false;
      this.el("status").textContent =
        "Cancelling at the next checkpoint; completed points will remain exportable.";
    };
    for (const format of ["json", "csv"])
      this.el(format).onclick = () => this.download(format);
    window.addEventListener("resize", () => {
      if (this.report) {
        this.chart("phase-chart", false);
        this.chart("error-chart", true);
      }
    });
    this.preview();
  }
  number(id) {
    const text = this.el(id).value;
    return text.trim() === "" ? NaN : Number(text);
  }
  modeChanged() {
    const mode = this.el("mode").value,
      ranges = { phase: [-2.4, 2.4], hold: [0.45, 0.9], bias: [-1, 1] },
      units = { phase: "phase / rad", hold: "hold / ω₀⁻¹", bias: "bias / ℏω₀" }[
        mode
      ];
    this.el("start").value = ranges[mode][0];
    this.el("end").value = ranges[mode][1];
    this.el("start-label").textContent = `First ${units}`;
    this.el("end-label").textContent = `Last ${units}`;
    this.el("hold-label").hidden = mode !== "bias";
    this.el("bias-label").hidden = mode !== "hold";
    this.el("saturation").value = mode === "phase" ? 1 : 10;
    this.preview();
  }
  plan() {
    const mode = this.el("mode").value,
      base = Scan3D.base(mode);
    if (mode === "bias") base.hold_time = this.number("hold");
    if (mode === "hold") base.hold_bias = this.number("bias");
    return {
      mode,
      base,
      start: this.number("start"),
      end: this.number("end"),
      points: this.number("points"),
      repeats: this.number("repeats"),
      refine: this.el("refine").checked,
      camera: {
        ...AbsorptionCamera3D.defaults,
        axis: this.el("axis").value,
        binning: this.number("binning"),
        saturation: this.number("saturation"),
        exposure_us: this.number("exposure"),
        fwhm_um: this.number("fwhm"),
        noise: this.el("noise").checked,
        seed: this.number("seed"),
      },
    };
  }
  preview() {
    const p = this.plan(),
      c = p.base;
    this.el("recipe").textContent =
      `Fixed Rb-87 recipe: N=${c.atoms}, aₛ=${c.scattering_nm} nm; frequencies x/y/z=${c.fx_hz}/${c.fy_hz}/${c.fz_hz} Hz, reference ${c.reference_hz} Hz. Box ${c.length} a₀, dt=${c.dt} ω₀⁻¹, expansion ${c.duration} ω₀⁻¹${p.mode === "phase" ? ", initial separation 6 a₀" : ", split 3 ω₀⁻¹, Gaussian barrier height 12 ℏω₀ and width 0.8 a₀"}. Camera ROI ±12 µm, strip 4 µm, efficiency 0.8, read noise 1 electron. ${p.points * (p.refine ? 2 : 1)} fresh evolutions; ${p.points * p.repeats * (p.refine ? 2 : 1)} exposures. Editing settings does not change existing results.`;
  }
  update(blocked) {
    this.blocked = blocked;
    this.el("start-run").disabled = this.active || blocked;
  }
  async start() {
    if (this.active || this.blocked) return;
    this.el("error").hidden = true;
    let runner;
    try {
      runner = new Scan3DRunner(this.plan(), (message, report) => {
        this.report = report;
        this.el("status").textContent =
          runner.paused && !message.startsWith("Paused")
            ? `Pause requested · ${message}`
            : message;
        if (
          report.records.length !== this.rendered ||
          report.status !== "running"
        )
          this.render();
      });
    } catch (e) {
      this.el("error").textContent = e.message;
      this.el("error").hidden = false;
      return;
    }
    this.runner = runner;
    this.active = true;
    this.rendered = -1;
    this.report = runner.report;
    this.el("settings").disabled = true;
    this.el("pause").disabled = false;
    this.el("cancel").disabled = false;
    this.el("pause").textContent = "Pause";
    this.el("json").disabled = this.el("csv").disabled = true;
    this.lock(true);
    this.update(true);
    try {
      await runner.run();
    } finally {
      this.active = false;
      this.el("settings").disabled = false;
      this.el("pause").disabled = this.el("cancel").disabled = true;
      this.lock(false);
      this.update(false);
      this.render();
    }
  }
  download(format) {
    if (!this.report || this.active) return;
    const data =
        format === "json"
          ? JSON.stringify(this.report)
          : Scan3D.csv(this.report),
      url = URL.createObjectURL(
        new Blob([data], {
          type:
            format === "json" ? "application/json" : "text/csv;charset=utf-8",
        }),
      ),
      a = document.createElement("a");
    a.href = url;
    a.download = `coldatomlab-scan3d.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  render() {
    const report = this.report;
    if (!report) return;
    this.rendered = report.records.length;
    this.el("results").hidden = false;
    const f = (v) =>
        v === null || v === undefined ? "Unavailable" : Number(v).toFixed(4),
      records = report.records,
      completed = records.filter((r) => r.status === "complete"),
      good = completed.reduce((s, r) => s + r.summary.valid, 0),
      attempts = completed.reduce((s, r) => s + r.summary.attempted, 0);
    this.el("summary").textContent =
      `${completed.length}/${Scan3D.jobs(report.plan).length} evolutions completed · ${records.length - completed.length} stopped · ${good}/${attempts} valid image fits · ${report.status}`;
    this.el("table").innerHTML = records
      .map((r) => {
        const s = r.summary || {};
        return `<tr><td>${f(r.value)}</td><td>${r.grid}³</td><td>${f(r.source?.protocol.hold_ms)}</td><td>${s.valid ?? 0} / ${s.attempted ?? 0}</td><td>${s.failure_fraction === null || s.failure_fraction === undefined ? r.status : (100 * s.failure_fraction).toFixed(1) + "%"}</td>${[s.mean_phase, s.phase_sd, s.camera_minus_ideal, s.ideal_minus_guide, s.mean_period, s.mean_contrast].map((v) => `<td>${f(v)}</td>`).join("")}</tr>`;
      })
      .join("");
    this.el("grid-table").innerHTML = report.refinement
      .map(
        (r) =>
          `<tr><td>${f(r.value)}</td>${r.width_relative.map((v) => `<td>${f(100 * v)}</td>`).join("")}<td>${f(r.norm_difference)}</td><td>${f(r.ideal_phase_difference)}</td></tr>`,
      )
      .join("");
    this.el("grid-table").closest(".table-scroll").hidden = !report.plan.refine;
    this.el("grid-note").textContent = report.plan.refine
      ? "Same physical recipe, box and time step. Width/norm changes describe the field. Ideal-image phase changes include solver, pixel sampling and estimator sensitivity; two grids do not establish convergence. Ideal fits use native source pixels without noise or optical blur. Noisy frames retain the selected binning, so 128³ pixels have half the physical pitch."
      : "Grid comparison was not requested. Enable Compare 64³ / 128³ for separate field and ideal-image sensitivity checks.";
    const warnings = records.flatMap((r) =>
      r.status !== "complete"
        ? [`Point ${r.point + 1}, ${r.grid}³: ${r.reason}`]
        : [
            ...new Set([
              ...r.ideal.warnings,
              ...r.shots.flatMap((i) => i.warnings),
            ]),
          ].map((v) => `Point ${r.point + 1}, ${r.grid}³: ${v}`),
    );
    this.el("warnings").replaceChildren(
      ...warnings.map((t) => {
        const li = document.createElement("li");
        li.textContent = t;
        return li;
      }),
    );
    this.chart("phase-chart", false);
    this.chart("error-chart", true);
    this.el("json").disabled = this.el("csv").disabled = this.active;
  }
  chart(id, error) {
    const width = Math.max(
        280,
        Math.round(this.el(id).getBoundingClientRect().width),
      ),
      ticks = width < 420 ? 2 : 4,
      p = this.report.plan,
      rows = this.report.records,
      extent = error
        ? Math.min(
            Math.PI,
            Math.max(
              0.05,
              ...rows.flatMap((r) =>
                r.summary
                  ? [
                      Math.abs(r.summary.camera_minus_ideal ?? 0) +
                        (r.summary.phase_sd ?? 0),
                      Math.abs(r.summary.ideal_minus_guide ?? 0),
                    ]
                  : [],
              ),
            ) * 1.2,
          )
        : Math.PI,
      lo = -extent,
      hi = extent,
      x = (v) => 58 + ((v - p.start) / (p.end - p.start)) * (width - 90),
      y = (v) => 274 - ((v - lo) / (hi - lo)) * 240;
    this.el(id).setAttribute("viewBox", `0 0 ${width} 330`);
    let svg = `<rect width="${width}" height="330" fill="#fafcfe"/>`;
    for (let i = 0; i <= ticks; i++) {
      const v = lo + ((hi - lo) * i) / ticks,
        xx = p.start + ((p.end - p.start) * i) / ticks;
      svg += `<path d="M58 ${y(v)}H${width - 32}" stroke="#e0e7ee"/><text x="48" y="${y(v) + 4}" text-anchor="end">${v.toFixed(error ? 3 : 2)}</text><text x="${x(xx)}" y="298" text-anchor="middle">${xx.toFixed(2)}</text>`;
    }
    for (const grid of [64, 128]) {
      const color = grid === 64 ? "#236bd7" : "#8752ae";
      let previous = null;
      for (const r of rows.filter((r) => r.grid === grid)) {
        const xx = x(r.value),
          s = r.summary;
        if (!s) {
          svg += `<path d="M${xx - 4} 276l8 8m-8 0l8 -8" stroke="#b13d44"/>`;
          previous = null;
          continue;
        }
        const mean = error ? s.camera_minus_ideal : s.mean_phase,
          ideal = error ? s.ideal_minus_guide : s.ideal_phase;
        if (mean !== null) {
          if (s.phase_sd !== null)
            for (const shift of [-2 * Math.PI, 0, 2 * Math.PI]) {
              const a = Math.max(lo, mean - s.phase_sd + shift),
                b = Math.min(hi, mean + s.phase_sd + shift);
              if (a <= b)
                svg += `<path d="M${xx} ${y(a)}V${y(b)}M${xx - 4} ${y(a)}h8M${xx - 4} ${y(b)}h8" stroke="${color}"/>`;
            }
          svg += `<circle cx="${xx}" cy="${y(mean)}" r="4" fill="${color}"/>`;
        } else
          svg += `<path d="M${xx - 4} 276l8 8m-8 0l8 -8" stroke="#b13d44"/>`;
        if (ideal !== null)
          svg += `<rect x="${xx - 4}" y="${y(ideal) - 4}" width="8" height="8" fill="none" stroke="${grid === 128 ? "#8752ae" : "#b58227"}"/>`;
        if (!error && grid === 64) {
          if (previous && Math.abs(s.guide - previous.guide) < Math.PI)
            svg += `<path d="M${previous.x} ${y(previous.guide)}L${xx} ${y(s.guide)}" stroke="#168a81" stroke-dasharray="5 4"/>`;
          svg += `<circle cx="${xx}" cy="${y(s.guide)}" r="2" fill="#168a81"/>`;
          previous = { x: xx, guide: s.guide };
        }
      }
    }
    svg += `<text x="${(width + 26) / 2}" y="324" text-anchor="middle">${{ phase: "Input pair phase / rad", hold: "Requested hold / ω₀⁻¹", bias: "Hold bias / ℏω₀" }[p.mode]}</text>`;
    this.el(id).innerHTML = svg;
  }
};
