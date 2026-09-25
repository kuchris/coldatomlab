# Cold Atom Lab

An interactive virtual laboratory for exploring Bose–Einstein condensate (BEC) expansion and matter-wave interference.

![Two coherent clouds in the local experiment interface](docs/preview.png)

## Run locally

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer. From this repository:

```powershell
uv sync
uv run python -m coldatomlab.server
```

Open **http://127.0.0.1:8765**. Stop the server with `Ctrl+C`. Use `--port 8766` if the default port is already occupied. The application runs locally without an account, API key, frontend build, or remote assets.

## Try an experiment

**Expansion:** the initial screen prepares a trapped condensate. Click **Release trap**, then **Run**. Watch the density spread and the RMS widths grow. **Pause** holds the state after the current batch finishes; **Step** advances one numerical step. **Reset** returns to the prepared initial state and restores its settings.

**Interference:** select **Two-cloud interference**, set interaction strength to **0**, and click **Prepare experiment**. These packets start released. Run to approximately `t = 2`, then pause. Prepare again with **Opposite · π** and compare the central density dip to the in-phase case. Try separation or interaction changes to explore different dynamics.

Use **Density / Phase** to switch the observation view. Parameter edits remain pending until **Prepare experiment** is clicked; preparation replaces the current run. Grid, domain size, and time step are under **Numerical resolution**. Numerical warnings stop playback before the cloud significantly reaches the periodic boundary region.

The English interface provides density and masked phase maps, central density profiles, RMS width histories, norm, energy, and boundary population. It adapts to desktop and narrow mobile layouts.

## Save and reproduce

Pause and click **Export run** to download a JSON record containing parameters, preparation metadata, the release protocol, diagnostics, and the final complex wavefunction.

```powershell
uv run python -m coldatomlab.replay "path/to/coldatomlab-single-100.json"
```

Replay computes the experiment again and reports the maximum difference from the saved wavefunction. It exits with an error for a discrepancy above `1e-8`.

## Validate

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

With the server running in another terminal:

```powershell
uv run playwright install chromium
uv run python -X utf8 -m scripts.browser_check
```

Browser checks exercise the actual controls, download and replay a run, compare interference phases, verify invalid-setting recovery and boundary stopping, and capture desktop/mobile screenshots. Reports and generated experiment files go to ignored `artifacts/`. See [validation evidence](docs/VALIDATION.md) for tested cases and limits.

## Model scope

This is an effective two-dimensional Gross–Pitaevskii model of an already prepared, dilute, weakly interacting condensate. In-plane release retains tight transverse confinement. The two-cloud initial state is an ideal coherent Gaussian pair. Units are dimensionless; atom species and physical trap scales are not assigned.

Laser cooling, condensation formation, a thermal component, full 3D expansion, and camera imaging are outside this release. Density and phase are model diagnostics, not laboratory images. Numerical accuracy depends on the chosen grid, step, and domain; passing reference cases does not validate every parameter combination.

See [the model and conventions](docs/MODEL.md), [implementation plan](PLAN.md), and [agent guidance](AGENTS.md).

## References

- [BEC interference: Nobel Prize educational material](https://www.nobelprize.org/prizes/physics/2001/9850-the-nobel-prize-in-physics-2001-2001-2/)
- [Numerical Solution of the Gross-Pitaevskii Equation for Bose-Einstein Condensation](https://arxiv.org/abs/cond-mat/0303239)
- [Split-step Fourier methods for the Gross-Pitaevskii equation](https://arxiv.org/abs/cond-mat/0411154)
