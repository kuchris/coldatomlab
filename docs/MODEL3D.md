# Interacting three-dimensional expansion

The v0.5 experiment evolves an independent norm-one complex field on a Cartesian 3D grid. It describes the coherent zero-temperature mean-field dynamics of one repulsive Rb-87 condensate. It does not model cooling, condensate formation, thermal atoms, losses, calibrated imaging or an interacting splitting experiment. The reference is theoretical, not an experimental data reproduction.

## Conventions

With `omega0=2*pi*f0`, `a0=sqrt(hbar/(m*omega0))`, `tau=omega0*t` and `X_i=r_i/a0`:

```text
integral |psi|^2 dX dY dZ = 1
g3D = 4*pi*N*a_s/a0                 (N-1 approximated by N)
i dpsi/dtau = [-1/2 Laplacian + V + g3D |psi|^2] psi
V = 1/2 sum_i (f_i/f0)^2 X_i^2      before release
V = 0                             after complete three-axis release
```

The interaction stays on after trap release. No axis is integrated out or retains confinement. Arrays use x/y/z order. Physical density is `N |psi|^2/a0^3`; a projection along z is `N/a0^2 integral |psi|^2 dZ`. Integrating over the image plane recovers atom number. Energies are per atom in `hbar*omega0`, displayed as `E/h` in Hz. Widths are central RMS widths, not fitted Gaussian widths or TF edge radii.

The primary-source audit in [3D_REFERENCE.md](3D_REFERENCE.md) maps this convention to Castin–Dum (1996) and Dalfovo et al. (1999), including the TF ODE, its domain of validity, and the RMS conversion `R/sqrt(7)`.

## Numerical method and visible state

Preparation uses normalized imaginary-time splitting with exact local nonlinear flow, a chemical-potential shift, and the Fourier kinetic propagator. Successive states are compared every 50 iterations with an L2 threshold of `2e-7`, up to 6,000 iterations. The UI also reports the separate relative stationary residual `||(H-mu)psi|| / mu`. The noninteracting oscillator is initialized analytically and its sampled spectral residual is measured, not assumed zero.

Real-time evolution uses double-complex Strang split-step Fourier propagation with density recomputed before the second nonlinear substep. There is no per-step real-time renormalization. Simulation time is an integer step count times the chosen step; frame rate affects wall-clock playback speed only. Pausing finishes the current batch. Release records the exact step and removes all trap energy. Reset restores the prepared wavefunction and settings. Duration is counted from release, or from preparation while held, and rounded to the nearest numerical step.

The periodic box is sampled on `[-L/2,L/2-dx]`. The outer band is `max(2,n//16)` cells on each face; preparation rejects probability above `1e-5` there, and evolution stops at the first step exceeding `1e-3`. This guard cannot guarantee an arbitrarily small reflection/wraparound error; compare larger domains. A conserved norm is not a convergence test.

The rotatable isosurface uses marching tetrahedra on the actual density. Rendering averages blocks to 32³ for 64³/96³/128³ fields; 32³ and 48³ fields retain their resolution. Thresholds refer to the displayed volume's peak. The physical box stays fixed while the user can rotate/zoom. These controls never evolve the state. Central slices and column densities always use the full numerical grid and share a linear color scale. They are ideal observables without a camera model.

## Reproducible numerical evidence

Measured locally on Windows, using the repository's double-precision NumPy/SciPy runtime. Run `uv run python -m scripts.validate_3d` to regenerate raw cases and refinement comparisons in ignored `artifacts/3d-validation.json`. Timings depend on hardware and concurrent work. The extended 128³ cases are slower than the interactive presets.

### Gaussian limit

At 48³, L=24, dt=0.004, frequencies `(30,42,21)` Hz with f0=30 Hz and zero scattering, release to tau=2 gives maximum relative RMS error **1.69e-10** against `sqrt((1+Omega_i^2*tau^2)/(2*Omega_i))`. Norm drift is **3.92e-13**. The sampled initial oscillator has a relative stationary residual about **2.84e-7** at dx=0.5; its energy and evolved pointwise density also pass independent analytic tests. All three projected integrals return the total atom number.

### Representative interacting convergence

N=20,000, a_s=5.3 nm, the same frequencies, g=676.527705; release to tau=1.5. Baseline 48³, L=24, dt=0.004, preparation step=0.002. Each comparison changes one resolution choice; the larger box keeps dx=0.5 by also increasing grid count.

| Change | Largest relative change among three widths and x/z, y/z |
|---|---:|
| dt halved to 0.002 | 2.17e-7 |
| 64³ at the same L=24 | 4.62e-6 |
| L=32, 64³ at the same dx=0.5 | 1.45e-7 |
| Preparation step halved to 0.001 | 2.02e-7 |

All are below the stated 0.5% engineering target. Relative post-release energy drift falls from **2.47e-6** to **6.17e-7** when dt halves, consistent with second-order behavior. Norm drift across these cases stays below **6e-13**. Preparation residuals range from **4.1e-7 to 4.8e-7**. Absolute GPE–TF width differences at tau=1.5 are about **+1.969%, +4.246%, +0.176%** for x/y/z, much larger than the measured numerical refinement changes. Initial kinetic/interaction energy is **0.126**; TF is visibly approximate here.

### Stronger-interaction TF comparison

The TF preset has N=150,000, g=5073.957788, n=96, L=48, dt=0.004, the same trap frequencies, and release duration tau=3 (15.9155 ms). The absolute TF initial widths and scaling ODE are independently calculated, without fitting the GPE output. The UI also shows `sigma_GPE(0)*b_i` as a separately labeled, initial-width-anchored comparison.

At tau=3 the 96³ GPE widths exceed the absolute TF prediction by **0.596%, 1.047%, 0.140%** (x/y/z). Both x/z and y/z change from below one to above one: the cloud's aspect ratios invert. Norm drift is **5.4e-13**. The relative energy drift is **2.25e-6**, reducing to **5.63e-7** with half dt. The stationary residual is **2.54e-7**. The separate scaling ODE's energy invariant is tested to `1e-8`.

The initial kinetic/interaction energy ratio is **0.03096**, smaller than the moderate case. Refinement at the same tau=3 separates numerical changes from the finite-interaction discrepancy:

| Change from the 96³, L=48 TF case | Largest relative change among widths and x/z, y/z |
|---|---:|
| dt halved | 2.87e-7 (0.000029%) |
| 128³, same L=48 | 5.66e-4 (0.0566%) |
| 128³, L=64, same dx=0.5 | 3.25e-5 (0.00325%) |

The refined 128³, L=48 absolute TF width differences are **+0.592%, +1.099%, +0.135%**. These exceed the measured refinement changes. This supports an approximate TF comparison at these settings, not exact TF dynamics or experimental agreement.

Reducing the box to L=40 with 96³ triggers the boundary guard at tau=2.984. That run is deliberately retained in the report as an unsafe full-duration choice; it must not be compared with tau=3 data as if times matched. All other full-duration validation cases avoid the boundary guard.

### CPU and memory

For the measured moderate 64³ state, preparation took about **27.5 s**; preparation plus evolution to tau=1.5 took **32.9 s**. The 96³ TF case took **107.9 s** for preparation plus evolution to tau=3. The 128³, L=48 refinement took **197.9 s** to prepare and **307.4 s** including evolution; the 128³, L=64 case took **287.0 s** total. These are direct numerical timings without browser transfer/rendering, measured with some other validation work running concurrently.

Persistent numerical arrays occupy about **16 MiB at 64³**, **54 MiB at 96³**, and **128 MiB at 128³**. These counts exclude temporary FFT/nonlinear arrays, Python objects, JSON serialization, exported files and browser memory; they are not peak RAM measurements. Four 3D sessions are retained independently of the original 2D sessions. Re-preparing reuses a page's session; inactive sessions expire after one hour.

## Browser verification

`scripts/three_browser_check.py` tests actual Chromium controls: prepare the Gaussian, rotate by mouse/keyboard, change threshold/zoom, release, single-step, run/pause/finish, switch all-density view modes, download and replay the final field, recover from invalid preparation with Reset, then prepare and complete the interacting 64³ preset. It verifies that the original 2D session survives navigation and checks 390px/320px layouts. The Gaussian browser export replays with zero maximum complex-field difference. This is distinct from the numerical convergence evidence above.

`scripts/three_tf_browser_check.py` passed the full 96³ TF preset, including shape inversion and projected views. The dashboard, original experiment and paper-benchmark browser scripts also passed after the navigation change. There were no page errors. The full Python suite passed **72 tests**; lint and Python formatting checks passed separately. Test outputs and screenshots are generated under ignored `artifacts/`; passing one configuration does not validate every allowed input.

After numerical validation, `uv run python -m scripts.three_figure` writes a standalone four-panel scientific figure to `artifacts/3d-tf-validation.png`, showing widths, aspect ratios, TF differences and numerical refinement separately.

## Export and limits

Schema `coldatomlab-3d-v1` stores all physical/numerical settings, scales, coordinates, preparation metadata, release step, final step, histories and the complete real/imaginary field. `uv run python -m coldatomlab.replay path/to/export.json` recomputes the preparation and protocol, validates coordinates/scales and compares the complex field to `1e-8`. The check validates the saved field, not every arbitrary history annotation. Reproducing large interacting exports takes preparation time again.

Neither numerical agreement with an analytic limit nor finite-g proximity to TF reproduces a published experiment. Quantitative comparison with data would additionally require actual apparatus parameters, imaging calibration, measured uncertainties and further physical terms where appropriate.
