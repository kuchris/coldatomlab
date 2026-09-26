"use strict";
// Exact isolated-well evolution; the instantaneous pulse swaps occupation amplitudes.
(() => {
  const convention = "J=0; H/h=U(n-N/2)^2-bias(n-N/2); midpoint S|n,N-n>=|N-n,n>; fixed-N pulse global phase omitted";
  const defaults = { ...Preparation.defaults, base: { ...Preparation.defaults.base }, phase_half_range: 0, bias_half_range_hz: 2 };
  function validate(input) {
    const p = Preparation.validate(input);
    if (p.base.tunnelling_hz !== 0) throw new Error("Spin echo requires J = 0 during the holds. Nonzero tunnelling is not silently removed.");
    return p;
  }
  function checkpoints(duration) {
    const rows = [];
    for (let i = 0; i <= 100; i++) {
      rows.push({ time_ms: duration * i / 100, pulse_applied: i > 50 });
      if (i === 50) rows.push({ time_ms: duration / 2, pulse_applied: true });
    }
    return rows;
  }
  function swap(state) { return { r: Float64Array.from(state.r).reverse(), im: Float64Array.from(state.im).reverse() }; }
  function propagate(c, state, time_ms) {
    if (c.tunnelling_hz !== 0 || !Number.isFinite(time_ms) || time_ms < 0) throw new Error("Invalid isolated hold.");
    const r = new Float64Array(c.atoms + 1), im = new Float64Array(c.atoms + 1);
    for (let k = 0; k <= c.atoms; k++) {
      const m = k - c.atoms / 2, a = -2 * Math.PI * (c.interaction_hz * m * m - c.bias_hz * m) * time_ms / 1000;
      r[k] = state.r[k] * Math.cos(a) - state.im[k] * Math.sin(a);
      im[k] = state.r[k] * Math.sin(a) + state.im[k] * Math.cos(a);
    }
    return { r, im };
  }
  function observe(c, state, time_ms) {
    const d = TwoMode.diagnostics(c, state.r, state.im);
    if (!Number.isFinite(d.norm) || Math.abs(d.norm - 1) > 1e-9) throw new Error("Echo norm check failed; no renormalization applied.");
    return { time_ms, real: Array.from(state.r), imag: Array.from(state.im), ...d };
  }
  function evolve(recipe) {
    const c = TwoMode.validate(recipe.config);
    if (c.tunnelling_hz !== 0) throw new Error("Spin echo requires J = 0.");
    const initial = TwoMode.initial(c), half = c.duration_ms / 2;
    const before = propagate(c, initial, half), after = swap(before);
    const record = { ...recipe, pulse_before: observe(c, before, half), pulse_after: observe(c, after, half), no_echo: { history: [] }, echo: { history: [] } };
    for (const point of checkpoints(c.duration_ms)) {
      for (const arm of ["no_echo", "echo"]) {
        const applied = arm === "echo" && point.pulse_applied;
        const state = observe(c, propagate(c, applied ? after : initial, applied ? point.time_ms - half : point.time_ms), point.time_ms);
        record[arm].state = state;
        record[arm].history.push({ ...Object.fromEntries(Preparation.historyKeys.map(k => [k, state[k]])), pulse_applied: applied });
      }
    }
    return record;
  }
  function ideal(plan) { return evolve({ index: -1, phase_offset: 0, bias_offset_hz: 0, config: { ...plan.base } }); }
  function aggregate(plan, reference, records) {
    if (!records.length) return null;
    return Object.fromEntries(["no_echo", "echo"].map(arm => {
      const result = Preparation.aggregate(plan, reference[arm], records.map(r => r[arm]));
      result.history.forEach((row, i) => {
        row.pulse_applied = reference[arm].history[i].pulse_applied;
        const effective = row.pulse_applied ? row.time_ms - plan.base.duration_ms : row.time_ms;
        row.guide_coherence = row.ideal_coherence * Math.abs(Preparation.sinc(plan.phase_half_range) * Preparation.sinc(2 * Math.PI * plan.bias_half_range_hz * effective / 1000));
      });
      return [arm, result];
    }));
  }
  function report(plan, reference, records, status) {
    return { schema: "coldatomlab-echo-v1", version: "0.14.0", convention, plan, status, ideal: reference, records, aggregate: aggregate(plan, reference, records) };
  }
  globalThis.Echo = { defaults, convention, validate, checkpoints, swap, propagate, observe, evolve, ideal, aggregate, report };
})();
