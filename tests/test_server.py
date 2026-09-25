import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from coldatomlab.server import LabServer


@pytest.fixture
def endpoint():
    server = LabServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def post(endpoint, payload):
    request = Request(
        endpoint + "/api",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request) as response:
        return json.load(response)


def test_sessions_and_invalid_prepare_preserve_previous_state(endpoint):
    a = post(endpoint, {"action": "prepare", "config": {"experiment": "double", "n": 64}})
    b = post(endpoint, {"action": "prepare", "config": {"experiment": "double", "n": 64}})
    key = a["session"]
    assert key != b["session"]
    post(endpoint, {"action": "step", "session": key, "count": 3})
    with pytest.raises(HTTPError) as exc:
        post(endpoint, {"action": "prepare", "session": key, "config": {"dt": 0}})
    assert exc.value.code == 400
    state = post(endpoint, {"action": "state", "session": key})
    assert state["result"]["diagnostics"]["steps"] == 3
    other = post(endpoint, {"action": "state", "session": b["session"]})
    assert other["result"]["diagnostics"]["steps"] == 0
    exported = post(endpoint, {"action": "export", "session": key})
    assert exported["result"]["schema"] == "coldatomlab-experiment-v1"


def test_http_rejects_foreign_origin_and_path_traversal(endpoint):
    request = Request(endpoint + "/api", data=b"{}", headers={"Origin": "https://example.com"})
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 403
    with pytest.raises(HTTPError) as exc:
        urlopen(endpoint + "/../pyproject.toml")
    assert exc.value.code == 404


def test_camera_endpoint_keeps_state_and_recovers_after_invalid_settings(endpoint):
    run = post(
        endpoint,
        {
            "action": "prepare",
            "config": {"experiment": "double", "n": 64, "physical": {"species": "Rb87"}},
        },
    )
    key = run["session"]
    before = post(endpoint, {"action": "export", "session": key})["result"]
    with pytest.raises(HTTPError) as error:
        post(endpoint, {"action": "capture", "session": key, "camera": {"binning": 3}})
    assert error.value.code == 400
    shot = post(
        endpoint, {"action": "capture", "session": key, "camera": {"noise": False, "strip_um": 5}}
    )
    assert shot["result"]["schema"] == "coldatomlab-camera-v1"
    assert shot["result"]["source"] == before
    assert post(endpoint, {"action": "export", "session": key})["result"] == before
