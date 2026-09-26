"use strict";
(() => {
  const $ = (id) => document.getElementById(id),
    keys = Object.keys(VortexModel.defaults),
    surface = new DensitySurface3D($("v-surface"));
  let solver = null,
    running = false,
    busy = false,
    dirty = true,
    pin = null;
  const fmt = (v, d = 3) =>
    v === null || !Number.isFinite(v) ? "Unresolved" : v.toFixed(d);
  function status(text) {
    $("v-status").textContent = text;
  }
  function controls() {
    $("v-prepare").disabled = busy || running;
    for (const id of ["run", "step"])
      $("v-" + id).disabled =
        !solver ||
        busy ||
        running ||
        dirty ||
        !!solver.lost ||
        !!solver.warning ||
        solver.complete;
    $("v-reset").disabled = !solver || busy || running;
    for (const id of ["pin", "json", "csv"])
      $("v-" + id).disabled =
        !solver ||
        busy ||
        running ||
        !!solver.lost ||
        solver.history.at(-1)?.steps !== solver.steps;
    $("v-pause").disabled = !running;
    $("v-release").disabled =
      !solver ||
      busy ||
      running ||
      dirty ||
      !!solver.warning ||
      solver.releaseStep !== null;
    window.VortexImagingUI?.updateControls();
    for (const el of document.querySelectorAll(
      "#v-form input,#v-form select,[data-vortex-preset]",
    ))
      el.disabled = busy || running;
  }
  function recipe(name) {
    const c = { ...VortexModel.defaults, stir_time: 4 };
    if (name === "negative") c.charge = -1;
    if (name === "ground") c.charge = 0;
    if (name === "imaging")
      Object.assign(c, {
        atoms: 1000,
        length: 24,
        n: 64,
        g: 0,
        height: 0,
        charge: 1,
        tof_duration: 2,
      });
    if (name === "stir")
      Object.assign(c, { g: 300, charge: 0, height: 12, duration: 5 });
    for (const k of keys) $("v-" + k).value = c[k];
    $("v-lesson").textContent =
      name === "stir"
        ? "Start from an interacting ground state with zero winding. The moving beam ramps off at t = 4 t₀; watch the cloud continue until 5 t₀. Crossing counts depend on resolution and density masking."
        : name === "ground"
          ? "A vortex-free Gaussian has no phase winding. Compare it with a pinned vortex; a density hole alone would not prove circulation."
          : `This ${c.charge > 0 ? "+1" : "−1"} recipe is a prepared oscillator eigenstate. Its phase winds once ${c.charge > 0 ? "counterclockwise" : "clockwise"}; it is not a movie of vortex formation.`;
    if (name === "imaging")
      $("v-lesson").textContent =
        "Prepare a single vortex, release all confinement, then run 2 t₀ of 3D expansion. Capture along z and compare ideal optics with blur and noise. g stays unchanged on release.";
    changed();
  }
  function changed() {
    dirty = true;
    status(
      "Settings pending · prepare to apply. Previous results are retained.",
    );
    controls();
  }
  function color(phase) {
    return `hsl(${((phase + Math.PI) / (2 * Math.PI)) * 360} 65% 57%)`;
  }
  function slice(canvas, s, phase) {
    const ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height,
      c = s.vortex,
      n = c.n,
      box = Math.min(w - 70, h - 65),
      ox = (w - box) / 2,
      oy = 20;
    ctx.fillStyle = "#0c181f";
    ctx.fillRect(0, 0, w, h);
    let peak = 0;
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++)
        peak = Math.max(
          peak,
          VortexModel.density(VortexModel.at(s.field, n, i, j)),
        );
    const px = (x) => ox + (x / c.length + 0.5) * box,
      py = (y) => oy + (0.5 - y / c.length) * box;
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        const p = VortexModel.at(s.field, n, i, j),
          rho = VortexModel.density(p),
          value = peak ? rho / peak : 0;
        ctx.fillStyle = phase
          ? value > 1e-3
            ? color(Math.atan2(p[1], p[0]))
            : "#0c181f"
          : `rgb(${Math.round(12 + 150 * Math.sqrt(value))} ${Math.round(24 + 194 * Math.sqrt(value))} ${Math.round(31 + 170 * Math.sqrt(value))})`;
        ctx.fillRect(
          ox + ((i - 0.5) * box) / n,
          oy + ((n - 0.5 - j) * box) / n,
          box / n + 0.3,
          box / n + 0.3,
        );
      }
    ctx.strokeStyle = "#e2f3ff";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.arc(px(0), py(0), (c.loop_radius / c.length) * box, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.setLineDash([]);
    if (!phase && s.gx) {
      ctx.strokeStyle = "#e4f4ffbb";
      const stride = Math.max(2, Math.floor(n / 16));
      for (let i = (stride / 2) | 0; i < n; i += stride)
        for (let j = (stride / 2) | 0; j < n; j += stride) {
          const p = VortexModel.at(s.field, n, i, j),
            rho = VortexModel.density(p);
          if (rho < peak * 0.01) continue;
          const a = VortexModel.at(s.gx, n, i, j),
            b = VortexModel.at(s.gy, n, i, j),
            vx = p[0] * a[1] - p[1] * a[0],
            vy = p[0] * b[1] - p[1] * b[0],
            mag = Math.hypot(vx, vy);
          if (mag < peak * 1e-5) continue;
          const x = px(((i - n / 2) * c.length) / n),
            y = py(((j - n / 2) * c.length) / n),
            dx = (6 * vx) / mag,
            dy = (-6 * vy) / mag;
          ctx.beginPath();
          ctx.moveTo(x - dx / 2, y - dy / 2);
          ctx.lineTo(x + dx, y + dy);
          ctx.lineTo(x + dx * 0.4 - dy * 0.4, y + dy * 0.4 + dx * 0.4);
          ctx.moveTo(x + dx, y + dy);
          ctx.lineTo(x + dx * 0.4 + dy * 0.4, y + dy * 0.4 - dx * 0.4);
          ctx.stroke();
        }
    }
    const d = s.history.at(-1);
    for (const v of d.crossings) {
      ctx.fillStyle = v.charge > 0 ? "#55bcff" : "#ffb96a";
      ctx.font = "bold 16px Consolas";
      ctx.textAlign = "center";
      ctx.fillText(v.charge > 0 ? "+" : "−", px(v.x), py(v.y) + 5);
    }
    const [height, x, y] = VortexModel.drive(c, d.time);
    if (height > 1e-8 && s.releaseStep == null) {
      ctx.strokeStyle = "#f6b469";
      ctx.beginPath();
      ctx.arc(px(x), py(y), (c.width / c.length) * box, 0, 2 * Math.PI);
      ctx.stroke();
    }
    ctx.fillStyle = "#adbec9";
    ctx.font = "11px Consolas";
    ctx.textAlign = "center";
    ctx.fillText(`−${c.length / 2}`, ox, oy + box + 18);
    ctx.fillText("0", px(0), oy + box + 18);
    ctx.fillText(`${c.length / 2}`, ox + box, oy + box + 18);
    ctx.fillText("x / a₀", w / 2, h - 7);
    ctx.fillText("y ↑", 19, h / 2);
    ctx.textAlign = "right";
    ctx.fillText(
      phase ? "hue: −π → 0 → +π" : `peak ${peak.toExponential(2)} a₀⁻³`,
      w - 10,
      12,
    );
  }
  function history() {
    const canvas = $("v-history"),
      ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height,
      rows = solver.history,
      maxT = Math.max(solver.vortex.duration, solver.history.at(-1).time),
      min = Math.min(-0.1, ...rows.map((d) => d.lz)),
      max = Math.max(0.1, ...rows.map((d) => d.lz));
    ctx.fillStyle = "#0c181f";
    ctx.fillRect(0, 0, w, h);
    ctx.font = "13px Consolas";
    ctx.fillStyle = "#acc0ce";
    ctx.fillText(max.toFixed(2), 8, 24);
    ctx.fillText(min.toFixed(2), 8, h - 35);
    ctx.fillText("0", 60, h - 8);
    ctx.fillText(maxT.toFixed(1) + " t₀", w - 85, h - 8);
    ctx.strokeStyle = "#73b9da";
    ctx.beginPath();
    rows.forEach((d, i) => {
      const x = 65 + ((w - 95) * d.time) / maxT,
        y = 20 + ((h - 55) * (max - d.lz)) / (max - min);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
  function render() {
    const d = solver.history.at(-1),
      c = solver.vortex;
    const metrics = [
      ["Time / ms", fmt(d.time * solver.units.time_ms)],
      [
        "TOF / ms",
        fmt(
          (solver.releaseStep === null
            ? 0
            : (solver.steps - solver.releaseStep) * c.dt) *
            solver.units.time_ms,
        ),
      ],
      ["RMS x / μm", fmt(d.widths[0] * solver.units.length_um)],
      ["RMS y / μm", fmt(d.widths[1] * solver.units.length_um)],
      ["RMS z / μm", fmt(d.widths[2] * solver.units.length_um)],
      [
        "Trapped time / ms",
        fmt((solver.releaseStep ?? solver.steps) * c.dt * solver.units.time_ms),
      ],
      ["Contour winding", d.winding ?? "Unresolved"],
      ["Flow circulation / (h/m)", fmt(d.flow_circulation_quanta)],
      ["Lz per particle / ℏ", fmt(d.lz)],
      ["Norm", fmt(d.norm, 6)],
      ["Energy / ℏω₀", fmt(d.energy, 5)],
      ["Boundary probability", d.edge_probability.toExponential(2)],
      ["Slice crossings + / −", `${d.positive} / ${d.negative}`],
    ];
    $("v-metrics").replaceChildren(
      ...metrics.map(([label, value]) => {
        const div = document.createElement("div"),
          small = document.createElement("small"),
          strong = document.createElement("strong");
        small.textContent = label;
        strong.textContent = value;
        div.append(small, strong);
        return div;
      }),
    );
    surface.update(solver.surface(), 0.2);
    slice($("v-density"), solver, false);
    slice($("v-phase"), solver, true);
    history();
    $("v-applied").textContent =
      `Applied: ${c.n}³ · N = ${c.atoms} · g = ${c.g} · aₛ = ${fmt(solver.config.scattering_nm)} nm · charge ${c.charge} · dt = ${c.dt} t₀. ${solver.preparation.kind}.`;
    $("v-units").textContent =
      `a₀ = ${fmt(solver.units.length_um)} μm · t₀ = ${fmt(solver.units.time_ms)} ms · h/m = ${fmt(solver.units.circulation_um2_ms)} μm²/ms.`;
    const [height] = VortexModel.drive(c, d.time);
    const free = solver.releaseStep !== null,
      endpoint = free
        ? solver.releaseStep + Math.round(c.tof_duration / c.dt)
        : Math.round(c.duration / c.dt);
    $("v-protocol").textContent =
      `t = ${fmt(d.time)} t₀ · trap ${free ? "OFF" : "ON"} · beam height ${fmt(free ? 0 : height)} ℏω₀ · ${endpoint} total steps. ${free ? "Full 3D free expansion; interactions remain on. Energy excludes the removed potential." : "Release trap begins TOF from this state. Energy may change while the beam moves."}`;
    $("v-topology").textContent = d.loop_reliable
      ? "The contour is resolved. Its integer winding measures net enclosed circulation; positive and negative crossings can cancel."
      : "Contour unresolved: low density or a large phase jump prevents a reliable winding. Unresolved is not zero.";
    status(
      solver.warning ||
        `${solver.complete ? "Complete" : running ? "Running" : "Ready / paused"} · ${solver.steps} steps · ${solver.adapter.vendor} hardware GPU`,
    );
    controls();
  }
  async function guarded(fn) {
    busy = true;
    controls();
    try {
      await fn();
    } catch (e) {
      running = false;
      status(e.message);
    } finally {
      busy = false;
      controls();
    }
  }
  $("v-form").addEventListener("submit", (e) => {
    e.preventDefault();
    guarded(async () => {
      const config = VortexModel.validate(
        Object.fromEntries(keys.map((k) => [k, Number($("v-" + k).value)])),
      );
      status("Preparing on GPU…");
      const next = await VortexGPU.create(config, status);
      solver?.destroy();
      solver = next;
      dirty = false;
      render();
    });
  });
  $("v-form").addEventListener("input", changed);
  for (const button of document.querySelectorAll("[data-vortex-preset]"))
    button.addEventListener("click", () => recipe(button.dataset.vortexPreset));
  async function run() {
    running = true;
    controls();
    while (running && solver && !solver.complete && !solver.warning) {
      await guarded(async () => {
        await solver.advance(20);
        render();
      });
      await new Promise((r) => setTimeout(r, 0));
    }
    running = false;
    controls();
  }
  $("v-release").addEventListener("click", () =>
    guarded(async () => {
      await solver.release();
      render();
    }),
  );
  $("v-run").addEventListener("click", run);
  $("v-pause").addEventListener("click", () => {
    running = false;
    controls();
  });
  $("v-step").addEventListener("click", () =>
    guarded(async () => {
      await solver.advance(1);
      render();
    }),
  );
  $("v-reset").addEventListener("click", () =>
    guarded(async () => {
      await solver.reset();
      render();
      if (dirty) status("Reset applied state · edited settings still pending.");
    }),
  );
  $("v-home").addEventListener("click", () => {
    surface.zoom = 1;
    $("v-zoom").value = 1;
    surface.home();
  });
  $("v-zoom").addEventListener("input", () => {
    surface.zoom = Number($("v-zoom").value);
    surface.draw();
  });
  $("v-pin").addEventListener("click", () => {
    pin = {
      vortex: { ...solver.vortex },
      releaseStep: solver.releaseStep,
      field: solver.field.slice(),
      history: [structuredClone(solver.history.at(-1))],
    };
    slice($("v-pin-phase"), pin, true);
    $("v-pin-label").textContent =
      `t = ${fmt(pin.history[0].time)} t₀ · g = ${pin.vortex.g} · charge ${pin.vortex.charge} · winding ${pin.history[0].winding ?? "Unresolved"} · Lz ${fmt(pin.history[0].lz)} ℏ`;
    $("v-pinned").hidden = false;
  });
  $("v-unpin").addEventListener("click", () => {
    pin = null;
    $("v-pinned").hidden = true;
  });
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $("v-json").addEventListener("click", () =>
    guarded(async () =>
      download(
        "coldatomlab-vortex.json",
        JSON.stringify(solver.export()),
        "application/json",
      ),
    ),
  );
  $("v-csv").addEventListener("click", () => {
    const fields = [
      "steps",
      "time",
      "norm",
      "energy",
      "lz",
      "edge_probability",
      "winding",
      "loop_reliable",
      "flow_circulation_quanta",
      "positive",
      "negative",
    ];
    download(
      "coldatomlab-vortex.csv",
      fields.join(",") +
        "\n" +
        solver.history
          .map((d) => fields.map((k) => d[k] ?? "").join(","))
          .join("\n"),
      "text/csv",
    );
  });
  window.addEventListener("message", (e) => {
    if (
      e.origin === location.origin &&
      e.source === parent &&
      e.data?.type === "vortex-hidden"
    )
      running = false;
  });
  window.addEventListener("pagehide", () => {
    running = false;
    solver?.destroy();
  });
  const resize = new ResizeObserver(() =>
    parent.postMessage(
      { type: "vortex-height", height: document.documentElement.scrollHeight },
      location.origin,
    ),
  );
  resize.observe(document.body);
  VortexImagingUI.attach(
    () => solver,
    () => busy || running,
  );
  controls();
})();
