#!/usr/bin/env python3
"""Run the whole site on your own computer with live agents on a local model (no API key, no cost).

    ollama pull llama3.1:8b
    python3 demo3/serve_local.py            # then open http://localhost:8000/clausestream/

"Run agents live" in the dashboard calls /api/demo3 here, which runs the role agent on Ollama.
Only this computer can reach it (it listens on 127.0.0.1).
"""
import argparse
import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo3"))
import agents  # noqa: E402

CASES = {c["id"]: c for c in json.loads((ROOT / "demo3" / "data" / "cases.json").read_text())["cases"]}
CONTRACT = agents.CONTRACT_FILE.read_text(encoding="utf-8")
RULES = agents.rule_card()
MODEL = os.environ.get("LOCAL_MODEL", "llama3.1:8b")


class Handler(SimpleHTTPRequestHandler):
    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/demo3"):
            return self._json(200, {"ok": True, "live": True, "backend": "ollama", "model": MODEL, "passcode_required": False})
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/demo3"):
            return self._json(404, {"error": "Not found."})
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        cp, role = CASES.get(req.get("cp_id")), req.get("role")
        if not cp or role not in agents.ROLES:
            return self._json(400, {"error": "Unknown CP or role."})
        if role == "sub" and not cp["subcontractor_quotes"]:
            return self._json(200, {"envelope": {"from_role": "sub", "decision": "PASS", "flags": [], "skipped": True,
                                                 "message": "No subcontractor pricing in this CP.", "to": "gc"}})
        try:
            answer, usage, _ = agents.review(role, cp, "ollama", MODEL, None, CONTRACT, RULES, use_cache=False)
        except Exception as e:  # noqa: BLE001
            return self._json(502, {"error": f"Local model call failed ({type(e).__name__}). Is Ollama running?"})
        env = agents.envelope(cp, role, answer, MODEL, agents.normalize(CONTRACT), None)
        env["usage"] = usage
        return self._json(200, {"envelope": env})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), partial(Handler, directory=str(ROOT)))
    print(f"Serving the site with live local agents ({MODEL}) at http://localhost:{a.port}/clausestream/")
    srv.serve_forever()


if __name__ == "__main__":
    main()
