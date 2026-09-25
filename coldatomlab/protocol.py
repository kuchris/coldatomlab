"""Deterministic split/hold/release timing and conservative profile diagnostics."""

import numpy as np


class SplitProtocol:
    def __init__(self, config, trap, x):
        self.config = config
        self.trap = trap
        self.barrier = np.exp(-0.5 * (x / config.barrier_width) ** 2)
        self.tilt = 0.5 * np.tanh(x / config.barrier_width)
        self.split_end = max(1, round(config.split_time / config.dt))
        self.release_at = self.split_end + round(config.hold_time / config.dt)
        self.end = self.release_at + max(1, round(config.expansion_time / config.dt))

    def stage(self, step):
        if step >= self.end:
            return "complete"
        if step >= self.release_at:
            return "expand"
        if step >= self.split_end:
            return "hold"
        return "split"

    def settings(self, step):
        stage = self.stage(step)
        if stage == "split":
            u = step / self.split_end
            return self.config.barrier_height * u * u * (3 - 2 * u), 0.0
        if stage == "hold":
            return self.config.barrier_height, self.config.bias
        return 0.0, 0.0

    def potential(self, step):
        height, bias = self.settings(step)
        if step >= self.release_at:
            return np.zeros_like(self.trap)
        return self.trap + height * self.barrier + bias * self.tilt

    def summary(self, step):
        height, bias = self.settings(step)
        dt = self.config.dt
        return {
            "stage": self.stage(step),
            "complete": step >= self.end,
            "split_end": self.split_end * dt,
            "release_time": self.release_at * dt,
            "end_time": self.end * dt,
            "barrier_height": height,
            "bias": bias,
        }


def fringe_metrics(x, profile):
    """Resolve a periodic pattern only when >=3 prominent, regularly spaced peaks exist.

    This estimates local profile modulation, not quantum coherence or camera visibility.
    """
    x, p = np.asarray(x), np.asarray(profile)
    peaks = np.where((p[1:-1] > p[:-2]) & (p[1:-1] >= p[2:]))[0] + 1
    peaks = peaks[p[peaks] > 0.08 * p.max()]
    empty = {"fringe_spacing": None, "fringe_contrast": None}
    if len(peaks) < 3:
        return empty
    # Require at least four grid cells per period and regular peak spacing.
    distances = np.diff(x[peaks])
    if distances.min() < 4 * (x[1] - x[0]) or np.std(distances) / np.mean(distances) > 0.3:
        return empty
    contrasts = []
    for a, b in zip(peaks[:-1], peaks[1:]):
        high = 0.5 * (p[a] + p[b])
        low = p[a : b + 1].min()
        contrasts.append((high - low) / (high + low))
    if min(contrasts) < 0.1:
        return empty
    return {
        "fringe_spacing": float(np.median(distances)),
        "fringe_contrast": float(np.median(contrasts)),
    }
