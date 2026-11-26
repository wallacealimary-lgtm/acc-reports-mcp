"""
Turns ACC's Relationship API into simple lookups:
"which issues / photos / assets / documents are linked to this form?"

Two shapes of form link exist:
  whole form   domain=autodesk-construction-form, type=form,      id=<formId>
  one question domain=autodesk-construction-form, type=formfield, id=urn:adsk:form.field:<formId>/<fieldId>
"""
from collections import defaultdict

from .acc import ASSET_DOMAIN, FORM_DOMAIN

FIELD_PREFIX = "urn:adsk:form.field:"


def _form_side(entity: dict) -> tuple[str, str | None] | None:
    """(form_id, field_id or None) if this entity is a form or form question."""
    if entity.get("domain") != FORM_DOMAIN:
        return None
    if entity.get("type") == "form":
        return entity["id"], None
    eid = entity.get("id", "")
    if entity.get("type") == "formfield" and eid.startswith(FIELD_PREFIX):
        form_id, _, field_id = eid[len(FIELD_PREFIX):].partition("/")
        return form_id, field_id or None
    return None


class FormLinks:
    """index[form_id] -> list of {domain, type, id, field}."""

    def __init__(self, project, form_id: str | None = None):
        self.index: dict[str, list[dict]] = defaultdict(list)
        if form_id:
            rels = project.relationships(FORM_DOMAIN, "form", form_id)
            rels += [r for r in project.relationships(FORM_DOMAIN, "formfield")
                     if any(e.get("id", "").startswith(f"{FIELD_PREFIX}{form_id}/") for e in r["entities"])]
        else:
            rels = project.relationships(FORM_DOMAIN)
        seen = set()
        for rel in rels:
            forms = [(e, _form_side(e)) for e in rel["entities"]]
            for e, side in forms:
                if not side:
                    continue
                for other in rel["entities"]:
                    if other is e or other.get("domain") == FORM_DOMAIN:
                        continue
                    key = (side, other["domain"], other["id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    self.index[side[0]].append({"domain": other["domain"], "type": other["type"],
                                                "id": other["id"], "field": side[1]})

    def of(self, form_id: str, domain_contains: str, field: str | None | bool = False) -> list[str]:
        """Ids linked to a form. field=False: any; None: whole-form only; "<id>": that question only."""
        out = []
        for link in self.index.get(form_id, []):
            if domain_contains not in link["domain"]:
                continue
            if field is not False and link["field"] != field:
                continue
            if link["id"] not in out:
                out.append(link["id"])
        return out


def asset_links(project) -> dict[str, dict[str, list[str]]]:
    """asset_id -> {"forms": [...], "issues": [...], "documents": [...]}"""
    out: dict = defaultdict(lambda: defaultdict(list))
    for rel in project.relationships(ASSET_DOMAIN):
        assets = [e for e in rel["entities"] if e.get("domain") == ASSET_DOMAIN]
        others = [e for e in rel["entities"] if e.get("domain") != ASSET_DOMAIN]
        for a in assets:
            for o in others:
                side = _form_side(o)
                if side:
                    bucket, oid = "forms", side[0]
                elif "issue" in o["domain"]:
                    bucket, oid = "issues", o["id"]
                elif "photo" in o["domain"]:
                    bucket, oid = "photos", o["id"]
                elif "document" in o["domain"]:
                    bucket, oid = "documents", o["id"]
                else:
                    bucket, oid = "other", o["id"]
                if oid not in out[a["id"]][bucket]:
                    out[a["id"]][bucket].append(oid)
    return out
