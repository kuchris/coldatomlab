"""Render the measured 3D TF comparison as a standalone scientific figure."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from coldatomlab.solver3d import Config3D, tf_reference


def main():
    report = json.loads(Path("artifacts/3d-validation.json").read_text())
    case = next(c for c in report["cases"] if c["name"] == "tf")
    c = Config3D(**case["config"])
    t = np.array([d["time"] for d in case["history"]])
    numerical = np.array([d["widths"] for d in case["history"]])
    ref = np.array(tf_reference(c, t)["widths"])
    ms = t * c.scales["time_ms"]
    a = c.scales["length_um"]
    colors = ["#356fbd", "#118c82", "#b77921"]
    fig, axs = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    for i, axis in enumerate("xyz"):
        axs[0, 0].plot(ms, numerical[:, i] * a, color=colors[i], label=axis + " GPE")
        axs[0, 0].plot(ms, ref[:, i] * a, "--", color=colors[i], label=axis + " TF")
        axs[1, 0].plot(ms, 100 * (numerical[:, i] / ref[:, i] - 1), color=colors[i], label=axis)
    for i in (0, 1):
        axs[0, 1].plot(
            ms, numerical[:, i] / numerical[:, 2], color=colors[i], label="xy"[i] + "/z GPE"
        )
        axs[0, 1].plot(ms, ref[:, i] / ref[:, 2], "--", color=colors[i], label="xy"[i] + "/z TF")
    axs[0, 1].axhline(1, color="gray", lw=0.8)
    axs[0, 0].set(ylabel="RMS width (µm)", title="All three widths")
    axs[0, 1].set(ylabel="Aspect ratio", title="Shape inversion on release")
    axs[1, 0].set(
        ylabel="(GPE / absolute TF − 1) × 100 (%)",
        title="Finite-interaction difference from theory",
    )
    changes = report["refinement_relative_changes"]
    names = ["tf_half_dt", "tf_fine_grid", "tf_large_box"]
    axs[1, 1].bar(
        ["Half dt", "Finer grid", "Larger box"],
        [100 * max(abs(np.array(changes[n]))) for n in names],
        color="#356fbd",
    )
    axs[1, 1].set(
        ylabel="Largest width / aspect change (%)", title="Numerical refinement at 15.915 ms"
    )
    for ax in [axs[0, 0], axs[0, 1], axs[1, 0]]:
        ax.set_xlabel("Time after release (ms)")
        ax.legend(fontsize=8, ncol=2)
        ax.grid(alpha=0.18)
    fig.suptitle(
        "3D Rb-87 expansion: numerical field and Castin–Dum TF approximation\nN = 150,000; trap = (30, 42, 21) Hz; 96³ baseline; no experimental data",
        fontsize=13,
    )
    fig.savefig("artifacts/3d-tf-validation.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
