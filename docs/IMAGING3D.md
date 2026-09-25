# Three-axis virtual absorption camera (v0.8)

The camera observes an immutable snapshot of the actual 3D numerical field. It works with the CPU reference and WebGPU backend, including the standalone static bundle. Acquisition and fitting use JavaScript double precision in the browser; this does not increase the precision of the underlying WebGPU float32 wavefunction. No simulation step, renormalization or change to the field occurs during capture.

## Try it

Choose **Camera-friendly pair · 2,000 atoms**, **Load settings**, **Prepare 3D experiment**, then **Run** to completion. Under **What would the camera see?**, capture ideal optics and pin the image. Try FWHM 4 µm, then 8 µm, or enable photon/read noise. Switch viewing axis to see which fringes survive projection. Capture requires a paused or completed run. Camera edits remain pending until capture; reset or preparation marks an existing image as a frozen earlier exposure.

The example is a declared noninteracting Rb-87 pair, N=2,000, initial right-minus-left phase 0.7 rad, 64³ cells over 32 a0, dt=0.004, and final time 3/omega0 = 15.9155 ms. It is a numerical teaching example, not a reconstruction of a published image or calibrated camera. Fewer atoms reduce optical depth; they do not alter this g=0 evolution.

## Projection and optics

The solver uses integral |psi|² d³X = 1, X=r/a0, a0=sqrt(hbar/(m omega0)), and g=4 pi N as/a0. The camera uses n_col=N integral |psi|² dX_los/a0² in atoms/µm², including the actual discretized norm. It never rescales the projection to force an atom count. Looking along z yields horizontal x/vertical y; along y yields x/z; along x yields y/z. Rows are vertical coordinates and plots place positive vertical coordinates upward.

The ideal resonant two-level Rb-87 D2 model uses lambda=0.780241209 µm, sigma0=3 lambda²/(2 pi), Isat=16.69 W/m², and s=I0/Isat. Transmission T solves

```
sigma0 n_col = -ln(T) + s (1-T).
```

Apply a normalized Gaussian **intensity** PSF with standard deviation FWHM/sqrt(8 ln 2) to T, using transparent exterior and a kernel truncated at six standard deviations. Average transmitted intensity over integer blocks of source cells, then sample the detector. Binning is 1/2/4/8/16 cells, requiring at least eight detector pixels per side. The minimum pixel pitch is the numerical grid spacing in physical units: this camera cannot recover subgrid structure. A PSF narrower than two source cells is explicitly warned as underresolved.

For pixel area A, pulse duration tp and quantum efficiency eta, expected reference electrons are R0=eta I0 tp A/(hc/lambda). Atom and reference frames have independent Poisson counts around R0 T_pixel and R0. Each frame also has independent zero-mean Gaussian read noise; a shared dark frame contains read noise only. All raw frames include a known 100-electron bias. Inversion uses dark-subtracted A and R:

```
n_est = [ln(R/A) + s (R-A)/R0] / sigma0.
```

If A or R is nonpositive, retain an invalid pixel (magenta), not zero density. Negative finite density estimates remain signed (blue); they are included in ROI sums. The square ROI selects pixel centers within the requested half-width; the strip selects vertical centers within half the requested strip width. Snapped bounds are displayed/exported. ROI count is unavailable if any ROI pixel is invalid. First-order count uncertainty propagates atom/reference shot noise and all three read noises, including the shared-dark covariance. At low counts the linear uncertainty approximation is unreliable; no fit phase confidence interval is claimed.

The model version `rb87-browser-camera-v1` specifies a deterministic 32-bit LCG, state=(1664525 state+1013904223) mod 2³², uniform=(state+0.5)/2³², Box–Muller normals without a spare sample, Knuth Poisson sampling below mean 30 and transformed rejection above it. Sampling proceeds row-major through the atom, reference and dark frames. This modest PRNG supports reproducible teaching demonstrations, not high-precision noise-tail metrology. It differs from the older 2D camera's NumPy generator.

## Image-only fringe estimate

The ideal binned density and reconstructed camera density are fitted **independently**. Each fit receives only horizontal pixel coordinates, the observed strip profile, and optionally estimated profile errors. It does not receive source phase, separation, time, wavefunction or the other profile.

The empirical fit is

```
z = (x-offset)/width
n_fit(x) = exp(-z²/2) [a0 + a1 z + a2 z² + b cos(k x) + c sin(k x)]
phase = atan2(c,b), period = 2 pi/k, fitted contrast = hypot(b,c)/a0.
```

There is no fitted constant background: dark-subtracted density has zero expected background. Allowing a free constant on this short ROI produced a degenerate envelope and unphysical contrast. The positive part of the measured profile supplies only initial center/width search scales; the fit itself retains signed data. The browser solves five linear coefficients by pivoted elimination and scans carrier/width/center, followed by five refinements. The independent Python implementation uses NumPy least squares.

Acceptance requires at least 20 valid samples, at least 2.5 cycles across the ROI, at least four pixels per period, positive envelope amplitude, fitted contrast 0.08–1.1, residual RMS/profile range <=0.12, and >=70% residual reduction relative to a refitted smooth envelope with the same width/center. The carrier must lie away from the search limits. With noise enabled its amplitude must exceed five times the largest estimated profile standard error. These are conservative demonstration gates, not a statistical confidence test. Fitted contrast is an empirical local carrier/envelope ratio and may slightly exceed one due to estimation error; it is not a clipped physical visibility.

Phase uses cos(k x − phase) at horizontal coordinate zero; it is distinct from the source mirror-weighted phase diagnostic. Along the split direction x, integration removes x-fringes; any horizontal fit would describe y modulation instead. Smooth projections, coarse pixels, strong blur, low signal or non-Gaussian interacting profiles may return **Unavailable**. The estimator is not guaranteed to recover a carrier from every valid condensate image. Blur changes the observed period and contrast as well as density: comparison is with the separately fitted ideal projection, not a forced theoretical answer.

## Papers and limits

- [Ketterle, Durfee & Stamper-Kurn (1999), Making, probing and understanding Bose–Einstein condensates](https://arxiv.org/abs/cond-mat/9904034): established absorption-imaging context and BEC observables.
- [Reinaudi et al. (2007), Strong saturation absorption imaging of dense clouds of ultracold atoms](https://arxiv.org/abs/0707.2930): saturation-corrected absorption relation. We use the ideal calibration factor alpha=1, not their apparatus calibration.
- [Shin et al., PRL 92, 050405 (2004)](https://doi.org/10.1103/PhysRevLett.92.050405): experimental motivation for splitting and interference, not these Rb-87 camera parameters. See [the separate source audit](SHIN_REFERENCE.md).

Gaussian intensity blur, uniform illumination, detector parameters, fitting gates and example settings are declared simplifications. Omitted effects include recoil and motion during exposure, defocus/coherent diffraction, optical pumping, detuning, multilevel structure, dark current, digitization/full-well clipping, technical fringes, multiple scattering, and a thermal cloud. Peak optical depth >4 and mean absorbed photons/atom >5 produce warnings. The default exposure can trigger the recoil warning even when the fit succeeds; successful numerical inversion does not certify a physically nondestructive measurement.

## Export and verification

**Export image** writes `coldatomlab-camera3d-v1`, including full source field/history, camera settings/seed, all three raw frames, axes/coordinates, recovered and ideal densities, ROI data, profiles and fits. With an image pinned it writes `coldatomlab-camera3d-comparison-v1` containing both immutable records. Matching detector axes are required to overlay pinned profiles; the table identifies pinned settings independently.

```
uv run python -m coldatomlab.replay path/to/coldatomlab-camera3d.json
```

Replay first verifies the source evolution (exact float64 replay or toleranced GPU-versus-CPU comparison), then independently reprojects the saved field and regenerates all numerical camera arrays/counts/bounds. Frame tolerance is atol=1e-8, rtol=2e-10, with equal invalid masks. Independent fit tolerances are 0.01 rad, 0.5% period, 0.01 contrast, curve rtol=1e-4/atol=1e-6, residual atol=1e-5; unavailable fits must remain unavailable with null measurements. Human-readable warning/reason text and page-local generation IDs are not evidence checked by replay.

## Verification evidence

Numerical checks cover all three projection orientations and atom integrals, ideal inversion, intensity-before-inversion binning, blur, blind synthetic phases 0/0.7/−1.2/3 rad, smooth/coarse/noisy rejection, invalid dark pixels, seeded frame repeatability, Poisson mean/variance at means 0.2/12/30/400, read-noise statistics, and tampered frames/axes. Synthetic phase error is required below 0.01 rad, period within 1%, and fitted contrast within 0.02. These tests do not establish experimental agreement.

Actual hardware Chrome browser checks separately exercise fresh WebGPU preparation/evolution, capture, immutable pin/comparison, seeds, axes, blur/binning, invalid-setting recovery, export, stale-source notice, fixed selector positions, and 390/320-pixel layouts. Complete source exports before/after acquisition are identical. The CPU browser path is tested separately. Representative 64³ WebGPU results at t=15.9155 ms:

| Acquisition | Image phase / rad | Fitted period / µm | Fitted contrast |
| --- | ---: | ---: | ---: |
| Ideal z projection | 0.6960 | 6.8814 | 0.8997 |
| FWHM 4 µm, no noise | 0.6901 | 8.1140 | 0.3085 |
| FWHM 8 µm | Unavailable | Unavailable | Unavailable |
| Ideal optics, noise seed 17 | 0.7265 | 6.8388 | 0.8541 |
| View along x | Unavailable | Unavailable | Unavailable |

The ideal image matches the separately fitted ideal projection to rounding, but the empirical carrier/envelope fit has model bias: 0.6960 differs from input 0.7 rad. Camera acquisition/export in the desktop browser workflow took about 0.4 s for this example; this includes UI/download overhead and is not a GPU speed benchmark.

Run the browser check against a temporary local server or extracted static package:

```
uv run python -m scripts.camera3d_browser_check --url http://127.0.0.1:8766/gpu.html
uv run python -m scripts.camera3d_browser_check --url http://127.0.0.1:8766/#lab3d --cpu
```

Evidence and screenshots are written under ignored `artifacts/camera3d/`. Static packaging includes both camera scripts; a plain static host suffices for the browser-only path. No public deployment is performed.

Release verification: **97 pytest tests passed**, Ruff passed, and changed JavaScript syntax checks passed. The extracted static ZIP completed the same camera workflow with zero simulation API requests and zero page errors; the full dashboard regression also passed. The representative GPU source's L2 wavefunction difference from the independent CPU reference was 1.433e-4, below the pre-existing 0.005 tolerance. This verifies the implemented model, not agreement with an experimental apparatus.
