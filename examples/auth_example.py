"""
The whole Autodesk sign-in in one short file, with nothing hidden.
It's the same flow the server uses (acc_reports_mcp/auth.py), minus the
saving and refreshing. Run it to watch each step:

    .venv/bin/python examples/auth_example.py

It reads APS_CLIENT_ID / APS_CLIENT_SECRET from .env, signs you in, and
lists your hubs. It saves nothing.
"""
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
CLIENT_ID = os.environ["APS_CLIENT_ID"]
CLIENT_SECRET = os.environ["APS_CLIENT_SECRET"]
CALLBACK = os.environ.get("APS_CALLBACK_URL") or "http://localhost:8080/callback"
SCOPES = "data:read"  # read-only: Autodesk will refuse any write made with this token

# Step 1: send you to Autodesk's sign-in page, saying which app is asking and for what.
state = secrets.token_urlsafe(8)  # a random value, to check the reply really is ours
url = "https://developer.api.autodesk.com/authentication/v2/authorize?" + urlencode({
    "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": CALLBACK,
    "scope": SCOPES, "state": state})
print("Step 1: opening Autodesk sign-in:\n ", url)
webbrowser.open(url)

# Step 2: after you sign in, Autodesk redirects the browser to our callback with a one-time code.
received = {}


class Callback(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        received.update(code=q.get("code", [None])[0], state=q.get("state", [None])[0])
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Got the code. Back to the terminal.")

    def log_message(self, *a):
        pass


cb = urlparse(CALLBACK)
server = HTTPServer((cb.hostname, cb.port), Callback)
while "code" not in received:
    server.handle_request()
assert received["state"] == state, "reply didn't come from our request"
print("Step 2: got a one-time code from Autodesk")

# Step 3: swap the code for an access token. Only this step uses the secret, from your machine.
token = httpx.post("https://developer.api.autodesk.com/authentication/v2/token",
                   auth=(CLIENT_ID, CLIENT_SECRET),
                   data={"grant_type": "authorization_code", "code": received["code"], "redirect_uri": CALLBACK}).json()
print(f"Step 3: access token received, valid {token['expires_in']} s, scope: {token.get('scope')}")

# Step 4: call the API as you. ACC applies your own permissions to everything below.
hubs = httpx.get("https://developer.api.autodesk.com/project/v1/hubs",
                 headers={"Authorization": f"Bearer {token['access_token']}"}).json()
print("Step 4: your hubs:")
for h in hubs.get("data", []):
    print(f"   {h['attributes']['name']}  (region {h['attributes'].get('region')})")
