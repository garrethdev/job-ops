"""Gmail API client (read-only) — shared in core so Module A imports it, not vice versa.

Exchanges the stored refresh token for an access token, searches messages, and
fetches metadata + snippet. Reads GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET /
GMAIL_REFRESH_TOKEN from the environment. Scope is gmail.readonly.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(RuntimeError):
    pass


def _require(env: Dict[str, str], *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise GmailError("missing Gmail secrets: " + ", ".join(missing))


class Gmail:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._cid = client_id
        self._csec = client_secret
        self._rt = refresh_token
        self._token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Gmail":
        import os
        _require(os.environ, "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")
        return cls(os.environ["GMAIL_CLIENT_ID"], os.environ["GMAIL_CLIENT_SECRET"],
                   os.environ["GMAIL_REFRESH_TOKEN"])

    def _access_token(self) -> str:
        if self._token:
            return self._token
        body = urllib.parse.urlencode({
            "client_id": self._cid, "client_secret": self._csec,
            "refresh_token": self._rt, "grant_type": "refresh_token",
        }).encode("utf-8")
        try:
            data = json.loads(urllib.request.urlopen(TOKEN_URL, data=body, timeout=30).read())
        except urllib.error.HTTPError as e:
            raise GmailError(f"token refresh failed ({e.code}) — refresh token may be "
                             f"revoked/expired: {e.read().decode()[:200]}") from e
        self._token = data["access_token"]
        return self._token

    def _get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {self._access_token()}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def profile(self) -> Dict[str, Any]:
        return self._get("/profile")

    def label_id(self, name: str) -> Optional[str]:
        for lbl in self._get("/labels").get("labels", []):
            if lbl.get("name") == name:
                return lbl.get("id")
        return None

    def search(self, query: str, max_results: int = 100) -> List[str]:
        out: List[str] = []
        page = ""
        while len(out) < max_results:
            q = urllib.parse.urlencode({"q": query, "maxResults": min(100, max_results - len(out))})
            if page:
                q += "&pageToken=" + page
            data = self._get("/messages?" + q)
            out.extend(m["id"] for m in data.get("messages", []))
            page = data.get("nextPageToken", "")
            if not page:
                break
        return out

    def message(self, msg_id: str) -> Dict[str, str]:
        """Return {id, from, subject, date, snippet} — metadata + snippet only."""
        m = self._get(f"/messages/{msg_id}?format=metadata"
                      "&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date")
        hdrs = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
        return {
            "id": msg_id,
            "from": hdrs.get("from", ""),
            "subject": hdrs.get("subject", ""),
            "date": hdrs.get("date", ""),
            "snippet": m.get("snippet", ""),
        }
