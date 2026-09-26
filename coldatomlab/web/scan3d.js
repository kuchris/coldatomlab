"use strict";
// Scan orchestration only. Evolution and acquisition remain in their existing solvers.
window.Scan3D = {
  wrap: (v) => Math.atan2(Math.sin(v), Math.cos(v)),
  base(mode) {
    return {
      ...Interferometry3D.defaults,
      n: 64,
      length: mode === "phase" ? 32 : 24,
      dt: mode === "phase" ? 0.004 : 0.006,
      atoms: 2000,
      scattering_nm: mode === "phase" ? 0 : 5.3,
      reference_hz: 30,
      fx_hz: 30,
      fy_hz: 42,
      fz_hz: 21,
      duration: mode === "phase" ? 3 : 2,
      preparation_dt: 0.002,
      experiment: mode === "phase" ? "pair" : "sequence",
    };
  },
  validate(plan) {
    if (!["phase", "hold", "bias"].includes(plan.mode))
      throw Error("Choose a scan protocol.");
    if (!Number.isInteger(plan.points) || plan.points < 2 || plan.points > 9)
      throw Error("Use 2–9 scan points.");
    if (
      !Number.isInteger(plan.repeats) ||
      plan.repeats < 1 ||
      plan.repeats > 20
    )
      throw Error("Use 1–20 exposures per point.");
    if (typeof plan.refine !== "boolean")
      throw Error("Invalid grid comparison setting.");
    if (plan.points * plan.repeats * (plan.refine ? 2 : 1) > 80)
      throw Error(
        "Limit this batch to 80 exposures; reduce points or repeats.",
      );
    const limits = { phase: [-Math.PI, Math.PI], hold: [0, 3], bias: [-5, 5] }[
      plan.mode
    ];
    if (
      ![plan.start, plan.end].every(Number.isFinite) ||
      plan.start >= plan.end ||
      plan.start < limits[0] ||
      plan.end > limits[1]
    )
      throw Error(`Scan range must increase within ${limits.join(" to ")}.`);
    if (
      plan.base.n !== 64 ||
      plan.base.experiment !== (plan.mode === "phase" ? "pair" : "sequence")
    )
      throw Error("Use a 64³ baseline with the matching scan experiment.");
    GPUCloud3D.validate(plan.base);
    for (const job of this.jobs(plan)) {
      GPUCloud3D.validate(job.config);
      AbsorptionCamera3D.validate(plan.camera, job.config.n);
    }
    return plan;
  },
  jobs(plan) {
    const key = {
        phase: "relative_phase",
        hold: "hold_time",
        bias: "hold_bias",
      }[plan.mode],
      out = [];
    for (let point = 0; point < plan.points; point++) {
      const value =
        plan.start + ((plan.end - plan.start) * point) / (plan.points - 1);
      for (const n of plan.refine ? [64, 128] : [64])
        out.push({
          point,
          value,
          grid: n,
          config: { ...plan.base, [key]: value, n },
        });
    }
    return out;
  },
  statistics(images) {
    const fits = images.map((i) => i.measured).filter((f) => f.available),
      count = fits.length;
    const result = {
      attempted: images.length,
      valid: count,
      failed: images.length - count,
      failure_fraction: images.length
        ? (images.length - count) / images.length
        : null,
      mean_phase: null,
      phase_sd: null,
      resultant: null,
      mean_period: null,
      mean_contrast: null,
    };
    if (!count) return result;
    const c = fits.reduce((s, f) => s + Math.cos(f.phase), 0) / count,
      s = fits.reduce((s, f) => s + Math.sin(f.phase), 0) / count,
      R = Math.min(1, Math.hypot(c, s));
    result.resultant = R;
    if (R >= 0.1) result.mean_phase = Math.atan2(s, c);
    if (count >= 2 && R >= 0.1)
      result.phase_sd = Math.sqrt(Math.max(0, -2 * Math.log(R)));
    result.mean_period = fits.reduce((s, f) => s + f.spacing, 0) / count;
    result.mean_contrast = fits.reduce((s, f) => s + f.contrast, 0) / count;
    return result;
  },
  guide(mode, c) {
    return this.wrap(
      mode === "phase"
        ? c.relative_phase
        : -c.hold_bias * Math.round(c.hold_time / c.dt) * c.dt,
    );
  },
  protocol(c) {
    const split =
        c.experiment === "sequence" ? Math.round(c.split_time / c.dt) : 0,
      hold = c.experiment === "sequence" ? Math.round(c.hold_time / c.dt) : 0,
      expansion = Math.round(c.duration / c.dt),
      ms = 1000 / (2 * Math.PI * c.reference_hz);
    return {
      split_steps: split,
      hold_steps: hold,
      expansion_steps: expansion,
      hold_ms: hold * c.dt * ms,
      end_ms: (split + hold + expansion) * c.dt * ms,
    };
  },
  summary(record, mode) {
    if (record.status !== "complete") return null;
    const stats = this.statistics(record.shots),
      truth = record.ideal.measured;
    return {
      ...stats,
      guide: this.guide(mode, record.source.config),
      ideal_phase: truth.phase,
      ideal_period: truth.spacing,
      ideal_contrast: truth.contrast,
      camera_minus_ideal:
        stats.mean_phase === null || truth.phase === null
          ? null
          : this.wrap(stats.mean_phase - truth.phase),
      ideal_minus_guide:
        truth.phase === null
          ? null
          : this.wrap(truth.phase - this.guide(mode, record.source.config)),
    };
  },
  refinement(records) {
    return records
      .filter((r) => r.grid === 64 && r.status === "complete")
      .flatMap((r) => {
        const fine = records.find(
          (f) =>
            f.point === r.point && f.grid === 128 && f.status === "complete",
        );
        if (!fine) return [];
        const a = r.source.diagnostics,
          b = fine.source.diagnostics;
        return [
          {
            point: r.point,
            value: r.value,
            width_relative: b.widths.map((v, i) => v / a.widths[i] - 1),
            norm_difference: b.norm - a.norm,
            ideal_phase_difference:
              r.ideal.measured.available && fine.ideal.measured.available
                ? this.wrap(fine.ideal.measured.phase - r.ideal.measured.phase)
                : null,
          },
        ];
      });
  },
  csv(report) {
    const rows = [
      [
        "parameter",
        "parameter_unit",
        "point",
        "value",
        "grid",
        "reference_hz",
        "actual_hold_ms",
        "actual_end_ms",
        "status",
        "valid_exposures",
        "failed_exposures",
        "failure_fraction",
        "mean_phase_rad",
        "circular_sd_rad",
        "ideal_phase_rad",
        "guide_rad",
        "camera_minus_ideal_rad",
        "ideal_minus_guide_rad",
        "mean_period_um",
        "mean_contrast",
        "reason",
      ],
    ];
    for (const r of report.records) {
      const s = r.summary || {};
      rows.push([
        report.plan.mode,
        { phase: "rad", hold: "omega0^-1", bias: "hbar omega0" }[
          report.plan.mode
        ],
        r.point,
        r.value,
        r.grid,
        report.plan.base.reference_hz,
        r.source?.protocol.hold_ms,
        r.source?.protocol.end_ms,
        r.status,
        s.valid,
        s.failed,
        s.failure_fraction,
        s.mean_phase,
        s.phase_sd,
        s.ideal_phase,
        s.guide,
        s.camera_minus_ideal,
        s.ideal_minus_guide,
        s.mean_period,
        s.mean_contrast,
        r.reason || "",
      ]);
    }
    return rows
      .map((r) =>
        r.map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`).join(","),
      )
      .join("\r\n");
  },
};

window.Scan3DRunner = class {
  constructor(
    plan,
    onProgress = () => {},
    factory = (c, p) => GPUCloud3D.create(c, p),
  ) {
    this.plan = structuredClone(Scan3D.validate(plan));
    this.onProgress = onProgress;
    this.factory = factory;
    this.paused = false;
    this.cancelled = false;
    this.report = {
      schema: "coldatomlab-scan3d-v1",
      version: "0.14.0",
      camera_model: "rb87-browser-camera-v1",
      plan: this.plan,
      status: "running",
      records: [],
      refinement: [],
    };
  }
  emit(message) {
    this.onProgress(message, this.report);
  }
  async checkpoint() {
    if (this.paused && !this.cancelled)
      this.emit("Paused at a checkpoint; Resume or Cancel.");
    while (this.paused && !this.cancelled)
      await new Promise((r) => setTimeout(r, 50));
    if (this.cancelled)
      throw new DOMException(
        "Scan cancelled; completed points are retained.",
        "AbortError",
      );
  }
  async run() {
    try {
      const jobs = Scan3D.jobs(this.plan);
      for (let index = 0; index < jobs.length; index++) {
        await this.checkpoint();
        const job = jobs[index];
        let sim = null;
        const title = `Point ${job.point + 1}/${this.plan.points} · ${job.grid}³`;
        this.emit(`${title} · preparing`);
        try {
          sim = await this.factory(job.config, (m) =>
            this.emit(`${title} · ${m}`),
          );
          while (!sim.complete && !sim.warning) {
            await this.checkpoint();
            await sim.advance(20);
            this.emit(`${title} · evolving · step ${sim.steps}`);
            await new Promise((r) => setTimeout(r, 0));
          }
          await this.checkpoint();
          if (sim.warning) {
            this.report.records.push({
              point: job.point,
              value: job.value,
              grid: job.grid,
              status: "failed",
              reason: sim.warning,
            });
            this.emit(`${title} · stopped: ${sim.warning}`);
            continue;
          }
          const snap = sim.snapshot(),
            source = {
              config: structuredClone(snap.config),
              scales: snap.scales,
              x: snap.x,
              columns: snap.columns,
              diagnostics: {
                norm: snap.diagnostics.norm,
                widths: snap.diagnostics.widths,
                time: snap.diagnostics.time,
                steps: snap.diagnostics.steps,
              },
              steps: sim.steps,
              release_step: sim.releaseStep,
              protocol: Scan3D.protocol(snap.config),
              backend: snap.backend,
            };
          const ideal = AbsorptionCamera3D.acquire(snap, {
            ...this.plan.camera,
            binning: 1,
            fwhm_um: 0,
            noise: false,
          });
          const record = {
            point: job.point,
            value: job.value,
            grid: job.grid,
            status: "complete",
            source,
            ideal,
            shots: [],
          };
          for (let repeat = 0; repeat < this.plan.repeats; repeat++) {
            await this.checkpoint();
            this.emit(`${title} · exposure ${repeat + 1}/${this.plan.repeats}`);
            await new Promise((r) => setTimeout(r, 0));
            const seed =
              (this.plan.camera.seed +
                job.point * this.plan.repeats +
                repeat) >>>
              0;
            record.shots.push(
              AbsorptionCamera3D.acquire(snap, { ...this.plan.camera, seed }),
            );
          }
          record.summary = Scan3D.summary(record, this.plan.mode);
          this.report.records.push(record);
          this.report.refinement = Scan3D.refinement(this.report.records);
          this.emit(`${title} · recorded`);
        } finally {
          sim?.destroy();
        }
      }
      this.report.status = "complete";
    } catch (e) {
      this.report.status = e.name === "AbortError" ? "cancelled" : "failed";
      this.report.message = e.message;
    }
    this.emit(
      this.report.status === "complete"
        ? "Scan complete."
        : this.report.message,
    );
    return this.report;
  }
};
