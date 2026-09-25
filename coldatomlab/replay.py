"""Reproduce an exported run from its parameters and release protocol."""

import argparse
import json
from pathlib import Path

import numpy as np

from .solver import replay


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
