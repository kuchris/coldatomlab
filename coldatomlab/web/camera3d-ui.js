"use strict";
window.Camera3DPanel = class {
  constructor(parent, exportSource, lock) {
    this.exportSource = exportSource;
    this.lock = lock;
    this.current = null;
    this.pinned = null;
    this.snapshot = null;
    const panel = document.createElement("section");
    panel.className = "three-camera";
    panel.id = "camera3d-panel";
    panel.innerHTML = `<p class="eyebrow">VIRTUAL ABSORPTION CAMERA / RB-87</p><h2>What would the camera see?</h2>
    <p class="three-note">Freeze the numerical cloud, choose a viewing axis, then compare an ideal projection with a reconstructed absorption image. Capture never advances the simulation.</p>
    <fieldset id="camera3d-controls"><div class="camera3d-controls">
    <label>Look along<select id="camera3d-axis"><option value="z">z → image x / y</option><option value="y">y → image x / z</option><option value="x">x → image y / z</option></select></label>
    <label>Pixel binning<select id="camera3d-binning"><option>1</option><option>2</option><option>4</option><option>8</option><option>16</option></select></label>
    <label>Optical FWHM / µm<input id="camera3d-fwhm_um" type="number" min="0" max="20" step="any" value="0"></label>
    <label>Probe I / Isat<input id="camera3d-saturation" type="number" min="0.001" max="10" step="any" value="1"></label>
    <label>Pulse / µs<input id="camera3d-exposure_us" type="number" min="0.1" max="100" step="any" value="5"></label>
    <label>Read noise / electrons<input id="camera3d-read_noise" type="number" min="0" max="20" step="any" value="1"></label>
    <label>Quantum efficiency<input id="camera3d-efficiency" type="number" min="0.05" max="1" step="any" value="0.8"></label>
    <label>Noise seed<input id="camera3d-seed" type="number" min="0" max="4294967295" step="1" value="17"></label>
    <label>ROI half-width / µm<input id="camera3d-roi_um" type="number" min="1" max="100" step="any" value="12"></label>
    <label>Strip width / µm<input id="camera3d-strip_um" type="number" min="0.2" max="40" step="any" value="4"></label>
    <label class="camera3d-noise"><input id="camera3d-noise" type="checkbox"> Photon &amp; read noise</label></div></fieldset>
    <div class="transport-buttons"><button id="camera3d-ideal">Ideal optics · noise off</button><button id="camera3d-capture" class="primary">Capture image</button><button id="camera3d-pin" disabled>Pin image</button><button id="camera3d-clear" disabled>Clear reference</button><button id="camera3d-export" disabled>Export image</button></div>
    <p id="camera3d-status" class="three-note" role="status">Pause a prepared 3D experiment to capture an image. Camera-friendly pair is a useful first example.</p><p id="camera3d-error" class="error" role="alert" hidden></p>
    <div id="camera3d-results" hidden><div class="camera3d-images"><figure><figcaption>Ideal column density · atoms / µm²</figcaption><canvas id="camera3d-truth-image" width="420" height="360"></canvas></figure><figure><figcaption>Reconstructed camera density · atoms / µm²</figcaption><canvas id="camera3d-camera-image" width="420" height="360"></canvas></figure></div>
    <p id="camera3d-image-note" class="three-note"></p><div class="table-scroll"><table class="benchmark-table"><thead><tr><th>Image measurement</th><th>Ideal projection</th><th>Camera estimate</th><th>Camera − ideal</th><th>Pinned camera</th></tr></thead><tbody id="camera3d-measurements"></tbody></table></div>
    <p id="camera3d-fit-note" class="three-note"></p><canvas id="camera3d-profile" width="900" height="280" aria-label="Strip density, image-only fringe fit, and pinned camera profile"></canvas><p id="camera3d-pin-note" class="three-note"></p>
    <details><summary>Detected light · raw atom / reference / dark frames</summary><div class="camera3d-raw"><figure><figcaption>Atoms / electrons</figcaption><canvas id="camera3d-raw-atoms" width="300" height="260"></canvas></figure><figure><figcaption>Reference / electrons</figcaption><canvas id="camera3d-raw-reference" width="300" height="260"></canvas></figure><figure><figcaption>Dark / electrons</figcaption><canvas id="camera3d-raw-dark" width="300" height="260"></canvas></figure></div></details>
    <ul id="camera3d-warnings" class="three-note"></ul></div>
    <p class="three-note">Ideal resonant two-level absorption with a Gaussian intensity PSF; no recoil, motion during exposure, defocus, optical pumping or calibrated apparatus. Phase is fitted from image pixels, not copied from the wavefunction. <a href="model3d.html" target="_blank" rel="noopener">Model, limits &amp; papers ↗</a></p>`;
    parent.append(panel);
    this.el = (id) => document.getElementById(`camera3d-${id}`);
    this.el("capture").onclick = () => this.capture();
    this.el("ideal").onclick = () => {
      this.el("fwhm_um").value = 0;
      this.el("binning").value = 1;
      this.el("noise").checked = false;
      this.status();
    };
    this.el("pin").onclick = () => {
      this.pinned = structuredClone(this.current);
      this.render();
      this.status();
    };
    this.el("clear").onclick = () => {
      this.pinned = null;
      this.render();
      this.status();
    };
    this.el("export").onclick = () => {
      const record = this.pinned
        ? {
            schema: "coldatomlab-camera3d-comparison-v1",
            reference: this.pinned,
            current: this.current,
          }
        : this.current;
      const url = URL.createObjectURL(
          new Blob([JSON.stringify(record)], { type: "application/json" }),
        ),
        a = document.createElement("a");
      a.href = url;
      a.download = "coldatomlab-camera3d.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    this.el("controls").addEventListener("input", () => this.status());
    window.addEventListener("resize", () => {
      if (this.current) this.render();
    });
  }
  settings() {
    return Object.fromEntries(
      Object.keys(AbsorptionCamera3D.defaults).map((k) => [
        k,
        k === "axis"
          ? this.el(k).value
          : k === "noise"
            ? this.el(k).checked
            : Number(this.el(k).value),
      ]),
    );
  }
  update(snapshot, running, busy, generation) {
    this.snapshot = snapshot;
    this.running = running;
    this.busy = busy;
    this.generation = generation;
    this.status();
  }
  status() {
    this.el("controls").disabled = this.running || this.busy;
    this.el("capture").disabled = !this.snapshot || this.running || this.busy;
    this.el("ideal").disabled = this.running || this.busy;
    for (const id of ["pin", "export"])
      this.el(id).disabled = !this.current || this.running || this.busy;
    this.el("clear").disabled = !this.pinned || this.running || this.busy;
    if (this.acquiring) {
      this.el("status").textContent =
        "Acquiring frozen image and fitting the observed profile…";
      return;
    }
    if (!this.current) return;
    const stale =
      this.current.source_generation !== this.generation ||
      this.current.source.steps !== this.snapshot?.diagnostics.steps;
    const pending =
      JSON.stringify(this.settings()) !==
      JSON.stringify(this.current.image.camera);
    this.el("status").textContent =
      `Captured at ${(this.current.source.steps * this.current.source.config.dt * this.current.source.scales.time_ms).toFixed(3)} ms along ${this.current.image.camera.axis}. ${stale ? "Source changed; this is a frozen earlier exposure. " : ""}${pending ? "Camera settings pending; Capture to apply. " : ""}${this.running ? "Pause to acquire another image." : ""}`;
  }
  async capture() {
    if (!this.snapshot || this.running || this.busy) return;
    this.el("error").hidden = true;
    this.acquiring = true;
    this.lock(true);
    this.status();
    try {
      const settings = this.settings(),
        snap = structuredClone(this.snapshot),
        generation = this.generation;
      AbsorptionCamera3D.validate(settings, snap.config.n);
      const source = await this.exportSource();
      await new Promise((resolve) => setTimeout(resolve, 0));
      const image = AbsorptionCamera3D.acquire(snap, settings);
      this.current = {
        schema: "coldatomlab-camera3d-v1",
        camera_model: "rb87-browser-camera-v1",
        source,
        source_generation: generation,
        image,
      };
      this.render();
    } catch (e) {
      this.el("error").textContent = e.message;
      this.el("error").hidden = false;
    } finally {
      this.acquiring = false;
      this.lock(false);
      this.status();
    }
  }
  heat(id, data, axes, x, maximum) {
    const canvas = this.el(id),
      ctx = canvas.getContext("2d"),
      n = data.length,
      w = canvas.width,
      h = canvas.height,
      off = document.createElement("canvas");
    off.width = off.height = n;
    const o = off.getContext("2d"),
      pixels = o.createImageData(n, n);
    for (let y = 0; y < n; y++)
      for (let i = 0; i < n; i++) {
        const v = data[y][i],
          t = Math.max(0, Math.min(1, (v ?? 0) / maximum)),
          at = 4 * ((n - 1 - y) * n + i);
        pixels.data.set(
          v === null
            ? [230, 40, 170, 255]
            : v < 0
              ? [35, 90, 190, 255]
              : [10 + 70 * t, 26 + 190 * t, 35 + 178 * t, 255],
          at,
        );
      }
    o.putImageData(pixels, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, 44, 16, w - 60, h - 58);
    const halfPixel = (x[1] - x[0]) / 2,
      lower = x[0] - halfPixel,
      upper = x.at(-1) + halfPixel;
    ctx.fillStyle = "#617283";
    ctx.font = "12px sans-serif";
    ctx.fillText(lower.toFixed(1), 44, h - 24);
    ctx.textAlign = "right";
    ctx.fillText(upper.toFixed(1), w - 16, h - 24);
    ctx.textAlign = "center";
    ctx.fillText(`${axes[0]} / µm`, w / 2, h - 5);
    ctx.textAlign = "right";
    ctx.fillText(upper.toFixed(1), 40, 24);
    ctx.fillText(lower.toFixed(1), 40, h - 42);
    ctx.textAlign = "center";
    ctx.save();
    ctx.translate(15, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${axes[1]} / µm`, 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
  }
  render() {
    if (!this.current) return;
    const v = this.current.image,
      p = this.pinned?.image;
    this.el("results").hidden = false;
    const peak = Math.max(
      ...v.truth_density.flat(),
      ...v.density.flat().filter((x) => x !== null),
      1e-10,
    );
    this.heat("truth-image", v.truth_density, v.axes, v.x_um, peak);
    this.heat("camera-image", v.density, v.axes, v.x_um, peak);
    const rawMax = Math.max(
      ...v.atoms_frame.flat(),
      ...v.reference_frame.flat(),
      ...v.dark_frame.flat(),
      1,
    );
    for (const name of ["atoms", "reference", "dark"])
      this.heat(`raw-${name}`, v[`${name}_frame`], v.axes, v.x_um, rawMax);
    this.el("image-note").textContent =
      `Looking along ${v.camera.axis}; detector horizontal ${v.axes[0]}, vertical ${v.axes[1]}. ${v.x_um.length} × ${v.x_um.length} pixels, ${v.pixel_um.toFixed(3)} µm/pixel. Shared density scale 0–${peak.toFixed(2)} atoms/µm². Raw frames share 0–${rawMax.toFixed(1)} electrons. ROI ${v.roi_bounds_um.map((x) => x.toFixed(2)).join(" to ")} µm; strip ${v.strip_bounds_um.map((x) => x.toFixed(2)).join(" to ")} µm. Full model count ${v.model_total_atoms.toFixed(2)}.`;
    const f = (x) =>
        x === null || x === undefined ? "Unavailable" : Number(x).toFixed(3),
      wrap = (x) => Math.atan2(Math.sin(x), Math.cos(x));
    const rows = [
      ["ROI atoms", v.truth_atoms_roi, v.atoms_roi, p?.atoms_roi],
      [
        "Fringe period / µm",
        v.truth.spacing,
        v.measured.spacing,
        p?.measured.spacing,
      ],
      ["Image phase / rad", v.truth.phase, v.measured.phase, p?.measured.phase],
      [
        "Fitted contrast",
        v.truth.contrast,
        v.measured.contrast,
        p?.measured.contrast,
      ],
    ];
    this.el("measurements").innerHTML = rows
      .map(
        ([name, truth, actual, pin]) =>
          `<tr><td>${name}</td><td>${f(truth)}</td><td>${f(actual)}</td><td>${truth === null || actual === null ? "—" : f(name.includes("phase") ? wrap(actual - truth) : actual - truth)}</td><td>${f(pin)}</td></tr>`,
      )
      .join("");
    this.el("fit-note").textContent =
      `Camera fit: ${v.measured.reason} ${v.measured.relative_rmse === undefined ? "" : `Residual / profile range ${v.measured.relative_rmse.toFixed(4)}.`} Ideal projection is fitted independently. Image phase uses cos(k ${v.axes[0]} − φ) at coordinate zero; it is not the source mirror phase. Number standard error ${f(v.atom_standard_error)} atoms.`;
    this.el("pin-note").textContent = p
      ? `Blue: camera · teal: ideal · dashed amber: fit · dashed purple: pinned. Pinned exposure: ${(this.pinned.source.steps * this.pinned.source.config.dt * this.pinned.source.scales.time_ms).toFixed(3)} ms, along ${p.camera.axis}, FWHM ${p.camera.fwhm_um} µm, pixels ${p.pixel_um.toFixed(3)} µm, noise ${p.camera.noise ? "on" : "off"}, seed ${p.camera.seed}. Pinned profiles appear only for matching detector axes; times and settings remain independent.`
      : "Blue: camera · teal: ideal projection · dashed amber: image-only fit. Pin an image to compare optics or noise.";
    this.el("warnings").replaceChildren(
      ...v.warnings.map((t) => {
        const li = document.createElement("li");
        li.textContent = t;
        return li;
      }),
    );
    const canvas = this.el("profile");
    canvas.width = Math.max(
      280,
      Math.round(canvas.getBoundingClientRect().width),
    );
    const ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height;
    const series = [
      { x: v.x_um, y: v.profile, color: "#3672dd" },
      { x: v.x_um, y: v.truth_profile, color: "#178e87" },
      ...(v.measured.available
        ? [
            {
              x: v.fit_x_um,
              y: v.measured.fit_profile,
              color: "#b58227",
              dash: true,
            },
          ]
        : []),
      ...(p && p.camera.axis === v.camera.axis
        ? [{ x: p.x_um, y: p.profile, color: "#895da8", dash: true }]
        : []),
    ];
    const xs = series.flatMap((s) => s.x),
      ys = series.flatMap((s) => s.y.filter((t) => t !== null));
    const xmin = Math.min(...xs),
      xmax = Math.max(...xs),
      ymin = Math.min(0, ...ys),
      ymax = Math.max(...ys, 1e-10) * 1.1;
    ctx.clearRect(0, 0, w, h);
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "#617283";
    ctx.fillText("strip density / atoms per µm²", 48, 15);
    for (let j = 0; j <= 4; j++) {
      const yy = 240 - j * 52;
      ctx.strokeStyle = "#e4e9ee";
      ctx.beginPath();
      ctx.moveTo(48, yy);
      ctx.lineTo(w - 20, yy);
      ctx.stroke();
      ctx.fillText((ymin + ((ymax - ymin) * j) / 4).toFixed(1), 2, yy + 4);
      ctx.fillText(
        (xmin + ((xmax - xmin) * j) / 4).toFixed(1),
        40 + ((w - 68) * j) / 4,
        259,
      );
    }
    ctx.fillText(`${v.axes[0]} / µm`, w - 70, 278);
    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.setLineDash(s.dash ? [6, 4] : []);
      ctx.beginPath();
      let connected = false;
      s.y.forEach((v, i) => {
        if (v === null) {
          connected = false;
          return;
        }
        const x = 48 + ((s.x[i] - xmin) / (xmax - xmin)) * (w - 68),
          y = 240 - ((v - ymin) / (ymax - ymin)) * 208;
        connected ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        connected = true;
      });
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
};
