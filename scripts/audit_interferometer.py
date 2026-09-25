"""Audit saved numerical evidence against the v0.7 physical acceptance criteria."""

import json
from pathlib import Path

import numpy as np


def audit(report):
    evidence = {}
    for name in ("sequence", "reverse"):
        entry = report[name]
        split, _, released, final = entry["cpu"]
        profile = split["measurement"]["profile"]
        depletion = profile[len(profile) // 2] / max(profile)
        phase = released["measurement"]["mirror_phase"]
        assert depletion < 0.01
        assert abs(phase - (-0.6 if name == "sequence" else 0.6)) < 0.03
        max_phase = 0
        for cpu, gpu in zip(entry["cpu"], entry["gpu"]):
            difference = abs(
                np.angle(
                    np.exp(
                        1j
                        * (gpu["measurement"]["mirror_phase"] - cpu["measurement"]["mirror_phase"])
                    )
                )
            )
            max_phase = max(max_phase, float(difference))
            assert difference < 0.002
            assert abs(gpu["diagnostics"]["norm"] - 1) < 0.001
        evidence[name] = {
            "split_center_to_peak": depletion,
            "release_phase": phase,
            "max_gpu_phase_difference_rad": max_phase,
        }
        assert final["measurement"]["fringes"]["spacing"] is not None
    assert (
        abs(
            report["sequence"]["cpu"][2]["measurement"]["mirror_phase"]
            + report["reverse"]["cpu"][2]["measurement"]["mirror_phase"]
        )
        < 1e-8
    )
    zero = report["pair_zero"]["gpu"][0]["measurement"]["profile"]
    opposite = report["pair_pi"]["gpu"][0]["measurement"]["profile"]
    mid = len(zero) // 2
    assert zero[mid] > 0.9 * max(zero)
    assert opposite[mid] / max(opposite) < 1e-8
    shifted = report["pair_shift"]["gpu"][0]["measurement"]["profile"]
    # A positive input phase moves the central density maximum to positive x.
    assert shifted[mid + 1] > shifted[mid - 1]
    evidence["pi_center_to_peak"] = opposite[mid] / max(opposite)
    reference = report["sequence"]["cpu"][-1]["measurement"]
    for name in ("half_dt", "finer_grid", "larger_box", "half_preparation"):
        result = report[name]["cpu"][-1]["measurement"]
        phase_error = abs(
            np.angle(np.exp(1j * (result["mirror_phase"] - reference["mirror_phase"])))
        )
        spacing_change = result["fringes"]["spacing"] / reference["fringes"]["spacing"] - 1
        contrast_change = result["fringes"]["contrast"] - reference["fringes"]["contrast"]
        assert phase_error < 0.01, (name, phase_error)
        assert abs(spacing_change) < 0.02, (name, spacing_change)
        assert abs(contrast_change) < 0.04, (name, contrast_change)
        evidence[name] = {
            "phase_change_rad": float(phase_error),
            "relative_spacing_change": spacing_change,
            "contrast_change": contrast_change,
            "relative_width_change": report[name]["relative_width_change"],
        }
    return evidence


def main():
    out = Path("artifacts/interferometer")
    evidence = audit(json.loads((out / "validation.json").read_text()))
    (out / "audit.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
