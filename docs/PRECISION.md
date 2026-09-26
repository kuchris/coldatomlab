# Repeated phase precision benchmark (v0.15)

Open **Quantum coherence → Precision benchmark ↓ → Run precision benchmark**.
This extends [Phase readout](READOUT.md) by repeating whole scans with new counts.
It runs in the existing dashboard and the extracted static ZIP without a GPU.

## Three comparisons

The default input is a balanced coherent state at phase 0.7 rad, with no hold,
U=bias=0, readout J=10 Hz, zero duration error and seed 17. A full scan has 12
equally spaced reference phases. Repeat the complete scan 100 times in each case:

| Case | Atoms per cloud N | Shots per reference setting S | Clouds per scan per arm K S | Atom uses per scan per arm N K S |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 20 | 64 | 768 | 15,360 |
| More atoms | 80 | 64 | 768 | 61,440 |
| More shots | 20 | 256 | 3,072 | 61,440 |

Every case has ideal and finite readout arms with separate count draws. At zero
bias/U and calibrated duration their probabilities agree; their realized count
histograms need not agree. Default total workload is 921,600 measured cloud
outcomes across all cases, settings, arms and repetitions. Atom uses count N
times the number of newly prepared clouds, not distinct particles tracked across
measurements. Finite readout consumes additional time as defined in v0.14; this
is an atom/shot comparison, not equal wall-clock laboratory cost.

- **Check counting precision** stages these calibrated settings.
- **Precise but biased** retains delta=8 Hz and a +20% pulse-duration error.
  Compare scatter with bias: increasing resources cannot remove this systematic
  readout error from an uncorrected estimator.
- **No identifiable phase** stages a fixed-occupation state. It has no incoming
  first-order coherence, so true-phase error, bias and RMSE are unavailable.

Choose the case below the table to inspect its repeated-error histogram. Tables
scroll horizontally on narrow screens. Presets preserve the current repetition
count and seed; settings apply on Run. Advanced controls retain coherent,
prescribed Gaussian or Fock preparations, arbitrary initial left fraction,
interactions, an isolated hold and an optional ideal midpoint echo. Changing N
changes the many-body state and can change interacting dynamics; do not interpret
every arbitrary-state comparison as a clean shot-noise scaling experiment.

Pause occurs between completed repetitions, each containing all three cases and
both arms. Cancel retains that balanced prefix. Fewer than two resolved estimates
have no scatter statistic. Invalid input preserves the previous result. Earlier
panels, pins and dashboard navigation remain independent. Reloading clears results.

## Physics and new sampling

The Hamiltonian, units, normalization, phase shift and ideal/finite mixing are
unchanged from v0.14. In basis |n,N-n>, sum |c_n|^2=1,

```text
H/h = -J(aL†aR+aR†aL) + U(n-N/2)² - delta(n-N/2)
c_n -> exp[-i(N-n)(alpha+pi/2)] c_n before mixing
z_ideal(alpha) = Re[q exp(-i alpha)], q=2<aL†aR>/N
tau_finite = (1+duration_error)/(8J) seconds
```

J, U, delta are in Hz and displayed time is ms. U uses the on-site pair
coefficient convention with its fixed-N constant removed. Positive delta raises
the right mode. Holds have J=0. Interactions and bias remain on during finite
mixing. The optional hold echo and reference-phase gate are instantaneous
prescribed operations. No real-time renormalization is performed.

The deterministic incoming and output states are computed once for every case
and reference setting. Each repetition then draws fresh ideal number counts
from those probabilities and fits a phase anew. This is mathematically the same
as identically preparing and propagating the deterministic state for every shot;
it does not model technical preparation variation. No sampled outcomes or fitted
phases are reused as repeated observations.

LCG recurrence r=(1664525*r+1013904223) mod 2^32 and u=(r+0.5)/2^32 is unchanged.
Blocks occupy one non-overlapping stream in this order:

1. Repetition index.
2. Baseline, more atoms, more shots.
3. Reference setting index.
4. Ideal, finite arm.
5. Shots within the setting/arm.

Integer affine skip-ahead locates each trial and block seed without replaying
earlier random draws. Python uses independent integer arithmetic and sampling.
Accepted workloads use at most 16 million draws, below the generator period.
Limits are 20–300 repetitions, 8–32 settings, 16–4096 shots per setting, N up to
100, strictly larger comparison N and comparison shots. Exceeding limits is
rejected rather than clipped.

## Precision, accuracy and uncertainty

Each scan uses the v0.14 unweighted first-harmonic count estimator and visibility
gate. It receives empirical count means and variances, never true q. Save phase,
local phase SE, contrast, residual and resolved status for every scan. Metrics
below condition on resolved estimates; attempted and unresolved counts remain
visible. Conditioning on rare surviving fits can be misleading when most scans
are unresolved. This benchmark does not silently call missing phase zero.

For resolved estimated phases theta_j, define v=mean(exp(i theta_j)), R=|v|.

- **Circular bias**: wrap(arg(v)-true phase). If R<=1e-8, the center is undefined.
- **Circular scatter**: sqrt(-2 log R). It measures concentration around the
  estimated center, not closeness to truth, and has finite-sample uncertainty.
  It is unavailable for R<=1e-8 rather than presenting an infinite value.
- **Wrapped RMSE**: sqrt(mean(wrap(theta_j-true phase)^2)). It includes bias and
  random error, with errors wrapped to [-pi,pi].
- **RMS reported SE**: sqrt(mean(SE_j^2)). The local delta-method SE is inherited
  from each count scan; it does not include systematic pulse distortion.
- **Scatter/SE**: circular scatter divided by RMS reported SE. Near one is useful
  evidence for calibration in a localized, high-signal distribution, not proof
  for arbitrary low-coherence or non-Gaussian cases.
- **Within one SE**: resolved fraction satisfying |wrapped error|<=SE_j. Roughly
  68% is expected for a well-calibrated unbiased Gaussian error model. This is
  an empirical diagnostic, not a claimed confidence interval or a guarantee.
- **Noiseless pulse bias**: model-only fitted readout phase minus the incoming
  coherence phase. This separates deterministic distortion from count noise.

Histograms use shared bins in wrapped error, with heights divided by all completed
repetitions. Their mass is therefore the resolved fraction. The x range adapts
to each case and includes zero; dotted lines mark noiseless bias when in range.
If the incoming phase is undefined, error histograms, bias and RMSE are absent.
Counts, unresolved outcomes and any apparent fits remain available in JSON.

## Analytic precision guide

For a balanced coherent state with U=0, ideal readout gives independent binomial
counts at each setting, with z_k=cos(phi-alpha_k) and
Var(zbar_k)=sin²(phi-alpha_k)/(N S). The full-period fit uses coefficients
a=(2/K)sum zbar_k cos(alpha_k), b=(2/K)sum zbar_k sin(alpha_k).

At high signal and large shot count, propagating that covariance through atan2
gives

```text
Var(phi_hat) ≈ 4/(K² N S) sum_k sin⁴(phi-alpha_k)
             = 3/(2 N K S), for the equally spaced K>=8 grid.
sigma_phi   ≈ sqrt[3/(2 N K S)].
```

The default guides are 0.009882 rad for baseline and 0.004941 rad for each larger
resource case. The guide is specific to this full-period unweighted estimator.
It is **not** the optimal local standard quantum limit 1/sqrt(N K S). Its
sqrt(3/2) prefactor must not be interpreted as solver error, or removing it as a
quantum advantage. The guide is only shown for balanced coherent U=0 inputs and
applies to ideal mixing. Interacting, imbalanced and prescribed number-narrow
states require their own sensitivity analysis.

## Export and verification

JSON schema `coldatomlab-precision-v1` includes model states once, recipes, every
trial's raw count histograms and block seeds, fits and summaries. CSV contains
per-trial estimates and applied physical/count settings; JSON is required for
full independent replay. Browser v0.15 refactors deterministic readout-state
formation into a reusable function without changing v0.14 physics or samples.
The v0.14 JSON version remains replayable.

```powershell
uv run pytest tests/test_precision.py tests/test_readout.py -q
uv run python -m scripts.package_webgpu
uv run python -m scripts.precision_browser_check
uv run python -m coldatomlab.replay path/to/coldatomlab-precision.json
```

Independent Python replay recomputes output states with NumPy spectral evolution,
fresh counts from integer seeds, least-squares fits and circular statistics.
The complex-state L2 gate is 5e-8 and norm-drift gate is 1e-9. State computation
is independent of frame rate; browser rendering only displays finished results.

## Literature and physical limits

[Gross et al., Nature 464, 1165–1169 (2010)](https://www.nature.com/articles/nature08919)
demonstrated nonlinear atom interferometry with phase sensitivity beyond the
classical precision limit. It motivates a future controlled comparison of
metrological resources and interaction-generated squeezed states. This version
establishes a count-estimator baseline; it does not reproduce that apparatus,
its squeezing protocol or its reported enhancement.

This remains a fixed spatial two-mode model with ideal number detection and
identically prepared pure states. There is no detector noise, atom loss,
technical preparation drift, continuous environmental noise, higher orbitals or
3D expansion. Number narrowing alone is not evidence of improved sensitivity.

## Validation evidence

Numerical: all 333 repository tests passed in 146.00 seconds, including 30
precision tests and 33 readout regression tests. They cover
LCG skip-ahead against sequential draws (including 15,999,999 steps), disjoint
trial/case/setting/arm blocks, fresh seeded samples, independent state/count/fit
replay, circular wrapping across pi, undefined phase, invalid workloads, tampered
exports and v0.14 export compatibility. Full-state oracle cases include N=99/100,
U=2 Hz, bias=20 Hz and a 1000 ms hold. A separate 200-scan experiment checks
empirical scatter against the analytic guide, reported SE and N/shot scaling.
A biased-pulse test checks that RMSE remains large even when scatter is small.

Live browser: installed Chrome passed local and extracted-static checks for
100 full-scan repetitions, all three cases and both arms, presets, case selectors,
fresh seed changes, deterministic reruns, pause/resume/cancel, invalid-workload
preservation, downloaded JSON/CSV and independent replay. Earlier manual,
preparation, echo, finite-pulse and readout exports were unchanged. Dashboard
navigation preserved the benchmark without a new tab. All six populated panels
fit within the iframe on 1440, 390 and 320 px layouts, with no document horizontal
overflow. Wide tables scroll inside the panel. Desktop and mobile screenshots
were visually inspected; compact mobile plot labels avoid overlap. No page errors
or quantum-iframe solver API requests occurred.

With the default seed and 100 scans, ideal circular scatter was 0.009030 rad
(baseline), 0.004972 rad (more atoms) and 0.004979 rad (more shots). Corresponding
RMS reported SE values were 0.009825, 0.004949 and 0.004940 rad. These are finite
Monte Carlo results, not exact expected values. The browser's biased example
(seed 18 in the scripted check) had finite baseline bias -0.540236 rad and scatter
0.009970 rad; its more-shots arm had bias -0.539672 rad and scatter 0.004928 rad.

Independent replay of the actual default browser export gave maximum full-state
L2 difference 7.90e-14 and norm drift 3.11e-14. These validate this specified
numerical and ideal-count model, not experimental accuracy. Evidence files are
under ignored `artifacts/precision/`; temporary validation servers close after
the check. The user's port-8765 server is not started by validation.
