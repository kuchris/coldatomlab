"""Reproduce an exported run from its parameters and release protocol."""

import argparse
import json
from pathlib import Path

import numpy as np

from .imaging import Camera, form_image
from .solver import Config, replay
from .solver3d import replay3d


def verify_run(data):
    sim = replay(data)
    saved = np.asarray(data["psi_real"]) + 1j * np.asarray(data["psi_imag"])
    if saved.shape != sim.psi.shape:
        raise ValueError("Saved wavefunction shape does not match the configured grid.")
    error = float(np.max(np.abs(sim.psi - saved)))
    if not np.isfinite(error) or error > 1e-8:
        raise ValueError("Replay differs from the saved state; check solver and NumPy versions.")
    return {"replayed": True, "max_wavefunction_error": error, "diagnostics": sim.diagnostics()}


def verify_export(data):
    if data.get("schema") == "coldatomlab-pulse-v1":
        from .pulse import verify_export as verify_pulse

        return verify_pulse(data)
    if data.get("schema") == "coldatomlab-echo-v1":
        from .echo import verify_export as verify_echo

        return verify_echo(data)
    if data.get("schema") == "coldatomlab-preparation-v1":
        from .preparation import verify_export as verify_preparation

        return verify_preparation(data)
    if data.get("schema") == "coldatomlab-twomode-v1":
        from .twomode import verify_export as verify_twomode

        return verify_twomode(data)
    if data.get("schema") == "coldatomlab-scan3d-v1":
        from .scan3d import verify_scan

        return verify_scan(data)
    if data.get("schema") == "coldatomlab-camera3d-comparison-v1":
        return {key: verify_export(data[key]) for key in ("reference", "current")}
    if data.get("schema") == "coldatomlab-camera3d-v1":
        from .camera3d import verify_camera

        return {"source": verify_export(data["source"]), **verify_camera(data)}
    if data.get("schema") == "coldatomlab-3d-comparison-v1":
        return {key: verify_export(data[key]) for key in ("reference", "current")}
    if data.get("schema") == "coldatomlab-webgpu-3d-v1":
        # Float32 GPU work is compared with an independent float64 reference;
        # it is deliberately not advertised as bitwise GPU replay.
        sim = replay3d({**data, "schema": "coldatomlab-3d-v1"})
        real, imag = np.asarray(data["psi_real"]), np.asarray(data["psi_imag"])
        if real.shape != sim.psi.shape or imag.shape != sim.psi.shape:
            raise ValueError("Saved GPU wavefunction shape does not match the grid.")
        saved = real + 1j * imag
        if not np.isfinite(saved).all():
            raise ValueError("Saved GPU field contains non-finite values.")
        if data.get("array_order") != "x,y,z" or not np.allclose(
            data["x"], sim.x, rtol=0, atol=1e-12
        ):
            raise ValueError("Saved GPU coordinate convention does not match.")
        if any(
            not np.isclose(data["scales"].get(k, float("nan")), v, rtol=2e-12, atol=0)
            for k, v in sim.config.scales.items()
        ):
            raise ValueError("Saved GPU physical scales do not match.")
        reference = sim.diagnostics()
        error = float(np.linalg.norm((saved - sim.psi).ravel()) * sim.dx**1.5)
        sim.psi = saved
        observed = sim.diagnostics()
        width_errors = (np.array(observed["widths"]) / reference["widths"] - 1).tolist()
        aspect_errors = [observed[k] / reference[k] - 1 for k in ("aspect_xz", "aspect_yz")]
        if (
            error > 0.005
            or abs(observed["norm"] - 1) > 0.001
            or max(abs(v) for v in width_errors + aspect_errors) > 0.005
        ):
            raise ValueError(
                "WebGPU field exceeds the float32 CPU-reference comparison tolerances."
            )
        return {
            "verified_against_cpu_reference": True,
            "exact_gpu_replay": False,
            "wavefunction_l2_difference": error,
            "relative_width_differences": width_errors,
            "relative_aspect_differences": aspect_errors,
            "gpu_field_diagnostics": observed,
            "cpu_reference_diagnostics": reference,
            "tolerances": {
                "wavefunction_l2": 0.005,
                "norm_drift": 0.001,
                "relative_width_and_aspect": 0.005,
            },
        }
    if data.get("schema") == "coldatomlab-3d-v1":
        sim = replay3d(data)
        real, imag = np.asarray(data["psi_real"]), np.asarray(data["psi_imag"])
        if real.shape != sim.psi.shape or imag.shape != sim.psi.shape:
            raise ValueError("Saved 3D wavefunction shape does not match the grid.")
        if data.get("array_order") != "x,y,z" or not np.array_equal(data["x"], sim.x):
            raise ValueError("Saved 3D coordinate/array convention does not match the grid.")
        if data.get("scales") != sim.config.scales:
            raise ValueError("Saved 3D physical scales do not match the configuration.")
        error = float(np.max(abs(sim.psi - (real + 1j * imag))))
        if not np.isfinite(error) or error > 1e-8:
            raise ValueError("3D replay differs from the saved wavefunction.")
        return {"replayed": True, "max_wavefunction_error": error, "diagnostics": sim.diagnostics()}
    if data.get("schema") == "coldatomlab-camera-comparison-v1":
        return {key: verify_export(data[key]) for key in ("reference", "current")}
    if data.get("schema") == "coldatomlab-camera-v1":
        source = data["source"]
        result = verify_run(source)
        config = Config(**source["config"])
        coordinates = np.arange(config.n) * (config.length / config.n) - config.length / 2
        if not np.array_equal(source["x"], coordinates):
            raise ValueError(
                "Saved camera source coordinates disagree with its grid configuration."
            )
        psi = np.asarray(source["psi_real"]) + 1j * np.asarray(source["psi_imag"])
        regenerated = form_image(
            abs(psi) ** 2,
            coordinates,
            config.physical,
            Camera(**data["image"]["camera"]),
        )
        if regenerated != data["image"]:
            raise ValueError(
                "Camera replay differs: check settings, frames, seed and NumPy version."
            )
        return {**result, "camera_replayed": True, "measured": regenerated["measured"]}
    if data.get("schema") == "coldatomlab-comparison-v1":
        return {key: verify_run(data[key]) for key in ("reference", "current")}
    return verify_run(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    data = json.loads(args.experiment.read_text(encoding="utf-8"))
    print(json.dumps(verify_export(data), indent=2))


if __name__ == "__main__":
    main()
