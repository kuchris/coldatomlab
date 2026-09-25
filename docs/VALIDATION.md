# Validation record

Validated locally on Windows with Python 3.12, NumPy 2.5.3, and Playwright Chromium. Dependency versions are captured in `uv.lock`. These checks validate the stated reference cases, not every allowed parameter combination or a physical apparatus.

## Numerical and HTTP checks

`uv run pytest -q`: **66 passed**. The original 42 checks remain in place alongside 18 camera checks, one camera HTTP workflow check, and five reduced-ballistic benchmark test cases, described below.

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

## Sequence milestone (v0.2)

The added numerical checks cover:

- Actual splitting from one trapped ground state. In a noninteracting reference with a 4-unit ramp, the central density falls below 1% of the peak; left/right populations stay symmetric, norm is preserved to `1e-10`, and the sequence stops on its exact configured step.
- Fast versus slow preparation at the same final potential. A ramp of `0.2` leaves energy about `9.586`, versus `4.895` for a ramp of `4`, in units of `hbar*omega0`. This is one controlled noninteracting comparison, not a universal monotonicity claim.
- Hold-phase accumulation for bias `−0.5`, `0`, and `+0.5` over one time unit. The measured mirror phase is approximately `+0.483`, `0`, and `−0.483` rad, within `0.03` rad of the isolated-arm approximation. Reversing the bias reverses phase and population imbalance.
- Driven evolution with `g=20`, ramp 1, hold 0.5, expansion 0.5: time steps `0.02`, `0.01`, and `0.005` exhibit decreasing density error; the medium/fine error is below 0.35 of the coarse/fine error. Grid and domain refinements at coincident coordinates keep relative density L2 differences below 1%.
- A known sinusoidal profile returns spacing 2 and contrast 0.6. Single-peak, flat, and low-contrast profiles return unavailable estimates.
- Rounded timing, zero-length hold, partial and complete replay, comparison-bundle verification, manual-release rejection in an automatic sequence, and invalid timing/barrier configurations.

`scripts/sequence_browser_check.py` additionally verifies the actual timeline, potential overlay, pause during Hold, automatic release at step 300, and exact completion at step 450 for a `2 / 1 / 1.5` sequence with `dt=0.01`. Replacing the hold bias `+0.5` with `−0.5` yields final left fractions about `0.5263` and `0.4737`, and opposite mirror phases. The pinned reference stays unchanged through preparation, playback, and reset. Both downloaded records replay with observed maximum complex-field error `0.0`.

The comparison workflow also passes invalid-duration recovery and 390px/320px mobile overflow checks, with no reported browser page errors. New evidence is saved to ignored `artifacts/sequence-browser-report.json`, `sequence-comparison.json`, and `sequence-*.png`. The phase and contrast diagnostics are labeled approximations; these checks do not establish many-body coherence, experimental metrology accuracy, or 3D validity.

## Laboratory units milestone (v0.3)

The physical-unit checks independently integrate the axial Gaussian density squared and recover the derived coupling, including its N and sqrt(fz) scaling and independence from f0. For Rb-87, N=200, as=5.3 nm, f0=20 Hz and fz=2000 Hz, the scales are a0=2.41143618 um, time=7.95774715 ms and g=22.03687574. A noninteracting released cloud agrees with the SI analytic expansion width to relative tolerance 2e-5; integrated planar number density recovers N to 1e-8.

Tests cover invalid physical values, integer atom count, excessive coupling rejection, custom mass, authoritative server-derived coupling, old exports, and exact physical replay. Applicability checks distinguish a well-separated default case, a marginal fz=200 Hz case and an outside-regime fz=20 Hz case, and use the actual field density.

All four guided sequences complete without boundary stopping and preserve norm to 1e-10. At the end of Hold, biases 0, +10 Hz and -10 Hz over 7.957747 ms give mirror phases approximately 0, -0.48103 and +0.48103 rad. Doubling the +10 Hz hold gives approximately -0.95595 rad. These are interacting, deterministic model results, not experimental calibration. The final positive/negative runs have complementary left fractions about 0.530434 and 0.469566.

For the full positive-bias example (split 4, hold 1, expand 2), relative density L2 differences are 3.99e-5 for dt=0.01 versus 0.005, 5.78e-7 for grid 128 versus 256 at L=32, and 5.75e-7 for L=32 versus L=64 at matched spacing. Spatial comparisons use coincident coordinates. These values concern this example; they do not validate every input combination or the fixed imaginary-time preparation step.

`scripts/physical_browser_check.py` exercises laboratory controls, derived coupling, invalid-input recovery, ms stepping/pause, actual density/potential plot conversion, complete positive/negative runs, immutable references and downloaded comparison replay. Both observed field replay errors are 0.0. A changed reference frequency verifies each run uses its own length/time factors in comparison plots. Reset restores physical parameters; weak axial confinement displays the expected warning; mixed comparisons use dimensionless axes. Switching back from physical units retains the derived coupling and accepts arbitrary converted values instead of failing HTML step validation. A targeted browser check also prepares successfully at the minimum dt and trap-frequency ratio before and after a unit-mode round trip.

Desktop and 390px/320px views, the linked reference page and browser console checks pass. A final visual pass checks the physical contour energies, millisecond comparison caption and narrow layout. Evidence is in ignored `artifacts/physical-browser-report.json`, `physical-comparison.json`, and screenshots. `docs/preview.png` shows the actual physical sequence during Hold. The original expansion/interference browser suite and the v0.2 sequence comparison suite also pass.

## Absorption camera milestone (v0.4)

Numerical tests cover the saturated Beer–Lambert inversion for optical depths 0–100 and saturation 0.001–10, exact ideal-camera recovery of column density/ROI moments/fringes, Gaussian-PSF broadening and absorption-deficit conservation, nonperiodic optical boundaries, and loss of resolved fringes under optical blur/coarse pixels. Native-grid noiseless inversion agrees to absolute density tolerance 1e-12 and measured moments to 1e-10.

Photon-only reference frames have mean and variance consistent with the expected Poisson rate over 16,384 pixels (3% mean / 5% variance tolerances). Atom/reference exposures have negligible sampled correlation before dark subtraction. Read-noise tests recover the dark variance, the additional two read-noise contributions after subtraction, and the shared-dark covariance. Identical seed/settings/source reproduce all frames; a new seed changes counts; doubling exposure doubles expected counts and improves normalized counting noise.

Invalid counts, small ROIs, unresolved strips, invalid camera parameters and unsupported species/modes have explicit tests. Capture preserves the entire source export. Raw-frame or coordinate tampering fails camera replay; an ordinary and a paired camera export both reproduce the source and camera. The HTTP capture route preserves the session through errors and successful acquisitions.

The actual Positive bias physical sequence gives ROI N=197.555, RMS x=8.7952 um and fine-grid fringe spacing=10.2486 um at the selected aperture. For FWHM 0, 2, 4 and 8 um without noise at native pixel pitch, profile contrast is about 0.841, 0.713, 0.473 and unavailable respectively. The 4 um image estimates N=195.181 and RMS x=8.8719 um, exposing blur/inversion bias rather than correcting it with known truth. These are controlled simulation values, not laboratory measurements or a universal resolution criterion.

`scripts/camera_browser_check.py` completes that sequence through the UI, acquires ideal/blurred/coarse/noisy exposures, checks fixed source time, pins an immutable image, verifies repeatable and changed seeds, and downloads a comparison. Both source replay errors are 0.0 and both complete camera records regenerate exactly. Low-count masks and ROI errors recover without losing the source; reset preserves the captured snapshot and displays a stale notice. Clearing the reference restores single-image export. Desktop and 390px/320px layouts, the imaging-paper page and console checks pass.

Evidence is in ignored `artifacts/camera-browser-report.json`, `camera-comparison.json`, `camera-single.json`, and screenshots. `docs/camera-preview.png` shows the actual 4 um FWHM comparison. The original single/two-cloud, sequence and physical-unit browser workflows also pass. Numerical evidence and browser evidence are separate; none validates omitted recoil, pumping, multilevel scattering or coherent optical propagation.

## Dashboard interface

The dashboard browser check covers all three template selections, staged settings without replacing the source state, search and no-results recovery, grid/list switching, model dialog, direct workspace links, browser Back, measurements/camera navigation, running-state guards, and 390px/320px layouts. Navigation preserves the complete solver state and pinned run. The camera browser check additionally verifies that both captured and pinned image records survive library/camera navigation unchanged. Re-selecting the current navigation item closes the mobile menu; Escape returns focus to its toggle.

All five browser workflows pass against the dashboard: library/navigation, original single/two-cloud, sequence, physical units and camera. The original workflow initially exceeded its five-second assertion timeout when all four numerical browser suites competed for the server lock; its isolated rerun passed. These are browser checks using the existing solver, not new 3D physics validation. Screenshots were inspected for desktop and mobile layout. Evidence is saved to ignored `artifacts/dashboard-browser-report.json` and `dashboard-*.png`; `docs/dashboard-preview.png` is the homepage capture.

## Shin Fig. 2 reduced benchmark

The five benchmark test cases independently check the free Gaussian analytic field, norm preservation without evolution renormalization, full-step/two-half-step equivalence, recovery of two synthetic profiles with different periods/centers/phases, rejection of a nonfringing profile, and grid/domain refinement plus width-sensitivity boundary control. Every reported case has analytic field L2 error below `1e-7`, norm error below `1e-12`, and edge probability below `1e-10`. Numerical refinements change fitted period by less than `1e-5 um`. The independent fitter tests do not use the paper's measured period.

The actual benchmark gives fitted spacing 40.057375321 um versus the reported 41.5 um, a -3.476204% discrepancy. This is not an experimental pass/fail test. See `docs/BENCHMARK.md` for the distinct quoted theory, recomputation, model assumptions and fit residual.

The live benchmark browser workflow verifies the calculated values, five-row source comparison, JSON download, refinement panel, direct link, 503 error/retry recovery and unchanged workspace/session/pinned reference. Desktop and 390px/320px layouts have no page errors or horizontal page overflow; tables intentionally scroll. The existing dashboard navigation workflow also passes. The exported scientific figure was rendered with Matplotlib and visually inspected separately from the browser. Evidence is in ignored `artifacts/shin-benchmark.json`, `shin-browser-export.json`, `shin-benchmark.png`, `benchmark-browser-report.json` and `benchmark-*.png`.

## Additional checks and limits

Ruff lint and formatting checks, JavaScript syntax checking, and `git diff --check` pass. The standalone replay command has also been run against a browser-downloaded export.

There is no lab-device validation, physical-unit calibration, 3D model validation, GPU backend, experimental camera calibration, or performance guarantee across machines. Browser testing used Chromium on this machine. The imaginary-time stopping criterion measures iteration convergence at a fixed preparation step; it does not replace preparation-step refinement for high-precision research.
