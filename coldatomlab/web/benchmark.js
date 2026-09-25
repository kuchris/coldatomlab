"use strict";

(() => {
  let result = null;
  let loading = false;
  function draw() {
    if (!result || $("paper-benchmark").hidden) return;
    const canvas = $("benchmark-profile");
    const width = canvas.clientWidth;
    const height = width < 500 ? 260 : 340;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    const left = 60, right = width - 18, top = 26, bottom = height - 45;
    const b = result.base;
    const max = Math.max(...b.density_per_um) * 1.08;
    const px = x => left + (x + 200) / 400 * (right - left);
    const py = y => bottom - y / max * (bottom - top);
    ctx.font = '11px "Segoe UI", sans-serif';
    ctx.fillStyle = "#637083";
    ctx.strokeStyle = "#e4e9ef";
    for (let i = 0; i <= 4; i++) {
      const value = max * i / 4;
      ctx.beginPath(); ctx.moveTo(left, py(value)); ctx.lineTo(right, py(value)); ctx.stroke();
      ctx.textAlign = "right";
      ctx.fillText(value.toFixed(3), left - 8, py(value) + 4);
      ctx.textAlign = "center";
      ctx.fillText(String(-200 + 100 * i), px(-200 + 100 * i), bottom + 20);
    }
    ctx.textAlign = "left"; ctx.fillText("Probability / µm", left, 14);
    ctx.textAlign = "center"; ctx.fillText("Position x / µm", (left + right) / 2, height - 4);
    for (const [values, color, dash] of [
      [b.density_per_um, "#2166ce", []], [b.fitted_density_per_um, "#a16617", [5, 4]],
    ]) {
      ctx.strokeStyle = color; ctx.lineWidth = 1.7; ctx.setLineDash(dash); ctx.beginPath();
      values.forEach((y, i) => i ? ctx.lineTo(px(b.x_um[i]), py(y)) : ctx.moveTo(px(b.x_um[i]), py(y)));
      ctx.stroke();
    }
  }
  function tableRow(body, cells) {
    const tr = document.createElement("tr");
    cells.forEach(value => {
      const td = document.createElement("td"); td.textContent = value; tr.append(td);
    });
    body.append(tr);
  }
  function display() {
    const b = result.base;
    $("benchmark-fit").textContent = `${b.fit.period_um.toFixed(3)} µm`;
    $("benchmark-difference").textContent = `${result.comparison[0].relative_difference_percent.toFixed(2)}%`;
    $("benchmark-width").textContent = `${result.inputs.packet_rms_width_um.toFixed(3)} µm · harmonic-ground-state surrogate from 615 Hz; not a measured cloud width`;
    $("benchmark-comparison").replaceChildren();
    result.comparison.forEach(row => tableRow($("benchmark-comparison"), [
      row.label, row.period_um.toFixed(4), row.difference_um.toFixed(4), `${row.relative_difference_percent.toFixed(3)}%`,
    ]));
    $("benchmark-checks").replaceChildren();
    Object.entries(result.checks).forEach(([name, c]) => tableRow($("benchmark-checks"), [
      name.replaceAll("_", " "), c.fit.period_um.toFixed(6), c.period_change_um.toExponential(2),
      c.analytic_wavefunction_l2_error.toExponential(2), c.edge_probability.toExponential(2),
    ]));
    $("benchmark-verification").textContent = `Base grid: ${b.n} points over ${b.length_um} µm. Norm: ${b.norm.toFixed(12)}. Field L2 error against the independent Gaussian solution: ${b.analytic_wavefunction_l2_error.toExponential(2)}. Relative profile fit residual: ${(b.fit.relative_profile_l2_residual * 100).toFixed(3)}%.`;
    $("benchmark-limitations").replaceChildren();
    result.limitations.forEach(text => { const li = document.createElement("li"); li.textContent = text; $("benchmark-limitations").append(li); });
    $("benchmark-result").hidden = false;
    $("benchmark-export").disabled = false;
    $("benchmark-status").textContent = "Calculation complete · comparison of one observable; experimental agreement is not established.";
    draw();
  }
  window.loadBenchmark = async () => {
    if (result) { draw(); return; }
    if (loading) return;
    loading = true;
    $("benchmark-retry").hidden = true;
    $("benchmark-status").textContent = "Calculating the wavepacket, fitted spacing and refinement checks…";
    try {
      const response = await fetch("/api/benchmark");
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      if (data.schema !== "coldatomlab-shin-benchmark-v1") throw new Error("Unexpected report format");
      result = data;
      display();
    } catch (error) {
      $("benchmark-status").textContent = `Could not calculate the benchmark. ${error.message}. Your workspace is unchanged.`;
      $("benchmark-retry").hidden = false;
    } finally { loading = false; }
  };
  $("benchmark-retry").addEventListener("click", window.loadBenchmark);
  $("benchmark-export").addEventListener("click", () => {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "coldatomlab-shin-benchmark.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener("resize", draw);
})();
