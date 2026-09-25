# Cold Atom Lab implementation plan

## Intended outcome

Build a local interactive experiment that lets a user prepare, release, and measure a Bose–Einstein condensate, then explore interference between two coherent clouds. The first release must run end to end in a browser with a real numerical solver.

## Model and conventions

- Use an effective two-dimensional Gross–Pitaevskii equation, with assumptions and units stated in the interface and documentation.
- Releasing the cloud removes the in-plane trap while retaining tight transverse confinement. Full three-dimensional free expansion requires a different model.
- Begin with dimensionless variables and wavefunction normalization integral |psi|^2 dx dy = 1. The interaction coefficient includes the chosen particle-number convention.
- Use imaginary-time propagation for trapped stationary states and split-step Fourier evolution for real time.
- Distinguish a coherent split condensate with a controlled relative phase from independently prepared clouds.
- The ideal two-cloud experiment uses an explicitly defined, normalized superposition of separated wave packets. A separate sequence experiment dynamically raises a barrier to split a single trapped condensate.
- Treat phase as a model diagnostic; mask it where density is too small for meaningful interpretation.
- Explain periodic FFT boundaries and choose a domain and duration that keep expanding clouds away from boundary artifacts.
- Monitor boundary density and warn or stop when the cloud approaches the periodic domain edges.
- Do not claim to simulate laser cooling, condensate formation, arbitrary finite temperature, or strongly correlated many-body dynamics.

## Milestones

First-release status: implemented and validated. See `docs/VALIDATION.md` for the reference cases and browser evidence; later extensions below remain outside this release.

1. Numerical core: grid, normalization, trapped state, release, density and width diagnostics.
2. Interactive single-cloud experiment: prepare, run, pause, reset, adjust trap parameters, inspect density and a density cross-section.
3. Coherent two-cloud experiment: vary separation and relative phase; release and compare interference patterns.
4. Measurements and export: record widths, norm, energy where appropriate, parameters, and simulation time; export reproducible results.
5. Browser validation and documentation: verify controls, parameter changes, recovery from invalid settings, and repeatable experiments.

## Acceptance evidence

- Noninteracting harmonic-trap ground-state density and energy agree with the analytic reference within documented numerical tolerances.
- Noninteracting Gaussian expansion agrees with its analytic width evolution.
- Real-time evolution conserves norm; time-independent, closed-system runs exhibit convergent energy error as the time step is reduced.
- Real-time evolution must not renormalize each step to conceal norm drift. Imaginary-time preparation uses normalization explicitly.
- Representative observables converge under smaller time steps, finer grids, and larger domains. Norm conservation alone is not proof of accuracy.
- Symmetric coherent clouds with relative phase zero and pi produce the expected central constructive and destructive interference in the suitable noninteracting reference case.
- Browser controls change the actual simulated state; pause holds simulation time, reset restores the initial state, and exported metadata reproduces the experiment.
- Report numerical checks and live browser checks separately.

## Second milestone: 2D split / hold / release

The next milestone remains two-dimensional. Implement a real time-dependent Gaussian barrier, a finite-duration left/right bias, automatic release, and a fixed expansion duration, starting from the same trapped ground state as the single-cloud experiment.

Acceptance criteria:

- A visible timeline follows actual solver steps and reports rounded stage boundaries. Preparation, pause, single-step, reset, automatic release, boundary stopping, and exact end-of-sequence stopping remain reproducible.
- Plot the applied potential and optional potential contours over the field. Expose barrier height/width, split time, hold time, expansion time, and hold bias.
- Report left/right population fractions, a clearly labeled mirror-weighted phase diagnostic, and conservative fringe-spacing/profile-contrast estimates with an unavailable state for unresolved patterns.
- Pin one immutable reference run, prepare a second run, and compare profiles, width histories, settings, and measurements on shared axes. Export both complete records and replay both.
- Validate actual cloud splitting, lower excitation for a controlled slower ramp, sign and approximate magnitude of bias-induced phase, norm preservation, dynamic time-step/grid/domain convergence, partial and complete replay, and invalid-sequence handling.
- Exercise the actual browser timeline and comparison workflows, including mobile layouts. Preserve the original single/two-cloud tests.

Status: implemented; see `docs/VALIDATION.md` for measured evidence and limitations. The separate fifth milestone supplies full three-dimensional single-cloud evolution.

## Third milestone: laboratory scales and literature-backed examples

- Keep the canonical norm-one solver and old dimensionless exports; accept validated physical species/mass, N, scattering length, f0 and fz and derive g server-side.
- Convert controls, axes, density, time, widths, energy, protocol and comparisons consistently. Preserve each reference run's scales and distinguish mixed-unit comparisons.
- Show transparent conservative quasi-2D/diluteness checks with unknown thermal validity explicitly stated.
- Supply four tested physical split/hold/release examples for zero/reversed bias and longer hold; identify them as teaching choices, not reproductions of a paper.
- Link established physics literature to the precise formulas, approximations and experimental inspiration used.
- Verify SI analytic limits, axial reduction, parameter scaling, invalid-input recovery, replay/backward compatibility, actual browser workflows and responsive layouts.

Status: implemented and verified. Numerical and browser evidence is recorded in `docs/VALIDATION.md`; physical derivation and paper provenance are in `docs/PHYSICAL_UNITS.md`.

## Fourth milestone: virtual absorption imaging

- Acquire immutable camera snapshots from a prepared Rb-87 physical run, looking along the retained axial direction. Do not modify the GPE state.
- Apply the ideal two-level saturation-corrected transmission law, Gaussian intensity PSF, pixel-area integration, independent photon noise and detector read noise in that order. Preserve raw atom/reference/dark frames and deterministic seeds.
- Recover column density from frames; compare ROI atom number, RMS widths and strip fringe spacing/contrast against model truth. Report invalid pixels, insufficient signal, recoil/model limits and unresolved fringes explicitly. Do not use model density to mask or fit the camera estimates.
- Let users vary pixel size, PSF FWHM, pulse/intensity and noise, pin a captured reference and export/replay both camera and source simulation.
- Reference Ketterle–Durfee–Stamper-Kurn and Reinaudi et al.; distinguish adopted equations from simplified optics and omitted experimental effects.
- Validate ideal inversion, blur/pixel response, noise statistics, ROI/invalid-data behavior, replay, preservation of solver state, actual browser operations and mobile layouts.

Status: implemented and verified. See `docs/IMAGING.md` for model/provenance and `docs/VALIDATION.md` for numerical and browser evidence.

## Paper benchmark: Shin et al., Fig. 2

Implement a separate, reproducible comparison of the reported Na-23 fringe spacing (41.5 um after 30 ms expansion from 13 um separation). Use a normalized, noninteracting coherent Gaussian pair and free Fourier propagation of its separable x component. This is a reduced ballistic benchmark, not the paper's interacting 3D splitting experiment or its absorption camera. The initial packet width is a declared harmonic-ground-state surrogate derived from 615 Hz, not a measured condensate width.

Compare a Gaussian-envelope sinusoidal fit of the numerical line density with the exact finite-width Gaussian prediction, the point-source prediction recomputed from rounded paper inputs, the paper's quoted prediction (39.8 um), and the reported measurement. Keep numerical error separate from discrepancy with experiment; no experimental confidence or agreement test is possible without uncertainty/raw data. Verify norm, analytic field agreement, grid/domain refinement, two-half-step equivalence, and width sensitivity without tuning to the measurement. Provide an English benchmark page, source/assumption map, downloadable report and runnable CLI. Preserve the existing experiments and their sessions.

Status: implemented and verified. See `docs/BENCHMARK.md` for method, values and limits; `docs/SHIN_REFERENCE.md` for the source audit; and `docs/VALIDATION.md` for numerical and browser evidence.

## Fifth milestone: interacting 3D single-cloud expansion

- Add an independent norm-one 3D GPE solver, with x/y/z array order, harmonic preparation and complete three-axis release. Use `a0=sqrt(hbar/(m omega0))`, time `1/omega0`, and `g3D=4 pi N as/a0`. Rb-87 physical controls and a zero-interaction analytic reference must be explicit. No retained axial confinement applies in this experiment.
- Separate numerical state, snapshot projections and rendering. Real-time Strang split-step Fourier evolution must preserve norm without renormalization. Imaginary-time preparation must report its step, convergence and iteration count. Finite periodic domains must warn/stop near boundaries.
- Benchmark CPU time and array memory; use a bounded grid suitable for local operation, and retain grid/domain/time/preparation-step refinement controls for verification.
- Provide a rotatable isodensity surface derived from the numerical volume, orthogonal central slices and three column-density projections. Label any coarsened rendering grid, selected isolevel, units and projected axes. No sodium/Rb camera inference from these ideal projections.
- Complete Prepare / Release / Run / Pause / Step / Reset, widths x/y/z, aspect ratios, norm, energy and boundary monitoring. Preserve separate 2D state through navigation. Export the complete final complex wavefunction and reconstruct it via the existing replay command.
- Validate 3D noninteracting ground-state energy/density and released Gaussian widths, interacting stationary-state residual, norm, time/space/domain/preparation-step refinement, projection integrals, exact release/replay, invalid-input recovery and boundary stopping.
- Compare a declared strong-interaction case against Castin-Dum Thomas-Fermi scaling, showing all three widths/aspect ratios and deviations. Distinguish the approximation's finite-kinetic-energy error from numerical error. Also show when the TF approximation is not applicable; no claim of experimental reproduction.
- Exercise actual 3D browser rendering, rotation, selectors, controls, export/replay, errors, navigation and mobile layouts. Report this separately from numerical checks.

Status: implemented and verified. See `docs/MODEL3D.md` for numerical convergence, TF comparison, performance, replay and browser evidence, and `docs/3D_REFERENCE.md` for the primary-source audit.

## Browser GPU execution

Implement an optional WebGPU backend for the existing 3D single-cloud experiment, with all preparation and real-time field evolution in the browser. Preserve the double-precision CPU reference. Keep physical conventions, full release and no real-time renormalization; label WebGPU complex-f32 explicitly. A radix-two FFT supports 32/64/128 grids; loading a GPU preset must explicitly select its supported grid. Do not silently reinterpret 96 as another grid.

Acceptance: independently test GPU FFT against a complex-field oracle and round-trip fields; fresh Gaussian and interacting calculations against CPU reference at identical settings; target RMS/aspect differences below 0.5% and norm drift below 0.1% for demonstrated runs. Verify time/preparation-step refinement, boundary stopping, real browser controls, backend switching, device/unavailable errors, GPU export and documented CPU reference verification. Report actual adapter identity, cold setup and fresh computation separately, with no cache-based speedup claims. WebGPU must need no simulation API calls; provide a static-shareable 3D entry page. Do not deploy publicly without an explicit request.

Status: implemented and verified on hardware Chrome/Edge. See `docs/WEBGPU.md` for precision, fresh-computation timing, independent CPU/FFT comparisons, browser checks, and standalone packaging.

## v0.7: three-dimensional coherent interferometer

Implement two distinct WebGPU and float64 CPU modes: a normalized, noninteracting coherent Gaussian pair with a controlled right-minus-left phase, and a single interacting condensate dynamically split by a Gaussian barrier, held with a smooth left/right bias, then released on all axes. Use the existing norm-one units and g convention. This is a Shin et al. (PRL 92, 050405, 2004)-inspired teaching protocol, not an apparatus reconstruction or a model of independently formed condensates.

- Round each stage duration to an integer step count, expose the actual timeline, evaluate the driven potential at step midpoints, and stop at the exact sequence end. Manual release is available only for the original single-cloud mode. Reset and exports must preserve the whole protocol.
- Display the actual applied axial potential, x line density, left/right populations, mirror-weighted phase and coherence, and conservative resolved fringe spacing/contrast. Unavailable measurements must remain unavailable, not be filled from theory. Compare immutable pinned runs on shared physical axes.
- Verify Gaussian fields against their finite-width analytic free solution, zero/pi central interference, phase-controlled fringe displacement, bias sign, physical splitting, time/grid/domain refinement and CPU/GPU field/observable comparisons. Preserve real-time norm without normalization; retain boundary and float32 drift stops.
- Exercise actual browser preparation, timeline, pause/step/reset, controls, projections, pin/export/replay, error recovery and mobile layout. Update static packaging and English model/provenance documentation. Report numerical and browser evidence separately.

Status: implemented; numerical and browser evidence is recorded in `docs/INTERFEROMETER3D.md`. The default 64³ contrast and mirror-phase estimates remain more grid-sensitive than RMS widths, with measured refinement differences and acceptance thresholds disclosed there.

## v0.8: stable controls and three-axis absorption camera

- Keep Experiment, Compute engine and Reference example above variable experiment controls in both 3D entry pages. Label 2D CPU and 3D WebGPU dashboard entries explicitly.
- Acquire immutable x/y/z line-of-sight projections from the actual 3D state, without evolving or modifying it. Preserve detector-plane axes and physical normalization N/a0². Run acquisition in browser JavaScript so the standalone WebGPU bundle remains server-independent.
- Apply the documented ideal Rb-87 saturation-corrected transmission law, Gaussian intensity PSF, physical pixel integration, seeded independent Poisson photon and Gaussian read noise, and atom/reference/dark-frame inversion. Preserve invalid and negative estimates, source identity/time, raw frames and settings. Report optical-depth, unresolved-PSF and omitted recoil limits.
- Estimate fringe phase, period and contrast from the observed profile alone, using a declared envelope/carrier fit and rejection gates. Fit the ideal projected density separately for comparison; never use source phase or density to seed or constrain the image fit. Distinguish this image phase from the wavefunction's mirror diagnostic, and report unavailable when projection, resolution, noise or model mismatch prevents a reliable fit.
- Support paused capture, ideal/noisy comparisons, immutable pin/export, stale-source notices and reproducible source/frame verification. Verify axis orientation, projection normalization, ideal inversion, PSF/binning, seeded noise statistics, blind synthetic phase recovery, unresolved cases, CPU/browser consistency and complete browser workflows on both entry pages and the static package.

Status: implemented. See `docs/IMAGING3D.md` for model conventions, primary references, numerical checks, browser workflows and standalone packaging evidence.

## v0.9: automated interferometer scans

Deliver an independent browser WebGPU scan workspace without changing the manually prepared cloud. Complete known pair-phase calibration first, then interacting hold-time and hold-bias scans using the declared Rb-87 teaching protocols. Keep the existing GPE and camera conventions; do not fit source phase into camera measurements.

- Provide bounded point ranges, explicit fixed physical/numerical/camera settings, repeated seeded camera exposures, progress, pause/resume/cancel, partial results and visible failure counts. Scan computation uses fresh numerical evolution for each parameter/grid; repeated camera exposures reuse the frozen field and must be labeled as detector noise only.
- Plot input versus recovered circular phase with detector-noise scatter, ideal image fit and declared input/isolated-well guide. Report wrapped phase differences, failures, contrast and period; no artificial phase unwrapping through missing points or claims of many-body phase fluctuations.
- Offer matched 64³/128³ runs at the same box/time/physical settings; compare widths/norm and ideal-image phase separately from noisy estimates. Identify estimator/pixel sampling as part of image-phase grid sensitivity; two grids are not a convergence proof.
- Export English CSV summary and a versioned compact JSON containing recipes, actual stage times, source projections/diagnostics, raw camera frames, fits and seeds. Verify source projection/width agreement against independently rerun float64 fields and camera/statistical regeneration in Python. State precisely what compact exports verify; they do not retain full complex GPU fields.
- Reference Shin et al. (2004) for controlled phase evolution and existing absorption-imaging sources; distinguish teaching protocols, image-fit bias, detector noise and numerical grid effects from a reproduction of experimental data.
- Validate circular statistics, invalid/unresolved data, recipe integrity, noise repeatability, pair calibration, interacting bias sign/hold response, refinement, tampering, resource cleanup, manual-state isolation, actual browser controls, responsive layouts and extracted standalone packaging. Keep README and model/reference evidence current.

Status: implemented and verified. See `docs/SCANS3D.md` for recipes, statistics, compact-export verification scope, literature, numerical evidence and live browser checks.

## v0.10: two-mode quantum coherence lab

Implement a separate fixed-N, two-site Bose-Hubbard experiment in the browser. This
is a finite many-body model, not a 3D GPE upgrade or a reproduction of an apparatus.
Use the occupation basis |n_L, N-n_L>, sum |c_n|^2 = 1, and
H/h = -J(a_L†a_R + a_R†a_L) + U(n_L-N/2)^2 - delta(n_L-N/2).
J, U and delta are in Hz; positive delta raises the right mode. U is the on-site
pair coefficient in U/2 [n_L(n_L-1)+n_R(n_R-1)], with its constant removed.
Time is displayed in ms; propagation is exp(-i 2 pi (H/h) t_seconds).

- Provide coherent binomial, number-narrow Gaussian and fixed-occupation initial
  states; compare tunnelling and isolated interacting holds. Gaussian preparation
  is prescribed, not simulated adiabatic squeezing. Fixed spatial modes, fixed N,
  no thermal mixture, loss, camera noise or 3D coupling.
- Use float64 spectral unitary propagation with a checked real-symmetric browser
  eigensolver; no real-time renormalization. Rendering cadence does not set physics.
- Plot occupation probabilities, mean populations, first-order coherence and
  history. Seeded ideal number measurements represent independent preparations at
  one time, not repeated nondestructive measurements on one cloud. Mask undefined
  phase and number-noise ratios. Do not equate number narrowing with entanglement.
- Support prepare/run/pause/step/reset, immutable pin comparison, JSON/CSV export,
  English explanatory text, desktop/mobile and a server-independent static package.
- Validate binomial moments, analytic noninteracting tunnelling, isolated-well
  phase sign, interacting collapse/revival, frozen number probabilities at J=0,
  norm/energy and spectral residuals, time subdivision, independent NumPy eigensolver
  agreement, measurement statistics/seeds and tamper-detecting replay. Target
  complex-state L2 < 5e-8 and norm drift < 1e-9 in validated cases. Explain that
  numerical accuracy within two modes does not establish spatial-model validity.
- Use Esteve et al. (2008) for number/phase measurement motivation, Gross (2012)
  for the fixed-N spin description and Smerzi et al. (1997) for Josephson context;
  state explicitly which physics is demonstrated rather than experimentally fitted.

Status: implemented and verified. The dedicated numerical suite has 39 passing
tests; the full suite has 151. Local-app and extracted-static browser controls,
independent export replay, desktop/mobile layouts and existing dashboard
regressions passed. See `docs/TWOMODE.md` for conventions, evidence and limitations.

## Later extensions

Dashboard interface: implemented with a light navigation shell, searchable experiment cards, grid/list views and direct workspace/measurement/camera links. Template illustrations are explicitly labeled; selecting a template stages its experiment type for preparation. Navigation preserves the solver session, pending settings and pinned comparisons. Desktop and mobile browser evidence is recorded in `docs/VALIDATION.md`. The dashboard now also links to the independent three-dimensional single-cloud experiment.

vortices and stirring; additional experiment protocols. These are separate from the first-release acceptance criteria.
