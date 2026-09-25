"use strict";
document.querySelector('#three-engine option[value="cpu"]').disabled = true;
document.getElementById("three-engine-note").textContent =
  "Standalone WebGPU lab · no Python or simulation server. Open over HTTPS or localhost in a browser with hardware WebGPU.";
window.showLab3D();
