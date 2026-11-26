"""
Rebuilds a complete ACC form, the way it looks in ACC: header details,
every section in order, every question with its answer, every table with
its rows, signatures, and everything linked to it (issues with their
comments and photos, photos on questions, assets, documents).

The form's OWN layout is used (form.nativeForm.layoutId), not the
template's current one: templates get edited, and field ids change when
they do, so an older form must be read with the layout it was filled in on.
"""
from .acc import DOC_DOMAIN
from .links import FormLinks

FORM_STATUS = {
    "draft": "Draft", "inProgress": "In progress", "inReview": "In review", "submitted": "Submitted",
    "closed": "Closed", "archived": "Archived", "void": "Void", "rejected": "Rejected",
}
ISSUE_STATUS = {
    "draft": "Draft", "open": "Open", "pending": "Pending", "in_progress": "In progress",
    "in_review": "In review", "completed": "Completed", "not_approved": "Not approved",
    "in_dispute": "In dispute", "closed": "Closed", "answered": "Answered", "work_completed": "Work completed",
    "ready_to_inspect": "Ready to inspect", "not_started": "Not started",
}
OPEN_ISSUE_STATUSES = {"draft", "open", "pending", "in_progress", "in_review", "in_dispute",
                       "not_approved", "work_completed", "ready_to_inspect", "not_started", "answered"}
TOGGLE_WORDS = {"p/f": ("Pass", "Fail"), "y/n": ("Yes", "No"), "c/nc": ("Compliant", "Not compliant")}


def name_of(project, user_id: str | None) -> str | None:
    if not user_id:
        return None
    return project.users.get(user_id, user_id)


def _value_of(entry: dict):
    """(key, value) of the first *Val key that is set on a value entry."""
    for k, v in entry.items():
        if k.endswith("Val") and v not in (None, ""):
            return k, v
    return None, None


def _answer(item: dict, entry: dict | None) -> dict:
    """Display text plus a normalised answer (pass/fail/na/yes/no) for one question."""
    if not entry:
        return {"value": None, "answer": None}
    key, raw = _value_of(entry)
    if key is None:
        return {"value": None, "answer": None}
    if key == "toggleVal":
        word = str(raw).strip().lower()
        yes, no = TOGGLE_WORDS.get(item.get("modifier", ""), ("Yes", "No"))
        if word in ("true", "1", "yes", "pass"):
            return {"value": yes, "answer": "pass" if yes == "Pass" else "yes"}
        if word in ("false", "0", "no", "fail"):
            return {"value": no, "answer": "fail" if no == "Fail" else "no"}
        if word in ("na", "n/a", "null", "none"):
            return {"value": "N/A", "answer": "na"}
        return {"value": str(raw), "answer": None}
    if key == "arrayVal" and isinstance(raw, list):
        return {"value": ", ".join(str(x) for x in raw), "answer": None}
    if key == "numberVal":
        try:
            f = float(raw)
            return {"value": str(int(f)) if f.is_integer() else str(f), "answer": None}
        except (TypeError, ValueError):
            pass
    if key == "svgVal":
        return {"value": "Signed", "answer": None, "svg": raw}
    return {"value": str(raw), "answer": None}


def _table(section_resp: dict, section_uid: str, item: dict, tabular: list[dict]) -> dict:
    cols = section_resp.get("tableColumns") or []
    if isinstance(cols, dict):
        cols = cols.get(section_uid) or cols.get(item.get("uid")) or [c for v in cols.values() for c in v]
    cols = sorted(cols, key=lambda c: c.get("sortIndex", 0))
    schema = item.get("schema")
    rows = []
    # Each row is one entry. ACC names a cell by columnName when it returns
    # a form (e.g. "item", "quantity"), and by columnId (the column uid) when
    # you write one, so match a column on any of its names.
    entries = [e for e in tabular if not schema or schema in (e.get("schema"), e.get("fieldId"), e.get("name"))]
    for entry in sorted(entries, key=lambda e: e.get("rank") or 0):
        for row in (entry.get("rows") or [entry]):
            if row.get("deleted"):
                continue
            cells = {}
            for c in row.get("columns", []):
                for key in (c.get("columnId"), c.get("columnName"), c.get("columnKey")):
                    if key:
                        cells[key] = _value_of(c)[1]
            rows.append([_fmt(next((cells[k] for k in (c.get("uid"), c.get("columnKey"), c.get("valueName"))
                                    if k in cells), None)) for c in cols])
    return {"kind": "table", "label": item.get("label") or section_resp.get("section", {}).get("label"),
            "columns": [c.get("label") or c.get("columnKey") for c in cols], "rows": rows}


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def issue_summary(project, issue: dict, details: bool = False) -> dict:
    out = {
        "id": issue["id"],
        "number": issue.get("displayId"),
        "title": issue.get("title"),
        "status": issue.get("status"),
        "statusLabel": ISSUE_STATUS.get(issue.get("status"), issue.get("status")),
        "open": issue.get("status") in OPEN_ISSUE_STATUSES,
        "type": project.issue_types.get(issue.get("issueSubtypeId")),
        "assignee": name_of(project, issue.get("assignedTo")),
        "dueDate": issue.get("dueDate"),
        "createdAt": issue.get("createdAt"),
        "closedAt": issue.get("closedAt"),
        "location": project.locations.get(issue.get("locationId")) or issue.get("locationDetails"),
        "description": issue.get("description"),
        "commentCount": issue.get("commentCount"),
    }
    if details:
        out["comments"] = [{"by": name_of(project, c.get("createdBy")), "at": c.get("createdAt"), "text": c.get("body")}
                           for c in project.issue_comments(issue["id"])]
        photos = []
        if issue.get("attachmentCount", 1):
            for a in project.issue_attachments(issue["id"]):
                photo = {"title": a["name"], "fileType": a["fileType"]}
                if a["fileType"] in ("jpg", "jpeg", "png", "gif", "webp", "svg") and a.get("url"):
                    raw = project.download(a["url"])
                    if raw:
                        import base64
                        mime = "image/svg+xml" if a["fileType"] == "svg" else f"image/{'jpeg' if a['fileType'] == 'jpg' else a['fileType']}"
                        photo["dataUri"] = f"data:{mime};base64," + base64.b64encode(raw).decode()
                photos.append(photo)
        out["attachments"] = photos
    return out


def _photo_summary(project, p: dict) -> dict:
    return {"id": p.get("id"), "title": p.get("title") or "Photo", "takenAt": p.get("takenAt"),
            "by": name_of(project, p.get("createdBy")), "description": p.get("description"),
            "dataUri": p.get("dataUri")}


def reconstruct_form(project, form_id: str, details: bool = True, form: dict | None = None,
                     links: FormLinks | None = None, issues_by_id: dict | None = None,
                     assets_by_id: dict | None = None) -> dict:
    """Everything about one form. details=False skips issue comments/photos (faster, for big reports)."""
    form = form or project.form(form_id)
    native = form.get("nativeForm") or {}
    links = links or FormLinks(project, form["id"])
    template = next((t for t in project.form_templates if t["id"] == form.get("formTemplateId")), {})
    warnings: list[str] = []

    # -- everything linked to the form, fetched once
    issue_ids = links.of(form["id"], "issue")
    if issues_by_id is None:
        issues_by_id = {}
        for iid in issue_ids:
            try:
                issues_by_id[iid] = project.issue(iid)
            except Exception as e:  # deleted or no access
                warnings.append(f"Linked issue {iid} could not be read: {e}")
    issues = {iid: issue_summary(project, issues_by_id[iid], details) for iid in issue_ids if iid in issues_by_id}
    photo_ids = links.of(form["id"], "photo")
    photos = {}
    if photo_ids:
        try:
            photos = {p["id"]: _photo_summary(project, p) for p in project.photos(photo_ids)}
        except Exception as e:
            warnings.append(f"Photos could not be read: {e}")

    # -- answers by field id
    values = {}
    for v in native.get("customValues") or []:
        if not v.get("deleted"):
            values[v.get("fieldId")] = v
    tabular = native.get("tabularValues") or []

    sections = []
    used_issue_ids, used_photo_ids = set(), set()
    layout_id = native.get("layoutId")
    if layout_id:
        layout = project.layout(layout_id)
        for sec in sorted(layout.get("sections", []), key=lambda s: s.get("sortIndex", s.get("displayIndex", 0))):
            sec_resp = project.section(layout_id, sec["uid"])
            items = []
            for item in sorted(sec_resp.get("sectionItems", []), key=lambda i: i.get("sortIndex", 0)):
                if item.get("type") == "table":
                    items.append(_table(sec_resp, sec["uid"], item, tabular))
                    continue
                schema = item.get("schema")
                if not schema:
                    items.append({"kind": "text", "label": item.get("label"), "description": item.get("description")})
                    continue
                ans = _answer(item, values.get(schema))
                field_keys = {schema, item.get("uid")}
                q_issue_ids = [i for k in field_keys if k for i in links.of(form["id"], "issue", k)]
                q_photo_ids = [p for k in field_keys if k for p in links.of(form["id"], "photo", k)]
                used_issue_ids.update(q_issue_ids)
                used_photo_ids.update(q_photo_ids)
                q = {"kind": "signature" if ans.get("svg") else "question", "label": item.get("label"),
                     "description": item.get("description") or None, "required": bool(item.get("isRequired")),
                     "valueType": item.get("valueName"), **ans,
                     "issues": [issues[i] for i in q_issue_ids if i in issues],
                     "photos": [photos[p] for p in q_photo_ids if p in photos]}
                items.append(q)
            sections.append({"title": sec.get("label"), "description": sec.get("description") or None, "items": items})
    elif native.get("pdfValues"):
        sections.append({"title": "PDF form fields", "description": "This form is a PDF template; values shown as filled in.",
                         "items": [{"kind": "question", "label": p.get("name"), "value": _fmt(p.get("value")),
                                    "answer": None, "issues": [], "photos": []} for p in native["pdfValues"]]})
    else:
        warnings.append("This form has no web layout, so only its header could be rebuilt.")

    # -- totals
    questions = [i for s in sections for i in s["items"] if i["kind"] == "question"]
    answers = [q.get("answer") for q in questions]
    status_history = [
        {"status": FORM_STATUS.get(k, k), "at": v.get("at"), "by": name_of(project, v.get("by"))}
        for k, v in (form.get("lastStatusChanges") or {}).items() if isinstance(v, dict)
    ]
    status_history.sort(key=lambda s: s["at"] or "")
    all_issues = list(issues.values())

    asset_ids = links.of(form["id"], "asset")
    assets = []
    for aid in asset_ids:
        a = (assets_by_id or {}).get(aid)
        assets.append({"id": aid, "name": a.get("clientAssetId") if a else aid,
                       "description": a.get("description") if a else None})

    return {
        "id": form["id"],
        "number": form.get("formNum"),
        "name": form.get("name"),
        "template": {"id": template.get("id"), "name": template.get("name"),
                     "type": (template.get("templateType") or "").replace("pg.template_type.", "").replace("_", " ")},
        "status": form.get("status"),
        "statusLabel": FORM_STATUS.get(form.get("status"), form.get("status")),
        "formDate": form.get("formDate"),
        "dueDate": form.get("dueDate"),
        "createdAt": form.get("createdAt"),
        "createdBy": name_of(project, form.get("createdBy")),
        "assignee": name_of(project, form.get("assigneeId")),
        "location": project.locations.get(form.get("locationId")) if form.get("locationId") else None,
        "description": form.get("description"),
        "notes": form.get("notes"),
        "submittedAt": form.get("lastSubmittedAt"),
        "submittedBy": name_of(project, form.get("lastSubmittedBy")),
        "statusHistory": status_history,
        "sections": sections,
        "issues": [i for iid, i in issues.items() if iid not in used_issue_ids],  # linked to the whole form
        "photos": [p for pid, p in photos.items() if pid not in used_photo_ids],
        "allIssues": all_issues,
        "assets": assets,
        "documents": links.of(form["id"], DOC_DOMAIN.split("-")[-1]),
        "counts": {
            "questions": len(questions),
            "answered": sum(1 for q in questions if q.get("value") not in (None, "")),
            # Only Pass/Fail questions count as pass/fail. A Yes/No answer is not
            # good or bad by itself ("Any defects? No" is good news).
            "pass": answers.count("pass"),
            "fail": answers.count("fail"),
            "yes": answers.count("yes"),
            "no": answers.count("no"),
            "na": answers.count("na"),
            "tables": sum(1 for s in sections for i in s["items"] if i["kind"] == "table"),
            "issues": len(all_issues),
            "openIssues": sum(1 for i in all_issues if i["open"]),
            "photos": len(photos),
        },
        "warnings": warnings,
    }


def strip_images(obj):
    """Same structure without embedded image data (for sending to Claude as JSON)."""
    if isinstance(obj, dict):
        return {k: ("<image: shown in the HTML report>" if k in ("dataUri", "svg") and v else strip_images(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_images(x) for x in obj]
    return obj
