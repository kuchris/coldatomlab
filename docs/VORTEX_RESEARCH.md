# Reproducible interacting vortex experiments (v0.18)

The release combines an automatic experiment with a stationary interacting
initial state and a quantitative model comparison. It is a zero-temperature
mean-field calculation with numerical checks, not an experimental reconstruction.

## Run an experiment

**Interacting vortex** is selected on entry. Set hold and flight times in ms, and press
**Run experiment**. The sequence prepares the state, holds it in the selected
trap, releases trap and beam, evolves to the TOF endpoint, calculates the
applicable paper reference, and captures the frozen field. Camera settings are
frozen when the sequence starts. Edits made to camera controls during a run apply
to the next acquisition. Manual preparation and controls are in collapsed panels.

Release and stop times use integer simulation steps, not wall-clock timing.
`hold_steps=round(hold_ms/step_ms)` and similarly for flight; the actual rounded
times appear in the saved run. There is no overshoot by a rendering batch.
Stop during preparation discards that incomplete preparation and preserves the
previous verified state. Stop during evolution saves the actual partial state
without fabricating an endpoint image. Leaving the Vortex Lab requests a stop
after the current calculation batch. Reload closes the session.

The latest three runs are kept automatically in page memory. **Compare runs**
opens summaries and core/cloud curves; each run can be exported as JSON before
it leaves this three-run window. These records remain fixed during later runs.
No data is uploaded. An automatic-run export embeds the full source once, and
its camera image implicitly uses that source. Standalone camera exports still
embed their own source field.

## Physical parameters and stationary state

Use the norm-one three-dimensional GPE

`i ∂t ψ = [−∇²/2 + (x²+y²+λ²z²)/2 + g|ψ|²]ψ`, `∫|ψ|² d³r=1`.

For the selected Rb-87 mass, `ω₀=2π fr`, `a₀=√(ℏ/mω₀)`, `t₀=1/ω₀`,
`λ=fz/fr`, `g=4π N aₛ/a₀`. N, scattering length and trap frequencies drive the
calculation. Editing advanced g instead updates the equivalent aₛ. The current
shared backend supports fr=10–100 Hz, fz=5–200 Hz and .5≤λ≤2; the UI rejects
unsupported configurations. g is limited to 1000 and aₛ to 0–10 nm.

The paper recipe uses N=10,000, fr=fz=50 Hz and g=80π, so Naₛ/a₀=20. Its derived
aₛ is approximately 3.05 nm. This maps the paper's dimensionless case to physical
units; no magnetic-field calibration or claim about standard Rb-87 scattering
conditions is implied. Other N/aₛ pairs with the same g have the same norm-one
dynamics and different imaging optical depth.

Stationary preparation starts from the charge ±1 oscillator state and performs
normalized imaginary-time evolution in the harmonic trap. Exact local nonlinear
imaginary-time flow and a kinetic Fourier step are composed symmetrically. A
fourfold rotation-sector projection removes numerical drift into the zero-charge
state: `Pq ψ = (1/4) Σk exp(−iqkπ/2) ψ(Rk r)`. It retains angular harmonics in
the same discrete sector; continuous axial symmetry is approached on refinement.
This is a centered constrained excited state, not an unconstrained ground state
or a demonstration of dynamical stability against all perturbations.

The final *full* GPE residual is `||Hψ−μψ||/(|μ| ||ψ||)`, with
`μ=<ψ|H|ψ>/<ψ|ψ>`. Both residual and chemical potential are reported for the
vortex itself. A residual above .0005 is rejected, even if successive iterates
change little. CPU/GPU preparation is independent. Only imaginary-time
preparation normalizes. Real-time evolution retains the existing no-rescaling
rule and .001 norm/boundary stopping thresholds.

The legacy imprint remains available as a separately labeled preparation.
Changing its g does not silently promote it to a stationary solution.

## The literature comparison

Source: [Lundh, Pethick & Smith, Physical Review A 58, 4816 (1998),
Vortices in Bose-Einstein-Condensed Atomic Clouds](https://arxiv.org/abs/cond-mat/9805351).
The relevant definitions and approximation are in section III B, equations
36–39 and figure 5. [Dalfovo et al., Reviews of Modern Physics 71, 463
(1999)](https://arxiv.org/abs/cond-mat/9806038) supplies the broader mean-field
context and its limits.

The reference assumes `ψ=f(r,t) exp(iφ) × axial Gaussian`, with
`2π∫r|f|²dr=1` and Gaussian width Z. In oscillator units its density dynamics are

`i ∂t f = [−(∂r²+r⁻¹∂r−r⁻²)/2 + g|f|²/(√(2π) Z)] f`,

`Z''=Z⁻³ + g [2π∫r|f|⁴dr]/(√(2π) Z²)`.

The spatially constant real term in the paper's radial equation has been removed
by a global-phase gauge; it does not affect density or the core/width observables.
Stationary preparation includes radial trap r²/2 and solves
`Z⁴ − [g ∫|f|⁴d²r/√(2π)] Z − 1 = 0`. The reported *radial* μ is not the full
3D chemical potential. Full 3D and this separable approximation have different
initial profiles; differences must not be presented as solver error.

The radial solver uses half-cell finite volumes, a regular charge-one origin
and a zero outer-face boundary. Transforming to `u=√(2πr dr) f` gives a real
symmetric tridiagonal kinetic operator. Crank–Nicolson kinetic evolution,
nonlinear phase half-steps and a coupled axial velocity-Verlet step retain norm
without rescaling. The interactive reference uses 512 radial cells, radius 24a₀,
dt=.002t₀ and TOF 0–2t₀. Python independently implements the same equations;
the refinement runner also checks 256 and 1024 cells.

The comparison is enabled for an isotropic, unstirred stationary charge ±1 run.
The zero-interaction stationary case supplies an analytic limit. Stirring and
other traps still run but do not get a falsely applicable paper curve. Camera
axis does not change this model-state comparison; side-view images do not get
the isolated-core camera estimate. The reference curve is newly calculated from the stated equations, not
digitized experimental data or a claim to reproduce every figure in the paper.

## Comparable observables

The core radius is the first radius where the radial density reaches **1/e of
its peak**. The cloud radius is `sqrt(<x²+y²>)`; their ratio is plotted against
TOF/t₀. For the full 3D state, the radial profile is the azimuthally averaged
z-column density, using 32 angles and cubic interpolation at quarter-cell radial
spacing. Negative interpolation overshoots are clipped to zero. Interpolation
does not increase physical grid resolution; the grid must be refined.

For the separable reference this projection gives the same radial shape as |f|².
For full 3D it defines a reproducible comparison without assuming Gaussian
axial shape. A noninteracting vortex has a constant ratio approximately .282.
This model-density measure is independent of the camera estimator, which uses
a noisy image and reports an apparent **half-depth diameter**. Do not compare
those two numbers as if they used the same definition.

## Reproducibility and validation

```powershell
uv run pytest
uv run python -m scripts.vortex_stationary_check
uv run python -m scripts.vortex_sequence_browser_check
uv run python -m scripts.vortex_browser_check
uv run python -m scripts.vortex_imaging_browser_check
uv run python -m coldatomlab.replay path/to/coldatomlab-run-1.json
```

`coldatomlab-vortex-v3` records the physical trap, preparation choice and paper
core history. `coldatomlab-vortex-sequence-v1` records requested/rounded times,
completion status, source, image and applicable paper reference. Python checks
the preparation against the initial field, propagates it independently, verifies
release timing and measurements, rebuilds camera exposures, and recalculates
the reference curve. These are numerical consistency checks, not signatures or
file authentication. Earlier state and image schemas remain readable.

Numerical verification on 2026-09-26:

- The complete numerical suite passed **384 tests**, followed by **14 new
  automatic-sequence/replay tests**. These cover the analytic oscillator,
  stationary hold, physical scales, independent paper equations, seeded camera
  reconstruction, and rejection of altered timing, preparation, core and camera
  results. Earlier state/image export schemas remain covered.
- For Na/a₀=20, isotropic trap, 128³, L=32a₀, float64 preparation gives
  μ=5.54165647ℏω₀ and full stationary residual 2.38×10⁻⁶. The hardware GPU
  residual is 1.27×10⁻⁵. These residuals do not by themselves establish spatial
  accuracy of the core estimator.
- A full **default one-button hardware WebGPU run**, N=10,000, hold=0,
  TOF=2t₀=6.366 ms, was exported and independently replayed in Python. Initial
  field L² difference was 1.64×10⁻⁵; final propagation difference was
  2.14×10⁻⁴. GPU final norm was .999779873, Lz=.999999999ℏ and boundary
  probability 2.42×10⁻¹⁰. No real-time normalization was used. The camera raw
  frames/core measurements and all reference-curve rows also passed replay.
- At fixed L=24a₀, refining 64³→128³ changed the core/cloud ratio by up to
  .00852, predominantly at early time: coarse grids underestimate the small
  initial core. The final ratio changed from .21653341 to .21653085.
- At fixed L=16a₀, 64³→128³ changed the ratio by at most .000684 through
  ωt=1.2. The default 128³/L=32 initial ratio differs from the finest
  128³/L=16 result by .000626 (about .34%). This bounds the tested refinement
  change; it is not a statistical confidence interval or a proof of exactness.
- At fixed spacing Δx=.25a₀, doubling the box L=16→32 changed the ratio by
  less than 2.75×10⁻⁹ through ωt=1.2. The small box becomes unsuitable later:
  its final edge probability is .00929 at ωt=2. The default L=32 run stays
  below 7.80×10⁻¹² in float64. Comparing L=24/128³ with L=32/128³ at the
  endpoint changes the ratio by .0000204; that latter comparison changes
  both box and spacing and must not be called an isolated box test.
- The default float64 run has maximum norm drift 3.58×10⁻¹³ and post-release
  free-energy drift 3.31×10⁻⁶ℏω₀. Energy across the removal of the trap is
  not conserved, so the trapped energy is not used as the free-flight baseline.
- Halving the full-3D step .004→.002t₀ at 128³, L=24 changed the final field
  by 3.37×10⁻⁶ in L² and the final ratio by 3.92×10⁻⁸. This measures temporal
  error at that spatial discretization, not total physical-model accuracy.
- The paper's reduced model was calculated on 256, 512 and 1024 radial cells.
  At Na/a₀=20 its final ratio was .21513442, .21477832 and .21469139,
  respectively. The full-3D default float64 final ratio was .21655123.
  Their difference is a **model discrepancy**, separate from both solvers'
  discretization changes. For g=0 the analytic ratio is approximately .282.

Browser verification is separate from numerical verification. Hardware Chrome
passed the local and unpacked-static one-button workflow, frozen camera settings,
exact rounded release/endpoint, repeated runs, three-run retention, preparation
and evolution Stop, navigation Stop, JSON downloads/replay, comparison quantity
selection and 390/320 px layouts. A negative stationary vortex with a different
75 Hz trap was also replayed on both local and static versions. Original manual vortex/imaging and existing
3D-camera controls also passed. The complete default 128³ sequence was checked
locally; the static acceptance uses a 32³ short run to exercise packaging and
controls, not to claim convergence of a coarse vortex core.

Generated reports are kept outside version control under
`artifacts/vortex-sequence/`: `refinement.json`, `errors.json`, `browser.json`,
full fields and downloaded sequences. The refinement command is intentionally
an offline calculation and can take tens of minutes. `--analyse` rereads its
saved measurements and checks declared tolerances without recomputing fields.

Finite temperature, damping, depletion, atom loss, vortex nucleation thresholds
and vortex lifetimes are outside this conservative calculation. Validating a
curve within this model does not establish those omitted mechanisms.
