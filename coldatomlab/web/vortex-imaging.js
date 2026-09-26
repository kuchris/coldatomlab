"use strict";
// Core extraction uses image pixels and the declared ROI only, never model truth.
window.VortexImaging = (() => {
  function snapshot(source) {
    const c = source.config,
      n = c.n,
      dx = c.length / n,
      field = source.field;
    const columns = Array.from({ length: 3 }, () =>
      Array.from({ length: n }, () => Array(n).fill(0)),
    );
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++)
        for (let k = 0; k < n; k++) {
          const at = 2 * ((i * n + j) * n + k),
            v = (field[at] ** 2 + field[at + 1] ** 2) * dx;
          columns[0][j][i] += v;
          columns[1][k][i] += v;
          columns[2][k][j] += v;
        }
    return {
      config: c,
      scales: source.scales,
      x: Array.from({ length: n }, (_, i) => (i - n / 2) * dx),
      columns,
    };
  }
  function core(density, x, roi, variance = null) {
    const no = (reason) => ({
      available: false,
      reason,
      x_um: null,
      y_um: null,
      contrast: null,
      diameter_um: null,
      depth_snr: null,
      radius_um: [],
      radial_density: [],
    });
    const n = x.length,
      pitch = x[1] - x[0],
      indices = x
        .map((v, i) => (Math.abs(v) <= roi ? i : -1))
        .filter((i) => i >= 0);
    const valid = (v) => typeof v === "number" && Number.isFinite(v);
    if (indices.length < 9)
      return no("Need at least nine pixels across the ROI.");
    let total = 0,
      cx = 0,
      cy = 0;
    for (const j of indices)
      for (const i of indices) {
        if (!valid(density[j][i])) return no("Invalid pixels in the core ROI.");
        const v = Math.max(0, density[j][i]);
        total += v;
        cx += x[i] * v;
        cy += x[j] * v;
      }
    if (total <= 0) return no("No positive image signal.");
    cx /= total;
    cy /= total;
    let r2 = 0;
    for (const j of indices)
      for (const i of indices)
        r2 +=
          (Math.max(0, density[j][i]) * ((x[i] - cx) ** 2 + (x[j] - cy) ** 2)) /
          total;
    const rms = Math.sqrt(r2);
    if (rms < 3 * pitch) return no("Cloud is too small to resolve a core.");
    function smooth(i, j) {
      let sum = 0;
      for (let dy = -1; dy <= 1; dy++)
        for (let dx = -1; dx <= 1; dx++) {
          const v = density[j + dy]?.[i + dx];
          if (!valid(v)) return Infinity;
          sum += v;
        }
      return sum / 9;
    }
    let best = null;
    for (const j of indices)
      for (const i of indices) {
        if (
          i < 2 ||
          j < 2 ||
          i >= n - 2 ||
          j >= n - 2 ||
          Math.hypot(x[i] - cx, x[j] - cy) > 0.35 * rms
        )
          continue;
        const value = smooth(i, j);
        if (!best || value < best.value) best = { i, j, value };
      }
    if (!best || !Number.isFinite(best.value))
      return no("No resolved central search window.");
    const { i, j, value } = best;
    const curvatureX = smooth(i - 1, j) + smooth(i + 1, j) - 2 * value,
      curvatureY = smooth(i, j - 1) + smooth(i, j + 1) - 2 * value;
    if (curvatureX <= 0 || curvatureY <= 0)
      return no("No local density minimum in both image directions.");
    const offset = (left, right, curvature) =>
      Math.max(-0.5, Math.min(0.5, (left - right) / (2 * curvature)));
    const px =
        x[i] + pitch * offset(smooth(i - 1, j), smooth(i + 1, j), curvatureX),
      py =
        x[j] + pitch * offset(smooth(i, j - 1), smooth(i, j + 1), curvatureY);
    const limit = Math.min(roi - Math.abs(px), roi - Math.abs(py), 1.2 * rms),
      bins = Math.floor(limit / pitch);
    if (bins < 4) return no("Core search lies too close to the ROI edge.");
    const sums = Array(bins).fill(0),
      counts = Array(bins).fill(0),
      vars = Array(bins).fill(0);
    for (const jj of indices)
      for (const ii of indices) {
        const b = Math.floor(Math.hypot(x[ii] - px, x[jj] - py) / pitch);
        if (b >= bins) continue;
        sums[b] += density[jj][ii];
        counts[b]++;
        vars[b] += variance?.[jj]?.[ii] ?? 0;
      }
    const radial = sums.map((s, b) => (counts[b] ? s / counts[b] : null)),
      r = sums.map((_, b) => (b + 0.5) * pitch);
    let peak = 1;
    for (let b = 2; b < bins; b++)
      if (
        radial[b] !== null &&
        (radial[peak] === null || radial[b] > radial[peak])
      )
        peak = b;
    if (radial[peak] === null || radial[peak] <= 0 || peak < 2)
      return no("No resolved surrounding density ring.");
    const depth = radial[peak] - value,
      contrast = depth / radial[peak];
    let vcore = 0;
    for (let dy = -1; dy <= 1; dy++)
      for (let dx = -1; dx <= 1; dx++)
        vcore += variance?.[j + dy]?.[i + dx] ?? 0;
    const error = Math.sqrt(vcore / 81 + vars[peak] / counts[peak] ** 2),
      snr = error > 0 ? depth / error : null;
    if (contrast < 0.1 || depth <= 0)
      return no("Density dip contrast is below 0.1.");
    if (error > 0 && snr < 5)
      return no("Density dip depth has signal-to-noise below 5.");
    const halfway = value + depth / 2;
    let radius = null;
    for (let b = 1; b <= peak; b++) {
      if (radial[b - 1] === null || radial[b] === null) continue;
      if (radial[b - 1] <= halfway && radial[b] >= halfway) {
        radius =
          r[b - 1] +
          (pitch * (halfway - radial[b - 1])) / (radial[b] - radial[b - 1]);
        break;
      }
    }
    if (radius === null || radius < pitch)
      return no("Half-depth diameter is unresolved by the pixels.");
    return {
      available: true,
      reason: "",
      x_um: px,
      y_um: py,
      contrast,
      diameter_um: 2 * radius,
      depth_snr: snr,
      radius_um: r,
      radial_density: radial,
    };
  }
  function measure(image, source) {
    const eligible =
      image.camera.axis === "z" &&
      Math.abs(source.config.charge) === 1 &&
      source.config.height === 0;
    const unavailable = {
      available: false,
      reason:
        "Single axial core measurement requires an unstirred charge ±1 state viewed along z.",
      x_um: null,
      y_um: null,
      contrast: null,
      diameter_um: null,
      depth_snr: null,
      radius_um: [],
      radial_density: [],
    };
    return {
      model: eligible
        ? core(image.truth_density, image.x_um, image.camera.roi_um)
        : { ...unavailable },
      camera: eligible
        ? core(
            image.density,
            image.x_um,
            image.camera.roi_um,
            image.density_variance,
          )
        : { ...unavailable },
    };
  }
  function acquire(source, settings) {
    const image = AbsorptionCamera3D.acquire(snapshot(source), settings, false);
    return {
      schema: "coldatomlab-vortex-image-v1",
      version: "0.17.0",
      camera_model: "rb87-browser-camera-v1",
      source,
      image,
      measurements: measure(image, source),
    };
  }
  return { snapshot, core, measure, acquire };
})();
