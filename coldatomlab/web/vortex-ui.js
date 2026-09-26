"use strict";
(() => {
  const $ = (id) => document.getElementById(id),
    keys = Object.keys(VortexModel.defaults),
    surface = new DensitySurface3D($("v-surface"));
  let solver = null,
    running = false,
    busy = false,
    dirty = true,
    pin = null,
    sequenceActive = false,
    stopSequence = false;
  const savedRuns = [];
  const fmt = (v, d = 3) =>
    v === null || !Number.isFinite(v) ? "Unresolved" : v.toFixed(d);
  function status(text) {
    $("v-status").textContent = text;
  }
  function controls() {
    $("v-sequence-run").disabled = busy || running;
    $("v-sequence-stop").disabled = !sequenceActive;
    $("v-compare-runs").disabled = !savedRuns.length;
    for (const id of ["v-hold-ms", "v-tof-ms"]) $(id).disabled = sequenceActive;
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
    if (name === "stationary")
      Object.assign(c, {
        stationary: 1,
        atoms: 10000,
        g: 4 * Math.PI * 20,
        axial_hz: 50,
        n: 128,
        length: 32,
      });
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
    syncScattering(true);
    $("v-hold-ms").value =
      name === "stir" ? (c.duration * 1000) / (2 * Math.PI * c.radial_hz) : 0;
    $("v-tof-ms").value = (c.tof_duration * 1000) / (2 * Math.PI * c.radial_hz);
    $("v-lesson").textContent =
      name === "stir"
        ? "Start from an interacting ground state with zero winding. The moving beam ramps off at t = 4 t₀; watch the cloud continue until 5 t₀. Crossing counts depend on resolution and density masking."
        : name === "ground"
          ? "A vortex-free Gaussian has no phase winding. Compare it with a pinned vortex; a density hole alone would not prove circulation."
          : `This ${c.charge > 0 ? "+1" : "−1"} recipe is a prepared oscillator eigenstate. Its phase winds once ${c.charge > 0 ? "counterclockwise" : "clockwise"}; it is not a movie of vortex formation.`;
    if (name === "imaging")
      $("v-lesson").textContent =
        "Prepare a single vortex, release all confinement, then run 2 t₀ of 3D expansion. Capture along z and compare ideal optics with blur and noise. g stays unchanged on release.";
    if (name === "stationary")
      $("v-lesson").textContent =
        "Interacting stationary vortex · Na/a₀ = 20 · isotropic trap. Run experiment prepares and releases it automatically. Full 3D GPE; comparison with the paper's reduced model requires separate convergence checks.";
    changed();
  }
  function syncScattering(fromG) {
    const n = Number($("v-atoms").value),
      f = Number($("v-radial_hz").value);
    const a =
      Math.sqrt(
        6.62607015e-34 / (2 * Math.PI) / (1.443160895e-25 * 2 * Math.PI * f),
      ) * 1e9;
    if (!(n > 0 && f > 0)) return;
    if (fromG)
      $("v-scattering").value =
        (Number($("v-g").value) * a) / (4 * Math.PI * n);
    else
      $("v-g").value = (4 * Math.PI * n * Number($("v-scattering").value)) / a;
  }
  function changed(event) {
    if (event?.target?.id === "v-g") syncScattering(true);
    if (["v-scattering", "v-atoms", "v-radial_hz"].includes(event?.target?.id))
      syncScattering(false);
    dirty = true;
    status(
      "Settings pending · Run experiment to apply. Previous results are retained.",
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
    if (c.stationary) {
      const prep = solver.preparation.prepared_state;
      metrics.push(
        [
          "Stationary residual",
          prep.relative_stationary_residual.toExponential(2),
        ],
        ["Chemical potential / ℏω₀", fmt(prep.chemical_potential, 5)],
      );
    }
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
  function readConfig() {
    return VortexModel.validate(
      Object.fromEntries(keys.map((k) => [k, Number($("v-" + k).value)])),
    );
  }
  function displayRuns() {
    $("v-run-list").replaceChildren(
      ...savedRuns.map((r) => {
        const article = document.createElement("article"),
          p = document.createElement("p"),
          button = document.createElement("button");
        const c = r.source.config,
          d = r.source.history.at(-1);
        p.textContent = `Run ${r.number} · ${r.status} · N ${c.atoms} · g ${fmt(c.g)} · ${c.n}³ · hold ${fmt(r.protocol.hold_steps * r.protocol.step_ms)} ms / TOF ${fmt(r.protocol.tof_steps * r.protocol.step_ms)} ms · final RMS x ${fmt(d.widths[0] * r.source.scales.length_um)} μm · camera contrast ${r.image?.measurements.camera.contrast == null ? "Unavailable" : fmt(r.image.measurements.camera.contrast)}.`;
        const tof =
          r.source.release_step === null
            ? null
            : (r.source.steps - r.source.release_step) * c.dt;
        if (
          r.reference &&
          d.paper_core?.core_ratio != null &&
          tof !== null &&
          tof <= 2
        ) {
          const rows = r.reference.rows,
            upper = Math.max(
              1,
              rows.findIndex((row) => row.time >= tof),
            ),
            lo = rows[upper - 1],
            hi = rows[upper];
          const reference =
            lo.core_ratio +
            ((hi.core_ratio - lo.core_ratio) * (tof - lo.time)) /
              (hi.time - lo.time);
          p.textContent += ` Core/cloud ratio ${fmt(d.paper_core.core_ratio, 5)}; 3D − paper approximation ${(d.paper_core.core_ratio - reference).toExponential(2)}. This difference is not a numerical error estimate.`;
        }
        button.textContent = "Export run JSON";
        button.addEventListener("click", () =>
          download(
            `coldatomlab-run-${r.number}.json`,
            JSON.stringify(r),
            "application/json",
          ),
        );
        article.append(p, button);
        return article;
      }),
    );
    drawPaper();
    controls();
  }
  function drawPaper() {
    const canvas = $("v-paper-plot"),
      ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height,
      key = $("v-paper-quantity").value;
    const colors = ["#167d83", "#b57525", "#7c58a4"],
      sets = [];
    savedRuns.forEach((run, index) => {
      const s = run.source,
        c = s.config;
      if (s.release_step === null) return;
      const rows = s.history
        .filter(
          (row) => row.steps >= s.release_step && row.paper_core?.[key] != null,
        )
        .map((row) => [row.time - s.release_step * c.dt, row.paper_core[key]]);
      if (rows.length) sets.push({ rows, color: colors[index], dash: false });
      if (run.reference)
        sets.push({
          rows: run.reference.rows.map((row) => [row.time, row[key]]),
          color: colors[index],
          dash: true,
        });
    });
    const maxX = Math.max(2, ...sets.flatMap((s) => s.rows.map((r) => r[0]))),
      maxY =
        Math.max(0.3, ...sets.flatMap((s) => s.rows.map((r) => r[1]))) * 1.1;
    ctx.fillStyle = "#f8fbfa";
    ctx.fillRect(0, 0, w, h);
    ctx.font = "13px Consolas";
    ctx.fillStyle = "#486363";
    for (let i = 0; i <= 4; i++) {
      const y = 25 + ((h - 65) * i) / 4;
      ctx.strokeStyle = "#d8e5e2";
      ctx.beginPath();
      ctx.moveTo(65, y);
      ctx.lineTo(w - 25, y);
      ctx.stroke();
      ctx.fillText(((1 - i / 4) * maxY).toFixed(3), 5, y + 4);
      ctx.fillText(
        ((i * maxX) / 4).toFixed(2),
        60 + ((w - 100) * i) / 4,
        h - 22,
      );
    }
    for (const s of sets) {
      ctx.strokeStyle = s.color;
      ctx.setLineDash(s.dash ? [6, 5] : []);
      ctx.beginPath();
      s.rows.forEach(([x, y], i) => {
        const px = 65 + ((w - 90) * x) / maxX,
          py = 25 + (h - 65) * (1 - y / maxY);
        i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      });
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.fillText("TOF / t₀ = ωt", w / 2 - 45, h - 3);
    if (!sets.length) ctx.fillText("No eligible core history yet.", 85, h / 2);
    $("v-paper-caption").textContent = savedRuns
      .map(
        (r, i) =>
          `Run ${r.number}: ${["teal", "ochre", "purple"][i]} · Na/a₀=${fmt(r.source.config.g / (4 * Math.PI))} · ${r.reference ? "paper approximation available" : "no applicable paper reference"}`,
      )
      .join(". ");
  }
  $("v-paper-quantity").addEventListener("change", drawPaper);
  let runNumber = 0;
  $("v-compare-runs").addEventListener("click", () => {
    $("v-run-comparison").hidden = !$("v-run-comparison").hidden;
  });
  $("v-sequence-stop").addEventListener("click", () => {
    stopSequence = true;
    $("v-sequence-status").textContent =
      "Stopping after the current calculation batch…";
  });
  $("v-sequence-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || running) return;
    if (!$("v-form").reportValidity() || !$("vi-form").reportValidity()) return;
    try {
      const config = readConfig();
      const protocol = VortexSequence.protocol(
        config,
        Number($("v-hold-ms").value),
        Number($("v-tof-ms").value),
      );
      const camera = VortexImagingUI.settings();
      AbsorptionCamera3D.validate(camera, config.n);
      sequenceActive = true;
      stopSequence = false;
      busy = true;
      controls();
      $("v-sequence-status").textContent = "Preparing…";
      const result = await VortexSequence.run(config, protocol, camera, {
        stopped: () => stopSequence,
        prepared: (next) => {
          solver?.destroy();
          solver = next;
          for (const k of keys) $("v-" + k).value = next.vortex[k];
          syncScattering(true);
          dirty = false;
          render();
        },
        stage: (stage, message) => {
          if (["Holding", "Released", "Expanding"].includes(stage) && solver)
            render();
          $("v-sequence-status").textContent = `${stage} · ${message}`;
        },
        capture: (source, settings) =>
          VortexImagingUI.capture(source, settings),
      });
      result.number = ++runNumber;
      savedRuns.push(result);
      if (savedRuns.length > 3) savedRuns.shift();
      displayRuns();
      $("v-sequence-status").textContent =
        result.status === "complete"
          ? "Complete · image captured and run saved. Compare runs to inspect or export it."
          : `Stopped · partial run saved. ${solver.warning || "No endpoint image captured."}`;
    } catch (error) {
      $("v-sequence-status").textContent = error.message;
    } finally {
      sequenceActive = false;
      busy = false;
      controls();
    }
  });
  $("v-form").addEventListener("submit", (e) => {
    e.preventDefault();
    guarded(async () => {
      const config = readConfig();
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
    ) {
      running = false;
      if (sequenceActive) stopSequence = true;
    }
  });
  window.addEventListener("pagehide", () => {
    stopSequence = true;
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
  recipe("stationary");
  status("Ready to prepare · Run experiment handles the complete sequence.");
  controls();
})();
