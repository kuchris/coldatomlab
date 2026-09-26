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

## v0.11: preparation variation in the two-mode lab

Keep the v0.10 Hamiltonian, fixed N and spectral solver unchanged. Add an
independent ensemble panel inside experiment 05. Each realization draws two
independent uniform offsets: initial phase in [-A,A] radians (wrapped modulo
2 pi) and bias in [-B,B] Hz. The drawn bias is constant throughout that run;
this is shot-to-shot technical variation, not continuous environmental noise.
Do not clip samples or silently change the manual experiment.

- Compare an ideal reference with 2–128 seeded preparations and 101 equally
  spaced physical times. Default to balanced N=40, J=U=delta=0, 500 ms, A=0.3 rad,
  B=1 Hz; offer an interacting hold and explicit copying of applied manual settings.
- Show individual coherence vectors, their complex average, average individual
  coherence magnitude, ensemble number probabilities and within/between-preparation
  number variance. Average density-matrix observables, never wavefunctions.
- At J=0 verify exact finite-sample factorization and the infinite uniform-ensemble
  guide C_ideal |sinc(A) sinc(2 pi B t)|. At J>0 mark that guide unavailable.
  Finite-sample departures from the guide are sampling effects, not solver error.
- Provide progress, pause/resume/cancel with completed-prefix results, manual-state
  isolation, JSON/CSV export and independent Python replay of settings, offsets,
  states, histories and aggregate observables. Preserve unavailable phase handling.
- Check zero-noise recovery, uniform RNG reproducibility/statistics, phase and bias
  sign/units, ensemble versus conditional coherence, total-variance decomposition,
  fixed probabilities at J=0, interacting/coupled cases, tampering, browser controls,
  responsive layout, in-dashboard persistence and extracted static packaging.
- Reference Gross (2012), section IV.3, for differential-energy-shift noise. Uniform
  distributions are declared teaching choices, not a measured noise spectrum or
  reconstruction of a published apparatus. No detector noise or atom loss is added.

Status: implemented. All 191 tests passed (40 preparation tests). Local and
extracted-static browser controls, exports/replay, manual isolation, dashboard
persistence and desktop/mobile layouts passed. See `docs/PREPARATION.md`.

## v0.12: ideal spin echo in the two-mode lab

Add a paired no-echo / echo comparison within experiment 05. Use exactly the
same seeded phase and static-bias offsets in both arms. Retain fixed N and the
existing Hz/ms, interaction and wavefunction conventions. Require J=0 during
both holds; reject nonzero J rather than silently changing it. The midpoint
pulse is the instantaneous mode swap S|n,N-n> = |N-n,n>, omitting only the
fixed-N global phase of a pi rotation. It is not an electromagnetic or finite
tunnelling pulse simulation. Hold evolution is exact in the diagonal occupation
basis and must not renormalize the state.

- Default balanced coherent N=40, U=0, initial phase spread=0, static bias
  half-range=2 Hz, duration=500 ms, 64 preparations, seed=17.
- Show paired ensemble-coherence histories and time-selectable individual
  coherence arrows. Include explicit before/after midpoint snapshots and a
  visible sequence. Plot 101 physical times plus a second midpoint sample;
  playback changes only the selected snapshot, never the physics.
- Offer initial-phase-spread and interacting examples. Initial phase variation
  is conjugated, not erased. The swap reverses the linear bias term but leaves
  U(n-N/2)^2 unchanged, so interaction dynamics are not time-reversed.
- Verify at U=0 and zero initial spread that echo refocuses any sampled static
  bias exactly at T. For J=0 the infinite uniform-ensemble guides use
  C_ideal |sinc(A) sinc(2 pi B t)| for no echo and
  C_ideal,echo |sinc(A) sinc(2 pi B (t-T))| after the pulse (time in seconds).
  Check nonzero U away from revival times and finite-sample complex averages.
- Preserve manual/preparation results and dashboard navigation. Support bounded
  settings, reproducible seeds, pause/resume/cancel completed prefixes,
  JSON/CSV exports and independent NumPy replay of both arms, pulse snapshots,
  histories and aggregate observables. Preserve undefined phase handling.
- Test pulse norm, inverse, population reversal, conjugated coherence, energy
  change, analytic fields, limits, zero variation, tampering and repeatability.
  Verify browser controls, slider/playback, mobile layout and static packaging.
- Reference Hahn (1950) for the echo concept and Gross (2012) section IV.3 for
  static differential-shift noise. Explicitly label the spatial mode swap and
  illustrative settings; no experimental apparatus reproduction is claimed.

Status: implemented. All 230 repository tests passed, including 39 echo tests.
Local and extracted-static browser checks passed for controls, both pulse
snapshots, timeline, exports/replay, preservation of existing experiments,
dashboard navigation and desktop/mobile layouts. See `docs/ECHO.md`.

## v0.13: finite tunnelling pulse

Extend experiment 05 with a separate paired comparison of no pulse, ideal
instantaneous swap, short finite pulse, nominal pi pulse and long finite pulse.
Use the same initial state and seeded static offsets in all five arms. Total
wall-clock duration T is identical: each rectangular finite pulse is centered
on T/2, with J=0 before and after it. Bias and U remain active during the pulse.
The Hamiltonian and Hz/ms conventions stay unchanged. The nominal resonant
noninteracting pi width is tau_pi=1/(4J) seconds, and the pulse propagator at
that width is i^N S. Keep its actual global phase; compare to ideal S using
phase-invariant fidelity rather than comparing raw amplitudes across arms.

- Controls: N, initial left fraction and phase, U, base bias, total duration,
  pulse J in [0.5,20] Hz, fractional duration error in [0,0.5], phase/bias
  spread, preparation count/seed. Widths are (1-error), 1 and (1+error) times
  tau_pi. Reject settings whose longest pulse is not shorter than T.
- Default balanced coherent N=40, U=base phase=base bias=phase spread=0,
  T=500 ms, pulse J=10 Hz, duration error=20%, bias spread=2 Hz, 32 preparations.
  Add a zero-bias all-left population-transfer preset and an interacting preset.
- Evolve arbitrary incoming normalized amplitudes with the existing float64
  spectral propagator. Do not normalize real-time states. Preserve legacy
  solver initialization and exports. Independent Python spectral replay must
  verify both finite and ideal paths, boundary states and all aggregates.
- Show actual population transfer and phase during the pulse, per-preparation
  vectors, ensemble coherence, and final mean fidelity against the ideal arm.
  Label conditional versus ensemble measurements. Sample the common time axis
  and every pulse boundary, including one-sided Hamiltonian/energy snapshots;
  retain both sides of the ideal discontinuity. Playback only inspects states.
- Verify arbitrary-state propagation, norm, piecewise energy, boundary
  continuity, rectangular-pulse Rabi transfer, pi global phase, finite-width
  errors, detuning, retained interactions, short-pulse trend, exact stage timing,
  zero duration error, seeded repeatability, invalid input and tampered exports.
- Preserve older panels and dashboard navigation; support pause/resume/cancel,
  completed-prefix JSON/CSV exports, static packaging, mobile and live browser
  controls. Keep fixed-orbital and finite-basis limits explicit; changing J is
  a prescribed two-mode control, not a simulated barrier ramp or microwave drive.
- Cite Gross (2012) for the coupled two-mode/spin framework and Hahn (1950)
  for echo context; derive the pulse calibration from this project's convention.

Status: implemented. All 270 repository tests passed, including 40 finite-pulse
tests. Local and extracted-static browser checks passed for five-arm controls,
timeline/zoom, actual pulse population transfer, exports/replay, preservation of
all earlier panels, navigation and desktop/mobile layouts. See `docs/PULSE.md`.

## v0.14: phase readout from atom counts

Add a separate experiment-05 panel: prepare a fixed-N pure state, isolated hold
(optional ideal midpoint echo), apply a controlled reference phase, mix, count.
Retain the existing Hz/ms, on-site U and normalization conventions. For analysis
phase alpha, apply c_n -> exp[-i(N-n)(alpha+pi/2)] c_n followed by the positive-J
rotation. Ideal pi/2 mixing gives z=2<NL>/N-1=Re(q exp[-i alpha]), where
q=2<aL†aR>/N. This explicitly fixes the sign and reference phase convention.

- Compare direct counting, instantaneous ideal mixing and a finite rectangular
  readout with J>0, duration (1+error)/(8J) seconds. U and bias stay active in
  the finite pulse. All arms start from the same state; finite readout adds its
  actual duration, whereas ideal readout takes zero time. The reference phase
  shift and optional echo remain prescribed instantaneous operations.
- Scan 8–32 equally spaced reference phases over one full period, with 16–4096
  independent ideal number measurements per setting/arm, seeded reproducibly.
  These are newly prepared copies, not repeated measurements of one cloud;
  omit technical preparation variation, detector effects, losses and 3D coupling.
- Infer offset, contrast and phase solely from count means using a first-harmonic
  fit. Show empirical standard errors, count histograms and a local delta-method
  phase standard error. Mask unresolved phase below a conservative 3-sigma
  amplitude threshold; label finite-pulse results as apparent fringe phase,
  with residuals and model-only bias shown separately. Never feed true q into
  the measured estimator. Partial scans have no fitted phase.
- Export complete incoming/output states, raw count histograms, recipes, seeds,
  statistics and fits in JSON, plus a CSV scan summary. Independent Python
  propagation and statistical replay verifies exports and rejects tampering.
- Verify analytic coherent-state binomial fringes, both quadratures/sign, Fock
  and vanishing coherence, interactions, echo, finite-pulse errors, norm, counting
  statistics, uncertainty scaling and full-state agreement. Check actual browser
  controls, cancellation, navigation, prior-panel isolation, mobile and extracted
  static packaging. Cite Gross (2012) for Ramsey readout; identify this as a fixed
  spatial two-mode teaching model, not reconstruction of a microwave apparatus.

Status: implemented. All 303 repository tests passed, including 33 readout
tests. Local and extracted-static browser checks passed for count inference,
controls, exports/replay, prior-panel isolation, navigation and desktop/mobile
layouts. See `docs/READOUT.md` for conventions, uncertainty limits and evidence.

## v0.15: repeated phase precision benchmark

Repeat complete v0.14 readout scans, drawing new ideal number measurements for
every setting, arm and repetition. Compare baseline, more atoms and more shots
with a common reference-phase grid and initial-state recipe. Reuse deterministic
output states only; every trial draws new counts and independently fits a phase.
All Hamiltonian, normalization, phase-gate and finite-pulse conventions stay as
in v0.14. This is an estimator benchmark, not new squeezing physics.

- Default balanced coherent N=20 versus 80, 64 versus 256 shots per setting,
  12 reference phases, 100 full-scan repetitions, phase=0.7 rad, zero hold/U/bias,
  readout J=10 Hz and zero duration error. Compare ideal and finite readout in
  all three cases. Offer a biased-pulse example and a zero-coherence example.
- Report per-case atom/shot budgets, resolved/attempted scans, circular bias and
  scatter, wrapped RMSE, RMS reported local phase SE, scatter/SE and the fraction
  within one SE of true phase. Label all phase statistics as conditional on
  resolved fits; never turn missing phase into zero. Separate noiseless readout
  bias from random counting variation. Plot repeated-estimate error histograms.
- For balanced coherent, noninteracting ideal readout only, show the large-shot
  prediction sqrt[3/(2 N K S)] for this full-period unweighted harmonic estimator.
  Validate N and S scaling. Do not label it the optimal local SQL or claim
  squeezing/quantum advantage. Pulse errors can leave narrow but biased estimates.
- Support 8–32 settings, 20–300 repetitions, 16–4096 shots, N up to 100 and an
  explicit 16-million-draw workload limit. Use deterministic non-overlapping LCG
  blocks across every case, arm and trial. Pause/cancel between complete paired
  repetitions; preserve completed prefixes and earlier experiment results.
- Export model states once plus every trial's count histograms, block seeds and
  fitted statistics in versioned JSON; CSV includes per-trial estimates and case
  settings. Independent Python replay checks propagation, RNG, fits and summary.
- Test statistical calibration across repeated scans, bias/RMSE separation,
  wrapping near pi, unresolved states, analytic scaling, reproducibility, invalid
  workloads and tampering. Verify live local/static controls, all-panel isolation,
  navigation and mobile layouts. Reference Gross et al. (2010) as motivation for
  later metrology comparisons, not an experimental result reproduced here.

Status: implemented. All 333 repository tests passed, including 30 precision
tests and 33 readout regression tests. Local and extracted-static browser
checks passed for repeated scans, independent replay, resource comparisons,
controls, prior-panel isolation and desktop/mobile layouts. See `docs/PRECISION.md`.

## Later extensions

Dashboard interface: implemented with a light navigation shell, searchable experiment cards, grid/list views and direct workspace/measurement/camera links. Template illustrations are explicitly labeled; selecting a template stages its experiment type for preparation. Navigation preserves the solver session, pending settings and pinned comparisons. Desktop and mobile browser evidence is recorded in `docs/VALIDATION.md`. The dashboard now also links to the independent three-dimensional single-cloud experiment.

vortices and stirring; additional experiment protocols. These are separate from the first-release acceptance criteria.
