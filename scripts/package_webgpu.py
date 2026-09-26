"""Package only static WebGPU assets; no Python simulation server is required."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    web = Path(__file__).resolve().parents[1] / "coldatomlab" / "web"
    out = Path("artifacts/coldatomlab-webgpu.zip")
    out.parent.mkdir(exist_ok=True)
    files = (
        "precision.js",
        "precision-ui.js",
        "readout.js",
        "readout-ui.js",
        "pulse.js",
        "pulse-ui.js",
        "echo.js",
        "echo-ui.js",
        "preparation.js",
        "preparation-ui.js",
        "quantum-host.js",
        "quantum.html",
        "twomode.js",
        "twomode-ui.js",
        "twomode.css",
        "gpu.html",
        "gpu3d.js",
        "scan3d.js",
        "scan3d-ui.js",
        "camera3d.js",
        "camera3d-ui.js",
        "interferometry3d.js",
        "gpu-page.js",
        "lab3d.js",
        "surface3d.js",
        "style.css",
        "dashboard.css",
        "lab3d.css",
        "model3d.html",
    )
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(web / name, name)
        archive.writestr("index.html", (web / "browser-home.html").read_text(encoding="utf-8"))
        archive.writestr(
            "README.txt",
            "Cold Atom Lab - standalone WebGPU 3D lab\n\nUpload this folder to an HTTPS static host, or serve it locally:\n  python -m http.server 8000\nThen open http://localhost:8000 in hardware-accelerated Chrome or Edge.\nDo not open index.html directly as a file: WebGPU requires a secure context.\n\nAll 3D preparation and evolution run in the browser. No Python simulation API, CUDA installation, account or remote asset is used. Python above is only an optional static file server.\n\nGPU calculations use float32. Inspect norm drift and compare quantitative results with the float64 CPU reference in the full repository. GPU exports use coldatomlab-webgpu-3d-v1; the repository replay command performs a toleranced CPU comparison, not bitwise GPU replay.\n",
        )
        archive.writestr(
            "QUANTUM.txt",
            "Cold Atom Lab - two-mode quantum coherence lab\n\n"
            "Open /#quantum on the same static host. This experiment uses "
            "browser float64 arithmetic and requires no GPU or simulation API.\n"
            "It evolves a fixed-N occupation state in two fixed spatial modes. "
            "It is not coupled to the 3D GPE or absorption camera. Model assumptions "
            "and primary paper references appear at the bottom of the page.\n"
            "Export reproducible data saves complete amplitudes, history and seeded "
            "ideal number counts. In the full repository, independently verify with:\n"
            "  uv run python -m coldatomlab.replay path/to/coldatomlab-quantum.json\n\n"
            "The preparation variation panel compares independent phase and static "
            "bias offsets, individual coherence and ensemble coherence. Its JSON "
            "exports can be checked with the same replay command. Uniform ranges "
            "are teaching choices, not calibrated laboratory noise.\n\n"
            "The Spin echo comparison uses paired static offsets with and without "
            "an ideal instantaneous midpoint L/R swap. J=0 during the holds; "
            "no microwave field or finite pulse is modeled. Its JSON is also "
            "supported by the repository replay command.\n\n"
            "Finite pulse comparison evolves short/nominal/long rectangular "
            "tunnelling pulses alongside no-pulse and instantaneous references. "
            "Bias and interactions remain active during the pulse. Its full "
            "JSON export is supported by the same replay command.\n",
        )
    print(out.resolve())


if __name__ == "__main__":
    main()
