"use strict";
(() => {
  if (window.self === window.top) return;
  const $ = id => document.getElementById(`tm-${id}`);
  const keys = Object.keys(TwoMode.presets.tunnelling);
  const historyKeys = ["time_ms", "mean_left", "mean_right", "coherence", "variance_left", "norm", "energy_hz"];
  let solver, current, pinned = null, running = false, timer = null, dirty = false;
  const lessons = {
    tunnelling: "Start with every atom on the left. With tunnelling on and interactions off, the mean population moves right and returns. Halfway through a transfer, a single count is uncertain even though the evolution is deterministic.",
    diffusion: "Turn tunnelling off: the atom-count distribution stays fixed. Interactions rotate different occupation amplitudes at different rates, so coherence falls and later revives. Run this example and pin it before trying the narrower state.",
    narrow: "Start from a prescribed narrower count distribution. Its coherence changes on a different timescale during the same isolated hold. Compare with your pinned coherent run; narrowing number spread can also reduce initial coherence.",
    fock: "Exactly 20 atoms on each side for the default N = 40. The ideal number result is certain, but first-order coherence is zero and its phase is undefined. A definite count is not the same as a definite relative phase.",
  };
  function message(text, error = false) { $("status").textContent = text; $("status").classList.toggle("error", error); }
  function stop() { running = false; clearTimeout(timer); timer = null; }
  function read() { return TwoMode.validate(Object.fromEntries(keys.map(k => [k, k === "initial" ? $(k).value : Number($(k).value)]))); }
  function enableInitial() { $("sigma").disabled = $("initial").value !== "gaussian"; $("phase").disabled = $("initial").value === "fock"; }
  function pending() {
    dirty = true; enableInitial();
    $("pending").textContent = "Settings changed. Prepare to apply; plots still show the prepared run.";
    document.querySelectorAll("[data-preset]").forEach(b => b.setAttribute("aria-pressed", "false"));
  }
  function stage(name) {
    for (const k of keys) $(k).value = TwoMode.presets[name][k];
    pending(); $("lesson").textContent = lessons[name];
    document.querySelectorAll("[data-preset]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.preset === name)));
  }
  function row(state) { return Object.fromEntries(historyKeys.map(k => [k, state[k]])); }
  function prepare() {
    try {
      const next = new TwoMode.Solver(read());
      stop(); solver = next; dirty = false;
      current = { config: { ...solver.config }, step: 0, state: solver.at(0), history: [], measurement: null };
      current.history.push(row(current.state));
      $("pending").textContent = "Settings applied. Changes take effect on Prepare.";
      render(); message("Ready. Run follows 200 equally spaced physical times.");
    } catch (e) { stop(); message(e.message, true); if (current) renderButtons(); }
  }
  function advance() {
    try {
      if (current.step >= 200) { stop(); render(); return; }
      const step = current.step + 1;
      const state = solver.at(current.config.duration_ms * step / 200);
      current.step = step; current.state = state; current.history.push(row(state)); current.measurement = null;
      if (step === 200) stop();
      render(); message(step === 200 ? "Complete. Sample counts, pin this run or prepare another state." : running ? "Running · spectral evolution; no per-step normalization." : "Paused at an exact model time.");
    } catch (e) { stop(); renderButtons(); message(e.message, true); }
  }
  function tick() { if (!running) return; advance(); if (running) timer = setTimeout(tick, 20); }
  const fmt = (x, digits = 3) => x === null ? "Unavailable" : x.toFixed(digits);
  function renderButtons() {
    $("run").textContent = running ? "Pause" : "Run";
    $("run").disabled = current.step >= 200;
    for (const id of ["step", "sample", "pin", "json", "csv"]) $(id).disabled = running;
    $("step").disabled ||= current.step >= 200;
    $("clear").disabled = !pinned;
  }
  function chart(id, xmax, ymax, xlabel, ylabel, draw) {
    const width = Math.max(200, Math.min(700, $(id).clientWidth)), height = 230;
    const left = 42, right = width - 12, top = 20, bottom = height - 38;
    const X = x => left + x / xmax * (right - left), Y = y => bottom - y / ymax * (bottom - top);
    let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${ylabel} against ${xlabel}"><title>${ylabel} against ${xlabel}</title>`;
    for (let i = 0; i <= 4; i++) {
      const y = i * ymax / 4;
      svg += `<path d="M${left} ${Y(y)}H${right}" stroke="#e3e9e8"/><text x="${left - 6}" y="${Y(y) + 4}" text-anchor="end">${ymax === 1 ? y.toFixed(2) : y.toFixed(2)}</text>`;
    }
    for (let i = 0; i <= 4; i++) svg += `<text x="${X(i * xmax / 4)}" y="${bottom + 17}" text-anchor="middle">${(i * xmax / 4).toFixed(xmax < 10 ? 1 : 0)}</text>`;
    svg += `<text x="${left}" y="11">${ylabel}</text><text x="${(left + right) / 2}" y="${height - 3}" text-anchor="middle">${xlabel}</text>`;
    $(id).innerHTML = svg + draw(X, Y, bottom, (right - left) / (xmax + 1)) + "</svg>";
  }
  function line(xs, ys, X, Y, color, dash = false) {
    return `<path d="${xs.map((x, i) => `${i ? "L" : "M"}${X(x).toFixed(3)} ${Y(ys[i]).toFixed(3)}`).join(" ")}" fill="none" stroke="${color}" stroke-width="2" ${dash ? 'stroke-dasharray="5 4"' : ""}/>`;
  }
  function renderCharts() {
    if (!current) return;
    const s = current.state, measurement = current.measurement;
    const maxN = Math.max(current.config.atoms, pinned?.config.atoms || 0);
    const ymax = Math.min(1, Math.max(0.1, ...s.probability, ...(pinned?.state.probability || []), ...(measurement ? measurement.counts.map(v => v / measurement.shots) : [])) * 1.12);
    chart("distribution", maxN, ymax, "Left atom count n", "Probability / frequency", (X, Y, bottom, bw) => {
      let out = s.probability.map((p, k) => `<rect x="${X(k) - bw * 0.4}" y="${Y(p)}" width="${bw * 0.8}" height="${Math.max(0, bottom - Y(p))}" fill="#16796e" opacity=".8"/>`).join("");
      if (measurement) out += measurement.counts.map((v, k) => `<rect x="${X(k) - bw * 0.18}" y="${Y(v / measurement.shots)}" width="${bw * 0.36}" height="${Math.max(0, bottom - Y(v / measurement.shots))}" fill="#b47316"/>`).join("");
      if (pinned) out += line(pinned.state.probability.map((_, i) => i), pinned.state.probability, X, Y, "#7a5c83", true);
      return out;
    });
    const end = Math.max(current.config.duration_ms, pinned?.config.duration_ms || 0);
    chart("coherence-plot", end, 1, "Hold time / ms", "Coherence / left fraction", (X, Y) => {
      let out = "";
      for (const r of [pinned, current]) if (r) {
        const xs = r.history.map(h => h.time_ms);
        out += line(xs, r.history.map(h => h.coherence), X, Y, "#16796e", r === pinned);
        out += line(xs, r.history.map(h => h.mean_left / r.config.atoms), X, Y, "#426fbd", r === pinned);
      }
      // A marker keeps the prepared (one-row) history visible.
      out += `<circle cx="${X(s.time_ms)}" cy="${Y(s.coherence)}" r="3" fill="#16796e"/>`;
      return out;
    });
  }
  function render() {
    const s = current.state, c = current.config;
    $("time").textContent = `${s.time_ms.toFixed(2)} ms`;
    $("left").textContent = fmt(s.mean_left, 2); $("right").textContent = fmt(s.mean_right, 2);
    $("left-bar").style.width = `${Math.max(0, Math.min(100, s.mean_left / c.atoms * 100))}%`;
    $("coherence").textContent = fmt(s.coherence);
    $("spread").textContent = fmt(Math.sqrt(s.variance_left));
    $("noise").textContent = fmt(s.number_noise_ratio);
    $("phase-value").textContent = fmt(s.phase);
    const description = r => `${r.config.initial}, N=${r.config.atoms}, J=${r.config.tunnelling_hz}, U=${r.config.interaction_hz}, δ=${r.config.bias_hz} Hz; t=${r.state.time_ms.toFixed(2)} ms`;
    $("reference").textContent = `Applied: ${description(current)}. ${pinned ? `Pinned (dashed): ${description(pinned)}.` : "No pinned reference."}`;
    $("accuracy").textContent = `Norm drift ${Math.abs(s.norm - 1).toExponential(1)} · energy/h ${s.energy_hz.toFixed(4)} Hz · spectral residual ${solver.eigen.residual.toExponential(1)}.`;
    const m = current.measurement;
    if (m) {
      const mean = m.counts.reduce((total, count, k) => total + count * k, 0) / m.shots;
      $("sample-info").textContent = `${m.shots} independent shots at ${m.time_ms.toFixed(2)} ms · seed ${m.seed} · sample mean left count ${mean.toFixed(3)}. Amber bars show relative frequency.`;
    } else $("sample-info").textContent = "No measurements sampled at this time. Advancing or resetting clears the previous histogram.";
    renderButtons(); renderCharts();
  }
  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $("form").addEventListener("submit", e => { e.preventDefault(); prepare(); });
  $("form").addEventListener("input", pending);
  document.querySelectorAll("[data-preset]").forEach(b => b.addEventListener("click", () => stage(b.dataset.preset)));
  $("run").onclick = () => { if (running) { stop(); renderButtons(); message("Paused. The state is held fixed."); } else { running = true; renderButtons(); tick(); } };
  $("step").onclick = advance;
  $("reset").onclick = () => {
    stop(); current.step = 0; current.state = solver.at(0); current.history = [row(current.state)]; current.measurement = null;
    render(); message(dirty ? "Reset to the prepared state. Edited settings are still pending." : "Reset to the prepared initial state.");
  };
  $("pin").onclick = () => { pinned = JSON.parse(JSON.stringify(current)); render(); message("Reference saved in this tab. Prepare another state to compare."); };
  $("clear").onclick = () => { pinned = null; render(); };
  $("sample").onclick = () => {
    try { current.measurement = TwoMode.sample(current.state, Number($("shots").value), Number($("seed").value)); render(); message("Counts sampled from independent copies of the displayed state."); }
    catch (e) { message(e.message, true); }
  };
  $("json").onclick = () => download("coldatomlab-quantum.json", JSON.stringify({
    schema: "coldatomlab-twomode-v1", version: "0.14.0",
    convention: "n_left=0..N; H/h in Hz; time_ms; right-minus-left phase", current, pinned,
  }, null, 2), "application/json");
  $("csv").onclick = () => {
    const header = ["run", ...keys, ...historyKeys];
    const rows = [header.join(",")];
    for (const [name, r] of [["current", current], ["pinned", pinned]]) if (r)
      for (const h of r.history) rows.push([name, ...keys.map(k => r.config[k]), ...historyKeys.map(k => h[k])].join(","));
    download("coldatomlab-quantum-history.csv", rows.join("\n") + "\n", "text/csv");
  };
  new ResizeObserver(renderCharts).observe($("distribution"));
  const resizeHost = () => parent.postMessage({ type: "quantum-height", height: Math.ceil(document.body.getBoundingClientRect().height) + 4 }, location.origin);
  new ResizeObserver(resizeHost).observe(document.body);
  document.querySelector('footer a[href="gpu.html"]').onclick = event => {
    event.preventDefault();
    parent.postMessage({ type: "quantum-route", route: "lab3d" }, location.origin);
  };
  stage("tunnelling"); prepare();
  new PreparationPanel(document.getElementById("ensemble-lab"), () => ({ ...current.config }));
  new EchoPanel(document.getElementById("echo-lab"));
  new ReadoutPanel(document.getElementById("readout-lab"));
  new FinitePulsePanel(document.getElementById("pulse-lab"));
  document.querySelectorAll("[data-scroll-to]").forEach(button => {
    button.onclick = () => {
      const section = document.getElementById(button.dataset.scrollTo);
      section.setAttribute("tabindex", "-1");
      section.scrollIntoView({ block: "start" });
      section.focus({ preventScroll: true });
    };
  });
})();
