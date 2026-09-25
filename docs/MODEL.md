# Physical and numerical model

## Conventions

The effective two-dimensional, dimensionless Gross–Pitaevskii equation is

```text
i ∂ψ/∂t = [−½∇² + V(x,y,t) + g|ψ|²] ψ
∫ |ψ|² dx dy = 1
V_trap = ½(ωx² x² + ωy² y²)
```

Here `g` includes the atom number and the effective transverse coupling. It is restricted to nonnegative values in this release. Coordinates use `a0 = sqrt(hbar/(m*omega0))`, time uses `1/omega0`, and energies use `hbar*omega0`. The frequency controls are ratios to `omega0`. No species, atom number, scattering length, transverse frequency, or physical reference frequency is selected, so the app reports dimensionless results rather than laboratory seconds or micrometers.

The model assumes a prepared dilute, weakly interacting condensate with frozen transverse motion. Releasing the trap switches off **in-plane** confinement; the transverse confinement remains. It does not model the formation of a condensate, finite-temperature thermal atoms, laser cooling, particle loss, strong correlations, or full three-dimensional expansion. Changing `g` without selecting a transverse scale does not establish that a particular physical realization remains in the quasi-2D regime.

## Preparation

**Single cloud:** start from the noninteracting Gaussian, then use normalized imaginary-time split evolution in the harmonic trap. The imaginary step is `0.002`. Every 100 iterations, compare the wavefunction to its previous checkpoint in discrete L2 norm. Stop below `2e-8`, or reject the preparation after 6,000 iterations. This is convergence to the finite-step discretized state, not an assertion of exact continuum ground-state accuracy. Preparation metadata is included in exports.

**Two clouds:** construct `φ(x+d/2,y) + exp(iθ) φ(x−d/2,y)` and normalize the sum, where `φ(x,y) = exp[−(ωx*x² + ωy*y²)/2]`. The two-cloud experiment starts with zero in-plane potential. Packet widths use the trap frequency controls, even for nonzero `g`; these ideal Gaussian packets are not claimed to be interacting ground states. Their relative phase is controlled. This preset does not simulate the splitting process; use the sequence experiment for dynamic splitting.

**Split / hold / release sequence:** start from the same single trapped ground state. The applied potential before release is

```text
V(x,y,t) = V_trap + A(t)*exp(−x²/(2*w²)) + B(t)*tanh(x/w)/2
```

During Split, `A(t) = Amax*(3*u²−2*u³)`, where `u` runs from 0 to 1, and `B=0`. During Hold, `A=Amax` and `B` is the chosen bias. Positive bias raises the right well; sufficiently separated arms approximately acquire `phase_right − phase_left = −bias*hold_time` in the noninteracting limit. The bias is switched on at the beginning of Hold. Release switches off the complete in-plane potential, including the barrier and bias. Evolution stops at the end of the expansion interval.

Durations are rounded to the nearest integer number of solver steps, with at least one step for Split and Expand. Hold may contain zero steps. The timeline displays actual rounded boundaries, and the export includes the configuration, release step, and protocol summary. The total requested duration is limited to 18 time units; boundary stopping may interrupt a sequence earlier. Barrier width must span at least two grid spacings, but this minimum is not a convergence guarantee.

These are mean-field controls inspired by double-well interferometry, not a calibrated reproduction of an atom-chip device. Number squeezing, entanglement, and stochastic phase diffusion are outside this deterministic GPE model.

## Evolution

The endpoint-excluded square grid has `n × n` points and spacing `L/n`. FFT frequencies are converted to angular wave numbers using `2*pi*fftfreq(n, dx)`. Each real-time step applies:

1. Half a local potential/nonlinear phase step.
2. A full kinetic step in Fourier space, multiplied by `exp(−i*dt*k²/2)`.
3. Half a local phase step, recomputing density after the kinetic step.

This is second-order Strang splitting. Real-time evolution is **not renormalized**. Rendering uses snapshots from the solver and never advances its own approximation. Playback requests batches of 10 solver steps; **Step** requests one. Pausing finishes any in-flight batch and then freezes time. The interface reports `Paused` only after that batch is displayed.

For the sequence, evaluate the external potential at each time-step midpoint. Stage switches fall exactly on step boundaries, so no step straddles a discontinuity. Diagnostics use the potential at the reported time. History retains the states immediately before potential switches as well as subsequent samples. Energy changes under the driven potential; it should not be interpreted as a conservation failure during Split or at bias/release switches.

The server stores independent sessions per browser page, with up to 16 sessions and one hour of inactivity before expiry. Preparation and state mutations are serialized. This loopback server is intended for a local computer, not public deployment.

## Diagnostics and boundaries

- **Norm:** discrete integral of `|ψ|²`.
- **RMS widths:** square roots of the centered second moments, divided by norm.
- **Energy:** kinetic energy from spectral derivatives, plus `∫V|ψ|²`, plus `g/2 ∫|ψ|⁴`. The factor of one half in the interaction energy differs from the GPE's local evolution term.
- **Central profile:** `|ψ(x,0)|²`, sampled along the central row; not a line-integrated image.
- **Boundary population:** norm in the union of the outer `n/16` rows and columns, with corners counted once. Stop once it exceeds `0.001` (0.1% of unit norm), or when time reaches 20.
- **Left/right populations:** normalized half-plane populations, with the `x=0` column divided equally. They sum to one; they are fractions, not absolute atom counts.
- **Mirror phase:** argument of `sum(conj(psi(−x,y))*psi(x,y))` for matched grid points with `x>0`. Global phase cancels. This is a spatially weighted phase diagnostic, not a fitted fringe phase. It becomes unavailable when normalized mirror overlap is below 0.1; a scalar phase may still be a poor description of strongly distorted arms.
- **Fringe estimates:** after release, find central-profile local maxima above 8% of the current peak. Require at least three peaks, spacing of at least four grid cells, relative spacing standard deviation at most 0.3, and each adjacent peak/valley contrast at least 0.1. Report median peak spacing and median `(mean_peak−valley)/(mean_peak+valley)`. These local profile estimates include envelope effects and are not a coherence measurement. Missing values mean no reliably resolved pattern under these criteria.

FFT boundaries are periodic. The boundary stop reduces wraparound artifacts but is not an absorbing boundary and does not certify accuracy. Phase variation can also require finer spatial sampling. Quantitative use requires separate time-step, grid, and domain convergence checks for the chosen experiment.

Energy is conserved only while the Hamiltonian is time independent. Releasing the trap changes potential energy instantaneously; the history records both sides of this jump at the same time.

## Display and export

Density uses a linear, frame-relative color scale whose maximum is shown in the legend. Axis extents remain fixed throughout a run. Phase uses a cyclic color map and is masked wherever density is less than 0.1% of the current peak. Plots adapt their ranges to the data. These are model diagnostics, not a virtual camera or absorption image.

JSON exports include configuration, solver and NumPy versions, preparation details, total step count, release step, sampled diagnostic history, grid coordinates, and the final complex wavefunction. Replay recreates the initial state and release protocol; it compares the recomputed field with the saved one. History sampling depends on playback batches, so replay targets the final physical state rather than identical history timestamps. Same-version replay should agree to rounding error; different solver or library versions may differ.

Potential contours at fixed energies 2, 4, 8, and 16 are computed from the applied potential, rather than decorative trap outlines. The central potential plot shows `x` from −6 to 6. **Pin reference** stores a snapshot and complete export in browser memory. It survives preparing/resetting the current experiment, but not page reload. A comparison uses shared plot axes and labels each run's time/settings; unequal times are allowed and are not automatically aligned. **Export comparison** downloads a `coldatomlab-comparison-v1` bundle containing two ordinary experiment records, both checked by the replay command.

## References

- Bao, Jaksch and Markowich, [Numerical Solution of the Gross–Pitaevskii Equation for Bose–Einstein Condensation](https://arxiv.org/abs/cond-mat/0303239), 2003.
- Javanainen and Ruostekoski, [Split-step Fourier methods for the Gross–Pitaevskii equation](https://arxiv.org/abs/cond-mat/0411154), 2004.
- NumPy, [Discrete Fourier Transform conventions](https://numpy.org/doc/stable/reference/routines.fft.html).
- Shin et al., [Atom interferometry with Bose–Einstein condensates in a double-well potential](https://arxiv.org/abs/cond-mat/0306305), 2004.
- Berrada et al., [Integrated Mach–Zehnder interferometer for Bose–Einstein condensates](https://www.nature.com/articles/ncomms3077), 2013. Inspiration for splitting and controlled bias; the present expansion readout and mean-field model do not reproduce its full experimental protocol or many-body correlations.
