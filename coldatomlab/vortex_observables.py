"""Model-density 1/e core radius for comparison with the paper's radial density.

Azimuthally averaged z-column density, cubic interpolation on 32 angles.
Interpolation does not add physical resolution: refine the underlying grid.
"""

import math

import numpy as np


def cubic_weight(d):
    d = abs(d)
    return np.where(
        d <= 1,
        1.5 * d**3 - 2.5 * d**2 + 1,
        np.where(d < 2, -0.5 * d**3 + 2.5 * d**2 - 4 * d + 2, 0),
    )


def core_from_field(field, dx):
    n = field.shape[0]
    column = np.sum(abs(field) ** 2, axis=2) * dx
    radius = np.arange(2 * n - 7) * dx / 4
    theta = np.arange(32) * 2 * np.pi / 32
    xx = n / 2 + radius[:, None] / dx * np.cos(theta)
    yy = n / 2 + radius[:, None] / dx * np.sin(theta)
    i = np.floor(xx).astype(int)
    j = np.floor(yy).astype(int)
    values = np.zeros_like(xx)
    for a in [-1, 0, 1, 2]:
        for b in [-1, 0, 1, 2]:
            values += (
                column[np.clip(i + a, 0, n - 1), np.clip(j + b, 0, n - 1)]
                * cubic_weight(xx - i - a)
                * cubic_weight(yy - j - b)
            )
    profile = np.maximum(values, 0).mean(axis=1)
    peak = int(np.argmax(profile))
    threshold = profile[peak] / math.e
    density = abs(field) ** 2
    x = (np.arange(n) - n / 2) * dx
    rms = math.sqrt(
        float(np.sum(density * (x[:, None, None] ** 2 + x[None, :, None] ** 2)) / density.sum())
    )
    if peak < 2 or profile[0] >= threshold:
        return dict(core_radius=None, radial_rms=rms, core_ratio=None)
    high = int(np.flatnonzero(profile[: peak + 1] >= threshold)[0])
    core = float(np.interp(threshold, profile[high - 1 : high + 1], radius[high - 1 : high + 1]))
    return dict(core_radius=core, radial_rms=rms, core_ratio=core / rms)
