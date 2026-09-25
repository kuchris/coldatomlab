# Reduced ballistic fringe benchmark

## Question and scope

How does a controlled free-particle calculation compare with the fringe period reported in Shin et al., PRL 92, 050405 (2004), Fig. 2? The [reference audit](SHIN_REFERENCE.md) identifies the primary sources and differences from the actual experiment. This module is separate from the interactive effective-2D GPE and Rb-87 camera. Neither those teaching presets nor the experimental apparatus are recalibrated here.

## Inputs and conventions

The separation is 13 um and time of flight is 30 ms, from the paper. Na-23 mass is `22.9897692820 u`, from [NIST](https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=Na), converted with the repository's atomic mass unit constant. Planck's constant is exact in SI. These give mass `3.8175410023e-26 kg` and a point-source period of `40.054399168 um`. The reported values `39.8 um` (quoted theory) and `41.5 um` (measurement) are retained separately; the paper does not establish why the rounded inputs do not yield its quoted prediction.

The initial x wavefunction is the coherent sum of equal Gaussian amplitudes centered at `+-d/2`, each with amplitude `exp(-(x-x0)^2/(4 sigma^2))`. Here sigma is an individual packet's **density RMS width**. Normalize once so `integral |psi|^2 dx = 1`, using x in um. Marginal density therefore has units `probability / um`; it is not atoms/um or an absorption image. Equal phase and zero interactions are declared assumptions.

Use `sigma = sqrt(hbar/(2 m 2 pi fr)) = 0.597865834 um`, where `fr = 615 Hz` is a reported trap frequency. The noninteracting ground-state interpretation is our surrogate choice, not the measured interacting condensate width. There is no adjustable parameter fitted to the experimental 41.5 um.

In a separable free-particle state, normalized transverse factors integrate to one. A one-dimensional Fourier calculation of x thus suffices for the marginal density of this **separable surrogate**. It does not model an interacting 3D cloud by freezing its transverse confinement.

## Propagation and independent reference

Fourier propagation uses `psi(t) = IFFT(FFT(psi(0)) exp(-i hbar k^2 t/(2m)))`, with k in inverse meters. The default is 4096 points across 1200 um. No normalization is applied during propagation. The free kinetic operator is exact in Fourier space; repeating two half steps checks operator composition, not the time accuracy of an interacting GPE.

Independently evaluate each free Gaussian with complex width `q = 1 + i hbar t/(2 m sigma^2)`: its amplitude is `q^(-1/2) exp(-(x-x0)^2/(4 sigma^2 q))`. The exact interference carrier period is

```text
lambda_gaussian = h t/(m d) * [1 + (2 m sigma^2/(hbar t))^2].
```

This is an analytic model check. It is not another measured value. The point-source limit drops the square-bracket correction.

## Measurement from the computed density

Fit samples within a fixed `[-200, 200] um` aperture to

```text
A exp(-(x-xc)^2/(2 s^2)) [1 + B cos(2 pi x/lambda + phi)].
```

All six parameters are fitted with bounded SciPy least squares. Numerical profile peaks initialize lambda and phase; profile moments initialize xc and s. Neither experimental spacing nor the analytic formula is passed into the fitter. At least three prominent fringes are required. The exact two-packet density has a slightly different envelope from this fitting function, so a finite fit residual/bias remains even with an accurate wavefunction. No statistical confidence interval is claimed for noiseless fitting.

The base period is **40.057375321 um**; the exact finite-Gaussian carrier is **40.057379727 um**. Their approximately `-4.41e-6 um` difference is fit/model bias. The relative density-fit L2 residual is **0.1461%**. None of these are experimental uncertainties.

## Numerical evidence and comparison

- Norm error is below `1e-12`; field L2 error against the Gaussian reference is about `2.96e-9` on the base domain.
- Doubling the grid at fixed domain changes fitted spacing by about `5.38e-9 um`.
- Doubling the domain at fixed grid spacing changes fitted spacing by about `5.90e-13 um`; the field L2 error drops to about `1.37e-14`.
- Two half steps change fitted spacing by about `2.06e-13 um`.
- Half/double packet-width sensitivity gives periods about `40.054557` and `40.100252 um`. The half-width case uses a larger 2400 um domain and 16384 points to contain its faster expansion. These are alternative surrogate assumptions, not uncertainty bars or numerical refinements.

The numerical fit differs from the published measurement by **-1.442624679 um**, or **-3.476204%**, using `(fit - measurement)/measurement`. Without measurement uncertainty or the raw experimental profile, no goodness-of-fit statistic or experimental agreement claim follows. The numerical checks pass; the complete experiment remains unreproduced.

## Reproduce and inspect

```powershell
uv run python -m coldatomlab.benchmark
uv run python -m scripts.benchmark_figure
uv run pytest tests/test_benchmark.py -q
```

The JSON report and scientific figure are generated in ignored `artifacts/`. In the running lab, **Paper benchmark** computes the same report through `/api/benchmark` and offers a JSON download. Its cached, read-only calculation is independent of browser experiment sessions. `scripts/benchmark_browser_check.py` verifies the actual display/download, failed-request recovery, preserved workspace/reference, direct link, and mobile layouts. No laboratory hardware or experimental camera calibration has been verified.
