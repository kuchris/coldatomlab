"""Driven 3D double well and state-derived interference diagnostics.

X, t, V use a0, omega0^-1, hbar*omega0. Relative phase is right minus left.
"""

import numpy as np


def stages(c):
    # Explicit half-up rounding, shared with JavaScript Math.round.
    split = int(c.split_time / c.dt + 0.5)
    hold = int(c.hold_time / c.dt + 0.5)
    expansion = int(c.duration / c.dt + 0.5)
    return split, split + hold, split + hold + expansion


def drive(c, step):
    if c.experiment != "sequence":
        return 0.0, 0.0
    split, release, _ = stages(c)
    if step < split:
        return c.barrier_height * np.sin(0.5 * np.pi * step / split) ** 2, 0.0
    if step < release:
        return c.barrier_height, c.hold_bias
    return 0.0, 0.0


def gaussian_pair(c, x, time=0):
    """Exact continuum free field, including initial packet overlap."""
    w = c.omegas
    q = 1 + 1j * w * time
    axes = [x[:, None, None], x[None, :, None], x[None, None, :]]
    prefactor = np.prod((w / np.pi) ** 0.25 / np.sqrt(q))
    packets = []
    for center in (-c.separation / 2, c.separation / 2):
        packets.append(
            prefactor
            * np.exp(
                -sum(
                    w[a] * (axes[a] - (center if a == 0 else 0)) ** 2 / (2 * q[a]) for a in range(3)
                )
            )
        )
    overlap = np.exp(-w[0] * c.separation**2 / 4)
    return (packets[0] + np.exp(1j * c.relative_phase) * packets[1]) / np.sqrt(
        2 * (1 + overlap * np.cos(c.relative_phase))
    )


def fringe_measurement(x, profile):
    """Local parabolic peaks; reject unresolved/unequally spaced structure."""
    peak = float(max(profile))
    peaks = []
    for i in range(1, len(x) - 1):
        if (
            profile[i] > profile[i - 1]
            and profile[i] >= profile[i + 1]
            and profile[i] > 0.15 * peak
        ):
            shift = (
                0.5
                * (profile[i - 1] - profile[i + 1])
                / (profile[i - 1] - 2 * profile[i] + profile[i + 1])
            )
            peaks.append((i, float(x[i] + shift * (x[1] - x[0]))))
    result = {"spacing": None, "contrast": None, "reason": "Need at least three resolved fringes."}
    if len(peaks) < 3:
        return result
    gaps = np.diff([p[1] for p in peaks])
    spacing = float(np.mean(gaps))
    if min(gaps) < 4 * (x[1] - x[0]) or np.std(gaps) / spacing > 0.15:
        result["reason"] = "Fringes are undersampled or spacing is nonuniform."
        return result
    contrasts = []

    def vertex_height(i):
        curvature = profile[i - 1] - 2 * profile[i] + profile[i + 1]
        shift = 0.5 * (profile[i - 1] - profile[i + 1]) / curvature if curvature else 0
        return max(0.0, float(profile[i] - 0.25 * (profile[i - 1] - profile[i + 1]) * shift))

    for (left, _), (right, _) in zip(peaks[:-1], peaks[1:]):
        high = min(vertex_height(left), vertex_height(right))
        valley = left + int(np.argmin(profile[left : right + 1]))
        low = vertex_height(valley)
        contrasts.append(float((high - low) / (high + low)))
    return {
        "spacing": spacing,
        "contrast": float(np.mean(contrasts)),
        "reason": "Resolved local peaks; envelope-sensitive estimate.",
    }


def measurements(c, x, psi, step, released):
    dx = c.length / c.n
    profile = np.sum(abs(psi) ** 2, axis=(1, 2)) * dx**2
    norm = float(sum(profile) * dx)
    mid = c.n // 2
    left = float((sum(profile[:mid]) + profile[mid] / 2) * dx / norm)
    # x=0 is shared; unmatched x=-L/2 is excluded from the mirror diagnostic.
    right_field, left_field = psi[mid + 1 :], psi[1:mid][::-1]
    cross = np.vdot(left_field, right_field) * dx**3
    denom = np.linalg.norm(left_field.ravel()) * np.linalg.norm(right_field.ravel()) * dx**3
    coherence = float(abs(cross) / denom) if denom > 1e-12 else 0.0
    phase = float(np.angle(cross)) if coherence > 0.2 and min(left, 1 - left) > 0.05 else None
    height, bias = drive(c, step)
    potential = (
        np.zeros_like(x)
        if released
        else 0.5 * (c.omegas[0] * x) ** 2
        + height * np.exp(-0.5 * (x / c.barrier_width) ** 2)
        + 0.5 * bias * np.tanh(x / c.barrier_width)
    )
    split, release, end = stages(c)
    stage = (
        (
            "Complete"
            if step >= end
            else "Split"
            if step < split
            else "Hold"
            if step < release
            else "Expansion"
        )
        if c.experiment == "sequence"
        else ("Expansion" if released else "Trapped")
    )
    return {
        "profile": profile.tolist(),
        "potential": potential.tolist(),
        "left_fraction": left,
        "right_fraction": 1 - left,
        "mirror_phase": phase,
        "mirror_coherence": coherence,
        "fringes": fringe_measurement(x, profile),
        "stage": stage,
        "stage_steps": [split, release, end] if c.experiment == "sequence" else None,
        "barrier_height": float(height),
        "hold_bias": float(bias),
    }
