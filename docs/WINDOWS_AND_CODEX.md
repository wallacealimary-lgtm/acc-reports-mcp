# Quick setup: Windows + Codex

The short version of how we got this running on a Windows laptop, signed in as someone else, and connected to Codex. Type every command by hand and press Enter after each one.

## Before you start

- **Python installed on the laptop** (once, not per folder). Get it from [python.org/downloads](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** on the first screen. Or, in PowerShell: `winget install Python.Python.3.12`. Then close and reopen PowerShell.
- **No GitHub account needed.**

## 1. Get the code

1. Open https://github.com/wallacealimary-lgtm/acc-reports-mcp
2. Click **Code → Download ZIP**, then unzip it into `Documents`. Rename the folder from `acc-reports-mcp-main` to `acc-reports-mcp`.
3. Open that folder in File Explorer. You should see `README.md` and `requirements.txt`. Click the address bar, type `powershell` and press Enter.

Your prompt should start with `PS C:\` and end with `acc-reports-mcp>`.

> **If you ever see `>>>`, you're inside Python, not PowerShell.** Typing `py` on its own does that. Type `exit()` and press Enter to get back.

## 2. Install

| Type | You should see |
|---|---|
| `py -V` (hyphen, capital V) | `Python 3.x` |
| `py -m venv .venv` (hyphen m; the last word starts with a full stop) | Nothing. The prompt returns, and a `.venv` folder appears |
| `.venv\Scripts\pip install -r requirements.txt` | Download lines, then **Successfully installed** |
| `.venv\Scripts\python run_report.py --sample report form_record --opt form=2` | A report opens in your browser with a yellow **SAMPLE DATA** banner |

If `py` isn't recognised, use `python` instead.

## 3. Your Autodesk app and sign-in

1. **aps.autodesk.com → My Apps → Create application**, type **Traditional Web App**. Set the Callback URL to `http://localhost:8080/callback`. Tick **Autodesk Construction Cloud API** and **Data Management API**.
2. **ACC → Account Admin → Custom Integrations → Add custom integration**, and paste the **Client ID**. Without this you get *403 Forbidden*.
3. In PowerShell:
   - `copy .env.example .env`
   - `notepad .env`: fill in the Client ID and Client Secret, save and close.
   - `.venv\Scripts\python authorize.py`: sign in in the browser and click **Allow**.
   - `.venv\Scripts\python run_report.py projects`: you should see your ACC projects.

## 4. Connect to Codex

Run `pwd` in PowerShell to get your folder's full path. Below, that's written as `C:\Users\you\Documents\acc-reports-mcp`.

In the Codex app's **add MCP server** form:

| Field | What to put |
|---|---|
| Command to launch | `C:\Users\you\Documents\acc-reports-mcp\.venv\Scripts\python.exe` |
| Arguments | `C:\Users\you\Documents\acc-reports-mcp\start_server.py` |
| Environment variables | Empty. Or, for the fictional sample project: `ACC_SAMPLE_MODE` = `true` |
| Environment variable pass-through | Empty |
| Working directory | The folder path, or empty |

Don't put your Client ID or Secret in the form. The server reads them from `.env`.

**Or from the Codex command line:**

```
codex mcp add acc-reports -- C:\Users\you\Documents\acc-reports-mcp\.venv\Scripts\python.exe C:\Users\you\Documents\acc-reports-mcp\start_server.py
```

Then ask Codex: *"Use acc-reports to list my projects."*

Codex may ask permission the first time it uses each tool. Everything this server does is read-only. The ready-made prompts (`forms_report` and so on) may not appear in Codex, but every tool and report works if you ask in plain words.
