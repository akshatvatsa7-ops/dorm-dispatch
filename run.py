#!/usr/bin/env python3
"""
Rebuild everything: results, figures, workbook, report and web page.

    python3 run.py

There is nothing to install. Everything is plain Python from the standard
library. The report is built with pdflatex if you have it; if you do not, the
rest still works and you simply do not get the PDF.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))


def build_report():
    """Compile the report, twice, so cross-references settle."""
    if shutil.which("pdflatex") is None:
        print("\npdflatex not found, skipping the report PDF.")
        print("The numbers and tables it needs are in report/, so you can "
              "compile it later or elsewhere.")
        return False
    report_dir = os.path.join(HERE, "report")
    for _ in range(2):
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            cwd=report_dir, capture_output=True, text=True)
    if r.returncode != 0 and not os.path.exists(
            os.path.join(report_dir, "report.pdf")):
        print("\npdflatex failed. Last lines of its output:")
        print("\n".join(r.stdout.strip().splitlines()[-12:]))
        return False
    # tidy up the files LaTeX leaves behind
    for ext in (".aux", ".log", ".out", ".toc"):
        p = os.path.join(report_dir, "report" + ext)
        if os.path.exists(p):
            os.remove(p)
    return True


def main():
    import study
    import site_page

    print("=" * 64)
    print("Dorm maintenance dispatch: rebuilding everything")
    print("=" * 64)
    out = study.main()

    print("\nbuilding the report ...")
    ok = build_report()

    print("building the web page ...")
    page = site_page.build()

    m = out["methods"]
    fifo, imp = m["fifo"], m["savings+improve"]
    print("\n" + "=" * 64)
    print("Headline numbers")
    print("=" * 64)
    print(f"  walking, first come first served : "
          f"{fifo['travel_per_tech_day']} min per technician per day")
    print(f"  walking, optimised               : "
          f"{imp['travel_per_tech_day']} min per technician per day")
    print(f"  urgent complaints on time, before: {fifo['by_priority'][1]['sla_met_pct']}%")
    print(f"  urgent complaints on time, after : {imp['by_priority'][1]['sla_met_pct']}%")
    print(f"  avoidable late urgent complaints : "
          f"{imp['urgent_avoidable_misses']} in {out['methods']['fifo']['days']} days "
          f"(baseline: {fifo['urgent_avoidable_misses']})")
    print("\nwritten:")
    print("  out/results/*.csv        every table as data")
    print("  out/figures/*.svg|.tikz  the figures, for the web and the report")
    print("  out/dispatch-model.xlsx  the same results as a workbook")
    if ok:
        print("  report/report.pdf        the written report")
    print(f"  {os.path.relpath(page, HERE)}          the project web page")


if __name__ == "__main__":
    main()
