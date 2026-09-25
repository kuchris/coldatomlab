"use strict";
window.Interferometry3D = {
  defaults: {
    experiment: "single",
    separation: 6,
    relative_phase: 0,
    barrier_height: 12,
    barrier_width: 0.8,
    split_time: 3,
    hold_time: 0.6,
    hold_bias: 1,
  },
  stages(c) {
    const split = Math.round(c.split_time / c.dt),
      release = split + Math.round(c.hold_time / c.dt);
    return [split, release, release + Math.round(c.duration / c.dt)];
  },
  drive(c, step) {
    if (c.experiment !== "sequence") return [0, 0];
    const [split, release] = this.stages(c);
    if (step < split)
      return [
        c.barrier_height * Math.sin(((Math.PI / 2) * step) / split) ** 2,
        0,
      ];
    return step < release ? [c.barrier_height, c.hold_bias] : [0, 0];
  },
  fringes(x, p) {
    const peak = Math.max(...p),
      peaks = [],
      dx = x[1] - x[0];
    for (let i = 1; i < x.length - 1; i++)
      if (p[i] > p[i - 1] && p[i] >= p[i + 1] && p[i] > 0.15 * peak) {
        const shift =
          (0.5 * (p[i - 1] - p[i + 1])) / (p[i - 1] - 2 * p[i] + p[i + 1]);
        peaks.push([i, x[i] + shift * dx]);
      }
    const unavailable = {
      spacing: null,
      contrast: null,
      reason: "Need at least three resolved fringes.",
    };
    if (peaks.length < 3) return unavailable;
    const gaps = peaks.slice(1).map((v, i) => v[1] - peaks[i][1]);
    const spacing = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    const sd = Math.sqrt(
      gaps.reduce((a, b) => a + (b - spacing) ** 2, 0) / gaps.length,
    );
    if (Math.min(...gaps) < 4 * dx || sd / spacing > 0.15)
      return {
        ...unavailable,
        reason: "Fringes are undersampled or spacing is nonuniform.",
      };
    const vertexHeight = (i) => {
      const curvature = p[i - 1] - 2 * p[i] + p[i + 1];
      const shift = curvature ? (0.5 * (p[i - 1] - p[i + 1])) / curvature : 0;
      return Math.max(0, p[i] - 0.25 * (p[i - 1] - p[i + 1]) * shift);
    };
    const contrasts = peaks.slice(1).map(([r], i) => {
      const l = peaks[i][0],
        high = Math.min(vertexHeight(l), vertexHeight(r));
      let valley = l;
      for (let j = l + 1; j <= r; j++) if (p[j] < p[valley]) valley = j;
      const low = vertexHeight(valley);
      return (high - low) / (high + low);
    });
    return {
      spacing,
      contrast: contrasts.reduce((a, b) => a + b, 0) / contrasts.length,
      reason: "Resolved local peaks; envelope-sensitive estimate.",
    };
  },
  measure(s) {
    const c = s.config,
      n = c.n,
      mid = n / 2,
      dx = s.dx,
      p = Array(n).fill(0),
      f = s.field;
    let cr = 0,
      ci = 0,
      l2 = 0,
      r2 = 0;
    for (let ix = 0; ix < n; ix++)
      for (let j = 0; j < n * n; j++) {
        const i = 2 * (ix * n * n + j),
          re = f[i],
          im = f[i + 1];
        p[ix] += (re * re + im * im) * dx * dx;
        if (ix > mid) {
          const k = 2 * ((n - ix) * n * n + j),
            lr = f[k],
            li = f[k + 1];
          cr += lr * re + li * im;
          ci += lr * im - li * re;
          l2 += lr * lr + li * li;
          r2 += re * re + im * im;
        }
      }
    const total = p.reduce((a, b) => a + b, 0),
      left = (p.slice(0, mid).reduce((a, b) => a + b, 0) + p[mid] / 2) / total;
    const coherence =
      l2 * r2 > 1e-24 ? Math.hypot(cr, ci) / Math.sqrt(l2 * r2) : 0;
    const [height, bias] = this.drive(c, s.steps),
      [split, release, end] = this.stages(c);
    const potential = s.x.map((x) =>
      s.releaseStep !== null
        ? 0
        : 0.5 * (s.w[0] * x) ** 2 +
          height * Math.exp(-0.5 * (x / c.barrier_width) ** 2) +
          0.5 * bias * Math.tanh(x / c.barrier_width),
    );
    return {
      profile: p,
      potential,
      left_fraction: left,
      right_fraction: 1 - left,
      mirror_phase:
        coherence > 0.2 && Math.min(left, 1 - left) > 0.05
          ? Math.atan2(ci, cr)
          : null,
      mirror_coherence: coherence,
      fringes: this.fringes(s.x, p),
      stage:
        c.experiment === "sequence"
          ? s.steps >= end
            ? "Complete"
            : s.steps < split
              ? "Split"
              : s.steps < release
                ? "Hold"
                : "Expansion"
          : s.releaseStep !== null
            ? "Expansion"
            : "Trapped",
      stage_steps: c.experiment === "sequence" ? [split, release, end] : null,
      barrier_height: height,
      hold_bias: bias,
    };
  },
};
