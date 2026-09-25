# Preparation variation (v0.11)

Open `/#quantum`, scroll to **What if each preparation is slightly different?**,
and click **Run preparations**. This panel preserves the manual experiment and
its pins. It also runs in the extracted static WebGPU package without a GPU or
simulation API. Reloading clears results.

## Try the comparison

The default is a balanced coherent state with N=40, J=U=bias=0 Hz and a 500 ms
hold. Each of 64 preparations draws an initial phase offset within ±0.3 rad and
a bias offset within ±1 Hz. Both distributions are independent and uniform.
The bias stays constant throughout each realization. Seed 17 reproduces the
same offsets; changing the seed generates a different finite ensemble.

At 500 ms, the default gives mean individual coherence 1 and ensemble coherence
0.0153198. The infinite-ensemble guide is zero there, up to roundoff. The small
finite-ensemble remainder is sampling variation, not numerical decoherence.
The left-count distribution is unchanged: mean 20, variance 10 atoms².

Set both variation ranges to zero to recover the ideal reference. **Add
interactions** stages U=1 Hz, so the individual states also undergo coherent
interaction dynamics. **Use prepared settings above** copies the manual
experiment's applied configuration, not pending edits. Click **Run preparations**
to apply any changes. Pause/resume operates between completed preparations;
Cancel keeps the completed prefix for inspection and export. Invalid settings
preserve the previous result.

## Model, normalization and units

The Hamiltonian, occupation basis and normalized initial states are unchanged
from [the two-mode model](TWOMODE.md). With n=nL and fixed total N:

```text
H/h = -J (aL† aR + aR† aL) + U (n - N/2)² - bias (n - N/2)
```

J, U and bias are in Hz. U corresponds to the on-site pair convention
U/2 [nL(nL-1)+nR(nR-1)], after removing a constant. Positive bias raises the
right well. Evolution uses exp(-i 2π (H/h) t), with t in seconds; UI times are
milliseconds. Each conditional state has sum |c_n|²=1. Spectral propagation
does not renormalize the evolving state.

For M completed preparations, the mixture is
rho = (1/M) sum_r |psi_r><psi_r|. We average probabilities and observables,
never the complex occupation amplitudes. Define q_r=2<aL†aR>_r/N. The two
coherence readings are different operations:

- Mean individual coherence: (1/M) sum_r |q_r|.
- Ensemble coherence: |(1/M) sum_r q_r|.

Vectors of similar length can point in different directions and largely cancel.
This does not imply that each conditional pure state has lost coherence.
With interactions, individual first-order coherence can also change unitarily.
Neither reading is a simulated single-shot camera fringe fit.

The final mixture count probabilities are mean_r P_r(n). The variance obeys:

```text
Var_mixture(n) = mean_r Var_r(n) + mean_r (mean_r(n) - mean_mixture(n))²
```

The first contribution is average within-preparation quantum variance; the
second is variation of preparation means. These are population moments of the
displayed empirical mixture, with divisor M. At J=0, the Hamiltonian is diagonal
in n: phase/bias variation changes no P_r(n), so the second term is zero up to
roundoff. At nonzero J, these variations can affect the count probabilities.

## Analytic guide and finite sampling

For J=0, phase offset alpha_r and bias offset beta_r give exactly:

```text
q_r(t) = q_ideal(t) exp(i alpha_r - i 2π beta_r t)
q_ensemble(t) = q_ideal(t) mean_r exp(i alpha_r - i 2π beta_r t)
```

This also holds with the same nonzero U in every preparation. For independent
uniform offsets alpha in [-A,A] rad and beta in [-B,B] Hz, the infinite-ensemble
coherence is C_ideal(t) |sinc(A) sinc(2πBt)|, with sinc(x)=sin(x)/x and sinc(0)=1.
The guide is unavailable for J≠0. A finite sample need not match it exactly;
in particular, taking the magnitude of a finite complex average leaves a
positive remainder near a zero of the infinite mean.

Every realization is evaluated at 101 equally spaced physical times. This is
plot sampling, not an integration step. Shorten the duration to inspect faster
oscillations. Frame rate does not set simulation time.

The reproducible unsigned 32-bit generator updates
r=(1664525*r+1013904223) modulo 2^32 and maps u=(r+0.5)/2^32.
Two successive draws per realization give offsets (2u-1)A and (2u-1)B,
including when a range is zero. Phase is wrapped modulo 2π. This deterministic
pseudorandom generator is a teaching sampler, not a laboratory noise model.

Limits: 2–128 preparations, A in [0,π], B in [0,5] Hz and an unsigned 32-bit
seed. The existing two-mode configuration limits still apply. The whole bias
range must lie within ±20 Hz; samples are never clipped or rejected.

## Export and independent verification

**Export ensemble JSON** uses `coldatomlab-preparation-v1`. It includes the
plan, completion status, ideal reference, offsets/configurations, every final
complex state, 101-point conditional histories and aggregate probabilities and
histories. It supports complete ensembles and nonempty cancelled prefixes.
**Export ensemble CSV** contains aggregate history plus applied settings;
it cannot substitute for the full replay data.

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-preparations.json
```

Python regenerates the offsets and independently evolves each state using
NumPy diagonalization. It checks configurations, final states, histories and
mixture observables. Scalar/array comparisons use absolute tolerance 5e-8;
phase differences are wrapped. Final complex-state L2 error must be below
5e-8 and norm drift below 1e-9. This verifies the declared numerical model,
not the physical validity of the two-mode approximation or the noise model.

Numerical verification: 191 repository tests passed, including 40 preparation
tests. New coverage includes zero variation, exact finite-sample factorization,
infinite-ensemble guide, count-variance decomposition, seeded reproducibility,
uniform statistics and sampling convergence, interacting/coupled/Gaussian/Fock
states, largest supported N, cancelled prefixes and tampered exports.

Browser verification is separate: Chrome in headless mode exercised
the local app and extracted static package, presets, copying applied settings,
run/pause/resume/cancel, seeded repeats, invalid-input recovery, JSON/CSV,
manual/pin isolation, dashboard persistence and widths 1440/390/320 px.
Independent replay of the default browser export had maximum complex-state
L2 error 1.10e-15; the coupled eight-preparation example had 1.61e-14.
Generated evidence is excluded from Git under `artifacts/preparation/`.

```powershell
uv run pytest tests/test_preparation.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.preparation_browser_check
```

## Provenance and limits

[Gross, J. Phys. B 45, 103001 (2012), section IV.3](https://arxiv.org/html/1203.5359v1#S4.SS3)
discusses differential energy shifts and technical phase noise. It motivates
distinguishing shot-to-shot offsets from noise varying during a single hold.
Our uniform distributions and parameter values are explicit teaching choices;
they are not fitted experimental distributions or a reproduction of published
data. The analytic guide follows from our stated distributions.

N is fixed. There is no atom loss, temperature model, continuous stochastic
drive, detector noise or 3D spatial evolution. Each realization is a unitary
conditional pure state; averaging makes a statistical mixture. The manual
**Sample atom counts** panel instead draws quantum outcomes from one fixed
state. The [3D scan](SCANS3D.md) repeats detector exposures on frozen fields.
These three kinds of repetition answer different questions.
