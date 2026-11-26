"""
Open issues: who has what, and how old it is. A weekly-meeting view.
Each issue also shows the form or asset it is linked to, if any.
"""
from acc_reports_mcp import report_kit as kit
from acc_reports_mcp.acc import ASSET_DOMAIN

TITLE = "Open issues by owner and age"
DESCRIPTION = ("Every open issue grouped by who it's assigned to, with age buckets, overdue flags "
               "and the form or asset it belongs to.")
OPTIONS = {
    "type": "Only issue types containing this text, e.g. 'Quality'",
    "assignee": "Only issues assigned to someone whose name contains this text",
}

# Age buckets in days: (label, up to and including this many days)
AGE_BUCKETS = [("0–7 days", 7), ("8–30 days", 30), ("31–90 days", 90), ("Over 90 days", 10 ** 6)]


def build(project, type=None, assignee=None):
    issues = [i for i in kit.load_issues(project).values() if i["open"]]
    if type:
        issues = [i for i in issues if type.lower() in (i["type"] or "").lower()]
    if assignee:
        issues = [i for i in issues if assignee.lower() in (i["assignee"] or "").lower()]

    # What each issue is linked to (forms and assets), from the Relationship API.
    form_names = {f["id"]: f"#{f.get('formNum')} {f.get('name')}" for f in project.forms()}
    asset_names = {a["id"]: a.get("clientAssetId") for a in project.assets()} if issues else {}
    context = {}
    links = kit.FormLinks(project)
    for form_id, rows in links.index.items():
        for l in rows:
            if "issue" in l["domain"]:
                context.setdefault(l["id"], []).append("Form " + form_names.get(form_id, form_id))
    for aid, linked in kit.asset_links(project).items():
        for iid in linked.get("issues", []):
            context.setdefault(iid, []).append("Asset " + (asset_names.get(aid) or aid))

    for i in issues:
        i["age"] = kit.days_since(i["createdAt"]) or 0
        i["bucket"] = next(label for label, top in AGE_BUCKETS if i["age"] <= top)
        due = kit.parse_date(i["dueDate"])
        i["overdue"] = bool(due and kit.days_since(due) > 0)
        i["linkedTo"] = context.get(i["id"], [])

    owners = []
    for name, rows in kit.group(issues, lambda i: i["assignee"] or "Unassigned").items():
        rows.sort(key=lambda i: (-int(i["overdue"]), -i["age"]))
        counts = kit.count_by(rows, "bucket")
        owners.append({"name": name, "issues": rows, "overdue": sum(i["overdue"] for i in rows),
                       "bar": [(counts.get(b, 0), t, b) for (b, _), t in zip(AGE_BUCKETS, ["good", "info", "warn", "bad"])]})
    owners.sort(key=lambda o: (-o["overdue"], -len(o["issues"])))

    return {
        "owners": owners,
        "buckets": [b for b, _ in AGE_BUCKETS],
        "by_type": kit.count_by(issues, lambda i: i["type"] or "No type"),
        "summary": {
            "open_issues": len(issues),
            "overdue": sum(i["overdue"] for i in issues),
            "unassigned": sum(1 for i in issues if not i["assignee"]),
            "older_than_30_days": sum(1 for i in issues if i["age"] > 30),
            "owners": len(owners),
        },
    }
