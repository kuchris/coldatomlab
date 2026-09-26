"use strict";
globalThis.EchoPanel = class {
  constructor(root) {
    this.root = root; this.data = null; this.running = false; this.paused = false; this.cancelled = false; this.timer = null;
    root.innerHTML = `
      <div class="panel-title"><div><p class="eyebrow">SPIN ECHO / A PAIRED COMPARISON</p><h2>Can the phases meet again?</h2></div><span class="tag">Ideal instantaneous L/R swap</span></div>
      <p>Give both arms exactly the same preparation and static bias. Halfway through one arm, exchange the left and right modes. Follow the coherence vectors as they spread, flip and refocus.</p>
      <div class="tm-actions"><button id="se-static">Refocus static bias</button><button id="se-phase">Keep initial phase spread</button><button id="se-interacting">Keep interactions</button></div>
      <p class="muted">Balanced coherent initial state · J = 0 during both holds · base phase and bias = 0. N stays fixed across preparations. Changes apply on Run comparison.</p>
      <div class="ep-controls se-controls">
        <label>Atoms N<input id="se-atoms" type="number" min="2" max="100" step="1" value="40"></label>
        <label>Interaction U / Hz<input id="se-interaction_hz" type="number" min="0" max="2" step="any" value="0"></label>
        <label>Total hold / ms<input id="se-duration_ms" type="number" min="1" max="1000" step="any" value="500"></label>
        <label>Initial phase variation ± / rad<input id="se-phase_half_range" type="number" min="0" max="3.141592653589793" step="any" value="0"></label>
        <label>Static bias variation ± / Hz<input id="se-bias_half_range_hz" type="number" min="0" max="5" step="any" value="2"></label>
        <label>Preparations<input id="se-preparations" type="number" min="2" max="128" step="1" value="64"></label>
        <label>Seed<input id="se-seed" type="number" min="0" max="4294967295" step="1" value="17"></label>
      </div>
      <p class="muted">Independent uniform offsets; each drawn bias is constant for its whole run. The two arms share every draw. These are teaching distributions, not measured noise.</p>
      <div class="tm-actions"><button id="se-run" class="primary">Run comparison</button><button id="se-pause" disabled>Pause computation</button><button id="se-cancel" disabled>Cancel comparison</button><button id="se-json" disabled>Export echo JSON</button><button id="se-csv" disabled>Export echo CSV</button></div>
      <p id="se-status" role="status" aria-live="polite">Ready. Manual and preparation-variation results are preserved.</p>
      <div id="se-results" hidden>
        <p id="se-applied" class="muted"></p>
        <div class="se-sequence" aria-label="Echo sequence"><div id="se-stage-first"><span>01 / FIRST HOLD</span><b id="se-first-label"></b></div><div id="se-stage-pulse"><span>02 / IDEAL π PULSE</span><b>L ↔ R</b></div><div id="se-stage-second"><span>03 / SECOND HOLD</span><b id="se-second-label"></b></div></div>
        <div class="se-scrub"><div><h3 id="se-time"></h3><p id="se-stage-note" class="muted"></p></div><button id="se-play">Play timeline</button></div>
        <label class="se-slider">Inspect time<input id="se-slider" type="range" min="0" max="101" step="1" value="101"></label>
        <div class="tm-actions"><button id="se-start">Start</button><button id="se-before">Before pulse</button><button id="se-after">After pulse</button><button id="se-end">End</button></div>
        <p class="muted">Playback selects precomputed physical states. Two consecutive snapshots show the same midpoint immediately before and after the instantaneous pulse.</p>
        <div class="se-vector-grid"><section class="tm-panel"><h3 class="se-free-color">No echo</h3><div id="se-vectors-free" class="chart"></div><p id="se-reading-free"></p></section><section class="tm-panel"><h3 class="se-echo-color">With echo</h3><div id="se-vectors-echo" class="chart"></div><p id="se-reading-echo"></p></section></div>
        <p class="muted">Thin arrows: individual normalized coherence vectors q = 2⟨a†L aR⟩/N. Thick arrow: their complex average. Circle: C = 1. Zero-length vectors have no defined phase. These are model moments, not atom positions or camera images.</p>
        <section class="tm-panel se-history-panel"><h3>Same offsets. Different sequences.</h3><div id="se-history" class="chart"></div><p class="muted"><span class="se-free-color">Rose: no echo.</span> <span class="se-echo-color">Teal: with echo.</span> Solid: finite-ensemble coherence. Dotted: infinite uniform-ensemble guides. Grey dashed: echo with no offsets. The vertical pulse marker is at half the hold; the dark cursor follows the selected snapshot.</p></section>
        <p id="se-explanation" class="se-explanation"></p>
      </div>
      <details><summary>What this echo can and cannot reverse</summary><p>The ideal swap sends |n, N−n⟩ to |N−n, n⟩. In fixed N, a π rotation differs only by a common phase, which we omit. At the pulse, left/right populations exchange and q becomes q*. It does not erase an initial phase distribution.</p><p>For J = 0, H/h = U(n−N/2)² − δ(n−N/2), with U and δ in Hz. The swap reverses the linear bias term but leaves the interaction term unchanged. A midpoint pulse cancels the accumulated static bias at the end, even with interactions, but does not reverse interaction dynamics. Norm is preserved without time-step renormalization. Pulse energy can change; an ideal swap is not a model of energy exchange with a drive.</p><p>For uniform half-ranges A rad and B Hz, no-echo coherence has guide Cideal(t)|sinc(A)sinc(2πBt)|. After the echo pulse, the guide is Cideal,echo(t)|sinc(A)sinc(2πB(t−T))|, with t and total T in seconds, sinc(x) = sin(x)/x and sinc(0) = 1. Finite ensembles need not coincide with these infinite-ensemble guides. The full occupation state is evolved; the guide is only a check.</p><p>Our modes are spatial left/right wells. This instantaneous swap does not simulate microwave coupling, a finite tunnelling pulse, pulse errors, time-varying noise, detector noise or losses. Higher spatial modes are omitted. Shorten the hold to resolve faster dynamics in the 101 sampled times.</p><p><a href="https://journals.aps.org/pr/abstract/10.1103/PhysRev.80.580" target="_blank" rel="noopener">Hahn (1950), Spin Echoes ↗</a> supplies the echo concept; <a href="https://arxiv.org/html/1203.5359v1#S4.SS3" target="_blank" rel="noopener">Gross (2012), §IV.3 ↗</a> discusses static differential-shift noise and echo in cold-atom systems. This is an ideal teaching comparison, not a reconstruction of either experiment.</p></details>`;
    this.$ = id => root.querySelector(`#se-${id}`);
    this.fields = ["atoms", "interaction_hz", "duration_ms", "phase_half_range", "bias_half_range_hz", "preparations", "seed"];
    for (const name of ["static", "phase", "interacting"]) this.$(name).onclick = () => this.preset(name);
    this.$("run").onclick = () => this.run();
    this.$("pause").onclick = () => { this.paused = !this.paused; this.buttons(); this.message(this.paused ? "Paused between completed pairs." : "Resuming comparison…"); };
    this.$("cancel").onclick = () => { this.cancelled = true; this.paused = false; this.message("Cancelling; completed pairs will be retained."); };
    this.$("slider").oninput = () => { this.stopPlayback(); this.render(); };
    for (const [name, index] of [["start", 0], ["before", 50], ["after", 51], ["end", 101]])
      this.$(name).onclick = () => { this.stopPlayback(); this.$("slider").value = index; this.render(); };
    this.$("play").onclick = () => {
      if (this.timer) { this.stopPlayback(); return; }
      if (+this.$("slider").value === 101) this.$("slider").value = 0;
      this.$("play").textContent = "Pause timeline";
      this.render();
      this.timer = setInterval(() => { this.$("slider").value = +this.$("slider").value + 1; this.render(); if (+this.$("slider").value === 101) this.stopPlayback(); }, 80);
    };
    this.$("json").onclick = () => this.download("coldatomlab-echo.json", JSON.stringify(this.data, null, 2), "application/json");
    this.$("csv").onclick = () => {
      const d = this.data, keys = Object.keys(d.aggregate.echo.history[0]), baseKeys = Object.keys(d.plan.base);
      const header = ["arm", "status", "completed_pairs", "requested_pairs", "phase_half_range_rad", "bias_half_range_hz", "seed", ...baseKeys, ...keys];
      const rows = [header.join(",")];
      for (const arm of ["no_echo", "echo"]) for (const r of d.aggregate[arm].history)
        rows.push([arm, d.status, d.records.length, d.plan.preparations, d.plan.phase_half_range, d.plan.bias_half_range_hz, d.plan.seed, ...baseKeys.map(k => d.plan.base[k]), ...keys.map(k => r[k])].join(","));
      this.download("coldatomlab-echo.csv", rows.join("\n") + "\n", "text/csv");
    };
    new ResizeObserver(() => this.render()).observe(this.$("history"));
  }
  preset(name) {
    const values = { atoms: 40, interaction_hz: name === "interacting" ? 1 : 0, duration_ms: name === "interacting" ? 250 : 500, phase_half_range: name === "phase" ? Math.PI / 2 : 0, bias_half_range_hz: 2 };
    for (const [k, v] of Object.entries(values)) this.$(k).value = v;
    this.message("Example settings staged. Click Run comparison.");
  }
  message(text, error = false) { this.$("status").textContent = text; this.$("status").classList.toggle("error", error); }
  stopPlayback() { clearInterval(this.timer); this.timer = null; this.$("play").textContent = "Play timeline"; }
  buttons() {
    for (const id of [...this.fields, "static", "phase", "interacting", "run"]) this.$(id).disabled = this.running;
    this.$("pause").disabled = !this.running; this.$("pause").textContent = this.paused ? "Resume computation" : "Pause computation";
    this.$("cancel").disabled = !this.running;
    for (const id of ["json", "csv"]) this.$(id).disabled = this.running || !this.data?.records.length || this.data.status === "failed";
    for (const id of ["slider", "play", "start", "before", "after", "end"]) this.$(id).disabled = this.running;
  }
  async run() {
    let plan;
    try {
      const v = {};
      for (const k of this.fields) { if (!this.$(k).value.trim()) throw new Error("Complete all echo settings."); v[k] = Number(this.$(k).value); }
      plan = Echo.validate({ base: { ...Echo.defaults.base, atoms: v.atoms, interaction_hz: v.interaction_hz, duration_ms: v.duration_ms }, phase_half_range: v.phase_half_range, bias_half_range_hz: v.bias_half_range_hz, preparations: v.preparations, seed: v.seed });
    } catch (e) { this.message(e.message, true); return; }
    this.stopPlayback(); this.running = true; this.paused = false; this.cancelled = false;
    this.data = null; this.$("results").hidden = true; this.buttons(); this.message("Preparing paired reference…");
    const breathe = () => new Promise(resolve => setTimeout(resolve, 20));
    try {
      await breathe(); const reference = Echo.ideal(plan), records = [];
      this.data = Echo.report(plan, reference, records, "running");
      for (const recipe of Preparation.recipes(plan)) {
        while (this.paused && !this.cancelled) await breathe();
        if (this.cancelled) break;
        records.push(Echo.evolve(recipe)); this.data = Echo.report(plan, reference, records, "running");
        this.message(`${records.length}/${plan.preparations} paired preparations completed.`);
        if (records.length === 1 || records.length % 4 === 0) { this.$("slider").value = 101; this.render(); }
        await breathe();
      }
      this.data = Echo.report(plan, reference, records, records.length === plan.preparations ? "complete" : "cancelled");
      this.message(`${this.data.status === "complete" ? "Complete" : "Cancelled"} · ${records.length}/${plan.preparations} paired preparations retained.`);
    } catch (e) { if (this.data) this.data.status = "failed"; this.message(`Stopped: ${e.message}`, true); }
    finally { this.running = false; this.paused = false; this.buttons(); this.render(); }
  }
  download(name, content, type) { const url = URL.createObjectURL(new Blob([content], { type })), a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  vectors(arm, id, color, i) {
    const d = this.data, w = Math.max(200, Math.min(650, this.$(id).clientWidth)), cx = w / 2, cy = 117, radius = Math.min(88, (w - 60) / 2);
    const marker = `se-arrow-${arm}`;
    let svg = `<svg viewBox="0 0 ${w} 240" role="img" aria-label="${arm === "echo" ? "Echo" : "No echo"} coherence vectors at selected time"><defs><marker id="${marker}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L8 4L0 8Z" fill="${color}"/></marker></defs><circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="#c8d4cf"/><path d="M${cx-radius} ${cy}H${cx+radius}M${cx} ${cy-radius}V${cy+radius}" stroke="#e0e7e4"/><text x="${cx+radius+4}" y="${cy+4}">Re</text><text x="${cx+4}" y="${cy-radius-6}">Im</text>`;
    const arrow = (r, width, opacity) => `<path d="M${cx} ${cy}L${cx + radius*r.coherence_real} ${cy - radius*r.coherence_imag}" fill="none" stroke="${color}" stroke-width="${width}" opacity="${opacity}" ${Math.hypot(r.coherence_real,r.coherence_imag)>1e-8 ? `marker-end="url(#${marker})"` : ""}/>`;
    for (const record of d.records) svg += arrow(record[arm].history[i], 1, .28);
    const row = d.aggregate[arm].history[i]; svg += arrow(row, 3, 1);
    svg += `<text x="${cx}" y="235" text-anchor="middle">Ensemble C = ${row.ensemble_coherence.toFixed(4)}</text></svg>`;
    this.$(id).innerHTML = svg;
    const phase = row.ensemble_coherence > 1e-8 ? `${Math.atan2(row.coherence_imag,row.coherence_real).toFixed(3)} rad` : "Unavailable";
    this.$(arm === "echo" ? "reading-echo" : "reading-free").textContent = `Mean individual C: ${row.mean_individual_coherence.toFixed(4)} · Ensemble phase: ${phase}`;
  }
  render() {
    const d = this.data; if (!d?.records.length) return;
    this.$("results").hidden = false;
    const i = +this.$("slider").value, rows = d.aggregate.echo.history, r = rows[i], duration = d.plan.base.duration_ms, half = duration / 2;
    const free = d.aggregate.no_echo.history;
    this.$("applied").textContent = `Displayed: ${d.records.length}/${d.plan.preparations} paired preparations · N=${d.plan.base.atoms}, U=${d.plan.base.interaction_hz} Hz, hold=${duration} ms · phase ±${d.plan.phase_half_range.toFixed(3)} rad · bias ±${d.plan.bias_half_range_hz} Hz · seed ${d.plan.seed}.`;
    this.$("first-label").textContent = `0 → ${half} ms`; this.$("second-label").textContent = `${half} → ${duration} ms`;
    this.$("time").textContent = `t = ${Number(r.time_ms.toFixed(3))} ms${i === 50 ? " · before pulse" : i === 51 ? " · after pulse" : ""}`;
    this.$("stage-note").textContent = i < 51 ? "Both arms evolve under the same static bias." : i === 51 ? "Only the echo arm swaps L/R: its coherence vectors are reflected across the real axis." : "The same bias keeps acting. Its accumulated effect cancels at the end of the echo arm.";
    for (const [name, active] of [["first", i < 50], ["pulse", i === 50 || i === 51], ["second", i > 51]]) this.$(`stage-${name}`).classList.toggle("active", active);
    this.vectors("no_echo", "vectors-free", "#a84e61", i); this.vectors("echo", "vectors-echo", "#16796e", i);
    const w = Math.max(210, this.$("history").clientWidth), left = 40, right = w - 14, top = 22, bottom = 210;
    const X = t => left + t / duration * (right-left), Y = c => bottom - c * (bottom-top);
    let svg = `<svg viewBox="0 0 ${w} 252" role="img" aria-label="No echo and echo ensemble coherence versus hold time">`;
    for (let k=0;k<=4;k++) svg += `<path d="M${left} ${Y(k/4)}H${right}" stroke="#e0e7e4"/><text x="${left-6}" y="${Y(k/4)+4}" text-anchor="end">${k/4}</text><text x="${X(duration*k/4)}" y="232" text-anchor="middle">${Number((duration*k/4).toFixed(2))}</text>`;
    const path = (history, key, color, dash="", width=2) => `<path d="${history.map((s,k)=>`${k?'L':'M'}${X(s.time_ms)} ${Y(s[key])}`).join(' ')}" fill="none" stroke="${color}" stroke-width="${width}" stroke-dasharray="${dash}"/>`;
    svg += path(rows,"ideal_coherence","#8c9892","6 5",1.5) + path(free,"guide_coherence","#a84e61","2 5",1) + path(rows,"guide_coherence","#16796e","2 5",1) + path(free,"ensemble_coherence","#a84e61") + path(rows,"ensemble_coherence","#16796e");
    svg += `<path d="M${X(half)} ${top}V${bottom}" stroke="#899b93" stroke-dasharray="4 4"/><text x="${X(half)+4}" y="14">π</text><path d="M${X(r.time_ms)} ${top}V${bottom}" stroke="#283e35"/><circle cx="${X(r.time_ms)}" cy="${Y(r.ensemble_coherence)}" r="4" fill="#16796e"/><text x="${left}" y="14">Coherence C</text><text x="${(left+right)/2}" y="249" text-anchor="middle">Hold time / ms</text></svg>`;
    this.$("history").innerHTML = svg;
    this.$("explanation").textContent = `At the selected time: no echo ${free[i].ensemble_coherence.toFixed(4)}; with echo ${r.ensemble_coherence.toFixed(4)}; echo without offsets ${r.ideal_coherence.toFixed(4)}. ${d.plan.base.interaction_hz ? "Interactions still act: the pulse does not reverse U, so coherence need not return to one." : "Without interactions, each individual balanced preparation stays at C = 1."} ${d.plan.phase_half_range ? "Initial phase spread remains; echo only cancels the accumulated static-bias contribution at the end." : "All initial phases match."}`;
  }
};
