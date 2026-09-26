"""Centered charge-sector imaginary-time preparation, independent float64 GPE."""

import math

import numpy as np
from scipy.fft import fftn, ifftn


def project(field, charge):
    """Project onto the C4 rotation sector; tends to axial q=±1 on refinement.

    Higher angular harmonics in the same discrete sector are not suppressed.
    Report the full GPE residual and refine, rather than assert exact symmetry.
    """
    neg = (-np.arange(field.shape[0])) % field.shape[0]
    rotated = field
    result = field.copy()
    for k in range(1, 4):
        rotated = rotated[neg, :, :].transpose(1, 0, 2)
        result += (-1j * charge) ** k * rotated
    return result / 4


def residual(sim, field):
    h = ifftn(0.5 * sim.k2 * fftn(field)) + (sim.trap + sim.config["g"] * abs(field) ** 2) * field
    norm = float(np.sum(abs(field) ** 2) * sim.dx**3)
    mu = float(np.vdot(field, h).real * sim.dx**3 / norm)
    error = float(np.linalg.norm(h - mu * field) * sim.dx**1.5 / (abs(mu) * math.sqrt(norm)))
    return mu, error


def prepare(sim, tau=0.002):
    c = sim.config
    lam = c["axial_hz"] / c["radial_hz"]
    field = (sim.X + 1j * c["charge"] * sim.Y) * np.exp(
        -0.5 * (sim.X**2 + sim.Y**2 + lam * sim.Z**2)
    )
    field /= np.sqrt(np.sum(abs(field) ** 2) * sim.dx**3)
    iterations, change = 0, 0.0
    if c["g"]:
        kinetic = np.exp(-0.5 * tau * sim.k2)
        mu_shift = 2 + lam / 2
        previous = field.copy()
        for iterations in range(1, 10001):
            v = sim.trap - mu_shift
            ex = np.exp(-tau * v)
            ratio = np.full_like(v, tau)
            np.divide(-np.expm1(-tau * v), v, out=ratio, where=abs(v) > 1e-12)
            field *= np.sqrt(ex / (1 + c["g"] * abs(field) ** 2 * ratio))
            field = ifftn(fftn(field) * kinetic)
            field *= np.sqrt(ex / (1 + c["g"] * abs(field) ** 2 * ratio))
            field = project(field, c["charge"])
            norm = math.sqrt(float(np.sum(abs(field) ** 2) * sim.dx**3))
            field /= norm  # Preparation only.
            mu_shift -= math.log(norm) / tau
            if iterations % 50 == 0:
                change = float(np.linalg.norm(field - previous) * sim.dx**1.5)
                if change < 2e-7:
                    break
                previous = field.copy()
        else:
            raise ValueError("Stationary vortex preparation did not converge.")
    mu, error = residual(sim, field)
    if not np.isfinite(error) or error > 5e-4:
        raise ValueError(
            f"Stationary vortex residual {error:.3g} exceeds 0.0005; refine the preparation."
        )
    return field, dict(
        kind="stationary centered C4 charge-sector vortex",
        iterations=iterations,
        dt=tau,
        iterate_l2_change=change,
        chemical_potential=mu,
        relative_stationary_residual=error,
    )
