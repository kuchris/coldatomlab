"""Frozen-axial-Gaussian unit conversion; see docs/PHYSICAL_UNITS.md."""

import math
from dataclasses import asdict, dataclass

H = 6.62607015e-34
HBAR = H / (2 * math.pi)
AMU = 1.66053906660e-27
RB87_MASS = 1.443160895e-25


@dataclass(frozen=True)
class Physical:
    species: str = "Rb87"
    mass_u: float = RB87_MASS / AMU
    atoms: int = 200
    scattering_nm: float = 5.3
    reference_hz: float = 20.0
    axial_hz: float = 2000.0

    def __post_init__(self):
        if self.species not in ("Rb87", "custom"):
            raise ValueError("Choose Rb87 or a custom bosonic species.")
        if type(self.atoms) is not int or not 10 <= self.atoms <= 100000:
            raise ValueError("Atom number must be an integer between 10 and 100000.")
        for name, low, high in (
            ("mass_u", 1, 300),
            ("scattering_nm", 0, 20),
            ("reference_hz", 1, 1000),
            ("axial_hz", 10, 100000),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be between {low} and {high}.")
        if self.species == "Rb87":
            object.__setattr__(self, "mass_u", RB87_MASS / AMU)

    def scales(self):
        mass = RB87_MASS if self.species == "Rb87" else self.mass_u * AMU
        az = math.sqrt(HBAR / (mass * 2 * math.pi * self.axial_hz))
        a = self.scattering_nm * 1e-9
        return {
            "length_um": math.sqrt(HBAR / (mass * 2 * math.pi * self.reference_hz)) * 1e6,
            "time_ms": 1000 / (2 * math.pi * self.reference_hz),
            "energy_hz": self.reference_hz,
            "axial_length_um": az * 1e6,
            "interaction": math.sqrt(8 * math.pi) * self.atoms * a / az,
            "scattering_axial_ratio": a / az,
            "axial_gap": self.axial_hz / self.reference_hz,
            "mass_kg": mass,
        }


def regime(physical, config, diagnostics, initial_mu):
    """Conservative scale checks, not a certification of 3D or finite-T validity."""
    scales = physical.scales()
    gap = scales["axial_gap"]
    peak_density = diagnostics["peak_density"]
    a = physical.scattering_nm * 1e-3  # micrometers
    gas = (
        physical.atoms
        * peak_density
        / scales["length_um"] ** 2
        / (math.sqrt(math.pi) * scales["axial_length_um"])
        * a**3
    )
    ratios = {
        "initial_mu_over_gap": initial_mu / gap,
        "peak_interaction_over_gap": config.interaction * peak_density / gap,
        "kinetic_over_gap": diagnostics["kinetic_per_particle"] / gap,
        "trap_over_axial": max(config.omega_x, config.omega_y) / gap,
        "scattering_over_axial_length": scales["scattering_axial_ratio"],
        "peak_gas_parameter": gas,
    }
    limits = (0.1, 0.1, 0.1, 0.1, 0.05, 0.001)
    severity = max(v / limit for v, limit in zip(ratios.values(), limits))
    status = "supported" if severity <= 1 else "marginal"
    if (
        max(list(ratios.values())[:4]) >= 1
        or ratios["scattering_over_axial_length"] >= 0.2
        or gas >= 0.01
    ):
        status = "outside"
    return {"status": status, "ratios": ratios, "parameters": asdict(physical), **scales}
