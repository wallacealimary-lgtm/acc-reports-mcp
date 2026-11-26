"""
Forms by status: every form on the project, grouped by template and
status, with the issues linked to each one and any failed checks.
"""
from acc_reports_mcp import report_kit as kit

TITLE = "Forms by status"
DESCRIPTION = ("Every form grouped by template and status, with linked issues and failed checks. "
               "Shows which forms need attention.")
OPTIONS = {
    "template": "Only templates whose name contains this text, e.g. 'Electrical'",
    "status": "Only these statuses, e.g. 'inProgress' or 'closed' (comma list ok)",
    "since": "Forms dated on or after YYYY-MM-DD",
    "until": "Forms dated on or before YYYY-MM-DD",
}

# Order the statuses appear in, and the colour each one gets.
STATUS_ORDER = ["Draft", "In progress", "In review", "Submitted", "Closed", "Archived"]
STATUS_TONE = {"Draft": "none", "In progress": "warn", "In review": "info", "Submitted": "info",
               "Closed": "good", "Archived": "none"}


def build(project, template=None, status=None, since=None, until=None):
    forms = kit.load_forms(project, template=template, status=status, since=since, until=until)

    # One row per template: how many forms in each status.
    by_template = []
    for name, rows in sorted(kit.group(forms, lambda f: f["template"]["name"] or "No template").items()):
        counts = kit.count_by(rows, "statusLabel")
        by_template.append({
            "name": name,
            "total": len(rows),
            "counts": counts,
            "bar": [(counts.get(s, 0), STATUS_TONE.get(s, "none"), s) for s in STATUS_ORDER if counts.get(s)],
            "openIssues": sum(f["counts"]["openIssues"] for f in rows),
            "fails": sum(f["counts"]["fail"] for f in rows),
        })

    # Forms someone should look at: open issues or failed checks.
    attention = [f for f in forms if f["counts"]["openIssues"] or f["counts"]["fail"]]
    attention.sort(key=lambda f: (-f["counts"]["openIssues"], -f["counts"]["fail"], f["number"] or 0))

    statuses = kit.count_by(forms, "statusLabel")
    closed = statuses.get("Closed", 0)
    return {
        "forms": sorted(forms, key=lambda f: (STATUS_ORDER.index(f["statusLabel"]) if f["statusLabel"] in STATUS_ORDER else 99,
                                              f["template"]["name"] or "", f["number"] or 0)),
        "by_template": by_template,
        "attention": attention,
        "statuses": statuses,
        "status_tone": STATUS_TONE,
        "summary": {
            "forms": len(forms),
            "closed": closed,
            "closed_pct": kit.pct(closed, len(forms)),
            "forms_with_open_issues": sum(1 for f in forms if f["counts"]["openIssues"]),
            "open_issues": sum(f["counts"]["openIssues"] for f in forms),
            "failed_checks": sum(f["counts"]["fail"] for f in forms),
            "by_status": statuses,
        },
    }
