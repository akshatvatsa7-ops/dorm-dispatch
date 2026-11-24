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
    """
    Compile both documents, each twice so cross-references settle.

    report.tex   the full write-up
    explainer.tex  the short plain-language companion

    Both pull their figures from report/numbers.tex, which study.py has just
    rewritten, so they cannot fall out of step with the results.
    """
    if shutil.which("pdflatex") is None:
        print("\npdflatex not found, skipping the PDFs.")
        print("The numbers and tables they need are in report/, so you can "
              "compile them later or elsewhere.")
        return False
    report_dir = os.path.join(HERE, "report")
    ok = True
    for name in ("report", "explainer"):
        for _ in range(2):
            r = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", name + ".tex"],
                cwd=report_dir, capture_output=True, text=True)
        if r.returncode != 0 and not os.path.exists(
                os.path.join(report_dir, name + ".pdf")):
            print(f"\npdflatex failed on {name}.tex. Last lines:")
            print("\n".join(r.stdout.strip().splitlines()[-12:]))
            ok = False
        # tidy up the files LaTeX leaves behind
        for ext in (".aux", ".log", ".out", ".toc"):
            p = os.path.join(report_dir, name + ext)
            if os.path.exists(p):
                os.remove(p)
    return ok


def main():
    import study
    import site_page

    print("=" * 64)
    print("Dorm maintenance dispatch: rebuilding everything")
    print("=" * 64)
    out = study.main()

    print("\nbuilding the report and the explainer ...")
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
        print("  report/explainer.pdf     the short plain explanation")
    print(f"  {os.path.relpath(page, HERE)}          the project web page")


if __name__ == "__main__":
    main()
