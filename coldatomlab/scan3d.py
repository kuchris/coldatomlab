"""Independent compact scan verification: evolved projections, camera frames, circular statistics."""

import math
from dataclasses import asdict

import numpy as np

from .camera3d import acquire_projection, validate_camera, verify_image
from .interferometry3d import stages
from .solver3d import Config3D, Solver3D


def wrap(value):
    return math.atan2(math.sin(value), math.cos(value))


def statistics(images):
    fits = [v["measured"] for v in images if v["measured"]["available"]]
    count = len(fits)
    result = dict(
        attempted=len(images),
        valid=count,
        failed=len(images) - count,
        failure_fraction=(len(images) - count) / len(images) if images else None,
        mean_phase=None,
        phase_sd=None,
        resultant=None,
        mean_period=None,
        mean_contrast=None,
    )
    if not count:
        return result
    c = sum(math.cos(v["phase"]) for v in fits) / count
    s = sum(math.sin(v["phase"]) for v in fits) / count
    r = min(1, math.hypot(c, s))
    result["resultant"] = r
    if r >= 0.1:
        result["mean_phase"] = math.atan2(s, c)
        if count >= 2:
            result["phase_sd"] = math.sqrt(max(0, -2 * math.log(r)))
    result["mean_period"] = sum(v["spacing"] for v in fits) / count
    result["mean_contrast"] = sum(v["contrast"] for v in fits) / count
    return result


def guide(mode, config):
    return wrap(
        config["relative_phase"]
        if mode == "phase"
        else -config["hold_bias"]
        * math.floor(config["hold_time"] / config["dt"] + 0.5)
        * config["dt"]
    )


def protocol(c):
    split = math.floor(c.split_time / c.dt + 0.5) if c.experiment == "sequence" else 0
    hold = math.floor(c.hold_time / c.dt + 0.5) if c.experiment == "sequence" else 0
    expansion = math.floor(c.duration / c.dt + 0.5)
    ms = c.scales["time_ms"]
    return dict(
        split_steps=split,
        hold_steps=hold,
        expansion_steps=expansion,
        hold_ms=hold * c.dt * ms,
        end_ms=(split + hold + expansion) * c.dt * ms,
    )


def summary(record, mode):
    values = statistics(record["shots"])
    truth = record["ideal"]["measured"]
    g = guide(mode, record["source"]["config"])
    return values | dict(
        guide=g,
        ideal_phase=truth["phase"],
        ideal_period=truth["spacing"],
        ideal_contrast=truth["contrast"],
        camera_minus_ideal=None
        if values["mean_phase"] is None or truth["phase"] is None
        else wrap(values["mean_phase"] - truth["phase"]),
        ideal_minus_guide=None if truth["phase"] is None else wrap(truth["phase"] - g),
    )


def refinement(records):
    result = []
    for coarse in records:
        if coarse["grid"] != 64 or coarse["status"] != "complete":
            continue
        fine = next(
            (
                r
                for r in records
                if r["point"] == coarse["point"] and r["grid"] == 128 and r["status"] == "complete"
            ),
            None,
        )
        if fine is None:
            continue
        a, b = coarse["source"]["diagnostics"], fine["source"]["diagnostics"]
        pa, pb = coarse["ideal"]["measured"], fine["ideal"]["measured"]
        result.append(
            dict(
                point=coarse["point"],
                value=coarse["value"],
                width_relative=[y / x - 1 for x, y in zip(a["widths"], b["widths"])],
                norm_difference=b["norm"] - a["norm"],
                ideal_phase_difference=wrap(pb["phase"] - pa["phase"])
                if pa["available"] and pb["available"]
                else None,
            )
        )
    return result


def compare(saved, expected, path="value"):
    """Reject missing/nonfinite data, including forged null statistics."""
    if isinstance(expected, dict):
        if not isinstance(saved, dict) or saved.keys() != expected.keys():
            raise ValueError(f"Scan {path} keys differ.")
        for key, value in expected.items():
            compare(saved[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(saved, list) or len(saved) != len(expected):
            raise ValueError(f"Scan {path} size differs.")
        for a, b in zip(saved, expected):
            compare(a, b, path)
    elif expected is None or isinstance(expected, (str, bool)):
        if saved != expected:
            raise ValueError(f"Scan {path} differs.")
    elif (
        not isinstance(saved, (int, float))
        or isinstance(saved, bool)
        or not math.isfinite(saved)
        or not math.isclose(saved, expected, rel_tol=2e-10, abs_tol=1e-7)
    ):
        raise ValueError(f"Scan {path} differs.")


def jobs(plan):
    mode = plan["mode"]
    if mode not in ("phase", "hold", "bias"):
        raise ValueError("Unknown scan protocol.")
    points, repeats, refine = plan["points"], plan["repeats"], plan["refine"]
    if (
        type(points) is not int
        or not 2 <= points <= 9
        or type(repeats) is not int
        or not 1 <= repeats <= 20
        or type(refine) is not bool
        or points * repeats * (2 if refine else 1) > 80
    ):
        raise ValueError("Invalid scan workload.")
    lo, hi = {"phase": (-math.pi, math.pi), "hold": (0, 3), "bias": (-5, 5)}[mode]
    if (
        not all(type(plan[k]) in (float, int) and math.isfinite(plan[k]) for k in ("start", "end"))
        or not lo <= plan["start"] < plan["end"] <= hi
    ):
        raise ValueError("Invalid scan range.")
    base = Config3D(**plan["base"])
    if (
        base.n != 64
        or base.experiment != ("pair" if mode == "phase" else "sequence")
        or asdict(base) != plan["base"]
    ):
        raise ValueError("Invalid scan base recipe.")
    key = {"phase": "relative_phase", "hold": "hold_time", "bias": "hold_bias"}[mode]
    result = []
    for point in range(points):
        value = plan["start"] + (plan["end"] - plan["start"]) * point / (points - 1)
        for n in [64, 128] if refine else [64]:
            c = Config3D(**(plan["base"] | {key: value, "n": n}))
            validate_camera(plan["camera"], n)
            result.append(dict(point=point, value=value, grid=n, config=asdict(c)))
    return result


def verify_scan(data):
    if (
        data.get("schema") != "coldatomlab-scan3d-v1"
        or data.get("camera_model") != "rb87-browser-camera-v1"
    ):
        raise ValueError("Unknown scan schema/camera model.")
    plan = data["plan"]
    expected_jobs = jobs(plan)
    records = data["records"]
    if (
        data["status"] not in ("complete", "cancelled", "failed")
        or len(records) > len(expected_jobs)
        or (data["status"] == "complete" and len(records) != len(expected_jobs))
    ):
        raise ValueError("Scan completion status/count differs.")
    evidence = []
    for record, job in zip(records, expected_jobs):
        compare(
            {k: record[k] for k in ("point", "value", "grid")},
            {k: job[k] for k in ("point", "value", "grid")},
            "job",
        )
        if record["status"] == "failed":
            if not isinstance(record.get("reason"), str) or not record["reason"]:
                raise ValueError("Stopped scan point needs a reason.")
            # A stopped run has no saved projection: its failure claim cannot be verified.
            evidence.append(dict(point=job["point"], grid=job["grid"], status="unverified_stop"))
            continue
        if record["status"] != "complete":
            raise ValueError("Invalid scan point status.")
        source = record["source"]
        compare(source["config"], job["config"], "source.config")
        c = Config3D(**job["config"])
        end = math.floor(c.duration / c.dt + 0.5) if c.experiment == "pair" else stages(c)[2]
        release = 0 if c.experiment == "pair" else stages(c)[1]
        if source["steps"] != end or source["release_step"] != release:
            raise ValueError("Scan source did not complete the declared protocol.")
        if (
            source["backend"].get("type") != "webgpu"
            or source["backend"].get("precision") != "complex-f32"
        ):
            raise ValueError("Scan source must declare WebGPU float32.")
        compare(source["scales"], c.scales, "source.scales")
        compare(source["protocol"], protocol(c), "source.protocol")
        sim = Solver3D(c)
        while not sim.complete and not sim.warning:
            sim.advance(20)
        if sim.steps != end or sim.warning:
            raise ValueError("CPU reference stopped before the scan endpoint.")
        compare(source["x"], sim.x.tolist(), "source.x")
        snapshot = sim.snapshot()
        columns = np.asarray(source["columns"], dtype=float)
        if columns.shape != (3, c.n, c.n) or not np.isfinite(columns).all() or (columns < 0).any():
            raise ValueError("Invalid scan projections.")
        oracle = np.asarray(snapshot["columns"])
        differences = [
            float(np.linalg.norm(a - b) / np.linalg.norm(b)) for a, b in zip(columns, oracle)
        ]
        diag = source["diagnostics"]
        dx = c.length / c.n
        norm = float(columns[0].sum() * dx**2)
        if not np.allclose(columns.sum(axis=(1, 2)) * dx**2, norm, rtol=1e-10, atol=1e-10):
            raise ValueError("Projection normalizations disagree.")
        # Moments from projections independently certify the saved widths.
        marginals = [columns[0].sum(axis=0), columns[0].sum(axis=1), columns[1].sum(axis=1)]
        widths = []
        for marginal in marginals:
            marginal = marginal / marginal.sum()
            mean = np.dot(marginal, sim.x)
            widths.append(float(np.sqrt(np.dot(marginal, (sim.x - mean) ** 2))))
        compare(
            diag, dict(norm=norm, widths=widths, steps=end, time=end * c.dt), "source.diagnostics"
        )
        width_error = np.asarray(widths) / snapshot["diagnostics"]["widths"] - 1
        if max(differences) > 0.005 or max(abs(width_error)) > 0.005 or abs(norm - 1) > 0.001:
            raise ValueError("Scan source exceeds CPU projection/width/norm tolerances.")
        axis = {"z": (0, ["x", "y"]), "y": (1, ["x", "z"]), "x": (2, ["y", "z"])}[
            plan["camera"]["axis"]
        ]
        density = columns[axis[0]] * c.atoms / c.scales["length_um"] ** 2
        coords = sim.x * c.scales["length_um"]
        images = [record["ideal"], *record["shots"]]
        if len(record["shots"]) != plan["repeats"]:
            raise ValueError("Scan exposure count differs.")
        for i, image in enumerate(images):
            camera = plan["camera"] | (
                dict(noise=False, binning=1, fwhm_um=0)
                if i == 0
                else dict(
                    seed=(plan["camera"]["seed"] + job["point"] * plan["repeats"] + i - 1) % (2**32)
                )
            )
            compare(image["camera"], camera, "camera recipe")
            regenerated = acquire_projection(density, coords, axis[1], camera, c.atoms)
            verify_image(image, regenerated)
        compare(record["summary"], summary(record, plan["mode"]), "summary")
        evidence.append(
            dict(
                point=job["point"],
                grid=c.n,
                status="verified",
                projection_relative_l2=differences,
                width_relative_difference=width_error.tolist(),
                images_verified=len(images),
            )
        )
    compare(data["refinement"], refinement(records), "refinement")
    return dict(
        scan_verified=True,
        scope="Saved complete projections, camera frames and statistics; no full GPU complex field or stopped-run verification.",
        status=data["status"],
        records=evidence,
        tolerances=dict(projection_relative_l2=0.005, width_relative=0.005, norm_drift=0.001),
    )
