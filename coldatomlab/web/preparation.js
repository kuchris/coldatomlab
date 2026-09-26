"use strict";
// Ensemble of independent pure-state preparations; never average amplitudes.
(() => {
  const historyKeys = ["time_ms", "mean_left", "variance_left", "coherence", "coherence_real", "coherence_imag", "norm", "energy_hz"];
  const defaults = { base: { ...TwoMode.presets.diffusion, interaction_hz: 0 }, phase_half_range: 0.3, bias_half_range_hz: 1, preparations: 64, seed: 17 };
  function validate(input) {
    const p = { ...defaults, ...input, base: TwoMode.validate(input.base || defaults.base) };
    for (const [key, lo, hi] of [["phase_half_range", 0, Math.PI], ["bias_half_range_hz", 0, 5], ["preparations", 2, 128], ["seed", 0, 4294967295]])
      if (!Number.isFinite(p[key]) || p[key] < lo || p[key] > hi) throw new Error(`${key} must be between ${lo} and ${hi}.`);
    if (!Number.isInteger(p.preparations) || !Number.isInteger(p.seed)) throw new Error("Preparation count and seed must be integers.");
    if (Math.abs(p.base.bias_hz) + p.bias_half_range_hz > 20) throw new Error("Base bias plus its variation must stay within ±20 Hz; no samples are clipped.");
    if (Object.keys(p).some(k => !Object.hasOwn(defaults, k))) throw new Error("Unknown preparation parameter.");
    return p;
  }
  function recipes(input) {
    const p = validate(input); let rng = p.seed >>> 0;
    const uniform = () => { rng = (Math.imul(1664525, rng) + 1013904223) >>> 0; return (rng + 0.5) / 4294967296; };
    return Array.from({ length: p.preparations }, (_, index) => {
      const phase_offset = (2 * uniform() - 1) * p.phase_half_range;
      const bias_offset_hz = (2 * uniform() - 1) * p.bias_half_range_hz;
      const phase = Math.atan2(Math.sin(p.base.phase + phase_offset), Math.cos(p.base.phase + phase_offset));
      return { index, phase_offset, bias_offset_hz, config: { ...p.base, phase, bias_hz: p.base.bias_hz + bias_offset_hz } };
    });
  }
  function evolve(recipe) {
    const solver = new TwoMode.Solver(recipe.config), history = [];
    let state;
    for (let i = 0; i <= 100; i++) {
      state = solver.at(recipe.config.duration_ms * i / 100);
      history.push(Object.fromEntries(historyKeys.map(k => [k, state[k]])));
    }
    return { ...recipe, state, history };
  }
  function ideal(plan) { return evolve({ index: -1, phase_offset: 0, bias_offset_hz: 0, config: { ...plan.base } }); }
  const sinc = x => Math.abs(x) < 1e-8 ? 1 - x * x / 6 : Math.sin(x) / x;
  function aggregate(plan, reference, records) {
    if (!records.length) return null;
    const count = records.length;
    const history = reference.history.map((ref, i) => {
      const rows = records.map(r => r.history[i]);
      const mean = key => rows.reduce((s, r) => s + r[key], 0) / count;
      const mean_left = mean("mean_left"), coherence_real = mean("coherence_real"), coherence_imag = mean("coherence_imag");
      const within_variance = mean("variance_left");
      const between_variance = rows.reduce((s, r) => s + (r.mean_left - mean_left) ** 2, 0) / count;
      return { time_ms: ref.time_ms, mean_left, coherence_real, coherence_imag,
        ensemble_coherence: Math.hypot(coherence_real, coherence_imag), mean_individual_coherence: mean("coherence"), ideal_coherence: ref.coherence,
        guide_coherence: plan.base.tunnelling_hz === 0 ? ref.coherence * Math.abs(sinc(plan.phase_half_range) * sinc(2 * Math.PI * plan.bias_half_range_hz * ref.time_ms / 1000)) : null,
        within_variance, between_variance, total_variance: within_variance + between_variance, mean_norm: mean("norm") };
    });
    const probability = Array.from({ length: plan.base.atoms + 1 }, (_, k) => records.reduce((s, r) => s + r.state.probability[k], 0) / count);
    return { count, history, probability };
  }
  function report(plan, reference, records, status) {
    return { schema: "coldatomlab-preparation-v1", version: "0.14.0",
      convention: "fixed-N density mixture; independent uniform offsets; bias constant per realization",
      plan, status, ideal: reference, records, aggregate: aggregate(plan, reference, records) };
  }
  globalThis.Preparation = { defaults, validate, recipes, evolve, ideal, aggregate, report, historyKeys, sinc };
})();
