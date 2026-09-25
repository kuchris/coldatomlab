# Validation record

Validated locally on Windows with Python 3.12, NumPy 2.5.3, and Playwright Chromium. Dependency versions are captured in `uv.lock`. These checks validate the stated reference cases, not every allowed parameter combination or a physical apparatus.

## Numerical and HTTP checks

`uv run pytest -q`: **18 passed**.

| Check | Acceptance criterion |
| --- | --- |
| Noninteracting harmonic ground state | L2 wavefunction error below `2e-6`; energy error below `1e-8` against `(omega_x + omega_y)/2` |
| Ground-state stationarity | Noninteracting maximum density change below `1e-5` at `t = 1`; interacting RMS x-width relative change below `0.002` at `t = 1` |
| Free Gaussian expansion | Both RMS widths agree with `sqrt((1 + omega²*t²)/(2*omega))` to relative error below `1e-5` at `t = 2` |
| Norm conservation | Drift below `1e-11` for free expansion and `2e-11` for the interacting static-trap cases; no real-time renormalization |
| Interference | At `t = 2`, the in-phase central density exceeds `0.002`; the pi-phase center is below `1e-12` times that value |
| Energy convergence | A displaced interacting state in a fixed trap has energy error reduced by a factor below `0.35` at each halving of `dt`: `0.02`, `0.01`, `0.005` |
| Resolution convergence | Interacting two-cloud expansion at `t = 1`: width differences below `0.5%`, central profile relative L2 differences below `1%`; halve `dt`, double grid resolution at fixed domain, and double domain at fixed spacing separately |
| Export and replay | Reconstruct a run released at step 17 and stopped at step 58; complex field agrees within `1e-13`; reset restores initial state exactly |
| Boundary guard | Evolution stops above `0.1%` boundary population; additional steps hold the state; reset clears the stop |
| Invalid settings | Reject invalid step, nonfinite phase, unsupported grid, negative coupling, wrong types, and overly coarse grid spacing |
| HTTP state | Separate sessions remain isolated; a rejected preparation preserves the prior experiment; foreign-origin POST and unlisted paths are rejected |

The resolution cases are `(n,L,dt) = (128,32,.01), (128,32,.005), (256,32,.005), (256,64,.005)`. Profiles are compared on coincident grid coordinates, without interpolation. The interacting references use `g = 20`. These tests demonstrate consistency on smooth, resolved states; they do not make a universal accuracy claim at the maximum allowed coupling or time step.

## Live browser checks

`uv run python -X utf8 -m scripts.browser_check` exercises the running HTTP server and actual page controls:

- Single-cloud release changes the trap state, grows RMS width, and changes the rendered field.
- Pause freezes simulation time; Step advances exactly one configured numerical step.
- Export downloads JSON; a fresh numerical replay matches the saved complex field (observed maximum error: `0.0`).
- Reset restores the initial rendered field and trapped state.
- An invalid grid/domain combination produces a useful error; correcting it successfully prepares another experiment.
- Two-cloud runs use the actual phase controls. Observed central densities near `t = 2`: `1.93e-2` for phase 0 and `1.45e-29` for phase pi. Exact pause time depends on the in-flight batch.
- Density/phase switching changes the canvas, and the model dialog opens and closes by keyboard.
- A cloud reaching the boundary stops playback, disables Run, and can be reset.
- Desktop (`1440px`), mobile (`390px`), and narrow mobile (`320px`) views render without horizontal page overflow.
- No browser page errors were reported.

Generated evidence lives in ignored `artifacts/`: `browser-report.json`, screenshots, and exported runs. Screenshots were visually inspected for labels, clipped content, and mobile layout. `docs/preview.png` is a representative desktop capture.

## Additional checks and limits

Ruff lint and formatting checks, JavaScript syntax checking, and `git diff --check` pass. The standalone replay command has also been run against a browser-downloaded export.

There is no lab-device validation, physical-unit calibration, 3D model validation, GPU backend, camera-image synthesis, or performance guarantee across machines. Browser testing used Chromium on this machine. The imaginary-time stopping criterion measures iteration convergence at a fixed preparation step; it does not replace preparation-step refinement for high-precision research.
