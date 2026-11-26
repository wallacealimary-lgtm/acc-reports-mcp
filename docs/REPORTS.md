# Editing reports and making your own

Every report lives in its own folder in `reports/`:

```
reports/
  _base.html            the shared look: header, colours, cards, tables
  _macros.html          small reusable pieces: status pills, stat cards, bars, photo grids
  forms_by_status/
    report.py           gets the data and works out the numbers
    template.html       turns those numbers into the page
  asset_readiness/ ...
  form_record/ ...
  open_issues/ ...
```

There are two kinds of change:

| You want to change… | Edit | Needs Python? |
|---|---|---|
| Colours, fonts, the header, your logo | `reports/_base.html` | No |
| What a report shows, column order, wording | that report's `template.html` | No |
| A rule, e.g. what counts as "Ready" | that report's `report.py` | A little |
| A whole new report | copy a folder | A little |

**The fastest way to work:** run the report against the sample project, change the file, run it again, refresh the browser.

```bash
.venv/bin/python run_report.py --sample report asset_readiness
```

Or ask Claude Code to do it: *"In reports/open_issues/template.html, add a column with the issue's location."* Claude can read the files and run the command above to check its work.

No restart is needed. Each report is loaded fresh every time it runs, so a change shows up on the next run, including from Claude Desktop.

---

## 1. Change the look (every report)

Open `reports/_base.html`. The colours are at the top:

```css
:root {
  --black: #111111;
  --accent: #FFE600;    /* header stripe and section dots */
  --good: #1E8E5A;      /* closed, pass, ready */
  --warn: #C77700;      /* in progress */
  --bad: #C62828;       /* open issues, fail */
}
```

Change `--accent` to your company colour and every report follows.

**Add a logo.** In the header block (`<div class="header">`), add an `<img>` in front of the title. To keep the report a single file you can send, use a data URI. Easiest: ask Claude to *"embed logo.png into the report header of _base.html as a data URI"*.

## 2. Change what a report shows

Templates use **Jinja**, which is HTML with a few extras:

| You write | It means |
|---|---|
| `{{ f.name }}` | show a value |
| `{% for f in data.forms %} … {% endfor %}` | repeat for each item |
| `{% if f.counts.fail %} … {% endif %}` | show only when true |
| `{{ f.formDate \| date }}` | format a date (`25 Nov 2026`) |
| `{{ ui.pill(f.statusLabel) }}` | a coloured status pill (from `_macros.html`) |
| `{{ ui.stat(12, "Open issues", "bad") }}` | a big number card |

**Example: add an "Assigned to" column to the forms table.** In `reports/forms_by_status/template.html`, find the **All forms** table and add a header cell and a data cell:

```html
<tr><th class="num">#</th><th>Form</th> … <th>Assigned to</th></tr>
…
<td class="muted">{{ f.assignee or "—" }}</td>
```

Run it again and the column is there. The fields you can use are listed under **What data is available** below.

## 3. Change a rule

Rules live in `report.py`, written in plain Python. For example, `reports/asset_readiness/report.py` decides readiness here:

```python
def readiness(forms, open_issues, fails):
    if open_issues or fails:
        return "Blocked"
    if not forms:
        return "No forms"
    if all(f["status"] == "closed" for f in forms):
        return "Ready"
    return "In progress"
```

Suppose your process says an asset is only Ready once its ACC status is **Commissioned**. Add that check to the function, and pass the asset's status in where the function is called.

## 4. Make a new report

Copy an existing folder, rename it, and change the two files. The folder name becomes the report's name. It shows up in `list_reports` and in Claude straight away.

A complete example: **forms per person**, i.e. who has filled in how many forms, and how many are still open.

`reports/forms_per_person/report.py`

```python
from acc_reports_mcp import report_kit as kit

TITLE = "Forms per person"
DESCRIPTION = "How many forms each person created, and how many are still open."
OPTIONS = {"template": "Only templates whose name contains this text"}


def build(project, template=None):
    forms = kit.load_forms(project, template=template)
    people = []
    for person, rows in kit.group(forms, lambda f: f["createdBy"] or "Unknown").items():
        still_open = [f for f in rows if f["status"] != "closed"]
        people.append({"name": person, "total": len(rows), "open": len(still_open)})
    people.sort(key=lambda p: -p["open"])
    return {"people": people, "summary": {"forms": len(forms), "people": len(people)}}
```

`reports/forms_per_person/template.html`

```html
{% extends "_base.html" %}
{% import "_macros.html" as ui %}
{% block content %}
<div class="stats">
  {{ ui.stat(data.summary.forms, "Forms") }}
  {{ ui.stat(data.summary.people, "People") }}
</div>
<div class="section">
  <h2>By person</h2>
  <div class="body">
    <table>
      <tr><th>Person</th><th class="num">Forms</th><th class="num">Still open</th></tr>
      {% for p in data.people %}
      <tr><td>{{ p.name }}</td><td class="num">{{ p.total }}</td><td class="num">{{ p.open }}</td></tr>
      {% endfor %}
    </table>
  </div>
</div>
{% endblock %}
```

Try it:

```bash
.venv/bin/python run_report.py --sample report forms_per_person
```

The rules for `report.py`:

- `TITLE` and `DESCRIPTION` are what Claude reads to decide when to use your report, so describe it the way someone would ask for it.
- `OPTIONS` lists the filters it accepts, each with a one-line explanation. Claude passes these as `options`.
- `build(project, **options)` returns a dictionary. The template gets it as `data`.
- Put the headline numbers in `data["summary"]`. That's what Claude gets back to describe the result in chat.
- Optional: `data["file_suffix"]` is added to the saved file name.

---

## What data is available

`report.py` gets a `project`. These helpers (in `acc_reports_mcp/report_kit.py`) do the heavy lifting:

| Helper | Gives you |
|---|---|
| `kit.load_forms(project, template=, status=, since=, until=, details=False)` | a list of fully rebuilt forms (below). `details=True` also loads issue comments and photos |
| `kit.load_issues(project)` | `{issue id: issue}` |
| `kit.load_assets(project)` | `{asset id: asset}` with `categoryName` and `statusName` added |
| `kit.asset_links(project)` | `{asset id: {"forms": [...], "issues": [...], "documents": [...]}}` |
| `kit.find_form(project, "12")` | one raw form by number, id or name |
| `kit.group(rows, key)`, `kit.count_by(rows, key)` | group or count a list by a field |
| `kit.pct(part, whole)`, `kit.days_since(date)`, `kit.parse_date(text)` | small sums and dates |

**A rebuilt form** (one item from `load_forms`, and what `get_form` returns):

```
id, number, name, status ("closed"), statusLabel ("Closed"),
template: {name, type}, formDate, dueDate, createdAt, createdBy, assignee,
location, description, notes, submittedAt, submittedBy,
statusHistory: [{status, at, by}],
assets: [{id, name, description}],
sections: [
  {title, description, items: [
     {kind: "question", label, value ("Pass" / "12.5" / "text"), answer ("pass"/"fail"/"na"/"yes"/"no"/None),
      required, issues: [...], photos: [...]},
     {kind: "table", label, columns: [...], rows: [[...], ...]},
     {kind: "signature", label, svg},
     {kind: "text", label, description}
  ]}
],
issues:    issues linked to the whole form,
photos:    photos linked to the whole form,
allIssues: every linked issue (whole form and questions),
counts: {questions, answered, pass, fail, yes, no, na, tables, issues, openIssues, photos},
warnings: [...]
```

**An issue:** `number, title, status, statusLabel, open (true/false), type, assignee, dueDate, createdAt, closedAt, location, description`. Loaded with details, it also has `comments: [{by, at, text}]` and `attachments: [{title, dataUri}]`.

**A photo:** `title, takenAt, by, description, dataUri` (the image itself, embedded so the report is one file).

**An asset:** `clientAssetId` (its name), `description`, `categoryName`, `statusName`, `locationId`.

If you need something that isn't here, `project` also has the raw calls: `project.issues()`, `project.forms()`, `project.assets()`, `project.relationships(domain)`, `project.issue_comments(id)` and more (see `acc_reports_mcp/acc.py`). All of them read only.

## Rebuilding the sample project

The sample data is generated by `tools/make_sample.py`. Edit it (add forms, issues, photos), then run `.venv/bin/python tools/make_sample.py` to rewrite `samples/sample_project.json`. Use it to test a report on a situation your real project doesn't have yet.
