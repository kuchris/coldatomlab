"""Reproduce an exported run from its parameters and release protocol."""

import argparse
import json
from pathlib import Path

import numpy as np

from .solver import replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    data = json.loads(args.experiment.read_text(encoding="utf-8"))
    sim = replay(data)
    saved = np.asarray(data["psi_real"]) + 1j * np.asarray(data["psi_imag"])
    if saved.shape != sim.psi.shape:
        raise ValueError("Saved wavefunction shape does not match the configured grid.")
    error = float(np.max(np.abs(sim.psi - saved)))
    print(
        json.dumps(
            {"replayed": True, "max_wavefunction_error": error, "diagnostics": sim.diagnostics()},
            indent=2,
        )
    )
    if not np.isfinite(error) or error > 1e-8:
        raise SystemExit("Replay differs from the saved state; check solver and NumPy versions.")


if __name__ == "__main__":
    main()
