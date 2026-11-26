"""
Run reports from a terminal, without Claude. Handy while editing a report:
change template.html, run this, refresh the browser.

    python run_report.py projects
    python run_report.py reports
    python run_report.py report forms_by_status --project "Northgate" --opt template=QA
    python run_report.py form 12 --project "Northgate"        (full form as JSON)

Add --sample to any command to use the fictional sample project.
"""
import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="run_report.py", description="ACC read-only reports")
    ap.add_argument("--sample", action="store_true", help="use the fictional sample project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("projects")
    sub.add_parser("reports")
    r = sub.add_parser("report")
    r.add_argument("name")
    r.add_argument("--project", default=None)
    r.add_argument("--opt", action="append", default=[], help="option=value (repeatable)")
    r.add_argument("--no-open", action="store_true")
    f = sub.add_parser("form")
    f.add_argument("form")
    f.add_argument("--project", default=None)
    args = ap.parse_args(argv)

    if args.sample:
        os.environ["ACC_SAMPLE_MODE"] = "true"
    from . import acc, config, engine  # import after the env var is set
    from .reconstruct import reconstruct_form, strip_images
    config.SAMPLE_MODE = config.SAMPLE_MODE or args.sample

    if args.cmd == "projects":
        for p in acc.list_projects():
            print(f"{p['name']:45} {p['id']}  ({p.get('hub')}, {p.get('region')})")
    elif args.cmd == "reports":
        for name, info in engine.available().items():
            print(f"{name}: {info['title']}\n    {info['description']}")
            for k, v in info["options"].items():
                print(f"      --opt {k}=...   {v}")
    elif args.cmd == "report":
        opts = dict(o.split("=", 1) for o in args.opt)
        result = engine.run(args.name, acc.open_project(args.project), opts)
        print(json.dumps(result, indent=2, default=str))
        if not args.no_open:
            webbrowser.open(Path(result["file"]).as_uri())
    elif args.cmd == "form":
        p = acc.open_project(args.project)
        hit = next((x for x in p.forms() if args.form in (x["id"], str(x.get("formNum")))), None)
        if not hit:
            sys.exit(f"No form {args.form}")
        print(json.dumps(strip_images(reconstruct_form(p, hit["id"], form=hit)), indent=2, default=str))


if __name__ == "__main__":
    main()
