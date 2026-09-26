"use strict";
(() => {
  const frame = document.getElementById("vortex-frame"),
    section = document.getElementById("vortex-page"),
    standalone = document.body.classList.contains("browser-home");
  function navigate() {
    const active = location.hash === "#vortex";
    section.hidden = !active;
    if (active && !frame.hasAttribute("src"))
      frame.src = "vortex.html#embedded";
    if (!active && frame.contentWindow)
      frame.contentWindow.postMessage(
        { type: "vortex-hidden" },
        location.origin,
      );
    if (standalone && active) {
      document.getElementById("experiments").hidden = true;
      document.title = "Vortex Lab · Cold Atom Lab";
    }
  }
  window.addEventListener("message", (event) => {
    if (
      event.origin !== location.origin ||
      event.source !== frame.contentWindow
    )
      return;
    if (
      event.data?.type === "vortex-height" &&
      Number.isFinite(event.data.height)
    )
      frame.style.height = `${Math.max(500, Math.min(20000, event.data.height))}px`;
  });
  window.addEventListener("hashchange", navigate);
  navigate();
})();
