"use strict";
// Frozen-state camera, double-precision browser arithmetic; independent of GPE evolution.
window.AbsorptionCamera3D = {
  defaults: {
    axis: "z",
    binning: 1,
    fwhm_um: 0,
    saturation: 1,
    exposure_us: 5,
    efficiency: 0.8,
    read_noise: 1,
    noise: false,
    seed: 17,
    roi_um: 12,
    strip_um: 4,
  },
  sigma: (3 * 0.780241209 ** 2) / (2 * Math.PI),
  validate(c, n) {
    if (!["x", "y", "z"].includes(c.axis))
      throw Error("Choose an imaging axis.");
    if (
      ![1, 2, 4, 8, 16].includes(c.binning) ||
      n % c.binning ||
      n / c.binning < 8
    )
      throw Error(
        "Choose a pixel size with at least eight camera pixels per side.",
      );
    if (
      typeof c.noise !== "boolean" ||
      !Number.isInteger(c.seed) ||
      c.seed < 0 ||
      c.seed > 4294967295
    )
      throw Error("Noise needs a boolean flag and a 32-bit integer seed.");
    for (const [key, lo, hi] of [
      ["fwhm_um", 0, 20],
      ["saturation", 0.001, 10],
      ["exposure_us", 0.1, 100],
      ["efficiency", 0.05, 1],
      ["read_noise", 0, 20],
      ["roi_um", 1, 100],
      ["strip_um", 0.2, 40],
    ])
      if (
        typeof c[key] !== "number" ||
        !Number.isFinite(c[key]) ||
        c[key] < lo ||
        c[key] > hi
      )
        throw Error(`${key} must be between ${lo} and ${hi}.`);
  },
  rng(seed) {
    let state = seed >>> 0;
    const uniform = () => {
      state = (Math.imul(1664525, state) + 1013904223) >>> 0;
      return (state + 0.5) / 4294967296;
    };
    const normal = () =>
      Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform());
    const logFact = (k) => {
      if (k < 256) {
        let sum = 0;
        for (let j = 2; j <= k; j++) sum += Math.log(j);
        return sum;
      }
      return (
        (k + 0.5) * Math.log(k) -
        k +
        0.5 * Math.log(2 * Math.PI) +
        1 / (12 * k) -
        1 / (360 * k ** 3) +
        1 / (1260 * k ** 5)
      );
    };
    const poisson = (mu) => {
      if (mu < 30) {
        let k = 0,
          p = 1,
          bound = Math.exp(-mu);
        do {
          k++;
          p *= uniform();
        } while (p > bound);
        return k - 1;
      }
      const b = 0.931 + 2.53 * Math.sqrt(mu),
        a = -0.059 + 0.02483 * b,
        inv = 1.1239 + 1.1328 / (b - 3.4),
        vr = 0.9277 - 3.6224 / (b - 2);
      for (;;) {
        const u = uniform() - 0.5,
          v = uniform(),
          us = 0.5 - Math.abs(u),
          k = Math.floor(((2 * a) / us + b) * u + mu + 0.43);
        if (us >= 0.07 && v <= vr) return k;
        if (k < 0 || (us < 0.013 && v > us)) continue;
        if (
          Math.log((v * inv) / (a / (us * us) + b)) <=
          -mu + k * Math.log(mu) - logFact(k)
        )
          return k;
      }
    };
    return { uniform, normal, poisson };
  },
  transmission(od, s) {
    let lo = Math.max(0, od - s),
      hi = od;
    for (let j = 0; j < 52; j++) {
      const u = (lo + hi) / 2;
      if (u + s * -Math.expm1(-u) < od) lo = u;
      else hi = u;
    }
    return Math.exp(-(lo + hi) / 2);
  },
  blur(input, sigma) {
    if (sigma < 1e-8) return input.map((r) => r.slice());
    const n = input.length,
      r = Math.ceil(6 * sigma),
      k = Array.from({ length: 2 * r + 1 }, (_, i) =>
        Math.exp(-0.5 * ((i - r) / sigma) ** 2),
      ),
      sum = k.reduce((a, b) => a + b, 0);
    let a = input.map((row) => row.map((v) => 1 - v));
    for (const axis of [0, 1]) {
      const out = Array.from({ length: n }, () => Array(n).fill(0));
      for (let y = 0; y < n; y++)
        for (let x = 0; x < n; x++)
          for (let j = -r; j <= r; j++) {
            const yy = axis === 0 ? y + j : y,
              xx = axis === 1 ? x + j : x;
            if (xx >= 0 && xx < n && yy >= 0 && yy < n)
              out[y][x] += (a[yy][xx] * k[j + r]) / sum;
          }
      a = out;
    }
    return a.map((row) => row.map((v) => Math.max(0, Math.min(1, 1 - v))));
  },
  bin(a, b) {
    const n = a.length / b;
    return Array.from({ length: n }, (_, y) =>
      Array.from({ length: n }, (_, x) => {
        let sum = 0;
        for (let j = 0; j < b; j++)
          for (let i = 0; i < b; i++) sum += a[y * b + j][x * b + i];
        return sum / (b * b);
      }),
    );
  },
  solve(a, b) {
    const n = b.length,
      m = a.map((r, i) => [...r, b[i]]);
    for (let i = 0; i < n; i++) {
      let p = i;
      for (let j = i + 1; j < n; j++)
        if (Math.abs(m[j][i]) > Math.abs(m[p][i])) p = j;
      if (Math.abs(m[p][i]) < 1e-13) return null;
      [m[p], m[i]] = [m[i], m[p]];
      const d = m[i][i];
      for (let k = i; k <= n; k++) m[i][k] /= d;
      for (let j = 0; j < n; j++)
        if (j !== i) {
          const v = m[j][i];
          for (let k = i; k <= n; k++) m[j][k] -= v * m[i][k];
        }
    }
    return m.map((r) => r[n]);
  },
  fit(x, y, errors = null) {
    const no = (reason) => ({
      available: false,
      reason,
      phase: null,
      spacing: null,
      contrast: null,
    });
    if (x.length < 20 || y.some((v) => v === null || !Number.isFinite(v)))
      return no("Need at least 20 valid profile samples in the ROI.");
    const range = x.at(-1) - x[0],
      pitch = x[1] - x[0],
      max = Math.max(...y),
      min = Math.min(...y),
      scale = max - min;
    if (!(scale > 1e-10)) return no("No density modulation.");
    const positive = y.map((v) => Math.max(v, 0)),
      sum = positive.reduce((a, b) => a + b, 0);
    if (sum <= 0) return no("No positive signal.");
    const center = x.reduce((a, v, i) => a + v * positive[i], 0) / sum,
      sd = Math.sqrt(
        x.reduce((a, v, i) => a + (v - center) ** 2 * positive[i], 0) / sum,
      );
    const kmin = (2 * Math.PI * 2.5) / range,
      kmax = (2 * Math.PI) / (4 * pitch);
    if (kmax <= kmin || sd < pitch)
      return no("Insufficient spatial resolution.");
    const normalized = y.map((v) => v / scale);
    function trial(k, width, offset) {
      const rows = x.map((v) => {
        const z = (v - offset) / width,
          e = Math.exp(-0.5 * z * z);
        return [e, e * z, e * z * z, e * Math.cos(k * v), e * Math.sin(k * v)];
      });
      const a = Array.from({ length: 5 }, () => Array(5).fill(0)),
        b = Array(5).fill(0);
      for (let i = 0; i < x.length; i++)
        for (let j = 0; j < 5; j++) {
          b[j] += rows[i][j] * normalized[i];
          for (let q = 0; q < 5; q++) a[j][q] += rows[i][j] * rows[i][q];
        }
      const coeff = AbsorptionCamera3D.solve(a, b);
      if (!coeff) return null;
      const predicted = rows.map((r) =>
        r.reduce((v, t, i) => v + t * coeff[i], 0),
      );
      const loss = predicted.reduce(
        (v, t, i) => v + (t - normalized[i]) ** 2,
        0,
      );
      return { k, width, offset, coeff, predicted, loss, rows };
    }
    let best = null;
    const dk = (kmax - kmin) / 80;
    for (const width of [0.45, 0.6, 0.8, 1, 1.3, 1.7, 2.2].map((v) => v * sd))
      for (const offset of [center - 0.2 * sd, center, center + 0.2 * sd])
        for (let j = 0; j <= 80; j++) {
          const v = trial(kmin + j * dk, width, offset);
          if (v && (!best || v.loss < best.loss)) best = v;
        }
    if (!best) return no("Ill-conditioned profile fit.");
    for (let stage = 0; stage < 5; stage++) {
      const old = best,
        step = dk / 4 ** (stage + 1);
      for (const width of [1 - 0.15 / 2 ** stage, 1, 1 + 0.15 / 2 ** stage].map(
        (v) => v * old.width,
      ))
        for (const offset of [
          old.offset - pitch / 2 ** stage,
          old.offset,
          old.offset + pitch / 2 ** stage,
        ])
          for (let j = -5; j <= 5; j++) {
            const k = old.k + j * step;
            if (k <= kmin || k >= kmax) continue;
            const v = trial(k, width, offset);
            if (v && v.loss < best.loss) best = v;
          }
    }
    const amplitude = Math.hypot(best.coeff[3], best.coeff[4]),
      baseline = best.coeff[0],
      contrast = amplitude / baseline,
      rmse = Math.sqrt(best.loss / x.length);
    const observedError = errors ? Math.max(...errors) : 0;
    // Compare with the same smooth envelope with no carrier, fitted independently.
    const ids = [0, 1, 2],
      a = ids.map((i) =>
        ids.map((j) => best.rows.reduce((s, r) => s + r[i] * r[j], 0)),
      ),
      b = ids.map((i) =>
        best.rows.reduce((s, r, j) => s + r[i] * normalized[j], 0),
      );
    const coeff = this.solve(a, b),
      baseLoss = coeff
        ? best.rows.reduce(
            (s, r, j) =>
              s +
              (ids.reduce((v, id, k) => v + r[id] * coeff[k], 0) -
                normalized[j]) **
                2,
            0,
          )
        : 0;
    if (
      baseline <= 0 ||
      contrast < 0.08 ||
      contrast > 1.1 ||
      rmse > 0.12 ||
      baseLoss <= 0 ||
      1 - best.loss / baseLoss < 0.7 ||
      amplitude * scale < 5 * observedError ||
      best.k - kmin < dk / 4 ||
      kmax - best.k < dk / 4
    )
      return {
        ...no(
          "Fringes are unresolved, noisy, or incompatible with the envelope/carrier fit.",
        ),
        relative_rmse: rmse,
      };
    return {
      available: true,
      reason:
        "Image-only envelope/carrier fit; phase at horizontal coordinate zero.",
      phase: Math.atan2(best.coeff[4], best.coeff[3]),
      spacing: (2 * Math.PI) / best.k,
      contrast,
      relative_rmse: rmse,
      fit_profile: best.predicted.map((v) => v * scale),
    };
  },
  acquire(snapshot, settings) {
    const c = { ...this.defaults, ...settings },
      n = snapshot.config.n;
    this.validate(c, n);
    const axes = { z: ["x", "y", 0], y: ["x", "z", 1], x: ["y", "z", 2] }[
      c.axis
    ];
    const a = snapshot.scales.length_um,
      dx = (snapshot.config.length / n) * a,
      b = c.binning,
      pitch = dx * b;
    const fineX = snapshot.x.map((v) => v * a),
      x = Array.from(
        { length: n / b },
        (_, i) =>
          fineX.slice(i * b, (i + 1) * b).reduce((s, v) => s + v, 0) / b,
      );
    const select = x
        .map((v, i) => (Math.abs(v) <= c.roi_um ? i : -1))
        .filter((i) => i >= 0),
      strip = x
        .map((v, i) => (Math.abs(v) <= c.strip_um / 2 ? i : -1))
        .filter((i) => i >= 0);
    if (select.length < 4 || !strip.length)
      throw Error("Enlarge the ROI/strip or use smaller pixels.");
    const truth = snapshot.columns[axes[2]].map((r) =>
      r.map((v) => (v * snapshot.config.atoms) / a ** 2),
    );
    const t = truth.map((r) =>
      r.map((v) => this.transmission(this.sigma * v, c.saturation)),
    );
    const sampled = this.bin(
      this.blur(t, c.fwhm_um / (Math.sqrt(8 * Math.log(2)) * dx)),
      b,
    );
    const fluence =
      ((c.saturation * 16.69 * c.exposure_us * 1e-6) /
        ((6.62607015e-34 * 299792458) / 0.780241209e-6)) *
      1e-12;
    const reference = fluence * pitch * pitch * c.efficiency,
      rng = this.rng(c.seed),
      frame = (mean) =>
        100 +
        (c.noise ? rng.poisson(mean) + c.read_noise * rng.normal() : mean);
    const atoms = sampled.map((r) => r.map((v) => frame(v * reference))),
      ref = sampled.map((r) => r.map(() => frame(reference))),
      dark = sampled.map((r) =>
        r.map(() => 100 + (c.noise ? c.read_noise * rng.normal() : 0)),
      );
    const density = atoms.map((r, j) =>
      r.map((v, i) => {
        const A = v - dark[j][i],
          R = ref[j][i] - dark[j][i];
        return A > 0 && R > 0
          ? (Math.log(R / A) + (c.saturation * (R - A)) / reference) /
              this.sigma
          : null;
      }),
    );
    const variance = atoms.map((r, j) =>
      r.map((v, i) => {
        const A = v - dark[j][i],
          R = ref[j][i] - dark[j][i];
        if (density[j][i] === null) return null;
        if (!c.noise) return 0;
        const ga = -1 / A - c.saturation / reference,
          gr = 1 / R + c.saturation / reference,
          gd = 1 / A - 1 / R;
        return (
          (ga * ga * (A + c.read_noise ** 2) +
            gr * gr * (R + c.read_noise ** 2) +
            gd * gd * c.read_noise ** 2) /
          this.sigma ** 2
        );
      }),
    );
    const profile = x.map((_, i) =>
      strip.some((j) => density[j][i] === null)
        ? null
        : strip.reduce((s, j) => s + density[j][i], 0) / strip.length,
    );
    const err = x.map((_, i) =>
      strip.some((j) => variance[j][i] === null)
        ? null
        : Math.sqrt(strip.reduce((s, j) => s + variance[j][i], 0)) /
          strip.length,
    );
    const truthPixels = this.bin(truth, b),
      truthProfile = x.map(
        (_, i) =>
          strip.reduce((s, j) => s + truthPixels[j][i], 0) / strip.length,
      );
    const fitX = select.map((i) => x[i]),
      measuredFit = this.fit(
        fitX,
        select.map((i) => profile[i]),
        c.noise ? select.map((i) => err[i]) : null,
      ),
      truthFit = this.fit(
        fitX,
        select.map((i) => truthProfile[i]),
      );
    let count = 0,
      truthCount = 0,
      countVariance = 0,
      invalid = 0;
    for (const j of select)
      for (const i of select) {
        truthCount += truthPixels[j][i] * pitch ** 2;
        if (density[j][i] === null) invalid++;
        else {
          count += density[j][i] * pitch ** 2;
          countVariance += variance[j][i] * pitch ** 4;
        }
      }
    const total = truth.flat().reduce((s, v) => s + v, 0) * dx * dx;
    const absorbed =
      (fluence * t.flat().reduce((s, v) => s + 1 - v, 0) * dx * dx) /
      snapshot.config.atoms;
    const warnings = [];
    if (invalid)
      warnings.push(
        `${invalid} invalid ROI pixels; atom count and image fit may be unavailable. Magenta pixels are invalid; negative estimates remain blue.`,
      );
    if (!measuredFit.available) warnings.push(measuredFit.reason);
    if (c.axis === "x")
      warnings.push(
        "Looking along the split direction integrates x-fringes away; no x phase can be recovered.",
      );
    if (c.fwhm_um > 0 && c.fwhm_um < 2 * dx)
      warnings.push(
        "PSF is narrower than two source cells; refine the source grid for optical accuracy.",
      );
    if (Math.max(...truth.flat()) * this.sigma > 4)
      warnings.push(
        "Peak optical depth exceeds 4; dark pixels and omitted multiple scattering limit interpretation.",
      );
    if (absorbed > 5)
      warnings.push(
        "More than five absorbed photons per atom on average; recoil and motion are not simulated.",
      );
    return {
      camera: c,
      axes: axes.slice(0, 2),
      x_um: x,
      pixel_um: pitch,
      truth_density: truthPixels,
      density,
      atoms_frame: atoms,
      reference_frame: ref,
      dark_frame: dark,
      expected_reference_e: reference,
      profile,
      profile_error: err,
      truth_profile: truthProfile,
      fit_x_um: fitX,
      measured: measuredFit,
      truth: truthFit,
      atoms_roi: invalid ? null : count,
      truth_atoms_roi: truthCount,
      atom_standard_error: invalid ? null : Math.sqrt(countVariance),
      invalid_roi_pixels: invalid,
      model_total_atoms: total,
      scattered_per_atom: absorbed,
      roi_bounds_um: [x[select[0]] - pitch / 2, x[select.at(-1)] + pitch / 2],
      strip_bounds_um: [x[strip[0]] - pitch / 2, x[strip.at(-1)] + pitch / 2],
      warnings,
    };
  },
};
