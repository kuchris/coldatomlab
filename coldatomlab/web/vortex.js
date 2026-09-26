"use strict";
// Geometry and diagnostics only: no evolution or fabricated vortex graphics.
window.VortexModel = (() => {
  const defaults = {
    atoms: 20000,
    tof_duration: 2,
    n: 64,
    length: 16,
    dt: 0.004,
    g: 0,
    charge: 1,
    duration: 2,
    height: 0,
    width: 0.8,
    radius: 2,
    omega: 1.2,
    stir_time: 8,
    ramp: 1,
    loop_radius: 1.5,
  };
  function validate(input) {
    const c = { ...defaults, ...input };
    if (
      Object.keys(c).some((k) => !Object.hasOwn(defaults, k)) ||
      ![32, 64, 128].includes(c.n)
    )
      throw Error("Unknown configuration or grid.");
    const limits = {
      atoms: [1000, 300000],
      tof_duration: [0.1, 6],
      length: [16, 32],
      dt: [0.001, 0.008],
      g: [0, 1000],
      duration: [0.1, 16],
      height: [0, 20],
      width: [0.5, 2],
      radius: [0, 4],
      omega: [-2, 2],
      stir_time: [1, 12],
      ramp: [0.25, 3],
      loop_radius: [0.75, 4],
    };
    for (const [k, [lo, hi]] of Object.entries(limits))
      if (
        typeof c[k] !== "number" ||
        !Number.isFinite(c[k]) ||
        c[k] < lo ||
        c[k] > hi
      )
        throw Error(`Invalid ${k}: expected ${lo}–${hi}.`);
    if (![-1, 0, 1].includes(c.charge))
      throw Error("Charge must be −1, 0 or 1.");
    if (c.length / c.n > 0.5 || c.width < (2 * c.length) / c.n)
      throw Error(
        "Resolve the cloud and stirrer: dx ≤ 0.5 and width ≥ 2 dx. Increase the grid.",
      );
    if (2 * c.ramp > c.stir_time)
      throw Error("Two ramps must fit within the stirring time.");
    if (!Number.isInteger(c.atoms))
      throw Error("Atom number must be an integer.");
    const a = Math.sqrt(
      6.62607015e-34 / (2 * Math.PI) / (1.443160895e-25 * 2 * Math.PI * 50),
    );
    if ((c.g * a * 1e9) / (4 * Math.PI * c.atoms) > 10)
      throw Error(
        "g/N implies scattering length above 10 nm; increase atom number or reduce g.",
      );
    return c;
  }
  function drive(c, t) {
    const a = Math.max(0, Math.min(1, t / c.ramp, (c.stir_time - t) / c.ramp));
    return [
      c.height * Math.sin((Math.PI * a) / 2) ** 2,
      c.radius * Math.cos(c.omega * t),
      c.radius * Math.sin(c.omega * t),
    ];
  }
  const density = (p) => p[0] * p[0] + p[1] * p[1];
  const angle = (a, b) =>
    Math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]);
  function at(field, n, i, j) {
    const k = 2 * ((i * n + j) * n + n / 2);
    return [field[k], field[k + 1]];
  }
  function sample(field, c, x, y) {
    const u = (x * c.n) / c.length + c.n / 2,
      v = (y * c.n) / c.length + c.n / 2,
      i = Math.floor(u),
      j = Math.floor(v),
      a = u - i,
      b = v - j;
    if (i < 0 || j < 0 || i >= c.n - 1 || j >= c.n - 1) return [0, 0];
    const p = at(field, c.n, i, j),
      q = at(field, c.n, i + 1, j),
      r = at(field, c.n, i, j + 1),
      s = at(field, c.n, i + 1, j + 1);
    return [0, 1].map(
      (k) =>
        p[k] * (1 - a) * (1 - b) +
        q[k] * a * (1 - b) +
        r[k] * (1 - a) * b +
        s[k] * a * b,
    );
  }
  function topology(field, c, gx, gy) {
    let peak = 0;
    const n = c.n,
      dx = c.length / n;
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++)
        peak = Math.max(peak, density(at(field, n, i, j)));
    const points = Array.from({ length: 128 }, (_, i) => [
      c.loop_radius * Math.cos((2 * Math.PI * i) / 128),
      c.loop_radius * Math.sin((2 * Math.PI * i) / 128),
    ]);
    const p = points.map(([x, y]) => sample(field, c, x, y));
    const jumps = p.map((v, i) => angle(v, p[(i + 1) % 128]));
    const reliable =
      peak > 0 &&
      p.every((v) => density(v) > peak * 1e-3) &&
      jumps.every((a) => Math.abs(a) < 0.75 * Math.PI);
    let circulation = null;
    if (reliable && gx && gy)
      circulation = points.reduce((sum, [x, y], i) => {
        const a = sample(gx, c, x, y),
          b = sample(gy, c, x, y),
          v = p[i],
          rho = density(v);
        return (
          sum +
          (-y * (v[0] * a[1] - v[1] * a[0]) + x * (v[0] * b[1] - v[1] * b[0])) /
            rho /
            128
        );
      }, 0);
    const centers = Array.from({ length: (n - 1) ** 2 }, (_, k) => {
      const i = Math.floor(k / (n - 1)),
        j = k % (n - 1),
        p = [
          at(field, n, i, j),
          at(field, n, i + 1, j),
          at(field, n, i, j + 1),
          at(field, n, i + 1, j + 1),
        ];
      return [0, 1].map((a) => p.reduce((s, v) => s + v[a], 0) / 4);
    });
    const crossings = [];
    for (let i = 0; i < n - 2; i++)
      for (let j = 0; j < n - 2; j++) {
        const p = [
          centers[i * (n - 1) + j],
          centers[(i + 1) * (n - 1) + j],
          centers[(i + 1) * (n - 1) + j + 1],
          centers[i * (n - 1) + j + 1],
        ];
        if (p.some((v) => density(v) < peak * 1e-3)) continue;
        const q = Math.round(
          p.reduce((s, v, k) => s + angle(v, p[(k + 1) % 4]), 0) /
            (2 * Math.PI),
        );
        if (Math.abs(q) === 1)
          crossings.push({
            x: (i + 1 - n / 2) * dx,
            y: (j + 1 - n / 2) * dx,
            charge: q,
          });
      }
    return {
      winding: reliable
        ? Math.round(jumps.reduce((s, x) => s + x, 0) / (2 * Math.PI))
        : null,
      loop_reliable: reliable,
      flow_circulation_quanta: circulation,
      crossings,
      positive: crossings.filter((p) => p.charge === 1).length,
      negative: crossings.filter((p) => p.charge === -1).length,
    };
  }
  return { defaults, validate, drive, density, at, sample, topology };
})();
