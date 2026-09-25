"""Norm-one 3D GPE; Cartesian arrays are ordered x, y, z. See docs/MODEL3D.md."""

import math
import time
from dataclasses import asdict, dataclass

import numpy as np
from scipy.fft import fftn, ifftn, irfftn, rfftn
from scipy.integrate import solve_ivp

from . import __version__
from .interferometry3d import drive, gaussian_pair, measurements, stages
from .physical import HBAR, RB87_MASS


@dataclass(frozen=True)
class Config3D:
    n: int = 64
    length: float = 24.0
    dt: float = 0.004
    atoms: int = 20000
    scattering_nm: float = 5.3
    reference_hz: float = 30.0
    fx_hz: float = 30.0
    fy_hz: float = 42.0
    fz_hz: float = 21.0
    duration: float = 2.0
    preparation_dt: float = 0.002
    experiment: str = "single"
    separation: float = 6.0
    relative_phase: float = 0.0
    barrier_height: float = 12.0
    barrier_width: float = 0.8
    split_time: float = 3.0
    hold_time: float = 0.6
    hold_bias: float = 1.0

    def __post_init__(self):
        if self.experiment not in ("single", "pair", "sequence"):
            raise ValueError("Unknown 3D experiment.")
        if self.experiment == "pair" and self.scattering_nm != 0:
            raise ValueError("The analytic coherent pair requires zero scattering length.")
        if type(self.n) is not int or self.n not in (32, 48, 64, 96, 128):
            raise ValueError("3D grid must be 32, 48, 64, 96 or 128.")
        if type(self.atoms) is not int or not 10 <= self.atoms <= 300000:
            raise ValueError("Atom number must be an integer from 10 to 300000.")
        for name, low, high in (
            ("length", 16, 64),
            ("dt", 0.0005, 0.01),
            ("scattering_nm", 0, 10),
            ("reference_hz", 10, 100),
            ("fx_hz", 5, 200),
            ("fy_hz", 5, 200),
            ("fz_hz", 5, 200),
            ("duration", 0.1, 4),
            ("preparation_dt", 0.0005, 0.004),
            ("separation", 2, 10),
            ("relative_phase", -math.pi, math.pi),
            ("barrier_height", 0, 40),
            ("barrier_width", 0.5, 2),
            ("split_time", 0.1, 6),
            ("hold_time", 0, 3),
            ("hold_bias", -5, 5),
        ):
            v = getattr(self, name)
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or not low <= v <= high
            ):
                raise ValueError(f"{name} must be between {low:g} and {high:g}.")
        if self.length / self.n > 0.5:
            raise ValueError(
                "Resolve the cloud with grid spacing <= 0.5 a0; use a finer grid or smaller box."
            )
        if self.experiment == "sequence" and self.barrier_width < 2 * self.length / self.n:
            raise ValueError("Resolve the barrier with at least two grid cells per width.")
        if any(not 0.5 <= w <= 2 for w in self.omegas):
            raise ValueError(
                "Each trap frequency must be between 0.5 and 2 times the reference frequency."
            )
        if self.scales["interaction"] > 8000:
            raise ValueError(
                "Derived 3D interaction exceeds 8000; reduce atoms or scattering length."
            )

    @property
    def omegas(self):
        return np.array([self.fx_hz, self.fy_hz, self.fz_hz]) / self.reference_hz

    @property
    def scales(self):
        a0 = math.sqrt(HBAR / (RB87_MASS * 2 * math.pi * self.reference_hz))
        return {
            "length_um": a0 * 1e6,
            "time_ms": 1000 / (2 * math.pi * self.reference_hz),
            "energy_hz": self.reference_hz,
            "interaction": 4 * math.pi * self.atoms * self.scattering_nm * 1e-9 / a0,
            "mass_kg": RB87_MASS,
        }


def tf_reference(config, times):
    """Thomas-Fermi scaling after full release; no finite-g fit to the solver."""
    g = config.scales["interaction"]
    if g == 0:
        return None
    w = config.omegas
    mu = 0.5 * (15 * g * np.prod(w) / (4 * np.pi)) ** (2 / 5)
    widths = np.sqrt(2 * mu) / w / math.sqrt(7)
    t = np.asarray(times, dtype=float)
    if len(t) == 0:
        return None
    if t.max() == 0:
        b = np.ones((len(t), 3))
        velocities = np.zeros_like(b)
    else:

        def rhs(_, y):
            return np.r_[y[3:], w**2 / (y[:3] * np.prod(y[:3]))]

        sol = solve_ivp(
            rhs,
            (0, float(t.max())),
            np.r_[np.ones(3), np.zeros(3)],
            rtol=1e-10,
            atol=1e-12,
            dense_output=True,
        )
        if not sol.success:
            raise ValueError("Thomas-Fermi reference integration failed.")
        b = sol.sol(t)[:3].T
        velocities = sol.sol(t)[3:].T
    return {
        "chemical_potential": float(mu),
        "initial_widths": widths.tolist(),
        "scales": b.tolist(),
        "widths": (b * widths).tolist(),
        "scaling_energy_invariant": (
            1 / np.prod(b, axis=1) + 0.5 * np.sum((velocities / w) ** 2, axis=1)
        ).tolist(),
    }


class Solver3D:
    def __init__(self, config: Config3D):
        started = time.perf_counter()
        self.config = config
        c = config
        self.dx = c.length / c.n
        self.x = (np.arange(c.n) - c.n // 2) * self.dx
        self.g = c.scales["interaction"]
        w = c.omegas
        x, y, z = self.x[:, None, None], self.x[None, :, None], self.x[None, None, :]
        self.trap = 0.5 * ((w[0] * x) ** 2 + (w[1] * y) ** 2 + (w[2] * z) ** 2)
        k = 2 * np.pi * np.fft.fftfreq(c.n, self.dx)
        self.k2 = k[:, None, None] ** 2 + k[None, :, None] ** 2 + k[None, None, :] ** 2
        self.kinetic_step = np.exp(-0.5j * c.dt * self.k2)
        if self.g:
            mu = tf_reference(c, [0])["chemical_potential"]
            self.psi = np.sqrt(np.maximum(mu - self.trap, 0) / self.g).astype(complex)
        else:
            self.psi = np.exp(-0.5 * (w[0] * x * x + w[1] * y * y + w[2] * z * z)).astype(complex)
        self.normalize()
        self.prepare()
        if c.experiment == "pair":
            self.psi = gaussian_pair(c, self.x)
            self.normalize()
            self.preparation.update(
                kind="normalized coherent Gaussian pair", relative_stationary_residual=None
            )
        self.initial = self.psi.copy()
        self.preparation["elapsed_seconds"] = time.perf_counter() - started
        self.preparation["persistent_array_bytes"] = sum(
            a.nbytes
            for a in (self.psi, self.initial, self.trap, self.k2, self.kinetic_step, self.x)
        )
        self.reset()
        if self.edge_mass() > 1e-5:
            raise ValueError(
                "Prepared cloud is too close to the boundary; increase the box and grid together."
            )

    def normalize(self):
        self.psi /= math.sqrt(float(np.sum(abs(self.psi) ** 2) * self.dx**3))

    def hamiltonian(self):
        return (
            ifftn(0.5 * self.k2 * fftn(self.psi))
            + (self.trap + self.g * abs(self.psi) ** 2) * self.psi
        )

    def prepare(self):
        tau = self.config.preparation_dt
        if self.g == 0:
            hpsi = self.hamiltonian()
            mu = float(np.vdot(self.psi, hpsi).real * self.dx**3)
            self.preparation = {
                "kind": "analytic noninteracting oscillator",
                "iterations": 0,
                "dt": tau,
                "iterate_l2_change": 0.0,
                "chemical_potential": mu,
                "relative_stationary_residual": float(
                    np.linalg.norm((hpsi - mu * self.psi).ravel()) * self.dx**1.5 / mu
                ),
            }
            return
        # This nonrotating ground state stays real under imaginary-time flow.
        # Use a Hermitian half-spectrum while preserving float64 precision.
        field = self.psi.real.copy()
        kinetic = np.exp(-0.5 * tau * self.k2[:, :, : self.config.n // 2 + 1])
        previous = field.copy()
        mu_shift = tf_reference(self.config, [0])["chemical_potential"]
        residual = float("inf")
        for iteration in range(1, 6001):
            # Exact local imaginary-time nonlinear flow with a chemical-potential
            # shift. Frozen-density exponentials otherwise create O(tau) bias.
            v = self.trap - mu_shift
            ex = np.exp(-tau * v)
            ratio = np.full_like(v, tau)
            np.divide(-np.expm1(-tau * v), v, out=ratio, where=abs(v) > 1e-12)
            field *= np.sqrt(ex / (1 + self.g * field**2 * ratio))
            field = irfftn(rfftn(field) * kinetic, s=field.shape)
            field *= np.sqrt(ex / (1 + self.g * field**2 * ratio))
            amplitude_norm = math.sqrt(float(np.sum(field**2) * self.dx**3))
            field /= amplitude_norm  # Imaginary time only, never real-time evolution.
            mu_shift -= math.log(amplitude_norm) / tau
            if iteration % 50 == 0:
                residual = float(np.linalg.norm((field - previous).ravel()) * self.dx**1.5)
                if residual < 2e-7:
                    break
                previous = field.copy()
        if residual >= 2e-7:
            raise ValueError("3D preparation did not converge; adjust trap or preparation step.")
        self.psi = field.astype(complex)
        hpsi = self.hamiltonian()
        mu = float(np.vdot(self.psi, hpsi).real * self.dx**3)
        self.preparation = {
            "kind": "normalized imaginary-time ground state",
            "iterations": iteration,
            "dt": tau,
            "iterate_l2_change": residual,
            "chemical_potential": mu,
            "relative_stationary_residual": float(
                np.linalg.norm((hpsi - mu * self.psi).ravel()) * self.dx**1.5 / mu
            ),
        }

    @property
    def time(self):
        return self.steps * self.config.dt

    def reset(self):
        self.psi = self.initial.copy()
        self.steps = 0
        self.release_step = 0 if self.config.experiment == "pair" else None
        self.warning = ""
        self.complete = False
        self.history = []
        self.last_batch_seconds = 0.0
        self.record()

    def release(self):
        if self.config.experiment != "single":
            raise ValueError("Release is automatic for this experiment.")
        if self.release_step is None:
            self.release_step = self.steps
            self.complete = False
            self.record()

    def edge_mass(self):
        p = abs(self.psi) ** 2
        b = max(2, self.config.n // 16)
        return float((p.sum() - p[b:-b, b:-b, b:-b].sum()) * self.dx**3)

    def applied_potential(self, step):
        c = self.config
        if self.release_step is not None or (c.experiment == "sequence" and step >= stages(c)[1]):
            return 0.0
        height, bias = drive(c, step)
        x = self.x[:, None, None]
        return (
            self.trap
            + height * np.exp(-0.5 * (x / c.barrier_width) ** 2)
            + 0.5 * bias * np.tanh(x / c.barrier_width)
        )

    def advance(self, count=4):
        if type(count) is not int or not 1 <= count <= 20:
            raise ValueError("3D step count must be an integer from 1 to 20.")
        if self.warning or self.complete:
            return
        started = time.perf_counter()
        c = self.config
        for _ in range(count):
            potential = self.applied_potential(self.steps + 0.5)
            self.psi *= np.exp(-0.5j * c.dt * (potential + self.g * abs(self.psi) ** 2))
            self.psi = ifftn(fftn(self.psi) * self.kinetic_step)
            self.psi *= np.exp(-0.5j * c.dt * (potential + self.g * abs(self.psi) ** 2))
            self.steps += 1
            if c.experiment == "sequence" and self.steps >= stages(c)[1]:
                self.release_step = stages(c)[1]
            if self.edge_mass() > 0.001:
                self.warning = (
                    "Cloud reached the periodic boundary region. Increase the box and grid."
                )
                break
            end = (
                stages(c)[2]
                if c.experiment == "sequence"
                else (self.release_step or 0) + int(c.duration / c.dt + 0.5)
            )
            if self.steps >= end:
                self.complete = True
                break
        self.last_batch_seconds = time.perf_counter() - started
        self.record()

    def diagnostics(self):
        p = abs(self.psi) ** 2
        dv = self.dx**3
        norm = float(p.sum() * dv)
        widths = []
        for axis in range(3):
            marginal = p.sum(axis=tuple(i for i in range(3) if i != axis)) * dv / norm
            mean = float(np.dot(marginal, self.x))
            widths.append(math.sqrt(float(np.dot(marginal, (self.x - mean) ** 2))))
        kinetic = float(np.sum(self.k2 * abs(fftn(self.psi)) ** 2) * dv / (2 * self.config.n**3))
        potential = float(np.sum(p * self.applied_potential(self.steps)) * dv)
        interaction = float(0.5 * self.g * np.sum(p * p) * dv)
        return {
            "time": self.time,
            "steps": self.steps,
            "norm": norm,
            "widths": widths,
            "aspect_xz": widths[0] / widths[2],
            "aspect_yz": widths[1] / widths[2],
            "energy": kinetic + potential + interaction,
            "kinetic": kinetic,
            "potential": potential,
            "interaction_energy": interaction,
            "edge_probability": self.edge_mass(),
            "released": self.release_step is not None,
            "peak_density": float(p.max()),
        }

    def record(self):
        self.history.append(self.diagnostics())

    def snapshot(self):
        p = abs(self.psi) ** 2
        n = self.config.n
        mid = n // 2
        factor = max(1, n // 32)
        nv = n // factor
        volume = p.reshape(nv, factor, nv, factor, nv, factor).mean(axis=(1, 3, 5))
        slices = [p[:, :, mid].T, p[:, mid, :].T, p[mid, :, :].T]
        columns = [p.sum(axis=2).T * self.dx, p.sum(axis=1).T * self.dx, p.sum(axis=0).T * self.dx]
        times = [
            0
            if self.release_step is None
            else max(0, (d["steps"] - self.release_step) * self.config.dt)
            for d in self.history
        ]
        ref = tf_reference(self.config, times) if self.config.experiment == "single" else None
        d0 = self.history[0]
        ratio = d0["kinetic"] / max(d0["interaction_energy"], 1e-30)
        return {
            "config": asdict(self.config),
            "scales": self.config.scales,
            "x": self.x.tolist(),
            "slices": [v.tolist() for v in slices],
            "columns": [v.tolist() for v in columns],
            "volume": volume.ravel().tolist(),
            "volume_n": nv,
            "volume_stride": factor,
            "volume_centers": self.x.reshape(nv, factor).mean(axis=1).tolist(),
            "diagnostics": self.diagnostics(),
            "history": self.history,
            "tf": ref,
            "tf_kinetic_ratio": ratio,
            "preparation": self.preparation,
            "warning": self.warning,
            "complete": self.complete,
            "last_batch_seconds": self.last_batch_seconds,
            "interferometry": measurements(
                self.config, self.x, self.psi, self.steps, self.release_step is not None
            ),
        }

    def export(self):
        return {
            "schema": "coldatomlab-3d-v1",
            "version": __version__,
            "config": asdict(self.config),
            "array_order": "x,y,z",
            "wavefunction_normalization": "integral |psi|^2 dX dY dZ = 1",
            "scales": self.config.scales,
            "x": self.x.tolist(),
            "steps": self.steps,
            "release_step": self.release_step,
            "preparation": self.preparation,
            "history": self.history,
            "psi_real": self.psi.real.tolist(),
            "psi_imag": self.psi.imag.tolist(),
        }


def replay3d(data):
    if data.get("schema") != "coldatomlab-3d-v1":
        raise ValueError("Not a 3D experiment export.")
    sim = Solver3D(Config3D(**data["config"]))
    steps, release = data["steps"], data["release_step"]
    if (
        type(steps) is not int
        or not 0 <= steps <= 30000
        or (release is not None and (type(release) is not int or not 0 <= release <= steps))
    ):
        raise ValueError("Invalid saved step/release protocol.")
    if sim.config.experiment != "single":
        expected = (
            0
            if sim.config.experiment == "pair"
            else (stages(sim.config)[1] if steps >= stages(sim.config)[1] else None)
        )
        if release != expected:
            raise ValueError("Saved release does not match the automatic sequence.")
        while sim.steps < steps:
            before = sim.steps
            sim.advance(min(20, steps - sim.steps))
            if sim.steps == before:
                raise ValueError("Replay stopped before the exported time.")
        return sim
    for target in [release, steps] if release is not None else [steps]:
        while sim.steps < target:
            before = sim.steps
            sim.advance(min(20, target - sim.steps))
            if sim.steps == before:
                raise ValueError("Replay stopped before the exported time.")
        if release is not None and sim.steps == release:
            sim.release()
    return sim
