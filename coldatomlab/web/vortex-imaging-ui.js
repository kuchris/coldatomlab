"use strict";
window.VortexImagingUI = (() => {
  const $ = (id) => document.getElementById(id);
  let getSolver = () => null,
    isBusy = () => true,
    captured = null,
    pinned = null,
    working = false;
  const fmt = (v, d = 3) =>
    v === null || !Number.isFinite(v) ? "Unavailable" : v.toFixed(d);
  function updateControls() {
    const s = getSolver();
    $("vi-capture").disabled =
      !s ||
      isBusy() ||
      working ||
      !!s.lost ||
      s.steps !== s.history.at(-1)?.steps;
    for (const id of ["pin", "json", "csv"])
      $("vi-" + id).disabled = !captured || working;
  }
  function settings() {
    return {
      ...AbsorptionCamera3D.defaults,
      axis: $("vi-axis").value,
      binning: Number($("vi-binning").value),
      fwhm_um: Number($("vi-fwhm").value),
      noise: $("vi-noise").value === "on",
      seed: Number($("vi-seed").value),
      roi_um: Number($("vi-roi").value),
      saturation: Number($("vi-saturation").value),
      exposure_us: Number($("vi-exposure").value),
    };
  }
  function image(canvas, values, record, measurement, max) {
    const ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height,
      n = values.length,
      size = Math.min(w - 65, h - 65),
      ox = (w - size) / 2,
      oy = 20,
      x = record.image.x_um,
      pitch = record.image.pixel_um,
      lo = x[0] - pitch / 2,
      span = n * pitch;
    ctx.fillStyle = "#0c181f";
    ctx.fillRect(0, 0, w, h);
    for (let j = 0; j < n; j++)
      for (let i = 0; i < n; i++) {
        const v = values[j][i],
          r = Math.min(1, Math.max(0, v / max));
        ctx.fillStyle =
          v === null
            ? "#b15aa9"
            : v < 0
              ? "#314e88"
              : `rgb(${Math.round(12 + 153 * r)} ${Math.round(24 + 198 * r)} ${Math.round(31 + 174 * r)})`;
        ctx.fillRect(
          ox + (i * size) / n,
          oy + ((n - 1 - j) * size) / n,
          size / n + 0.1,
          size / n + 0.1,
        );
      }
    if (measurement.available) {
      const px = ox + ((measurement.x_um - lo) / span) * size,
        py = oy + size - ((measurement.y_um - lo) / span) * size;
      ctx.strokeStyle = "#ffffff";
      ctx.beginPath();
      ctx.moveTo(px - 6, py);
      ctx.lineTo(px + 6, py);
      ctx.moveTo(px, py - 6);
      ctx.lineTo(px, py + 6);
      ctx.stroke();
    }
    ctx.fillStyle = "#afc5d4";
    ctx.font = "12px Consolas";
    ctx.textAlign = "center";
    ctx.fillText(fmt(lo, 1), ox, oy + size + 17);
    ctx.fillText(fmt(lo + span, 1), ox + size, oy + size + 17);
    ctx.fillText(record.image.axes[0] + " / μm", w / 2, h - 8);
    ctx.fillText(record.image.axes[1] + " ↑", 18, h / 2);
  }
  function plot() {
    const canvas = $("vi-profile"),
      ctx = canvas.getContext("2d"),
      w = canvas.width,
      h = canvas.height,
      m = captured.measurements,
      sets = [
        m.model,
        m.camera,
        ...(pinned ? [pinned.measurements.camera] : []),
      ],
      maxX = Math.max(1, ...sets.flatMap((v) => v.radius_um)),
      maxY = Math.max(
        1,
        ...sets.flatMap((v) => v.radial_density).filter(Number.isFinite),
      );
    ctx.fillStyle = "#0c181f";
    ctx.fillRect(0, 0, w, h);
    ctx.font = "13px Consolas";
    ctx.fillStyle = "#afc5d4";
    ctx.fillText("Model: teal · Camera: orange · Pinned: purple", 60, 20);
    ctx.fillText("0", 60, h - 10);
    ctx.fillText(fmt(maxX, 1) + " μm", w - 90, h - 10);
    ctx.fillText(fmt(maxY, 1), 5, 40);
    sets.forEach((v, index) => {
      ctx.strokeStyle = ["#70c5bb", "#f6b469", "#bf9de5"][index];
      ctx.beginPath();
      let started = false;
      v.radial_density.forEach((y, i) => {
        if (y === null) {
          started = false;
          return;
        }
        const x = 60 + ((w - 90) * v.radius_um[i]) / maxX,
          yy = 35 + (h - 65) * (1 - y / maxY);
        started ? ctx.lineTo(x, yy) : ctx.moveTo(x, yy);
        started = true;
      });
      ctx.stroke();
    });
    if (!sets.some((v) => v.available))
      ctx.fillText(
        "No resolved radial core measurement for this image.",
        70,
        h / 2,
      );
  }
  function render() {
    const r = captured,
      a = r.image,
      m = r.measurements,
      max = Math.max(
        1e-9,
        ...a.truth_density.flat(),
        ...a.density.flat().filter(Number.isFinite),
      );
    image($("vi-model"), a.truth_density, r, m.model, max);
    image($("vi-camera"), a.density, r, m.camera, max);
    plot();
    const c = r.source.config,
      tof =
        r.source.release_step === null
          ? 0
          : (r.source.steps - r.source.release_step) *
            c.dt *
            r.source.scales.time_ms;
    $("vi-applied").textContent =
      `Frozen at t = ${fmt(r.source.steps * c.dt * r.source.scales.time_ms)} ms · TOF ${fmt(tof)} ms · N = ${c.atoms} · view ${a.camera.axis} · pixel ${fmt(a.pixel_um)} μm · FWHM ${fmt(a.camera.fwhm_um)} μm · noise ${a.camera.noise ? "on" : "off"} · seed ${a.camera.seed}.`;
    $("vi-scale").textContent =
      `Shared linear density scale: 0–${fmt(max)} atoms/μm². ${a.invalid_roi_pixels} invalid ROI pixels. Capture and pin remain fixed during later evolution.`;
    const rows = [
      ["Core x / μm", "x_um"],
      ["Core y / μm", "y_um"],
      ["Dip contrast", "contrast"],
      ["Apparent half-depth diameter / μm", "diameter_um"],
      ["Dip depth SNR", "depth_snr"],
    ];
    $("vi-measurements").replaceChildren(
      ...rows.map(([label, key]) => {
        const tr = document.createElement("tr");
        const value = (v) =>
          key === "depth_snr" && v.available && v[key] === null
            ? "Noise off"
            : fmt(v[key]);
        for (const text of [label, value(m.model), value(m.camera)]) {
          const td = document.createElement("td");
          td.textContent = text;
          tr.append(td);
        }
        return tr;
      }),
    );
    const crossings = r.source.history.at(-1).crossings,
      phase =
        crossings.length === 1 && a.camera.axis === "z"
          ? `Central phase crossing: (${fmt(crossings[0].x * r.source.scales.length_um)}, ${fmt(crossings[0].y * r.source.scales.length_um)}) μm.`
          : "";
    $("vi-status").textContent = [
      m.camera.available
        ? "Image captured · density dip resolved."
        : `Image captured · ${m.camera.reason}`,
      phase,
      ...a.warnings,
    ]
      .filter(Boolean)
      .join(" ");
    updateControls();
  }
  $("vi-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if ($("vi-capture").disabled) return;
    working = true;
    updateControls();
    try {
      captured = VortexImaging.acquire(getSolver().export(), settings());
      render();
    } catch (e) {
      $("vi-status").textContent = e.message;
    } finally {
      working = false;
      updateControls();
    }
  });
  $("vi-form").addEventListener("input", () => {
    $("vi-status").textContent =
      "Camera settings pending · Capture image applies them. Existing exposure remains fixed.";
  });
  $("vi-ideal").addEventListener("click", () => {
    $("vi-fwhm").value = 0;
    $("vi-binning").value = 1;
    $("vi-noise").value = "off";
    $("vi-status").textContent =
      "Ideal optics staged · Capture image to apply.";
  });
  $("vi-blur").addEventListener("click", () => {
    $("vi-fwhm").value = 3;
    $("vi-status").textContent =
      "3 μm resolution staged · Capture image to apply.";
  });
  $("vi-pin").addEventListener("click", () => {
    pinned = structuredClone(captured);
    $("vi-pinned").hidden = false;
    const a = pinned.image,
      max = Math.max(
        1e-9,
        ...a.truth_density.flat(),
        ...a.density.flat().filter(Number.isFinite),
      );
    image(
      $("vi-pin-image"),
      a.density,
      pinned,
      pinned.measurements.camera,
      max,
    );
    $("vi-pin-label").textContent =
      $("vi-applied").textContent + ` Pinned scale 0–${fmt(max)} atoms/μm².`;
    plot();
  });
  $("vi-unpin").addEventListener("click", () => {
    pinned = null;
    $("vi-pinned").hidden = true;
    plot();
  });
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $("vi-json").addEventListener("click", () =>
    download(
      "coldatomlab-vortex-image.json",
      JSON.stringify(captured),
      "application/json",
    ),
  );
  $("vi-csv").addEventListener("click", () => {
    const rows = ["image,radius_um,density_atoms_per_um2"];
    for (const key of ["model", "camera"]) {
      const m = captured.measurements[key];
      m.radius_um.forEach((r, i) =>
        rows.push(`${key},${r},${m.radial_density[i] ?? ""}`),
      );
    }
    download(
      "coldatomlab-vortex-core-profile.csv",
      rows.join("\n"),
      "text/csv",
    );
  });
  return {
    settings,
    capture: (source, camera = settings()) => {
      captured = VortexImaging.acquire(source, camera);
      render();
      return captured;
    },
    attach: (getter, busy) => {
      getSolver = getter;
      isBusy = busy;
      updateControls();
    },
    updateControls,
  };
})();
