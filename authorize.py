"""
Sign in to Autodesk once, as yourself. Run from the repo folder:

    python authorize.py

Your browser opens Autodesk's login page. After you sign in, your login is
saved (outside this folder, in ~/.acc-reports-mcp/token.json) and the
server keeps it fresh by itself. Run this again only if it tells you to.
"""
from acc_reports_mcp import auth, config

if __name__ == "__main__":
    try:
        me = auth.login()
    except config.SetupError as e:
        raise SystemExit(f"Setup needed: {e}")
    print(f"\nSigned in as {me.get('name')} <{me.get('email')}>")
    print(f"Scopes: {me.get('scopes')}  (read-only)")
    print(f"Login saved to {config.TOKEN_PATH}")
    print("Now restart Claude (or reconnect the acc-reports server) and ask it something.")
