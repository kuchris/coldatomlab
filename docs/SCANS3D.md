# Automated 3D phase scans (v0.9)

The **Measure a phase curve** workspace runs fresh WebGPU experiments at a sequence of parameter values, then acquires repeated virtual camera images from each frozen final field. It is available in both the full dashboard and the static GPU package. It never advances, replaces or resets the manually prepared experiment. Scan controls require hardware WebGPU even if the manual experiment uses the CPU backend; independent float64 verification is provided offline.

## Workflow

1. Open the 3D lab or `gpu.html`. No manual preparation is required for a scan.
2. Start with **Known pair phase · calibration**. Choose the first/last phase, number of points and exposures. **Run scan** prepares and evolves a new field for each point.
3. Inspect input versus recovered phase, detector scatter, ideal-image phase and wrapped differences. Export CSV for the table or **Export reproducible data** for recipes, projections, raw frames and measurements.
4. Choose **Interacting split · hold bias** or **Interacting split · hold time** to vary the dynamical protocol. Actual rounded hold time is displayed in milliseconds.
5. Enable **Compare 64³ / 128³** to repeat each physical recipe on both grids. This is slower and increases export size.

Pause/cancel take effect after the current preparation, step batch or exposure. Preparation is not interruptible. Cancel discards the unfinished point and retains completed points for export. Boundary/norm stops are recorded with a reason and the scan continues to the next recipe; device or unexpected acquisition errors stop the batch. A batch marked complete means all scheduled jobs were attempted, not that all images or fields succeeded. A scan is bounded to 2–9 points, 1–20 exposures and at most 80 total exposures. Reloading clears the results.

## Physical recipes and units

Conventions remain integral |psi|² d³X=1, X=r/a0, a0=sqrt(hbar/(m omega0)), tau=omega0 t, and g=4 pi N as/a0. Real-time evolution is never renormalized. All three axes release. Rb-87 N=2,000 and f0=30 Hz are fixed in the current scan UI, with trap frequencies x/y/z=30/42/21 Hz; one time unit is 5.30516 ms. The recipe is shown before running and retained in the export.

| Setting | Pair calibration | Interacting hold/bias scans |
| --- | --- | --- |
| Initial condition | Normalized coherent Gaussian pair | Prepared single condensate |
| Scattering length | 0 nm | 5.3 nm |
| Box / a0 | 32 | 24 |
| dt / omega0^-1 | 0.004 | 0.006 |
| Preparation dt | 0.002 | 0.002 |
| Pair separation | 6 a0 | Not applicable |
| Barrier | Not applicable | Height 12 hbar omega0; width 0.8 a0 |
| Split duration | Not applicable | 3 omega0^-1 |
| Expansion duration | 3 omega0^-1 | 2 omega0^-1 |
| Default scan interval | Phase −2.4 to +2.4 rad | Bias −1 to +1 hbar omega0; hold 0.45–0.9 omega0^-1 |
| Fixed hold/bias | Not applicable | Hold 0.6 for bias scans; bias +1 for hold scans |

Five points and five detector exposures are selected initially. Endpoints are included. Each stage duration is rounded using floor(duration/dt+0.5); actual split, hold, expansion step counts and physical hold/end times are exported. A requested hold of 0.675 at dt=0.006 becomes 0.678. There is no hidden fitting to paper data.

The shorter hold settings 0 and 0.3 hit the periodic-boundary guard in exploratory runs with this box; hold 1.2 completed but had unresolved image fits. The default interval uses working examples. Wider intervals remain selectable and retain those failures. This is a physical/numerical applicability limit, not a reason to suppress failed points or weaken a guard.

## Phase guide, camera and statistics

The pair guide is the known initial right-minus-left phase. The interacting guide is −bias × **actual** hold time: from d(phi_R−phi_L)/dt=−(V_R−V_L)/hbar, assuming well-separated arms. The smooth tanh bias, finite coupling, interaction imbalance and nonrigid profiles can make the image phase differ. The guide neither drives nor constrains the camera fit, and is not identified with the post-expansion mirror phase.

Each source has an independent **ideal** image acquisition with no blur/noise and native source pixels. Each measured exposure uses the selected optics and detector settings. The algorithm and rejection criteria are unchanged from [v0.8 imaging](IMAGING3D.md). Default camera values are ROI ±12 µm, strip 4 µm, quantum efficiency 0.8, read noise 1 electron, pulse 5 µs and native pixels. Pair scans start at I/Isat=1; interacting scans start at 10 to improve transmitted counts in the denser cloud. Strong saturation is part of the ideal absorption equation, not proof that omitted recoil, multilevel or motion effects are negligible. Per-point camera warnings remain visible.

The seed for point p and exposure j is `(first_seed + p * repeats + j) mod 2^32`, with zero-based indices. The same seed list is used for both grids, although different detector grids consume different random sequences. A new numerical evolution is performed for every parameter/grid job. Only repeated detector exposures share a frozen field; these are **detector noise repeats**, not independent condensate realizations or a simulation of quantum/thermal phase diffusion.

For K valid measured phases, C=mean cos(phi), S=mean sin(phi), R=sqrt(C²+S²). The circular mean is atan2(S,C), and circular scatter is sqrt(−2 ln R), clipping floating-point R to at most one. The mean/scatter are unavailable for R<0.1; scatter additionally requires K>=2. Period and fitted contrast are arithmetic means of valid fits. Failure fraction=(attempted−valid)/attempted. Surviving-image statistics can be selection-biased when fits fail. No standard error or confidence interval is claimed.

All phase differences use atan2(sin(delta),cos(delta)). Plots retain the ±pi branch, break guide lines across its jump, and wrap scatter bars at the branch. No unwrapping is inferred through missing points. The error plot scales to the observed differences/scatter, while the phase plot uses ±pi. Failed/no-mean points appear as red crosses at the bottom of the chart, not zero-phase measurements. Raw images remain in JSON even when fits fail.

## Grid sensitivity

64³ and 128³ runs have identical physical inputs, box and step durations. Width differences are `(fine/coarse−1)`; the table shows all three axes and norm differences. The separate ideal-image phase difference includes solver, profile sampling and estimator effects. Ideal images use native cells without noise/PSF; measured exposures keep the selected integer binning, so the finer grid's detector pitch is half as large. No claim of equal detector hardware/noise between grids is made. Two grids provide sensitivity evidence, not an asymptotic convergence proof or universal error bar.

## Compact export and independent replay

`coldatomlab-scan3d-v1` stores the immutable plan, status, ordered completed/stopped records, grid comparison, actual timing, source physical coordinates/scales, all three final projections, norm/width diagnostics, backend identity, ideal image and all detector frames/settings/seeds/fits. It omits full complex wavefunctions and intermediate histories to keep batches manageable. CSV contains the summary, parameter units, physical timing and failure information; use JSON for replay.

```
uv run python -m coldatomlab.replay path/to/coldatomlab-scan3d.json
```

For each saved complete record, Python validates the recipe/order/count/timing, independently prepares and evolves the float64 field to the endpoint, and compares all three projections (relative L2 <=0.005), widths (relative difference <=0.005) and norm drift (<=0.001). Projection integrals/moments must independently reproduce the saved norm/widths. It then regenerates the camera from the **saved GPU projection**, using the independent NumPy optical implementation and specified PRNG, and checks every numerical image/frame plus fit, as in v0.8. This separates GPU-versus-CPU tolerance from deterministic camera consistency. Circular statistics, guide and grid differences are recomputed and checked.

This verifies density projections and measured observables, **not the full complex GPU field**. Stopped records have no saved projection and are explicitly returned as `unverified_stop`; cancellation/failure status and missing jobs remain visible. Human-readable warning text, adapter descriptions and stop reasons are provenance, not independently certified measurements. Replaying a batch recomputes all complete fields, including both grids, and can take substantially longer than browser execution.

## Primary references

- [Shin et al., Atom Interferometry with Bose–Einstein Condensates in a Double-Well Potential, PRL 92, 050405 (2004)](https://arxiv.org/abs/cond-mat/0306305): motivation for coherent splitting, controlled phase shifts and evolution while separated. Their Na-23 optical apparatus and published data are not reproduced by these Rb-87 scan recipes.
- [Reinaudi et al. (2007), Strong saturation absorption imaging](https://arxiv.org/abs/0707.2930): the saturation correction, with the project's declared ideal alpha=1 limit.
- [Ketterle, Durfee & Stamper-Kurn (1999), Making, probing and understanding Bose–Einstein condensates](https://arxiv.org/abs/cond-mat/9904034): absorption-imaging and condensate-measurement context.

The [existing source audit](SHIN_REFERENCE.md), [3D solver evidence](INTERFEROMETER3D.md) and [camera limits](IMAGING3D.md) remain applicable. The estimator, acceptance gates, PRNG and scan intervals are implementation choices, not methods claimed to be copied from those experiments.

## Verification

Numerical tests check branch-cut circular means/scatter, ambiguous/no/single valid measurements, recipe bounds, exact detector-seed schedules, incomplete datasets, grid statistics, cancellation/resource cleanup, and tampering with frames, seed, projection, recipe, statistics or completion counts. Browser tests use real fresh WebGPU runs and then independently replay their exports.

Representative 64³ hardware Chrome runs, three exposures per point, first seed 17:

| Scan point | Ideal-image phase / rad | Mean measured phase / rad | Detector circular scatter / rad |
| --- | ---: | ---: | ---: |
| Pair input −1 rad | −0.99390 | −0.99733 | 0.03740 |
| Pair input 0 rad | 0.000002 | 0.00569 | 0.00505 |
| Pair input +1 rad | 0.99390 | 1.00643 | 0.04410 |
| Bias −1, hold 0.6 | 0.58847 | 0.58206 | 0.01780 |
| Bias +1, hold 0.6 | −0.58859 | −0.60404 | 0.01049 |
| Hold 0.45, bias +1 | −0.43810 | −0.44188 | 0.03467 |
| Hold 0.9, bias +1 | −0.88771 | −0.89619 | 0.01990 |

For pair phases 0.2 and 0.8, 64³→128³ maximum relative width changes were 7.75e-7 (0.0000775%), while ideal-image phase changed by 0.000580 and 0.000984 rad. Norm changed by about −1.45e-5. These are measured sensitivities for these recipes, not general accuracy guarantees.

Browser controls checked separately: manual-state preservation through scan execution, pause/resume, fresh same-seed repeatability, failed-input recovery, hold/bias scans, unresolved x-view images, cancellation retaining completed points, CSV/JSON downloads, refinement and 390/320-pixel layouts. Screenshots and exports are under ignored `artifacts/scan3d/`. Reproduce with a temporary server:

```
uv run python -m coldatomlab.server --port 8766
uv run python -m scripts.scan3d_browser_check --refine --verify
```

`--verify` runs the independent float64/camera checks after browser testing. The static package includes both scan scripts and requires no simulation API or remote assets; publication is not performed automatically.

Release checks: **112 pytest tests passed**; Ruff check/format and changed JavaScript syntax checks passed. Complete phase, bias, hold, unresolved-view, cancelled and 64³/128³ exports passed independent replay. The largest measured GPU/CPU projection relative L2 difference in these exports was 3.03e-4, below the 0.005 gate. Full dashboard and standalone browser workflows had no page errors; extracted static runs made no simulation API requests. The final ZIP was separately checked for actual checkpoint pause/resume, CSV timing columns, scaled error plots, model links and mobile overflow. These checks verify the implemented model and controls, not experimental agreement.
