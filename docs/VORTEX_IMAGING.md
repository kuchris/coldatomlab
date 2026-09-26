# Vortex release and absorption imaging (v0.17)

Experiment 06 now connects the complex 3D field to a simulated photograph.
Choose **Release & photograph → Prepare experiment → Release trap → Run**,
then **Capture image** in the imaging panel. Pin that exposure, stage
**Try 3 μm resolution**, and capture again. Enable noise to inspect a seeded
photon/read-noise realization. This does not add fluctuations to the condensate.

## Release protocol and units

The [Vortex Lab conventions](VORTEX.md) remain unchanged: norm-one ψ,
Rb-87 mass, a₀=1.525 μm, t₀=3.183 ms, g=4πNaₛ/a₀. Atom number is explicit;
changing N at fixed g changes the derived scattering length and image optical
depth, not the dimensionless GPE dynamics. The allowed derived aₛ is 0–10 nm.
The noninteracting recipe is an ideal reference, not a claim that ordinary
Rb-87 has zero scattering length under the experimental conditions of a paper.

Release records the current integer step and removes **both** harmonic trap
and stirring beam. Interactions remain active. Evolution ends at
`release_step + round(tof_duration/dt)`; the displayed time is the actual rounded
time. Release is permitted after a trapped run finishes. Reset restores the
prepared field and trap. No real-time normalization, damping or loss is applied.
Energy drops by the removed potential energy at release; subsequently it is
the kinetic plus interaction energy. RMS widths are centered moments of the
full 3D numerical density. Trapped and TOF times are displayed separately.

The imaging recipe uses N=1000, g=0, charge +1, 64³ cells, box length 24a₀,
dt=.004t₀, and TOF=2t₀=6.366 ms. It starts with an analytic oscillator vortex.
Longer or interacting releases may reach the periodic boundary: the solver
stops when boundary probability or absolute norm drift exceeds .001. The stop
threshold is an operational limit, not a guarantee of negligible field error.
Increase box and grid together and repeat convergence checks for new protocols.

## Photograph and core estimate

The image integrates `N |ψ|²/a₀²` over the dimensionless viewing coordinate:
z view has horizontal x / vertical y, y view x / z, and x view y / z. All axes
are physical μm; a shared linear atoms/μm² scale compares model pixel averages
with recovered camera density. A captured field and pinned exposure are frozen
across evolution, reset, re-preparation and dashboard navigation; reload clears
them. This software snapshot does not model destructive measurement backaction.

The camera reuses the [absorption model](IMAGING.md): saturation-corrected
transmission, Gaussian intensity PSF before pixel integration, independent
photon and read noise, and atom/reference/dark frames. Efficiency is .8 and
read noise 1 electron RMS. No fringe fitting runs in this panel. Negative
estimates remain blue and invalid pixels magenta. Recoil, motion during exposure,
optical pumping, detuning/calibration errors and multiple scattering are omitted.
Fluence warnings still apply even with detector noise disabled.

The single-core estimator uses image pixels only, independently for model and
camera images. It is enabled only for an unstirred charge ±1 preparation viewed
along z. Side views and stirred clouds can be photographed but have no reported
single-core measurement. This restriction does not establish that every allowed
interacting state has a stationary, straight vortex line.

1. Within the origin-centered ROI, positive pixel weights locate the cloud
   centroid and RMS radius. Raw signed density estimates remain unchanged.
2. Search within .35 times that RMS radius for a minimum of the 3×3 mean.
   Require positive curvature in both image directions; estimate a subpixel
   center from local parabolic interpolation, capped at half a pixel.
3. Form one-pixel-wide annular means about that estimated center, to the smaller
   of 1.2 RMS radii or the distance to the ROI boundary. The ring peak supplies
   the surrounding density; the 3×3 core mean supplies the dip baseline.
4. Report contrast `(ring − core)/ring` and twice the interpolated radius of the
   first outward half-depth crossing before the ring peak.

At least nine pixels must span the ROI. Invalid ROI pixels, insufficient spatial
resolution, contrast below .1, or noisy depth SNR below 5 produce **Unavailable**
with a reason. Noiseless depth SNR is labeled **Noise off**. SNR propagates the
camera's per-pixel density variance through the two means; it is not a position
uncertainty or confidence interval. Searching for a minimum/maximum introduces
selection bias, and pixel averaging/PSF changes apparent diameter and contrast.
The apparent diameter is not a healing-length measurement. A density dip alone
does not prove winding; the separate numerical phase diagnostic supplies that
information. The default g=0 vortex has a finite oscillator-scale density core
even though an interacting healing-length interpretation is inapplicable.

Pinning retains the camera image and overlays its radial profile in purple.
Each pinned image labels its own density scale. JSON exports the current source
protocol, initial/final field, history, settings, frames and measurements; CSV
exports the current model/camera radial profiles. Export a pinned comparison
before replacing the current exposure if a separate file is needed.

## Reproduce the checks

```powershell
uv run pytest tests/test_vortex.py tests/test_vortex_imaging.py tests/test_camera3d.py
uv run python -m scripts.vortex_release_check
uv run python -m scripts.vortex_imaging_browser_check
uv run python -m scripts.vortex_browser_check
uv run python -m coldatomlab.replay path/to/coldatomlab-vortex-image.json
```

The new source schema is `coldatomlab-vortex-v2`, recording `release_step` and
three RMS widths. The verifier still accepts v0.16 vortex files. Image schema
`coldatomlab-vortex-image-v1` embeds the source; Python independently propagates
the saved field, checks source preparation/history, projects it, regenerates
the seeded frames, and recomputes core measurements. The image arrays use
absolute tolerance 1e-8 and relative 2e-10; core estimates use 1e-8. Field/history
tolerances remain those in [VORTEX.md](VORTEX.md), with RMS widths checked at
relative .001 and absolute 1e-5. Prose warnings/provenance are not authenticated.

## Numerical evidence

For released charge ±1 oscillator vortices,
`σx=σy=√(1+t²)`, `σz=√(1+4t²)/2`, free energy=1.5 and Lz=±1 in oscillator
units. The charge-zero reference has `σx=σy=√((1+t²)/2)` and free energy=1.
Full float64 split-step runs check these quantities after 500 steps without
rescaling, and compare the complex field including its phase.

The infinite-space analytic field differs slightly from a periodic-box result:

| Grid | Box / a₀ | Complex field L² error at TOF 2 |
| --- | ---: | ---: |
| 64³ | 24 | 8.0064×10⁻⁵ |
| 128³ | 24 | 7.7439×10⁻⁵ |
| 64³ | 32 | 1.8534×10⁻⁵ |
| 128³ | 32 | 9.5077×10⁻⁸ |

The default error is dominated by finite-box effects, not time integration.
The box/grid check composes the exact free spectral multiplier in one transform;
the tests separately exercise all 500 solver steps. Holding for .4 then releasing
for .4 gives field errors 1.7996×10⁻⁵, 4.4990×10⁻⁶ and 1.1248×10⁻⁶ for
dt=.008/.004/.002, consistent with second-order convergence.

A separate g=10 quench of the same normalized analytic field tests retained
interactions during release. Successive time-refinement differences are
7.2708×10⁻⁶ and 1.8175×10⁻⁶; its field differs from g=0 by .1702 in L².
This check is a prescribed quench, not an independently relaxed interacting vortex.

Camera tests cover all three projection orientations using an asymmetric
displaced cloud, atom totals, ideal inversion, blur/binning, displaced dip
localization, repeated noise seeds, missing/invalid signal and export tampering.

## Browser evidence and experimental reference

Actual hardware Chrome WebGPU and independent float64 replay give, at the
default imaging endpoint, norm .99985264, RMS `(2.236069,2.236069,2.061559)` and
field replay difference 8.77×10⁻⁵. This is measured float32 drift, not hidden by
renormalization. The ideal camera gives contrast .90136 and apparent diameter
3.56094 μm; FWHM=3 μm reduces contrast to .42326. One noisy seed is not a
precision claim. Local and extracted static checks exercise the actual controls,
immutable images/pins, downloads and independent replay, navigation, and
1440/390/320 px layouts. Mid-beam interacting release, partial/complete replay
and a rounded TOF endpoint also pass. The full numerical suite passed 375 tests;
the final imaging file passed 19 tests, including three subsequently added
projection-orientation cases. Existing trapped-vortex and 3D-camera browser
regressions passed. Evidence is under ignored `artifacts/vortex-imaging/`.

[Madison et al., PRL 84, 806 (2000), Vortex formation in a stirred
Bose–Einstein condensate](https://arxiv.org/abs/cond-mat/9912015) motivates the
release-and-image sequence: their protocol switched off confinement, expanded
for 27 ms and imaged along the vortex axis. This implementation does not match
their apparatus, scattering conditions, expansion time or measured core size.
Numerical and browser checks establish the stated implementation behavior;
they do not establish agreement with experimental images.
