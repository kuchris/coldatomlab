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
