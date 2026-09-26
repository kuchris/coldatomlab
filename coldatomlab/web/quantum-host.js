"use strict";
// Keep the quantum workspace alive inside the library shell across navigation.
(() => {
  const frame = document.getElementById("quantum-frame");
  const section = document.getElementById("quantum-page");
  const standalone = document.body.classList.contains("browser-home");
  function navigate() {
    const active = location.hash === "#quantum";
    section.hidden = !active;
    if (active && !frame.hasAttribute("src")) frame.src = "quantum.html#embedded";
    if (standalone) {
      document.getElementById("experiments").hidden = active || location.hash === "#vortex";
      if (location.hash !== "#vortex") document.title = `${active ? "Quantum coherence" : "Experiments"} · Cold Atom Lab`;
    }
  }
  window.addEventListener("message", event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === "quantum-height" && Number.isFinite(event.data.height))
      frame.style.height = `${Math.max(400, Math.min(40000, event.data.height))}px`;
    if (event.data?.type === "quantum-route" && ["experiments", "lab3d"].includes(event.data.route)) {
      if (standalone && event.data.route === "lab3d") location.href = "gpu.html";
      else location.hash = event.data.route;
    }
  });
  window.addEventListener("hashchange", navigate);
  navigate();
})();
