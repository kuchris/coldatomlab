"use strict";

// Navigation only changes what is visible. The existing solver session and
// pinned records stay in memory until the user explicitly prepares or resets.
(() => {
  const routes = {
    experiments: "Experiments",
    workspace: "Experiment workspace",
    measurements: "Measurements",
    "camera-lab": "Virtual camera",
    benchmark: "Paper benchmark",
  };
  const nav = $("lab-navigation");
  const toggle = $("nav-toggle");
  function closeNavigation() {
    nav.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  }
  function navigate() {
    const route = Object.hasOwn(routes, location.hash.slice(1))
      ? location.hash.slice(1) : "experiments";
    const library = route === "experiments";
    const benchmark = route === "benchmark";
    $("experiment-library").hidden = !library;
    $("lab-workbench").hidden = library || benchmark;
    $("paper-benchmark").hidden = !benchmark;
    $("page-label").textContent = routes[route];
    document.title = `${routes[route]} · Cold Atom Lab`;
    document.querySelectorAll("[data-route]").forEach((link) => {
      if (link.dataset.route === route) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    closeNavigation();
    if (!library && !benchmark && state) render();
    if (benchmark) window.loadBenchmark();
    requestAnimationFrame(() => {
      const target = route === "measurements" || route === "camera-lab"
        ? $(route) : $("main-content");
      target.scrollIntoView({ block: "start" });
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    });
  }
  window.addEventListener("hashchange", navigate);
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-open")) {
      closeNavigation();
      toggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!nav.contains(event.target) && !toggle.contains(event.target)) closeNavigation();
    const link = event.target.closest('a[href^="#"]');
    if (link && link.hash === location.hash && Object.hasOwn(routes, link.hash.slice(1))) {
      event.preventDefault();
      navigate();
    }
  });
  for (const id of ["nav-model", "library-model"]) {
    $(id).addEventListener("click", () => {
      closeNavigation();
      $("model-dialog").showModal();
    });
  }
  const search = $("experiment-search");
  function filter() {
    const query = search.value.trim().toLowerCase();
    let count = 0;
    document.querySelectorAll(".experiment-card").forEach((card) => {
      card.hidden = !card.dataset.search.includes(query);
      if (!card.hidden) count++;
    });
    $("library-count").textContent = `${count} experiment${count === 1 ? "" : "s"}`;
    $("library-empty").hidden = count !== 0;
  }
  search.addEventListener("input", filter);
  $("clear-search").addEventListener("click", () => {
    search.value = "";
    filter();
    search.focus();
  });
  for (const mode of ["grid", "list"]) {
    $(`${mode}-layout`).addEventListener("click", () => {
      $("experiment-cards").classList.toggle("list-layout", mode === "list");
      $("grid-layout").setAttribute("aria-pressed", String(mode === "grid"));
      $("list-layout").setAttribute("aria-pressed", String(mode === "list"));
    });
  }
  document.querySelectorAll(".open-experiment").forEach((button) => {
    button.addEventListener("click", () => {
      if (busy || running) return;
      $("experiment").value = button.dataset.experiment;
      $("experiment").dispatchEvent(new Event("change", { bubbles: true }));
      location.hash = "workspace";
    });
  });
  window.updateDashboard = () => {
    document.querySelectorAll(".open-experiment").forEach((button) => {
      button.disabled = busy || running;
      button.title = running ? "Pause your current experiment to change its setup." : "Choose settings, then Prepare experiment to apply them.";
    });
    const names = { single: "Condensate expansion", double: "Matter-wave interference", sequence: "Split / hold / release" };
    const status = disconnected ? "Connection lost" : busy ? "Working" : running ? "Running" : dirty ? "Settings pending" : state?.complete ? "Complete" : state?.warning ? "Stopped" : state?.diagnostics.steps ? "Paused" : "Ready";
    $("library-session-status").textContent = state
      ? `${names[state.config.experiment]} · ${status}` : "Preparing your first cloud…";
  };
  window.updateDashboard();
  navigate();
})();
