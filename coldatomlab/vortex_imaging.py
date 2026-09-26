"""Independent vortex-image projection, dip measurement and acquisition replay."""

import math

import numpy as np
from scipy.ndimage import uniform_filter

from .camera3d import acquire_projection, verify_image
from .vortex import validate
from .vortex import verify_export as verify_source


def core(density, x, roi, variance=None):
    def no(reason):
        return dict(
            available=False,
            reason=reason,
            x_um=None,
            y_um=None,
            contrast=None,
            diameter_um=None,
            depth_snr=None,
            radius_um=[],
            radial_density=[],
        )

    a = np.asarray(density, dtype=float)
    x = np.asarray(x, dtype=float)
    pitch = x[1] - x[0]
    indices = np.flatnonzero(abs(x) <= roi)
    if len(indices) < 9:
        return no("Need at least nine pixels across the ROI.")
    xx, yy = np.meshgrid(x, x)
    mask = (abs(xx) <= roi) & (abs(yy) <= roi)
    if not np.isfinite(a[mask]).all():
        return no("Invalid pixels in the core ROI.")
    weights = np.where(mask, np.maximum(a, 0), 0)
    total = weights.sum()
    if total <= 0:
        return no("No positive image signal.")
    cx = (xx * weights).sum() / total
    cy = (yy * weights).sum() / total
    rms = math.sqrt((((xx - cx) ** 2 + (yy - cy) ** 2) * weights).sum() / total)
    if rms < 3 * pitch:
        return no("Cloud is too small to resolve a core.")
    smooth = uniform_filter(np.nan_to_num(a, nan=0), size=3, mode="constant")
    search = mask & (np.hypot(xx - cx, yy - cy) <= 0.35 * rms)
    search[:2, :] = search[-2:, :] = False
    search[:, :2] = search[:, -2:] = False
    if not search.any():
        return no("No resolved central search window.")
    # Finite support in every candidate's 3x3 averaging window.
    finite = uniform_filter(np.isfinite(a).astype(float), size=3, mode="constant") > 1 - 1e-12
    search &= finite
    if not search.any():
        return no("No resolved central search window.")
    j, i = np.unravel_index(np.argmin(np.where(search, smooth, np.inf)), a.shape)
    value = float(smooth[j, i])
    curvature_x = smooth[j, i - 1] + smooth[j, i + 1] - 2 * value
    curvature_y = smooth[j - 1, i] + smooth[j + 1, i] - 2 * value
    if curvature_x <= 0 or curvature_y <= 0:
        return no("No local density minimum in both image directions.")
    px = x[i] + pitch * np.clip(
        (smooth[j, i - 1] - smooth[j, i + 1]) / (2 * curvature_x), -0.5, 0.5
    )
    py = x[j] + pitch * np.clip(
        (smooth[j - 1, i] - smooth[j + 1, i]) / (2 * curvature_y), -0.5, 0.5
    )
    bins = math.floor(min(roi - abs(px), roi - abs(py), 1.2 * rms) / pitch)
    if bins < 4:
        return no("Core search lies too close to the ROI edge.")
    which = np.floor(np.hypot(xx - px, yy - py) / pitch).astype(int)
    selection = mask & (which < bins)
    counts = np.bincount(which[selection], minlength=bins)
    sums = np.bincount(which[selection], weights=a[selection], minlength=bins)
    v = np.zeros_like(a) if variance is None else np.asarray(variance, dtype=float)
    vsums = np.bincount(which[selection], weights=v[selection], minlength=bins)
    radial = np.divide(sums, counts, out=np.full(bins, np.nan), where=counts > 0)
    radii = (np.arange(bins) + 0.5) * pitch
    peak = 1 + int(np.nanargmax(radial[1:]))
    if radial[peak] <= 0 or peak < 2:
        return no("No resolved surrounding density ring.")
    depth = radial[peak] - value
    contrast = depth / radial[peak]
    error = math.sqrt(v[j - 1 : j + 2, i - 1 : i + 2].sum() / 81 + vsums[peak] / counts[peak] ** 2)
    snr = depth / error if error > 0 else None
    if contrast < 0.1 or depth <= 0:
        return no("Density dip contrast is below 0.1.")
    if error > 0 and snr < 5:
        return no("Density dip depth has signal-to-noise below 5.")
    halfway = value + depth / 2
    radius = None
    for b in range(1, peak + 1):
        if radial[b - 1] <= halfway <= radial[b]:
            radius = radii[b - 1] + pitch * (halfway - radial[b - 1]) / (radial[b] - radial[b - 1])
            break
    if radius is None or radius < pitch:
        return no("Half-depth diameter is unresolved by the pixels.")
    return dict(
        available=True,
        reason="",
        x_um=float(px),
        y_um=float(py),
        contrast=float(contrast),
        diameter_um=float(2 * radius),
        depth_snr=None if snr is None else float(snr),
        radius_um=radii.tolist(),
        radial_density=[float(v) if np.isfinite(v) else None for v in radial],
    )


def acquire(source, settings):
    c = validate(source["config"])
    n = c["n"]
    raw = np.asarray(source["field"], dtype=float)
    if raw.shape != (2 * n**3,) or not np.isfinite(raw).all():
        raise ValueError("Invalid source field.")
    density = (raw[::2] ** 2 + raw[1::2] ** 2).reshape((n, n, n))
    directions = {"z": (2, ["x", "y"]), "y": (1, ["x", "z"]), "x": (0, ["y", "z"])}
    if settings["axis"] not in directions:
        raise ValueError("Invalid view axis.")
    axis, axes = directions[settings["axis"]]
    a = source["scales"]["length_um"]
    dx = c["length"] / n
    column = density.sum(axis=axis).T * dx * c["atoms"] / a**2
    x = (np.arange(n) - n / 2) * dx * a
    image = acquire_projection(column, x, axes, settings, c["atoms"], fit_fringes=False)
    eligible = settings["axis"] == "z" and abs(c["charge"]) == 1 and c["height"] == 0
    unavailable = dict(
        available=False,
        reason="Single axial core measurement requires an unstirred charge ±1 state viewed along z.",
        x_um=None,
        y_um=None,
        contrast=None,
        diameter_um=None,
        depth_snr=None,
        radius_um=[],
        radial_density=[],
    )
    measurements = {
        "model": core(image["truth_density"], image["x_um"], settings["roi_um"])
        if eligible
        else unavailable.copy(),
        "camera": core(
            image["density"], image["x_um"], settings["roi_um"], image["density_variance"]
        )
        if eligible
        else unavailable.copy(),
    }
    return image, measurements


def verify_export(data):
    if (
        data.get("schema") != "coldatomlab-vortex-image-v1"
        or data.get("version") != "0.17.0"
        or data.get("camera_model") != "rb87-browser-camera-v1"
    ):
        raise ValueError("Unsupported vortex image export.")
    source = verify_source(data["source"])
    image, measurements = acquire(data["source"], data["image"]["camera"])
    verified = verify_image(data["image"], image)
    for name, expected in measurements.items():
        saved = data["measurements"][name]
        if saved["available"] != expected["available"]:
            raise ValueError("Core availability differs.")
        for key in expected:
            if key in ("reason", "available"):
                continue
            actual = np.asarray(saved[key], dtype=float)
            target = np.asarray(expected[key], dtype=float)
            if actual.shape != target.shape or not np.allclose(
                actual, target, atol=1e-8, rtol=1e-8, equal_nan=True
            ):
                raise ValueError(f"Core measurement differs: {name}.{key}")
    return dict(verified=True, source=source, camera=verified, measurements=measurements)
