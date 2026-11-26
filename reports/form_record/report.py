"""
Form record: rebuilds one form exactly as filled in (every section,
answer, table, signature), with its linked issues (comments and photos),
question photos and assets. Print it to PDF from the browser.

Give `template` instead of `form` to get a pack: every form from that
template in one printable document (e.g. a handover pack).
"""
from acc_reports_mcp import report_kit as kit

TITLE = "Form record"
DESCRIPTION = ("A complete, printable copy of one form (or a pack of forms from one template): "
               "answers, tables, signatures, linked issues with comments and photos, assets.")
OPTIONS = {
    "form": "The form: its id, its number (e.g. '12') or part of its name",
    "template": "Instead of one form: every form from templates containing this text",
    "status": "With template: only these statuses, e.g. 'closed'",
}
MAX_FORMS = 50  # a pack bigger than this gets slow and huge


def build(project, form=None, template=None, status=None):
    if not form and not template:
        raise ValueError("Say which form (form=...) or which template for a pack (template=...).")
    if form:
        f = kit.find_form(project, form)
        records = [kit.reconstruct_form(project, f["id"], details=True, form=f,
                                        assets_by_id=kit.load_assets(project))]
        suffix = f"form-{f.get('formNum')}"
    else:
        records = kit.load_forms(project, template=template, status=status, details=True)[:MAX_FORMS]
        suffix = template
    return {
        "records": records,
        "file_suffix": suffix,
        "summary": {
            "forms": len(records),
            "names": [f"#{r['number']} {r['name']}" for r in records][:20],
            "open_issues": sum(r["counts"]["openIssues"] for r in records),
            "failed_checks": sum(r["counts"]["fail"] for r in records),
            "warnings": [w for r in records for w in r["warnings"]],
        },
    }
