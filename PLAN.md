# Cold Atom Lab implementation plan

## Intended outcome

Build a local interactive experiment that lets a user prepare, release, and measure a Bose–Einstein condensate, then explore interference between two coherent clouds. The first release must run end to end in a browser with a real numerical solver.

## Model and conventions

- Use an effective two-dimensional Gross–Pitaevskii equation, with assumptions and units stated in the interface and documentation.
- Releasing the cloud removes the in-plane trap while retaining tight transverse confinement. Full three-dimensional free expansion requires a different model.
- Begin with dimensionless variables and wavefunction normalization integral |psi|^2 dx dy = 1. The interaction coefficient includes the chosen particle-number convention.
- Use imaginary-time propagation for trapped stationary states and split-step Fourier evolution for real time.
- Distinguish a coherent split condensate with a controlled relative phase from independently prepared clouds.
- The first two-cloud experiment uses an explicitly defined, normalized superposition of separated wave packets. Dynamically raising a barrier to split a trapped condensate is a later extension.
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

## Later extensions

Virtual absorption imaging with an explicitly defined projection and camera model, finite resolution and noise; vortices and stirring; physical-unit presets; additional experiment protocols. These are separate from the first-release acceptance criteria.
