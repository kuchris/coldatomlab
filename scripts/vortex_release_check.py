"""Independent analytic free-flight and hold/release convergence checks."""

import json
import math
from pathlib import Path

import numpy as np
from scipy.fft import fftn, ifftn

from coldatomlab.vortex import Vortex


def exact(s, t):
    r, z = 1 + 1j * t, 1 + 2j * t
    return (
        2**0.25
        / math.pi**0.75
        * np.exp(-(s.X**2 + s.Y**2) / (2 * r) - s.Z**2 / z)
        * (s.X + 1j * s.Y)
        / (r**2 * np.sqrt(z))
    )


def main():
    report = {"free_box_grid": [], "hold_release_dt": []}
    # With g=V=0 the same spectral propagator composes exactly. Use it once
    # here to isolate spatial/box errors; pytest exercises all 500 split steps.
    for n, length in [(64, 24), (128, 24), (64, 32), (128, 32)]:
        s = Vortex(dict(n=n, length=length, width=1))
        s.release()
        s.psi = ifftn(fftn(s.psi) * s.kinetic**500)
        s.steps = 500
        error = float(np.linalg.norm(s.psi - exact(s, 2)) * s.dx**1.5)
        report["free_box_grid"].append(dict(n=n, length=length, l2=error, **s.diagnostics()))
    assert report["free_box_grid"][0]["l2"] < 9e-5
    assert report["free_box_grid"][-1]["l2"] < 2e-7

    for dt in [0.008, 0.004, 0.002]:
        s = Vortex(dict(n=64, length=24, dt=dt))
        s.advance(round(0.4 / dt))
        s.release()
        s.advance(round(0.4 / dt))
        error = float(np.linalg.norm(s.psi - exact(s, 0.4) * np.exp(-1.2j)) * s.dx**1.5)
        report["hold_release_dt"].append(dict(dt=dt, l2=error, **s.diagnostics()))
    errors = [row["l2"] for row in report["hold_release_dt"]]
    assert 3.8 < errors[0] / errors[1] < 4.2
    assert 3.8 < errors[1] / errors[2] < 4.2

    # Quench the same normalized reference into g=10 at release: interactions
    # must remain active, and refinement must conserve the free GPE energy.
    initial = Vortex(dict(n=32, width=1)).initial
    states, rows = [], []
    for dt in [0.008, 0.004, 0.002]:
        s = Vortex(dict(n=32, width=1, g=10, dt=dt), initial)
        s.release()
        start = s.diagnostics()
        s.advance(round(0.4 / dt))
        end = s.diagnostics()
        states.append(s.psi)
        rows.append(dict(dt=dt, energy_drift=end["energy"] - start["energy"], **end))
        assert abs(end["norm"] - 1) < 1e-11
    differences = [float(np.linalg.norm(states[i] - states[i + 1]) * 0.5**1.5) for i in [0, 1]]
    assert 3.8 < differences[0] / differences[1] < 4.2
    free = Vortex(dict(n=32, width=1), initial)
    free.release()
    free.advance(100)
    interaction_effect = float(np.linalg.norm(states[1] - free.psi) * 0.5**1.5)
    assert interaction_effect > 0.01
    report["interacting_release"] = dict(
        rows=rows, successive_l2=differences, effect_l2=interaction_effect
    )
    out = Path("artifacts/vortex-imaging/release-refinement.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
