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

Status: implemented; see `docs/VALIDATION.md` for measured evidence and limitations. Full three-dimensional evolution remains a future milestone.

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

## Later extensions

vortices and stirring; additional experiment protocols. These are separate from the first-release acceptance criteria.
