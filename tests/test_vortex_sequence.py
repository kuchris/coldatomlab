"""Automatic protocol integrity and independently replayed stationary exports."""

import copy
import math

import numpy as np
import pytest

from coldatomlab.vortex import Vortex, scales
from coldatomlab.vortex_imaging import acquire
from coldatomlab.vortex_paper import PaperVortex
from coldatomlab.vortex_sequence import verify_export


@pytest.fixture(scope="module")
def sequence():
    s = Vortex(dict(n=32, width=1, stationary=1, axial_hz=50, duration=0.1, tof_duration=0.1))
    s.release()
    rows = [s.diagnostics()]
    s.advance(25)
    rows.append(s.diagnostics())

    def packed(field):
        return np.stack([field.real, field.imag], axis=-1).ravel().tolist()

    source = dict(
        schema="coldatomlab-vortex-v3",
        version="0.18.0",
        array_order="x,y,z interleaved real,imag",
        config=s.config,
        scales=scales(s.config),
        steps=s.steps,
        release_step=0,
        initial=packed(s.initial),
        field=packed(s.psi),
        history=rows,
        preparation=dict(prepared_state=s.preparation),
    )
    camera = dict(
        axis="z",
        binning=1,
        fwhm_um=0,
        saturation=1,
        exposure_us=5,
        efficiency=0.8,
        read_noise=1,
        noise=False,
        seed=17,
        roi_um=8,
        strip_um=4,
    )
    image, measurements = acquire(source, camera)
    image["camera"] = camera
    paper = PaperVortex(0, cells=512)
    reference_rows = [paper.diagnostics()]
    for _ in range(10):
        paper.advance(100)
        reference_rows.append(paper.diagnostics())
    return dict(
        schema="coldatomlab-vortex-sequence-v1",
        version="0.18.0",
        status="complete",
        source=source,
        protocol=dict(
            requested_hold_ms=0,
            requested_tof_ms=0.1 * scales(s.config)["time_ms"],
            hold_steps=0,
            tof_steps=25,
            step_ms=s.config["dt"] * scales(s.config)["time_ms"],
        ),
        image=dict(
            schema="coldatomlab-vortex-image-v1",
            version="0.17.0",
            camera_model="rb87-browser-camera-v1",
            image=image,
            measurements=measurements,
        ),
        reference=dict(
            coupling=0,
            cells=512,
            radius=24,
            dt=0.002,
            rows=reference_rows,
            preparation=paper.preparation,
        ),
    )


def test_automatic_stationary_replay(sequence):
    result = verify_export(sequence)
    assert result["verified"] and result["paper_reference_verified"]
    assert result["result"]["source"]["evolution_l2_error"] < 1e-12


@pytest.mark.parametrize(
    "kind",
    [
        "timing",
        "release",
        "endpoint",
        "status",
        "stopped_image",
        "missing_reference",
        "reference_coupling",
        "reference_curve",
        "mu",
        "residual",
        "core",
        "camera",
    ],
)
def test_sequence_tampering(sequence, kind):
    data = copy.deepcopy(sequence)
    if kind == "timing":
        data["protocol"]["tof_steps"] += 1
    elif kind == "release":
        data["source"]["release_step"] = 1
    elif kind == "endpoint":
        data["source"]["steps"] -= 1
    elif kind == "status":
        data["status"] = "almost"
    elif kind == "stopped_image":
        data["status"] = "stopped"
    elif kind == "missing_reference":
        data["reference"] = None
    elif kind == "reference_coupling":
        data["reference"]["coupling"] = 1
    elif kind == "reference_curve":
        data["reference"]["rows"][-1]["core_ratio"] += 0.01
    elif kind == "mu":
        data["source"]["preparation"]["prepared_state"]["chemical_potential"] += 0.1
    elif kind == "residual":
        data["source"]["preparation"]["prepared_state"]["relative_stationary_residual"] = math.nan
    elif kind == "core":
        data["source"]["history"][-1]["paper_core"]["core_radius"] += 0.1
    elif kind == "camera":
        data["image"]["image"]["atoms_frame"][16, 16] += 1
    with pytest.raises(ValueError):
        verify_export(data)


def test_stopped_source_without_endpoint_image(sequence):
    data = copy.deepcopy(sequence)
    data.update(status="stopped", image=None, reference=None)
    assert verify_export(data)["status"] == "stopped"
