# Browser GPU execution (v0.6)

v0.7 extends the same backend to coherent Gaussian pairs and a driven 3D interferometer. See [interferometry conventions and new validation](INTERFEROMETER3D.md). The original single-cloud checks below retain their own scope; they are not substituted for the sequence-specific tests.

The 3D lab now defaults to **WebGPU · browser GPU · float32**. The CPU float64 reference remains selectable in the full local app. The standalone `gpu.html` contains only the 3D lab and makes no simulation API requests; it can be served by an ordinary static HTTPS host. No CUDA installation is required.

## Supported execution

Hardware WebGPU was verified in installed Chrome and Edge on this Windows machine; the adapter identifies itself as NVIDIA / Blackwell, non-fallback. The detected discrete card is RTX 5070 Ti with about 16 GiB VRAM. Bundled Playwright Chromium exposed no adapter here, so numerical GPU tests explicitly use installed Chrome and reject software adapters. This does not prove that every embedded/in-app browser exposes WebGPU.

The page must use HTTPS or localhost. Missing hardware/API support produces an explicit error and suggests a supported browser or the full app's CPU reference. There is no silent switch to CPU. The standalone page disables CPU selection because it has no simulation server.

See the official [WebGPU adapter API](https://developer.mozilla.org/en-US/docs/Web/API/GPU/requestAdapter) and [WGSL specification](https://www.w3.org/TR/WGSL/). Current WGSL uses f32 (and optional f16), without native f64 arithmetic. This implementation uses complex pairs of f32 and does not emulate f64.

## Algorithm and numerical contract

The physical scales, norm-one convention, repulsive interaction and complete release are identical to [MODEL3D.md](MODEL3D.md). Each workgroup performs an entire one-dimensional radix-two FFT in shared memory; three axis passes form the 3D transform. Butterfly phases are generated in JavaScript double precision and stored as float32 constants. The supported grids are **32³, 64³, 128³**. Unsupported 48³/96³ settings are rejected, not rounded. Loading a GPU preset visibly selects its supported grid: the Gaussian uses 64³ and TF uses 128³; the CPU equivalents remain 48³ and 96³.

Imaginary-time flow and norm reduction stay on the GPU. Its nonlinear local flow uses a small-argument series for the removable singularity in `(1-exp(-tau*v))/v`. Normalization is performed only during imaginary-time preparation. Convergence is checked every 50 iterations against an L2 change of `3e-6`, up to 6,000 iterations. A separately measured relative stationary residual above `5e-4` rejects preparation. The float64 reference retains its stricter `2e-7` iterate-change criterion.

Real-time Strang evolution never renormalizes. Per-step GPU reductions stop at the first step exceeding 0.1% boundary probability or 0.1% norm drift. The boundary band and prepared-cloud rejection match the CPU method. GPU device loss is surfaced; re-prepare or select CPU. Diagnostic widths and energies are calculated from the downloaded field and its spectral kinetic operator, with JavaScript double-precision accumulation. Slices, projections, rendering and TF reference curves remain independent of field evolution. The browser integrates the reference TF ODE with RK4 steps no larger than 0.005.

## Measured performance

Fresh calculations on the machine above, with no prepared-state cache:

| Case | Fresh GPU setup, preparation and initial diagnostics | Evolution, including recorded diagnostics |
|---|---:|---:|
| Noninteracting 64³, L=24, tau=2 | 0.12 s | 1.82 s |
| Interacting 64³, N=20,000, L=24, tau=2 | 0.41 s | 1.83 s |
| TF 128³, N=150,000, L=48, tau=3 | 1.34 s | 4.18 s |

These are browser-library measurements at batches of 20 steps, including GPU work completion/readback, excluding live surface rendering and export serialization. Interactive playback uses batches of eight and includes rendering, so its wall time is longer. The packaged static TF page was also tested end to end: 1.81 s from Prepare click to Ready, and 10.91 s from Run click to Complete at 128³, with no API requests or page errors. Separate first-use setup observations were about 0.25–0.46 s; graphics-driver shader caches and other workload affect setup. Every case creates a new simulation/device and computes a new field; no result cache is involved.

Before this change the 64³ CPU preparation took 28.32 s. A separate safe CPU optimization uses real FFTs during the real-valued stationary-state preparation, reducing it to 23.44 s. That CPU change preserved the prepared field to 8.8e-15 maximum difference and the field after 200 real steps to 5.9e-15. The GPU has a different precision and stopping threshold, so its speed difference is accompanied by the accuracy checks below rather than described as identical arithmetic.

## Numerical evidence

`uv run python -X utf8 -m scripts.webgpu_check` runs actual hardware WebGPU in Chrome. Reports go to ignored `artifacts/webgpu/validation.json`.

- A seeded complex random 32³ FFT agrees with the independent NumPy transform to relative L2 **1.54e-7**. Maximum complex round-trip error is **1.34e-6**.
- The noninteracting 64³ release agrees with the exact Gaussian widths within the declared 0.1% target; final norm is **0.9998278773** at tau=2.
- The interacting 64³ release at tau=2 differs from the matching float64 CPU widths by at most **1.44e-5 relative (0.00144%)**; complex-field L2 difference is **2.12e-4**. Final norm is **0.9998143808**, a **0.0186%** drift. Relative energy change is about **−0.0222%**.
- The 128³ TF release at tau=3 differs from the previously validated 128³/L=48 float64 widths by at most **3.03e-5 relative (0.00303%)**; final norm is **0.9997574817**. This comparison uses matching grids, not the different 96³ CPU UI preset.
- Halving real-time and preparation steps in the moderate case changes widths by less than 0.005%. Float32 round-off is visible: the half-real-time-step run has norm **0.9994975727**, worse than the baseline despite its smaller step. Smaller dt is not automatically more accurate after many f32 FFTs; use float64 for strict conservation/precision work.
- A shifted Gaussian reaches the boundary guard after exactly one step, and a destroyed GPU device raises an error. Preparation, release, pause/step/finish/reset, rotation, density views, invalid-grid recovery, export, 390px/320px layouts and unsupported-hardware reporting pass in the actual browser without simulation API calls.

The acceptance limits for demonstrated GPU/CPU comparisons are 0.5% relative width/aspect difference, 0.1% norm drift, and 0.005 complex-field L2 difference. These are explicit engineering tolerances, not universal scientific error bounds. Thermal physics, losses and experimental calibration remain outside the model. The prior float64 validation is not relabeled as GPU validation.

## Exports and sharing

GPU records use **`coldatomlab-webgpu-3d-v1`** with adapter/precision, coordinates, physical scales, preparation/release metadata and the complete final complex field. The existing command:

```powershell
uv run python -m coldatomlab.replay path/to/gpu-export.json
```

recalculates a float64 CPU reference, checks saved coordinates/scales, compares field/widths/aspects/norm, and returns `verified_against_cpu_reference: true` and `exact_gpu_replay: false` when tolerances pass. It does not claim bitwise reproducibility across GPU vendors. CPU exports retain their original exact-field replay behavior.

Create a standalone static bundle:

```powershell
uv run python -m scripts.package_webgpu
```

This creates ignored `artifacts/coldatomlab-webgpu.zip` containing only the listed HTML/CSS/JS assets and instructions. Extract and serve it locally (`python -m http.server 8000`) or upload the files to a static HTTPS host. The Python command here is just a file server. No public deployment is performed by packaging.

## Browser package navigation

The packaged `index.html` is the experiment library, with 04 (3D WebGPU) and
05 (two-mode quantum) in project order. Both experiments open in the same tab.
The Cold Atom Lab logo returns to that library; in the full local app it returns
to the complete dashboard. Experiments 01–03 require the local Python solver.
