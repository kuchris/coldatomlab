// Lab-unit controls adapt to the canonical dimensionless solver configuration.
const physicalKeys = [
  "species",
  "mass_u",
  "atoms",
  "scattering_nm",
  "reference_hz",
  "axial_hz",
];
const unitFields = {
  omega_x: ["energy_hz", "Trap frequency x", "Hz"],
  omega_y: ["energy_hz", "Trap frequency y", "Hz"],
  separation: ["length_um", "Cloud separation", "μm"],
  barrier_height: ["energy_hz", "Barrier height · V/h", "Hz"],
  barrier_width: ["length_um", "Barrier width", "μm"],
  split_time: ["time_ms", "Split time", "ms"],
  hold_time: ["time_ms", "Hold time", "ms"],
  expansion_time: ["time_ms", "Expansion", "ms"],
  bias: ["energy_hz", "Hold bias · ΔV/h", "Hz"],
  dt: ["time_ms", "Time step", "ms"],
  length: ["length_um", "Domain side", "μm"],
};
const naturalScale = { length_um: 1, time_ms: 1, energy_hz: 1 };
let formScale = { ...naturalScale },
  inputDefaults = null;

function physicalInputs() {
  if ($("unit-mode").value !== "physical") return null;
  return Object.fromEntries(
    physicalKeys.map((k) => [
      k,
      k === "species" ? $(k).value : Number($(k).value),
    ]),
  );
}
function draftScales() {
  const p = physicalInputs();
  if (!p) return { ...naturalScale };
  const mass =
    p.species === "Rb87" ? 1.443160895e-25 : p.mass_u * 1.6605390666e-27;
  const hbar = 6.62607015e-34 / (2 * Math.PI);
  const az = Math.sqrt(hbar / (mass * 2 * Math.PI * p.axial_hz));
  return {
    length_um: Math.sqrt(hbar / (mass * 2 * Math.PI * p.reference_hz)) * 1e6,
    time_ms: 1000 / (2 * Math.PI * p.reference_hz),
    energy_hz: p.reference_hz,
    interaction:
      (Math.sqrt(8 * Math.PI) * p.atoms * p.scattering_nm * 1e-9) / az,
  };
}
function syncPhysicalInputs() {
  const physical = !!physicalInputs();
  if (
    !physical &&
    Number.isFinite(formScale.interaction) &&
    formScale.interaction <= 100
  ) {
    $("interaction").step = "any";
    $("interaction").value = String(formScale.interaction);
  }
  $("physical-controls").hidden = !physical;
  for (const k of physicalKeys) $(k).disabled = !physical;
  $("mass_u").disabled = !physical || $("species").value !== "custom";
  $("interaction").disabled = physical;
  if (!inputDefaults) {
    inputDefaults = Object.fromEntries(
      Object.keys(unitFields).map((k) => {
        const input = $(k),
          label = input.labels[0];
        return [
          k,
          {
            min: input.min,
            max: input.max,
            step: input.step,
            options: input.options
              ? Array.from(input.options, (o) => Number(o.value))
              : null,
            label,
            text: label.firstChild.textContent,
          },
        ];
      }),
    );
  }
  const next = draftScales();
  if (
    ![next.length_um, next.time_ms, next.energy_hz].every(
      (v) => Number.isFinite(v) && v > 0,
    )
  )
    return;
  for (const [k, [scale, title, unit]] of Object.entries(unitFields)) {
    const input = $(k),
      old = inputDefaults[k];
    const canonical = Number(input.value) / formScale[scale];
    if (old.options) {
      input.replaceChildren(
        ...old.options.map(
          (v) =>
            new Option((v * next[scale]).toFixed(3), String(v * next[scale])),
        ),
      );
      input.value = String(
        old.options.reduce((a, b) =>
          Math.abs(a - canonical) < Math.abs(b - canonical) ? a : b,
        ) * next[scale],
      );
    } else {
      if (old.min !== "") input.min = String(Number(old.min) * next[scale]);
      if (old.max !== "") input.max = String(Number(old.max) * next[scale]);
      input.step = "any"; // Physical edits may map to arbitrary dimensionless values.
      if (formScale[scale] !== next[scale]) {
        const exact = canonical * next[scale];
        let displayed = Number(exact.toPrecision(8));
        // Rounding the display must not put a valid endpoint outside its range.
        if (exact >= Number(input.min) && exact <= Number(input.max))
          displayed = Math.max(
            Number(input.min),
            Math.min(Number(input.max), displayed),
          );
        input.value = String(displayed);
      }
    }
    old.label.firstChild.textContent = physical
      ? `${title} · ${unit}`
      : old.text;
  }
  formScale = next;
  $("interaction-value").textContent = physical
    ? `${next.interaction.toFixed(3)} (derived)`
    : $("interaction").value;
  $("separation-value").textContent =
    `${Number($("separation").value).toFixed(2)} ${physical ? "μm" : "a₀"}`;
  $("trap-units-note").textContent = physical
    ? "Frequencies are cycles/s (Hz), not angular frequencies. Changing the reference scale rescales displayed controls at fixed dimensionless settings."
    : "In units of ω₀; sets packet widths for two clouds.";
  $("sequence-limit").textContent =
    `Automatic release and stop. Total duration ≤ ${(18 * next.time_ms).toFixed(2)} ${physical ? "ms" : "ω₀⁻¹"}. Positive bias raises the right well.`;
}
function canonicalValue(key) {
  let value = Number($(key).value) * (key === "phase" ? Math.PI : 1);
  if (!unitFields[key]) return value;
  value /= formScale[unitFields[key][0]];
  const limits = inputDefaults[key];
  for (const bound of [limits.min, limits.max]) {
    if (
      bound !== "" &&
      bound !== undefined &&
      Math.abs(value - Number(bound)) < 1e-10
    )
      return Number(bound);
  }
  return value;
}
function restorePhysical(c) {
  // Bring current controls to natural units before loading saved canonical values.
  $("unit-mode").value = "dimensionless";
  syncPhysicalInputs();
  for (const key of fields)
    $(key).value =
      key === "experiment" ? c[key] : c[key] / (key === "phase" ? Math.PI : 1);
  if (c.physical) {
    for (const k of physicalKeys) $(k).value = c.physical[k];
    $("unit-mode").value = "physical";
  }
  labels();
}
function labScale(s = state) {
  return s?.physical || naturalScale;
}
function unitText(kind, s = state) {
  return s?.physical
    ? { length: "μm", time: "ms", energy: "Hz (E/h)" }[kind]
    : { length: "a₀", time: "ω₀⁻¹", energy: "ℏω₀" }[kind];
}
function renderPhysical() {
  const p = state.physical;
  $("physical-readout").hidden = !p;
  if (!p) return;
  $("physical-scale").textContent =
    `${p.parameters.species === "Rb87" ? "⁸⁷Rb" : "Custom boson"} · ${p.parameters.atoms} atoms · g = ${p.interaction.toFixed(3)} · a₀ = ${p.length_um.toFixed(3)} μm · 1/ω₀ = ${p.time_ms.toFixed(3)} ms · aᶻ = ${p.axial_length_um.toFixed(3)} μm`;
  const box = $("regime-status");
  box.dataset.status = p.status;
  box.textContent = {
    supported: "Scale separation supported",
    marginal: "Marginal scale separation",
    outside: "Outside the frozen-axial regime",
  }[p.status];
  const names = [
    "Initial μ∥ / ℏωz",
    "Peak gn / ℏωz",
    "Mean kinetic / ℏωz",
    "max(fx, fy) / fz",
    "as / az",
    "Peak n3D as³",
  ];
  $("regime-ratios").textContent = Object.values(p.ratios)
    .map((v, i) => `${names[i]} = ${v.toPrecision(3)}`)
    .join(" · ");
  $("lab-snapshot").textContent =
    `Current run: fx = ${(state.config.omega_x * p.energy_hz).toFixed(2)} Hz, fy = ${(state.config.omega_y * p.energy_hz).toFixed(2)} Hz, fz = ${p.parameters.axial_hz} Hz (retained after release).`;
}
const demos = {
  balanced: {
    bias: 0,
    hold_time: 1,
    text: "Symmetric reference. Run to completion, then Pin reference. Compare with a biased run at the same readout time.",
  },
  positive: {
    bias: 0.5,
    hold_time: 1,
    text: "Raise the right well by ΔV/h = 10 Hz. Inspect the negative right-minus-left phase during Hold and the changed interference profile after release.",
  },
  negative: {
    bias: -0.5,
    hold_time: 1,
    text: "Reverse the bias to −10 Hz. Against the +10 Hz reference, the ideal symmetric model should mirror the populations and phase sign.",
  },
  longer: {
    bias: 0.5,
    hold_time: 2,
    text: "Double the hold from 7.96 to 15.92 ms at +10 Hz. Inspect phase at the end of Hold; interactions and tunnelling mean the change need not be exactly twice as large.",
  },
};
function setupDemos() {
  $("load-demo").addEventListener("click", () => {
    const demo = demos[$("demo").value];
    restorePhysical({
      experiment: "sequence",
      n: 128,
      length: 32,
      dt: 0.01,
      interaction: 20,
      omega_x: 1,
      omega_y: 1.4,
      separation: 6,
      phase: 0,
      barrier_height: 12,
      barrier_width: 0.7,
      split_time: 4,
      expansion_time: 2,
      hold_time: demo.hold_time,
      bias: demo.bias,
      physical: {
        species: "Rb87",
        mass_u: 86.90918052,
        atoms: 200,
        scattering_nm: 5.3,
        reference_hz: 20,
        axial_hz: 2000,
      },
    });
    $("demo-note").textContent =
      demo.text +
      " Teaching parameters; not a reproduction of a published apparatus. Prepare to apply.";
    dirty = true;
    controls();
  });
}
