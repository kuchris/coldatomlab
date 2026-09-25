"""Effective 2D GPE with norm-one wavefunctions and periodic spectral derivatives."""

import math
from dataclasses import asdict, dataclass

import numpy as np

from . import __version__
from .protocol import SplitProtocol, fringe_metrics


@dataclass(frozen=True)
class Config:
    experiment: str = "single"
    n: int = 128
    length: float = 32.0
    dt: float = 0.005
    interaction: float = 20.0
    omega_x: float = 1.0
    omega_y: float = 1.4
    separation: float = 6.0
    phase: float = 0.0
    barrier_height: float = 12.0
    barrier_width: float = 0.7
    split_time: float = 4.0
    hold_time: float = 2.0
    expansion_time: float = 3.0
    bias: float = 0.5

    def __post_init__(self):
        if self.experiment not in ("single", "double", "sequence"):
            raise ValueError("Choose a single-cloud, two-cloud, or split/hold/release experiment.")
        if type(self.n) is not int or self.n not in (64, 128, 256):
            raise ValueError("Grid size must be 64, 128, or 256.")
        for name, low, high in (
            ("length", 24, 64),
            ("dt", 0.001, 0.02),
            ("interaction", 0, 100),
            ("omega_x", 0.5, 2),
            ("omega_y", 0.5, 2),
            ("separation", 2, 12),
            ("phase", -math.pi, math.pi),
            ("barrier_height", 0, 30),
            ("barrier_width", 0.5, 1.5),
            ("split_time", 0.1, 8),
            ("hold_time", 0, 6),
            ("expansion_time", 0.1, 8),
            ("bias", -3, 3),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number.")
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be between {low:g} and {high:g}.")
        if self.length / self.n > 0.5:
            raise ValueError("Use a finer grid for this domain (spacing must be at most 0.5).")
        if self.experiment == "sequence":
            if self.split_time + self.hold_time + self.expansion_time > 18:
                raise ValueError("Sequence duration must not exceed 18 time units.")
            if self.barrier_width < 2 * self.length / self.n:
                raise ValueError("Resolve the barrier with a finer grid or a wider barrier.")


class Solver:
    def __init__(self, config: Config):
        self.config = config
        self.dx = config.length / config.n
        self.x = np.arange(config.n) * self.dx - config.length / 2
        self.X, self.Y = np.meshgrid(self.x, self.x)
        k = 2 * np.pi * np.fft.fftfreq(config.n, d=self.dx)
        self.k2 = k[:, None] ** 2 + k[None, :] ** 2
        self.trap = 0.5 * ((config.omega_x * self.X) ** 2 + (config.omega_y * self.Y) ** 2)
        self.kinetic_step = np.exp(-0.5j * config.dt * self.k2)
        self.potential = self.trap.copy()
        self.protocol = (
            SplitProtocol(config, self.trap, self.X) if config.experiment == "sequence" else None
        )
        self.preparation = {"kind": "analytic coherent Gaussian pair", "iterations": 0}
        if config.experiment != "double":
            self.psi = self.gaussian().astype(complex)
            self.normalize()
            self.prepare_ground_state()
        else:
            half = config.separation / 2
            self.psi = (
                self.gaussian(-half) + np.exp(1j * config.phase) * self.gaussian(half)
            ).astype(complex)
            self.normalize()
        self.initial = self.psi.copy()
        self.reset()

    def gaussian(self, center=0.0):
        c = self.config
        return np.exp(-0.5 * (c.omega_x * (self.X - center) ** 2 + c.omega_y * self.Y**2))

    def normalize(self):
        self.psi /= np.sqrt(np.sum(np.abs(self.psi) ** 2) * self.dx**2)

    def prepare_ground_state(self):
        # Fixed, small imaginary step; normalization belongs only to preparation.
        tau = 0.002
        kinetic = np.exp(-0.5 * tau * self.k2)
        previous = self.psi.copy()
        residual = float("inf")
        for iteration in range(1, 6001):
            self.psi *= np.exp(
                -tau / 2 * (self.trap + self.config.interaction * np.abs(self.psi) ** 2)
            )
            self.psi = np.fft.ifft2(np.fft.fft2(self.psi) * kinetic)
            self.psi *= np.exp(
                -tau / 2 * (self.trap + self.config.interaction * np.abs(self.psi) ** 2)
            )
            self.normalize()
            if iteration % 100 == 0:
                residual = float(np.linalg.norm(self.psi - previous) * self.dx)
                if residual < 2e-8:
                    break
                previous = self.psi.copy()
        if residual >= 2e-8:
            raise ValueError("Ground-state preparation did not converge. Try stronger confinement.")
        self.preparation = {
            "kind": "normalized imaginary-time ground state",
            "iterations": iteration,
            "dt": tau,
            "iterate_l2_change": residual,
        }

    def reset(self):
        self.psi = self.initial.copy()
        self.steps = 0
        self.release_step = 0 if self.config.experiment == "double" else None
        self.potential = np.zeros_like(self.trap) if self.released else self.trap.copy()
        self.warning = ""
        self.complete = False
        self.history = []
        self.record()

    @property
    def released(self):
        return self.release_step is not None

    @property
    def time(self):
        return self.steps * self.config.dt

    def release(self):
        if self.protocol:
            raise ValueError("The sequence releases the trap automatically after Hold.")
        if not self.released:
            self.release_step = self.steps
            self.potential = np.zeros_like(self.trap)
            self.record()  # Preserve both sides of the potential-energy jump.

    def advance(self, count=10):
        if type(count) is not int or not 1 <= count <= 100:
            raise ValueError("Step count must be an integer between 1 and 100.")
        if self.warning or self.complete:
            return
        c = self.config
        for _ in range(count):
            if self.protocol:
                # Midpoint evaluation maintains second-order time integration within stages.
                self.potential = self.protocol.potential(self.steps + 0.5)
            self.psi *= np.exp(
                -0.5j * c.dt * (self.potential + c.interaction * np.abs(self.psi) ** 2)
            )
            self.psi = np.fft.ifft2(np.fft.fft2(self.psi) * self.kinetic_step)
            self.psi *= np.exp(
                -0.5j * c.dt * (self.potential + c.interaction * np.abs(self.psi) ** 2)
            )
            self.steps += 1
            if self.protocol:
                if self.steps in (self.protocol.split_end, self.protocol.release_at):
                    # Preserve both sides of externally imposed potential jumps.
                    self.potential = self.protocol.potential(self.steps - 1e-9)
                    self.record()
                if self.steps >= self.protocol.release_at:
                    self.release_step = self.protocol.release_at
                self.potential = self.protocol.potential(self.steps)
                if self.steps >= self.protocol.end:
                    self.complete = True
            if self.edge_mass() > 0.001:
                self.warning = "Cloud reached the boundary region. Reset with a larger domain."
                break
            if self.time >= 20:
                self.warning = "Reached the experiment time limit (20). Reset to start another run."
                break
            if self.complete:
                break
        self.record()

    def edge_mass(self):
        edge = max(2, self.config.n // 16)
        rho = np.abs(self.psi) ** 2
        return float(
            (
                rho[:edge].sum()
                + rho[-edge:].sum()
                + rho[edge:-edge, :edge].sum()
                + rho[edge:-edge, -edge:].sum()
            )
            * self.dx**2
        )

    def diagnostics(self):
        rho = np.abs(self.psi) ** 2
        norm = float(rho.sum() * self.dx**2)
        mean_x = float((rho * self.X).sum() * self.dx**2 / norm)
        mean_y = float((rho * self.Y).sum() * self.dx**2 / norm)
        kinetic = float(
            (self.k2 * np.abs(np.fft.fft2(self.psi)) ** 2).sum()
            * self.dx**2
            / (2 * self.config.n**2)
        )
        potential = float((rho * self.potential).sum() * self.dx**2)
        interaction = float(0.5 * self.config.interaction * (rho**2).sum() * self.dx**2)
        mid = self.config.n // 2
        center = rho[:, mid].sum() * 0.5
        left_fraction = float((rho[:, :mid].sum() + center) * self.dx**2 / norm)
        left = self.psi[:, mid - 1 : 0 : -1]
        right = self.psi[:, mid + 1 :]
        overlap = np.vdot(left, right)
        denominator = np.linalg.norm(left) * np.linalg.norm(right)
        similarity = float(abs(overlap) / denominator) if denominator > 1e-15 else 0.0
        return {
            "time": self.time,
            "steps": self.steps,
            "norm": norm,
            "width_x": float(np.sqrt((rho * (self.X - mean_x) ** 2).sum() * self.dx**2 / norm)),
            "width_y": float(np.sqrt((rho * (self.Y - mean_y) ** 2).sum() * self.dx**2 / norm)),
            "energy": kinetic + potential + interaction,
            "edge_mass": self.edge_mass(),
            "released": self.released,
            "left_fraction": left_fraction,
            "right_fraction": 1 - left_fraction,
            "relative_phase": float(np.angle(overlap)) if similarity > 0.1 else None,
            "mirror_similarity": similarity,
            **(
                fringe_metrics(self.x, rho[mid])
                if self.released
                else {"fringe_spacing": None, "fringe_contrast": None}
            ),
        }

    def record(self):
        self.history.append(self.diagnostics())

    def snapshot(self):
        rho = np.abs(self.psi) ** 2
        phase = np.angle(self.psi)
        # JSON null marks low-density pixels; zero is a valid phase.
        phase_view = np.where(rho >= rho.max() * 1e-3, phase, None)
        return {
            "config": asdict(self.config),
            "diagnostics": self.history[-1],
            "preparation": self.preparation,
            "warning": self.warning,
            "x": self.x.tolist(),
            "density": rho.tolist(),
            "phase": phase_view.tolist(),
            "cross_section": rho[self.config.n // 2].tolist(),
            "initial_peak": float((np.abs(self.initial) ** 2).max()),
            "history": self.history,
            "release_step": self.release_step,
            "complete": self.complete,
            "protocol": self.protocol.summary(self.steps) if self.protocol else None,
            "potential": self.potential.tolist(),
            "potential_profile": self.potential[self.config.n // 2].tolist(),
        }

    def export(self):
        return {
            "schema": "coldatomlab-experiment-v1",
            "solver_version": __version__,
            "numpy_version": np.__version__,
            "config": asdict(self.config),
            "model": "i dpsi/dt = [-laplacian/2 + V + g|psi|^2]psi; integral |psi|^2 = 1",
            "units": {
                "length": "a0",
                "time": "1/omega0",
                "energy": "hbar*omega0",
                "density": "1/a0^2",
                "a0": "sqrt(hbar/(m*omega0))",
            },
            "steps": self.steps,
            "release_step": self.release_step,
            "preparation": self.preparation,
            "history": self.history,
            "x": self.x.tolist(),
            "psi_real": self.psi.real.tolist(),
            "psi_imag": self.psi.imag.tolist(),
            "warning": self.warning,
            "protocol": self.protocol.summary(self.steps) if self.protocol else None,
        }


def replay(data):
    """Recreate initial state and protocol from an exported experiment."""
    if data.get("schema") != "coldatomlab-experiment-v1":
        raise ValueError("Unsupported experiment format.")
    sim = Solver(Config(**data["config"]))
    target = data["steps"]
    release = data["release_step"]
    if type(target) is not int or not 0 <= target <= math.ceil(20 / sim.config.dt):
        raise ValueError("Invalid replay step count.")
    if release is not None and (type(release) is not int or not 0 <= release <= target):
        raise ValueError("Invalid release step.")
    if sim.protocol:
        expected_release = sim.protocol.release_at if target >= sim.protocol.release_at else None
        if target > sim.protocol.end or release != expected_release:
            raise ValueError("Saved release or end step disagrees with the configured sequence.")
        while sim.steps < target:
            sim.advance(min(100, target - sim.steps))
            if sim.warning and sim.steps < target:
                raise ValueError("Replay reached a boundary before the saved step.")
        return sim
    while sim.steps < target:
        if release is not None and sim.steps == release:
            sim.release()
        stop = release if release is not None and sim.steps < release else target
        sim.advance(min(100, stop - sim.steps))
        if sim.warning and sim.steps < target:
            raise ValueError("Replay encountered a boundary or time limit before the saved step.")
    if release == target:
        sim.release()
    return sim
