# Laboratory units and the papers behind them

Laboratory mode adds SI scales to the existing effective 2D solver. It is a zero-temperature mean-field model with a frozen axial Gaussian, not a calibrated reconstruction of a particular apparatus. The dimensionless mode remains available.

## Conventions and derivation

Use frequencies in cycles per second: omega0 = 2 pi f0 and omegaz = 2 pi fz. All lengths in the following derivation are in meters.

```text
a0 = sqrt(hbar / (m omega0))
az = sqrt(hbar / (m omegaz))
g3D = 4 pi hbar^2 as / m
chi(z) = exp(-z^2 / (2 az^2)) / (pi az^2)^(1/4)
integral |chi|^4 dz = 1 / (sqrt(2 pi) az)
g2D = g3D / (sqrt(2 pi) az)
g = N g2D / (hbar omega0 a0^2) = sqrt(8 pi) N as / az
```

We use the large-N `N` convention, not `N-1`, and normalize the planar wavefunction to one. The omitted axial zero-point energy is a constant hbar omegaz / 2. Releasing the trap retains axial confinement, so this coupling remains constant.

For canonical dimensionless coordinates X, time tau, energy epsilon and density rho:

```text
x_um = X a0 10^6
t_ms = tau / omega0 * 1000
E/h in Hz = epsilon f0
n2D in atoms/um^2 = N rho / (a0 10^6)^2
```

Widths and fringe spacing use the same length scale. Energy readouts are mean-field energy per particle under the norm-one convention, with the interaction-energy factor 1/2. Potential/bias in Hz means V/h, not an angular frequency. The field remains a model density, not an absorption image.

Rb-87 uses mass `1.443160895e-25 kg` from Steck's data table. The editable `5.3 nm` scattering length is a rounded teaching value, not a state- or field-specific calibration. Custom species use a user-supplied bosonic mass and repulsive scattering length. The app does not determine their stability, spin state or Feshbach tuning. Planck's constant is `6.62607015e-34 J s`; the atomic mass unit is `1.66053906660e-27 kg`.

## Applicability panel

The diagnostic panel reports the following ratios. “Supported” means they meet conservative app thresholds; these numerical thresholds are our choices, not universal criteria quoted from a paper.

| Check | Supported threshold |
|---|---:|
| Initial planar mu estimate / hbar omegaz | <= 0.1 |
| Current peak g rho / (omegaz/omega0) | <= 0.1 |
| Current mean kinetic energy / hbar omegaz | <= 0.1 |
| max(fx, fy) / fz | <= 0.1 |
| as / az | <= 0.05 |
| Peak reconstructed n3D as^3 | <= 0.001 |

Initial mu is the expectation of kinetic + external + full nonlinear terms in the prepared field. It approximates the chemical potential of the stationary trapped state; for the ideal two-packet initial state it is only an energy-scale estimate. It excludes the axial zero point. Current kinetic energy is obtained from the solver's Fourier derivatives. The peak 3D density assumes `n3D(x,y,0) = n2D(x,y)/(sqrt(pi) az)`.

Exceeding any threshold shows “Marginal”. An energy/frequency ratio >= 1, as/az >= 0.2, or gas parameter >= 0.01 shows “Outside”. These warnings do not stop the exploratory solver, and do not imply a 3D calculation was performed. Large derived g (>100) is rejected because it exceeds this release's numerical operating range.

This is an instantaneous scale check, not a guarantee of validity throughout a run. It omits high-energy momentum tails, nonseparable trap effects, excited axial modes and thermal populations. A physical experiment also needs kB T much smaller than hbar omegaz; no temperature is simulated or certified here. Finite-size phase coherence, depletion, phase diffusion and many-body correlations are not established by this panel. Grid/domain/time-step convergence remains a separate requirement.

## Guided comparisons

All examples use Rb-87, N=200, as=5.3 nm, f0=20 Hz, fx=20 Hz, fy=28 Hz and fz=2000 Hz. This gives a0=2.411436 um, az=0.241144 um, 1/omega0=7.957747 ms and g=22.036876. The barrier rises to V/h=240 Hz over 31.83099 ms, has width 1.688005 um, and expansion lasts 15.91549 ms. The numerical default is 128^2 points, L=32 a0 and dt=0.01/omega0. Durations round to solver steps.

| Example | Bias Delta V/h | Hold | Question |
|---|---:|---:|---|
| Symmetric reference | 0 Hz | 7.957747 ms | Does symmetry preserve equal populations? |
| Positive bias | +10 Hz | 7.957747 ms | Which sign does right-minus-left phase acquire? |
| Reverse bias | -10 Hz | 7.957747 ms | Do phase and population imbalance reverse? |
| Longer hold | +10 Hz | 15.91549 ms | How much additional phase accumulates? |

Load settings, Prepare, Run, and Pin reference. Load and run a second example, then compare. Pause near the end of Hold to inspect phase before expansion changes the spatially weighted diagnostic. For isolated arms the estimate is `Delta phi = -2 pi (Delta V/h) T_seconds`; interactions, residual tunnelling and distorted arms can change the result. The longer-hold run has a different absolute final time but the same expansion duration. These are our pedagogical settings, not values fitted to Shin et al.

Changing reference frequency or mass rescales the input display at fixed dimensionless trap/protocol settings; editing a time, width or frequency directly changes its physical value. Changing N, as, mass or fz recomputes g at Prepare. Pending edits never relabel the existing prepared run. Both physical runs in a comparison use their own unit conversions; a mixed physical/dimensionless comparison uses dimensionless plot/table axes with an explicit notice.

Exports retain dimensionless arrays and canonical protocol parameters, and add the complete physical configuration, SI constants-derived scales, and the current applicability report. Replay derives g again from the saved configuration. Old dimensionless exports remain supported. Pinned snapshots retain their own scales; references are local to the page and disappear on reload.

## Reference map

These established papers supply the physical basis; numerical and browser tests check our implementation, not the papers or a laboratory device.

1. **Dalfovo, Giorgini, Pitaevskii & Stringari (1999), Reviews of Modern Physics 71, 463.** [Theory of Bose-Einstein condensation in trapped gases](https://arxiv.org/abs/cond-mat/9806038). Foundation for dilute-gas mean-field theory, GPE energy and harmonic oscillator scales; see Sec. III. Our effective-2D implementation is a reduction of this framework, and does not implement the review's finite-temperature theory.
2. **Petrov, Holzmann & Shlyapnikov (2000), Physical Review Letters 84, 2551.** [Bose-Einstein condensation in quasi-2D trapped gases](https://arxiv.org/abs/cond-mat/9909344). Establishes the importance of tight confinement and quasi-2D scattering. Our constant repulsive coupling uses the weak-confinement-scattering limit; we do not implement its full energy-dependent scattering theory or confinement-induced interaction changes.
3. **Hadzibabic & Dalibard (2011), Rivista del Nuovo Cimento 34, 389.** [Two-dimensional Bose fluids: An atomic physics perspective](https://arxiv.org/abs/0912.1490). Sections 6.2–6.3, especially Eqs. 75–78, explain the approximate sqrt(8 pi) as/az coupling, the axial Gaussian reduction, and limitations from residual axial excitation. We multiply their dimensionless coupling by N because our wavefunction has unit norm. We do not simulate BKT thermodynamics.
4. **Shin et al. (2004), Physical Review Letters 92, 050405.** [Atom interferometry with Bose-Einstein condensates in a double-well potential](https://arxiv.org/abs/cond-mat/0306305). Experimental inspiration for coherent splitting, phase accumulation under an energy bias and interference readout. Our 2D Gaussian barrier and retained axial confinement are different from their optical apparatus and expansion geometry.
5. **Daniel Steck, Rubidium 87 D Line Data, revision 2.3.4 (2025).** [Atomic mass, Table 2](https://steck.us/alkalidata/rubidium87numbers.pdf). Atomic constants only; this source is not used as a scattering-length calibration.

Read Dalfovo first for the GPE foundation, then Hadzibabic–Dalibard for the dimensional reduction, Petrov for where the simple coupling breaks down, and Shin for the experimental motivation.
