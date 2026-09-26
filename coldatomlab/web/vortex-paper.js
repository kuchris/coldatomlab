"use strict";
// Lundh–Pethick–Smith Eqs. 36–39: radial GPE plus Gaussian axial width.
// Independent Float64 browser arithmetic. This is not full 3D GPE evolution.
window.VortexPaper = (() => {
  class Reference {
    constructor(coupling, cells = 512, radius = 24, dt = 0.002) {
      this.n = cells;
      this.dr = radius / cells;
      this.g = 4 * Math.PI * coupling;
      this.dt = dt;
      this.r = Float64Array.from(
        { length: cells },
        (_, i) => (i + 0.5) * this.dr,
      );
      this.w = this.r.map((r) => 2 * Math.PI * r * this.dr);
      this.d = this.r.map((r) => 1 / this.dr ** 2 + 0.5 / r ** 2);
      this.d[cells - 1] += radius / (2 * this.r[cells - 1] * this.dr ** 2);
      this.off = Float64Array.from(
        { length: cells - 1 },
        (_, i) =>
          (-(i + 1) * this.dr) /
          (2 * this.dr ** 2 * Math.sqrt(this.r[i] * this.r[i + 1])),
      );
      this.re = this.r.map(
        (r, i) => r * Math.exp((-r * r) / 2) * Math.sqrt(this.w[i]),
      );
      this.im = new Float64Array(cells);
      this.z = 1;
      this.v = 0;
      this.steps = 0;
      this.normalize();
      this.realFactor = this.factor(0, dt);
      this.imagFactor = this.factor(0.002, 0);
    }
    normalize() {
      let sum = 0;
      for (let i = 0; i < this.n; i++) sum += this.re[i] ** 2 + this.im[i] ** 2;
      const norm = Math.sqrt(sum);
      for (let i = 0; i < this.n; i++) {
        this.re[i] /= norm;
        this.im[i] /= norm;
      }
      return norm;
    }
    factor(hr, hi) {
      const invR = new Float64Array(this.n),
        invI = new Float64Array(this.n),
        cr = new Float64Array(this.n),
        ci = new Float64Array(this.n);
      for (let i = 0; i < this.n; i++) {
        const lower = i ? this.off[i - 1] / 2 : 0;
        const ar =
          1 +
          (hr * this.d[i]) / 2 -
          (i ? lower * (hr * cr[i - 1] - hi * ci[i - 1]) : 0);
        const ai =
            (hi * this.d[i]) / 2 -
            (i ? lower * (hr * ci[i - 1] + hi * cr[i - 1]) : 0),
          den = ar * ar + ai * ai;
        invR[i] = ar / den;
        invI[i] = -ai / den;
        if (i < this.n - 1) {
          cr[i] = (this.off[i] / 2) * (hr * invR[i] - hi * invI[i]);
          ci[i] = (this.off[i] / 2) * (hr * invI[i] + hi * invR[i]);
        }
      }
      return { hr, hi, invR, invI, cr, ci };
    }
    kinetic(f) {
      const { hr, hi, invR, invI, cr, ci } = f,
        rr = new Float64Array(this.n),
        ii = new Float64Array(this.n);
      for (let i = 0; i < this.n; i++) {
        let tr = this.d[i] * this.re[i],
          ti = this.d[i] * this.im[i];
        if (i) {
          tr += this.off[i - 1] * this.re[i - 1];
          ti += this.off[i - 1] * this.im[i - 1];
        }
        if (i < this.n - 1) {
          tr += this.off[i] * this.re[i + 1];
          ti += this.off[i] * this.im[i + 1];
        }
        let br = this.re[i] - 0.5 * (hr * tr - hi * ti),
          bi = this.im[i] - 0.5 * (hr * ti + hi * tr);
        if (i) {
          br -= (this.off[i - 1] / 2) * (hr * rr[i - 1] - hi * ii[i - 1]);
          bi -= (this.off[i - 1] / 2) * (hr * ii[i - 1] + hi * rr[i - 1]);
        }
        rr[i] = br * invR[i] - bi * invI[i];
        ii[i] = br * invI[i] + bi * invR[i];
      }
      for (let i = this.n - 2; i >= 0; i--) {
        rr[i] -= cr[i] * rr[i + 1] - ci[i] * ii[i + 1];
        ii[i] -= cr[i] * ii[i + 1] + ci[i] * rr[i + 1];
      }
      this.re = rr;
      this.im = ii;
    }
    quartic() {
      let sum = 0;
      for (let i = 0; i < this.n; i++)
        sum += (this.re[i] ** 2 + this.im[i] ** 2) ** 2 / this.w[i];
      return sum;
    }
    async prepare(progress) {
      let old = this.re.slice(),
        mu = 2,
        change = Infinity,
        iteration = 0;
      const tau = 0.002;
      for (iteration = 1; iteration <= 20000; iteration++) {
        const g = this.g / (Math.sqrt(2 * Math.PI) * this.z);
        const local = () => {
          for (let i = 0; i < this.n; i++) {
            const v = 0.5 * this.r[i] ** 2 - mu,
              e = Math.exp(-tau * v),
              q = Math.abs(v) > 1e-12 ? -Math.expm1(-tau * v) / v : tau;
            const factor = Math.sqrt(
              e /
                (1 +
                  ((g * (this.re[i] ** 2 + this.im[i] ** 2)) / this.w[i]) * q),
            );
            this.re[i] *= factor;
            this.im[i] *= factor;
          }
        };
        local();
        this.kinetic(this.imagFactor);
        local();
        mu -= Math.log(this.normalize()) / tau;
        const coefficient = (this.g * this.quartic()) / Math.sqrt(2 * Math.PI);
        let lo = 1,
          hi = Math.max(2, coefficient + 2);
        for (let j = 0; j < 48; j++) {
          const z = (lo + hi) / 2;
          if (z ** 4 - coefficient * z - 1 > 0) hi = z;
          else lo = z;
        }
        this.z = (lo + hi) / 2;
        if (iteration % 50 === 0) {
          let sum = 0;
          for (let i = 0; i < this.n; i++) sum += (this.re[i] - old[i]) ** 2;
          change = Math.sqrt(sum);
          progress(`Paper reference · ${iteration} preparation steps`);
          if (change < 1e-9) break;
          old = this.re.slice();
          await new Promise((r) => setTimeout(r, 0));
        }
      }
      if (iteration > 20000) throw Error("Paper reference did not converge.");
      let chemical = 0;
      const h = new Float64Array(this.n),
        g = this.g / (Math.sqrt(2 * Math.PI) * this.z);
      for (let i = 0; i < this.n; i++) {
        h[i] =
          (this.d[i] +
            0.5 * this.r[i] ** 2 +
            (g * this.re[i] ** 2) / this.w[i]) *
          this.re[i];
        if (i) h[i] += this.off[i - 1] * this.re[i - 1];
        if (i < this.n - 1) h[i] += this.off[i] * this.re[i + 1];
        chemical += h[i] * this.re[i];
      }
      let error = 0;
      for (let i = 0; i < this.n; i++)
        error += (h[i] - chemical * this.re[i]) ** 2;
      error = Math.sqrt(error) / Math.abs(chemical);
      if (error > 2e-4)
        throw Error("Paper reference stationary residual is too large.");
      this.preparation = {
        iterations: iteration,
        dt: tau,
        radial_mu: chemical,
        radial_residual: error,
        iterate_change: change,
      };
    }
    acceleration() {
      return (
        1 / this.z ** 3 +
        (this.g * this.quartic()) / (Math.sqrt(2 * Math.PI) * this.z ** 2)
      );
    }
    advance(count) {
      for (let step = 0; step < count; step++) {
        this.v += 0.5 * this.dt * this.acceleration();
        const middle = this.z + 0.5 * this.dt * this.v,
          g = this.g / (Math.sqrt(2 * Math.PI) * middle);
        const local = () => {
          for (let i = 0; i < this.n; i++) {
            const phase =
                (-0.5 * this.dt * g * (this.re[i] ** 2 + this.im[i] ** 2)) /
                this.w[i],
              a = Math.cos(phase),
              b = Math.sin(phase),
              re = this.re[i],
              im = this.im[i];
            this.re[i] = re * a - im * b;
            this.im[i] = im * a + re * b;
          }
        };
        local();
        this.kinetic(this.realFactor);
        local();
        this.z += this.dt * this.v;
        this.v += 0.5 * this.dt * this.acceleration();
        this.steps++;
      }
    }
    diagnostics() {
      let norm = 0,
        square = 0,
        peak = 0,
        kin = 0,
        edge = 0;
      const p = this.re.map((v, i) => (v * v + this.im[i] ** 2) / this.w[i]);
      for (let i = 0; i < this.n; i++) {
        const mass = p[i] * this.w[i];
        norm += mass;
        square += mass * this.r[i] ** 2;
        if (p[i] > p[peak]) peak = i;
        kin += this.d[i] * mass;
        if (i < this.n - 1)
          kin +=
            2 *
            this.off[i] *
            (this.re[i] * this.re[i + 1] + this.im[i] * this.im[i + 1]);
        if (this.r[i] > 0.875 * this.r[this.n - 1]) edge += mass;
      }
      const threshold = p[peak] / Math.E;
      let high = 0;
      while (p[high] < threshold) high++;
      const lowR = high ? this.r[high - 1] : 0,
        lowP = high ? p[high - 1] : 0;
      const core =
          lowR +
          ((this.r[high] - lowR) * (threshold - lowP)) / (p[high] - lowP),
        rms = Math.sqrt(square / norm);
      return {
        time: this.steps * this.dt,
        norm,
        core_radius: core,
        radial_rms: rms,
        core_ratio: core / rms,
        axial_rms: this.z / Math.sqrt(2),
        energy:
          kin +
          0.25 * (this.v ** 2 + 1 / this.z ** 2) +
          (this.g * this.quartic()) / (2 * Math.sqrt(2 * Math.PI) * this.z),
        edge_probability: edge,
      };
    }
  }
  async function calculate(coupling, progress = () => {}) {
    const s = new Reference(coupling);
    await s.prepare(progress);
    const rows = [s.diagnostics()];
    for (let i = 0; i < 10; i++) {
      s.advance(100);
      rows.push(s.diagnostics());
      progress(`Paper reference · TOF ${(i + 1) / 5} t₀`);
      await new Promise((r) => setTimeout(r, 0));
    }
    return {
      model: "Lundh-Pethick-Smith radial plus axial Gaussian",
      doi: "10.1103/PhysRevA.58.4816",
      coupling,
      cells: 512,
      radius: 24,
      dt: 0.002,
      preparation: s.preparation,
      rows,
    };
  }
  return { calculate };
})();
