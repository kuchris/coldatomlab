"""Package only static WebGPU assets; no Python simulation server is required."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    web = Path(__file__).resolve().parents[1] / "coldatomlab" / "web"
    out = Path("artifacts/coldatomlab-webgpu.zip")
    out.parent.mkdir(exist_ok=True)
    files = (
        "gpu.html",
        "gpu3d.js",
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
        archive.writestr("index.html", (web / "gpu.html").read_text(encoding="utf-8"))
        archive.writestr(
            "README.txt",
            "Cold Atom Lab - standalone WebGPU 3D lab\n\nUpload this folder to an HTTPS static host, or serve it locally:\n  python -m http.server 8000\nThen open http://localhost:8000 in hardware-accelerated Chrome or Edge.\nDo not open index.html directly as a file: WebGPU requires a secure context.\n\nAll 3D preparation and evolution run in the browser. No Python simulation API, CUDA installation, account or remote asset is used. Python above is only an optional static file server.\n\nGPU calculations use float32. Inspect norm drift and compare quantitative results with the float64 CPU reference in the full repository. GPU exports use coldatomlab-webgpu-3d-v1; the repository replay command performs a toleranced CPU comparison, not bitwise GPU replay.\n",
        )
    print(out.resolve())


if __name__ == "__main__":
    main()
