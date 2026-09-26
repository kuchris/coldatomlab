"""Full 3D conservative vortex GPE reference, in radial oscillator units."""

import math

import numpy as np
from scipy.fft import fftn, ifftn

from .physical import HBAR, RB87_MASS
from .solver3d import Config3D, Solver3D

DEFAULTS = dict(
    atoms=20000,
    tof_duration=2,
    n=64,
    length=16,
    dt=0.004,
    g=0,
    charge=1,
    duration=2,
    height=0,
    width=0.8,
    radius=2,
    omega=1.2,
    stir_time=8,
    ramp=1,
    loop_radius=1.5,
)


def validate(config):
    c = DEFAULTS | config
    if set(c) != set(DEFAULTS) or c["n"] not in (32, 64, 128) or type(c["n"]) is not int:
        raise ValueError("Unknown vortex configuration or grid.")
    for k, lo, hi in [
        ("atoms", 1000, 300000),
        ("tof_duration", 0.1, 6),
        ("length", 16, 32),
        ("dt", 0.001, 0.008),
        ("g", 0, 1000),
        ("duration", 0.1, 16),
        ("height", 0, 20),
        ("width", 0.5, 2),
        ("radius", 0, 4),
        ("omega", -2, 2),
        ("stir_time", 1, 12),
        ("ramp", 0.25, 3),
        ("loop_radius", 0.75, 4),
    ]:
        v = c[k]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"Invalid {k}.")
    if type(c["charge"]) is not int or c["charge"] not in (-1, 0, 1):
        raise ValueError("Charge must be -1, 0 or 1.")
    if c["length"] / c["n"] > 0.5 or c["width"] < 2 * c["length"] / c["n"]:
        raise ValueError("Resolve the cloud and stirrer: dx<=0.5 and width>=2dx.")
    if 2 * c["ramp"] > c["stir_time"]:
        raise ValueError("Two ramps must fit within the stirring time.")
    if type(c["atoms"]) is not int:
        raise ValueError("Atom number must be an integer.")
    if c["g"] * scales()["length_um"] * 1000 / (4 * math.pi * c["atoms"]) > 10:
        raise ValueError(
            "g/N implies scattering length above 10 nm; increase atom number or reduce g."
        )
    return c


def scales():
    a = math.sqrt(HBAR / (RB87_MASS * 2 * math.pi * 50))
    return dict(
        length_um=a * 1e6,
        time_ms=1000 / (2 * math.pi * 50),
        energy_hz=50,
        circulation_um2_ms=2 * math.pi * a * a / (1 / (2 * math.pi * 50)) * 1e9,
    )


def parent_config(c):
    a = scales()["length_um"] * 1e-6
    return Config3D(
        n=c["n"],
        length=c["length"],
        dt=c["dt"],
        atoms=c["atoms"],
        scattering_nm=c["g"] * a / (4 * math.pi * c["atoms"]) * 1e9,
        reference_hz=50,
        fx_hz=50,
        fy_hz=50,
        fz_hz=100,
        duration=min(c["duration"], 4),
        preparation_dt=0.002,
    )


def drive(c, t):
    a = max(0, min(1, t / c["ramp"], (c["stir_time"] - t) / c["ramp"]))
    return (
        c["height"] * math.sin(math.pi * a / 2) ** 2,
        c["radius"] * math.cos(c["omega"] * t),
        c["radius"] * math.sin(c["omega"] * t),
    )


def sample2(field, x, y, length):
    n = field.shape[0]
    u = x * n / length + n / 2
    v = y * n / length + n / 2
    i, j = math.floor(u), math.floor(v)
    a, b = u - i, v - j
    if not (0 <= i < n - 1 and 0 <= j < n - 1):
        return 0j
    return (
        field[i, j] * (1 - a) * (1 - b)
        + field[i + 1, j] * a * (1 - b)
        + field[i, j + 1] * (1 - a) * b
        + field[i + 1, j + 1] * a * b
    )


def winding_diagnostics(field, c, gx=None, gy=None):
    n = c["n"]
    dx = c["length"] / n
    plane = field[:, :, n // 2]
    peak = float(np.max(abs(plane) ** 2))
    points = [
        (
            c["loop_radius"] * math.cos(2 * math.pi * i / 128),
            c["loop_radius"] * math.sin(2 * math.pi * i / 128),
        )
        for i in range(128)
    ]
    values = np.array([sample2(plane, x, y, c["length"]) for x, y in points])
    jumps = np.angle(np.roll(values, -1) * values.conj())
    reliable = bool(
        peak > 0 and np.min(abs(values) ** 2) > peak * 1e-3 and np.max(abs(jumps)) < 0.75 * math.pi
    )
    winding = int(round(float(jumps.sum() / (2 * np.pi)))) if reliable else None
    circulation = None
    if reliable and gx is not None:
        total = 0.0
        for i, (x, y) in enumerate(points):
            psi = values[i]
            vx = float(
                (psi.conjugate() * sample2(gx[:, :, n // 2], x, y, c["length"])).imag
                / abs(psi) ** 2
            )
            vy = float(
                (psi.conjugate() * sample2(gy[:, :, n // 2], x, y, c["length"])).imag
                / abs(psi) ** 2
            )
            total += (-y * vx + x * vy) / 128
        circulation = total  # integral(v.dl)/(2pi) in oscillator units
    centered = (plane[:-1, :-1] + plane[1:, :-1] + plane[:-1, 1:] + plane[1:, 1:]) / 4
    crossings = []
    for i in range(n - 2):
        for j in range(n - 2):
            p = np.array(
                [centered[i, j], centered[i + 1, j], centered[i + 1, j + 1], centered[i, j + 1]]
            )
            if np.min(abs(p) ** 2) < peak * 1e-3:
                continue
            angles = np.angle(np.roll(p, -1) * p.conj())
            q = int(round(float(angles.sum() / (2 * np.pi))))
            if abs(q) == 1:
                crossings.append(dict(x=(i + 1 - n / 2) * dx, y=(j + 1 - n / 2) * dx, charge=q))
    return dict(
        winding=winding,
        loop_reliable=reliable,
        flow_circulation_quanta=circulation,
        crossings=crossings,
        positive=sum(p["charge"] == 1 for p in crossings),
        negative=sum(p["charge"] == -1 for p in crossings),
    )


class Vortex:
    def __init__(self, config, initial=None):
        self.config = c = validate(config)
        n = c["n"]
        self.dx = c["length"] / n
        self.x = (np.arange(n) - n / 2) * self.dx
        self.X, self.Y, self.Z = np.meshgrid(self.x, self.x, self.x, indexing="ij", sparse=True)
        self.trap = 0.5 * (self.X**2 + self.Y**2 + 4 * self.Z**2)
        self.k = 2 * np.pi * np.fft.fftfreq(n, self.dx)
        self.k2 = (
            self.k[:, None, None] ** 2 + self.k[None, :, None] ** 2 + self.k[None, None, :] ** 2
        )
        self.kinetic = np.exp(-0.5j * c["dt"] * self.k2)
        if initial is None:
            solver = Solver3D(parent_config(c))
            self.psi = solver.psi.copy()
            self.preparation = solver.preparation
            if c["charge"]:
                r = np.sqrt(self.X**2 + self.Y**2)
                if c["g"] == 0:
                    self.psi *= self.X + 1j * c["charge"] * self.Y
                else:
                    xi = 1 / math.sqrt(2 * c["g"] * float(np.max(abs(self.psi) ** 2)))
                    self.psi *= (self.X + 1j * c["charge"] * self.Y) / np.sqrt(r * r + xi * xi)
                self.psi /= np.sqrt(np.sum(abs(self.psi) ** 2) * self.dx**3)  # preparation only
        else:
            self.psi = np.asarray(initial, dtype=complex).copy()
            if (
                self.psi.shape != (n, n, n)
                or not np.isfinite(self.psi).all()
                or abs(np.sum(abs(self.psi) ** 2) * self.dx**3 - 1) > 1e-3
            ):
                raise ValueError("Invalid prepared field; no real-time normalization is applied.")
        self.initial = self.psi.copy()
        self.steps = 0
        self.release_step = None

    def release(self):
        if self.release_step is None:
            self.release_step = self.steps

    def potential(self, t):
        if self.release_step is not None and t >= self.release_step * self.config["dt"] - 1e-12:
            return 0.0
        h, x, y = drive(self.config, t)
        return self.trap + h * np.exp(
            -0.5 * ((self.X - x) ** 2 + (self.Y - y) ** 2) / self.config["width"] ** 2
        )

    def advance(self, count):
        c = self.config
        for _ in range(count):
            v = self.potential((self.steps + 0.5) * c["dt"])
            self.psi *= np.exp(-0.5j * c["dt"] * (v + c["g"] * abs(self.psi) ** 2))
            self.psi = ifftn(fftn(self.psi) * self.kinetic)
            self.psi *= np.exp(-0.5j * c["dt"] * (v + c["g"] * abs(self.psi) ** 2))
            self.steps += 1

    def diagnostics(self):
        c = self.config
        dv = self.dx**3
        p = abs(self.psi) ** 2
        norm = float(p.sum() * dv)
        ft = fftn(self.psi)
        gx = ifftn(1j * self.k[:, None, None] * ft)
        gy = ifftn(1j * self.k[None, :, None] * ft)
        kinetic = float(np.sum(0.5 * self.k2 * abs(ft) ** 2) * dv / c["n"] ** 3)
        energy = kinetic + float(
            np.sum(self.potential(self.steps * c["dt"]) * p + 0.5 * c["g"] * p * p) * dv
        )
        lz = float(np.sum((self.psi.conj() * (self.X * gy - self.Y * gx)).imag) * dv / norm)
        band = max(2, c["n"] // 16)
        edge = float((p.sum() - p[band:-band, band:-band, band:-band].sum()) * dv)
        return dict(
            steps=self.steps,
            time=self.steps * c["dt"],
            norm=norm,
            energy=energy,
            lz=lz,
            edge_probability=edge,
            widths=[
                float(
                    np.sqrt(
                        max(0, np.sum(p * a * a) * dv / norm - (np.sum(p * a) * dv / norm) ** 2)
                    )
                )
                for a in (self.X, self.Y, self.Z)
            ],
            **winding_diagnostics(self.psi, c, gx, gy),
        )


def verify_export(data):
    """Independent preparation and float64 propagation check, not bitwise GPU replay."""
    if (data.get("schema"), data.get("version")) not in (
        ("coldatomlab-vortex-v1", "0.16.0"),
        ("coldatomlab-vortex-v2", "0.17.0"),
    ):
        raise ValueError("Unsupported vortex export.")
    if data.get("schema") == "coldatomlab-vortex-v2" and "release_step" not in data:
        raise ValueError("Missing release protocol.")
    c = validate(data["config"])
    if data.get("array_order") != "x,y,z interleaved real,imag":
        raise ValueError("Invalid array convention.")
    if data.get("scales") != scales():
        if set(data.get("scales", {})) != set(scales()) or any(
            not math.isclose(data["scales"][k], v, rel_tol=2e-12) for k, v in scales().items()
        ):
            raise ValueError("Physical scales do not match.")
    steps = data["steps"]
    release_step = data.get("release_step")
    if release_step is not None and (
        type(release_step) is not int
        or not 0 <= release_step <= steps
        or release_step > math.floor(c["duration"] / c["dt"] + 0.5)
    ):
        raise ValueError("Invalid release step.")
    endpoint = (
        math.floor(c["duration"] / c["dt"] + 0.5)
        if release_step is None
        else release_step + math.floor(c["tof_duration"] / c["dt"] + 0.5)
    )
    if type(steps) is not int or not 0 <= steps <= endpoint:
        raise ValueError("Invalid step count.")

    def field(key):
        raw = np.asarray(data[key], dtype=float)
        if raw.shape != (2 * c["n"] ** 3,) or not np.isfinite(raw).all():
            raise ValueError(f"Invalid {key} field.")
        return (raw[::2] + 1j * raw[1::2]).reshape((c["n"],) * 3)

    initial, saved = field("initial"), field("field")
    reference = Vortex(c)
    dv = reference.dx**3
    preparation_error = float(np.sqrt(np.sum(abs(reference.psi - initial) ** 2) * dv))
    if preparation_error > 3e-4:
        raise ValueError("Initial field does not match the declared preparation.")
    sim = Vortex(c, initial)
    sim.release_step = release_step
    rows = data["history"]
    if (
        not isinstance(rows, list)
        or not rows
        or rows[0].get("steps") != 0
        or rows[-1].get("steps") != steps
    ):
        raise ValueError("Incomplete diagnostic history.")
    previous = -1
    max_errors = dict(norm=0.0, energy=0.0, lz=0.0)
    for row in rows:
        step = row["steps"]
        if type(step) is not int or not previous < step <= steps:
            raise ValueError("Invalid history ordering.")
        if not math.isclose(row["time"], step * c["dt"], abs_tol=1e-12):
            raise ValueError("History time does not match the physical steps.")
        sim.advance(step - sim.steps)
        actual = sim.diagnostics()
        for key, tol in [
            ("norm", 0.001),
            ("energy", 0.005),
            ("lz", 0.005),
            ("edge_probability", 2e-5),
        ]:
            if not math.isfinite(row[key]) or abs(actual[key] - row[key]) > tol:
                raise ValueError(f"CPU replay differs in {key}; refine before drawing conclusions.")
            if key in max_errors:
                max_errors[key] = max(max_errors[key], abs(actual[key] - row[key]))
        if data["schema"] == "coldatomlab-vortex-v2":
            widths = np.asarray(row.get("widths"), dtype=float)
            if widths.shape != (3,) or not np.allclose(
                widths, actual["widths"], rtol=0.001, atol=1e-5
            ):
                raise ValueError("History widths differ from CPU replay.")
        # A threshold crossing can legitimately change between float32 and
        # float64. Reject an unconfirmed history instead of silently accepting
        # the saved classification; callers can refine or inspect the full field.
        for key in ("winding", "loop_reliable", "positive", "negative"):
            if row[key] != actual[key]:
                raise ValueError(
                    f"History {key} differs at step {step}; inspect density masking and refine."
                )
        flow, target = row["flow_circulation_quanta"], actual["flow_circulation_quanta"]
        if (flow is None) != (target is None) or (
            flow is not None and not math.isclose(flow, target, abs_tol=0.002, rel_tol=0.002)
        ):
            raise ValueError(f"History circulation differs at step {step}.")
        remaining = list(actual["crossings"])
        for crossing in row["crossings"]:
            match = next(
                (
                    v
                    for v in remaining
                    if v["charge"] == crossing["charge"]
                    and math.hypot(v["x"] - crossing["x"], v["y"] - crossing["y"]) <= sim.dx * 1.01
                ),
                None,
            )
            if match is None:
                raise ValueError("History crossing location differs from CPU replay.")
            remaining.remove(match)
        if remaining:
            raise ValueError("History crossing locations are incomplete.")
        previous = step
    error = float(np.sqrt(np.sum(abs(sim.psi - saved) ** 2) * dv))
    if not math.isfinite(error) or error > 0.005:
        raise ValueError("GPU field differs from float64 replay by more than 0.005 in L2.")
    sim.psi = saved
    actual = sim.diagnostics()
    final = rows[-1]
    for key in ("norm", "energy", "lz", "edge_probability"):
        if not math.isclose(final[key], actual[key], rel_tol=2e-5, abs_tol=2e-6):
            raise ValueError(f"Saved final {key} does not match the field.")
    for key in ("winding", "loop_reliable", "positive", "negative", "crossings"):
        if final[key] != actual[key]:
            raise ValueError(f"Saved final {key} does not match the field.")
    flow, target = final["flow_circulation_quanta"], actual["flow_circulation_quanta"]
    if (flow is None) != (target is None) or (
        flow is not None and not math.isclose(flow, target, rel_tol=2e-4, abs_tol=2e-4)
    ):
        raise ValueError("Saved flow circulation does not match the field.")
    return dict(
        verified=True,
        preparation_l2_error=preparation_error,
        evolution_l2_error=error,
        history_max_errors=max_errors,
        diagnostics=actual,
        comparison="Independent float64 preparation and evolution; finite tolerances, not bitwise replay.",
    )
