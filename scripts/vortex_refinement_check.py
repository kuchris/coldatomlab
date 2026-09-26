"""Slow independent time, grid and box refinement of the stirred recipe."""

import json
import time
from pathlib import Path

import numpy as np

from coldatomlab.vortex import Vortex

out = Path("artifacts/vortex")
out.mkdir(parents=True, exist_ok=True)
base = dict(n=64, g=300, charge=0, height=12, stir_time=4, duration=5)
report = {}
for name, extra in [
    ("base", {}),
    ("half_dt", dict(dt=0.002)),
    ("fine", dict(n=128)),
    ("large", dict(n=128, length=32)),
]:
    c = base | extra
    start = time.perf_counter()
    s = Vortex(c)
    rows = [s.diagnostics()]
    for i in range(5):
        s.advance(round(1 / s.config["dt"]))
        rows.append(s.diagnostics())
        print(name, i + 1, rows[-1], flush=True)
    np.savez_compressed(out / f"{name}.npz", psi=s.psi, initial=s.initial)
    report[name] = {"config": s.config, "diagnostics": rows, "seconds": time.perf_counter() - start}
    (out / "refinement.json").write_text(json.dumps(report, indent=2), encoding="utf8")

# Compare on physically identical nodes; no fitted global phase is removed.
b = np.load(out / "base.npz")["psi"]
h = np.load(out / "half_dt.npz")["psi"]
f = np.load(out / "fine.npz")["psi"][::2, ::2, ::2]
large = np.load(out / "large.npz")["psi"]
crop = large[32:96, 32:96, 32:96]
errors = {
    "half_dt_l2": float(np.linalg.norm(b - h) * 0.25**1.5),
    "fine_grid_l2": float(np.linalg.norm(b - f) * 0.25**1.5),
    "larger_box_l2_shared_volume": float(np.linalg.norm(b - crop) * 0.25**1.5),
    "mass_outside_original_box": float(
        (np.sum(abs(large) ** 2) - np.sum(abs(crop) ** 2)) * 0.25**3
    ),
}
assert errors["half_dt_l2"] < 0.0002
assert errors["fine_grid_l2"] < 0.005
assert errors["larger_box_l2_shared_volume"] < 0.006
for case in report.values():
    rows = case["diagnostics"]
    assert rows[0]["winding"] == 0 and rows[0]["positive"] == rows[0]["negative"] == 0
    assert rows[-1]["winding"] == 2 and rows[-1]["positive"] > 0
    assert abs(rows[-1]["norm"] - 1) < 1e-9
    assert abs(rows[-1]["energy"] - rows[-2]["energy"]) < 0.00002
report["field_comparisons"] = errors
(out / "refinement.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print(errors, flush=True)
