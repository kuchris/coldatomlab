"""Loopback-only HTTP interface. Each browser owns an independent simulation."""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from .imaging import Camera, capture
from .solver import Config, Solver

WEB = Path(__file__).parent / "web"


class LabServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.sessions = {}
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, content_type="application/json"):
        payload = (
            json.dumps(data, allow_nan=False).encode()
            if content_type == "application/json"
            else data
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/physical.js": ("physical.js", "text/javascript; charset=utf-8"),
            "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
            "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
            "/physical-units": ("physical-units.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/camera.js": ("camera.js", "text/javascript; charset=utf-8"),
            "/imaging": ("imaging.html", "text/html; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path not in files:
            return self.respond(404, {"error": "Not found"})
        name, mime = files[self.path]
        self.respond(200, (WEB / name).read_bytes(), mime)

    def do_POST(self):
        allowed = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }
        if self.headers.get("Origin") and self.headers["Origin"] not in allowed:
            return self.respond(403, {"error": "Use the local experiment page."})
        if self.path != "/api":
            return self.respond(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Request is empty or too large.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Request must be an object.")
            with self.server.lock:
                now = time.monotonic()
                for key, (_, touched) in list(self.server.sessions.items()):
                    if now - touched > 3600:
                        del self.server.sessions[key]
                action = data.get("action")
                key = data.get("session")
                if action == "prepare":
                    if key not in self.server.sessions and len(self.server.sessions) >= 16:
                        raise ValueError(
                            "All 16 experiment sessions are in use. Restart the server."
                        )
                    sim = Solver(Config(**data.get("config", {})))
                    key = key if key in self.server.sessions else uuid4().hex
                else:
                    if key not in self.server.sessions:
                        raise ValueError("Session expired. Prepare an experiment again.")
                    sim = self.server.sessions[key][0]
                    if action == "step":
                        sim.advance(data.get("count", 10))
                    elif action == "release":
                        sim.release()
                    elif action == "reset":
                        sim.reset()
                    elif action not in ("export", "state", "capture"):
                        raise ValueError("Unknown experiment action.")
                self.server.sessions[key] = (sim, now)
                if action == "capture":
                    result = capture(sim, Camera(**data.get("camera", {})))
                else:
                    result = sim.export() if action == "export" else sim.snapshot()
                self.respond(200, {"session": key, "result": result})
        except (ValueError, TypeError, KeyError) as exc:
            self.respond(400, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description="Start Cold Atom Lab on this computer.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = LabServer(("127.0.0.1", args.port))
    print(f"Cold Atom Lab: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
