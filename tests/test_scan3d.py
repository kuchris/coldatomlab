import copy
import json
import math
import subprocess
from dataclasses import asdict

import numpy as np
import pytest

from coldatomlab.camera3d import acquire_projection
from coldatomlab.scan3d import jobs, protocol, refinement, statistics, summary, verify_scan
from coldatomlab.solver3d import Config3D, Solver3D


def javascript(code, data=None):
    prelude = "global.window=global;require('./coldatomlab/web/interferometry3d.js');require('./coldatomlab/web/gpu3d.js');require('./coldatomlab/web/camera3d.js');require('./coldatomlab/web/scan3d.js');const data=JSON.parse(require('fs').readFileSync(0,'utf8'));"
    result = subprocess.run(
        ["node", "-e", prelude + code],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def images(phases):
    return [
        dict(measured=dict(available=p is not None, phase=p, spacing=5, contrast=0.7))
        for p in phases
    ]


@pytest.mark.parametrize(
    "phases",
    [[math.pi - 0.02, -math.pi + 0.02, None], [None, None], [0, math.pi], [0.3], [0.3, 0.3]],
)
def test_circular_statistics_match_browser(phases):
    obs = images(phases)
    result = statistics(obs)
    browser = javascript("console.log(JSON.stringify(Scan3D.statistics(data)))", obs)
    for key, value in result.items():
        if value is None:
            assert browser[key] is None
        else:
            assert browser[key] == pytest.approx(value, abs=2e-8)
    if phases[0] == math.pi - 0.02:
        assert abs(abs(result["mean_phase"]) - math.pi) < 1e-12
        assert result["phase_sd"] == pytest.approx(0.02, abs=1e-5)
        assert result["failure_fraction"] == pytest.approx(1 / 3)


@pytest.fixture
def report():
    c = Config3D(
        n=64, length=32, atoms=2000, scattering_nm=0, experiment="pair", dt=0.01, duration=0.1
    )
    camera = dict(
        axis="z",
        binning=1,
        fwhm_um=0,
        saturation=10,
        exposure_us=5,
        efficiency=0.8,
        read_noise=1,
        noise=True,
        seed=17,
        roi_um=12,
        strip_um=4,
    )
    plan = dict(
        mode="phase",
        base=asdict(c),
        start=-0.5,
        end=0.5,
        points=2,
        repeats=2,
        refine=False,
        camera=camera,
    )
    records = []
    for job in jobs(plan):
        sim = Solver3D(Config3D(**job["config"]))
        while not sim.complete:
            sim.advance(20)
        snap = sim.snapshot()
        diag = snap["diagnostics"]
        source = dict(
            config=job["config"],
            steps=sim.steps,
            release_step=sim.release_step,
            scales=snap["scales"],
            x=snap["x"],
            columns=snap["columns"],
            diagnostics={k: diag[k] for k in ("norm", "widths", "time", "steps")},
            backend=dict(type="webgpu", precision="complex-f32"),
            protocol=protocol(sim.config),
        )
        density = np.asarray(snap["columns"][0]) * c.atoms / c.scales["length_um"] ** 2
        coords = sim.x * c.scales["length_um"]

        def capture(settings):
            return acquire_projection(density, coords, ["x", "y"], settings, c.atoms) | dict(
                camera=settings
            )

        record = {k: job[k] for k in ("point", "value", "grid")}
        record.update(
            status="complete",
            source=source,
            ideal=capture(camera | dict(noise=False, fwhm_um=0, binning=1)),
            shots=[capture(camera | dict(seed=17 + job["point"] * 2 + i)) for i in range(2)],
        )
        record["summary"] = summary(record, "phase")
        records.append(record)
    data = dict(
        schema="coldatomlab-scan3d-v1",
        camera_model="rb87-browser-camera-v1",
        plan=plan,
        status="complete",
        records=records,
        refinement=[],
    )

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return None if isinstance(value, float) and not math.isfinite(value) else value

    return clean(json.loads(json.dumps(data, default=lambda v: v.tolist())))


def test_projection_and_camera_replay(report):
    assert verify_scan(report)["scan_verified"]
    browser = javascript(
        "console.log(JSON.stringify(data.records.map(r=>Scan3D.summary(r,'phase'))))", report
    )
    for actual, record in zip(browser, report["records"]):
        assert actual == record["summary"]


@pytest.mark.parametrize(
    "tamper", ["frame", "seed", "summary", "projection", "recipe", "missing", "nonfinite"]
)
def test_scan_tampering_rejected(report, tamper):
    r = report["records"][0]
    if tamper == "frame":
        r["shots"][0]["atoms_frame"][0][0] += 1
    if tamper == "seed":
        r["shots"][0]["camera"]["seed"] += 1
    if tamper == "summary":
        r["summary"]["valid"] += 1
    if tamper == "projection":
        r["source"]["columns"][0][20][20] += 0.01
    if tamper == "recipe":
        r["source"]["config"]["relative_phase"] += 0.01
    if tamper == "missing":
        report["records"].pop()
    if tamper == "nonfinite":
        r["summary"]["mean_phase"] = float("nan")
    with pytest.raises(ValueError):
        verify_scan(report)


def test_partial_recipe_and_refinement(report):
    report["status"] = "cancelled"
    report["records"].pop()
    assert verify_scan(report)["status"] == "cancelled"
    a = report["records"][0]
    b = copy.deepcopy(a)
    b["grid"] = 128
    b["source"]["diagnostics"]["widths"][0] *= 1.01
    delta = refinement([a, b])
    assert delta[0]["width_relative"][0] == pytest.approx(0.01)
    js = javascript("console.log(JSON.stringify(Scan3D.refinement(data)))", [a, b])
    assert js == delta


def test_recipe_validation_and_scan_resource_cleanup(report):
    plan = report["plan"]
    assert javascript(
        "console.log(JSON.stringify(Scan3D.jobs(Scan3D.validate(data))))", plan
    ) == jobs(plan)
    plan["points"] = 9
    plan["repeats"] = 20
    with pytest.raises(ValueError):
        jobs(plan)
    assert javascript("try{Scan3D.validate(data);console.log(false)}catch{console.log(true)}", plan)
    plan["points"] = 2
    plan["repeats"] = 1
    code = """(async()=>{let destroyed=0,advanced=0;let runner;
      const factory=async()=>({complete:false,steps:0,advance:async function(){advanced++;runner.cancelled=true},destroy:()=>destroyed++});
      runner=new Scan3DRunner(data,()=>{},factory);const r=await runner.run();
      console.log(JSON.stringify({status:r.status,destroyed,advanced,records:r.records.length}));})();"""
    assert javascript(code, plan) == dict(status="cancelled", destroyed=1, advanced=1, records=0)
