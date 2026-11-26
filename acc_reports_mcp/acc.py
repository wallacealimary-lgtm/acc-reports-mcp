"""
Reads one ACC project's data: issues, forms, assets, relationships,
photos, members. Every method is a READ.

Two interchangeable versions:
  LiveProject    talks to Autodesk (needs your sign-in)
  SampleProject  reads the fictional sample bundle in samples/ (no sign-in)

Everything else in the server (form reconstruction, reports) only uses
the methods below, so it works the same against either.

Endpoint notes (checked live, Nov 2026):
  - Construction APIs want the bare project GUID, no "b." prefix, plus an
    x-ads-region header (US / EMEA / AUS) for non-US hubs.
  - Forms: list via v2 with includeNativeFormValues=true, which returns
    each form's answers (customValues) and table rows (tabularValues).
    Layouts are v1, layout sections are v2.
  - Assets: v2 list uses cursorState paging; categories/statuses are v1.
  - Relationships: search pages with a continuationToken.
  - Photos: POST photos:filter with include=signedUrls. Signed URLs live
    about a minute, so photos are downloaded straight away.
"""
import base64
import json
from functools import cached_property
from pathlib import Path

from . import aps, config

ISSUE_DOMAIN = "autodesk-bim360-issue"
FORM_DOMAIN = "autodesk-construction-form"
ASSET_DOMAIN = "autodesk-bim360-asset"
PHOTO_DOMAIN = "autodesk-construction-photo"
DOC_DOMAIN = "autodesk-bim360-documentmanagement"
DEFAULT_TYPE = {ISSUE_DOMAIN: "issue", FORM_DOMAIN: "form", ASSET_DOMAIN: "asset", PHOTO_DOMAIN: "photo"}


def bare(project_id: str) -> str:
    return project_id[2:] if project_id.startswith("b.") else project_id


# ===================================================================== live

def list_projects() -> list[dict]:
    """Every hub and project the signed-in user can see."""
    if config.SAMPLE_MODE:
        return [SampleProject().summary()]
    c = aps.Client()
    out = []
    for hub in c.get("/project/v1/hubs").get("data", []):
        region = hub["attributes"].get("region") or "US"
        for p in c.get_all_offset(f"/project/v1/hubs/{hub['id']}/projects", page_size=100, key="data"):
            out.append({
                "id": bare(p["id"]),
                "name": p["attributes"]["name"],
                "hub": hub["attributes"]["name"],
                "hub_id": hub["id"],
                "region": region,
            })
    return out


_project_cache: dict[str, "LiveProject"] = {}


def open_project(name_or_id: str | None):
    """Find a project by id or (part of its) name. Returns a project object."""
    if config.SAMPLE_MODE:
        return SampleProject()
    wanted = (name_or_id or config.DEFAULT_PROJECT or "").strip()
    if not wanted:
        raise ValueError("Which project? Pass a project name or id (list_projects shows them), "
                         "or set ACC_DEFAULT_PROJECT in .env.")
    if wanted in _project_cache:
        return _project_cache[wanted]
    projects = list_projects()
    key = bare(wanted).lower()
    exact = [p for p in projects if p["id"].lower() == key or p["name"].lower() == key]
    partial = [p for p in projects if key in p["name"].lower()]
    matches = exact or partial
    if not matches:
        raise ValueError(f"No project matching '{wanted}'. You can see: "
                         + ", ".join(p["name"] for p in projects[:30]))
    if len(matches) > 1:
        raise ValueError(f"'{wanted}' matches several projects: "
                         + "; ".join(f"{p['name']} ({p['id']})" for p in matches[:10]) + ". Be more specific.")
    proj = LiveProject(matches[0])
    _project_cache[wanted] = proj
    return proj


class LiveProject:
    def __init__(self, info: dict):
        self.info = info
        self.id = info["id"]
        self.name = info["name"]
        self.c = aps.Client(region=info.get("region"))
        self._layouts: dict = {}
        self._sections: dict = {}
        self._rels: dict = {}

    def summary(self) -> dict:
        return dict(self.info)

    # ------------------------------------------------------------- people
    @cached_property
    def users(self) -> dict:
        """autodeskId / user id -> display name. Needs account:read; falls back to ids."""
        try:
            rows = self.c.get_all_offset(f"/construction/admin/v1/projects/{self.id}/users", page_size=200)
        except aps.ApsError:
            return {}
        names = {}
        for u in rows:
            label = u.get("name") or u.get("email") or u.get("id")
            if u.get("companyName"):
                label = f"{label} ({u['companyName']})"
            for k in ("autodeskId", "id"):
                if u.get(k):
                    names[u[k]] = label
        return names

    # ------------------------------------------------------------- issues
    def issues(self, status: str | None = None) -> list[dict]:
        params = {"filter[status]": status} if status else {}
        return self.c.get_all_offset(f"/construction/issues/v1/projects/{self.id}/issues", params, page_size=100)

    def issue(self, issue_id: str) -> dict:
        return self.c.get(f"/construction/issues/v1/projects/{self.id}/issues/{issue_id}")

    def issue_comments(self, issue_id: str) -> list[dict]:
        rows = self.c.get_all_offset(f"/construction/issues/v1/projects/{self.id}/issues/{issue_id}/comments", page_size=100)
        return sorted(rows, key=lambda r: r.get("createdAt") or "")

    def issue_attachments(self, issue_id: str) -> list[dict]:
        """Files attached to an issue. Images get a short-lived download URL."""
        data = self.c.get(f"/construction/issues/v1/projects/{self.id}/attachments/{issue_id}/items")
        out = []
        for a in data.get("attachments", []):
            if a.get("isDeleted"):
                continue
            item = {"name": a.get("displayName") or a.get("name"), "fileType": (a.get("fileType") or "").lower(),
                    "createdAt": a.get("createdOn") or a.get("createdAt"), "url": None}
            urn = a.get("storageUrn") or ""
            if "os.object:" in urn:
                bucket, obj = urn.split("os.object:", 1)[1].split("/", 1)
                try:
                    item["url"] = self.c.get(f"/oss/v2/buckets/{bucket}/objects/{obj}/signeds3download").get("url")
                except aps.ApsError:
                    pass
            out.append(item)
        return out

    @cached_property
    def issue_types(self) -> dict:
        """subtype id -> 'Type / Subtype'."""
        data = self.c.get(f"/construction/issues/v1/projects/{self.id}/issue-types", {"include": "subtypes"})
        out = {}
        for t in data.get("results", []):
            for s in t.get("subtypes", []):
                out[s["id"]] = t["title"] if s.get("title") == t.get("title") else f"{t['title']} / {s['title']}"
        return out

    # ------------------------------------------------------------- assets
    def assets(self) -> list[dict]:
        return self.c.get_all_cursor(f"/construction/assets/v2/projects/{self.id}/assets", page_size=200)

    @cached_property
    def asset_categories(self) -> dict:
        rows = self.c.get(f"/construction/assets/v1/projects/{self.id}/categories").get("results", [])
        return {r["id"]: r for r in rows}

    @cached_property
    def asset_statuses(self) -> dict:
        rows = self.c.get_all_cursor(f"/construction/assets/v1/projects/{self.id}/asset-statuses", page_size=200)
        return {r["id"]: r for r in rows}

    # -------------------------------------------------------------- forms
    @cached_property
    def form_templates(self) -> list[dict]:
        return self.c.get(f"/construction/forms/v1/projects/{self.id}/form-templates").get("data", [])

    def forms(self, template_id: str | None = None) -> list[dict]:
        params = {"includeNativeFormValues": "true"}
        if template_id:
            params["templateId"] = template_id
        return self.c.get_all_offset(f"/construction/forms/v2/projects/{self.id}/forms", params, page_size=50)

    def form(self, form_id: str) -> dict:
        rows = self.c.get(f"/construction/forms/v2/projects/{self.id}/forms",
                          {"ids": form_id, "includeNativeFormValues": "true"}).get("data", [])
        if not rows:
            raise ValueError(f"No form with id {form_id} in {self.name}.")
        return rows[0]

    def layout(self, layout_id: str) -> dict:
        if layout_id not in self._layouts:
            self._layouts[layout_id] = self.c.get(f"/construction/forms/v1/projects/{self.id}/layouts/{layout_id}")
        return self._layouts[layout_id]

    def section(self, layout_id: str, section_uid: str) -> dict:
        key = f"{layout_id}/{section_uid}"
        if key not in self._sections:
            self._sections[key] = self.c.get(
                f"/construction/forms/v2/projects/{self.id}/layouts/{layout_id}/sections/{section_uid}")
        return self._sections[key]

    # ------------------------------------------------------ relationships
    def relationships(self, domain: str, type_: str | None = None, id_: str | None = None) -> list[dict]:
        """Links where one side is in `domain` (optionally one type / one id)."""
        if id_ and not type_:  # the API needs a type whenever an id is given
            type_ = DEFAULT_TYPE.get(domain)
        key = (domain, type_, id_)
        if key in self._rels:
            return self._rels[key]
        out, token = [], None
        while True:
            params = {"domain": domain, "pageLimit": 200}
            if type_:
                params["type"] = type_
            if id_:
                params["id"] = id_
            if token:
                params["continuationToken"] = token
            page = self.c.get(f"/bim360/relationship/v2/containers/{self.id}/relationships:search", params)
            out.extend(page.get("relationships") or [])
            token = (page.get("page") or {}).get("continuationToken")
            if not token or len(out) > 50000:
                break
        self._rels[key] = out
        return out

    # ------------------------------------------------------------- photos
    def photos(self, ids: list[str]) -> list[dict]:
        """Photo records (title, takenAt, ...) plus `dataUri` with the image embedded."""
        out = []
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            data = self.c.query(f"/construction/photos/v1/projects/{self.id}/photos:filter",
                                {"filter": {"id": chunk}, "include": ["signedUrls"], "limit": 50})
            for p in data.get("results", []):
                urls = p.get("signedUrls") or {}
                for key in ("thumbnailUrl", "fileUrl"):
                    raw = aps.download(urls[key]) if urls.get(key) else None
                    if raw:
                        p["dataUri"] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
                        break
                out.append(p)
        return out

    def download(self, url: str) -> bytes | None:
        return aps.download(url)

    # ---------------------------------------------------------- locations
    @cached_property
    def locations(self) -> dict:
        """location id -> 'Building > Level > Room'."""
        try:
            rows = self.c.get_all_offset(f"/construction/locations/v2/projects/{self.id}/trees/default/nodes",
                                         page_size=1000)
        except aps.ApsError:
            return {}
        by_id = {r["id"]: r for r in rows}

        def path(r):
            parts = []
            while r and r.get("parentId"):
                parts.append(r["name"])
                r = by_id.get(r["parentId"])
            return " > ".join(reversed(parts))
        return {rid: path(r) for rid, r in by_id.items()}


# =================================================================== sample

class SampleProject(LiveProject):
    """Same interface as LiveProject, reading samples/<bundle>.json instead of Autodesk."""

    def __init__(self, bundle: Path | None = None):
        path = bundle or (config.SAMPLES_DIR / "sample_project.json")
        self.d = json.loads(Path(path).read_text())
        self.info = self.d["project"]
        self.id, self.name = self.info["id"], self.info["name"]
        self._layouts, self._sections, self._rels = {}, {}, {}

    users = property(lambda self: self.d.get("users", {}))
    issue_types = property(lambda self: self.d.get("issue_types", {}))
    asset_categories = property(lambda self: {r["id"]: r for r in self.d.get("asset_categories", [])})
    asset_statuses = property(lambda self: {r["id"]: r for r in self.d.get("asset_statuses", [])})
    form_templates = property(lambda self: self.d.get("form_templates", []))
    locations = property(lambda self: self.d.get("locations", {}))

    def issues(self, status=None):
        return [i for i in self.d.get("issues", []) if not status or i["status"] in status.split(",")]

    def issue(self, issue_id):
        return next(i for i in self.d["issues"] if i["id"] == issue_id)

    def issue_comments(self, issue_id):
        return self.d.get("issue_comments", {}).get(issue_id, [])

    def issue_attachments(self, issue_id):
        return self.d.get("issue_attachments", {}).get(issue_id, [])

    def assets(self):
        return self.d.get("assets", [])

    def forms(self, template_id=None):
        return [f for f in self.d.get("forms", []) if not template_id or f["formTemplateId"] == template_id]

    def form(self, form_id):
        for f in self.d.get("forms", []):
            if f["id"] == form_id:
                return f
        raise ValueError(f"No form with id {form_id} in the sample project.")

    def layout(self, layout_id):
        return self.d["layouts"][layout_id]

    def section(self, layout_id, section_uid):
        return self.d["sections"][f"{layout_id}/{section_uid}"]

    def relationships(self, domain, type_=None, id_=None):
        out = []
        for rel in self.d.get("relationships", []):
            for e in rel["entities"]:
                if e["domain"] == domain and (not type_ or e["type"] == type_) and (not id_ or e["id"] == id_):
                    out.append(rel)
                    break
        return out

    def photos(self, ids):
        wanted = set(ids)
        out = []
        for p in self.d.get("photos", []):
            if p["id"] in wanted:
                p = dict(p)
                img = config.SAMPLES_DIR / p.pop("sampleFile", "")
                if img.is_file():
                    mime = "image/svg+xml" if img.suffix == ".svg" else "image/png"
                    p["dataUri"] = f"data:{mime};base64," + base64.b64encode(img.read_bytes()).decode()
                out.append(p)
        return out

    def download(self, url):
        img = config.SAMPLES_DIR / url
        return img.read_bytes() if url and img.is_file() else None
