# Three-dimensional release: reference audit

This is a theoretical validation reference for a zero-temperature, repulsive, single-component condensate released from a harmonic trap. It is not a reproduction of a particular experimental data set. The equations below define a genuine 3D field calculation; the scaling model is an independent comparison, not its evolution engine.

## Primary sources

- Y. Castin and R. Dum, **Bose-Einstein Condensates in Time Dependent Traps**, Physical Review Letters **77**, 5315–5319 (1996), [DOI](https://doi.org/10.1103/PhysRevLett.77.5315), [publisher full text](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevLett.77.5315/fulltext). Equations (3)–(6) supply the norm-one GPE and TF equilibrium; (11) gives anisotropic scaling, with initial conditions immediately below it. Equations (15)–(18) identify the approximation and its kinetic correction. Equations (19)–(22) concern complete release from a cigar-shaped trap.
- F. Dalfovo, S. Giorgini, L. P. Pitaevskii and S. Stringari, **Theory of Bose-Einstein condensation in trapped gases**, Reviews of Modern Physics **71**, 463–512 (1999), [DOI](https://doi.org/10.1103/RevModPhys.71.463), [author manuscript](https://arxiv.org/abs/cond-mat/9806038). Sections III.D and IV.D, especially equations (50)–(57) and (101)–(106), cross-check TF equilibrium, boundary corrections, scaling, and release energy. Equation numbers here refer to the linked manuscript, version 2.

Castin–Dum assumes dominant interactions, with chemical potential much larger than each trap quantum. Scaling is a TF approximation to 3D GPE, not an exact solution at arbitrary interaction strength. Dalfovo et al. explicitly distinguish kinetic boundary corrections and finite-particle-number behavior. Neither source prescribes software validation tolerances or validates this implementation.

## Norm, scales, and coupling

The following dimensionless conversion is derived here from the sources' dimensional GPE. Choose a reference angular frequency `omega0 = 2*pi*f0` and define

```text
a0 = sqrt(hbar/(m*omega0))
q_i = r_i/a0                 tau = omega0*t
Omega_i = omega_i/omega0     omega_i = 2*pi*f_i
psi(q,tau) = a0^(3/2)*Phi(r,t)
integral |psi|^2 d^3q = 1

i*dpsi/dtau = [-1/2 Laplacian_q + V + g3D*|psi|^2]*psi
g3D = 4*pi*N*a_s/a0
V_trap = 1/2 sum_i Omega_i^2*q_i^2
V_release = 0
```

`N` is the condensate atom number; this convention adopts `N-1 ≈ N`. Keep `g3D` fixed after release: removal of the trap does not turn off collisions. Do not reuse the quasi-2D coupling, integrate out an axis, or retain a transverse zero-point term. Positive scattering length is the scope here.

Physical number density is `N*|psi|^2/a0^3`. Projection along z is `N/a0^2 * integral |psi|^2 dq_z`, with analogous expressions along x and y. Integrating the projected density over its physical image plane must recover the same total atom number as the volume integral. A central slice is not a projection.

## TF equilibrium and width conversion

Substitution of the scales above into the source TF normalization gives

```text
mu_TF = 1/2 * [15*g3D*Omega_x*Omega_y*Omega_z/(4*pi)]^(2/5)
rho_TF(q) = max(mu_TF - V_trap(q), 0)/g3D
R_i = sqrt(2*mu_TF)/Omega_i
sigma_i_TF = R_i/sqrt(7)
```

`mu_TF` is in `hbar*omega0`, and radii/widths are in `a0`. Equivalently, using `omega_bar=(omega_x*omega_y*omega_z)^(1/3)` and `a_bar=sqrt(hbar/(m*omega_bar))`, the dimensional result is `mu_TF_phys=(hbar*omega_bar/2)*(15*N*a_s/a_bar)^(2/5)`.

The RMS factor is derived by integrating the normalized ellipsoidal parabola: substitute `u_i=q_i/R_i`, then `integral u_i^2*(1-u^2) d^3u / integral (1-u^2) d^3u = 1/7`. Thus a TF edge radius, RMS width, Gaussian fit width, and full width at half maximum are different quantities. No width conversion should be guessed from a paper's plot label.

These formulas are undefined as a TF reference at `g3D=0`. The noninteracting harmonic ground state instead has `sigma_i(0)=1/sqrt(2*Omega_i)`, energy `sum_i Omega_i/2`, and after full release

```text
sigma_i(tau) = sqrt((1 + Omega_i^2*tau^2)/(2*Omega_i)).
```

This last expression is the exact free Gaussian reference, obtained by propagating the harmonic oscillator ground state.

## Anisotropic expansion reference

In the chosen dimensionless time, Castin–Dum's equation becomes

```text
B = b_x*b_y*b_z
b_i'' = Omega_i^2/(b_i*B)
b_i(0) = 1                b_i'(0) = 0
sigma_i_TF(tau) = sigma_i_TF(0)*b_i(tau)
sigma_i_TF/sigma_j_TF = (Omega_j/Omega_i)*(b_i/b_j)
```

Primes denote derivatives with respect to `tau`. Complete release removes all three confining terms. If a trap were retained, its contribution would be `-Omega_i(tau)^2*b_i`; it must not remain in this experiment. Numerically integrate all three equations for general anisotropy. The cigar approximation is not a general closed-form solution.

An independently derived ODE diagnostic is

```text
1/B + 1/2 * sum_i (b_i'/Omega_i)^2 = 1.
```

It follows directly by differentiating the left side and substituting the ODE. It checks scaling integration separately from the GPE solver. It is not a substitute for GPE energy conservation.

## Comparing a finite-interaction stationary state

Report both comparisons with explicit names:

1. **Absolute TF prediction:** `sigma_TF_i(0)*b_i(tau)`. This tests the initial TF size and expansion together.
2. **Initial-width-anchored scaling:** `sigma_GPE_i(0)*b_i(tau)`. This removes the initial width offset to expose the expansion-factor discrepancy. It does not make scaling exact and must not be described as an unfitted absolute TF prediction.

For either, record fractional differences per axis and aspect ratio. Also record stationary chemical potential, kinetic/interaction/trap energies, the stationary residual, and initial widths. A clean separation is: numerical error from refinement; finite-interaction difference from the approximate reference; experimental discrepancy only when actual measured data and conditions are supplied.

Useful applicability indicators are `mu_TF/Omega_i` in every direction, `E_kin/E_int` in the prepared state, and physical peak gas parameter `n_peak*a_s^3`. They answer different questions. Large TF parameters do not establish numerical spatial resolution; a dilute gas does not by itself establish a negligible thermal fraction. At finite interaction strength, resolved GPE tails and quantum pressure legitimately differ from the compact TF parabola. During release, kinetic flow grows, so a large total kinetic energy at late time is not itself a failure of TF hydrodynamics.

## Proposed numerical validation policy

The following are engineering targets and experiment design choices, not claims from the papers. Publish actual measurements before marking a case validated.

- Start with an anisotropic noninteracting case: target relative RMS error below `1e-3` on each axis over the demonstrated time window, and norm drift below `1e-10` for double precision. Inspect density/field agreement as well as widths. Resolve narrow initial widths and expanded tails.
- Prepare the interacting state by imaginary time. Vary imaginary-time step and preparation duration; report the residual `||(H-mu)psi||` relative to a stated energy scale, not only successive energy differences. A plateau can be discretization error.
- For a representative interacting release, halve the real-time step, refine spatial spacing at fixed box, and enlarge the box at comparable spacing in separate studies. An initial practical target is less than `0.5%` change in all widths and aspect ratios; tighten when the claimed scientific comparison needs it. Check post-release energy drift and its decrease under time refinement. Never renormalize real-time steps.
- Compare scaling ODE solutions with tighter integration tolerance or smaller reference steps until their change is negligible against the GPE uncertainty. Check the invariant above.
- Establish a TF comparison in a state with small prepared kinetic contribution and large `mu_TF/Omega_i` for all axes. A percent-level or few-percent GPE/TF difference may be a useful measured outcome, but there is no universal allowed TF error. Select and document the case and desired tolerance before interpreting it. If a tolerance fails after numerical convergence, report finite-interaction disagreement rather than tuning parameters to hide it.
- To demonstrate approach toward TF, compare multiple interaction strengths with each state independently resolved. Raising `g3D` increases cloud size and changes edge/healing scales; holding an inadequate grid fixed invalidates that trend.
- Monitor boundary-shell probability and density near all six faces throughout expansion. Stop before periodic images interact. A low norm drift does not detect wraparound. Box refinement must corroborate the duration claimed safe.
- Record actual wall time, grid, precision and peak/process memory for preparation and evolution separately. A visualization downsample does not alter the solver grid; numerical measurements use the original state.

## Interpretation limits

The proposed calculation contains coherent mean-field dynamics of one condensate, with contact repulsion and a harmonic initial trap. It omits finite temperature, atom losses, quantum depletion corrections, trap imperfections, and calibrated imaging response. A projected 3D numerical density is a model observable, not a synthetic noisy camera unless an explicit forward imaging model is applied. The literature supports the theoretical comparison; independent browser checks must establish that controls and displayed projections use this implemented state correctly.
