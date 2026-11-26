"""
Asset readiness: every asset grouped by category (system), with the forms
and issues linked to it, and a simple readiness call per asset.

Readiness rules (change them in readiness() below):
  Blocked      an open issue, or a failed check on a linked form
  In progress  has forms, but not all of them are closed
  Ready        has forms, all closed, nothing open or failed
  No forms     nothing linked yet
"""
from acc_reports_mcp import report_kit as kit

TITLE = "Asset readiness by system"
DESCRIPTION = ("Assets grouped by category, each with its linked forms and issues and a "
               "Ready / In progress / Blocked / No forms status. Good for commissioning and handover.")
OPTIONS = {
    "category": "Only categories whose name contains this text, e.g. 'Dock'",
    "asset_status": "Only assets whose ACC status contains this text, e.g. 'Installed'",
}

READINESS_ORDER = ["Blocked", "In progress", "Ready", "No forms"]
READINESS_TONE = {"Blocked": "bad", "In progress": "warn", "Ready": "good", "No forms": "none"}


def readiness(forms, open_issues, fails):
    if open_issues or fails:
        return "Blocked"
    if not forms:
        return "No forms"
    if all(f["status"] == "closed" for f in forms):
        return "Ready"
    return "In progress"


def build(project, category=None, asset_status=None):
    assets = kit.load_assets(project)
    links = kit.asset_links(project)
    forms_by_id = {f["id"]: f for f in kit.load_forms(project, with_assets=False)}
    issues_by_id = kit.load_issues(project)

    rows = []
    for a in assets.values():
        if category and category.lower() not in a["categoryName"].lower():
            continue
        if asset_status and asset_status.lower() not in a["statusName"].lower():
            continue
        linked = links.get(a["id"], {})
        forms = [forms_by_id[fid] for fid in linked.get("forms", []) if fid in forms_by_id]
        issue_ids = set(linked.get("issues", []))
        for f in forms:  # issues raised on the asset's forms count too
            issue_ids.update(i["id"] for i in f["allIssues"])
        issues = [issues_by_id[i] for i in issue_ids if i in issues_by_id]
        open_issues = [i for i in issues if i["open"]]
        fails = sum(f["counts"]["fail"] for f in forms)
        state = readiness(forms, open_issues, fails)
        rows.append({
            "id": a["id"], "name": a.get("clientAssetId") or a["id"], "description": a.get("description"),
            "category": a["categoryName"], "status": a["statusName"],
            "location": project.locations.get(a.get("locationId")) if a.get("locationId") else None,
            "forms": forms, "issues": issues, "openIssues": open_issues, "fails": fails,
            "documents": len(linked.get("documents", [])), "readiness": state,
        })

    systems = []
    for name, items in sorted(kit.group(rows, "category").items()):
        counts = kit.count_by(items, "readiness")
        systems.append({
            "name": name, "assets": sorted(items, key=lambda r: (READINESS_ORDER.index(r["readiness"]), r["name"])),
            "counts": counts, "ready_pct": kit.pct(counts.get("Ready", 0), len(items)),
            "bar": [(counts.get(s, 0), READINESS_TONE[s], s) for s in READINESS_ORDER],
            "openIssues": sum(len(r["openIssues"]) for r in items),
        })
    systems.sort(key=lambda s: (s["ready_pct"], s["name"]))

    totals = kit.count_by(rows, "readiness")
    return {
        "systems": systems,
        "blocked": [r for r in rows if r["readiness"] == "Blocked"],
        "tone": READINESS_TONE,
        "order": READINESS_ORDER,
        "summary": {
            "assets": len(rows),
            "ready": totals.get("Ready", 0),
            "ready_pct": kit.pct(totals.get("Ready", 0), len(rows)),
            "blocked": totals.get("Blocked", 0),
            "in_progress": totals.get("In progress", 0),
            "no_forms": totals.get("No forms", 0),
            "open_issues": sum(len(r["openIssues"]) for r in rows),
            "systems": len(systems),
        },
    }
