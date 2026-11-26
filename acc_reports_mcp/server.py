"""
The MCP server: the list of tools Claude can use, and the prompts you
can pick from a menu. Every tool is read-only.

Claude reads each tool's docstring to decide when to use it, so the
docstrings are written for Claude: what it does, when to use it, what
comes back.

Run it directly to check it starts:   python start_server.py
"""
import webbrowser
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import acc, auth, config, engine
from .reconstruct import ISSUE_STATUS, issue_summary, reconstruct_form, strip_images
from .report_kit import find_form, load_assets, load_forms

mcp = FastMCP(
    name="acc-reports",
    instructions=(
        "Read-only tools for Autodesk Construction Cloud (ACC): projects, issues and comments, "
        "assets, forms (fully rebuilt, with photos, tables and linked issues) and relationships, "
        "plus HTML reports. Nothing here can change ACC data. "
        "Every tool takes `project`: a project name (or part of one) or id; call list_projects if unsure. "
        "For a finished, shareable document use run_report (list_reports shows what exists); "
        "for a quick answer in chat use the list_/get_ tools. "
        + ("SAMPLE MODE is on: all data is fictional sample data, say so in answers." if config.SAMPLE_MODE else "")
    ),
)


# ------------------------------------------------------------------ setup

@mcp.tool()
def who_am_i() -> dict:
    """Which Autodesk account the server is signed in as, and its (read-only) scopes. Use to check setup."""
    if config.SAMPLE_MODE:
        return {"name": "Sample mode", "email": None, "scopes": "none: fictional sample data"}
    return auth.who_am_i()


@mcp.tool()
def list_projects() -> list[dict]:
    """Every ACC project the signed-in user can see: name, id, hub, region. Call first if the project is unclear."""
    return acc.list_projects()


# ----------------------------------------------------------------- issues

@mcp.tool()
def list_issues(project: str, status: str | None = None, assignee: str | None = None,
                type: str | None = None, limit: int = 200) -> dict:
    """
    Issues on a project, newest first, as short summaries (number, title,
    status, type, assignee, due date, location).
    status: e.g. "open", "closed", "in_review" (comma list ok).
    assignee / type: filter by part of the name.
    """
    p = acc.open_project(project)
    rows = [issue_summary(p, i) for i in p.issues(status)]
    if assignee:
        rows = [r for r in rows if assignee.lower() in (r["assignee"] or "").lower()]
    if type:
        rows = [r for r in rows if type.lower() in (r["type"] or "").lower()]
    rows.sort(key=lambda r: r["createdAt"] or "", reverse=True)
    for r in rows:
        r.pop("description", None)
    counts: dict = {}
    for r in rows:
        counts[r["statusLabel"]] = counts.get(r["statusLabel"], 0) + 1
    return {"project": p.name, "total": len(rows), "byStatus": counts, "issues": rows[:limit],
            "truncated": len(rows) > limit, "knownStatuses": list(ISSUE_STATUS)}


@mcp.tool()
def get_issue(project: str, issue: str) -> dict:
    """
    One issue in full: description, all comments, attachments, and what it
    is linked to. `issue` is the issue number (e.g. "12") or its id.
    """
    p = acc.open_project(project)
    text = issue.strip().lstrip("#")
    match = next((i for i in p.issues() if i["id"] == text or str(i.get("displayId")) == text), None)
    if not match:
        raise ValueError(f"No issue '{issue}' on {p.name}.")
    out = issue_summary(p, match, details=True)
    linked = []
    for rel in p.relationships(acc.ISSUE_DOMAIN, None, match["id"]):
        for e in rel["entities"]:
            if e["id"] != match["id"]:
                linked.append({"domain": e["domain"], "type": e["type"], "id": e["id"]})
    out["linkedTo"] = linked
    return strip_images(out)


# ----------------------------------------------------------------- assets

@mcp.tool()
def list_assets(project: str, category: str | None = None, status: str | None = None, limit: int = 300) -> dict:
    """
    Assets on a project with readable category and status names.
    category / status: filter by part of the name, e.g. category="Dock".
    """
    p = acc.open_project(project)
    rows = []
    for a in load_assets(p).values():
        if category and category.lower() not in a["categoryName"].lower():
            continue
        if status and status.lower() not in a["statusName"].lower():
            continue
        rows.append({"id": a["id"], "name": a.get("clientAssetId"), "description": a.get("description"),
                     "category": a["categoryName"], "status": a["statusName"],
                     "location": p.locations.get(a.get("locationId")) if a.get("locationId") else None})
    rows.sort(key=lambda r: (r["category"], r["name"] or ""))
    return {"project": p.name, "total": len(rows), "assets": rows[:limit], "truncated": len(rows) > limit}


# ------------------------------------------------------------------ forms

@mcp.tool()
def list_form_templates(project: str) -> list[dict]:
    """Form templates on a project (name, type, id) with how many forms use each."""
    p = acc.open_project(project)
    counts: dict = {}
    for f in p.forms():
        counts[f.get("formTemplateId")] = counts.get(f.get("formTemplateId"), 0) + 1
    return [{"id": t["id"], "name": t.get("name"), "type": (t.get("templateType") or "").replace("pg.template_type.", ""),
             "forms": counts.get(t["id"], 0)} for t in p.form_templates]


@mcp.tool()
def list_forms(project: str, template: str | None = None, status: str | None = None,
               since: str | None = None, until: str | None = None, limit: int = 300) -> dict:
    """
    Forms on a project as summaries: number, name, template, status, date,
    linked assets, issue counts (open), pass/fail counts.
    template: part of the template name. status: e.g. "closed", "inProgress".
    since / until: form date range, YYYY-MM-DD.
    """
    p = acc.open_project(project)
    forms = load_forms(p, template=template, status=status, since=since, until=until)
    rows = [{"id": f["id"], "number": f["number"], "name": f["name"], "template": f["template"]["name"],
             "status": f["statusLabel"], "date": f["formDate"], "assets": [a["name"] for a in f["assets"]],
             **{k: f["counts"][k] for k in ("questions", "answered", "pass", "fail", "issues", "openIssues", "photos")}}
            for f in forms]
    return {"project": p.name, "total": len(rows), "forms": rows[:limit], "truncated": len(rows) > limit}


@mcp.tool()
def get_form(project: str, form: str) -> dict:
    """
    Rebuild one form completely, as filled in: header details, every section
    and question with its answer, tables with their rows, signatures, photos
    on questions, linked issues (with comments) and linked assets.
    `form` is the form number (e.g. "12"), its id, or part of its name.
    Images are left out of this answer; run_report("form_record") makes a
    printable page with the photos in it.
    """
    p = acc.open_project(project)
    f = find_form(p, form)
    return strip_images(reconstruct_form(p, f["id"], details=True, form=f, assets_by_id=load_assets(p)))


# ---------------------------------------------------------- relationships

@mcp.tool()
def get_links(project: str, item_type: str, item_id: str) -> dict:
    """
    Everything linked to one item (via ACC's Relationship API).
    item_type: "issue", "form", "asset" or "photo". item_id: the item's id
    (from list_issues / list_forms / list_assets).
    """
    domains = {"issue": acc.ISSUE_DOMAIN, "form": acc.FORM_DOMAIN, "asset": acc.ASSET_DOMAIN, "photo": acc.PHOTO_DOMAIN}
    if item_type not in domains:
        raise ValueError("item_type must be one of: " + ", ".join(domains))
    p = acc.open_project(project)
    linked = []
    for rel in p.relationships(domains[item_type], None, item_id):
        for e in rel["entities"]:
            if e["id"] != item_id:
                linked.append({"domain": e["domain"], "type": e["type"], "id": e["id"], "linkedOn": e.get("createdOn")})
    return {"item": {"type": item_type, "id": item_id}, "links": linked}


# ---------------------------------------------------------------- reports

@mcp.tool()
def list_reports() -> dict:
    """The reports that can be made with run_report: name, what it shows, and its options."""
    return engine.available()


@mcp.tool()
def run_report(project: str, report: str, options: dict | None = None, open_in_browser: bool = True) -> dict:
    """
    Make a report as an HTML page (opens in the browser; print to PDF from there).
    report: a name from list_reports, e.g. "forms_by_status", "asset_readiness",
    "form_record", "open_issues". options: that report's options, e.g.
    {"template": "Electrical", "status": "closed"}.
    Returns the file path and a summary of the numbers, so you can describe the result.
    """
    p = acc.open_project(project)
    result = engine.run(report, p, options or {})
    if open_in_browser:
        webbrowser.open(Path(result["file"]).as_uri())
    return result


# ---------------------------------------------------------------- prompts
# Prompts are ready-made requests you pick from a menu (in Claude Code type
# "/" and look for acc-reports). They fill in the blanks and hand Claude the
# full instruction; Claude then uses the tools above.

@mcp.prompt()
def forms_report(project: str, template: str = "") -> str:
    """Forms report: progress by status, plus what needs attention."""
    scope = f'forms from templates matching "{template}"' if template else "all forms"
    return (f"Run the forms_by_status report for {project} ({scope}"
            + (f', options {{"template": "{template}"}}' if template else "") + "). "
            "Then summarise in five bullet points: overall progress, the template furthest behind, "
            "forms with open issues (who owns them), any failed checks, and one suggested next action.")


@mcp.prompt()
def commissioning_check(project: str, system: str) -> str:
    """What's stopping a system (asset category) from being ready?"""
    return (f'Run the asset_readiness report for {project} with options {{"category": "{system}"}}. '
            "List every Blocked asset with the reason (open issue and owner, or failed check), then the "
            "In progress assets and which forms are still open. Finish with what must happen for the "
            f"whole {system} system to be Ready.")


@mcp.prompt()
def weekly_issues(project: str) -> str:
    """Weekly issues review: who owns what, what's overdue."""
    return (f"Run the open_issues report for {project}. Then give me a short agenda for the weekly "
            "meeting: overdue issues by owner first, then anything unassigned, then issues older than 30 days.")


@mcp.prompt()
def form_pack(project: str, template: str, status: str = "closed") -> str:
    """Printable pack of every form from one template (e.g. for handover)."""
    return (f'Run the form_record report for {project} with options {{"template": "{template}", "status": "{status}"}}. '
            "Tell me how many forms are in the pack, and flag any with open issues or failed checks.")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
