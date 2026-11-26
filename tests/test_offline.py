"""
Offline checks, no Autodesk login needed (uses the sample project).
Run:  python -m tests.test_offline   (from the repo folder)
"""
import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ACC_SAMPLE_MODE"] = "true"
os.environ["ACC_REPORTS_DIR"] = tempfile.mkdtemp(prefix="acc-reports-test-")


def test_read_only_client():
    from acc_reports_mcp import aps
    c = aps.Client()
    try:
        c.query("/construction/issues/v1/projects/x/issues", {})
    except aps.ReadOnlyViolation:
        pass
    else:
        raise AssertionError("POST to a non-search endpoint was not refused")
    code = "\n".join(p.read_text() for p in (ROOT / "acc_reports_mcp").glob("*.py"))
    assert not re.search(r"\.(put|patch|delete)\(", code), "write call found in the server code"


def test_form_rebuild():
    from acc_reports_mcp import acc
    from acc_reports_mcp.reconstruct import reconstruct_form
    p = acc.open_project(None)
    r = reconstruct_form(p, "F2")
    assert r["counts"]["fail"] == 1 and r["counts"]["tables"] == 1 and r["counts"]["photos"] == 2
    q = next(i for s in r["sections"] for i in s["items"] if i.get("label") == "Oil levels correct on all compressors")
    assert q["value"] == "Fail" and q["issues"][0]["number"] == 1 and q["photos"][0]["dataUri"]
    assert q["issues"][0]["comments"], "issue comments missing"
    table = next(i for s in r["sections"] for i in s["items"] if i["kind"] == "table")
    assert table["rows"][1] == ["Discharge", "95.2", "79", "No: high"]
    assert [i["number"] for i in r["issues"]] == [2], "whole-form issue missing"


def test_reports():
    from acc_reports_mcp import acc, engine
    p = acc.open_project(None)
    expect = {"forms_by_status": {}, "asset_readiness": {}, "open_issues": {},
              "form_record": {"form": "2"}}
    assert set(expect) <= set(engine.available())
    for name, opts in expect.items():
        out = engine.run(name, p, opts)
        html = Path(out["file"]).read_text()
        assert "SAMPLE DATA" in html and len(html) > 3000, name
    assert engine.run("asset_readiness", p)["summary"]["blocked"] == 3
    assert engine.run("open_issues", p)["summary"]["overdue"] == 3


async def _mcp_roundtrip():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    # Started exactly the way Claude starts it: python <repo>/start_server.py, from another folder.
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "start_server.py")], cwd=tempfile.gettempdir(),
                                   env={**os.environ, "ACC_SAMPLE_MODE": "true"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            prompts = {pr.name for pr in (await s.list_prompts()).prompts}
            res = await s.call_tool("get_form", {"project": "sample", "form": "2"})
            form = json.loads(res.content[0].text)
            rep = await s.call_tool("run_report", {"project": "sample", "report": "forms_by_status",
                                                   "open_in_browser": False})
            return tools, prompts, form, json.loads(rep.content[0].text)


def test_mcp_server():
    tools, prompts, form, rep = asyncio.run(_mcp_roundtrip())
    assert {"list_projects", "list_issues", "get_issue", "list_assets", "list_forms", "get_form",
            "get_links", "list_reports", "run_report"} <= tools, tools
    assert {"forms_report", "commissioning_check", "weekly_issues", "form_pack"} <= prompts
    assert form["counts"]["fail"] == 1 and "base64" not in json.dumps(form)
    assert rep["summary"]["forms"] == 6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all offline checks passed")
