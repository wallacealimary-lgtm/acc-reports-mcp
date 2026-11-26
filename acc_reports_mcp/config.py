"""
Settings for the server. Everything comes from environment variables, or
from a `.env` file in the repo folder (copy `.env.example` to start).

Nothing here is secret except APS_CLIENT_SECRET, which lives only in your
`.env` (never commit it, never paste it into a chat).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


# Your own APS app (aps.autodesk.com > My Apps).
APS_CLIENT_ID = _env("APS_CLIENT_ID")
APS_CLIENT_SECRET = _env("APS_CLIENT_SECRET")
# Must match a Callback URL registered on that app.
CALLBACK_URL = _env("APS_CALLBACK_URL", "http://localhost:8080/callback")

# Read-only scopes. This is the ceiling for everything the server can do:
# even if someone added a write call to the code, Autodesk would refuse it.
#   data:read          read ACC project data (issues, forms, assets, photos...)
#   account:read       read project members, so reports show names not IDs
#   user-profile:read  show who you signed in as
SCOPES = "data:read account:read user-profile:read"

# Where your login (access + refresh token) is stored. Outside the repo on
# purpose, so it can never be committed by accident.
TOKEN_PATH = Path(_env("ACC_TOKEN_PATH") or Path.home() / ".acc-reports-mcp" / "token.json").expanduser()

# Optional: a project name or id to use when a request doesn't say which.
DEFAULT_PROJECT = _env("ACC_DEFAULT_PROJECT")

# Where finished reports are written.
OUTPUT_DIR = Path(_env("ACC_REPORTS_DIR") or ROOT / "output").expanduser()

# Where report definitions live (one folder per report). Edit or add here.
REPORTS_DIR = Path(_env("ACC_REPORT_TEMPLATES_DIR") or ROOT / "reports").expanduser()

# Sample mode: run everything against the bundled fictional data in
# samples/, no Autodesk login needed. Good for trying reports out.
SAMPLE_MODE = _env("ACC_SAMPLE_MODE").lower() in ("1", "true", "yes", "on")
SAMPLES_DIR = ROOT / "samples"


class SetupError(RuntimeError):
    """A setup step is missing. The message says which one and how to fix it."""


def require_app_credentials() -> None:
    missing = [n for n, v in (("APS_CLIENT_ID", APS_CLIENT_ID), ("APS_CLIENT_SECRET", APS_CLIENT_SECRET)) if not v]
    if missing:
        raise SetupError(
            "Missing " + " and ".join(missing) + ". Copy .env.example to .env and paste in the "
            "Client ID and Client Secret of your APS app (see README, step 2). "
            "Or set ACC_SAMPLE_MODE=true to try the server with sample data."
        )
