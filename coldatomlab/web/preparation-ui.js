"use strict";
globalThis.PreparationPanel = class {
  constructor(root, getPrepared) {
    this.root = root; this.getPrepared = getPrepared; this.base = { ...Preparation.defaults.base };
    this.data = null; this.running = false; this.paused = false; this.cancelled = false;
    root.innerHTML = `
      <div class="panel-title"><div><p class="eyebrow">PREPARATION VARIATION / AN ENSEMBLE OF STATES</p><h2>What if each preparation is slightly different?</h2></div><span class="tag">Fixed N · no detector noise</span></div>
      <p>Repeat the same intended preparation with small phase and bias offsets. Each run has its own quantum state. Compare the coherence within runs with what remains when their signals are averaged.</p>
      <div class="tm-actions"><button id="ep-demo">Phase variation example</button><button id="ep-interacting">Add interactions</button><button id="ep-copy">Use prepared settings above</button></div>
      <p id="ep-base" class="muted"></p>
      <div class="ep-controls"><label>Initial phase variation ± / rad<input id="ep-phase" type="number" min="0" max="3.141592653589793" step="any" value="0.3"></label><label>Bias variation ± / Hz<input id="ep-bias" type="number" min="0" max="5" step="any" value="1"></label><label>Preparations<input id="ep-count" type="number" min="2" max="128" step="1" value="64"></label><label>Seed<input id="ep-seed" type="number" min="0" max="4294967295" step="1" value="17"></label></div>
      <p class="muted">Offsets are independent and uniform within the selected ranges. Bias stays constant during each run. These ranges are teaching choices, not a measured laboratory noise spectrum.</p>
      <div class="tm-actions"><button id="ep-run" class="primary">Run preparations</button><button id="ep-pause" disabled>Pause</button><button id="ep-cancel" disabled>Cancel</button><button id="ep-json" disabled>Export ensemble JSON</button><button id="ep-csv" disabled>Export ensemble CSV</button></div>
      <p id="ep-status" role="status" aria-live="polite">Ready. This panel runs independently of the experiment above.</p>
      <div id="ep-results" hidden>
        <p id="ep-applied" class="muted"></p>
        <div class="tm-plots ep-plots"><section class="tm-panel"><h3>Individual coherence vs ensemble coherence</h3><div id="ep-history" class="chart"></div><p class="muted">Teal: magnitude of the averaged coherence vector. Blue dashed: average of individual magnitudes. Grey: ideal preparation. Amber dotted: infinite uniform-ensemble guide (J = 0 only).</p></section><section class="tm-panel"><h3>Where do the final phases point?</h3><div id="ep-vectors" class="chart"></div><p class="muted">Thin blue vectors: each preparation at the final time. Thick teal: their vector average. Grey: ideal reference. Vector length is coherence C; a zero vector has no defined phase.</p></section><section class="tm-panel"><h3>Final left-count probabilities</h3><div id="ep-probability" class="chart"></div><p class="muted">Teal: ensemble mixture. Grey outline: ideal preparation. These are probabilities, not sampled atom counts. At J = 0, phase and bias variation leave this distribution unchanged.</p></section><section class="tm-panel"><h3>Read the difference</h3><div id="ep-readings" class="ep-readings"></div><p id="ep-guide-note" class="muted"></p><p class="muted">Total count variance = average within-preparation quantum variance + variance of the preparation means. Technical phase variation can reduce ensemble coherence without increasing count variance.</p></section></div>
        <details><summary>Inspect individual preparations</summary><div class="ep-table"><table><thead><tr><th>Run</th><th>Phase offset / rad</th><th>Bias offset / Hz</th><th>Final coherence</th><th>Final phase / rad</th><th>Mean left count</th></tr></thead><tbody id="ep-rows"></tbody></table></div></details>
      </div>
      <details><summary>Model and analytic check</summary><p>Each realization uses the fixed-N Hamiltonian above with its own initial phase and constant bias. We average density-matrix observables, never state amplitudes. The ensemble coherence is |mean(2⟨a†L aR⟩/N)|; the mean individual coherence is mean(|2⟨a†L aR⟩/N|). They need not agree.</p><p>For isolated wells (J = 0), independent uniform offsets of half-ranges A rad and B Hz give the infinite-ensemble guide C(t) = Cideal(t) |sinc(A) sinc(2πBt)|, where sinc(x) = sin(x)/x and time is in seconds. Finite ensembles fluctuate around this guide. The guide is unavailable for J ≠ 0. The plot samples 101 times; shorten the duration to inspect faster changes.</p><p>This is preparation-to-preparation technical variation, not noise varying during a single evolution, detector noise, thermalization or loss. Each conditional state still evolves unitarily. <a href="https://arxiv.org/html/1203.5359v1#S4.SS3" target="_blank" rel="noopener">Gross (2012), differential energy shifts ↗</a> motivates this distinction; the chosen distributions are not a reproduction of that experiment.</p></details>`;
    this.$ = id => root.querySelector(`#ep-${id}`);
    this.$("demo").onclick = () => this.example(false);
    this.$("interacting").onclick = () => this.example(true);
    this.$("copy").onclick = () => { this.base = getPrepared(); this.describe(); this.message("Copied applied settings, not pending edits. Click Run preparations to apply here."); };
    this.$("run").onclick = () => this.run();
    this.$("pause").onclick = () => { this.paused = !this.paused; this.buttons(); this.message(this.paused ? "Paused after the current completed preparation." : "Resuming preparations…"); };
    this.$("cancel").onclick = () => { this.cancelled = true; this.paused = false; this.message("Cancelling; completed preparations will be retained."); };
    this.$("json").onclick = () => this.download("coldatomlab-preparations.json", JSON.stringify(this.data, null, 2), "application/json");
    this.$("csv").onclick = () => {
      const d = this.data, keys = Object.keys(d.aggregate.history[0]), baseKeys = Object.keys(d.plan.base);
      const header = ["status", "completed_preparations", "requested_preparations", "phase_half_range_rad", "bias_half_range_hz", "seed", ...baseKeys, ...keys];
      const rows = d.aggregate.history.map(r => [d.status, d.records.length, d.plan.preparations, d.plan.phase_half_range, d.plan.bias_half_range_hz, d.plan.seed, ...baseKeys.map(k => d.plan.base[k]), ...keys.map(k => r[k] ?? "")].join(","));
      this.download("coldatomlab-preparations.csv", [header.join(","), ...rows].join("\n") + "\n", "text/csv");
    };
    new ResizeObserver(() => this.render()).observe(this.$("history"));
    this.describe();
  }
  describe() { const b = this.base; this.$("base").textContent = `Next ensemble: ${b.initial}, N=${b.atoms}, left fraction=${b.left_fraction}, phase=${b.phase.toFixed(3)} rad, J=${b.tunnelling_hz}, U=${b.interaction_hz}, δ=${b.bias_hz} Hz, duration=${b.duration_ms} ms. Manual state and pins are preserved.`; }
  example(interacting) {
    this.base = { ...Preparation.defaults.base, interaction_hz: interacting ? 1 : 0 };
    this.$("phase").value = 0.3; this.$("bias").value = 1;
    this.describe(); this.message("Example settings staged. Click Run preparations.");
  }
  message(text, error = false) { this.$("status").textContent = text; this.$("status").classList.toggle("error", error); }
  buttons() {
    for (const id of ["demo", "interacting", "copy", "phase", "bias", "count", "seed", "run"]) this.$(id).disabled = this.running;
    this.$("pause").disabled = !this.running; this.$("pause").textContent = this.paused ? "Resume" : "Pause";
    this.$("cancel").disabled = !this.running;
    for (const id of ["json", "csv"]) this.$(id).disabled = this.running || !this.data?.records.length || this.data.status === "failed";
  }
  async run() {
    let plan;
    try {
      for (const id of ["phase", "bias", "count", "seed"]) if (!this.$(id).value.trim()) throw new Error("Complete all ensemble settings.");
      plan = Preparation.validate({ base: { ...this.base }, phase_half_range: Number(this.$("phase").value), bias_half_range_hz: Number(this.$("bias").value), preparations: Number(this.$("count").value), seed: Number(this.$("seed").value) });
    } catch (e) { this.message(e.message, true); return; }
    this.running = true; this.paused = false; this.cancelled = false; this.buttons();
    this.message("Preparing independent reference…");
    const breathe = () => new Promise(resolve => setTimeout(resolve, 20));
    try {
      await breathe();
      const reference = Preparation.ideal(plan), records = [];
      this.data = Preparation.report(plan, reference, records, "running"); this.$("results").hidden = true;
      for (const recipe of Preparation.recipes(plan)) {
        while (this.paused && !this.cancelled) await breathe();
        if (this.cancelled) break;
        records.push(Preparation.evolve(recipe));
        this.data = Preparation.report(plan, reference, records, "running");
        this.message(`${records.length}/${plan.preparations} preparations completed. Each bias is fixed for its entire run.`);
        if (records.length === 1 || records.length % 4 === 0) this.render();
        await breathe();
      }
      this.data = Preparation.report(plan, reference, records, records.length === plan.preparations ? "complete" : "cancelled");
      this.message(`${this.data.status === "complete" ? "Complete" : "Cancelled"} · ${records.length}/${plan.preparations} preparations retained. ${records.length ? "Exports include the completed ensemble." : "No completed result to export."}`);
    } catch (e) { if (this.data) this.data.status = "failed"; this.message(`Stopped: ${e.message}`, true); }
    finally { this.running = false; this.paused = false; this.buttons(); this.render(); }
  }
  download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  chart(id, xmax, ymax, xlabel, ylabel, draw) {
    const w = Math.max(200, Math.min(650, this.$(id).clientWidth)), h = 230, left = 42, right = w - 12, top = 22, bottom = 191;
    const X = x => left + x / xmax * (right - left), Y = y => bottom - y / ymax * (bottom - top);
    let svg = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${ylabel} against ${xlabel}"><title>${ylabel} against ${xlabel}</title>`;
    for (let i = 0; i <= 4; i++) svg += `<path d="M${left} ${Y(i*ymax/4)}H${right}" stroke="#e2e9e6"/><text x="${left-5}" y="${Y(i*ymax/4)+4}" text-anchor="end">${(i*ymax/4).toFixed(2)}</text>`;
    for (let i = 0; i <= 4; i++) svg += `<text x="${X(i*xmax/4)}" y="${bottom+17}" text-anchor="middle">${(i*xmax/4).toFixed(0)}</text>`;
    this.$(id).innerHTML = svg + `<text x="${left}" y="12">${ylabel}</text><text x="${(left+right)/2}" y="226" text-anchor="middle">${xlabel}</text>` + draw(X, Y, bottom, (right-left)/(xmax+1)) + "</svg>";
  }
  path(rows, x, y, X, Y, color, dash = "") { return `<path d="${rows.map((r, i) => `${i ? "L" : "M"}${X(r[x])} ${Y(r[y])}`).join(" ")}" fill="none" stroke="${color}" stroke-width="2" stroke-dasharray="${dash}"/>`; }
  render() {
    const d = this.data;
    if (!d?.records.length) return;
    this.$("results").hidden = false;
    const b = d.plan.base, history = d.aggregate.history, end = history.at(-1);
    this.$("applied").textContent = `Displayed: ${d.records.length}/${d.plan.preparations} preparations · ${b.initial}, N=${b.atoms}, J=${b.tunnelling_hz}, U=${b.interaction_hz}, δ=${b.bias_hz} Hz · phase ±${d.plan.phase_half_range} rad · bias ±${d.plan.bias_half_range_hz} Hz · seed ${d.plan.seed} · final time ${b.duration_ms} ms.`;
    this.chart("history", b.duration_ms, 1, "Time / ms", "Coherence C", (X,Y) => {
      let out = this.path(history, "time_ms", "ideal_coherence", X,Y,"#87908e","6 4") + this.path(history,"time_ms","mean_individual_coherence",X,Y,"#426fbd","3 3");
      if (b.tunnelling_hz === 0) out += this.path(history,"time_ms","guide_coherence",X,Y,"#b47316","2 4");
      return out + this.path(history,"time_ms","ensemble_coherence",X,Y,"#16796e");
    });
    const w = Math.max(200, Math.min(650, this.$("vectors").clientWidth)), h = 230, cx = w/2, cy = 113, radius = Math.min(85, (w-60)/2);
    const vector = (re,im,color,width,opacity=1) => `<path d="M${cx} ${cy}L${cx+radius*re} ${cy-radius*im}" stroke="${color}" stroke-width="${width}" opacity="${opacity}"/><circle cx="${cx+radius*re}" cy="${cy-radius*im}" r="2.5" fill="${color}" opacity="${opacity}"/>`;
    let vectors = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Final normalized coherence vectors in the complex plane"><circle cx="${cx}" cy="${cy}" r="${radius}" stroke="#c9d8d1" fill="none"/><path d="M${cx-radius} ${cy}H${cx+radius}M${cx} ${cy-radius}V${cy+radius}" stroke="#e2e9e6"/><text x="${cx+radius+4}" y="${cy+4}">Re</text><text x="${cx+5}" y="${cy-radius-5}">Im</text>`;
    for (const r of d.records) vectors += vector(r.state.coherence_real,r.state.coherence_imag,"#426fbd",1,.35);
    vectors += vector(d.ideal.state.coherence_real,d.ideal.state.coherence_imag,"#727b78",2) + vector(end.coherence_real,end.coherence_imag,"#16796e",4);
    this.$("vectors").innerHTML = vectors + `<text x="${cx}" y="224" text-anchor="middle">Final time ${b.duration_ms} ms · circle C = 1</text></svg>`;
    const prob = d.aggregate.probability, ideal = d.ideal.state.probability, ymax = Math.min(1, Math.max(.1,...prob,...ideal)*1.1);
    this.chart("probability", b.atoms, ymax, "Left atom count n", "Probability", (X,Y,bottom,bw) => prob.map((p,k) => `<rect x="${X(k)-bw*.4}" y="${Y(p)}" width="${bw*.8}" height="${Math.max(0,bottom-Y(p))}" fill="#16796e"/><rect x="${X(k)-bw*.45}" y="${Y(ideal[k])}" width="${bw*.9}" height="${Math.max(0,bottom-Y(ideal[k]))}" fill="none" stroke="#87908e"/>`).join(""));
    const reading = (label,value,unit="") => `<div><span>${label}</span><strong>${value.toFixed(4)}${unit}</strong></div>`;
    this.$("readings").innerHTML = reading("Ensemble coherence",end.ensemble_coherence)+reading("Mean individual coherence",end.mean_individual_coherence)+reading("Ideal coherence",end.ideal_coherence)+reading("Total count variance",end.total_variance," atoms²")+reading("Within-preparation variance",end.within_variance," atoms²")+reading("Between-preparation variance",end.between_variance," atoms²");
    this.$("guide-note").textContent = b.tunnelling_hz === 0 ? "The amber guide describes infinitely many uniform draws. A finite ensemble need not reach it exactly; it can retain residual coherence." : "Analytic uniform-ensemble guide unavailable: J is nonzero. The displayed curves come from independent numerical evolutions.";
    this.$("rows").innerHTML = d.records.map(r => `<tr><td>${r.index+1}</td><td>${r.phase_offset.toFixed(4)}</td><td>${r.bias_offset_hz.toFixed(4)}</td><td>${r.state.coherence.toFixed(4)}</td><td>${r.state.phase === null ? "Unavailable" : r.state.phase.toFixed(4)}</td><td>${r.state.mean_left.toFixed(4)}</td></tr>`).join("");
  }
};
