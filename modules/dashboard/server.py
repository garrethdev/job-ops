"""Dashboard HTTP backend (stdlib http.server). Imports core only."""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from core import store as store_mod
from core.apollo import ApolloError, find_contact
from core.config import apollo_key

STATIC = Path(__file__).resolve().parent / "static"

_ID = r"([0-9a-f]{40})"
RE_ENRICH = re.compile(rf"^/api/leads/{_ID}/enrich$")
RE_NOTES = re.compile(rf"^/api/leads/{_ID}/notes$")
RE_LEAD = re.compile(rf"^/api/leads/{_ID}$")


def _lead_view(r: Dict[str, Any]) -> Dict[str, Any]:
    """Trim a record to what the table needs (drop the bulky snippet)."""
    return {
        "id": r.get("id"),
        "title": r.get("title"),
        "company": r.get("company"),
        "lane": r.get("lane"),
        "fit_score": r.get("fit_score"),
        "fit_rationale": r.get("fit_rationale"),
        "red_flags": r.get("red_flags", []),
        "url": r.get("url"),
        "location": r.get("location"),
        "source_detail": r.get("source_detail"),
        "status": r.get("status"),
        "contact": r.get("contact", {}),
        "notes": r.get("notes", ""),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quieter console
        pass

    # --- helpers ---------------------------------------------------------
    def _send(self, code: int, payload: Any, ctype: str = "application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    # --- routes ----------------------------------------------------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/api/leads":
            leads = [_lead_view(r) for r in store_mod.load()]
            leads.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
            return self._send(200, {"leads": leads, "apollo_ready": bool(apollo_key())})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        m = RE_ENRICH.match(self.path)
        if m:
            return self._enrich(m.group(1))
        m = RE_NOTES.match(self.path)
        if m:
            return self._notes(m.group(1))
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        m = RE_LEAD.match(self.path)
        if m:
            ok = store_mod.delete_record(m.group(1))
            return self._send(200 if ok else 404, {"ok": ok})
        return self._send(404, {"error": "not found"})

    # --- handlers --------------------------------------------------------
    def _enrich(self, lead_id: str):
        rec = store_mod.get_record(lead_id)
        if not rec:
            return self._send(404, {"error": "lead not found"})
        # Already revealed? Don't spend another credit.
        if (rec.get("contact") or {}).get("linkedin"):
            return self._send(200, {"lead": _lead_view(rec), "meta": {"credits_used": 0, "cached": True}})
        try:
            res = find_contact(rec.get("company", ""), lane=rec.get("lane", ""))
        except ApolloError as e:
            return self._send(502, {"error": f"apollo: {e}"})
        contact = res.get("contact")
        if not contact:
            return self._send(200, {"lead": _lead_view(rec), "meta": res["meta"]})
        patch = {"contact": contact}
        if rec.get("status") == "new":
            patch["status"] = "enriched"
        updated = store_mod.update_record(lead_id, patch)
        return self._send(200, {"lead": _lead_view(updated), "meta": res["meta"]})

    def _notes(self, lead_id: str):
        notes = str(self._read_json().get("notes", ""))[:4000]
        updated = store_mod.update_record(lead_id, {"notes": notes})
        if not updated:
            return self._send(404, {"error": "lead not found"})
        return self._send(200, {"lead": _lead_view(updated)})


def serve(host: str = "127.0.0.1", port: int = 8787):
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"lead dashboard -> http://{host}:{port}  (Ctrl-C to stop)")
    print(f"apollo: {'ready' if apollo_key() else 'NO KEY (find-linkedin disabled)'}")
    httpd.serve_forever()
