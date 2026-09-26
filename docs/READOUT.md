# Phase readout (v0.14)

Open **Quantum coherence → Phase readout ↓ → Run phase readout**. This panel runs
inside the dashboard and in the extracted static ZIP, without WebGPU or a solver
API. Every count represents a freshly prepared copy of the same quantum state.
It is not repeated nondestructive measurement of one cloud.

## Explore

- **Read a coherent phase**: balanced coherent N=40, initial phase 0.7 rad,
  no hold, U=bias=0, Jreadout=10 Hz, 12 reference phases, 256 shots per arm and
  setting, seed 17. Direct count means stay around 20. After mixing they follow
  a fringe. Ideal and calibrated finite readout have identical probabilities
  but independent count samples.
- Change the initial phase to 0 or pi (3.141592653589793), then Run. At reference
  phase alpha=0 the ideal output switches from all left to all right, while
  direct counting has the same binomial distribution in both cases. These
  endpoints have zero ideal counting variance, not camera noise.
- **Try a biased pulse** retains delta=8 Hz during a 20% too-long readout.
  Compare the apparent count-inferred phase with model-only readout bias.
- **Try a fixed-number state** has no first-order coherence. Ideal mean count
  fringes vanish even though output counts fluctuate; unresolved phase is
  unavailable, not zero. Higher-order correlations are not inferred here.
- Under **Preparation and echo**, choose a prescribed Gaussian number-narrow
  state or an ideal midpoint echo during an isolated hold. The Gaussian is not
  an adiabatic preparation simulation. Echo cancels static bias during the hold
  at U=0, but does not cancel interactions or bias during finite readout.

Settings and presets apply only on Run. Pause occurs between completed reference
settings, each containing three arms. Cancel retains the finished scan prefix;
partial scans have histograms but no harmonic fit. Invalid settings preserve
the prior result. Inspect selectors and dashboard navigation preserve applied
settings, samples and earlier experiments. Reloading clears results.

## Physical convention

The basis is |n,N-n>, n=0,...,N, with sum |c_n|^2=1. Define m=n-N/2 and

```text
H/h = -J(aL†aR + aR†aL) + U m² - delta m
q = 2<aL†aR>/N
z = 2<NL>/N - 1
```

J, U and delta are frequencies in Hz; displayed times are ms. U is the on-site
pair coefficient in U/2[nL(nL-1)+nR(nR-1)] with the fixed-N constant removed.
Positive delta raises the right mode. Time evolution is exp[-i2pi(H/h)t] with
t in seconds. No propagation step renormalizes the state.

The preparation hold has J=0. Optional ideal midpoint echo reverses occupation
amplitudes n -> N-n, omitting its fixed-N global phase. The input state is the
same for all reference phases and all arms. The gate before mixing is

```text
c_n -> exp[-i(N-n)(alpha+pi/2)] c_n
```

For positive-J mixing at U=delta=0, tau_pi/2=1/(8J) seconds, giving

```text
z(alpha) = Re[q exp(-i alpha)]
         = Re(q) cos(alpha) + Im(q) sin(alpha).
```

Thus alpha=0 and pi/2 measure the two quadratures. The pi/2 reference offset in
the gate makes this a cosine convention. This is a phase gate followed by the
project's existing real-J Hamiltonian, not an implicit complex coupling or a
Hadamard matrix substituted into the finite arm.

Direct counting measures the unmodified incoming state. Ideal mixing is an
instantaneous rotation evaluated with a resonant spectral propagator; its
calibration duration is a mathematical rotation parameter, not elapsed time.
Finite mixing uses the actual Hamiltonian, retaining U and delta, for
(1+duration_error)/(8J) seconds. The finite arm therefore adds its readout time
to the common hold; this is not an equal-total-duration comparison.

## Counts and inference

Use K=8–32 equally spaced alpha=2pi*k/K without duplicating the endpoint. Each
arm at each setting has 16–4096 independent ideal projective number measurements
drawn from its full P(n). A single 32-bit LCG stream with recurrence
r=(1664525*r+1013904223) mod 2^32 and u=(r+0.5)/2^32 supplies consecutive,
non-overlapping blocks in setting-major, then direct/ideal/finite order. Histograms
are exported along with each block seed. N_L+N_R=N in every outcome.

For each count histogram, compute the sample mean, unbiased sample variance and
SEM=sqrt(variance/shots). Error bars are SEM of the mean, not per-shot scatter.
The inference function receives only alpha, measured z and its empirical mean
variance. It never receives the state's true q, phase or predicted variance.

Fit z=offset+a*cos(alpha)+b*sin(alpha) using unweighted full-period least squares.
The browser uses orthogonal Fourier sums; Python independently uses the design
matrix pseudoinverse. Contrast=hypot(a,b) is not clipped; phase=atan2(b,a).
Propagate each setting's independent empirical mean variance into the coefficient
covariance. A delta-method gradient (-b,a)/(a²+b²) gives a local phase standard
error. Mask phase and its SE unless contrast is greater than both 1e-8 and three
times the largest quadrature standard error. This is a conservative visibility
gate, not a formal hypothesis test or a guarantee against false detections.

The phase SE is a local, high-signal approximation, not a confidence interval.
Empirical variance can be poorly estimated with few shots. Near zero coherence,
phase is not identifiable. A full-period scan avoids the sign ambiguity of one
readout setting; a partial prefix is deliberately not fitted.

Finite-pulse distortions can cause offsets, phase bias or higher harmonics. Its
fitted phase is an **apparent fringe phase**, not automatically the incoming
coherence phase. The UI reports unweighted RMS fit residuals in z units. The
separate **model readout bias** uses a fit to noiseless model means minus the
incoming model phase, wrapped to [-pi,pi]. Statistical phase SE excludes this
systematic bias. A visible residual is not automatically noise, and contrast or
number narrowing alone does not demonstrate quantum metrological advantage.

## Exports and independent replay

JSON schema `coldatomlab-readout-v1` retains the applied recipe, incoming and all
output complex amplitudes, count histograms/seeds, statistics and both measured
and noiseless fits. Output time is hold_ms for direct/ideal and hold_ms+width_ms
for finite readout. Ideal output energy uses its U=delta=0 rotation Hamiltonian;
finite output energy uses the driven Hamiltonian. Neither is a drive-energy budget.
The inherited base.duration_ms is solver metadata; hold_ms is the active hold.

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-readout.json
uv run pytest tests/test_readout.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.readout_browser_check
```

The Python verifier independently regenerates states using NumPy Hermitian
diagonalization, count draws, empirical statistics and least-squares fits. It
checks exact schema structure and settings, wraps phase differences, and enforces
full complex-state L2 < 5e-8 and norm drift < 1e-9. Count regeneration verifies
the declared ideal measurement model, not a physical detector. CSV supplies the
scan summary and applied settings; JSON is required for full replay.

## Literature and limits

[Gross (2012), section IV.1](https://arxiv.org/html/1203.5359v1#S4.SS1) describes
Ramsey readout through population differences and relates fringe visibility to
mean spin length. This implementation uses fixed spatial modes and prescribed
phase/mixing operations; it does not recreate an internal-state microwave/RF
apparatus or claim the experimental sensitivity gains discussed there.

No preparation noise, detector noise, atom loss, finite-rise phase gate, orbital
excitation, 3D expansion or continuous environmental noise is modeled. Fixed-mode
validity is a physical approximation independent of numerical convergence.
The state dimension is N+1, with 2<=N<=100. Simulation is independent of rendering.

## Validation evidence

Numerical: all 303 repository tests passed in 144.40 seconds, including 33
readout tests. They cover analytic binomial fringes at both
quadratures and the phase branch cut, arbitrary coherent/Gaussian/Fock states,
interacting and detuned propagation against an independent matrix exponential,
echo and phase-sign checks, zero coherence, seeded stream blocks, empirical
phase scatter versus the reported local SE, invalid settings and export tampering.
Full complex-state replay includes N=100, U=2 Hz, bias=20 Hz and a 1000 ms hold.

Live browser: headless installed Chrome passed local-server and extracted-static
checks for all three presets, hold/echo, count selectors, pause/resume/cancel,
invalid-input preservation, seeded repeatability, changed seeds, actual JSON/CSV
downloads and independent replay. Earlier manual, preparation, echo and pulse
exports remained identical. Direct quantum.html links returned to the same
in-dashboard route without a new tab. Desktop 1440 px and mobile 390/320 px had
no document horizontal overflow; wide results tables scroll within their panel.
All five populated panels fit inside the resized iframe, including the 320 px
layout exceeding the former 20,000 px height cap. No page script errors occurred.
Desktop and mobile screenshots were visually inspected.

The default ideal readout inferred phase 0.703037 rad, local SE 0.003654 rad and
contrast 0.998202 from a true phase of 0.7 rad. Independent replay of the actual
browser export had maximum complex-state L2 difference 2.36e-14 and norm drift
1.18e-14. The interacting/echo export had L2 difference 2.35e-14 and norm drift
1.65e-14. These establish agreement inside the specified two-mode and ideal-count
models, not experimental accuracy. Browser artifacts are generated locally under
`artifacts/readout/` and excluded from version control. Validation servers use
temporary ports and close automatically.
