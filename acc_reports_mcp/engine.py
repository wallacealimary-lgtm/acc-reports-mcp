"""
Finds and runs reports.

A report is a folder in reports/ with two files:
  report.py      TITLE, DESCRIPTION, OPTIONS and a build(project, **options) -> dict
  template.html  a Jinja2 template that turns that dict into a page

Add a folder and it shows up in list_reports; no other code changes.
"""
import importlib.util
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config


def _load(folder: Path):
    spec = importlib.util.spec_from_file_location(f"acc_report_{folder.name}", folder / "report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def available() -> dict:
    out = {}
    for folder in sorted(config.REPORTS_DIR.iterdir()):
        if folder.is_dir() and (folder / "report.py").exists() and not folder.name.startswith(("_", ".")):
            try:
                mod = _load(folder)
                out[folder.name] = {"title": getattr(mod, "TITLE", folder.name),
                                    "description": getattr(mod, "DESCRIPTION", ""),
                                    "options": getattr(mod, "OPTIONS", {})}
            except Exception as e:  # a broken report shouldn't hide the others
                out[folder.name] = {"title": folder.name, "description": f"Could not load: {e}", "options": {}}
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:60] or "report"


def _filters(env: Environment) -> None:
    def date_fmt(v, fmt="%d %b %Y"):
        if not v:
            return ""
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime(fmt)
        except ValueError:
            return str(v)
    env.filters["date"] = date_fmt
    env.filters["pct"] = lambda part, whole: round(100 * part / whole) if whole else 0
    env.filters["slug"] = _slug


def run(name: str, project, options: dict | None = None) -> dict:
    folder = config.REPORTS_DIR / name
    if not (folder / "report.py").exists():
        raise ValueError(f"No report called '{name}'. Available: {', '.join(available())}")
    mod = _load(folder)
    allowed = set(getattr(mod, "OPTIONS", {}))
    options = {k: v for k, v in (options or {}).items() if v not in (None, "")}
    unknown = set(options) - allowed
    if unknown:
        raise ValueError(f"Report '{name}' has no option(s) {', '.join(sorted(unknown))}. "
                         f"Options: {', '.join(sorted(allowed)) or 'none'}")
    data = mod.build(project, **options)

    env = Environment(loader=FileSystemLoader([str(folder), str(config.REPORTS_DIR)]),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    _filters(env)
    now = datetime.now()
    html = env.get_template("template.html").render(
        data=data, project=project.summary(), title=getattr(mod, "TITLE", name),
        options=options, generated_at=now, sample_mode=config.SAMPLE_MODE)

    out_dir = config.OUTPUT_DIR / _slug(project.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = _slug(str(data.get("file_suffix", ""))) if data.get("file_suffix") else ""
    path = out_dir / f"{name}{'_' + suffix if suffix else ''}_{now:%Y%m%d-%H%M}.html"
    path.write_text(html, encoding="utf-8")
    return {"report": name, "file": str(path), "summary": data.get("summary", {})}
