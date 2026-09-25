# Two-mode quantum coherence lab (v0.10)

## Experiment and controls

Open `quantum.html` from the experiment library, sidebar or standalone GPU page.
Experiment links use the same tab. The Cold Atom Lab logo returns to the local
experiment library or, in the static package, its 04/05 library. Moving between
pages starts a fresh experiment; exported records retain runs for later replay. The page uses
only local static assets and browser float64 arithmetic. There is no GPU, Python
simulation request, remote font or external script dependency.

Four recipes stage settings; **Prepare experiment** applies them:

| Recipe | Initial state | J / Hz | U / Hz | Duration / ms |
| --- | --- | ---: | ---: | ---: |
| Watch atoms tunnel | All 40 atoms left | 5 | 0 | 100 |
| Let coherence evolve | Balanced coherent binomial, N=40 | 0 | 1 | 500 |
| Narrow the number spread | Balanced Gaussian amplitudes, N=40, sigma=1.5 | 0 | 1 | 500 |
| Exactly half in each well | Fixed occupation, 20 left and 20 right | 0 | 1 | 500 |

Every recipe has zero bias and zero input phase. These are teaching parameters,
not fits to a paper. Number narrowing is prescribed in the initial state; no
adiabatic barrier ramp, cooling or squeezing preparation is simulated.

Run displays 200 equally spaced physical times. Pause holds the state; Step
advances one display interval; Reset restores the **applied** initial state even
if the form has pending edits. The final time is exact. Playback cadence changes
wall-clock speed only. Fast physical changes can be undersampled by the history
plot; shorten the duration to inspect them. State evaluation itself has no
time-stepping approximation.

Pin preserves an immutable complete record, including that run's settings, time,
history and any sampled counts. Dashed probability and history curves show the
reference on shared axes; references with different N or durations retain their
own coordinates. Pins survive preparation/reset within the tab, but not reload.

## Hamiltonian and normalization

The occupation basis is ordered `n_left=0,...,N`. State vector component c[n]
multiplies |n,N-n>, and sum |c[n]|^2 = 1. N is a fixed integer from 2 to 100;
there are N+1 many-body amplitudes, despite retaining only two spatial orbitals.

With m = n_left-N/2:

```text
H/h = -J (a_L† a_R + a_R† a_L) + U m² - delta m
diagonal[n] = U (n-N/2)² - delta (n-N/2)
off_diagonal[n,n+1] = -J sqrt((n+1)(N-n))
c(t) = exp[-i 2 pi (H/h) t_seconds] c(0)
```

J, U and delta are in **Hz**, rather than angular-frequency units. Time controls
and exports use ms and convert to seconds for propagation. Positive delta raises
the right-well energy, so its one-particle term is delta(n_right-n_left)/2.

The on-site pair convention is U/2 [n_left(n_left-1)+n_right(n_right-1)]. At fixed
N this is U m² plus the constant U(N²/4-N/2), which is removed everywhere,
including the exported complex-state phase and energy diagnostic. U does not
include N or N-1. The controls allow repulsive U from 0 to 2 Hz, J from 0 to 20 Hz,
bias from -20 to 20 Hz, and duration from 1 to 1000 ms. They are independently
chosen effective coefficients, not inferred from a 3D GPE or atomic species.

Initial amplitudes before explicit preparation normalization are:

- Coherent: sqrt[choose(N,n) p^n (1-p)^(N-n)] exp[i(N-n) phi].
- Gaussian: exp[-(n-Np)^2/(4 sigma^2)] exp[i(N-n) phi].
- Fock: only n=floor(Np+0.5) is occupied. The input phase is physically irrelevant
  for this single occupation component, and its form control is disabled.

Here p is the input left fraction and phi is the right-minus-left orbital phase.
The finite Gaussian truncates at n=0,N, so its actual mean and variance must be
calculated rather than assumed to equal Np and sigma². The coherent p=0 and p=1
limits are prepared without logarithmic singularities.

## Observables and measurements

All plots derive from the complex occupation state:

```text
P(n) = |c[n]|²
mean_left = sum n P(n)
variance_left = sum (n-mean_left)² P(n)
cross = <a_L† a_R> = sum conj(c[n+1]) c[n] sqrt((n+1)(N-n))
C = 2 |cross| / N
phase = arg(cross), available only when C > 1e-8
number_noise_ratio = variance_left / [N p_obs (1-p_obs)]
p_obs = mean_left / N
```

The noise ratio is unavailable when its denominator is at most 1e-8. It compares
with the binomial variance at the **observed** mean population, avoiding a false
number-squeezing interpretation for an ordinary unbalanced coherent state. It
is not a spin-squeezing parameter or entanglement witness. C includes population
balance as well as phase coherence; for a pure coherent state it is
2 sqrt[p(1-p)]. In particular, all atoms in one well gives C=0.

C and its phase are first-order moments, not a phase probability distribution,
single-shot fringe fit or simulated absorption image. The Fock preset has C=0;
this statement does not predict the absence of fringes in an individual spatial
interference measurement, which this page does not model.

**Sample atom counts** draws 1–10000 independent ideal number measurements from
the frozen P(n). Each shot represents the same preparation and hold repeated on
a fresh system. There is no detector noise, loss, continuous measurement or
post-measurement evolution. The displayed state is unchanged. Advancing or
resetting clears the sampled histogram; a pin keeps its own histogram.

An unsigned 32-bit seed initializes the reproducible LCG
`r=(1664525*r+1013904223) mod 2^32`, with `u=(r+0.5)/2^32` mapped through the
occupation cumulative distribution. This is a teaching sampler, not a source
of cryptographic randomness. Equal settings/time/seed reproduce the same counts.

## Numerical method and independent replay

`web/twomode.js` contains the DOM-independent browser solver. It diagonalizes the
real symmetric Hamiltonian using cyclic Jacobi rotations in float64. Rotations
stop below `2e-15 * scale`, with scale=max(1,max absolute matrix entry) and at most
60 sweeps. Before accepting preparation it checks the maximum component residual
`|HV-VE|/scale` and orthogonality error `|V^T V-I|` are each below 1e-11.

Propagation projects the initial complex amplitudes into this eigenbasis,
multiplies by the spectral phase and reconstructs the state at the requested
time. It does not repeatedly propagate from the previous display frame and never
renormalizes during real time. A norm deviation above 1e-9 stops the calculation.
Energy uses the same offset-removed Hamiltonian. Norm conservation alone is not
an accuracy test; analytic dynamics and independent complex states are checked.

`coldatomlab/twomode.py` uses NumPy's independent Hermitian eigensolver, independent
initial amplitudes and observable formulas. The replay command dispatches schema
`coldatomlab-twomode-v1` to this reference:

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-quantum.json
```

JSON records the basis/unit convention, complete current and optional pinned
configs, display-step index, final real/imaginary occupation amplitudes, complete
final diagnostics, each display-time history row, and optional seed/counts.
Replay checks the exact expected time sequence and history length, each saved
observable (absolute tolerance 5e-8), final complex-state L2 below 5e-8, and norm
drift below 1e-9. Phase comparisons are wrapped and preserve unavailable values.
Counts are regenerated exactly from the validated **exported** probabilities,
because a random threshold close to a bin boundary need not fall on the same
side for two independent eigensolvers. This is separate from independently
verifying those probabilities against the Python state.

CSV exports both current and pinned histories with their model parameters; it is
an analysis table, not a substitute for the complete JSON replay record.

## Analytic references and validation evidence

For an initially left-localized noninteracting state with zero bias,
`<N_left>/N = cos²(2 pi J t)`. The single-particle energy splitting is 2hJ;
the population period is 1/(2J). At J=5 Hz the population is all right at 50 ms
and returns left at 100 ms. With bias, letting Omega=sqrt[J²+(delta/2)²],
`p_left = 1-(J/Omega)² sin²(2 pi Omega t)`. The occupation distribution is binomial
with variance N p_left(1-p_left).

For a balanced coherent state in isolated wells (J=0),
`2 <a_L†a_R>/N = exp[i(phi-2 pi delta t)] cos(2 pi U t)^(N-1)`.
Number probabilities stay fixed. Finite-system coherence can collapse and revive;
this is not irreversible environmental decoherence. For N=40, U=1 Hz and zero
bias, C is zero at 250 ms and returns to one at 500 ms, with a pi phase change.

The dedicated numerical tests cover nine reference configurations including
N=2, odd N, biased/interacting and degenerate Hamiltonians, narrow boundary states
and N=100/J=20/U=2/bias=-20 at 1000 ms. They check complex states against Python,
norm and energy, analytic tunnelling with and without bias, isolated phase sign,
collapse/revival, frozen P(n), binomial/Gaussian/Fock limits, exact time subdivision,
display-order independence, sample moments/seeds and invalid inputs. Tampering
checks alter amplitudes, probabilities, history, time, seed, counts, configuration,
basis, step and non-finite values. The dedicated suite has 39 passing tests.

Live browser evidence is separate: installed headless Chrome exercised actual
controls on the local app and an **extracted ZIP** with no simulation API requests
from the quantum page. It covered all four recipes, pause/step/reset, pending and
invalid settings, unchanged source state during sampling, equal/different seeds,
immutable comparison, both exports, undefined Fock phase, largest N preparation,
desktop and 390/320 px layouts without horizontal overflow, dashboard search and
same-tab entry links and logo-to-library return paths. Downloaded complete and partial runs were independently
replayed, including both 201-row comparison histories. Example complex-state L2
differences were 1.17e-15 (Gaussian comparison), 5.88e-15 (pinned coherent hold)
and 5.59e-14 (N=100 interacting browser run after one display step).

Reproduce the checks; browser servers are temporary and closed on exit:

```powershell
uv run pytest tests/test_twomode.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.twomode_browser_check
uv run python -m scripts.navigation_browser_check
```

Generated evidence lives outside version control in `artifacts/twomode/`, including
JSON/replay pairs, history CSVs, browser report and desktop/mobile screenshots.

## Paper provenance and physical limits

- [Estève et al., Nature 455, 1216–1219 (2008)](https://arxiv.org/abs/0810.0600):
  motivates inspecting atom-number difference together with relative-phase
  coherence in split condensates. The paper demonstrates experimental squeezing
  and entanglement; this page does not reproduce its lattice, atom number,
  preparation, measured squeezing or detection calibration.
- [Gross, J. Phys. B 45, 103001 (2012)](https://arxiv.org/abs/1203.5359):
  supplies the fixed-N collective-spin framework, coherent-state number noise
  and the need to distinguish number variance, mean spin/coherence and
  metrologically useful squeezing. Our displayed number-noise ratio is not the
  review's metrological squeezing criterion.
- [Smerzi et al., PRL 79, 4950–4953 (1997)](https://arxiv.org/abs/cond-mat/9706220):
  context for coupled two-mode population/phase dynamics and Josephson effects.
  This implementation retains the finite-N occupation state rather than evolving
  only mean-field population and phase equations. It does not claim a validated
  self-trapping benchmark against that paper.

The model assumes two fixed, orthonormal localized orbitals and conserves total
N. It omits higher spatial modes, interaction-driven orbital deformation, thermal
mixtures, environmental coupling, losses, 3D expansion and imaging. The chosen
J/U values do not establish that a real trap stays in the two-mode regime. There
is no spatial grid convergence claim: full occupation-basis convergence **within
two modes** cannot establish the validity of the spatial truncation. A later
coupling to a 3D orbital calculation or apparatus must be validated separately.
