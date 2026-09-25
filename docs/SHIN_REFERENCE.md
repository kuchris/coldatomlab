# Shin Fig. 2 reference audit

This supports a **reduced fringe-spacing benchmark**, not an experimental image reproduction.

## Primary-source observations

[Shin et al., Physical Review Letters 92, 050405 (2004)](https://doi.org/10.1103/PhysRevLett.92.050405), checked against [arXiv:cond-mat/0306305v2](https://arxiv.org/pdf/cond-mat/0306305v2), pp. 1–2, Fig. 2 and Eq. (1):

- Species: sodium-23; final separation: 13 µm; ballistic expansion: 30 ms.
- Typical single-beam frequencies: radial 615 Hz, axial 30 Hz; peak mean-field energy approximately h × 3 kHz.
- Fig. 2 uses an absorption image integrated across a strip, then a Gaussian-envelope sinusoidal fit. Typical contrast exceeds 60%.
- Reported measured period: **41.5 µm**. Reported point-source prediction: **39.8 µm**.
- Eq. (1)'s interference phase is `m d x / (hbar t) + phi_r`, implying `lambda = h t / (m d)` in its long-expansion approximation.
- Neither a numerical raw profile nor a period uncertainty accompanies Fig. 2. Its plotted profile axes do not supply numerical tick scales. Initial production above ten million atoms is not a calibrated Fig. 2 atom count.

These reported values should be stored separately from recalculated values; the paper's approximate “within 4%” wording is not a statistical confidence interval.

## Independent calculation

[Steck, Sodium D Line Data, revision 2.3.4, Table 2](https://steck.us/alkalidata/sodiumnumbers.pdf) gives sodium mass `3.8175410023e-26 kg`. Using exact `h = 6.62607015e-34 J s` and the paper's rounded `d = 13e-6 m`, `t = 0.030 s` gives **40.05439917 µm**, rather than 39.8 µm. The source does not establish the reason for this difference; do not silently adjust separation to remove it.

Define comparison error explicitly as `100 * (simulation - reported measurement) / reported measurement`. The recalculated point-source value differs from 41.5 µm by **−3.483375%**. The quoted 39.8 µm differs by **−4.096386%** under that denominator. Neither number proves experimental agreement without uncertainty information.

## Local model audit and recommended comparison

The current [model](MODEL.md) retains transverse confinement, prepares ideal Gaussian pairs or a harmonic trap with a raised Gaussian barrier, and defaults to Rb-87 teaching parameters. Its generic peak-spacing diagnostic is not the paper's fitted fringe period. The [camera](IMAGING.md) implements ideal Rb-87 optics only.

Our inference from the reported energy and frequencies is that copying them into the frozen-axis model is unjustified: 3 kHz exceeds both confinement frequencies. Three-dimensional interacting release, the apparatus potential, and sodium absorption calibration are outside this reduced benchmark. The separate [3D interferometer](INTERFEROMETER3D.md) now implements interacting splitting and release with a declared Rb-87 teaching potential; it does not reconstruct the sodium apparatus or camera.

A defensible implementation evolves an explicitly noninteracting Gaussian pair using sodium mass, matching only separation and expansion time. Packet width, envelope, normalization and numerical domain must remain labeled modeling choices. Integrate the numerical density, fit its carrier period, and show the simulation, finite-width analytic check, rounded-input point-source prediction, quoted prediction, and reported measurement separately. Do not tune packet width to reproduce 41.5 µm.

For an initial amplitude `exp(-x²/(2 a²))`, free Gaussian propagation gives carrier period `h t / (m d) * (1 + (m a² / (hbar t))²)`. This independent analytic consequence is a solver check, not another experimental datum. Keep any fit/window/envelope bias separate from time/grid/domain convergence. Require resolved fringes, negligible boundary contamination and independent variation of numerical controls; norm conservation alone is insufficient.

Do not claim the benchmark reproduces the measured contrast, cloud envelope, atom number, noise, splitting dynamics or three-dimensional experiment. A successful result establishes numerical consistency and a transparent one-observable comparison to a published value; it does not establish calibrated experimental validation.
