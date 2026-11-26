"""
Run reports from a terminal, without Claude. Examples:

    python run_report.py --sample reports
    python run_report.py --sample report form_record --opt form=2
    python run_report.py projects
    python run_report.py report forms_by_status --project "Northgate" --opt template=QA

See docs/REPORTS.md.
"""
from acc_reports_mcp.cli import main

if __name__ == "__main__":
    main()
