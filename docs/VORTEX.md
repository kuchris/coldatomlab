# Vortex Lab (v0.17; trapped reference introduced in v0.16)

Experiment 06 evolves a trapped three-dimensional condensate on hardware WebGPU.
Open **Vortex Lab → Prepare experiment → Run**. The default is an analytic
single-vortex reference. The **Stir a cloud** recipe starts with zero winding;
its moving Gaussian switches off at t=4 and evolution continues to t=5.
All times in those controls use the oscillator time t₀.

## Physical conventions

The dimensionless equation is

`i ∂t ψ = [−∇²/2 + V(r,t) + g |ψ|²] ψ`, with `∫ |ψ|² d³r = 1`.

The mass is Rb-87, `ω₀=2π×50 s⁻¹`, `a₀=√(ℏ/mω₀)=1.525 μm`,
`t₀=1/ω₀=3.183 ms`. Energy is in `ℏω₀`; `g=4π N aₛ/a₀` is the
norm-one three-dimensional interaction coefficient. The numerical backend uses
the selected N (default 20,000) and derives aₛ from g/N; this is a parameterization, not a
calibration of a particular experimental scattering-length control.

`V=(x²+y²+4z²)/2 + H(t) exp(−[(x−R cos Ωt)²+(y−R sin Ωt)²]/(2σ²))`.

Before release the trap frequencies are `(50,50,100) Hz`. The repulsive beam is uniform in z.
With ramp length r and stirring duration T,
`H(t)=Hmax sin²[π clamp(min(t/r,(T−t)/r),0,1)/2]`.
Two ramps must fit within T. Potential values are evaluated at the physical
step midpoint, independently of browser rendering speed.

There is no damping, thermal cloud, quantum depletion, loss or stochastic term.
No vortices are inserted during real-time evolution. The beam can do work and
supply angular momentum; energy conservation is expected only with static V.
After the programmed beam is off, the remaining trap is axially symmetric.
Manual **Release trap** removes both potentials simultaneously; g stays unchanged.
See [release and absorption imaging](VORTEX_IMAGING.md) for the v0.17 protocol.

## Preparations and what to compare

- **Positive / negative vortex:** at g=0, multiply the oscillator ground state
  by `(x ± i y)` and normalize during preparation. This is an exact continuum
  eigenstate with energy 3 and Lz/Nℏ = ±1. Its density is stationary; its global
  phase rotates. Preparing it does not demonstrate spontaneous vortex formation.
- **No vortex:** analytic Gaussian at g=0; imaginary-time interacting ground
  state for g>0. Its initial winding is zero.
- **Interacting imprint:** nonzero initial charge with g>0 multiplies the ground
  state by `(x+i q y)/√(x²+y²+ξ²)`, with
  `ξ=[2 g max(|ψ_ground|²)]⁻¹/²`, then normalizes. This prescribed initial field
  is **not** a stationary interacting vortex. The saved stationary residual
  belongs to the underlying ground state, not the imprinted state.
- **Stir a cloud:** g=300, q=0, Hmax=12, σ=0.8, R=2, Ω=1.2,
  r=1, T=4, endpoint=5, grid=64³, box=16, dt=0.004.
  This shows emerging circulation and subsequent conservative motion. It does
  not promise an equilibrated vortex lattice or a critical-frequency curve.

## Measurements and display limits

The 3D surface uses the numerical density, sampled onto at most 32³ display
points, at 20% of its current peak. Drag or use arrow keys to rotate; the zoom
slider magnifies the surface without changing the simulation.

Density and phase plots use the native central z=0 slice. Density brightness
uses the square root of density relative to the current peak; the numeric peak
is labeled. Phase hue runs from −π through zero to +π. Phase is masked below
0.1% of the slice peak. Arrows indicate current direction with a fixed display
length, masked below 1% of peak; their lengths are not velocities.

The dashed counterclockwise circular contour has the configured radius.
128 bilinear complex-field samples define its phase increments. Winding is the
rounded sum divided by 2π. It is unresolved if any sample is below 0.1% of peak,
or an adjacent increment reaches 0.75π. Missing winding is never shown as zero.

Independent flow circulation integrates `Im(ψ*∇ψ)/|ψ|²` along the same contour
using **spectral derivatives** and bilinear interpolation. Its displayed unit is
one quantum `h/m=4.591 μm²/ms`. This numerical integral approaches integer winding
with refinement; it is not rounded to make agreement appear exact.

Lz is the full-volume integral of `Im[ψ*(x∂y−y∂x)ψ]`, divided by norm, in ℏ per
particle. Norm, instantaneous energy and boundary probability use the full 3D
field. Boundary mass is measured in an outer band of `max(2,n/16)` cells.

Crossings are phase windings on plaquettes of complex values averaged to cell
centers. This shifts plaquettes so the analytic on-axis zero lies inside one.
All four corner densities must exceed 0.1% of peak. Positions are approximate,
with grid-cell precision. These are **density-qualified central-plane crossings**,
not a reconstruction of 3D vortex filaments or a converged total vortex count.
Opposite charges can cancel inside the contour; crossings elsewhere do not
contribute to that contour's winding. A density hole with constant phase has
zero winding and is explicitly tested as a counterexample.

## Controls and files

Settings and recipes remain pending until Prepare. Run advances bounded batches;
Pause waits for the current batch, Step advances one physical step, Reset restores
the applied preparation. The endpoint is rounded to the nearest full time step.
Leaving the Vortex Lab pauses it after the current batch and preserves its state.
Pinned phase images and readings are copied and remain unchanged by subsequent
runs or preparations. Reloading clears browser state and pins.

Every step checks norm and edge probability. A deviation `|norm−1|>0.001` or
boundary probability `>0.001` stops evolution. Real-time evolution is never
renormalized. These guards detect major failure; they do not prove convergence.
WebGPU absence, shader/preparation failures and lost devices are surfaced as
errors. Repreparing destroys the replaced device; closing the page releases it.

JSON (`coldatomlab-vortex-v1`) saves the configuration, scales, preparation
metadata, hardware backend, interleaved full initial/final complex fields and
all recorded diagnostics. Order is x,y,z with z fastest and real,imag adjacent.
CSV saves history in oscillator units; unresolved measurements are empty cells.
Pinned display comparisons are not part of the JSON export: export each run
separately when preserving a pair for later analysis.

```powershell
uv run python -m coldatomlab.replay path/to/coldatomlab-vortex.json
uv run pytest tests/test_vortex.py -q
uv run python -m scripts.vortex_browser_check
uv run python -m scripts.vortex_gpu_check
uv run python -m scripts.vortex_refinement_check
uv run python -m scripts.package_webgpu
```

The replay command independently prepares a float64 field (initial L² tolerance
0.0003), evolves the saved prepared field without rescaling, and compares the
final full field (L² tolerance 0.005). History tolerances are absolute 0.001 norm,
0.005 energy/Lz and 0.00002 edge probability; circulation uses 0.002 absolute or
relative tolerance. Discrete winding/counts must agree; intermediate crossing
locations may differ by one cell. Final saved-field diagnostics are independently
recomputed with tighter tolerances and exact classification agreement. A
threshold-sensitive history can fail verification despite small field error;
inspect masking and refine instead of treating it as bitwise reproducibility.
Backend descriptions and preparation timing are provenance, not independently
verifiable measurements. This export verifier is not a file-authenticity system.

## Numerical evidence

The analytic ±1 states have energy 2.99999997 and Lz ±1 at 32³. Norm drift after
250 float64 steps is approximately 3×10⁻¹⁴; fixed-trap energy drift is below
10⁻⁸. Refinement of dt at 64³ checks second-order error against the exact complex
state, including global phase. Analytic circulation-integral error falls from
about 0.0079 at 32³ to below 0.002 at 64³.

For the stirred recipe at t=5:

| Calculation | Norm | Energy | Lz/Nℏ | Contour winding | Qualified + / − crossings |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64³ float64, dt=.004 | 1 | 9.70471 | 2.95846 | 2 | 4 / 1 |
| 64³ float64, dt=.002 | 1 | 9.70479 | 2.95851 | 2 | 4 / 1 |
| 128³ float64, dt=.004 | 1 | 9.70470 | 2.95862 | 2 | 3 / 1 |
| 128³ float64, box=32, dx=.25 | 1 | 9.70472 | 2.95904 | 2 | 4 / 1 |
| 64³ WebGPU float32 | 0.9998877 | 9.70326 | 2.95839 | 2 | 4 / 1 |

The temporal refinement full-field L² difference is 0.0000973. The 64³/128³
comparison on shared nodes is 0.00343. The GPU-to-float64 evolution difference
from the same prepared initial field is 0.00106; independent preparation differs
by 0.0000221. Every case starts with zero winding and no qualified crossings.
The float64 energy change between t=4 and t=5 is about 7×10⁻⁶.

Doubling the box at the same spacing changes the shared-volume field by
0.00471 in L²; probability outside the original box is 0.0000126. The larger
box reduces final boundary probability below 2×10⁻¹³. The default box is a
bounded teaching demonstration, not a claim of arbitrary-duration convergence.

The differing small crossing counts are a **detector-resolution limit**, despite
agreement in net contour winding and angular momentum. Do not report those
counts as a converged physical observable. Longer/stronger stirring can send
waves to the periodic boundary; increase the box and grid together and recheck.

## Browser evidence and scientific scope

Actual Chrome used NVIDIA/Blackwell hardware WebGPU (fallback=false). Local and
extracted static ZIP checks exercise direct-link routing, positive/negative
preparations, run/pause/step/reset, immutable pinning, JSON/CSV, independent replay,
state-preserving navigation, the existing quantum workspace, and 1440/390/320 px
layouts. Injected norm and boundary failures stop after one step; lost-device
reads fail explicitly. Existing single-cloud release and split-sequence GPU
exports still pass their independent CPU comparison after the shared potential
shader extension. Screenshots/reports are under ignored `artifacts/vortex/`.

Automated numerical results and browser controls establish implementation
behavior within those checks, not experimental agreement over all settings.
The physical motivation is [Madison et al., PRL 84, 806 (2000),
Vortex formation in a stirred Bose–Einstein condensate](https://arxiv.org/abs/cond-mat/9912015).
They observed vortices in optically stirred trapped Rb-87. Our orbiting Gaussian,
parameters, preparations and conservative model are teaching choices; this is
not a reproduction of their apparatus, threshold or measured vortex lifetime.
