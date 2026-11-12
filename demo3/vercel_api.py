"""Optional live endpoint for Claude (Vercel Python function). NOT deployed: Demo 3 runs on local models.

To enable: move this file to api/demo3.py, add a root requirements.txt with anthropic, and set
ANTHROPIC_API_KEY and DEMO_PASSCODE in Vercel. For free live runs use serve_local.py instead.


POST /api/demo3  {"passcode": "...", "cp_id": "CP-0209", "role": "owner"}
Runs ONE party's agent on one saved Change Proposal and returns its envelope. The dashboard calls
it once per role so each handoff appears as it finishes.

Guards: the passcode must match DEMO_PASSCODE; only saved CP ids are accepted (no free text, so the
endpoint can't be used as a general chatbot); a per-instance hourly cap. Set a monthly spend limit
in the Claude Console as the hard stop.
Environment variables (Vercel project settings): ANTHROPIC_API_KEY, DEMO_PASSCODE, optional DEMO3_MODEL.
"""
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo3"))
import agents  # noqa: E402

HOURLY_CAP = int(os.environ.get("DEMO3_HOURLY_CAP", "120"))
_calls = []
_cases = {c["id"]: c for c in json.loads((ROOT / "demo3" / "data" / "cases.json").read_text())["cases"]}


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"ok": True, "live": bool(os.environ.get("ANTHROPIC_API_KEY")),
                         "passcode_required": bool(os.environ.get("DEMO_PASSCODE"))})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(min(n, 10000)) or b"{}")
        except Exception:  # noqa: BLE001
            return self._send(400, {"error": "Bad request."})
        expected = os.environ.get("DEMO_PASSCODE", "")
        if not expected or not hmac.compare_digest(str(req.get("passcode", "")), expected):
            return self._send(401, {"error": "Wrong passcode."})
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return self._send(503, {"error": "Live mode is not configured."})
        cp, role = _cases.get(req.get("cp_id")), req.get("role")
        if not cp or role not in agents.ROLES:
            return self._send(400, {"error": "Unknown CP or role."})
        now = time.time()
        _calls[:] = [t for t in _calls if now - t < 3600]
        if len(_calls) >= HOURLY_CAP:
            return self._send(429, {"error": "Hourly limit reached. Showing the saved run instead."})
        _calls.append(now)
        if role == "sub" and not cp["subcontractor_quotes"]:
            return self._send(200, {"envelope": {"from_role": "sub", "decision": "PASS", "flags": [], "skipped": True,
                                                 "message": "No subcontractor pricing in this CP.", "to": "gc"}})
        try:
            import anthropic
            client = anthropic.Anthropic()
            model = os.environ.get("DEMO3_MODEL", agents.DEFAULT_MODEL)
            contract = agents.CONTRACT_FILE.read_text(encoding="utf-8")
            answer, usage, _ = agents.review(role, cp, "anthropic", model, client, contract, agents.rule_card(), use_cache=False)
            env = agents.envelope(cp, role, answer, model, agents.normalize(contract), None)
            env["usage"] = usage
            return self._send(200, {"envelope": env})
        except Exception as e:  # noqa: BLE001
            return self._send(502, {"error": f"Agent call failed: {type(e).__name__}"})
