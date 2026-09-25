# Agent instructions

## Scope

Before implementing an experiment or changing the numerical model, read `PLAN.md` for the release scope, physical assumptions, and acceptance criteria. Keep implementation status and runnable instructions current in `README.md`.

## Physics and validation

- Drive visualizations and measurements from the numerical state. Label illustrative graphics separately.
- Define units, wavefunction normalization, and the interaction-coefficient convention before introducing physical parameters.
- Keep the solver independent from rendering. Simulation time steps must be independent of frame rate.
- Validate solver changes against the analytic references and convergence checks in `PLAN.md`. Real-time evolution must preserve norm through the integrator, not through per-step renormalization that conceals drift.
- Identify model limits in the relevant experiment UI, including the retained transverse confinement of an effective two-dimensional release.
- Report numerical verification and live browser verification separately. A successful build does not establish working controls or physically accurate results.

## Working conventions

- Keep source code, UI labels, and repository documentation in English; explain progress to the user in Traditional Chinese unless they request otherwise.
- Complete one usable experiment at a time, with its measurements and validation, before adding another.
- Keep local environments, credentials, and generated experiment output outside version control.
- Before committing, run `git diff --check` and checks appropriate to the changed behavior. For documentation-only changes, inspect links and consistency without inventing runtime test results.
- Commit descriptive, cohesive changes; preserve unrelated user work.
