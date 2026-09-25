"use strict";
let cameraRecord = null,
  pinnedImage = null,
  cameraDirty = false;
const cameraKeys = [
  "binning",
  "fwhm_um",
  "saturation",
  "exposure_us",
  "efficiency",
  "read_noise",
  "noise",
  "seed",
  "roi_um",
  "strip_um",
];

function cameraControls() {
  const eligible = state?.config.physical?.species === "Rb87";
  $("camera-parameters").disabled = busy || running;
  $("capture").disabled = !eligible || busy || running || dirty || disconnected;
  $("camera-ideal").disabled = busy || running;
  $("camera-pin").disabled = !cameraRecord || busy;
  $("camera-export").disabled = !cameraRecord || busy;
  $("camera-availability").textContent = !eligible
    ? "Prepare a Rubidium-87 laboratory run first. Guided experiments provide ready-to-use settings."
    : running
      ? "Pause the simulation to capture a fixed state."
      : "Camera settings apply at Capture. The simulation state is held fixed during acquisition.";
  if (eligible) {
    const dx =
      (state.config.length / state.config.n) * state.physical.length_um;
    for (const option of $("cam-binning").options) {
      const b = Number(option.value);
      option.textContent = `${(dx * b).toFixed(3)} μm · ${state.config.n / b}² pixels`;
      option.disabled = state.config.n / b < 8;
    }
  }
  if (cameraRecord) {
    const image = cameraRecord.image,
      source = cameraRecord.source;
    const time = source.steps * source.config.dt * source.physical.time_ms;
    const stale =
      source.steps !== state?.diagnostics.steps ||
      JSON.stringify(source.config) !== JSON.stringify(state?.config);
    $("camera-caption").textContent =
      `Captured at ${time.toFixed(3)} ms · ${image.x_um.length} × ${image.x_um.length} pixels · ${image.pixel_um.toFixed(3)} μm/pixel · FWHM ${image.camera.fwhm_um} μm · ${image.camera.noise ? "noise on, seed " + image.camera.seed : "noise off"}.${stale ? " Saved exposure: the current simulation has changed." : ""}${cameraDirty ? " Camera edits pending; capture again to apply them." : ""}`;
  }
}

function setupCamera() {
  $("camera-form").addEventListener("input", () => {
    cameraDirty = true;
    cameraControls();
  });
  $("camera-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const camera = Object.fromEntries(
      cameraKeys.map((k) => [
        k,
        k === "noise" ? $("cam-" + k).checked : Number($("cam-" + k).value),
      ]),
    );
    const result = await request("capture", { camera });
    if (!result) {
      $("camera-caption").textContent =
        `Capture failed: ${$("error").textContent}`;
      return;
    }
    cameraRecord = result;
    cameraDirty = false;
    renderCamera();
    cameraControls();
  });
  $("camera-ideal").addEventListener("click", () => {
    $("cam-binning").value = "1";
    $("cam-fwhm_um").value = "0";
    $("cam-noise").checked = false;
    cameraDirty = true;
    cameraControls();
  });
  $("camera-pin").addEventListener("click", () => {
    pinnedImage = structuredClone(cameraRecord);
    $("camera-clear").hidden = false;
    $("camera-pin").textContent = "Replace pinned image";
    renderCamera();
  });
  $("camera-clear").addEventListener("click", () => {
    pinnedImage = null;
    $("camera-clear").hidden = true;
    $("camera-pin").textContent = "Pin image";
    renderCamera();
  });
  $("camera-export").addEventListener("click", () => {
    const data = pinnedImage
      ? {
          schema: "coldatomlab-camera-comparison-v1",
          reference: pinnedImage,
          current: cameraRecord,
        }
      : cameraRecord;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `coldatomlab-camera${pinnedImage ? "-comparison" : ""}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener("resize", () => {
    if (cameraRecord) renderCamera();
  });
}

function imagePanel(id, data, peak, x, roi) {
  const { ctx, w, h } = surface(id),
    side = Math.min(w - 68, h - 60),
    left = (w - side) / 2,
    top = 16;
  const canvas = document.createElement("canvas"),
    n = data.length;
  canvas.width = canvas.height = n;
  const context = canvas.getContext("2d"),
    pixels = context.createImageData(n, n);
  for (let y = 0; y < n; y++)
    for (let xx = 0; xx < n; xx++) {
      const value = data[y][xx];
      const rgb =
        value === null
          ? [207, 103, 156]
          : value < 0
            ? [61, 76, 125]
            : densityColor(value / peak);
      pixels.data.set([...rgb, 255], ((n - 1 - y) * n + xx) * 4);
    }
  context.putImageData(pixels, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(canvas, left, top, side, side);
  const dx = x[1] - x[0],
    low = x[0] - dx / 2,
    span = dx * n;
  ctx.strokeStyle = "#e3ae76";
  ctx.setLineDash([4, 4]);
  ctx.strokeRect(
    left + ((roi[0] - low) / span) * side,
    top + (1 - (roi[1] - low) / span) * side,
    ((roi[1] - roi[0]) / span) * side,
    ((roi[1] - roi[0]) / span) * side,
  );
  ctx.setLineDash([]);
  ctx.fillStyle = "#a9bbb0";
  ctx.textAlign = "center";
  for (let i = 0; i <= 4; i++)
    ctx.fillText(
      (low + (span * i) / 4).toFixed(1),
      left + (side * i) / 4,
      top + side + 17,
    );
  ctx.fillText("x / μm", left + side / 2, top + side + 34);
  ctx.save();
  ctx.translate(left - 14, top + side / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("y / μm", 0, 0);
  ctx.restore();
}

function renderCamera() {
  if (!cameraRecord) return;
  const im = cameraRecord.image,
    ref = pinnedImage?.image;
  $("camera-result").hidden = false;
  const peak = Math.max(
    1e-9,
    ...im.truth_density.flat(),
    ...im.density.flat().filter((v) => v !== null),
  );
  imagePanel("camera-truth", im.truth_density, peak, im.x_um, im.roi_bounds_um);
  imagePanel("camera-image", im.density, peak, im.x_um, im.roi_bounds_um);
  $("camera-legend").textContent =
    `Shared linear scale: 0–${peak.toPrecision(3)} atoms/μm². Blue: negative noise estimates. Magenta: invalid counts. Dashed box: measurement ROI. Model image is averaged onto camera pixels; model moments use the original grid.`;
  const fmt = (v) => (v === null || v === undefined ? "—" : v.toFixed(3));
  const body = $("camera-measurements");
  body.replaceChildren();
  for (const [label, key] of [
    ["Atoms in ROI", "atoms"],
    ["RMS x / μm", "width_x"],
    ["RMS y / μm", "width_y"],
    ["Fringe spacing / μm", "fringe_spacing"],
    ["Profile contrast", "fringe_contrast"],
  ]) {
    const a = im.truth[key],
      b = im.measured[key],
      delta = a !== null && b !== null ? b - a : null;
    const row = document.createElement("tr");
    for (const v of [
      label,
      fmt(a),
      fmt(b),
      fmt(delta),
      fmt(ref?.measured[key]),
    ]) {
      const td = document.createElement("td");
      td.textContent = v;
      row.append(td);
    }
    body.append(row);
  }
  $("camera-statistics").textContent =
    `Full model N = ${im.model_total_atoms.toFixed(3)} · ROI [${im.roi_bounds_um.map((v) => v.toFixed(2)).join(", ")}] μm on both axes · strip y = [${im.strip_bounds_um.map((v) => v.toFixed(2)).join(", ")}] μm · estimated atom standard error = ${fmt(im.atom_standard_error)} · invalid ROI pixels = ${im.invalid_roi_pixels}. Widths need valid pixels and number SNR ≥ 5 with noise enabled.`;
  const series = [
    {
      color: "#c3e2a0",
      points: im.model_x_um.map((x, i) => [x, im.truth_profile[i]]),
    },
    { color: "#8dbfcb", points: im.x_um.map((x, i) => [x, im.profile[i]]) },
  ];
  if (ref)
    series.push({
      color: "#e3ae76",
      dashed: true,
      points: ref.x_um.map((x, i) => [x, ref.profile[i]]),
    });
  // Break curves at masked samples instead of drawing artificial bridges.
  const segments = series.flatMap((s) => {
    const groups = [];
    let points = [];
    for (const pair of s.points) {
      if (pair[1] === null) {
        if (points.length) groups.push({ ...s, points });
        points = [];
      } else points.push(pair);
    }
    if (points.length) groups.push({ ...s, points });
    return groups;
  });
  const xs = series.flatMap((s) => s.points.map((p) => p[0])),
    ys = segments.flatMap((s) => s.points.map((p) => p[1]));
  rawPlot(
    "camera-profile",
    segments,
    Math.min(...xs),
    Math.max(...xs),
    Math.max(1e-8, ...ys) * 1.1,
    "x / μm",
    "n / atoms μm⁻²",
    Math.min(0, ...ys),
  );
  const mid = Math.floor(im.x_um.length / 2);
  const countSeries = [
    {
      color: "#8dbfcb",
      points: im.x_um.map((x, i) => [
        x,
        im.atoms_frame[mid][i] - im.dark_frame[mid][i],
      ]),
    },
    {
      color: "#c3e2a0",
      points: im.x_um.map((x, i) => [
        x,
        im.reference_frame[mid][i] - im.dark_frame[mid][i],
      ]),
    },
    { color: "#e3ae76", dashed: true, points: im.x_um.map((x) => [x, 0]) },
  ];
  const counts = countSeries.flatMap((s) => s.points.map((p) => p[1]));
  rawPlot(
    "camera-counts",
    countSeries,
    im.x_um[0],
    im.x_um.at(-1),
    Math.max(...counts) * 1.1,
    "x / μm",
    "Dark-subtracted electrons",
    Math.min(0, ...counts),
  );
  $("camera-reference-note").textContent = ref
    ? `Pinned: FWHM ${ref.camera.fwhm_um} μm, pixel ${ref.pixel_um.toFixed(3)} μm, noise ${ref.camera.noise ? "on" : "off"}, t = ${(pinnedImage.source.steps * pinnedImage.source.config.dt * pinnedImage.source.physical.time_ms).toFixed(3)} ms. Pinned values use their own ROI and strip; compare settings and times before interpreting differences.`
    : "Pin an image, then change FWHM, pixel size or noise and capture the same state to compare. Reusing the same settings and seed reproduces the same counts.";
  const list = $("camera-warnings");
  list.replaceChildren();
  for (const warning of im.warnings) {
    const li = document.createElement("li");
    li.textContent = warning;
    list.append(li);
  }
  $("camera-export").textContent = ref
    ? "Export camera comparison ↓"
    : "Export image ↓";
}
