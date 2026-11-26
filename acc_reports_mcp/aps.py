"""
The only place that talks HTTP to Autodesk.

Read-only by construction: this client has `get()` and `query()` and
nothing else. `query()` exists because a few READ endpoints are POSTs
(e.g. photos:filter); it refuses any path that isn't on the read-only
allow-list below. There is no put/patch/delete anywhere in this repo.
"""
import time

import httpx

from . import auth

BASE_URL = "https://developer.api.autodesk.com"

# POST endpoints that only read data. Anything else is refused.
READ_ONLY_POST_SUFFIXES = (":filter", ":search")


class ApsError(RuntimeError):
    def __init__(self, status: int, path: str, body: str):
        hint = {
            401: "Your sign-in expired: run python authorize.py.",
            403: "Your Autodesk account (or the APS app) has no access to this. Check the app is "
                 "added to the ACC account as a custom integration, and that you're a member of the project.",
            404: "Not found: check the project or item id.",
            429: "Autodesk is rate-limiting requests; wait a minute and try again.",
        }.get(status, "")
        super().__init__(f"Autodesk API {status} on {path}. {hint} Details: {body[:400]}")
        self.status = status


class ReadOnlyViolation(RuntimeError):
    pass


class Client:
    def __init__(self, region: str | None = None):
        self.region = region  # x-ads-region: "US", "EMEA" or "AUS"
        self._http = httpx.Client(base_url=BASE_URL, timeout=60)

    def _headers(self) -> dict:
        h = {"Authorization": f"Bearer {auth.get_access_token()}"}
        if self.region:
            h["x-ads-region"] = self.region
        return h

    def _send(self, method: str, path: str, **kw) -> dict:
        for attempt in range(4):
            resp = self._http.request(method, path, headers=self._headers(), **kw)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(min(int(resp.headers.get("Retry-After", "2") or 2), 20))
                continue
            if resp.is_error:
                raise ApsError(resp.status_code, path, resp.text)
            return resp.json() if resp.content else {}
        raise ApsError(429, path, "still rate-limited after retries")

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._send("GET", path, params=params)

    def query(self, path: str, body: dict) -> dict:
        """POST to a read-only search/filter endpoint."""
        if not path.split("?")[0].endswith(READ_ONLY_POST_SUFFIXES):
            raise ReadOnlyViolation(f"Refusing POST to {path}: this server is read-only.")
        return self._send("POST", path, json=body)

    # ---------------------------------------------------------- paging helpers

    def get_all_offset(self, path: str, params: dict | None = None, page_size: int = 100,
                       key: str | None = None, max_items: int = 20000) -> list:
        """Pages through offset/limit endpoints (Issues, Forms, Admin...)."""
        out: list = []
        params = dict(params or {})
        while True:
            params.update({"limit": page_size, "offset": len(out)})
            page = self.get(path, params)
            rows = page.get(key) if key else (page.get("results") if "results" in page else page.get("data"))
            rows = rows or []
            out.extend(rows)
            total = (page.get("pagination") or {}).get("totalResults")
            if not rows or len(out) >= max_items or (total is not None and len(out) >= total):
                return out
            if total is None and len(rows) < page_size:
                return out

    def get_all_cursor(self, path: str, params: dict | None = None, page_size: int = 100,
                       max_items: int = 20000) -> list:
        """Pages through cursorState endpoints (Assets)."""
        out: list = []
        params = dict(params or {})
        params["limit"] = page_size
        while True:
            page = self.get(path, params)
            out.extend(page.get("results") or [])
            cursor = (page.get("pagination") or {}).get("cursorState")
            if not cursor or not page.get("results") or len(out) >= max_items:
                return out
            params["cursorState"] = cursor


def download(url: str) -> bytes | None:
    """Fetch a pre-signed URL (photos, attachments). No auth header needed."""
    try:
        resp = httpx.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPError:
        return None
