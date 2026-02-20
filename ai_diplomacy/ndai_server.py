"""
NDAI negotiation server client and dummy stub.

When --ndai is set, the game uses this client to:
- /init/game/phase: kick off the server for a phase (wait for confirm)
- get_joint_statement/game/phase/power_name: each power gets joint statement

Set NDAI_SERVER_URL in env (e.g. http://127.0.0.1:8080) or defaults to that.
Run the dummy server with: python -m ai_diplomacy.ndai_server
"""

import asyncio
import json
import logging
import os
import random
from typing import Any, Dict

# All powers for stub joint-statement; normalize to uppercase for keys
STUB_POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]

# Templates for joint statements: {self} = power_name, {other} = other power. Read as contract-style statements.
STUB_JOINT_STATEMENT_TEMPLATES = [
    "{other} agrees to support {self} in the Balkan theater.",
    "{self} and {other} commit to a non-aggression pact in the Mediterranean.",
    "{other} pledges military assistance to {self} for the upcoming campaign.",
    "{self} and {other} agree to coordinate on the disposition of forces in the center.",
    "{other} undertakes to refrain from hostile moves against {self} this season.",
    "{self} and {other} declare a mutual interest in containing expansion in the east.",
    "{other} agrees to facilitate {self}'s advance in exchange for future considerations.",
    "{self} and {other} affirm a shared commitment to stability in the western front.",
    "{other} commits to diplomatic support for {self} in the current phase.",
    "{self} and {other} agree to joint action regarding the northern waters.",
    "{other} pledges to coordinate convoy support with {self}.",
    "{self} and {other} agree to mutual defense in the event of third-party aggression.",
    "{other} agrees to help {self} with the Balkan war.",
    "{self} and {other} formalize an understanding on sphere of influence.",
]

logger = logging.getLogger("ndai_server")

# Base URL for the NDAI server (no trailing slash)
def _base_url() -> str:
    return os.environ.get("NDAI_SERVER_URL", "http://127.0.0.1:8080")


async def init_game_phase(phase: str) -> bool:
    """Call /init/game/phase; wait for confirm. Returns True on success or on connection error (dummy mode)."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; NDAI client will use dummy responses. pip install httpx")
        return True
    base = _base_url().rstrip("/")
    url = f"{base}/init/game/phase"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json={"phase": phase})
            r.raise_for_status()
            data = r.json() if r.content else {}
            if data.get("status") in ("ok", "confirm", "confirmed") or r.status_code == 200:
                logger.info(f"NDAI init game phase confirmed for {phase}")
                return True
            logger.warning(f"NDAI init returned unexpected response: {data}")
            return True  # proceed anyway in dummy mode
    except Exception as e:
        logger.warning(f"NDAI init_game_phase failed (server may be down): {e}. Proceeding as dummy.")
        return True


async def get_joint_statement(phase: str, power_name: str) -> Dict[str, str]:
    """
    Call get_joint_statement/game/phase/power_name; wait for response.
    Returns a dict mapping other_power -> joint statement string, e.g. {"RUSSIA": "...", "ITALY": "..."}.
    On connection error returns {} (dummy mode).
    """
    try:
        import httpx
    except ImportError:
        return {}
    base = _base_url().rstrip("/")
    url = f"{base}/get_joint_statement/game/{phase}/{power_name}"
    logger.info(f"NDAI get_joint_statement: {url}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json() if r.content else {}
            if "joint_statement" in data and isinstance(data["joint_statement"], dict):
                logger.info(f"NDAI get_joint_statement: {data['joint_statement']}")
                return data["joint_statement"]
            return {}
    except Exception as e:
        logger.warning(f"NDAI get_joint_statement failed for {power_name}: {e}. Using empty joint statement.")
        return {}


# --- Dummy stub server (run with: python -m ai_diplomacy.ndai_server) ---

def _run_stub_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class StubHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            try:
                data = json.loads(body.decode()) if body else {}
            except Exception:
                data = {}
            if self.path == "/init/game/phase":
                phase = data.get("phase", "unknown")
                logger.info(f"Stub: init game phase {phase}")
                response = {"status": "ok", "message": "confirmed"}
            else:
                response = {"status": "ok"}
            self._send_json(200, response)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 4 and parts[0] == "get_joint_statement" and parts[1] == "game":
                phase, power_name = parts[2], parts[3].upper()
                logger.info(f"Stub: get_joint_statement for {power_name} phase {phase}")
                others = [p for p in STUB_POWERS if p != power_name]
                num_chosen = random.randint(1, min(3, len(others)))
                chosen = random.sample(others, num_chosen)
                self_display = power_name.title()
                joint_statement = {}
                for p in chosen:
                    other_display = p.title()
                    template = random.choice(STUB_JOINT_STATEMENT_TEMPLATES)
                    stmt = template.format(self=self_display, other=other_display)
                    joint_statement[p] = f"{stmt} (phase {phase})"
                response = {"joint_statement": joint_statement}
            else:
                response = {}
            self._send_json(200, response)

        def _send_json(self, code, obj):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            raw = json.dumps(obj).encode()
            self.send_header("Content-Length", len(raw))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            pass  # suppress default request logging

    port = int(os.environ.get("NDAI_STUB_PORT", "8080"))
    logger.info(f"NDAI stub server starting on port {port}")
    server = HTTPServer(("0.0.0.0", port), StubHandler)
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _run_stub_server()
