import copy
import json
import math
import subprocess

import numpy as np
import pytest
from scipy.linalg import expm

from coldatomlab import pulse
from coldatomlab.preparation import recipes
from coldatomlab.replay import verify_export
from coldatomlab.twomode import hamiltonian, initial_state
from coldatomlab.twomode import validate as base_config


def plan(**kwargs):
    return (
        dict(
            base=base_config(dict(atoms=8, left_fraction=0.5, tunnelling_hz=0, duration_ms=500)),
            phase_half_range=0,
            bias_half_range_hz=2,
            preparations=2,
            seed=17,
            pulse_j_hz=10,
            duration_error=0.2,
        )
        | kwargs
    )


def js(code, data):
    p = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "require('./coldatomlab/web/preparation.js');require('./coldatomlab/web/echo.js');"
            "require('./coldatomlab/web/pulse.js');const data=JSON.parse(require('fs').readFileSync(0,'utf8'));"
            + code,
        ],
        input=json.dumps(data),
        text=True,
        encoding="utf8",
        capture_output=True,
        check=True,
    )
    return json.loads(p.stdout)


def report(p):
    return js(
        "const p=FinitePulse.validate(data),ref=FinitePulse.reference(p);console.log(JSON.stringify(FinitePulse.report(p,ref,Preparation.recipes(FinitePulse.ensemble(p)).map(r=>FinitePulse.evolve(p,r)),'complete')));",
        p,
    )


def field(state):
    return np.asarray(state["real"]) + 1j * np.asarray(state["imag"])


@pytest.mark.parametrize(
    "config",
    [
        {},
        dict(interaction_hz=0.3),
        dict(atoms=3, left_fraction=0.8, phase=2.9, bias_hz=-7),
        dict(initial="gaussian", sigma=0.5),
        dict(initial="fock", left_fraction=0.25),
        dict(atoms=100, interaction_hz=2, bias_hz=15, duration_ms=1000),
    ],
)
def test_independent_full_state_replay(config):
    p = plan(phase_half_range=0.7)
    p["base"].update(config)
    check = verify_export(report(p))
    assert check["maximum_complex_state_l2"] < 5e-8
    assert check["maximum_norm_drift"] < 1e-9


@pytest.mark.parametrize("atoms", [2, 3, 8])
def test_resonant_pi_global_phase_and_incomplete_exchange(atoms):
    p = plan(bias_half_range_hz=0)
    p["base"].update(atoms=atoms, left_fraction=1)
    r = report(p)["records"][0]
    target = field(r["arms"]["ideal"]["state"])
    assert field(r["arms"]["nominal"]["state"]) == pytest.approx((1j) ** atoms * target, abs=1e-12)
    for arm, w in pulse.windows(p).items():
        left = math.cos(math.pi * w["ratio"] / 2) ** 2
        out = r["arms"][arm]
        assert out["state"]["mean_left"] / atoms == pytest.approx(left, abs=1e-12)
        assert out["fidelity_to_ideal"] == pytest.approx((1 - left) ** atoms, abs=1e-12)
        for row in out["history"]:
            elapsed = max(0, min(w["width_ms"], row["time_ms"] - w["start_ms"])) / 1000
            assert row["mean_left"] / atoms == pytest.approx(
                math.cos(2 * math.pi * p["pulse_j_hz"] * elapsed) ** 2, abs=1e-12
            )


@pytest.mark.parametrize("bias,phase,pop", [(0, 0.3, 0.4), (3, -0.7, 0.8), (-12, 2.9, 1)])
def test_noninteracting_full_fields_against_single_particle_closed_form(bias, phase, pop):
    p = plan(bias_half_range_hz=0)
    p["base"].update(atoms=5, bias_hz=bias, phase=phase, left_fraction=pop)
    r = report(p)["records"][0]
    spinor = np.array([np.sqrt(pop), np.sqrt(1 - pop) * np.exp(1j * phase)])

    def evolve2(state, j, t):
        h = np.array([[-bias / 2, -j], [-j, bias / 2]])
        omega = np.hypot(j, bias / 2)
        if omega == 0:
            return state.copy()
        angle = 2 * np.pi * omega * t / 1000
        return (np.cos(angle) * np.eye(2) - 1j * np.sin(angle) * h / omega) @ state

    for arm, w in pulse.windows(p).items():
        v = evolve2(
            evolve2(evolve2(spinor, 0, w["start_ms"]), p["pulse_j_hz"], w["width_ms"]),
            0,
            p["base"]["duration_ms"] - w["end_ms"],
        )
        expected = np.array(
            [math.sqrt(math.comb(5, n)) * v[0] ** n * v[1] ** (5 - n) for n in range(6)]
        )
        assert np.linalg.norm(field(r["arms"][arm]["state"]) - expected) < 1e-11


def test_interactions_and_bias_remain_active_during_pulse():
    p = plan(bias_half_range_hz=0)
    p["base"].update(atoms=4, interaction_hz=1.2, bias_hz=2, left_fraction=0.7, phase=0.4)
    r = report(p)["records"][0]
    h = hamiltonian(p["base"])
    hp = hamiltonian(p["base"] | dict(tunnelling_hz=p["pulse_j_hz"]))
    initial = initial_state(p["base"])
    for arm, w in pulse.windows(p).items():
        before = expm(-2j * np.pi * h * w["start_ms"] / 1000) @ initial
        expected = (
            expm(-2j * np.pi * h * (p["base"]["duration_ms"] - w["end_ms"]) / 1000)
            @ expm(-2j * np.pi * hp * w["width_ms"] / 1000)
            @ before
        )
        assert np.linalg.norm(field(r["arms"][arm]["state"]) - expected) < 1e-11
    no_u = copy.deepcopy(p)
    no_u["base"]["interaction_hz"] = 0
    assert (
        np.linalg.norm(
            field(r["arms"]["nominal"]["state"])
            - field(report(no_u)["records"][0]["arms"]["nominal"]["state"])
        )
        > 0.1
    )


def test_arbitrary_incoming_state_and_segment_composition():
    c = base_config(dict(atoms=5, tunnelling_hz=7, interaction_hz=0.6, bias_hz=-2, duration_ms=500))
    rng = np.random.default_rng(17)
    state = rng.normal(size=6) + 1j * rng.normal(size=6)
    state /= np.linalg.norm(state)
    data = dict(config=c, r=state.real.tolist(), im=state.imag.tolist())
    result = js(
        "let s=new TwoMode.Solver(data.config,{r:data.r,im:data.im});let a=s.at(37);let b=new TwoMode.Solver(data.config,{r:a.real,im:a.imag}).at(63);console.log(JSON.stringify({a,b,full:s.at(100)}));",
        data,
    )
    expected = expm(-2j * np.pi * hamiltonian(c) * 0.1) @ state
    assert np.linalg.norm(field(result["b"]) - expected) < 1e-11
    assert np.linalg.norm(field(result["full"]) - expected) < 1e-11
    assert result["a"]["norm"] == pytest.approx(1, abs=1e-12)


@pytest.mark.parametrize(
    "state",
    [dict(r=[1, 0], im=[0, 0]), dict(r=[2, 0, 0], im=[0, 0, 0]), dict(r=[0, 0, 0], im=[0, 0, 0])],
)
def test_bad_incoming_states_not_renormalized(state):
    c = base_config(dict(atoms=2))
    assert js(
        "try{new TwoMode.Solver(data.config,data.state);console.log(false)}catch(e){console.log(true)}",
        dict(config=c, state=state),
    )


def test_continuity_and_energy_at_switches():
    p = plan(phase_half_range=0.5)
    p["base"].update(interaction_hz=0.4, left_fraction=0.7, phase=0.6)
    result = report(p)
    for r in result["records"]:
        for arm, w in pulse.windows(p).items():
            b = r["boundaries"][arm]
            assert field(b["before_on"]) == pytest.approx(field(b["after_on"]), abs=1e-13)
            assert field(b["before_off"]) == pytest.approx(field(b["after_off"]), abs=1e-13)
            jump = -p["pulse_j_hz"] * p["base"]["atoms"] * b["before_on"]["coherence_real"]
            assert b["after_on"]["energy_hz"] - b["before_on"]["energy_hz"] == pytest.approx(
                jump, abs=1e-11
            )
            for stage in [0, 1, 2]:
                energies = [
                    h["energy_hz"] for h in r["arms"][arm]["history"] if h["stage"] == stage
                ]
                assert max(energies) - min(energies) < 1e-9
            for i, point in enumerate(result["checkpoints"]):
                if abs(point["time_ms"] - w["start_ms"]) < 1e-9:
                    row = r["arms"][arm]["history"][i]
                    assert row["active_j_hz"] == (
                        0 if point["side"] == "before" else p["pulse_j_hz"]
                    )
            pulse_rows = [h for h in r["arms"][arm]["history"] if h["stage"] == 1]
            assert len(pulse_rows) >= 21


def test_faster_pulse_approaches_ideal_at_fixed_total_time():
    fidelities = []
    for j in [2, 5, 10, 20]:
        p = plan(pulse_j_hz=j, bias_half_range_hz=0)
        p["base"].update(atoms=4, bias_hz=0.7, phase=0.3)
        r = report(p)
        assert r["records"][0]["arms"]["nominal"]["state"]["time_ms"] == 500
        fidelities.append(r["aggregate"]["nominal"]["mean_fidelity_to_ideal"])
    assert np.all(np.diff(fidelities) > 0)
    assert fidelities[-1] > 0.99


def test_zero_duration_error_collapses_finite_arms_and_reproducible_draws():
    p = plan(duration_error=0)
    a = report(p)
    assert a == report(p)
    for record in a["records"]:
        assert record["arms"]["short"] == record["arms"]["nominal"] == record["arms"]["long"]
    assert [r["bias_offset_hz"] for r in a["records"]] == [
        r["bias_offset_hz"] for r in recipes(pulse.ensemble(p))
    ]
    assert all(
        "guide_coherence" not in row for arm in pulse.ARMS for row in a["aggregate"][arm]["history"]
    )


def test_cancelled_prefix_replays():
    p = plan()
    r = report(p)
    r["status"] = "cancelled"
    r["records"] = r["records"][:1]
    ref = pulse.reference(p)
    records = [pulse.evolve(p, recipes(pulse.ensemble(p))[0])]
    r["aggregate"] = pulse.aggregate(p, ref, records)
    assert verify_export(r)["preparations_verified"] == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("pulse_j_hz", 0),
        ("pulse_j_hz", 21),
        ("duration_error", -0.1),
        ("duration_error", 0.51),
        ("preparations", 1),
        ("seed", 2**32),
    ],
)
def test_invalid_settings_both_languages(key, value):
    p = plan(**{key: value})
    with pytest.raises(ValueError):
        pulse.validate(p)
    assert js("try{FinitePulse.validate(data);console.log(false)}catch(e){console.log(true)}", p)


def test_invalid_hold_and_pulse_windows_rejected():
    p = plan()
    p["base"]["duration_ms"] = 30
    with pytest.raises(ValueError):
        pulse.validate(p)
    assert js("try{FinitePulse.validate(data);console.log(false)}catch(e){console.log(true)}", p)
    p["base"].update(duration_ms=500, tunnelling_hz=1)
    with pytest.raises(ValueError):
        pulse.validate(p)
    assert js("try{FinitePulse.validate(data);console.log(false)}catch(e){console.log(true)}", p)


@pytest.mark.parametrize(
    "path,value",
    [
        (("convention",), "ideal finite swap"),
        (("status",), "running"),
        (("plan", "pulse_j_hz"), 11),
        (("windows", "nominal", "width_ms"), 26),
        (("checkpoints", 2, "side"), "before"),
        (("records", 0, "arms", "nominal", "state", "real", 2), 0.7),
        (("records", 0, "boundaries", "long", "before_off", "imag", 2), 0.4),
        (("records", 0, "arms", "short", "fidelity_to_ideal"), 0.5),
        (("records", 0, "arms", "nominal", "history", 2, "active_j_hz"), 10),
        (("aggregate", "short", "mean_fidelity_to_ideal"), 0.4),
        (("aggregate", "ideal", "probability", 2), 0.9),
        (("reference", "arms", "no_echo", "state", "norm"), 0.9),
    ],
)
def test_tampering_rejected(path, value):
    r = report(plan())
    node = r
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        verify_export(r)
