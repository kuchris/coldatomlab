# Finite tunnelling pulses (v0.13)

Open `/#quantum`, click **Finite pulse comparison ↓**, then **Run finite-pulse
comparison**. Five arms use the same initial quantum state and seeded static
phase/bias offsets: no pulse, ideal instantaneous swap, short finite pulse,
nominal π pulse and long finite pulse. This works in the local dashboard and
the extracted static ZIP without a GPU or simulation API.

## Explore the difference

- **Watch population transfer** starts all N=40 atoms on the left, with
  U=bias=0, total time 100 ms and pulse J=10 Hz. The nominal pulse lasts 25 ms;
  the short and long ones last 20 and 30 ms. At the nominal pulse midpoint,
  mean populations are 20/20; at its end all atoms have transferred. Both
  ±20% duration errors leave 9.54915% of the population on the left.
- **Compare echo recovery** is the default: balanced coherent N=40, U=0,
  initial phase zero, static bias half-range 2 Hz, total time 500 ms,
  Jpulse=10 Hz, 20% duration error, 32 preparations and seed 17.
- **Keep interactions during pulse** sets U=0.3 Hz and total time 250 ms.
  Interactions remain active in both the free holds and the driven interval.
  The zero-interaction π calibration no longer guarantees a perfect exchange.

Presets preserve count and seed, and stage other settings until Run. Controls
include N, U, total duration, pulse J, duration error and count/seed. Expand
**Initial state and static offsets** to edit left fraction, initial phase,
base bias and uniform variation ranges. All UI states are coherent states;
the numerical module also accepts the existing Gaussian and Fock states.

Choose an individual preparation and short/nominal/long arm to inspect. The
population plot compares all five arms for that preparation; it defaults to
**Zoom around the pulse** so the finite exchange is visible. Uncheck to see the
full experiment. The phase panel shows each arm's conditional coherence vector,
while the lower chart shows the magnitude of the complex average across
preparations. These are different measurements. Phase is unavailable for C≤1e-8.

Timeline playback selects precomputed physical states. Start, pulse start,
midpoint, pulse end and final-time buttons use exact checkpoints. Boundary
snapshots are one-sided: an ideal swap changes the state immediately, whereas
finite J switching preserves the state but changes its Hamiltonian. Inactive
arms simply keep evolving through those shared checkpoints.

Pause/resume operates between completed preparations, each containing all five
arms. Cancel retains the completed prefix for inspection/export. Invalid input
preserves the previous comparison. Earlier quantum, preparation and ideal-echo
panels and pins remain unchanged, including across dashboard navigation.
Reloading clears results.

## Pulse definition and calibration

The fixed-N occupation basis is |n,N−n>, m=n−N/2 and sum |c_n|²=1. The
[existing two-mode convention](TWOMODE.md) remains:

```text
H/h = −J(aL†aR + aR†aL) + U m² − δ m
psi(t) = exp[−i 2π (H/h) t] psi(0)
```

J, U and δ are in Hz. In formulas t is seconds; UI/export times are ms.
U is the coefficient in U/2[nL(nL−1)+nR(nR−1)], with a fixed-N constant removed.
Positive δ raises the right well. There is no real-time renormalization.

For U=δ=0, H/h=−2J Jx, where Jx is the dimensionless collective-spin operator.
Therefore the resonant π width is tau_pi=1/(4J) seconds, or 250/J ms. The
finite operator at that width is exp(+iπJx)=i^N S, where S reverses occupation
amplitudes. The ideal arm uses S with its global phase omitted, as in v0.12.
The finite arms retain their actual complex phase; their raw fields must not
be forced to match S by renormalization or an undisclosed phase change.

For fractional duration error e, the three widths are (1−e)tau_pi, tau_pi
and (1+e)tau_pi. Every finite pulse is centered on T/2:

```text
t_on  = (T − width)/2
t_off = (T + width)/2
J(t)  = Jpulse inside [t_on, t_off], 0 in the holds
```

All arms end at the same total T. The pulse replaces part of the free hold;
it is not extra time added to the experiment. U and each preparation's δ remain
unchanged across both switches. The nominal calibration assumes U=δ=0 and
does not imply exact inversion at nonzero detuning or interaction.

Limits: Jpulse in [0.5,20] Hz, e in [0,0.5], total time in [1,1000] ms, and
the longest pulse strictly shorter than T. Other bounds are inherited from
[Preparation variation](PREPARATION.md). The bias range must fit entirely
within ±20 Hz; no draws are clipped. Hold J must be zero, and invalid settings
are rejected rather than reinterpreted.

## Evolution, observables and references

Each hold uses exact diagonal evolution. Each driven interval diagonalizes the
real symmetric Hamiltonian, projects the incoming arbitrary complex normalized
state into its eigenbasis and evolves spectrally. Initial eigenstate coefficients
are recomputed for the actual incoming state; a perfect swap is never inserted
in the finite path. The previous default `TwoMode.Solver(config)` behavior is
preserved; its optional incoming state is copied and validated without norming.

Sampling combines 101 uniform full-experiment times, 21 uniform times within
each finite pulse, and all switch/midpoint events. Near-identical times merge
within 1e-9 ms, prioritizing exact event times. Every event has before/after
rows. The default has 150 rows per arm; other settings can have a different
count. Plot spacing is not an integration step. Shorten T or adjust parameters
to inspect dynamics faster than the displayed sampling.

For an all-left noninteracting state, resonant transfer obeys
<nL>/N=cos²(2πJ t_pulse). More generally, at constant bias the transfer to the
right is [J²/(J²+(δ/2)²)] sin²(2π sqrt[J²+(δ/2)²] t_pulse). Tests also construct
the full N-particle coherent amplitudes from the analytic two-component spinor,
so correct populations alone cannot hide an incorrect complex phase.

Within a constant-H segment, norm and energy are conserved. At switch-on,
Delta<E/h>=−Jpulse N Re(q), where q=2<aL†aR>/N is evaluated at the switch;
switch-off removes the coupling contribution. The state is continuous. No
atom-plus-drive energy budget is modeled.

The table reports final ensemble coherence, mean left fraction and mean
F_r=|<psi_ideal,r(T)|psi_arm,r(T)>|². Fidelity compares paired complete
many-body states and ignores global phase; averaging the F_r is not the
fidelity between two mixed ensemble density matrices, nor an experimental
gate-fidelity calibration. High coherence alone does not imply correct exchange.

Default measured results (32 preparations, seed 17):

| Arm | Final ensemble C | Mean paired fidelity |
|---|---:|---:|
| No pulse | 0.240061 | 0.011164 |
| Instantaneous swap | 1.000000 | 1.000000 |
| Short, 20 ms | 0.897344 | 0.283490 |
| Nominal, 25 ms | 0.997524 | 0.954733 |
| Long, 30 ms | 0.882485 | 0.207533 |

These are finite-sample teaching results, not experimental data. Uniform draws
use the existing documented generator and the same recipe in every arm.

## Exports and validation

**Export pulse JSON** uses `coldatomlab-pulse-v1`, retaining the plan, convention,
windows, exact checkpoints, zero-offset reference, actual offset recipes, five
final complex states per preparation, finite switch-boundary states, conditional
histories and all aggregates. **Export pulse CSV** saves aggregate histories,
applied settings, completion status, checkpoint side and applied J. CSV lacks
the amplitudes required for full replay.

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-pulse.json
uv run pytest tests/test_pulse.py tests/test_twomode.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.pulse_browser_check
```

Python independently diagonalizes hold and pulse matrices with NumPy, applies
an explicit swap matrix only in the ideal arm, and verifies recipes, windows,
checkpoints, complex states, histories, fidelities and aggregate distributions.
Absolute comparison tolerance is 5e-8 with wrapped phase differences; complex
state L2 tolerance is 5e-8 and norm drift tolerance is 1e-9. Complete results
and nonempty cancelled prefixes are supported.

All 270 repository tests passed. The 40 finite-pulse tests include independent
replay through N=100, incoming
state propagation and segment composition, rejection of unnormalized states,
analytic Rabi fields/populations, i^N global phase, retained U/bias, switch
continuity/energy, faster-pulse approach to the ideal, zero duration error,
reproducibility, exact timing, invalid settings and tampered exports.

Separate Chrome checks exercise both the local and extracted-static dashboard:
all presets, arm/preparation selection, zoom, timeline play/pause/slider and
stage buttons, pause/resume/cancel, invalid recovery, seeded repeats, JSON/CSV
and independent replay. They verify preservation of all earlier panels, same-tab
navigation and responsive widths 1440/390/320 px, including the complete iframe
height. Default browser replay gives maximum complex-state L2 error 1.17e-13
and norm drift 1.67e-14; the interacting case gives 4.29e-14 and 1.38e-14.
Evidence lives outside Git under `artifacts/pulse/`.

## Paper provenance and model limits

[Gross (2012)](https://arxiv.org/html/1203.5359v1) supplies the coupled two-mode
collective-spin framework and discusses technical phase noise and echo.
[Hahn (1950)](https://journals.aps.org/pr/abstract/10.1103/PhysRev.80.580)
provides the classic echo context. Pulse durations here follow algebra from our
Hamiltonian convention, not a reconstruction of either paper's apparatus.

J(t) is a prescribed control between two fixed spatial orbitals. We do not
evolve a changing barrier, orbital deformation, higher-mode excitation,
electromagnetic fields, pulse rise/fall times, heating, loss, detector noise or
time-dependent stochastic bias. Fast switching may violate the fixed-mode
approximation in an actual trap. Numerical agreement within this basis does
not establish that such a pulse can be implemented in a particular apparatus.
