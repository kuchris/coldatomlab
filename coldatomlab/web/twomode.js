"use strict";

// Fixed-N Bose-Hubbard solver, independent of the DOM and rendering cadence.
(() => {
  const defaults = { atoms: 40, tunnelling_hz: 5, interaction_hz: 0, bias_hz: 0,
    initial: "coherent", left_fraction: 1, phase: 0, sigma: 1.5, duration_ms: 100 };
  function validate(input) {
    const c = { ...defaults, ...input };
    for (const [key, lo, hi] of [["atoms", 2, 100], ["tunnelling_hz", 0, 20],
      ["interaction_hz", 0, 2], ["bias_hz", -20, 20], ["left_fraction", 0, 1],
      ["phase", -Math.PI, Math.PI], ["sigma", 0.25, 20], ["duration_ms", 1, 1000]]) {
      if (!Number.isFinite(c[key]) || c[key] < lo || c[key] > hi)
        throw new Error(`${key} must be between ${lo} and ${hi}.`);
    }
    if (!Number.isInteger(c.atoms)) throw new Error("Atom number must be an integer.");
    if (!["coherent", "gaussian", "fock"].includes(c.initial)) throw new Error("Unknown initial state.");
    if (Object.keys(c).some(k => !Object.hasOwn(defaults, k))) throw new Error("Unknown model parameter.");
    return c;
  }
  function initial(c) {
    const n = c.atoms, p = c.left_fraction;
    const r = new Float64Array(n + 1), im = new Float64Array(n + 1);
    let logChoose = 0, norm = 0;
    for (let k = 0; k <= n; k++) {
      let a;
      if (c.initial === "fock") a = k === Math.round(n * p) ? 1 : 0;
      else if (c.initial === "gaussian") a = Math.exp(-(((k - n * p) / c.sigma) ** 2) / 4);
      else if (p === 0 || p === 1) a = k === n * p ? 1 : 0;
      else a = Math.exp((logChoose + k * Math.log(p) + (n - k) * Math.log1p(-p)) / 2);
      const angle = (n - k) * c.phase;
      r[k] = a * Math.cos(angle); im[k] = a * Math.sin(angle); norm += a * a;
      logChoose += Math.log((n - k) / (k + 1));
    }
    // Initial preparation only. Time evolution never normalizes the state.
    for (let k = 0; k <= n; k++) { r[k] /= Math.sqrt(norm); im[k] /= Math.sqrt(norm); }
    return { r, im };
  }
  function matrix(c) {
    const size = c.atoms + 1, a = new Float64Array(size * size);
    for (let k = 0; k < size; k++) {
      const m = k - c.atoms / 2;
      a[k * size + k] = c.interaction_hz * m * m - c.bias_hz * m;
      if (k < size - 1) a[k * size + k + 1] = a[(k + 1) * size + k] =
        -c.tunnelling_hz * Math.sqrt((k + 1) * (c.atoms - k));
    }
    return a;
  }
  // Cyclic Jacobi rotations. Check residual and orthogonality before accepting.
  function eigensystem(h, n) {
    const a = h.slice(), v = new Float64Array(n * n);
    let scale = 1;
    for (let i = 0; i < n; i++) { v[i * n + i] = 1; scale = Math.max(scale, Math.abs(a[i * n + i])); }
    for (const x of a) scale = Math.max(scale, Math.abs(x));
    for (let sweep = 0; sweep < 60; sweep++) {
      let largest = 0;
      for (let p = 0; p < n - 1; p++) for (let q = p + 1; q < n; q++) {
        const apq = a[p * n + q]; largest = Math.max(largest, Math.abs(apq));
        if (Math.abs(apq) < 2e-15 * scale) continue;
        const tau = (a[q * n + q] - a[p * n + p]) / (2 * apq);
        const t = (tau >= 0 ? 1 : -1) / (Math.abs(tau) + Math.hypot(1, tau));
        const cs = 1 / Math.hypot(1, t), sn = t * cs;
        a[p * n + p] -= t * apq; a[q * n + q] += t * apq;
        a[p * n + q] = a[q * n + p] = 0;
        for (let k = 0; k < n; k++) {
          if (k !== p && k !== q) {
            const kp = a[k * n + p], kq = a[k * n + q];
            a[k * n + p] = a[p * n + k] = cs * kp - sn * kq;
            a[k * n + q] = a[q * n + k] = sn * kp + cs * kq;
          }
          const vp = v[k * n + p], vq = v[k * n + q];
          v[k * n + p] = cs * vp - sn * vq; v[k * n + q] = sn * vp + cs * vq;
        }
      }
      if (largest < 2e-15 * scale) break;
      if (sweep === 59) throw new Error("Spectral solver did not converge.");
    }
    const values = Float64Array.from({ length: n }, (_, i) => a[i * n + i]);
    let residual = 0, orthogonality = 0;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      let hv = 0, vv = 0;
      for (let k = 0; k < n; k++) { hv += h[i * n + k] * v[k * n + j]; vv += v[k * n + i] * v[k * n + j]; }
      residual = Math.max(residual, Math.abs(hv - v[i * n + j] * values[j]) / scale);
      orthogonality = Math.max(orthogonality, Math.abs(vv - (i === j ? 1 : 0)));
    }
    if (residual > 1e-11 || orthogonality > 1e-11) throw new Error("Spectral accuracy check failed.");
    return { values, vectors: v, residual, orthogonality };
  }
  function diagnostics(c, r, im) {
    const n = c.atoms, probability = Array.from(r, (x, k) => x * x + im[k] * im[k]);
    let norm = 0, mean = 0, re = 0, imaginary = 0, energy = 0;
    for (let k = 0; k <= n; k++) { norm += probability[k]; mean += k * probability[k]; }
    let variance = 0;
    for (let k = 0; k <= n; k++) {
      variance += (k - mean) ** 2 * probability[k];
      const m = k - n / 2;
      energy += probability[k] * (c.interaction_hz * m * m - c.bias_hz * m);
      if (k < n) {
        const f = Math.sqrt((k + 1) * (n - k));
        re += f * (r[k + 1] * r[k] + im[k + 1] * im[k]);
        imaginary += f * (r[k + 1] * im[k] - im[k + 1] * r[k]);
      }
    }
    energy -= 2 * c.tunnelling_hz * re;
    const coherence = 2 * Math.hypot(re, imaginary) / n;
    const binomialVariance = mean * (1 - mean / n);
    return { probability, norm, mean_left: mean, mean_right: n * norm - mean,
      variance_left: variance, coherence, phase: coherence > 1e-8 ? Math.atan2(imaginary, re) : null,
      coherence_real: 2 * re / n, coherence_imag: 2 * imaginary / n,
      number_noise_ratio: binomialVariance > 1e-8 ? variance / binomialVariance : null,
      energy_hz: energy };
  }
  class Solver {
    constructor(input, initialState = null) {
      this.config = validate(input);
      const n = this.config.atoms + 1;
      this.eigen = eigensystem(matrix(this.config), n);
      this.initial = initialState === null ? initial(this.config) : {
        r: Float64Array.from(initialState.r), im: Float64Array.from(initialState.im),
      };
      if (this.initial.r.length !== n || this.initial.im.length !== n ||
          [...this.initial.r, ...this.initial.im].some(x => !Number.isFinite(x)) ||
          Math.abs(this.initial.r.reduce((s, x, k) => s + x*x + this.initial.im[k]**2, 0) - 1) > 1e-9)
        throw new Error("Incoming state must be finite, normalized and have N + 1 amplitudes. It is not renormalized.");
      this.br = new Float64Array(n); this.bi = new Float64Array(n);
      for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
        this.br[j] += this.eigen.vectors[k * n + j] * this.initial.r[k];
        this.bi[j] += this.eigen.vectors[k * n + j] * this.initial.im[k];
      }
    }
    at(time_ms) {
      if (!Number.isFinite(time_ms) || time_ms < 0 || time_ms > this.config.duration_ms + 1e-9)
        throw new Error("Time is outside this experiment.");
      const n = this.config.atoms + 1, r = new Float64Array(n), im = new Float64Array(n);
      for (let j = 0; j < n; j++) {
        const theta = -2 * Math.PI * this.eigen.values[j] * time_ms / 1000;
        const re = this.br[j] * Math.cos(theta) - this.bi[j] * Math.sin(theta);
        const imaginary = this.br[j] * Math.sin(theta) + this.bi[j] * Math.cos(theta);
        for (let k = 0; k < n; k++) { r[k] += this.eigen.vectors[k * n + j] * re; im[k] += this.eigen.vectors[k * n + j] * imaginary; }
      }
      const observed = diagnostics(this.config, r, im);
      if (Math.abs(observed.norm - 1) > 1e-9) throw new Error("Norm accuracy check failed; run stopped.");
      return { time_ms, real: Array.from(r), imag: Array.from(im), ...observed };
    }
  }
  function sample(state, shots, seed) {
    if (!Number.isInteger(shots) || shots < 1 || shots > 10000) throw new Error("Shots must be an integer from 1 to 10000.");
    if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) throw new Error("Seed must be an unsigned 32-bit integer.");
    const counts = Array(state.probability.length).fill(0);
    let rng = seed >>> 0;
    for (let i = 0; i < shots; i++) {
      rng = (Math.imul(1664525, rng) + 1013904223) >>> 0;
      const u = (rng + 0.5) / 4294967296;
      let sum = 0, k = 0;
      for (; k < counts.length - 1; k++) { sum += state.probability[k]; if (u < sum) break; }
      counts[k]++;
    }
    return { time_ms: state.time_ms, shots, seed, counts };
  }
  const presets = {
    tunnelling: { ...defaults },
    diffusion: { ...defaults, initial: "coherent", left_fraction: 0.5, tunnelling_hz: 0, interaction_hz: 1, duration_ms: 500 },
    narrow: { ...defaults, initial: "gaussian", left_fraction: 0.5, tunnelling_hz: 0, interaction_hz: 1, duration_ms: 500 },
    fock: { ...defaults, initial: "fock", left_fraction: 0.5, tunnelling_hz: 0, interaction_hz: 1, duration_ms: 500 },
  };
  globalThis.TwoMode = { Solver, validate, initial, matrix, diagnostics, sample, presets };
})();
