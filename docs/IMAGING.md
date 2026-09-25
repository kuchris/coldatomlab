# Virtual absorption imaging

This camera observes a frozen copy of a prepared Rb-87 laboratory run along z. The GPE's axial wavefunction is normalized, so its planar number density is already the column density seen by this camera: ncol = N |psi|^2 / a0^2. No extra integration over x or y is applied. Acquisition never advances, renormalizes or perturbs the source wavefunction; real resonant absorption imaging can be destructive.

## Forward model

Assume a resonant, closed two-level cycling transition, uniform probe intensity and known optical calibration. Use lambda = 780.241209 nm, sigma0 = 3 lambda^2 / (2 pi), and a rounded Isat = 16.69 W/m^2. There is no detuning, polarization error or optical pumping model. The current camera therefore requires physical Rb-87, rather than silently assigning these constants to a custom species.

For input saturation s0 = I0/Isat, solve for transmission T:

```text
OD = sigma0 ncol = -ln(T) + s0 (1-T)
u = -ln(T):  u + s0 (1-exp(-u)) = OD
```

Bisection in u avoids underflow inside a logarithm. In the weak-probe limit the relation reduces to Beer–Lambert transmission. This is the ideal alpha=1 limit of Reinaudi et al.'s saturation-corrected relation; the app does not infer the calibration factor from data.

Apply a normalized Gaussian **intensity** PSF to the transmitted light, then integrate over each square camera pixel. The PSF standard deviation is FWHM / sqrt(8 ln 2). Convolution uses transparent space beyond the simulated field, not periodic wraparound. This approximate intensity-transfer model does not propagate a coherent optical field or account for defocus and aberrations. A FWHM below two solver cells is flagged as under-resolved.

Object-space pixel pitch is an integer binning factor times the solver's physical grid spacing. Available factors are 1, 2, 4, 8 and 16, with at least eight detector pixels per side. These are physical pixels integrating photons **before** independent read noise, not software summation of already-read pixels. Pixel centers are the means of the covered solver coordinates. The field edge lies half a grid cell beyond its first/last sample, so its center is offset from zero by half a solver cell. The UI reports actual snapped ROI and strip boundaries.

For pulse duration tau, photon fluence F and quantum efficiency eta:

```text
F = I0 tau / (h c / lambda)
mu_ref = eta F pixel_area
mu_atoms = mu_ref * pixel-averaged blurred transmission
```

Each atoms/reference exposure draws independent Poisson photoelectrons and independent zero-mean Gaussian read noise. The dark exposure contains read noise and a known constant 100-electron bias; dark current is zero. The same measured dark frame is subtracted from both signal frames, creating correlated subtraction noise. Noise-off mode uses exact expected counts and the exact bias. Quantum efficiency is Poisson thinning, not an extra independent noise term. Exported frames are electrons including bias, with no gain conversion, ADC quantization or full-well clipping.

The seeded NumPy generator makes settings + source state reproducible. Reusing the seed produces the same exposure; change it for another realization. A common seed across different Poisson means is not a physically correlated acquisition model.

## Image-only reconstruction and measurements

Let A = atoms_frame - dark_frame and R = reference_frame - dark_frame. Reconstruct:

```text
OD_est = ln(R/A) + s0 (R-A)/mu_ref
ncol_est = OD_est / sigma0
```

Pixels with A <= 0 or R <= 0 are masked, shown magenta, and exported as null. Negative reconstructed densities from valid counts are retained and shown blue; clipping them would bias the atom count upward. Model density is never used to choose valid camera pixels or to fit a measurement.

The user sets a square ROI centered at the origin and a horizontal profile-strip width. They snap to camera pixel centers. At least four pixels per ROI side and one strip row are required. Number is the signed density sum times pixel area. Widths are centered second moments, with no PSF deconvolution or Gaussian fitting. Model moments use all original solver cells covered by exactly the same ROI. Number comparisons therefore refer to **atoms in the ROI**, and the full model count is shown separately. Excluding more than 1% of model atoms triggers an aperture warning.

Any invalid ROI pixel makes the number and widths unavailable rather than silently undercounting. For valid but noisy ROIs, approximate number uncertainty is propagated from A, R and the shared dark exposure:

```text
dOD/dA_raw = -1/A - s0/mu_ref
dOD/dR_raw =  1/R + s0/mu_ref
dOD/dD_raw =  1/A - 1/R
Var(OD) ~ (dOD/dA_raw)^2 (A + read_rms^2)
        + (dOD/dR_raw)^2 (R + read_rms^2)
        + (dOD/dD_raw)^2 read_rms^2
SE(N_ROI) = pixel_area / sigma0 * sqrt(sum_ROI Var(OD))
```

This linearized estimate is unreliable at very low counts and is not a fit confidence interval. Noisy widths are withheld below number SNR 5; negative second moments also yield unavailable widths. Signed atom estimates may still be negative when noise dominates. Zero-temperature atomic number fluctuations are not added.

Fringe estimates use the strip-averaged profile within the ROI. The model profile averages over the same y aperture on the fine grid; the camera profile uses camera pixels. Require at least three regular peaks, spacing at least four samples, spacing coefficient of variation <=0.3, and each local peak/valley contrast >=0.1. Noise additionally requires a fully valid strip within the ROI and a profile peak-to-peak range above ten times its largest estimated standard error. These conservative app criteria are not a universal Rayleigh limit or an experimental phase/visibility fit. “Unavailable” can mean unresolved, noisy, masked, or simply no fringes.

## Try the resolution experiment

1. Load the **Positive bias** guided experiment, Prepare and Run to completion.
2. In Virtual camera, choose **Ideal optics · noise off**, then **Capture image** and **Pin image**.
3. Set optical FWHM to 2, 4 and 8 um in turn, capturing the same state each time. Keep the ROI and strip fixed for comparison.
4. Increase pixel size, enlarging the strip if necessary, then enable noise and compare several seeds or pulse durations.

In the tested example, model spacing is about 10.249 um. At native pixel pitch 0.603 um without noise, recovered profile contrasts at FWHM 0, 2 and 4 um are approximately 0.841, 0.713 and 0.473. At 8 um the fringe estimator reports unavailable. This is one documented model/estimator example, not a general optical resolution threshold. Even without noise, unresolved optical structure can bias inferred atom counts because spatial averaging and logarithmic inversion do not commute.

Pinned images are immutable and retain their own source time, optics, ROI, strip and noise settings. Changing the simulation leaves the old exposure visible with a stale-snapshot notice. Changed camera controls apply only at Capture. Export contains the full source experiment, all frames, calibration constants, camera settings, seed and measurements. The normal replay command checks both source evolution and exact camera regeneration; comparison exports verify both acquisitions. References are page-local and disappear on reload.

## Limits and literature

Pulse duration changes photon budget, not evolution during exposure. Recoil heating, radiation pressure, atomic motion, loss, repumping and multilevel optical dynamics are omitted. The UI estimates mean absorbed photons per atom from the unblurred transmission and warns above five; this is an app heuristic, not a universal nondestructive-imaging boundary. Large optical depth (>4) also triggers a limitation note. No setting is certified as a realistic laboratory pulse. The GPE's quasi-2D and numerical-convergence limits still apply.

- **Ketterle, Durfee & Stamper-Kurn (1999), Making, probing and understanding Bose-Einstein condensates.** [Lecture/review](https://arxiv.org/abs/cond-mat/9904034), especially Sec. 3 and Appendix A. Foundation for column-density absorption imaging, photon noise and atom/reference/background processing. Our Gaussian PSF and measurement thresholds are simplified implementation choices, not a reconstruction of their apparatus.
- **Reinaudi, Lahaye, Wang & Guery-Odelin (2007), Optics Letters 32, 3143–3145.** [Strong saturation absorption imaging of dense clouds of ultracold atoms](https://arxiv.org/abs/0707.2930), Eqs. 1–3. Source of the saturation-corrected propagation/inversion relation. We set the calibration factor alpha to one; their measured calibration and full experimental protocol are not reproduced.
- **Steck, Rubidium 87 D Line Data, revision 2.3.4 (2025).** [Data tables and Sec. 4.3.1](https://steck.us/alkalidata/rubidium87numbers.pdf). Source of the D2 wavelength and ideal cycling-transition cross-section/saturation intensity. The app assumes that ideal transition is already prepared and does not simulate state preparation.

For the underlying atomic dynamics and physical scales, see [Laboratory units and the papers behind them](PHYSICAL_UNITS.md).
