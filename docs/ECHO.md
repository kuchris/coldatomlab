# Ideal spin echo comparison (v0.12)

Open **Quantum coherence** at `/#quantum`, click **Spin echo comparison ↓**,
then **Run comparison**. The same page and controls are included in the static
WebGPU ZIP; echo uses browser float64 and needs no GPU or simulation API.

## Three examples

1. **Refocus static bias**: balanced coherent N=40, J=U=0 Hz, total hold
   T=500 ms, no initial phase spread, independent uniform bias offsets ±2 Hz.
   At T/2 the echo arm swaps L/R; the other arm keeps evolving. With 64
   preparations and seed 17, final ensemble coherence is 0.292491 without echo
   and 1 with echo. Individual coherence remains 1. The infinite-ensemble
   no-echo guide is zero at T; its finite-sample remainder is not solver error.
2. **Keep initial phase spread**: add independent uniform initial offsets ±π/2
   rad. Echo cancels the accumulated static-bias contribution at T but only
   conjugates the initial phase distribution. Final coherence equals the initial
   finite-ensemble coherence, rather than automatically becoming 1. The
   infinite-ensemble value for this example is 2/π.
3. **Keep interactions**: U=1 Hz, T=250 ms, initial phase spread zero. Static
   bias still cancels at T, but interactions are not reversed. This time is
   chosen away from the revival: individual and ensemble first-order coherence
   approach zero even with echo. This does not imply loss of pure-state norm.

The controls let you change N (2–100), U (0–2 Hz), total hold (1–1000 ms),
phase half-range (0–π rad), bias half-range (0–5 Hz), preparations (2–128) and
unsigned 32-bit seed. UI preparations are balanced coherent states with base
phase and bias zero. J is fixed at zero. Both arms always share the same draws.
The numerical module also supports the existing Gaussian and Fock states and
nonzero base phase/bias; it explicitly rejects J≠0. No samples are clipped.

Pause/resume operates between completed pairs. Cancel retains completed pairs;
a nonempty prefix can be exported and independently replayed. Invalid input
preserves the previous result. Manual states, pins and the preparation-variation
panel remain untouched. Dashboard navigation preserves all three panels;
reloading clears them.

## Read the timeline

The slider and **Play timeline** inspect precomputed states. **Before pulse**
and **After pulse** select consecutive snapshots at exactly T/2. At the swap,
the echo vectors reflect across the real axis while the no-echo vectors do not
change. No physical time elapses during this ideal operation.

There are 101 uniformly spaced times plus a second midpoint snapshot, giving
102 rows per arm. Both midpoint sides are retained in exports; `pulse_applied`
distinguishes them. This sampling sets the plotted resolution, not an integrator
step. Playback speed does not change evolution. Shorten the duration to resolve
rapid interaction dynamics.

Thin arrows show each conditional coherence q=2<aL†aR>/N; thick arrows show
their complex mean. Length is coherence, not atom number or spatial position.
Phase is unavailable when the relevant magnitude is at most 1e-8. The plots
compare ensemble magnitudes; the readings also report the mean of individual
magnitudes. These quantities need not agree, as explained in
[Preparation variation](PREPARATION.md).

## Hamiltonian and exact pulse

Use n=nL, m=n−N/2 and fixed total N. The [two-mode conventions](TWOMODE.md)
are unchanged:

```text
H/h = U m² − δ m                         (J = 0)
c_n(t) = c_n(0) exp[−i 2π (U m² − δ m) t]
S |n,N−n> = |N−n,n>
psi_echo(t ≥ T/2) = exp[−i H(t−T/2)/hbar] S exp[−i H T/(2 hbar)] psi(0)
```

U and δ are in Hz; t and T in these formulas are seconds. UI milliseconds are
converted explicitly. U is the on-site pair coefficient of
U/2[nL(nL−1)+nR(nR−1)], after removing a constant. Positive δ raises the right
well. Each state has sum_n |c_n|²=1. Propagation and pulse preserve norm without
renormalization.

S reverses the occupation-amplitude array. A physical collective π rotation
about x, exp(−iπJx), equals (−i)^N S; this fixed-N global phase is omitted by
the export convention. S²=I. At the pulse P_after(n)=P_before(N−n),
<nL>_after=N−<nL>_before and q_after=q_before*. Pulse energy can change:
Delta<E/h>=2δ<m>_before. The external drive is not modeled, so this jump is
not an energy-conservation check on an atom-plus-drive system.

Because S m S=−m but S m² S=m², equal holds cancel the linear static bias.
The final amplitudes satisfy the exact identity:

```text
c_n,echo(T) = c_(N−n)(0) exp[−i 2π U (n−N/2)² T]
```

The U term retains the full elapsed time. For a balanced coherent state,
individual coherence in either arm is |cos(2πUt)|^(N−1), including across
the ideal pulse. Initial phase offsets are conjugated rather than removed.

## Ensemble guides

Let alpha be the initial phase offset in [-A,A] rad and beta the static bias
offset in [-B,B] Hz. The ideal reference uses the same sequence with both
offsets zero. At each time, before taking a magnitude:

```text
No echo:       q_r = q_ideal exp[i alpha_r − i 2π beta_r t]
Echo, pre:     q_r = q_ideal,echo exp[i alpha_r − i 2π beta_r t]
Echo, post:    q_r = q_ideal,echo exp[−i alpha_r − i 2π beta_r (t−T)]
```

The finite ensemble is the mean of these vectors, not a mean of state
amplitudes. For independent uniform offsets, replace the exponential factor
by sinc(A)sinc(2πBt) before the pulse and sinc(A)sinc(2πB(t−T)) after it.
Here sinc(x)=sin(x)/x, with sinc(0)=1. Plot guides use the magnitude of this
factor times the ideal coherence. Even where the infinite mean is zero,
the magnitude of a finite mean can be positive.

The sampler is the same documented unsigned 32-bit generator as v0.11, with
two draws per preparation even for zero ranges. No-echo and echo share a
single recipe record, so their random inputs cannot independently drift.

## Export, verification and evidence

**Export echo JSON** uses `coldatomlab-echo-v1`. It saves the plan, convention,
status, paired recipes, complete complex final states in both arms, complete
pulse-before/pulse-after states, 102-point conditional histories, ideal
reference and both ensemble aggregates. **Export echo CSV** contains the two
aggregate histories with applied settings, status and pulse-side flags; it
does not contain the complex amplitudes required for independent replay.

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-echo.json
uv run pytest tests/test_echo.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.echo_browser_check
```

The browser multiplies occupation amplitudes by exact diagonal phases. Python
instead uses NumPy Hamiltonian diagonalization and an explicit permutation
matrix for S. Replay regenerates offsets and checks both arms, pulse states,
histories and aggregates. Absolute numeric tolerance is 5e-8; phase differences
are wrapped. Complex-state L2 tolerance is 5e-8 and norm drift tolerance 1e-9.
Completed ensembles and nonempty cancelled prefixes are supported.

All 230 repository tests passed. The 39 echo tests cover independent
amplitudes/observables, static cancellation,
remaining interaction evolution, exact finite-sample and infinite-ensemble
formulas, initial phase spread, pulse inverse/populations/coherence/energy,
equivalence to a π rotation up to global phase, midpoint sides, zero variation,
count moments, seeded repeatability, invalid settings and export tampering.

Separate Chrome browser checks exercise local and extracted-static controls,
timeline play/pause/slider and midpoint buttons, all presets, invalid recovery,
cancelled prefixes, JSON/CSV/replay, manual/pin/preparation isolation, same-tab
section navigation and dashboard persistence. Widths 1440/390/320 px have no
horizontal overflow. The default browser export's maximum independent
complex-state L2 difference is 1.89e-15; the interacting example's is 3.00e-15.
Generated logs, exports and screenshots live under `artifacts/echo/` outside Git.

## Papers and limits

- [Hahn, Physical Review 80, 580 (1950), Spin Echoes](https://journals.aps.org/pr/abstract/10.1103/PhysRev.80.580):
  the classic echo concept, originally studied using radiofrequency pulses and
  nuclear spins. This simulation does not reconstruct those measurements.
- [Gross, J. Phys. B 45, 103001 (2012), §IV.3](https://arxiv.org/html/1203.5359v1#S4.SS3):
  differential energy shifts, shot-to-shot phase noise and spin echo in cold-atom
  work. Finite-frequency noise remains a separate issue. Our uniform ranges
  are teaching choices rather than a measured noise spectrum.

These are left/right spatial orbitals, not two hyperfine states. The pulse is
an ideal instantaneous mode swap: no microwave field, finite tunnelling pulse,
drive work, pulse error, higher orbital excitation or spatial motion is evolved.
No thermalization, losses, detector noise or time-varying stochastic drive is
included. The result demonstrates refocusing within the declared two-mode
Hamiltonian; it is not experimental validation or reversal of all decoherence.

The [finite tunnelling pulse comparison](PULSE.md) replaces the instantaneous
swap with actual coupled evolution in a separate panel, retaining this ideal
echo as one reference arm.
