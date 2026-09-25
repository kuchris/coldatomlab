"""Independent fixed-N two-mode reference: NumPy Hermitian diagonalization."""

import math

import numpy as np

DEFAULTS = dict(
    atoms=40,
    tunnelling_hz=5,
    interaction_hz=0,
    bias_hz=0,
    initial="coherent",
    left_fraction=1,
    phase=0,
    sigma=1.5,
    duration_ms=100,
)


def validate(config):
    c = DEFAULTS | config
    for key, lo, hi in [
        ("atoms", 2, 100),
        ("tunnelling_hz", 0, 20),
        ("interaction_hz", 0, 2),
        ("bias_hz", -20, 20),
        ("left_fraction", 0, 1),
        ("phase", -math.pi, math.pi),
        ("sigma", 0.25, 20),
        ("duration_ms", 1, 1000),
    ]:
        value = c[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid {key}.")
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"Invalid {key}.")
    if int(c["atoms"]) != c["atoms"]:
        raise ValueError("Atom number must be an integer.")
    c["atoms"] = int(c["atoms"])
    if c["initial"] not in ("coherent", "gaussian", "fock") or set(c) != set(DEFAULTS):
        raise ValueError("Unknown initial state or parameter.")
    return c


def initial_state(c):
    n, p = c["atoms"], c["left_fraction"]
    k = np.arange(n + 1)
    if c["initial"] == "fock":
        a = (k == math.floor(n * p + 0.5)).astype(float)
    elif c["initial"] == "gaussian":
        a = np.exp(-(((k - n * p) / c["sigma"]) ** 2) / 4)
    elif p in (0, 1):
        a = (k == n * p).astype(float)
    else:
        a = np.sqrt([math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in k])
    psi = a * np.exp(1j * (n - k) * c["phase"])
    return psi / np.linalg.norm(psi)


def hamiltonian(c):
    n = c["atoms"]
    m = np.arange(n + 1) - n / 2
    off = -c["tunnelling_hz"] * np.sqrt(np.arange(1, n + 1) * np.arange(n, 0, -1))
    return (
        np.diag(c["interaction_hz"] * m**2 - c["bias_hz"] * m) + np.diag(off, 1) + np.diag(off, -1)
    )


def diagnostics(c, psi):
    n = c["atoms"]
    k = np.arange(n + 1)
    probability = abs(psi) ** 2
    norm = float(probability.sum())
    mean = float(k @ probability)
    variance = float((k - mean) ** 2 @ probability)
    cross = np.sum(psi[1:].conj() * psi[:-1] * np.sqrt(k[1:] * (n - k[:-1])))
    coherence = float(2 * abs(cross) / n)
    denominator = mean * (1 - mean / n)
    return dict(
        probability=probability.tolist(),
        norm=norm,
        mean_left=mean,
        mean_right=n * norm - mean,
        variance_left=variance,
        coherence=coherence,
        phase=float(np.angle(cross)) if coherence > 1e-8 else None,
        coherence_real=float(2 * cross.real / n),
        coherence_imag=float(2 * cross.imag / n),
        number_noise_ratio=variance / denominator if denominator > 1e-8 else None,
        energy_hz=float(np.vdot(psi, hamiltonian(c) @ psi).real),
    )


class Reference:
    def __init__(self, config):
        self.config = validate(config)
        self.eigenvalues, self.vectors = np.linalg.eigh(hamiltonian(self.config))
        self.coefficients = self.vectors.T @ initial_state(self.config)

    def at(self, time_ms):
        if not math.isfinite(time_ms) or not 0 <= time_ms <= self.config["duration_ms"] + 1e-9:
            raise ValueError("Time is outside this experiment.")
        psi = self.vectors @ (
            np.exp(-2j * np.pi * self.eigenvalues * time_ms / 1000) * self.coefficients
        )
        return dict(
            time_ms=time_ms,
            real=psi.real.tolist(),
            imag=psi.imag.tolist(),
            **diagnostics(self.config, psi),
        )


def sample(state, shots, seed):
    if type(shots) is not int or not 1 <= shots <= 10000:
        raise ValueError("Invalid shot count.")
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError("Invalid seed.")
    cumulative = np.cumsum(state["probability"])
    counts = np.zeros(len(cumulative), dtype=int)
    rng = seed
    for _ in range(shots):
        rng = (1664525 * rng + 1013904223) % 2**32
        k = min(
            int(np.searchsorted(cumulative, (rng + 0.5) / 2**32, side="right")), len(counts) - 1
        )
        counts[k] += 1
    return dict(time_ms=state["time_ms"], shots=shots, seed=seed, counts=counts.tolist())


def _compare(saved, reference, context):
    if set(saved) != set(reference):
        raise ValueError(f"{context}: fields differ.")
    for key, value in reference.items():
        if value is None:
            valid = saved[key] is None
        elif key == "phase" and saved[key] is not None:
            valid = (
                math.isfinite(saved[key])
                and abs(np.angle(np.exp(1j * (saved[key] - value)))) < 5e-8
            )
        else:
            try:
                a, b = np.asarray(saved[key], dtype=float), np.asarray(value, dtype=float)
                valid = (
                    a.shape == b.shape
                    and np.isfinite(a).all()
                    and np.allclose(a, b, rtol=0, atol=5e-8)
                )
            except (ValueError, TypeError):
                valid = False
        if not valid:
            raise ValueError(f"{context}: {key} differs from independent reference.")


def verify_record(record):
    ref = Reference(record["config"])
    step = record["step"]
    if type(step) is not int or not 0 <= step <= 200:
        raise ValueError("Invalid display step.")
    time_ms = ref.config["duration_ms"] * step / 200
    state = ref.at(time_ms)
    _compare(record["state"], state, "Final state")
    saved_field = np.array(record["state"]["real"]) + 1j * np.array(record["state"]["imag"])
    field = np.array(state["real"]) + 1j * np.array(state["imag"])
    error = float(np.linalg.norm(saved_field - field))
    if error > 5e-8 or abs(record["state"]["norm"] - 1) > 1e-9:
        raise ValueError("Complex-state or norm tolerance exceeded.")
    history = record["history"]
    if len(history) != step + 1:
        raise ValueError("History length differs from completed steps.")
    for i, row in enumerate(history):
        snapshot = ref.at(ref.config["duration_ms"] * i / 200)
        _compare(row, {k: snapshot[k] for k in HISTORY_KEYS}, "History")
    measurement = record["measurement"]
    if measurement is not None:
        # Regenerate from the exported probabilities after independently checking
        # their accuracy; seed thresholds near bin edges need not be bit-identical
        # between independent eigensolvers.
        regenerated = sample(record["state"], measurement["shots"], measurement["seed"])
        if measurement != regenerated:
            raise ValueError("Measurement seed, counts or time differs.")
    return dict(
        verified=True,
        complex_state_l2=error,
        history_rows=len(history),
        measurement_verified=measurement is not None,
    )


HISTORY_KEYS = (
    "time_ms",
    "mean_left",
    "mean_right",
    "coherence",
    "variance_left",
    "norm",
    "energy_hz",
)


def verify_export(data):
    if data.get("schema") != "coldatomlab-twomode-v1":
        raise ValueError("Unknown two-mode schema.")
    if data.get("convention") != "n_left=0..N; H/h in Hz; time_ms; right-minus-left phase":
        raise ValueError("Unknown basis or units.")
    return dict(
        current=verify_record(data["current"]),
        pinned=verify_record(data["pinned"]) if data.get("pinned") is not None else None,
        reference="Independent NumPy float64 spectral evolution; fixed two-mode model only",
    )
