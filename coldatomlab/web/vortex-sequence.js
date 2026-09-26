"use strict";
// Protocol time uses integer solver steps; UI frame rate never sets release time.
window.VortexSequence = {
  protocol(config, holdMs, tofMs) {
    const t0 = 1000 / (2 * Math.PI * config.radial_hz);
    if (
      !Number.isFinite(holdMs) ||
      holdMs < 0 ||
      holdMs > 16 * t0 ||
      !Number.isFinite(tofMs) ||
      tofMs < 0.1 * t0 ||
      tofMs > 6 * t0
    )
      throw Error(
        "Hold must be 0–16 t₀ and TOF 0.1–6 t₀. Times are entered in ms.",
      );
    return {
      requested_hold_ms: holdMs,
      requested_tof_ms: tofMs,
      hold_steps: Math.round(holdMs / (t0 * config.dt)),
      tof_steps: Math.round(tofMs / (t0 * config.dt)),
      step_ms: config.dt * t0,
    };
  },
  async run(config, protocol, camera, hooks) {
    const t0 = 1000 / (2 * Math.PI * config.radial_hz);
    const c = {
      ...config,
      duration: Math.max(0.1, protocol.requested_hold_ms / t0),
      tof_duration: protocol.requested_tof_ms / t0,
    };
    const progress = (message) => {
      if (hooks.stopped())
        throw Error("Stopped during preparation; previous results retained.");
      hooks.stage("Preparing", message);
    };
    const s = await VortexGPU.create(c, progress);
    if (hooks.stopped()) {
      s.destroy();
      throw Error("Stopped during preparation; previous results retained.");
    }
    hooks.prepared(s);
    const advanceTo = async (end, stage) => {
      while (s.steps < end && !hooks.stopped() && !s.warning) {
        await s.advance(Math.min(20, end - s.steps));
        hooks.stage(stage, `${s.steps} steps`);
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    };
    await advanceTo(protocol.hold_steps, "Holding");
    if (!hooks.stopped() && !s.warning) {
      await s.release();
      hooks.stage("Released", "Trap and beam off");
      await advanceTo(protocol.hold_steps + protocol.tof_steps, "Expanding");
    }
    const source = s.export();
    let reference = null;
    if (
      !hooks.stopped() &&
      !s.warning &&
      c.stationary &&
      c.charge &&
      c.height === 0 &&
      c.axial_hz === c.radial_hz
    ) {
      try {
        reference = await VortexPaper.calculate(
          c.g / (4 * Math.PI),
          (message) => {
            if (hooks.stopped()) throw Error("Reference calculation stopped.");
            hooks.stage("Analysing", message);
          },
        );
      } catch (error) {
        if (!hooks.stopped()) throw error;
      }
    }
    const complete =
      !hooks.stopped() &&
      !s.warning &&
      s.steps === protocol.hold_steps + protocol.tof_steps &&
      s.releaseStep === protocol.hold_steps;
    const result = {
      schema: "coldatomlab-vortex-sequence-v1",
      version: "0.18.0",
      protocol: { ...protocol },
      status: complete ? "complete" : "stopped",
      source,
      image: null,
      reference,
    };
    if (complete) {
      hooks.stage("Capturing", "Frozen endpoint");
      result.image = hooks.capture(source, camera);
      // The sequence owns one source field. Its image implicitly uses that
      // endpoint; the standalone image export still embeds its own source.
      result.image = { ...result.image };
      delete result.image.source;
    }
    return result;
  },
};
