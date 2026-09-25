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

**Two clouds:** construct `φ(x+d/2,y) + exp(iθ) φ(x−d/2,y)` and normalize the sum, where `φ(x,y) = exp[−(ωx*x² + ωy*y²)/2]`. The two-cloud experiment starts with zero in-plane potential. Packet widths use the trap frequency controls, even for nonzero `g`; these ideal Gaussian packets are not claimed to be interacting ground states. Their relative phase is controlled. Barrier raising and physical splitting are not simulated.

## Evolution

The endpoint-excluded square grid has `n × n` points and spacing `L/n`. FFT frequencies are converted to angular wave numbers using `2*pi*fftfreq(n, dx)`. Each real-time step applies:

1. Half a local potential/nonlinear phase step.
2. A full kinetic step in Fourier space, multiplied by `exp(−i*dt*k²/2)`.
3. Half a local phase step, recomputing density after the kinetic step.

This is second-order Strang splitting. Real-time evolution is **not renormalized**. Rendering uses snapshots from the solver and never advances its own approximation. Playback requests batches of 10 solver steps; **Step** requests one. Pausing finishes any in-flight batch and then freezes time. The interface reports `Paused` only after that batch is displayed.

The server stores independent sessions per browser page, with up to 16 sessions and one hour of inactivity before expiry. Preparation and state mutations are serialized. This loopback server is intended for a local computer, not public deployment.

## Diagnostics and boundaries

- **Norm:** discrete integral of `|ψ|²`.
- **RMS widths:** square roots of the centered second moments, divided by norm.
- **Energy:** kinetic energy from spectral derivatives, plus `∫V|ψ|²`, plus `g/2 ∫|ψ|⁴`. The factor of one half in the interaction energy differs from the GPE's local evolution term.
- **Central profile:** `|ψ(x,0)|²`, sampled along the central row; not a line-integrated image.
- **Boundary population:** norm in the union of the outer `n/16` rows and columns, with corners counted once. Stop once it exceeds `0.001` (0.1% of unit norm), or when time reaches 20.

FFT boundaries are periodic. The boundary stop reduces wraparound artifacts but is not an absorbing boundary and does not certify accuracy. Phase variation can also require finer spatial sampling. Quantitative use requires separate time-step, grid, and domain convergence checks for the chosen experiment.

Energy is conserved only while the Hamiltonian is time independent. Releasing the trap changes potential energy instantaneously; the history records both sides of this jump at the same time.

## Display and export

Density uses a linear, frame-relative color scale whose maximum is shown in the legend. Axis extents remain fixed throughout a run. Phase uses a cyclic color map and is masked wherever density is less than 0.1% of the current peak. Plots adapt their ranges to the data. These are model diagnostics, not a virtual camera or absorption image.

JSON exports include configuration, solver and NumPy versions, preparation details, total step count, release step, sampled diagnostic history, grid coordinates, and the final complex wavefunction. Replay recreates the initial state and release protocol; it compares the recomputed field with the saved one. History sampling depends on playback batches, so replay targets the final physical state rather than identical history timestamps. Same-version replay should agree to rounding error; different solver or library versions may differ.

## References

- Bao, Jaksch and Markowich, [Numerical Solution of the Gross–Pitaevskii Equation for Bose–Einstein Condensation](https://arxiv.org/abs/cond-mat/0303239), 2003.
- Javanainen and Ruostekoski, [Split-step Fourier methods for the Gross–Pitaevskii equation](https://arxiv.org/abs/cond-mat/0411154), 2004.
- NumPy, [Discrete Fourier Transform conventions](https://numpy.org/doc/stable/reference/routines.fft.html).
