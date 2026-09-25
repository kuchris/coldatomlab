"""Render the exported benchmark using standard scientific plotting tools."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/shin-benchmark.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/shin-benchmark.png"))
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    b = data["base"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    ax.plot(b["x_um"], b["density_per_um"], color="#2166ce", lw=1.7, label="Numerical density")
    ax.plot(
        b["x_um"],
        b["fitted_density_per_um"],
        color="#a16617",
        ls="--",
        lw=1.4,
        label="Fitted density",
    )
    ax.set(
        xlabel="Position x (µm)",
        ylabel="Marginal probability density (1/µm)",
        title="Reduced free-wavepacket model · Na-23",
        xlim=(-200, 200),
    )
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.15)
    ax = axes[1]
    labels = [
        "Numerical fit",
        "Finite Gaussian",
        "Rounded-input formula",
        "Paper's quoted theory",
        "Published measurement",
    ]
    colors = ["#2166ce", "#177687", "#637083", "#916013", "#20252c"]
    for i, (row, color) in enumerate(zip(data["comparison"], colors)):
        value = row["period_um"]
        ax.scatter(value, 4 - i, color=color, marker="D" if i == 4 else "o", s=40)
        ax.annotate(
            f"{value:.4f}", (value, 4 - i), xytext=(5, 9), textcoords="offset points", fontsize=9
        )
    ax.axvline(41.5, color="#20252c", alpha=0.2, ls="--")
    ax.set(
        yticks=range(5),
        yticklabels=labels[::-1],
        xlabel="Fringe spacing (µm)",
        title="One observable compared with Shin et al.",
        ylim=(-0.7, 4.7),
        xlim=(39.4, 42.2),
    )
    ax.grid(axis="x", alpha=0.15)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Shin et al., PRL 92, 050405 (2004), Fig. 2 · Reduced ballistic benchmark", fontsize=13
    )
    fig.text(
        0.05,
        0.035,
        "d = 13 µm; t = 30 ms. Initial width is a declared noninteracting surrogate; no fitting to the published spacing.\n"
        "No experimental profile or period uncertainty supplied. Differences do not establish experimental agreement.",
        fontsize=9,
        color="#536073",
    )
    fig.tight_layout(rect=(0.01, 0.13, 0.99, 0.93), w_pad=3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
