#!/usr/bin/env python3
"""Claude LLM shim — Vasu's instance only.

Runs on the WSL *host* (where `claude` is logged in) and exposes a tiny HTTP
endpoint the backend container calls instead of Groq/Ollama. See
.claude/specs/claude-llm/approach.md.

    POST /chat  {system, user, json: bool, model: "haiku"|"sonnet", max_tokens?}
                -> {text: "..."}            (200)  or  {error: "..."} (500)
    GET  /health -> {ok: true, model: <default>}

- Auth: every request must carry  X-Shim-Token: <CLAUDE_SHIM_TOKEN>  (if set).
- Serialized: one subscription, so calls run one at a time under a lock.
- Stdlib only (no venv needed); run with the host's python3.

Env:
    CLAUDE_BIN            default /home/vasu/.local/bin/claude
    CLAUDE_SHIM_PORT      default 8099
    CLAUDE_SHIM_TOKEN     shared secret (recommended; empty = no auth)
    CLAUDE_DEFAULT_MODEL  default "haiku"
    CLAUDE_CALL_TIMEOUT   seconds, default 180
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLAUDE_BIN = os.getenv("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
PORT = int(os.getenv("CLAUDE_SHIM_PORT", "8099"))
TOKEN = os.getenv("CLAUDE_SHIM_TOKEN", "")
DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "haiku")
TIMEOUT = int(os.getenv("CLAUDE_CALL_TIMEOUT", "180"))

_lock = threading.Lock()

JSON_NUDGE = (
    "\n\nRespond with ONLY a single valid JSON object. "
    "No prose, no markdown, no code fences."
)


def _run_claude(system: str, user: str, want_json: bool, model: str) -> str:
    prompt = f"{system}\n\n{user}" if system else user
    if want_json:
        prompt += JSON_NUDGE
    # -p (print mode) reads the prompt from stdin when none is given positionally.
    with _lock:  # one subscription -> serialize
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    return proc.stdout.strip()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "model": DEFAULT_MODEL})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/chat":
            self._send(404, {"error": "not found"})
            return
        if TOKEN and self.headers.get("X-Shim-Token", "") != TOKEN:
            self._send(401, {"error": "bad token"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, {"error": f"bad body: {e}"})
            return
        try:
            text = _run_claude(
                system=req.get("system", ""),
                user=req.get("user", ""),
                want_json=bool(req.get("json", False)),
                model=req.get("model") or DEFAULT_MODEL,
            )
            self._send(200, {"text": text})
        except subprocess.TimeoutExpired:
            self._send(504, {"error": f"claude timed out after {TIMEOUT}s"})
        except Exception as e:
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"claude_shim on :{PORT} (bin={CLAUDE_BIN}, default={DEFAULT_MODEL}, auth={'yes' if TOKEN else 'no'})")
    srv.serve_forever()
