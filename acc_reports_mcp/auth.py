"""
Autodesk sign-in (3-legged OAuth), read-only scopes.

How it works, in four steps:
  1. `python authorize.py` opens Autodesk's login page in your browser.
  2. You sign in as yourself and approve the app.
  3. Autodesk sends a one-time code back to the local callback URL; we swap
     it for an access token (valid ~1 hour) and a refresh token.
  4. Both are saved to TOKEN_PATH. From then on the server refreshes the
     access token by itself, so you only sign in again if the refresh token
     is revoked or goes unused for a long time.

Because you sign in as yourself, the server can only ever see what YOU can
see in ACC. Claude never sees the token; it only sees tool results.
"""
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from . import config

AUTHORIZE_URL = "https://developer.api.autodesk.com/authentication/v2/authorize"
TOKEN_URL = "https://developer.api.autodesk.com/authentication/v2/token"
USERINFO_URL = "https://api.userprofile.autodesk.com/userinfo"

_lock = threading.Lock()


class NotSignedIn(config.SetupError):
    pass


# ------------------------------------------------------------ token store

def _load() -> dict | None:
    if not config.TOKEN_PATH.exists():
        return None
    try:
        return json.loads(config.TOKEN_PATH.read_text())
    except json.JSONDecodeError:
        return None


def _save(body: dict, previous_refresh: str | None = None) -> dict:
    cache = {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token") or previous_refresh,
        "expires_at": time.time() + int(body.get("expires_in", 3600)),
        "scope": body.get("scope", config.SCOPES),
    }
    config.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOKEN_PATH.write_text(json.dumps(cache, indent=2))
    try:
        os.chmod(config.TOKEN_PATH, 0o600)  # only you can read it
    except OSError:
        pass
    return cache


def get_access_token() -> str:
    """A valid access token, refreshed if it is about to expire."""
    with _lock:  # one refresh at a time; refresh tokens rotate
        cache = _load()
        if not cache:
            raise NotSignedIn(
                "You're not signed in to Autodesk yet. In a terminal, from the repo folder, run: "
                "python authorize.py  (see README, step 3)."
            )
        if cache["expires_at"] > time.time() + 60:
            return cache["access_token"]
        config.require_app_credentials()
        resp = httpx.post(
            TOKEN_URL,
            auth=(config.APS_CLIENT_ID, config.APS_CLIENT_SECRET),
            data={"grant_type": "refresh_token", "refresh_token": cache["refresh_token"], "scope": config.SCOPES},
            timeout=30,
        )
        if resp.is_error:
            raise NotSignedIn(
                f"Your Autodesk sign-in has expired ({resp.status_code}). Run python authorize.py again."
            )
        return _save(resp.json(), cache["refresh_token"])["access_token"]


def who_am_i() -> dict:
    resp = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {get_access_token()}"}, timeout=30)
    resp.raise_for_status()
    info = resp.json()
    return {"name": info.get("name"), "email": info.get("email"), "scopes": (_load() or {}).get("scope")}


# ------------------------------------------------------------ browser login

def login() -> dict:
    """Interactive sign-in. Used by authorize.py; not called by Claude."""
    config.require_app_credentials()
    callback = urlparse(config.CALLBACK_URL)
    if callback.hostname not in ("localhost", "127.0.0.1"):
        raise config.SetupError("APS_CALLBACK_URL must point at localhost for the local sign-in.")
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != callback.path:
                self.send_response(404)
                self.end_headers()
                return
            q = parse_qs(parsed.query)
            if q.get("state", [None])[0] != state:
                result["error"] = "state mismatch (try again)"
            else:
                result["code"] = q.get("code", [None])[0]
                result["error"] = q.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Signed in. You can close this tab." if result.get("code") else f"Sign-in failed: {result.get('error')}"
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *args):
            pass

    params = urlencode({
        "response_type": "code",
        "client_id": config.APS_CLIENT_ID,
        "redirect_uri": config.CALLBACK_URL,
        "scope": config.SCOPES,
        "state": state,
        "prompt": "login",  # always ask, so you consciously pick the account
    })
    url = f"{AUTHORIZE_URL}?{params}"
    print("Opening Autodesk sign-in in your browser...\nIf nothing opens, paste this link into a browser:\n" + url + "\n")
    webbrowser.open(url)

    server = HTTPServer((callback.hostname, callback.port or 80), Handler)
    while "code" not in result and not result.get("error"):
        server.handle_request()
    server.server_close()
    if not result.get("code"):
        raise RuntimeError(f"Autodesk sign-in failed: {result.get('error')}")

    resp = httpx.post(
        TOKEN_URL,
        auth=(config.APS_CLIENT_ID, config.APS_CLIENT_SECRET),
        data={"grant_type": "authorization_code", "code": result["code"], "redirect_uri": config.CALLBACK_URL},
        timeout=30,
    )
    if resp.is_error:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text}")
    _save(resp.json())
    return who_am_i()
