"""Independent checks of automatic experiment timing and frozen acquisition."""

import math

from .vortex import scales, validate
from .vortex import verify_export as verify_source
from .vortex_imaging import verify_export as verify_image
from .vortex_paper import PaperVortex


def verify_export(data):
    if data.get("schema") != "coldatomlab-vortex-sequence-v1" or data.get("version") != "0.18.0":
        raise ValueError("Unsupported automatic vortex experiment.")
    source = data["source"]
    c = validate(source["config"])
    p = data["protocol"]
    t0 = scales(c)["time_ms"]
    hold, tof = p["requested_hold_ms"], p["requested_tof_ms"]
    if not (
        math.isfinite(hold)
        and 0 <= hold <= 16 * t0
        and math.isfinite(tof)
        and 0.1 * t0 <= tof <= 6 * t0
    ):
        raise ValueError("Invalid sequence durations.")
    step_ms = t0 * c["dt"]
    hs, ts = math.floor(hold / step_ms + 0.5), math.floor(tof / step_ms + 0.5)
    if (
        p["hold_steps"] != hs
        or p["tof_steps"] != ts
        or not math.isclose(p["step_ms"], step_ms, rel_tol=1e-12)
    ):
        raise ValueError("Rounded sequence times do not match.")
    if not math.isclose(c["duration"], max(0.1, hold / t0), rel_tol=1e-12) or not math.isclose(
        c["tof_duration"], tof / t0, rel_tol=1e-12
    ):
        raise ValueError("Source durations do not match the requested sequence.")
    release = source.get("release_step")
    if release is not None and release != hs:
        raise ValueError("Source released at the wrong step.")
    if source["steps"] > (hs if release is None else hs + ts):
        raise ValueError("Source passed its declared sequence stage.")
    if data["status"] == "complete":
        if release != hs or source["steps"] != hs + ts or source.get("warning"):
            raise ValueError("Sequence did not reach a valid endpoint.")
        image = data["image"]
        if "source" in image and image["source"] != source:
            raise ValueError("Image does not belong to the sequence endpoint.")
        result = verify_image(dict(image, source=source))
    elif data["status"] == "stopped" and data.get("image") is None:
        result = verify_source(source)
    else:
        raise ValueError("Invalid automatic experiment status or acquisition.")
    reference = data.get("reference")
    eligible = (
        c["stationary"] and c["charge"] and c["height"] == 0 and c["axial_hz"] == c["radial_hz"]
    )
    if data["status"] == "complete" and eligible and reference is None:
        raise ValueError("Missing paper model comparison.")
    if reference is not None:
        if (
            not eligible
            or reference.get("coupling") != c["g"] / (4 * math.pi)
            or reference.get("cells") != 512
            or reference.get("radius") != 24
            or reference.get("dt") != 0.002
        ):
            raise ValueError("Paper reference conditions do not match.")
        sim = PaperVortex(c["g"] / (4 * math.pi), cells=512)
        rows = [sim.diagnostics()]
        for _ in range(10):
            sim.advance(100)
            rows.append(sim.diagnostics())
        if len(reference["rows"]) != len(rows):
            raise ValueError("Incomplete paper reference.")
        for saved, expected in zip(reference["rows"], rows):
            for key, value in expected.items():
                if not math.isclose(saved[key], value, rel_tol=1e-7, abs_tol=1e-8):
                    raise ValueError(f"Paper reference replay differs in {key}.")
        for key in ("radial_mu", "radial_residual", "iterate_change"):
            if not math.isclose(
                reference["preparation"][key], sim.preparation[key], rel_tol=1e-6, abs_tol=1e-8
            ):
                raise ValueError("Paper reference preparation differs.")
    return dict(
        verified=True,
        protocol=p,
        status=data["status"],
        result=result,
        paper_reference_verified=reference is not None,
    )
