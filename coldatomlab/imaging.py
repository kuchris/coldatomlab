"""Ideal Rb-87 absorption camera, independent of GPE evolution. See docs/IMAGING.md."""

import math
from dataclasses import asdict, dataclass

import numpy as np

from .physical import H
from .protocol import fringe_metrics

WAVELENGTH_UM = 0.780241209
SIGMA_UM2 = 3 * WAVELENGTH_UM**2 / (2 * math.pi)
ISAT_W_M2 = 16.69


@dataclass(frozen=True)
class Camera:
    binning: int = 2
    fwhm_um: float = 1.5
    saturation: float = 0.1
    exposure_us: float = 5.0
    efficiency: float = 0.8
    read_noise: float = 0.0
    noise: bool = True
    seed: int = 17
    roi_um: float = 20.0
    strip_um: float = 4.0

    def __post_init__(self):
        if type(self.binning) is not int or self.binning not in (1, 2, 4, 8, 16):
            raise ValueError("Camera binning must be 1, 2, 4, 8 or 16 solver cells.")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("Noise seed must be an integer from 0 to 4294967295.")
        if type(self.noise) is not bool:
            raise ValueError("Noise must be true or false.")
        for name, low, high in (
            ("fwhm_um", 0, 20),
            ("saturation", 0.001, 10),
            ("exposure_us", 0.1, 100),
            ("efficiency", 0.05, 1),
            ("read_noise", 0, 20),
            ("roi_um", 1, 100),
            ("strip_um", 0.2, 20),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be between {low} and {high}.")


def transmission(od, saturation):
    """Solve u + s(1-exp(-u)) = OD in log-transmission u without log(0)."""
    low = np.maximum(0, od - saturation)
    high = od.copy()
    for _ in range(52):
        middle = (low + high) / 2
        below = middle + saturation * (-np.expm1(-middle)) < od
        low = np.where(below, middle, low)
        high = np.where(below, high, middle)
    return np.exp(-(low + high) / 2)


def blur_transmission(t, sigma_cells):
    if sigma_cells < 1e-8:
        return t.copy()
    radius = max(1, math.ceil(6 * sigma_cells))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (x / sigma_cells) ** 2)
    kernel /= kernel.sum()
    deficit = 1 - t
    # Zero-padded absorption deficit means transparent space beyond the field.
    for axis in (0, 1):
        deficit = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="full")[radius : radius + len(row)],
            axis,
            deficit,
        )
    return np.clip(1 - deficit, 0, 1)


def bin_mean(a, b):
    n = len(a) // b
    return a.reshape(n, b, n, b).mean(axis=(1, 3))


def moments(density, x, mask, area):
    mass = density * mask * area
    total = float(mass.sum())
    empty = {"atoms": total, "width_x": None, "width_y": None}
    if total <= 0:
        return empty
    xx, yy = np.meshgrid(x, x)
    mx, my = (mass * xx).sum() / total, (mass * yy).sum() / total
    vx, vy = (
        float((mass * (xx - mx) ** 2).sum() / total),
        float((mass * (yy - my) ** 2).sum() / total),
    )
    return {
        "atoms": total,
        "width_x": math.sqrt(vx) if vx > 0 else None,
        "width_y": math.sqrt(vy) if vy > 0 else None,
    }


def form_image(rho, x, physical, camera):
    if physical is None or physical.species != "Rb87":
        raise ValueError("Absorption imaging currently requires a prepared Rb-87 laboratory run.")
    n = len(x)
    b = camera.binning
    if n // b < 8:
        raise ValueError("Use at least 8 camera pixels per side.")
    u = physical.scales()
    x = np.asarray(x) * u["length_um"]
    dx = float(x[1] - x[0])
    pitch = dx * b
    centers = x.reshape(-1, b).mean(axis=1)
    selection = np.abs(centers) <= camera.roi_um
    strip = np.abs(centers) <= camera.strip_um / 2
    if selection.sum() < 4 or not strip.any():
        raise ValueError(
            "ROI needs at least four pixels per side and the profile strip at least one row."
        )
    fine_selection = np.repeat(selection, b)
    fine_strip = np.repeat(strip, b)
    roi = selection[:, None] & selection[None, :]
    fine_roi = fine_selection[:, None] & fine_selection[None, :]
    density = rho * physical.atoms / u["length_um"] ** 2
    od = SIGMA_UM2 * density
    t = transmission(od, camera.saturation)
    blurred = blur_transmission(t, camera.fwhm_um / (math.sqrt(8 * math.log(2)) * dx))
    sampled_t = bin_mean(blurred, b)
    photon_energy = H * 299792458 / (WAVELENGTH_UM * 1e-6)
    fluence = camera.saturation * ISAT_W_M2 * camera.exposure_us * 1e-6 / photon_energy * 1e-12
    reference_e = fluence * pitch**2 * camera.efficiency
    expected_atoms = reference_e * sampled_t
    expected_reference = np.full_like(expected_atoms, reference_e)
    rng = np.random.default_rng(camera.seed)

    def frame(mean):
        return (
            rng.poisson(mean).astype(float) + rng.normal(0, camera.read_noise, mean.shape)
            if camera.noise
            else mean.copy()
        ) + 100.0

    atoms_frame, reference_frame = frame(expected_atoms), frame(expected_reference)
    dark_frame = (
        rng.normal(0, camera.read_noise, expected_atoms.shape)
        if camera.noise
        else np.zeros_like(expected_atoms)
    ) + 100.0
    a, r = atoms_frame - dark_frame, reference_frame - dark_frame
    valid = (a > 0) & (r > 0)
    # Do not clip negative reconstructed density: that would bias number estimates upward.
    recovered_od = np.zeros_like(a)
    recovered_od[valid] = (
        np.log(r[valid] / a[valid]) + camera.saturation * (r[valid] - a[valid]) / reference_e
    )
    recovered = recovered_od / SIGMA_UM2
    variance = np.zeros_like(a)
    if camera.noise:
        av, rv = a[valid], r[valid]
        ga, gr = -1 / av - camera.saturation / reference_e, 1 / rv + camera.saturation / reference_e
        gd = 1 / av - 1 / rv
        variance[valid] = (
            ga**2 * (av + camera.read_noise**2)
            + gr**2 * (rv + camera.read_noise**2)
            + gd**2 * camera.read_noise**2
        ) / SIGMA_UM2**2
    truth = moments(density, x, fine_roi, dx**2)
    measured = moments(recovered, centers, roi, pitch**2)
    error = float(np.sqrt(variance[roi].sum()) * pitch**2)
    invalid_roi = int((~valid & roi).sum())
    if invalid_roi:
        measured = dict.fromkeys(measured)
    snr = measured["atoms"] / error if measured["atoms"] is not None and error > 0 else None
    if camera.noise and (snr is None or snr < 5):
        measured["width_x"] = measured["width_y"] = None
    truth_profile = density[fine_strip].mean(axis=0)
    profile = recovered[strip].mean(axis=0)
    profile_error = np.sqrt(variance[strip].sum(axis=0)) / strip.sum()
    profile_valid = valid[strip].all(axis=0)
    truth_fringe = fringe_metrics(x[fine_selection], truth_profile[fine_selection])
    noisy_fringe = fringe_metrics(centers[selection], profile[selection])
    # A noisy profile must have a modulation signal above five estimated standard errors.
    resolved = bool(profile_valid[selection].all())
    if camera.noise:
        resolved &= np.ptp(profile[selection]) > 10 * float(np.max(profile_error[selection]))
    if not resolved:
        noisy_fringe = {"fringe_spacing": None, "fringe_contrast": None}
    truth.update(truth_fringe)
    measured.update(noisy_fringe)
    warnings = []
    if invalid_roi:
        warnings.append(
            "Nonpositive dark-subtracted counts in the ROI: number and width estimates are unavailable."
        )
    if camera.noise and (snr is None or snr < 5):
        warnings.append(
            "ROI number signal-to-noise is below 5 or unavailable; widths are not reported."
        )
    if noisy_fringe["fringe_spacing"] is None:
        warnings.append(
            "No reliably resolved camera fringes under the spacing, contrast and noise criteria."
        )
    scattered = float(fluence * (1 - t).sum() * dx**2 / physical.atoms)
    if scattered > 5:
        warnings.append(
            "More than 5 absorbed photons per atom on average: recoil/motion may matter but are not modeled."
        )
    if 0 < camera.fwhm_um < 2 * dx:
        warnings.append(
            "PSF FWHM spans fewer than two solver cells; refine the simulation grid for optical accuracy."
        )
    if truth["atoms"] < 0.99 * physical.atoms:
        warnings.append(
            "The selected ROI excludes more than 1% of the model atoms; compare ROI counts, not total N."
        )
    if np.max(od) > 4:
        warnings.append(
            "Peak model optical depth exceeds 4; dark pixels and omitted multiple-scattering effects limit interpretation."
        )

    def nullable(a, mask):
        return np.where(mask, a, None).tolist()

    return {
        "camera": asdict(camera),
        "pixel_um": pitch,
        "x_um": centers.tolist(),
        "model_x_um": x.tolist(),
        "truth_density": bin_mean(density, b).tolist(),
        "density": nullable(recovered, valid),
        "od": nullable(recovered_od, valid),
        "atoms_frame": atoms_frame.tolist(),
        "reference_frame": reference_frame.tolist(),
        "dark_frame": dark_frame.tolist(),
        "expected_atoms_e": expected_atoms.tolist(),
        "expected_reference_e": reference_e,
        "fluence_per_um2": fluence,
        "sigma_um2": SIGMA_UM2,
        "scattered_per_atom": scattered,
        "truth_profile": truth_profile.tolist(),
        "profile": nullable(profile, profile_valid),
        "profile_error": profile_error.tolist(),
        "truth": truth,
        "measured": measured,
        "atom_standard_error": error if not invalid_roi else None,
        "number_snr": snr,
        "invalid_roi_pixels": invalid_roi,
        "warnings": warnings,
        "roi_bounds_um": [
            float(centers[selection][0] - pitch / 2),
            float(centers[selection][-1] + pitch / 2),
        ],
        "strip_bounds_um": [
            float(centers[strip][0] - pitch / 2),
            float(centers[strip][-1] + pitch / 2),
        ],
        "model_total_atoms": float(density.sum() * dx**2),
    }


def capture(sim, config):
    return {
        "schema": "coldatomlab-camera-v1",
        "source": sim.export(),
        "image": form_image(abs(sim.psi) ** 2, sim.x, sim.config.physical, config),
    }
