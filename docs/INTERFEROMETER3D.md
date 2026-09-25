# Three-dimensional coherent interferometry (v0.7)

The browser GPU and CPU reference implement two separate experiments: an analytic coherent Gaussian pair and an interacting split / hold / release protocol. Both evolve the full three-dimensional wavefunction. The surface, column projections, axial density and measurements are derived from that state.

## Conventions and preparation

Use the [existing 3D conventions](MODEL3D.md): `integral |psi|² dX dY dZ = 1`, length `a0 = sqrt(hbar / (m omega0))`, time `omega0^-1`, energy `hbar omega0`, and `g = 4 pi N as / a0`. Species is Rb-87. The line-density plot shows `N integral |psi|² dY dZ / a0` in atoms/µm. The potential plot shows the actual potential along y=z=0, converted to V/h in Hz.

The analytic pair requires as=0. With `w_i = f_i/f0`, prepare the normalized sum of oscillator Gaussians centered at X=−d/2 and +d/2, with the right packet multiplied by `exp(i phi)`. Its continuum normalization includes overlap `S=exp(-w_x d²/4)`, giving the divisor `sqrt(2(1+S cos(phi)))`; the sampled initial field is normalized once on its grid. It is deliberately not a stationary state. The trap starts fully released. These are coherently specified packets, not independently formed condensates.

The exact free reference evolves each axis with `q_i=1+i w_i t`, amplitude factor `q_i^-1/2`, and Gaussian exponent `-w_i (X_i-X0_i)²/(2 q_i)`. The interference carrier is `cos(phi-kX)` with `k=w_x² t d/(1+w_x² t²)`. The finite-width phase period is `2 pi / k`; positive phi moves carrier maxima toward positive X. A density-envelope maximum need not coincide with a carrier maximum. Reference calculations use the continuum formula independently of the FFT solver.

## Driven sequence

Prepare a single trapped interacting ground state, then run this explicit teaching potential:

```text
V(X,Y,Z,s) = (w_x² X²+w_y² Y²+w_z² Z²)/2
             + H(s) exp(-X²/(2 b²)) + B(s) tanh(X/b)/2
H(s) = Hmax sin²(pi s/(2 S))       during Split
     = Hmax                      during Hold
B(s) = configured bias           during Hold only
V = 0                            during Expansion
```

Each duration is rounded half-up to an integer number of steps. S is the split step count. The displayed timeline uses those actual boundaries; Hold may have zero steps. Evolution evaluates the entire external potential at the midpoint of each time step. Both Strang local half-steps use that same potential and their own current density. Release removes the trap, barrier and bias on all axes, retaining the contact interaction. Manual release is disabled in this mode. Run stops at the exact rounded end; Reset restores the original ground state and protocol.

A positive hold bias raises the right well. Well-separated, weakly tunneling packets therefore accumulate a negative right-minus-left phase, approximately `-B * hold_time`. The smooth tanh profile, tunneling, interactions and excitations prevent this from being an exact universal law. Energy changes during the driven sequence; after release it should converge toward conserved energy. Real-time evolution never renormalizes the state.

The default sequence uses N=2000, as=5.3 nm, frequencies (30,42,21) Hz at f0=30 Hz, 64³ samples in a 24 a0 cube, dt=0.006, barrier height 12, width 0.8 a0, split time 3, hold time 0.6, bias ±1 and expansion duration 2. This is approximately 15.92 ms splitting, 3.18 ms hold, and 10.60 ms expansion after rounding. The barrier is uniform in y/z. The pair presets use a larger 32 a0 cube, separation 6 a0 and duration 3 to suppress long-time periodic-tail contamination.

## Measurements and comparison

- Left/right populations split the X=0 cell equally. A changing imbalance after release can arise from interference across that plane; it is not a label tracking each original packet.
- Mirror phase is `arg integral_(X>0) conj(psi(-X,Y,Z)) psi(X,Y,Z) dV`. Coherence is the magnitude of that overlap divided by the product of the half-cloud norms. The unmatched periodic endpoint is excluded. Phase is unavailable if coherence is at most 0.2 or either side has at most 5% population. This is a wavefunction diagnostic, not an image fit or a phase attached separately to each cloud once they overlap.
- Fringe spacing uses parabolically interpolated local peaks above 15% of the line-profile maximum. At least three peaks, four cells per spacing and a spacing coefficient of variation no greater than 15% are required. Otherwise spacing and contrast are unavailable. Contrast uses parabolic peak/valley heights (clamped to nonnegative density), taking the lower of each adjacent pair of peaks. Finite envelopes and sampling bias both estimates, so they must not be equated to the analytic carrier period or the paper's fitted contrast.
- Pin stores an immutable snapshot and complete export. Current and pinned line densities share physical axes, retaining their own atom numbers, scales and times. The comparison export contains both full records; replay verifies each independently. A reload clears the pinned record.

The noninteracting single-cloud and Castin–Dum width curves are not applicable to these experiments and are suppressed. Column density is ideal, with no absorption camera or optical noise. Boundary stopping, float32 norm-drift stopping, and preparation residual checks remain active. Unsupported settings are rejected rather than silently approximated.

## Relation to established experiments

[Shin et al., PRL 92, 050405 (2004)](https://doi.org/10.1103/PhysRevLett.92.050405), [author manuscript](https://arxiv.org/abs/cond-mat/0306305), motivates coherent splitting, a controlled phase shift during separation, and interference readout after release. That work used sodium, an optical double well and absorption imaging. This implementation uses Rb-87 and a declared harmonic-plus-Gaussian model, and measures its numerical wavefunction. No apparatus parameters, experimental contrast, thermal phase fluctuations or measured image are reproduced. The separate [Shin benchmark](BENCHMARK.md) remains a reduced sodium fringe-spacing comparison with a different purpose. The earlier [source audit](SHIN_REFERENCE.md) documents those reported data and limitations.

## Reproduce verification

```powershell
uv run pytest -q
uv run python -m scripts.interferometer_check --url http://127.0.0.1:8766 --refinements
uv run python -m scripts.audit_interferometer
uv run python -m scripts.interferometer_browser_check --url http://127.0.0.1:8766/gpu.html
uv run python -m scripts.interferometer_browser_check --url http://127.0.0.1:8766/#lab3d --cpu-smoke
uv run python -m coldatomlab.replay artifacts/interferometer/comparison.json
uv run python -m scripts.package_webgpu
```

The numerical browser script compares real hardware GPU fields against independent float64 runs and analytic pair fields, then optionally performs CPU refinements. The browser-control script exercises actual controls and downloads. Outputs are ignored under `artifacts/interferometer/`. GPU replay is a toleranced CPU comparison, not bitwise GPU reproduction.

## Measured numerical evidence

Hardware Chrome selected the NVIDIA Blackwell adapter (RTX 5070 Ti). Three coherent-pair phases (0, pi, 0.7) and both sequence bias signs completed without norm/boundary stops. Independent full-field comparisons, not only screenshots or widths, gave:

| Case | GPU vs CPU field L2 | Maximum relative width difference |
| --- | ---: | ---: |
| Pair phase 0 | 0.0001442 | 0.00207% |
| Pair phase pi | 0.0001530 | 0.00189% |
| Pair phase 0.7 | 0.0001433 | 0.00216% |
| Sequence, positive bias | 0.0004488 | 0.00493% |
| Sequence, negative bias | 0.0004477 | 0.00488% |

CPU pair fields differ from the continuum solution by about 0.0000641 in L2 at t=3 in the 32 a0 box. The pi-state central line density is about 1.02e-10 of the peak on GPU, while phase zero has its maximum at the center; a positive phase moves the central density maximum rightward. These test coherent interference, not independently randomized phases.

At the split boundary, central line density is 0.001955 of the side maximum. The pre-expansion mirror phases are −0.593137 and +0.593137 rad under opposite biases, close to the separated-well estimate ±0.6. GPU/CPU phase differences at the recorded stage boundaries and final time are below 0.000050 rad. After expansion the mirror diagnostic changes as the packets overlap; it must not be read as the original packet phase. The default GPU sequence finishes at step 933, t=5.598, with norm 0.999788692 (0.0212% drift), without real-time normalization.

CPU refinements compare the same physical end time. For dt=0.003 the requested expansion is set to 1.998 so the end remains t=5.598; naively re-rounding duration 2 would instead end at 5.601.

| Refinement from 64³, L=24, dt=.006 | Maximum width change | Mirror phase change | Relative fringe-spacing change | Contrast change |
| --- | ---: | ---: | ---: | ---: |
| Half time step, same end time | 0.000425% | 0.00000316 rad | 0.000303% | 0.00000228 |
| 96³, same box | 0.00298% | 0.00839 rad | 0.0288% | 0.0174 |
| L=36, 96³, same cell size | 0.00688% | 0.0000666 rad | 0.000726% | 0.00000751 |
| Half preparation step | 0.000123% | 0.00000000239 rad | 0.00000914% | 0.0000000745 |

The 64³ contrast estimate is about 0.9073 versus 0.9246 at 96³. The mirror phase changes by about 0.48 degrees under grid refinement. These observables are less converged than the widths; displayed digits are not accuracy guarantees. The audit requires phase changes below 0.01 rad, relative spacing changes below 2%, and absolute contrast changes below 0.04 for these refinements. These are disclosed engineering acceptance tolerances, not universal uncertainty bounds.

Contrast initially used sampled extrema, which changed by about 0.0522 under refinement. After correcting it to use parabolic heights, the stored solver profiles were remeasured independently in Python and browser JavaScript, agreeing within 1e-12. No field or physical setting was changed or fitted to a target.

## Browser evidence

Hardware Chrome completed actual zero/pi and dynamic-sequence runs, automatic release/end, pause holding time, single-step, reset, invalid-pair recovery, projections, immutable pinning and full comparison export. The exported sequence and comparison both pass the official CPU replay verifier. A separate CPU browser run completes a short interacting sequence and passes exact field replay. Existing single-cloud browser regression checks pass, including 2D-session preservation, rendering, navigation and error recovery.

The same interferometer workflow runs from the extracted static ZIP on an ordinary localhost file server with no simulation API requests or JavaScript errors. Desktop, 390px and 320px layouts were exercised. Static publishing itself is not part of this release. WebGPU support in the Codex embedded browser and other GPU vendors is not established by these Chrome checks.
