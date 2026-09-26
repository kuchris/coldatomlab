"""Independent NumPy camera oracle and browser acquisition verification.

Projection is N integral |psi|² dX_los / a0², never a 2D frozen-axis reduction.
"""

import math

import numpy as np

from .imaging import SIGMA_UM2, bin_mean, blur_transmission, transmission
from .solver3d import Config3D


class CameraRNG:
    """Specified 32-bit LCG, Box-Muller normals, Knuth/PTRS Poisson counts."""

    def __init__(self, seed):
        self.state = seed

    def uniform(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return (self.state + 0.5) / 4294967296

    def normal(self):
        return math.sqrt(-2 * math.log(self.uniform())) * math.cos(2 * math.pi * self.uniform())

    def poisson(self, mu):
        if mu < 30:
            k, p, bound = 0, 1.0, math.exp(-mu)
            while True:
                k += 1
                p *= self.uniform()
                if p <= bound:
                    return k - 1
        b = 0.931 + 2.53 * math.sqrt(mu)
        a, inv, vr = -0.059 + 0.02483 * b, 1.1239 + 1.1328 / (b - 3.4), 0.9277 - 3.6224 / (b - 2)
        while True:
            u, v = self.uniform() - 0.5, self.uniform()
            us = 0.5 - abs(u)
            k = math.floor((2 * a / us + b) * u + mu + 0.43)
            if us >= 0.07 and v <= vr:
                return k
            if k < 0 or (us < 0.013 and v > us):
                continue
            logfact = (
                sum(math.log(j) for j in range(2, k + 1))
                if k < 256
                else (
                    (k + 0.5) * math.log(k)
                    - k
                    + 0.5 * math.log(2 * math.pi)
                    + 1 / (12 * k)
                    - 1 / (360 * k**3)
                    + 1 / (1260 * k**5)
                )
            )
            if math.log(v * inv / (a / (us * us) + b)) <= -mu + k * math.log(mu) - logfact:
                return k


def project(source, axis):
    c = Config3D(**source["config"])
    psi = np.asarray(source["psi_real"]) + 1j * np.asarray(source["psi_imag"])
    if psi.shape != (c.n,) * 3 or not np.isfinite(psi).all():
        raise ValueError("Invalid camera source field.")
    directions = {"x": (0, ["y", "z"]), "y": (1, ["x", "z"]), "z": (2, ["x", "y"])}
    if axis not in directions:
        raise ValueError("Invalid camera direction.")
    along, axes = directions[axis]
    density = (
        (abs(psi) ** 2).sum(axis=along).T * (c.length / c.n) * c.atoms / c.scales["length_um"] ** 2
    )
    return density, (np.arange(c.n) - c.n // 2) * (c.length / c.n) * c.scales["length_um"], axes


def fit_profile(x, y, errors=None):
    """Image-only scan, using independent NumPy least squares rather than JS elimination."""

    def no(reason):
        return dict(available=False, reason=reason, phase=None, spacing=None, contrast=None)

    x, y = np.asarray(x), np.asarray(y, dtype=float)
    if len(x) < 20 or not np.isfinite(y).all():
        return no("Need 20 valid samples.")
    span, pitch, scale = np.ptp(x), x[1] - x[0], np.ptp(y)
    if scale <= 1e-10 or np.maximum(y, 0).sum() <= 0:
        return no("No signal.")
    p = np.maximum(y, 0)
    center = np.dot(x, p) / sum(p)
    sd = math.sqrt(np.dot((x - center) ** 2, p) / sum(p))
    kmin, kmax = 2 * np.pi * 2.5 / span, 2 * np.pi / (4 * pitch)
    if kmax <= kmin or sd < pitch:
        return no("Insufficient resolution.")
    yn = y / scale

    def trial(k, width, offset):
        z = (x - offset) / width
        e = np.exp(-0.5 * z * z)
        matrix = np.array([e, e * z, e * z * z, e * np.cos(k * x), e * np.sin(k * x)]).T
        coeff, _, rank, _ = np.linalg.lstsq(matrix, yn, rcond=None)
        if rank < 5:
            return None
        predicted = matrix @ coeff
        return dict(
            k=k,
            width=width,
            offset=offset,
            coeff=coeff,
            predicted=predicted,
            loss=sum((predicted - yn) ** 2),
            rows=matrix,
        )

    best = None
    dk = (kmax - kmin) / 80
    for width in sd * np.array([0.45, 0.6, 0.8, 1, 1.3, 1.7, 2.2]):
        for offset in [center - 0.2 * sd, center, center + 0.2 * sd]:
            for j in range(81):
                value = trial(kmin + j * dk, width, offset)
                if value is not None and (best is None or value["loss"] < best["loss"]):
                    best = value
    if best is None:
        return no("Ill-conditioned fit.")
    for stage in range(5):
        old, step = best, dk / 4 ** (stage + 1)
        for width in old["width"] * np.array([1 - 0.15 / 2**stage, 1, 1 + 0.15 / 2**stage]):
            for offset in [
                old["offset"] - pitch / 2**stage,
                old["offset"],
                old["offset"] + pitch / 2**stage,
            ]:
                for j in range(-5, 6):
                    k = old["k"] + j * step
                    if not kmin < k < kmax:
                        continue
                    value = trial(k, width, offset)
                    if value is not None and value["loss"] < best["loss"]:
                        best = value
    amplitude = math.hypot(*best["coeff"][3:5])
    baseline = best["coeff"][0]
    contrast = amplitude / baseline if baseline else float("inf")
    rmse = math.sqrt(best["loss"] / len(x))
    smooth = best["rows"][:, [0, 1, 2]]
    coeff = np.linalg.lstsq(smooth, yn, rcond=None)[0]
    base_loss = sum((smooth @ coeff - yn) ** 2)
    noise = max(errors) if errors is not None else 0
    if (
        baseline <= 0
        or not 0.08 <= contrast <= 1.1
        or rmse > 0.12
        or base_loss <= 0
        or 1 - best["loss"] / base_loss < 0.7
        or amplitude * scale < 5 * noise
        or best["k"] - kmin < dk / 4
        or kmax - best["k"] < dk / 4
    ):
        return no("Unresolved/noisy/model mismatch.")
    return dict(
        available=True,
        phase=math.atan2(best["coeff"][4], best["coeff"][3]),
        spacing=2 * np.pi / best["k"],
        contrast=contrast,
        relative_rmse=rmse,
        fit_profile=(best["predicted"] * scale).tolist(),
    )


def acquire_reference(source, c):
    density, fine_x, axes = project(source, c["axis"])
    return acquire_projection(density, fine_x, axes, c, source["config"]["atoms"])


def validate_camera(c, n):
    """Validate browser-camera settings without acquiring a frame."""
    if c["axis"] not in ("x", "y", "z"):
        raise ValueError("Invalid camera direction.")
    b = c["binning"]
    if type(b) is not int or b not in (1, 2, 4, 8, 16) or n % b or n // b < 8:
        raise ValueError("Invalid binning.")
    for key, lo, hi in [
        ("fwhm_um", 0, 20),
        ("saturation", 0.001, 10),
        ("exposure_us", 0.1, 100),
        ("efficiency", 0.05, 1),
        ("read_noise", 0, 20),
        ("roi_um", 1, 100),
        ("strip_um", 0.2, 40),
    ]:
        if (
            isinstance(c[key], bool)
            or not isinstance(c[key], (int, float))
            or not math.isfinite(c[key])
            or not lo <= c[key] <= hi
        ):
            raise ValueError(f"Invalid {key}.")
    if (
        type(c["noise"]) is not bool
        or type(c["seed"]) is not int
        or not 0 <= c["seed"] <= 2**32 - 1
    ):
        raise ValueError("Invalid noise settings.")


def acquire_projection(density, fine_x, axes, c, atom_number, fit_fringes=True):
    """Independent optical acquisition from a verified physical column density."""
    b = c["binning"]
    n = len(fine_x)
    validate_camera(c, n)
    dx = fine_x[1] - fine_x[0]
    pitch = dx * b
    x = fine_x.reshape(-1, b).mean(axis=1)
    t = transmission(SIGMA_UM2 * density, c["saturation"])
    sampled = bin_mean(blur_transmission(t, c["fwhm_um"] / (math.sqrt(8 * math.log(2)) * dx)), b)
    fluence = (
        c["saturation"]
        * 16.69
        * c["exposure_us"]
        * 1e-6
        / (6.62607015e-34 * 299792458 / (0.780241209e-6))
        * 1e-12
    )
    reference = fluence * pitch**2 * c["efficiency"]
    rng = CameraRNG(c["seed"])

    def frame(means):
        return np.array(
            [
                100
                + (rng.poisson(float(mu)) + c["read_noise"] * rng.normal() if c["noise"] else mu)
                for mu in means.ravel()
            ]
        ).reshape(means.shape)

    atoms = frame(sampled * reference)
    ref = frame(np.full_like(sampled, reference))
    dark = np.array(
        [100 + (c["read_noise"] * rng.normal() if c["noise"] else 0) for _ in sampled.ravel()]
    ).reshape(sampled.shape)
    av, rv = atoms - dark, ref - dark
    valid = (av > 0) & (rv > 0)
    recovered = np.full_like(atoms, np.nan)
    recovered[valid] = (
        np.log(rv[valid] / av[valid]) + c["saturation"] * (rv[valid] - av[valid]) / reference
    ) / SIGMA_UM2
    variance = np.zeros_like(atoms)
    if c["noise"]:
        a, r = av[valid], rv[valid]
        ga, gr, gd = (
            -1 / a - c["saturation"] / reference,
            1 / r + c["saturation"] / reference,
            1 / a - 1 / r,
        )
        variance[valid] = (
            ga**2 * (a + c["read_noise"] ** 2)
            + gr**2 * (r + c["read_noise"] ** 2)
            + gd**2 * c["read_noise"] ** 2
        ) / SIGMA_UM2**2
    variance[~valid] = np.nan
    selection = np.abs(x) <= c["roi_um"]
    strip = np.abs(x) <= c["strip_um"] / 2
    if selection.sum() < 4 or not strip.any():
        raise ValueError("ROI/strip too small.")
    profile = recovered[strip].mean(axis=0)
    errors = np.sqrt(variance[strip].sum(axis=0)) / strip.sum()
    truth = bin_mean(density, b)
    truth_profile = truth[strip].mean(axis=0)
    roi = selection[:, None] & selection[None, :]
    invalid = int((~valid & roi).sum())
    return dict(
        axes=axes,
        x_um=x,
        truth_density=truth,
        density=recovered,
        **({} if fit_fringes else {"density_variance": variance}),
        atoms_frame=atoms,
        reference_frame=ref,
        dark_frame=dark,
        expected_reference_e=reference,
        pixel_um=pitch,
        model_total_atoms=density.sum() * dx**2,
        profile=profile,
        profile_error=errors,
        truth_profile=truth_profile,
        fit_x_um=x[selection],
        measured=(
            fit_profile(x[selection], profile[selection], errors[selection] if c["noise"] else None)
            if fit_fringes
            else dict(
                available=False,
                reason="Fringe analysis not requested.",
                phase=None,
                spacing=None,
                contrast=None,
            )
        ),
        truth=fit_profile(x[selection], truth_profile[selection])
        if fit_fringes
        else dict(
            available=False,
            reason="Fringe analysis not requested.",
            phase=None,
            spacing=None,
            contrast=None,
        ),
        atoms_roi=None if invalid else recovered[roi].sum() * pitch**2,
        truth_atoms_roi=truth[roi].sum() * pitch**2,
        atom_standard_error=None if invalid else math.sqrt(variance[roi].sum()) * pitch**2,
        invalid_roi_pixels=invalid,
        scattered_per_atom=fluence * (1 - t).sum() * dx**2 / atom_number,
        roi_bounds_um=[x[selection][0] - pitch / 2, x[selection][-1] + pitch / 2],
        strip_bounds_um=[x[strip][0] - pitch / 2, x[strip][-1] + pitch / 2],
    )


def verify_camera(data):
    if data.get("camera_model") != "rb87-browser-camera-v1":
        raise ValueError("Unknown 3D camera model.")
    saved = data["image"]
    regenerated = acquire_reference(data["source"], saved["camera"])
    return verify_image(saved, regenerated)


def verify_image(saved, regenerated):
    """Check numerical images and fits; reason/warning prose is not verified."""
    if saved["axes"] != regenerated["axes"]:
        raise ValueError("Camera plane axes do not match the projection.")
    for key, value in regenerated.items():
        if key in ("axes", "measured", "truth"):
            continue
        actual = np.asarray(saved[key], dtype=float)
        expected = np.asarray(value, dtype=float)
        if actual.shape != expected.shape or not np.allclose(
            actual, expected, rtol=2e-10, atol=1e-8, equal_nan=True
        ):
            raise ValueError(f"3D camera replay differs in {key}.")
    for key in ("measured", "truth"):
        fit = regenerated[key]
        if saved[key]["available"] != fit["available"]:
            raise ValueError("Camera fit availability differs from independent reference.")
        if fit["available"]:
            if not all(np.isfinite(saved[key][k]) for k in ("phase", "spacing", "contrast")):
                raise ValueError("Nonfinite camera fit.")
            phase = abs(np.angle(np.exp(1j * (saved[key]["phase"] - fit["phase"]))))
            if (
                phase > 0.01
                or abs(saved[key]["spacing"] / fit["spacing"] - 1) > 0.005
                or abs(saved[key]["contrast"] - fit["contrast"]) > 0.01
            ):
                raise ValueError("Camera fit differs from independent reference.")
            curve = np.asarray(saved[key]["fit_profile"], dtype=float)
            if curve.shape != np.shape(fit["fit_profile"]) or not np.allclose(
                curve, fit["fit_profile"], rtol=1e-4, atol=1e-6
            ):
                raise ValueError("Camera fit curve differs from independent reference.")
            if not np.isclose(saved[key]["relative_rmse"], fit["relative_rmse"], atol=1e-5):
                raise ValueError("Camera fit residual differs from independent reference.")
        elif any(saved[key][k] is not None for k in ("phase", "spacing", "contrast")):
            raise ValueError("Unavailable camera fit must have null measurements.")
    return {
        "camera_verified": True,
        "frame_tolerance": 1e-8,
        "independent_fits": {key: regenerated[key] for key in ("measured", "truth")},
    }
