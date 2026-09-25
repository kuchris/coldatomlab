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
];

function config() {
  return Object.fromEntries(
    fields.map((key) => [
      key,
      key === "experiment"
        ? $(key).value
        : Number($(key).value) * (key === "phase" ? Math.PI : 1),
    ]),
  );
}

function controls() {
  $("parameters").disabled = busy || running;
  $("prepare").disabled = busy || running;
  for (const id of ["step", "reset", "release", "export"]) {
    $(id).disabled =
      !state || busy || running || disconnected || (dirty && id !== "reset");
  }
  $("release").disabled ||= !!state?.diagnostics.released || !!state?.warning;
  $("step").disabled ||= !!state?.warning;
  $("run").disabled =
    !running && (!state || busy || dirty || disconnected || !!state?.warning);
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
      if (state.warning) running = false;
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
  $("double-controls").hidden = !two;
  $("experiment-note").textContent = two
    ? "Prepare two coherent Gaussian packets, already released. Change the relative phase to move the fringes."
    : "Prepare the ground state in a harmonic trap. Release it to watch the cloud expand.";
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
    for (const key of fields)
      $(key).value =
        key === "experiment"
          ? result.config[key]
          : result.config[key] / (key === "phase" ? Math.PI : 1);
    labels();
  }
});
$("export").addEventListener("click", async () => {
  const data = await request("export");
  if (!data) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `coldatomlab-${data.config.experiment}-${data.steps}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
    length = state.config.length;
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
  ctx.fillText("x / a₀", left + side / 2, top + side + 34);
  ctx.save();
  ctx.translate(left - 37, top + side / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("y / a₀", 0, 0);
  ctx.restore();
  canvas.setAttribute(
    "aria-label",
    `${view === "density" ? "Density" : "Masked phase"} of ${state.config.experiment === "single" ? "one condensate" : "two coherent clouds"}, time ${state.diagnostics.time.toFixed(3)}, domain ${length} a0 per side`,
  );
  $("legend-label").textContent =
    view === "density" ? "DENSITY |ψ|² · a₀⁻²" : "PHASE · RADIANS";
  $("legend-low").textContent = view === "density" ? "0" : "−π";
  $("legend-high").textContent =
    view === "density" ? peak.toPrecision(3) : "+π";
  $("colorbar").style.background =
    view === "density"
      ? ""
      : `linear-gradient(90deg,${Array.from({ length: 13 }, (_, i) => `rgb(${phaseColor(-Math.PI + (i * Math.PI) / 6).join(",")})`).join(",")})`;
}

function plot(id, series, xmin, xmax, ymax, xlabel, ylabel) {
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
    ctx.fillText(((ymax * i) / 3).toPrecision(2), left - 9, y + 3);
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
        py = bottom - (y / ymax) * (bottom - top);
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
        bottom - (y / ymax) * (bottom - top),
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
  const d = state.diagnostics;
  $("experiment-title").textContent =
    state.config.experiment === "single"
      ? "Condensate expansion"
      : "Matter-wave interference";
  $("time").innerHTML = `${d.time.toFixed(3)} <small>ω₀⁻¹</small>`;
  $("width").innerHTML = `${d.width_x.toFixed(3)} <small>a₀</small>`;
  $("norm").textContent = d.norm.toFixed(8);
  $("energy").innerHTML = `${d.energy.toFixed(4)} <small>ℏω₀</small>`;
  $("grid-label").textContent =
    `${state.config.n} × ${state.config.n} · L = ${state.config.length} a₀`;
  $("trap-state").textContent = d.released
    ? "TRAP OFF / EXPANDING"
    : "TRAP ON / CONFINED";
  $("warning").textContent = state.warning;
  $("warning").hidden = !state.warning;
  $("boundary").textContent =
    `Boundary population: ${(100 * d.edge_mass).toExponential(2)}% / stop at 0.1%`;
  drawField();
  plot(
    "profile",
    [
      {
        color: "#c3e2a0",
        points: state.x.map((x, i) => [x, state.cross_section[i]]),
      },
    ],
    -state.config.length / 2,
    state.config.length / 2,
    Math.max(...state.cross_section) * 1.15,
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
    ],
    0,
    Math.max(1, d.time),
    Math.max(...history.map((p) => Math.max(p.width_x, p.width_y))) * 1.15,
    "t / ω₀⁻¹",
    "RMS width / a₀",
  );
}

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (state) render();
  }, 100);
});
labels();
controls();
request("prepare", { config: config() });
