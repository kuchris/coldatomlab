"use strict";
const $ = (id) => document.getElementById(id);
let session = null,
  state = null,
  busy = false,
  running = false,
  dirty = false;
let disconnected = false,
  view = "density",
  timer = null;
let reference = null;
const fields = [
  "experiment",
  "n",
  "length",
  "dt",
  "interaction",
  "omega_x",
  "omega_y",
  "separation",
  "phase",
  "barrier_height",
  "barrier_width",
  "split_time",
  "hold_time",
  "expansion_time",
  "bias",
];

function config() {
  const result = Object.fromEntries(
    fields.map((key) => [
      key,
      key === "experiment" ? $(key).value : canonicalValue(key),
    ]),
  );
  result.physical = physicalInputs();
  return result;
}

function controls() {
  $("parameters").disabled = busy || running;
  $("prepare").disabled = busy || running;
  for (const id of ["step", "reset", "release", "export", "pin"]) {
    $(id).disabled =
      !state || busy || running || disconnected || (dirty && id !== "reset");
  }
  $("release").disabled ||=
    !!state?.diagnostics.released || !!state?.warning || !!state?.protocol;
  $("step").disabled ||= !!state?.warning || !!state?.complete;
  $("run").disabled =
    !running &&
    (!state ||
      busy ||
      dirty ||
      disconnected ||
      !!state?.warning ||
      !!state?.complete);
  $("run").textContent = running ? "Ⅱ Pause" : "▶ Run";
  $("status").textContent = disconnected
    ? "Connection lost"
    : running
      ? "Running"
      : busy
        ? "Working…"
        : dirty
          ? "Parameters changed"
          : state?.warning
            ? "Stopped"
            : state?.complete
              ? "Complete"
              : state?.diagnostics.steps
                ? "Paused"
                : "Ready";
  $("prepare-note").textContent = dirty
    ? "Changes pending. Prepare to apply them, or reset to restore the saved settings."
    : "Preparation replaces the current experiment.";
}

async function request(action, extra = {}) {
  if (busy) return null;
  busy = true;
  controls();
  $("error").hidden = true;
  try {
    const response = await fetch("/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, session, ...extra }),
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.error || "The experiment could not be updated.");
    session = data.session;
    disconnected = false;
    $("connection").textContent = "Local solver connected";
    if (action !== "export") {
      state = data.result;
      if (action === "prepare" || action === "reset") dirty = false;
      if (state.warning || state.complete) running = false;
      render();
    }
    return data.result;
  } catch (error) {
    running = false;
    $("error").textContent = error.message;
    $("error").hidden = false;
    // Recover by preparing afresh after transport failure; avoid stepping stale state.
    if (error instanceof TypeError) {
      disconnected = true;
      $("connection").textContent = "Solver unavailable";
    }
    return null;
  } finally {
    busy = false;
    controls();
  }
}

function labels() {
  $("interaction-value").textContent = $("interaction").value;
  $("separation-value").textContent =
    Number($("separation").value).toFixed(1) + " a₀";
  $("phase-value").textContent = Number($("phase").value).toFixed(2) + " π";
  const two = $("experiment").value === "double";
  const sequence = $("experiment").value === "sequence";
  $("double-controls").hidden = !two;
  $("sequence-controls").hidden = !sequence;
  $("experiment-note").textContent = sequence
    ? "Start with one trapped condensate. Raise a barrier, hold with a bias, then release and measure interference."
    : two
      ? "Prepare two coherent Gaussian packets, already released. Change the relative phase to move the fringes."
      : "Prepare the ground state in a harmonic trap. Release it to watch the cloud expand.";
  syncPhysicalInputs();
}

$("config-form").addEventListener("input", () => {
  dirty = true;
  labels();
  controls();
});
$("config-form").addEventListener("change", () => {
  dirty = true;
  labels();
  controls();
});
$("config-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  running = false;
  clearTimeout(timer);
  await request("prepare", { config: config() });
});
document.querySelectorAll("[data-phase]").forEach((button) =>
  button.addEventListener("click", () => {
    $("phase").value = button.dataset.phase;
    dirty = true;
    labels();
    controls();
  }),
);
$("run").addEventListener("click", () => {
  running = !running;
  controls();
  if (running) loop();
  else clearTimeout(timer);
});
async function loop() {
  if (!running) return;
  await request("step", { count: 10 });
  if (running) timer = setTimeout(loop, 35);
}
$("step").addEventListener("click", () => request("step", { count: 1 }));
$("release").addEventListener("click", () => request("release"));
$("reset").addEventListener("click", async () => {
  const result = await request("reset");
  if (result) {
    restorePhysical(result.config);
  }
});
$("export").addEventListener("click", async () => {
  const data = await request("export");
  if (!data) return;
  const exported = reference
    ? {
        schema: "coldatomlab-comparison-v1",
        reference: reference.export,
        current: data,
      }
    : data;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `coldatomlab-${reference ? "comparison" : data.config.experiment}-${data.steps}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("pin").addEventListener("click", async () => {
  const data = await request("export");
  if (!data) return;
  reference = { snapshot: structuredClone(state), export: data };
  $("clear-reference").hidden = false;
  $("pin").textContent = "Replace reference";
  $("export").textContent = "Export comparison ↓";
  render();
});
$("clear-reference").addEventListener("click", () => {
  reference = null;
  $("clear-reference").hidden = true;
  $("pin").textContent = "Pin reference";
  $("export").textContent = "Export run ↓";
  render();
});
$("potential-overlay").addEventListener("change", () => {
  if (state) drawField();
});
for (const name of ["density", "phase"])
  $(name + "-view").addEventListener("click", () => {
    view = name;
    for (const other of ["density", "phase"]) {
      $(other + "-view").classList.toggle("selected", other === name);
      $(other + "-view").setAttribute("aria-pressed", String(other === name));
    }
    if (state) drawField();
  });
$("model-open").addEventListener("click", () => $("model-dialog").showModal());
$("model-close").addEventListener("click", () => $("model-dialog").close());

function surface(id) {
  const canvas = $(id),
    rect = canvas.getBoundingClientRect(),
    ratio = window.devicePixelRatio || 1;
  const w = Math.max(250, rect.width),
    h = Math.max(150, rect.height);
  canvas.width = Math.round(w * ratio);
  canvas.height = Math.round(h * ratio);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.font = "10px Consolas, monospace";
  return { canvas, ctx, w, h };
}

const stops = [
  [12, 19, 22],
  [30, 83, 96],
  [120, 184, 165],
  [229, 212, 137],
  [255, 243, 196],
];
function densityColor(t) {
  const p = Math.min(3.99999, Math.max(0, t * 4)),
    i = Math.floor(p),
    f = p - i;
  return stops[i].map((v, k) => Math.round(v + f * (stops[i + 1][k] - v)));
}
function phaseColor(theta) {
  // Periodic RGB mapping; -pi and +pi have the same color.
  return [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3].map((offset) =>
    Math.round(145 + 95 * Math.cos(theta + offset)),
  );
}

function drawField() {
  const { canvas, ctx, w, h } = surface("field");
  const n = state.config.n,
    length = state.config.length * labScale().length_um;
  const side = Math.min(w - 88, h - 105),
    left = (w - side) / 2,
    top = 44;
  const raw = document.createElement("canvas");
  raw.width = n;
  raw.height = n;
  const rc = raw.getContext("2d"),
    pixels = rc.createImageData(n, n);
  const peak = Math.max(...state.density.map((row) => Math.max(...row)));
  for (let y = 0; y < n; y++)
    for (let x = 0; x < n; x++) {
      const phase = state.phase[y][x];
      const rgb =
        view === "density"
          ? densityColor(state.density[y][x] / peak)
          : phase === null
            ? stops[0]
            : phaseColor(phase);
      const index = ((n - 1 - y) * n + x) * 4;
      pixels.data.set([...rgb, 255], index);
    }
  rc.putImageData(pixels, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(raw, left, top, side, side);
  if ($("potential-overlay").checked)
    drawContours(ctx, state.potential, left, top, side);
  ctx.strokeStyle = "#82988c25";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const p = (side * i) / 4;
    ctx.beginPath();
    ctx.moveTo(left + p, top);
    ctx.lineTo(left + p, top + side);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(left, top + p);
    ctx.lineTo(left + side, top + p);
    ctx.stroke();
    ctx.fillStyle = "#93a69c";
    ctx.textAlign = "center";
    ctx.fillText(
      (length * (i / 4 - 0.5)).toFixed(0),
      left + p,
      top + side + 17,
    );
    ctx.textAlign = "right";
    ctx.fillText((length * (0.5 - i / 4)).toFixed(0), left - 10, top + p + 3);
  }
  ctx.fillStyle = "#b0c4b7";
  ctx.textAlign = "center";
  ctx.fillText(`x / ${unitText("length")}`, left + side / 2, top + side + 34);
  ctx.save();
  ctx.translate(left - 37, top + side / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(`y / ${unitText("length")}`, 0, 0);
  ctx.restore();
  canvas.setAttribute(
    "aria-label",
    `${view === "density" ? "Density" : "Masked phase"} of ${state.config.experiment === "single" ? "one condensate" : "two coherent clouds"}, time ${(state.diagnostics.time * labScale().time_ms).toFixed(3)} ${unitText("time")}, domain ${length} ${unitText("length")} per side`,
  );
  $("legend-label").textContent =
    view === "density"
      ? state.physical
        ? "DENSITY · ATOMS/μm²"
        : "DENSITY |ψ|² · a₀⁻²"
      : "PHASE · RADIANS";
  $("legend-low").textContent = view === "density" ? "0" : "−π";
  $("legend-high").textContent =
    view === "density"
      ? (
          peak *
          (state.physical
            ? state.config.physical.atoms / state.physical.length_um ** 2
            : 1)
        ).toPrecision(3)
      : "+π";
  $("colorbar").style.background =
    view === "density"
      ? ""
      : `linear-gradient(90deg,${Array.from({ length: 13 }, (_, i) => `rgb(${phaseColor(-Math.PI + (i * Math.PI) / 6).join(",")})`).join(",")})`;
}

function plot(id, series, xmin, xmax, ymax, xlabel, ylabel, ymin = 0) {
  const comparable =
    id === "potential-profile" || !reference || !!reference.snapshot.physical;
  if (state.physical && comparable) {
    const factors = (s) => {
      const p = s.physical;
      return id === "profile"
        ? [p.length_um, s.config.physical.atoms / p.length_um ** 2]
        : id === "widths"
          ? [p.time_ms, p.length_um]
          : id === "potential-profile"
            ? [p.length_um, p.energy_hz]
            : [p.time_ms, 1];
    };
    const current = factors(state);
    series = series.map((s) => {
      const scale = factors(s.reference ? reference.snapshot : state);
      return {
        ...s,
        points: s.points.map(([x, y]) => [x * scale[0], y * scale[1]]),
      };
    });
    const xs = series.flatMap((s) => s.points.map((p) => p[0]));
    const ys = series.flatMap((s) => s.points.map((p) => p[1]));
    xmin = Math.min(xmin * current[0], ...xs);
    xmax = Math.max(xmax * current[0], ...xs);
    ymin *= current[1];
    ymax = id === "population-history" ? 1 : Math.max(...ys, 1e-10) * 1.15;
    if (id === "potential-profile") {
      ymin = Math.min(...ys, 0);
      if (ymax < 1) {
        ymin = -0.1 * current[1];
        ymax = current[1];
      }
    }
    xlabel =
      id === "profile" || id === "potential-profile" ? "x / μm" : "t / ms";
    ylabel = {
      profile: "n(x, 0) / atoms μm⁻²",
      widths: "RMS width / μm",
      "potential-profile": "V/h / Hz",
      "population-history": "Left / total",
    }[id];
  }
  rawPlot(id, series, xmin, xmax, ymax, xlabel, ylabel, ymin);
}
function rawPlot(id, series, xmin, xmax, ymax, xlabel, ylabel, ymin = 0) {
  const { ctx, w, h } = surface(id),
    left = 55,
    right = w - 16,
    top = 23,
    bottom = h - 36;
  ymax = Math.max(ymax, 1e-8);
  xmax = Math.max(xmax, xmin + 1e-6);
  ctx.strokeStyle = "#34443c";
  ctx.fillStyle = "#a0b0aa";
  ctx.lineWidth = 0.6;
  for (let i = 0; i <= 3; i++) {
    const y = bottom - ((bottom - top) * i) / 3;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(
      (ymin + ((ymax - ymin) * i) / 3).toPrecision(2),
      left - 9,
      y + 3,
    );
    const x = left + ((right - left) * i) / 3;
    ctx.textAlign = "center";
    ctx.fillText((xmin + ((xmax - xmin) * i) / 3).toFixed(1), x, bottom + 17);
  }
  ctx.textAlign = "left";
  ctx.fillText(ylabel, left, 11);
  ctx.textAlign = "center";
  ctx.fillText(xlabel, (left + right) / 2, h - 3);
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, right - left, bottom - top);
  ctx.clip();
  for (const s of series) {
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 1.7;
    ctx.setLineDash(s.dashed ? [5, 4] : []);
    ctx.beginPath();
    s.points.forEach(([x, y], i) => {
      const px = left + ((x - xmin) / (xmax - xmin)) * (right - left),
        py = bottom - ((y - ymin) / (ymax - ymin)) * (bottom - top);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
    if (s.points.length === 1) {
      const [x, y] = s.points[0];
      ctx.fillStyle = s.color;
      ctx.beginPath();
      ctx.arc(
        left + ((x - xmin) / (xmax - xmin)) * (right - left),
        bottom - ((y - ymin) / (ymax - ymin)) * (bottom - top),
        3,
        0,
        2 * Math.PI,
      );
      ctx.fill();
    }
  }
  ctx.restore();
}

function render() {
  const d = state.diagnostics,
    scale = labScale();
  renderPhysical();
  $("contour-levels").textContent = state.physical
    ? `· ${[2, 4, 8, 16].map((v) => (v * scale.energy_hz).toFixed(0)).join(" / ")} Hz (V/h)`
    : "· 2 / 4 / 8 / 16 ℏω₀";
  $("experiment-title").textContent =
    state.config.experiment === "sequence"
      ? "Split, hold & interfere"
      : state.config.experiment === "single"
        ? "Condensate expansion"
        : "Matter-wave interference";
  $("time").innerHTML =
    `${(d.time * scale.time_ms).toFixed(3)} <small>${unitText("time")}</small>`;
  $("width").innerHTML =
    `${(d.width_x * scale.length_um).toFixed(3)} <small>${unitText("length")}</small>`;
  $("norm").textContent = d.norm.toFixed(8);
  $("energy").innerHTML =
    `${(d.energy * scale.energy_hz).toFixed(4)} <small>${unitText("energy")}</small>`;
  $("grid-label").textContent =
    `${state.config.n} × ${state.config.n} · L = ${(state.config.length * scale.length_um).toFixed(2)} ${unitText("length")}`;
  $("trap-state").textContent = d.released
    ? "TRAP OFF / EXPANDING"
    : "TRAP ON / CONFINED";
  $("warning").textContent = state.warning;
  $("warning").hidden = !state.warning;
  $("boundary").textContent =
    `Boundary population: ${(100 * d.edge_mass).toExponential(2)}% / stop at 0.1%`;
  drawField();
  renderProtocol();
  renderComparison();
  $("populations").textContent =
    `${(100 * d.left_fraction).toFixed(1)}% / ${(100 * d.right_fraction).toFixed(1)}%`;
  $("relative-phase").textContent =
    d.relative_phase === null
      ? "—"
      : `${(d.relative_phase / Math.PI).toFixed(3)} π`;
  $("fringe-spacing").textContent =
    d.fringe_spacing === null
      ? "—"
      : `${(d.fringe_spacing * scale.length_um).toFixed(3)} ${unitText("length")}`;
  $("fringe-contrast").textContent =
    d.fringe_contrast === null ? "—" : d.fringe_contrast.toFixed(3);
  const ref = reference?.snapshot;
  const extent = Math.max(state.config.length, ref?.config.length || 0) / 2;
  plot(
    "profile",
    [
      {
        color: "#c3e2a0",
        points: state.x.map((x, i) => [x, state.cross_section[i]]),
      },
      ...(ref
        ? [
            {
              color: "#e3ae76",
              reference: true,
              dashed: true,
              points: ref.x.map((x, i) => [x, ref.cross_section[i]]),
            },
          ]
        : []),
    ],
    -extent,
    extent,
    Math.max(...state.cross_section, ...(ref?.cross_section || [])) * 1.15,
    "x / a₀",
    "|ψ(x, 0)|² / a₀⁻²",
  );
  const history = state.history;
  plot(
    "widths",
    [
      { color: "#c3e2a0", points: history.map((p) => [p.time, p.width_x]) },
      {
        color: "#8dbfcb",
        dashed: true,
        points: history.map((p) => [p.time, p.width_y]),
      },
      ...(ref
        ? [
            {
              color: "#e3ae76",
              reference: true,
              points: ref.history.map((p) => [p.time, p.width_x]),
            },
            {
              color: "#b98e69",
              reference: true,
              dashed: true,
              points: ref.history.map((p) => [p.time, p.width_y]),
            },
          ]
        : []),
    ],
    0,
    Math.max(1, d.time, ref?.diagnostics.time || 0),
    Math.max(
      ...[...history, ...(ref?.history || [])].map((p) =>
        Math.max(p.width_x, p.width_y),
      ),
    ) * 1.15,
    "t / ω₀⁻¹",
    "RMS width / a₀",
  );
}

function drawContours(ctx, potential, left, top, side) {
  const n = potential.length,
    cell = side / n;
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, side, side);
  ctx.clip();
  ctx.strokeStyle = "#e3ae7680";
  ctx.lineWidth = 0.8;
  ctx.setLineDash([3, 3]);
  for (const level of [2, 4, 8, 16]) {
    ctx.beginPath();
    for (let y = 0; y < n - 1; y++)
      for (let x = 0; x < n - 1; x++) {
        const vertices = [
          [x, y],
          [x + 1, y],
          [x + 1, y + 1],
          [x, y + 1],
        ];
        const points = [];
        for (let edge = 0; edge < 4; edge++) {
          const a = vertices[edge],
            b = vertices[(edge + 1) % 4];
          const va = potential[a[1]][a[0]],
            vb = potential[b[1]][b[0]];
          if ((va <= level && vb > level) || (vb <= level && va > level)) {
            const u = (level - va) / (vb - va);
            points.push([
              left + (a[0] + u * (b[0] - a[0]) + 0.5) * cell,
              top + (n - 0.5 - a[1] - u * (b[1] - a[1])) * cell,
            ]);
          }
        }
        for (let k = 0; k + 1 < points.length; k += 2) {
          ctx.moveTo(...points[k]);
          ctx.lineTo(...points[k + 1]);
        }
      }
    ctx.stroke();
  }
  ctx.restore();
}

function renderProtocol() {
  const p = state.protocol;
  $("sequence-timeline").hidden = !p;
  $("sequence-plots").hidden = !p;
  if (!p) return;
  const d = state.diagnostics,
    scale = labScale();
  $("potential-unit").textContent = state.physical
    ? "V(x, 0) / h · Hz"
    : "V(x, 0) / ℏω₀";
  $("potential-status").textContent = d.released
    ? "Trap released — V = 0. Axial confinement remains."
    : "Applied in-plane trap, barrier and bias.";
  $("sequence-stage").textContent = state.warning
    ? "Stopped before completion"
    : d.steps === 0
      ? "Prepared · ready to split"
      : {
          split: "Splitting the condensate",
          hold: "Holding · accumulating phase",
          expand: "Released · expanding",
          complete: "Sequence complete",
        }[p.stage];
  $("sequence-clock").textContent =
    `${(d.time * scale.time_ms).toFixed(2)} / ${(p.end_time * scale.time_ms).toFixed(2)} ${unitText("time")}`;
  $("split-end").textContent = `0–${(p.split_end * scale.time_ms).toFixed(2)}`;
  $("hold-end").textContent =
    `${(p.split_end * scale.time_ms).toFixed(2)}–${(p.release_time * scale.time_ms).toFixed(2)}`;
  $("expand-end").textContent =
    `${(p.release_time * scale.time_ms).toFixed(2)}–${(p.end_time * scale.time_ms).toFixed(2)}`;
  for (const stage of ["split", "hold", "expand"])
    $("stage-" + stage).classList.toggle("active", p.stage === stage);
  $("sequence-progress").max = p.end_time;
  $("sequence-progress").value = d.time;
  $("sequence-live").textContent =
    `Barrier ${(p.barrier_height * scale.energy_hz).toFixed(2)} · Hold bias ${(p.bias * scale.energy_hz).toFixed(2)} ${unitText("energy")} · Mirror phase ${d.relative_phase === null ? "—" : (d.relative_phase / Math.PI).toFixed(3) + " π"}`;
  const samples = state.x
    .map((x, i) => [x, state.potential_profile[i]])
    .filter(([x]) => Math.abs(x) <= 6);
  plot(
    "potential-profile",
    [{ color: "#e3ae76", points: samples }],
    -6,
    6,
    Math.max(1, ...samples.map((p) => p[1])) * 1.1,
    "x / a₀",
    "V / ℏω₀",
    Math.min(0, ...samples.map((p) => p[1])),
  );
  const series = [
    {
      color: "#c3e2a0",
      points: state.history.map((p) => [p.time, p.left_fraction]),
    },
  ];
  if (reference)
    series.push({
      color: "#e3ae76",
      reference: true,
      dashed: true,
      points: reference.snapshot.history.map((p) => [p.time, p.left_fraction]),
    });
  plot(
    "population-history",
    series,
    0,
    Math.max(p.end_time, reference?.snapshot.diagnostics.time || 0),
    1,
    "t / ω₀⁻¹",
    "Left / total",
  );
}

function renderComparison() {
  $("comparison").hidden = !reference;
  if (!reference) return;
  const a = reference.snapshot,
    b = state;
  const physicalComparison = !!a.physical && !!b.physical;
  $("comparison-caption").textContent =
    `Reference A: ${a.config.experiment} at ${(a.diagnostics.time * (physicalComparison ? a.physical.time_ms : 1)).toFixed(3)} ${physicalComparison ? "ms" : "ω₀⁻¹"}. Current B: ${b.config.experiment} at ${(b.diagnostics.time * (physicalComparison ? b.physical.time_ms : 1)).toFixed(3)} ${physicalComparison ? "ms" : "ω₀⁻¹"}. Overlaid data: reference in amber, current in green/cyan. Widths: solid x, dashed y.`;
  const rows = [
    [physicalComparison ? "Time / ms" : "Time / ω₀⁻¹", "time"],
    [physicalComparison ? "RMS width x / μm" : "RMS width x / a₀", "width_x"],
    ["Left population fraction", "left_fraction"],
    ["Mirror phase / rad", "relative_phase"],
    [
      physicalComparison ? "Fringe spacing / μm" : "Fringe spacing / a₀",
      "fringe_spacing",
    ],
    ["Profile contrast", "fringe_contrast"],
    [physicalComparison ? "Energy / h · Hz" : "Energy / ℏω₀", "energy"],
  ];
  const body = $("comparison-body");
  body.replaceChildren();
  for (const [label, key] of rows) {
    const tr = document.createElement("tr");
    const value = (s) => {
      const v = s.diagnostics[key];
      const factor = {
        time: "time_ms",
        width_x: "length_um",
        fringe_spacing: "length_um",
        energy: "energy_hz",
      }[key];
      return v !== null && physicalComparison && factor
        ? v * s.physical[factor]
        : v;
    };
    for (const val of [label, value(a), value(b)]) {
      const td = document.createElement("td");
      td.textContent = typeof val === "number" ? val.toFixed(4) : (val ?? "—");
      tr.append(td);
    }
    body.append(tr);
  }
  const labels = {
    experiment: "Experiment",
    interaction: "Interaction g",
    omega_x: "Trap x / ω₀",
    omega_y: "Trap y / ω₀",
    separation: "Packet separation / a₀",
    phase: "Preset phase / rad",
    barrier_height: "Barrier / ℏω₀",
    barrier_width: "Barrier width / a₀",
    split_time: "Split time",
    hold_time: "Hold time",
    expansion_time: "Expansion time",
    bias: "Hold bias / ℏω₀",
    n: "Grid",
    length: "Domain side / a₀",
    dt: "Time step",
  };
  $("comparison-settings").textContent = Object.entries(labels)
    .map(([key, label]) => `${label}: A ${a.config[key]} · B ${b.config[key]}`)
    .join("\n");
  $("comparison-settings").textContent +=
    `\nPhysical parameters A: ${JSON.stringify(a.config.physical)}\nPhysical parameters B: ${JSON.stringify(b.config.physical)}`;
  $("comparison-caption").textContent += physicalComparison
    ? " Physical axes use each run’s own conversion factors."
    : " Comparison plots and table use dimensionless units; physical scales may differ or be unavailable.";
}

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (state) render();
  }, 100);
});
setupDemos();
labels();
controls();
request("prepare", { config: config() });
