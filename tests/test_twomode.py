import copy
import json
import subprocess

import numpy as np
import pytest

from coldatomlab.replay import verify_export
from coldatomlab.twomode import HISTORY_KEYS, Reference, hamiltonian, sample, validate


def js(code, data=None):
    result = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "const data=JSON.parse(require('fs').readFileSync(0,'utf8'));" + code,
        ],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def field(state):
    return np.array(state["real"]) + 1j * np.array(state["imag"])


@pytest.mark.parametrize(
    "config",
    [
        {},
        dict(atoms=2, left_fraction=0.5, phase=1.2),
        dict(atoms=41, initial="gaussian", sigma=0.25, left_fraction=0.5),
        dict(initial="fock", left_fraction=0.5),
        dict(tunnelling_hz=0, interaction_hz=1, left_fraction=0.5, duration_ms=1000),
        dict(
            atoms=100,
            tunnelling_hz=20,
            interaction_hz=2,
            bias_hz=-20,
            left_fraction=0.7,
            phase=-2.9,
            duration_ms=1000,
        ),
        dict(atoms=100, tunnelling_hz=0, interaction_hz=0, bias_hz=0),
        dict(initial="gaussian", sigma=20, left_fraction=0, interaction_hz=0.8, bias_hz=5),
        dict(atoms=3, initial="fock", left_fraction=0.5, tunnelling_hz=0.1),
    ],
)
def test_browser_complex_state_against_independent_spectrum(config):
    result = js(
        "const s=new TwoMode.Solver(data);console.log(JSON.stringify({"
        "states:[0,.137,.5,1].map(f=>s.at(f*s.config.duration_ms)),"
        "residual:s.eigen.residual,orthogonality:s.eigen.orthogonality}));",
        config,
    )
    ref = Reference(config)
    energy0 = result["states"][0]["energy_hz"]
    for state in result["states"]:
        expected = ref.at(state["time_ms"])
        assert np.linalg.norm(field(state) - field(expected)) < 5e-8
        assert abs(state["norm"] - 1) < 1e-9
        assert abs(state["energy_hz"] - energy0) < 1e-8
        for key in ("coherence", "variance_left", "mean_left", "coherence_imag"):
            assert state[key] == pytest.approx(expected[key], abs=5e-8)
    assert result["residual"] < 1e-11
    assert result["orthogonality"] < 1e-11


def test_tunnelling_analytic_binomial_and_bias_frequency():
    for bias in (0, 3):
        c = dict(atoms=30, tunnelling_hz=5, bias_hz=bias, interaction_hz=0, left_fraction=1)
        states = js(
            "const s=new TwoMode.Solver(data);console.log(JSON.stringify([0,7,25,50,100].map(t=>s.at(t))))",
            c,
        )
        omega = np.hypot(5, bias / 2)
        for s in states:
            p = 1 - (5 / omega) ** 2 * np.sin(2 * np.pi * omega * s["time_ms"] / 1000) ** 2
            assert s["mean_left"] == pytest.approx(30 * p, abs=1e-10)
            assert s["variance_left"] == pytest.approx(30 * p * (1 - p), abs=1e-10)


def test_isolated_hold_frozen_number_distribution_collapse_revival_and_phase_sign():
    config = dict(
        atoms=40,
        left_fraction=0.5,
        tunnelling_hz=0,
        interaction_hz=1,
        bias_hz=0.7,
        phase=0.3,
        duration_ms=1000,
    )
    states = js(
        "const s=new TwoMode.Solver(data);console.log(JSON.stringify([0,13,50,250,500,1000].map(t=>s.at(t))))",
        config,
    )
    for s in states:
        t = s["time_ms"] / 1000
        expected_cross = np.exp(1j * (0.3 - 2 * np.pi * 0.7 * t)) * np.cos(2 * np.pi * t) ** 39
        assert s["probability"] == pytest.approx(states[0]["probability"], abs=1e-13)
        assert s["coherence_real"] == pytest.approx(expected_cross.real, abs=1e-12)
        assert s["coherence_imag"] == pytest.approx(expected_cross.imag, abs=1e-12)
    assert states[3]["phase"] is None
    assert states[-1]["coherence"] == pytest.approx(1)


def test_number_narrow_state_and_fixed_counts_do_not_imply_coherence():
    states = js(
        "console.log(JSON.stringify(['diffusion','narrow','fock'].map(k=>new TwoMode.Solver(TwoMode.presets[k]).at(0))))"
    )
    coherent, narrow, fock = states
    assert coherent["variance_left"] == pytest.approx(10)
    assert coherent["number_noise_ratio"] == pytest.approx(1)
    assert narrow["variance_left"] == pytest.approx(2.25, abs=1e-10)
    assert 0.9 < narrow["coherence"] < coherent["coherence"]
    assert fock["coherence"] == 0 and fock["phase"] is None
    assert fock["variance_left"] == 0
    pole = Reference({}).at(0)
    assert pole["number_noise_ratio"] is None


def test_time_subdivision_and_unit_convention():
    ref = Reference(dict(interaction_hz=0.8, bias_hz=2, left_fraction=0.6))
    h = hamiltonian(ref.config)
    assert h[20, 21] == pytest.approx(-5 * np.sqrt(21 * 20))
    assert h[19, 19] == pytest.approx(0.8 + 2)
    e, v = np.linalg.eigh(h)
    half = v @ (np.exp(-2j * np.pi * e * 0.025) * (v.T @ field(ref.at(25))))
    assert np.linalg.norm(half - field(ref.at(50))) < 1e-12
    # Browser direct evaluation is independent of intermediate display visits.
    error = js(
        "const s=new TwoMode.Solver(data),a=s.at(50);for(let t=0;t<50;t+=.3)s.at(t);const b=s.at(50);console.log(JSON.stringify(a.real.map((v,i)=>v-b.real[i])))",
        ref.config,
    )
    assert np.max(np.abs(error)) == 0


def test_seeded_measurements_reproduce_and_have_binomial_statistics():
    state = Reference(dict(left_fraction=0.5, tunnelling_hz=0)).at(0)
    browser = js("console.log(JSON.stringify(TwoMode.sample(data,10000,17)))", state)
    assert browser == sample(state, 10000, 17)
    counts = np.array(browser["counts"])
    mean = counts @ np.arange(41) / 10000
    variance = counts @ (np.arange(41) - mean) ** 2 / 10000
    assert abs(mean - 20) < 0.12
    assert abs(variance - 10) < 0.5
    assert sample(state, 10000, 18)["counts"] != browser["counts"]


@pytest.fixture
def exported():
    return js(
        """
      const s=new TwoMode.Solver({...TwoMode.presets.narrow,tunnelling_hz:2});
      const keys=data, history=[];
      for(let i=0;i<=20;i++){const st=s.at(s.config.duration_ms*i/200);history.push(Object.fromEntries(keys.map(k=>[k,st[k]])));}
      const state=s.at(s.config.duration_ms*20/200);
      const current={config:s.config,step:20,state,history,measurement:TwoMode.sample(state,1000,17)};
      console.log(JSON.stringify({schema:'coldatomlab-twomode-v1',version:'0.10.0',
        convention:'n_left=0..N; H/h in Hz; time_ms; right-minus-left phase',current,pinned:current}));
    """,
        HISTORY_KEYS,
    )


def test_export_replay(exported):
    result = verify_export(exported)
    assert result["current"]["verified"] and result["pinned"]["measurement_verified"]
    assert result["current"]["complex_state_l2"] < 1e-10


@pytest.mark.parametrize(
    "change",
    ["field", "probability", "history", "time", "seed", "counts", "config", "basis", "step", "nan"],
)
def test_replay_rejects_tampering(exported, change):
    data = copy.deepcopy(exported)
    r = data["current"]
    if change == "field":
        r["state"]["real"][20] += 0.01
    if change == "probability":
        r["state"]["probability"][20] += 0.01
    if change == "history":
        r["history"][1]["coherence"] += 0.1
    if change == "time":
        r["state"]["time_ms"] += 1
    if change == "seed":
        r["measurement"]["seed"] += 1
    if change == "counts":
        r["measurement"]["counts"][0] += 1
    if change == "config":
        r["config"]["bias_hz"] += 1
    if change == "basis":
        data["convention"] = "wrong"
    if change == "step":
        r["step"] = 2.1
    if change == "nan":
        r["state"]["coherence"] = float("nan")
    with pytest.raises(ValueError):
        verify_export(data)


@pytest.mark.parametrize(
    "bad",
    [
        dict(atoms=1),
        dict(atoms=2.5),
        dict(atoms=True),
        dict(bias_hz=21),
        dict(initial="other"),
        dict(tunnelling_hz=-1),
        dict(sigma=0),
        dict(duration_ms=0),
        dict(extra=2),
    ],
)
def test_invalid_config_rejected_in_both_engines(bad):
    with pytest.raises(ValueError):
        validate(bad)
    assert js(
        "let rejected=false;try{TwoMode.validate(data)}catch(e){rejected=true}console.log(JSON.stringify(rejected))",
        bad,
    )


@pytest.mark.parametrize("shots,seed", [(0, 17), (1.5, 17), (10001, 0), (10, -1), (10, 2**32)])
def test_invalid_measurement_rejected(shots, seed):
    with pytest.raises(ValueError):
        sample(Reference({}).at(0), shots, seed)
    assert js(
        "let ok=false;try{TwoMode.sample(new TwoMode.Solver({}).at(0),data[0],data[1])}catch(e){ok=true}console.log(JSON.stringify(ok))",
        [shots, seed],
    )
