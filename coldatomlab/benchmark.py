"""Reduced ballistic comparison with Shin et al., PRL 92, 050405, Fig. 2.

This is a normalized separable free-particle model, not a simulation of their
interacting 3D preparation or sodium absorption camera. See docs/SHIN_REFERENCE.md.
"""

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from .physical import AMU, HBAR, H

MASS_U = 22.9897692820  # NIST Na-23 atomic mass; see source URL in report.
MASS = MASS_U * AMU
SEPARATION_UM = 13.0
TIME_MS = 30.0
RADIAL_HZ = 615.0
PAPER_MEASURED_UM = 41.5
PAPER_THEORY_UM = 39.8
WIDTH_UM = math.sqrt(HBAR / (2 * MASS * 2 * math.pi * RADIAL_HZ)) * 1e6


def propagate(n=4096, length_um=1200.0, width_um=WIDTH_UM, parts=1):
    """Norm-one x wavefunction; lengths in um and density in probability/um.

    An initially separable transverse factor integrates to one under free
    evolution, so this computes its marginal x profile without a 3D grid.
    """
    if n < 64 or n % 2 or length_um <= 0 or width_um <= 0 or parts < 1:
        raise ValueError("Use an even grid >=64 and positive lengths/step count.")
    dx = length_um / n
    x = (np.arange(n) - n // 2) * dx
    initial = sum(
        np.exp(-((x - center) ** 2) / (4 * width_um**2))
        for center in (-SEPARATION_UM / 2, SEPARATION_UM / 2)
    ).astype(complex)
    normalization = math.sqrt(float(np.sum(abs(initial) ** 2) * dx))
    initial /= normalization
    k = 2 * np.pi * np.fft.fftfreq(n, d=dx * 1e-6)
    step = np.exp(-0.5j * HBAR * k**2 * (TIME_MS * 1e-3 / parts) / MASS)
    psi = initial.copy()
    for _ in range(parts):
        psi = np.fft.ifft(np.fft.fft(psi) * step)
    q = 1 + 1j * HBAR * TIME_MS * 1e-3 / (2 * MASS * (width_um * 1e-6) ** 2)
    analytic = (
        sum(
            np.exp(-((x - center) ** 2) / (4 * width_um**2 * q)) / np.sqrt(q)
            for center in (-SEPARATION_UM / 2, SEPARATION_UM / 2)
        )
        / normalization
    )
    return x, psi, analytic


def fringe_fit(x, density):
    """Fit A exp(-(x-xc)^2/(2s^2)) [1+B cos(2pi*x/lambda+phase)].

    Only the supplied profile determines the initialization and fit. Neither
    the paper's measured period nor its analytical prediction enters the fit.
    """
    x, density = np.asarray(x, dtype=float), np.asarray(density, dtype=float)
    if (
        x.ndim != 1
        or density.shape != x.shape
        or len(x) < 64
        or not np.isfinite(x).all()
        or not np.isfinite(density).all()
        or np.any(density < 0)
        or density.max() <= 0
        or np.any(np.diff(x) <= 0)
    ):
        raise ValueError("Fit needs a positive, finite resolved line density.")
    y = density / density.max()
    peaks, _ = find_peaks(y, prominence=0.08, distance=4)
    if len(peaks) < 3:
        raise ValueError("At least three resolved fringes are required.")
    spacing = float(np.median(np.diff(x[peaks])))
    mean = float(np.sum(x * y) / np.sum(y))
    sigma = float(np.sqrt(np.sum((x - mean) ** 2 * y) / np.sum(y)))

    def model(p):
        a, xc, s, contrast, period, phase = p
        return (
            a
            * np.exp(-0.5 * ((x - xc) / s) ** 2)
            * (1 + contrast * np.cos(2 * np.pi * x / period + phase))
        )

    # The brightest peak provides a phase seed without consulting source phase.
    phase = float(
        (-2 * np.pi * x[peaks[np.argmax(y[peaks])]] / spacing + np.pi) % (2 * np.pi) - np.pi
    )
    dx = float(np.median(np.diff(x)))
    span = float(np.ptp(x))
    result = least_squares(
        lambda p: model(p) - y,
        [0.5, mean, sigma, 0.8, spacing, phase],
        bounds=([0, x[0], dx, 0, 4 * dx, -4 * np.pi], [2, x[-1], 2 * span, 1, span / 2, 4 * np.pi]),
        x_scale="jac",
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=1000,
    )
    if not result.success:
        raise ValueError("Fringe fit did not converge.")
    return {
        "period_um": float(result.x[4]),
        "contrast": float(result.x[3]),
        "envelope_sigma_um": float(result.x[2]),
        "center_um": float(result.x[1]),
        "phase_rad": float(result.x[5]),
        "relative_profile_l2_residual": float(
            np.linalg.norm(model(result.x) - y) / np.linalg.norm(y)
        ),
    }, model(result.x) * density.max()


def run_case(n=4096, length_um=1200.0, width_um=WIDTH_UM, parts=1):
    x, psi, analytic = propagate(n, length_um, width_um, parts)
    dx = length_um / n
    density = abs(psi) ** 2
    # Fixed physical fitting aperture, independent of the experimental period.
    selection = abs(x) <= 200
    fit, fitted = fringe_fit(x[selection], density[selection])
    point = H * TIME_MS * 1e-3 / (MASS * SEPARATION_UM * 1e-6) * 1e6
    tau = HBAR * TIME_MS * 1e-3 / (2 * MASS * (width_um * 1e-6) ** 2)
    return {
        "n": n,
        "length_um": length_um,
        "dx_um": dx,
        "width_um": width_um,
        "propagation_parts": parts,
        "norm": float(density.sum() * dx),
        "edge_probability": float(density[abs(x) > 0.45 * length_um].sum() * dx),
        "analytic_wavefunction_l2_error": float(np.linalg.norm(psi - analytic) * math.sqrt(dx)),
        "point_source_period_um": point,
        "finite_gaussian_period_um": point * (1 + 1 / tau**2),
        "fit": fit,
        "x_um": x[selection].tolist(),
        "density_per_um": density[selection].tolist(),
        "fitted_density_per_um": fitted.tolist(),
    }


@lru_cache(maxsize=1)
def report():
    base = run_case()
    checks = {}
    for name, kwargs in {
        "finer_grid": {"n": 8192},
        "larger_domain": {"n": 8192, "length_um": 2400.0},
        "two_half_steps": {"parts": 2},
        "half_packet_width": {"n": 16384, "length_um": 2400.0, "width_um": WIDTH_UM / 2},
        "double_packet_width": {"width_um": 2 * WIDTH_UM},
    }.items():
        case = run_case(**kwargs)
        checks[name] = {
            k: v
            for k, v in case.items()
            if k not in ("x_um", "density_per_um", "fitted_density_per_um")
        }
        checks[name]["period_change_um"] = case["fit"]["period_um"] - base["fit"]["period_um"]
    measured = PAPER_MEASURED_UM
    comparison = []
    for label, value in (
        ("Numerical wavepacket fit", base["fit"]["period_um"]),
        ("Exact finite-width Gaussian phase period", base["finite_gaussian_period_um"]),
        ("Point-source formula, rounded inputs", base["point_source_period_um"]),
        ("Paper's quoted point-source prediction", PAPER_THEORY_UM),
        ("Published measured spacing", measured),
    ):
        comparison.append(
            {
                "label": label,
                "period_um": value,
                "difference_um": value - measured,
                "relative_difference_percent": 100 * (value - measured) / measured,
            }
        )
    return {
        "schema": "coldatomlab-shin-benchmark-v1",
        "scope": "Reduced ballistic fringe-spacing comparison; not full experimental reproduction",
        "sources": {
            "paper": "https://arxiv.org/abs/cond-mat/0306305v2",
            "figure": "Fig. 2 and Eq. (1), pages 2-3 of the arXiv PDF",
            "mass": "https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=Na",
        },
        "inputs": {
            "species": "Na-23",
            "mass_u": MASS_U,
            "mass_kg": MASS,
            "separation_um": SEPARATION_UM,
            "expansion_ms": TIME_MS,
            "radial_frequency_hz": RADIAL_HZ,
            "packet_rms_width_um": WIDTH_UM,
            "packet_width_origin": "Noninteracting harmonic-ground-state surrogate, not measured",
            "interaction": 0,
            "relative_phase_rad": 0,
            "normalization": "Integral of marginal probability density dx = 1; no atom count fit",
            "fit_aperture_um": [-200, 200],
        },
        "published": {
            "measured_period_um": measured,
            "quoted_theory_um": PAPER_THEORY_UM,
            "measurement_uncertainty_um": None,
            "raw_data_available_in_reference": False,
        },
        "base": base,
        "checks": checks,
        "comparison": comparison,
        "limitations": [
            "The experiment is interacting and three-dimensional; this benchmark propagates a separable noninteracting Gaussian pair.",
            "The paper uses Na-23; the existing Rb-87 camera and example images are not this experiment.",
            "The chosen initial width, zero relative phase and normalized amplitude are surrogate assumptions, not a reconstruction of Fig. 2.",
            "Only the reported scalar spacing is compared. No experimental profile, pixel data or uncertainty has been imported.",
            "The density-envelope fit residual is a numerical/model residual, not experimental error or a confidence interval.",
            "No parameters were tuned to 41.5 um. A small spacing discrepancy does not validate the full 3D dynamics or camera.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/shin-benchmark.json"))
    args = parser.parse_args()
    result = report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "comparison": result["comparison"],
                "analytic_error": result["base"]["analytic_wavefunction_l2_error"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
