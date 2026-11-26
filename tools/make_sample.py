"""
Builds samples/sample_project.json: a small FICTIONAL project in the same
shape the ACC APIs return, so every feature (tables, signatures, photos on
questions, issues linked to questions and to whole forms, comments, assets)
can be tried without an Autodesk login:

    python run_report.py --sample report form_record --opt form=2

Re-run this script after editing it:  python tools/make_sample.py
All names, companies and data are made up.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples"

U = {"U-SAM": "Sam Rivera (Northline Mechanical)", "U-PRI": "Priya Shah (Client QA)",
     "U-TOM": "Tom Becker (Voltix Electrical)", "U-JO": "Jo Okafor (Main contractor)"}
ISSUE_TYPES = {"st-def": "Quality / Defect", "st-snag": "Commissioning / Snag", "st-hs": "Safety / Hazard"}

CATS = [{"id": "2", "name": "Refrigeration plant"}, {"id": "3", "name": "Dock equipment"},
        {"id": "4", "name": "Electrical distribution"}]
STATS = [{"id": "s-del", "label": "Delivered"}, {"id": "s-ins", "label": "Installed"},
         {"id": "s-com", "label": "Commissioned"}]
ASSETS = [
    ("A1", "RC-01", "Compressor rack 1", "2", "s-com"), ("A2", "RC-02", "Compressor rack 2", "2", "s-ins"),
    ("A3", "EV-11", "Evaporator, chamber 1", "2", "s-ins"), ("A4", "DL-01", "Dock leveller 01", "3", "s-com"),
    ("A5", "DL-02", "Dock leveller 02", "3", "s-ins"), ("A6", "DD-01", "Dock door 01", "3", "s-ins"),
    ("A7", "DB-01", "Distribution board DB-01", "4", "s-ins"), ("A8", "DB-02", "Distribution board DB-02", "4", "s-del"),
]

# ---------------------------------------------------------- form templates
T_COM, T_DOCK = "tpl-com01", "tpl-qa02"
TEMPLATES = [
    {"id": T_COM, "name": "COM-01 Refrigeration plant commissioning", "templateType": "pg.template_type.commissioning"},
    {"id": T_DOCK, "name": "QA-02 Dock equipment installation check", "templateType": "pg.template_type.quality"},
]


def field(uid, label, schema, value_name, **kw):
    return {"uid": uid, "label": label, "schema": schema, "type": "field", "valueName": value_name, **kw}


LAYOUTS, SECTIONS = {}, {}


def layout(lid, sections):
    LAYOUTS[lid] = {"layout": {"uid": lid, "type": "form"},
                    "sections": [{"uid": s["uid"], "label": s["label"], "description": s.get("description", ""),
                                  "sortIndex": i} for i, s in enumerate(sections)]}
    for s in sections:
        items = [dict(it, sortIndex=i) for i, it in enumerate(s["items"])]
        SECTIONS[f"{lid}/{s['uid']}"] = {"section": {"uid": s["uid"], "label": s["label"]}, "sectionItems": items,
                                         "tableColumns": s.get("tableColumns", {}), "actions": []}


layout("L-COM", [
    {"uid": "sec-id", "label": "Identification", "items": [
        field("i1", "Plant tag", "f-tag", "textVal", isRequired=True),
        field("i2", "Commissioning engineer", "f-eng", "textVal"),
        field("i3", "Refrigerant", "f-ref", "choiceVal", presets=[{"value": "R744 (CO2)"}, {"value": "R290"}]),
    ]},
    {"uid": "sec-chk", "label": "Pre-start checks", "description": "Pass, Fail or N/A. Photo and issue for every Fail.", "items": [
        field("c1", "Pipework pressure-tested and certificate seen", "f-c1", "toggleVal", modifier="p/f"),
        field("c2", "Oil levels correct on all compressors", "f-c2", "toggleVal", modifier="p/f"),
        field("c3", "Leak detection alarms tested", "f-c3", "toggleVal", modifier="p/f"),
        field("c4", "Guarding and labels fitted", "f-c4", "toggleVal", modifier="p/f"),
    ]},
    {"uid": "sec-tbl", "label": "Run-in readings", "items": [
        {"uid": "tb1", "type": "table", "schema": "tbl-readings", "label": "Readings after 2 hours", "addRowLabel": "Add reading"},
    ], "tableColumns": {"tb1": [
        {"uid": "col-pt", "label": "Point", "columnKey": "point", "columnType": "text_val", "sortIndex": 0},
        {"uid": "col-p", "label": "Pressure (bar)", "columnKey": "pressure", "columnType": "number_val", "sortIndex": 1},
        {"uid": "col-t", "label": "Temperature (°C)", "columnKey": "temp", "columnType": "number_val", "sortIndex": 2},
        {"uid": "col-ok", "label": "Within range", "columnKey": "ok", "columnType": "text_val", "sortIndex": 3},
    ]}},
    {"uid": "sec-sign", "label": "Sign-off", "items": [
        field("s1", "Outcome", "f-out", "choiceVal"),
        field("s2", "Comments", "f-com", "textVal"),
        field("s3", "Client signature", "f-sig", "svgVal"),
    ]},
])
layout("L-DOCK", [
    {"uid": "d-id", "label": "Identification", "items": [
        field("d1", "Asset tag", "g-tag", "textVal"), field("d2", "Installer", "g-ins", "textVal")]},
    {"uid": "d-chk", "label": "Installation checks", "items": [
        {"uid": "note", "type": "text", "label": "Check with the door closed and isolated."},
        field("d3", "Fixed securely, levels within tolerance", "g-c1", "toggleVal", modifier="p/f"),
        field("d4", "Safety edge and photo-eyes working", "g-c2", "toggleVal", modifier="p/f"),
        field("d5", "Emergency stop tested", "g-c3", "toggleVal", modifier="p/f"),
        field("d6", "Cycles tested", "g-cyc", "numberVal"),
    ]},
])

SIG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 80'><path d='M10 60 C40 10, 60 70, 90 35 "
       "S140 20, 160 50 S210 60, 230 25' fill='none' stroke='#1a1a1a' stroke-width='3'/></svg>")


def val(schema, key, v):
    return {"fieldId": schema, key: v, "deleted": False}


def com_form(fid, num, tag, status, date, c, readings, outcome, signed, by="U-SAM"):
    cv = [val("f-tag", "textVal", tag), val("f-eng", "textVal", "Sam Rivera"), val("f-ref", "choiceVal", "R744 (CO2)")]
    cv += [val(f"f-c{i + 1}", "toggleVal", x) for i, x in enumerate(c) if x is not None]
    if outcome:
        cv.append(val("f-out", "choiceVal", outcome))
        cv.append(val("f-com", "textVal", "Plant running stable after 2 h run-in." if outcome == "Accepted" else "Re-test after leak repair."))
    if signed:
        cv.append(val("f-sig", "svgVal", SIG))
    # Shape as ACC returns it: one entry per row, cells named by columnName, ordered by rank.
    rows = [{"schema": "tbl-readings", "id": f"{fid}-r{i}", "rank": i, "deleted": False, "columns": [
        {"columnName": "point", "textVal": pt}, {"columnName": "pressure", "numberVal": p},
        {"columnName": "temp", "numberVal": t}, {"columnName": "ok", "textVal": ok}]} for i, (pt, p, t, ok) in enumerate(readings)]
    return form(fid, num, f"COM-01 {tag}", T_COM, "L-COM", status, date, cv, rows, by)


def dock_form(fid, num, tag, status, date, c, cycles, by="U-JO"):
    cv = [val("g-tag", "textVal", tag), val("g-ins", "textVal", "Portside Doors Ltd")]
    cv += [val(f"g-c{i + 1}", "toggleVal", x) for i, x in enumerate(c) if x is not None]
    if cycles is not None:
        cv.append(val("g-cyc", "numberVal", cycles))
    return form(fid, num, f"QA-02 {tag}", T_DOCK, "L-DOCK", status, date, cv, [], by)


def form(fid, num, name, tpl, lid, status, date, cv, rows, by):
    changes = {"inProgress": {"at": f"{date}T08:00:00Z", "by": by}}
    if status == "closed":
        changes["closed"] = {"at": f"{date}T16:30:00Z", "by": "U-PRI"}
    return {"id": fid, "formNum": num, "name": name, "formTemplateId": tpl, "status": status, "formDate": date,
            "createdAt": f"{date}T08:00:00Z", "createdBy": by, "assigneeId": by, "assigneeType": "user",
            "description": "Fictional sample data.", "lastStatusChanges": changes,
            "lastSubmittedAt": f"{date}T16:30:00Z" if status == "closed" else None,
            "lastSubmittedBy": "U-PRI" if status == "closed" else None,
            "nativeForm": {"layoutId": lid, "customValues": cv, "tabularValues": rows}}


FORMS = [
    com_form("F1", 1, "RC-01", "closed", "2026-10-02", ["True", "True", "True", "True"],
             [("Suction", 26.1, -8.0, "Yes"), ("Discharge", 88.4, 71.0, "Yes"), ("Gas cooler out", 85.0, 31.5, "Yes")],
             "Accepted", True),
    com_form("F2", 2, "RC-02", "inProgress", "2026-11-12", ["True", "False", "True", None],
             [("Suction", 24.9, -6.5, "Yes"), ("Discharge", 95.2, 79.0, "No: high")], "Re-test", False),
    com_form("F3", 3, "EV-11", "inProgress", "2026-11-20", ["True", None, None, None], [], None, False),
    dock_form("F4", 4, "DL-01", "closed", "2026-09-18", ["True", "True", "True"], 50),
    dock_form("F5", 5, "DL-02", "inProgress", "2026-11-03", ["True", "False", "True"], 12),
    dock_form("F6", 6, "DD-01", "closed", "2026-10-28", ["True", "True", "na"], 40),
]


def issue(iid, num, title, status, st, who, created, due=None, desc="", comments=0, attach=0, closed=None):
    return {"id": iid, "displayId": num, "title": title, "status": status, "issueSubtypeId": st, "assignedTo": who,
            "assignedToType": "user", "createdAt": f"{created}T09:00:00Z", "dueDate": due, "description": desc,
            "commentCount": comments, "attachmentCount": attach, "closedAt": closed}


ISSUES = [
    issue("I1", 1, "Oil level low on compressor 2, RC-02", "open", "st-snag", "U-SAM", "2026-11-12", "2026-11-19",
          "Sight glass below minimum on compressor 2. Top up and re-check after 1 h run.", 2, 1),
    issue("I2", 2, "Discharge pressure above design on RC-02", "in_review", "st-snag", "U-SAM", "2026-11-12", "2026-12-05",
          "95 bar at 2 h, design max 90 bar. Check gas cooler fans and controller setpoint.", 1),
    issue("I3", 3, "Safety edge not stopping door DL-02 at 30 mm", "open", "st-hs", "U-JO", "2026-11-03", "2026-11-10",
          "Door reverses late. Installer to adjust and re-test before handover.", 1, 1),
    issue("I4", 4, "Missing warning label on DD-01 motor cover", "closed", "st-def", "U-JO", "2026-10-28", "2026-11-04",
          "", 1, 0, "2026-11-01T10:00:00Z"),
    issue("I5", 5, "DB-02 delivered with wrong IP rating", "open", "st-def", "U-TOM", "2026-08-14", "2026-09-30",
          "Board is IP31, spec says IP54 for the cold store. Replacement ordered.", 0),
    issue("I6", 6, "Cable tray support spacing in plant room", "pending", "st-def", None, "2026-11-18", None,
          "Supports at 2.4 m, spec 1.5 m.", 0),
]
COMMENTS = {
    "I1": [{"createdBy": "U-SAM", "createdAt": "2026-11-13T10:12:00Z", "body": "Topped up, running to re-check."},
           {"createdBy": "U-PRI", "createdAt": "2026-11-14T15:40:00Z", "body": "Still at minimum after 1 h. Please investigate oil return."}],
    "I2": [{"createdBy": "U-SAM", "createdAt": "2026-11-20T09:05:00Z", "body": "Fan 3 was wired in reverse. Fixed; re-test booked."}],
    "I3": [{"createdBy": "U-JO", "createdAt": "2026-11-04T08:30:00Z", "body": "Installer coming back on Thursday."}],
    "I4": [{"createdBy": "U-PRI", "createdAt": "2026-11-01T10:00:00Z", "body": "Label fitted, checked on site. Closing."}],
}
ATTACH = {"I1": [{"name": "sight-glass.svg", "fileType": "svg", "url": "img/sight-glass.svg"}],
          "I3": [{"name": "safety-edge.svg", "fileType": "svg", "url": "img/safety-edge.svg"}]}

PHOTOS = [
    {"id": "P1", "title": "Oil sight glass, compressor 2", "takenAt": "2026-11-12T10:30:00Z", "createdBy": "U-SAM", "sampleFile": "img/sight-glass.svg"},
    {"id": "P2", "title": "Gas cooler fans", "takenAt": "2026-11-12T11:05:00Z", "createdBy": "U-SAM", "sampleFile": "img/gas-cooler.svg"},
    {"id": "P3", "title": "Safety edge test", "takenAt": "2026-11-03T14:20:00Z", "createdBy": "U-JO", "sampleFile": "img/safety-edge.svg"},
    {"id": "P4", "title": "Plant room overview", "takenAt": "2026-10-02T09:00:00Z", "createdBy": "U-SAM", "sampleFile": "img/plant-room.svg"},
]


def rel(a, b):
    return {"entities": [a, b]}


def ent(domain, type_, id_):
    return {"domain": domain, "type": type_, "id": id_}


FORM, FFLD = "autodesk-construction-form", "urn:adsk:form.field:"
ASSET, ISSUE_D, PHOTO = "autodesk-bim360-asset", "autodesk-bim360-issue", "autodesk-construction-photo"
form_of_asset = {"A1": "F1", "A2": "F2", "A3": "F3", "A4": "F4", "A5": "F5", "A6": "F6"}
RELS = [rel(ent(ASSET, "asset", a), ent(FORM, "form", f)) for a, f in form_of_asset.items()]
RELS += [
    rel(ent(FORM, "formfield", f"{FFLD}F2/f-c2"), ent(ISSUE_D, "issue", "I1")),   # issue on the oil-level question
    rel(ent(FORM, "formfield", f"{FFLD}F2/f-c2"), ent(PHOTO, "photo", "P1")),     # photo on the same question
    rel(ent(FORM, "form", "F2"), ent(ISSUE_D, "issue", "I2")),                     # issue on the whole form
    rel(ent(FORM, "form", "F2"), ent(PHOTO, "photo", "P2")),
    rel(ent(FORM, "formfield", f"{FFLD}F5/g-c2"), ent(ISSUE_D, "issue", "I3")),
    rel(ent(FORM, "formfield", f"{FFLD}F5/g-c2"), ent(PHOTO, "photo", "P3")),
    rel(ent(FORM, "form", "F6"), ent(ISSUE_D, "issue", "I4")),
    rel(ent(FORM, "form", "F1"), ent(PHOTO, "photo", "P4")),
    rel(ent(ASSET, "asset", "A8"), ent(ISSUE_D, "issue", "I5")),                   # issue straight on an asset
]


def svg(title, shapes):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 220'><rect width='300' height='220' fill='#dfe6e9'/>"
            f"{shapes}<rect y='190' width='300' height='30' fill='#2d3436'/>"
            f"<text x='12' y='210' fill='#fff' font-family='Arial' font-size='14'>{title} (sample)</text></svg>")


IMAGES = {
    "sight-glass.svg": svg("Sight glass", "<circle cx='150' cy='95' r='60' fill='#b2bec3' stroke='#2d3436' stroke-width='6'/>"
                           "<rect x='95' y='110' width='110' height='40' fill='#e17055'/><line x1='90' y1='105' x2='210' y2='105' stroke='#d63031' stroke-width='3' stroke-dasharray='6 4'/>"),
    "gas-cooler.svg": svg("Gas cooler", "<rect x='30' y='40' width='240' height='130' fill='#636e72'/>"
                          + "".join(f"<circle cx='{x}' cy='105' r='30' fill='#b2bec3' stroke='#2d3436' stroke-width='3'/>" for x in (80, 150, 220))),
    "safety-edge.svg": svg("Safety edge", "<rect x='60' y='20' width='180' height='150' fill='#fdcb6e' stroke='#2d3436' stroke-width='4'/>"
                           "<rect x='60' y='160' width='180' height='14' fill='#d63031'/><rect x='140' y='150' width='20' height='20' fill='#2d3436'/>"),
    "plant-room.svg": svg("Plant room", "<rect x='20' y='60' width='120' height='110' fill='#74b9ff'/><rect x='160' y='80' width='120' height='90' fill='#81ecec'/>"
                          "<rect x='20' y='30' width='260' height='12' fill='#636e72'/>"),
}


def main():
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    for name, body in IMAGES.items():
        (OUT / "img" / name).write_text(body)
    bundle = {
        "_note": "FICTIONAL sample data in the shape of ACC API responses. Generated by tools/make_sample.py.",
        "project": {"id": "sample-harbour-cold-store", "name": "Sample: Harbour Cold Store", "hub": "Sample hub", "region": "EMEA"},
        "users": U, "issue_types": ISSUE_TYPES, "locations": {},
        "asset_categories": CATS, "asset_statuses": STATS,
        "assets": [{"id": i, "clientAssetId": tag, "description": d, "categoryId": c, "statusId": s} for i, tag, d, c, s in ASSETS],
        "form_templates": TEMPLATES, "layouts": LAYOUTS, "sections": SECTIONS, "forms": FORMS,
        "issues": ISSUES, "issue_comments": COMMENTS, "issue_attachments": ATTACH,
        "photos": PHOTOS, "relationships": RELS,
    }
    (OUT / "sample_project.json").write_text(json.dumps(bundle, indent=1, ensure_ascii=False))
    print(f"Wrote {OUT / 'sample_project.json'}")


if __name__ == "__main__":
    main()
