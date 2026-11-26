# How the sign-in works

There are **two separate connections**, and they work differently:

```
 You ──▶ Claude ──(1)──▶ acc-reports server ──(2)──▶ Autodesk (ACC)
          on your computer      on your computer          in the cloud
```

**(1) Claude ↔ the server: no login.** Claude starts `start_server.py` as a program on your own computer and talks to it through a direct pipe. Your Claude config only says *what to run*. It holds no password.

**(2) The server ↔ Autodesk: your Autodesk sign-in (3-legged OAuth).** "3-legged" means three parties agree:

- **you** sign in and approve,
- **the app** (your APS app, identified by its Client ID and Secret),
- **Autodesk**, which issues a token for that app, acting as you.

## What happens when you run `authorize.py`

1. Your browser opens Autodesk's sign-in page. The link says which app is asking (the Client ID) and what for (the **scopes**).
2. You sign in and approve. Autodesk redirects the browser to `http://localhost:8080/callback`: a tiny web server that `authorize.py` runs for a few seconds to catch the reply. The reply holds a **one-time code**.
3. The server sends the code plus your app's **Client Secret** to Autodesk and gets back:
   - an **access token**: lets the server call the API as you for about an hour,
   - a **refresh token**: lets it get a new access token later without you signing in again.
4. Both are saved to `~/.acc-reports-mcp/token.json`. The file is readable only by you and sits outside the repo, so it can't be committed by accident.

From then on, every API call carries the access token. When it's about to expire, the server swaps the refresh token for a new one by itself.

To watch each step happen, run the stand-alone example: `.venv/bin/python examples/auth_example.py`. It's about 60 lines and saves nothing.

## What limits what it can do

Three limits apply on top of each other. The tightest one wins.

| Limit | Set by | Here |
|---|---|---|
| **Scopes**: what the token may do at all | the sign-in request (`acc_reports_mcp/config.py`) | `data:read account:read user-profile:read`: read only |
| **Your ACC permissions**: which projects and items you can see | your ACC project admins | exactly what you see in ACC |
| **The app being allowed on the ACC account** | an ACC account admin (Custom Integrations) | needed once per ACC account |

So even if someone added a "create issue" tool to this code, Autodesk would reject it: the token only carries read scopes.

## Where everything lives

| What | Where | Secret? |
|---|---|---|
| Client ID | `.env` | No (it identifies the app) |
| Client Secret | `.env` | **Yes**. Never share it, commit it or paste it into a chat |
| Your sign-in (tokens) | `~/.acc-reports-mcp/token.json` | **Yes**. It's a live login |
| Claude config | Claude's settings | No (paths only) |

Claude itself never sees the secret or the tokens. It only sees what the tools return.

## Sharing with someone else

Give them the code (or the repo link), not your `.env` and not your token file. They create their own APS app, add their own Client ID to their own ACC account, and sign in as themselves. Each person's server can then see only what that person can see.

## Signing out

Delete `~/.acc-reports-mcp/token.json`. To cut access off completely, remove the app under your Autodesk profile's connected apps, or delete or rotate its secret at [aps.autodesk.com](https://aps.autodesk.com).

## Regions

ACC hubs live in a region: US, EMEA (`acc.autodesk.eu`) or AUS. The server reads each hub's region when it lists projects, and sends the matching `x-ads-region` header automatically. You don't need to set anything.

## Hosting it for a team (later)

This version runs on each person's own computer. To host one copy for a team, connection (1) moves onto the web, and people sign in to the server itself (MCP's remote transport, with OAuth). The server then holds tokens for several users, so it needs a proper secret store. That's a different build: start with this one.
