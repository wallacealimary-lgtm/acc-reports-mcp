"""
Helpers that report builders (reports/<name>/report.py) can use, so each
report stays short and readable. Import with:

    from acc_reports_mcp import report_kit as kit
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from .links import FormLinks, asset_links
from .reconstruct import FORM_STATUS, ISSUE_STATUS, issue_summary, reconstruct_form

__all__ = ["load_forms", "load_issues", "load_assets", "asset_links", "count_by", "pct", "days_since",
           "parse_date", "FORM_STATUS", "ISSUE_STATUS", "issue_summary", "reconstruct_form", "FormLinks"]


def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def days_since(value) -> int | None:
    d = parse_date(value)
    return (datetime.now(timezone.utc).date() - d).days if d else None


def pct(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def count_by(rows, key) -> dict:
    """Counter as a plain dict, biggest first. key is a field name or a function."""
    get = key if callable(key) else (lambda r: r.get(key))
    return dict(Counter(get(r) for r in rows).most_common())


def load_issues(project, details: bool = False) -> dict:
    """issue id -> issue summary (status, assignee, type, ...)."""
    return {i["id"]: issue_summary(project, i, details) for i in project.issues()}


def load_assets(project) -> dict:
    """asset id -> asset with readable category and status names added."""
    cats, stats = project.asset_categories, project.asset_statuses
    out = {}
    for a in project.assets():
        a = dict(a)
        a["categoryName"] = (cats.get(a.get("categoryId")) or {}).get("name") or "Uncategorised"
        a["statusName"] = (stats.get(a.get("statusId")) or {}).get("label") or "No status"
        out[a["id"]] = a
    return out


def load_forms(project, template: str | None = None, status: str | None = None,
               since: str | None = None, until: str | None = None, details: bool = False,
               with_assets: bool = True) -> list[dict]:
    """
    Every form on the project, fully rebuilt (answers, tables, linked
    issues, photos, assets), filtered by:
      template  part of the template name, e.g. "Electrical"
      status    form status, e.g. "closed" or "inProgress" (comma list ok)
      since / until   form date range, YYYY-MM-DD
    details=True also loads issue comments and photos (slower).
    """
    templates = project.form_templates
    template_ids = None
    if template:
        template_ids = {t["id"] for t in templates if template.lower() in (t.get("name") or "").lower()}
        if not template_ids:
            raise ValueError(f"No form template matches '{template}'. Templates: "
                             + ", ".join(t.get("name", "") for t in templates))
    wanted_status = {s.strip() for s in status.split(",")} if status else None
    lo, hi = parse_date(since), parse_date(until)

    forms = []
    for f in project.forms():
        if template_ids and f.get("formTemplateId") not in template_ids:
            continue
        if wanted_status and f.get("status") not in wanted_status \
                and FORM_STATUS.get(f.get("status"), "").lower() not in {s.lower() for s in wanted_status}:
            continue
        d = parse_date(f.get("formDate") or f.get("createdAt"))
        if (lo and d and d < lo) or (hi and d and d > hi):
            continue
        forms.append(f)

    links = FormLinks(project)
    raw_issues = {i["id"]: i for i in project.issues()} if any(
        "issue" in l["domain"] for ls in links.index.values() for l in ls) else {}
    assets = load_assets(project) if with_assets and any(
        "asset" in l["domain"] for ls in links.index.values() for l in ls) else {}
    return [reconstruct_form(project, f["id"], details=details, form=f, links=links,
                             issues_by_id=raw_issues, assets_by_id=assets) for f in forms]


def find_form(project, form) -> dict:
    """One form by id, number ('12' or '#12') or part of its name."""
    forms = project.forms()
    text = str(form).strip().lower()
    hits = [f for f in forms if f["id"].lower() == text or str(f.get("formNum")) == text.lstrip("#")]
    hits = hits or [f for f in forms if text in (f.get("name") or "").lower()]
    if not hits:
        raise ValueError(f"No form matches '{form}'.")
    if len(hits) > 1:
        raise ValueError(f"'{form}' matches {len(hits)} forms: "
                         + "; ".join(f"#{f.get('formNum')} {f.get('name')}" for f in hits[:10])
                         + ". Use the form number or id.")
    return hits[0]


def group(rows, key) -> dict:
    out = defaultdict(list)
    get = key if callable(key) else (lambda r: r.get(key))
    for r in rows:
        out[get(r)].append(r)
    return dict(out)
