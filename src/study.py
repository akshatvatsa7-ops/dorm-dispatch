"""
Runs the whole study and writes every output: result tables, the figures,
the Excel workbook, and a file of numbers for the report to quote.

The last of those matters more than it sounds. Every figure quoted in the
report is defined here as a LaTeX command and written to report/numbers.tex,
so the report cannot drift out of step with the code. If an assumption
changes, you rerun this file and the report updates itself.
"""

import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import campus as campus_mod
import instance as inst
import dispatch
import experiment
import exact
import figures
import xlsx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RESULTS = os.path.join(ROOT, "out", "results")
REPORT = os.path.join(ROOT, "report")

DAYS = 30
BASE_SEED = 2026
SEEDS = [2026, 7, 101, 555, 9001]

# Complaint rates to sweep, in complaints per day. 58 is the base case; the
# rest run from a quiet spell up to roughly double the normal load.
LOADS = [40, 50, 58, 70, 85, 100]

# The crew-against-load grid. Three crew sizes at three rates is enough to
# show where each crew stops coping without running the whole cross product.
GRID_LOADS = [58, 85, 110]
GRID_CREWS = [3, 4, 5]

METHOD_LABEL = {
    "fifo": "First come first served",
    "savings": "Clarke-Wright savings",
    "priority": "Priority insertion",
    "savings+improve": "Savings + 2-opt/Or-opt",
}


def write_csv(name, rows):
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, name)
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return rows


def main():
    t0 = time.time()
    c = campus_mod.build()
    out = {}

    # ---------------------------------------------------------------
    # 1. the campus itself
    # ---------------------------------------------------------------
    loc_rows = [["index", "name", "short", "category", "campus",
                 "latitude", "longitude", "walk from depot (min)"]]
    for i, name in enumerate(c["names"]):
        loc_rows.append([i, name, c["short"][i], c["category"][i], c["zone"][i],
                         round(c["coords"][i][0], 6), round(c["coords"][i][1], 6),
                         c["walk"][0][i]])
    write_csv("locations.csv", loc_rows)

    walk_rows = [[""] + c["short"]]
    for i, s in enumerate(c["short"]):
        walk_rows.append([s] + c["walk"][i])
    write_csv("walk_minutes.csv", walk_rows)

    flat = [c["walk"][i][j] for i in range(len(c["walk"]))
            for j in range(len(c["walk"])) if i != j]
    cross = [c["walk"][i][j] for i in range(len(c["walk"]))
             for j in range(len(c["walk"]))
             if c["zone"][i] != c["zone"][j]]
    same = [c["walk"][i][j] for i in range(len(c["walk"]))
            for j in range(len(c["walk"]))
            if i != j and c["zone"][i] == c["zone"][j]]
    out["campus"] = {
        "locations": len(c["names"]),
        # one of the locations is the depot, which does not raise complaints
        "complaint_sites": len(c["names"]) - 1,
        "dorms": sum(1 for x in c["category"] if x == "dorm"),
        "new_campus": c["meta"]["n_new_campus"],
        "old_campus": c["meta"]["n_old_campus"],
        "tunnel_m": c["tunnel"]["length_m"],
        "mean_walk": round(sum(flat) / len(flat), 1),
        "mean_same_campus": round(sum(same) / len(same), 1),
        "mean_cross_campus": round(sum(cross) / len(cross), 1),
        "max_walk": round(max(flat), 1),
        "depots": {t: {"name": c["names"][i], "zone": c["zone"][i]}
                   for t, i in c["depot"].items()},
    }

    # ---------------------------------------------------------------
    # 2. the four methods, same ticket stream
    # ---------------------------------------------------------------
    print("comparing the four methods over", DAYS, "days ...")
    results = experiment.compare_methods(c, days=DAYS, seed=BASE_SEED)

    rows = [["method", "objective", "weighted tardiness (h)",
             "walking (min/technician/day)", "tickets closed",
             "closed on time (%)", "urgent closed on time (%)",
             "mean wait, urgent (h)", "mean tickets waiting"]]
    for m, r in results.items():
        rows.append([METHOD_LABEL[m], r["objective"], r["weighted_tardiness"],
                     r["travel_per_tech_day"], r["completed"], r["sla_met_pct"],
                     r["by_priority"][1]["sla_met_pct"],
                     r["by_priority"][1]["mean_wait_h"], r["mean_backlog"]])
    write_csv("methods.csv", rows)
    out["methods"] = {m: {k: v for k, v in r.items() if k != "per_day"}
                      for m, r in results.items()}

    per_day_rows = [["method", "day", "raised", "in queue", "closed",
                     "left waiting", "walking (min)", "weighted tardiness"]]
    for m, r in results.items():
        for d in r["per_day"]:
            per_day_rows.append([METHOD_LABEL[m], d["day"] + 1, d["raised"],
                                 d["queue"], d["done"], d["backlog"],
                                 d["travel_min"], d["weighted_tardiness"]])
    write_csv("per_day.csv", per_day_rows)

    # ---------------------------------------------------------------
    # 3. does the result survive a different random draw?
    # ---------------------------------------------------------------
    print("repeating on", len(SEEDS), "independent ticket streams ...")
    seed_rows = [["seed"] + [METHOD_LABEL[m] for m in dispatch.METHODS]]
    seed_obj = {m: [] for m in dispatch.METHODS}
    for s in SEEDS:
        row = [s]
        for m in dispatch.METHODS:
            r = experiment.simulate(m, c, days=DAYS, seed=s)
            seed_obj[m].append(r["objective"])
            row.append(r["objective"])
        seed_rows.append(row)
    write_csv("seeds.csv", seed_rows)
    out["seeds"] = {m: {"values": v, "mean": round(sum(v) / len(v), 1),
                        "min": min(v), "max": max(v)}
                    for m, v in seed_obj.items()}

    # ---------------------------------------------------------------
    # 4. how many technicians, and of which trade?
    # ---------------------------------------------------------------
    print("trying different crew sizes and mixes ...")
    crews = [
        ("2 of each trade (6)", {"electrical": 2, "plumbing": 2, "carpentry": 2}),
        ("3 of each trade (9)", {"electrical": 3, "plumbing": 3, "carpentry": 3}),
        ("4 of each trade (12)", {"electrical": 4, "plumbing": 4, "carpentry": 4}),
        ("5 of each trade (15)", {"electrical": 5, "plumbing": 5, "carpentry": 5}),
        ("4 electrical / 4 plumbing / 1 carpentry (9)",
         {"electrical": 4, "plumbing": 4, "carpentry": 1}),
    ]
    crew_rows = [["crew", "technicians", "objective", "weighted tardiness (h)",
                  "closed on time (%)", "urgent closed on time (%)",
                  "walking (min/technician/day)", "mean tickets waiting"]]
    out["crew"] = {}
    for label, mix in crews:
        r = experiment.simulate("savings+improve", c, days=DAYS,
                                crew_mix=mix, seed=BASE_SEED)
        crew_rows.append([label, sum(mix.values()), r["objective"],
                          r["weighted_tardiness"], r["sla_met_pct"],
                          r["by_priority"][1]["sla_met_pct"],
                          r["travel_per_tech_day"], r["mean_backlog"]])
        out["crew"][label] = {k: v for k, v in r.items() if k != "per_day"}
    write_csv("crew.csv", crew_rows)

    # ---------------------------------------------------------------
    # 5. a busy week
    # ---------------------------------------------------------------
    print("sweeping the complaint rate ...")
    surge_rows = [["complaints per day", "method", "objective",
                   "closed on time (%)", "urgent closed on time (%)",
                   "mean tickets waiting", "left unfinished"]]
    out["surge"] = {}
    for load in LOADS:
        for m in ("fifo", "savings+improve"):
            r = experiment.simulate(m, c, days=DAYS, tickets_per_day=load,
                                    seed=BASE_SEED)
            surge_rows.append([load, METHOD_LABEL[m], r["objective"],
                               r["sla_met_pct"], r["by_priority"][1]["sla_met_pct"],
                               r["mean_backlog"], r["unfinished_at_end"]])
            out["surge"][f"{load}-{m}"] = {k: v for k, v in r.items()
                                           if k != "per_day"}
    write_csv("surge.csv", surge_rows)

    # ---------------------------------------------------------------
    # 5b. how many technicians do you need at each complaint rate?
    # ---------------------------------------------------------------
    print("crossing crew size with the complaint rate ...")
    grid_rows = [["complaints per day", "technicians per trade", "crew",
                  "objective", "closed on time (%)",
                  "urgent closed on time (%)", "mean tickets waiting",
                  "left unfinished", "walking (min/technician/day)"]]
    out["grid"] = {}
    for load in GRID_LOADS:
        for per in GRID_CREWS:
            mix = {t: per for t in ("electrical", "plumbing", "carpentry")}
            r = experiment.simulate("savings+improve", c, days=DAYS,
                                    crew_mix=mix, tickets_per_day=load,
                                    seed=BASE_SEED)
            grid_rows.append([load, per, per * 3, r["objective"],
                              r["sla_met_pct"],
                              r["by_priority"][1]["sla_met_pct"],
                              r["mean_backlog"], r["unfinished_at_end"],
                              r["travel_per_tech_day"]])
            out["grid"][f"{load}-{per}"] = {k: v for k, v in r.items()
                                            if k != "per_day"}
    write_csv("crew_load_grid.csv", grid_rows)

    # ---------------------------------------------------------------
    # 6. do the conclusions depend on our assumptions?
    # ---------------------------------------------------------------
    print("checking sensitivity to the assumptions ...")
    sens_rows = [["assumption", "value", "method", "objective",
                  "walking (min/technician/day)", "closed on time (%)"]]
    out["sensitivity"] = []
    for alpha in (0.0, 0.05, 0.25):
        for m in ("fifo", "savings+improve"):
            r = experiment.simulate(m, c, days=DAYS, seed=BASE_SEED, alpha=alpha)
            sens_rows.append(["cost of a walking minute", alpha, METHOD_LABEL[m],
                              r["objective"], r["travel_per_tech_day"],
                              r["sla_met_pct"]])
            out["sensitivity"].append({"what": "alpha", "value": alpha,
                                       "method": m,
                                       "objective": r["objective"],
                                       "travel": r["travel_per_tech_day"]})
    original = campus_mod.DETOUR_FACTOR
    for detour in (1.2, 1.3, 1.4):
        campus_mod.DETOUR_FACTOR = detour
        cc = campus_mod.build()
        for m in ("fifo", "savings+improve"):
            r = experiment.simulate(m, cc, days=DAYS, seed=BASE_SEED)
            sens_rows.append(["walking detour factor", detour, METHOD_LABEL[m],
                              r["objective"], r["travel_per_tech_day"],
                              r["sla_met_pct"]])
            out["sensitivity"].append({"what": "detour", "value": detour,
                                       "method": m,
                                       "objective": r["objective"],
                                       "travel": r["travel_per_tech_day"]})
    campus_mod.DETOUR_FACTOR = original
    write_csv("sensitivity.csv", sens_rows)

    # ---------------------------------------------------------------
    # 7. how far off the true optimum are we?
    # ---------------------------------------------------------------
    print("solving small instances exactly by branch and bound ...")
    bb_rows = [["tickets", "exact optimum", "jobs done by the optimum",
                "first come first served", "savings", "priority insertion",
                "savings + improvement", "jobs done by savings + improvement",
                "gap of savings + improvement (%)",
                "nodes (nearest first, warm start)",
                "nodes (nearest first, cold start)",
                "nodes (arbitrary order, warm start)",
                "nodes (arbitrary order, cold start)", "seconds"]]
    out["exact"] = []
    for n in (6, 7, 8, 9, 10):
        b = exact.benchmark(c, n_jobs=n, seed=BASE_SEED)
        h = {r["method"]: r for r in b["heuristics"]}
        bb_rows.append([n, b["exact"]["cost"], b["exact"]["served"],
                        h["fifo"]["cost"],
                        h["savings"]["cost"], h["priority"]["cost"],
                        h["savings+improve"]["cost"],
                        h["savings+improve"]["served"],
                        h["savings+improve"].get("gap_pct"),
                        b["exact"]["nodes"], b["exact_cold"]["nodes"],
                        b["exact_naive_warm"]["nodes"],
                        b["exact_naive"]["nodes"],
                        b["exact"]["seconds"]])
        out["exact"].append({
            "n": n, "optimum": b["exact"]["cost"],
            "served": b["exact"]["served"],
            "heuristic": h["savings+improve"]["cost"],
            "savings": h["savings"]["cost"],
            "savings_gap": h["savings"].get("gap_pct"),
            "gap": h["savings+improve"].get("gap_pct"),
            "nodes_warm": b["exact"]["nodes"],
            "nodes_cold": b["exact_cold"]["nodes"],
            "nodes_arb_warm": b["exact_naive_warm"]["nodes"],
            "nodes_arb_cold": b["exact_naive"]["nodes"],
            "seconds": b["exact"]["seconds"]})
    write_csv("branch_and_bound.csv", bb_rows)

    # ---------------------------------------------------------------
    # 8. one day in detail, and the figures
    # ---------------------------------------------------------------
    tickets, team, day_plans = experiment.one_day_plans(c, seed=BASE_SEED)
    out["one_day"] = {m: {"cost": v["cost"], "travel": v["travel"],
                          "done": v["done"], "deferred": len(v["deferred"])}
                      for m, v in day_plans.items()}
    out["one_day"]["tickets"] = len(tickets)
    out["one_day"]["summary"] = inst.summarise(tickets)

    schedule_rows = [["technician", "stop", "location", "trade", "priority",
                      "repair (min)", "window opens", "window shuts"]]
    for name, route in sorted(day_plans["savings+improve"]["plan"].items()):
        for k, t in enumerate(route, start=1):
            schedule_rows.append([name, k, c["short"][t.site], t.trade,
                                  t.priority, t.service, t.win_start, t.win_end])
    write_csv("example_day_schedule.csv", schedule_rows)

    print("drawing figures ...")
    figures.build_all(c, results, day_plans, team)

    # ---------------------------------------------------------------
    # 9. the workbook
    # ---------------------------------------------------------------
    xlsx.write(os.path.join(ROOT, "out", "dispatch-model.xlsx"), [
        ("Locations", loc_rows),
        ("Walking minutes", walk_rows),
        ("Method comparison", rows),
        ("Day by day", per_day_rows),
        ("Crew scenarios", crew_rows),
        ("Complaint rate sweep", surge_rows),
        ("Crew vs complaint rate", grid_rows),
        ("Sensitivity", sens_rows),
        ("Branch and bound", bb_rows),
        ("Example day schedule", schedule_rows),
        ("Repeat seeds", seed_rows),
    ])

    # ---------------------------------------------------------------
    # 10. numbers for the report, and the summary for the web page
    # ---------------------------------------------------------------
    out["runtime_seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(RESULTS, "summary.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    write_numbers(out, results)
    write_tables(out, results, {"sensitivity": sens_rows})

    print(f"\ndone in {out['runtime_seconds']}s. "
          f"results in out/results, figures in out/figures.")
    return out


def latex_table(name, header, rows, align=None, note=None):
    """
    Write a table as a LaTeX fragment the report can include. Generating
    these from the same run that produced the numbers means a table can
    never disagree with the text around it.
    """
    os.makedirs(os.path.join(REPORT, "tables"), exist_ok=True)
    align = align or ("l" + "r" * (len(header) - 1))

    def cell(v):
        if v is None:
            return "--"
        s = str(v)
        # The callers already write percent signs the way LaTeX wants
        # them, so only the characters they do not handle are escaped.
        return s.replace("&", r"\&").replace("_", r"\_")

    lines = [r"\begin{tabular}{" + align + "}", r"\toprule"]
    lines.append(" & ".join(r"\textbf{" + cell(h) + "}" for h in header) + r" \\")
    lines.append(r"\midrule")
    for r in rows:
        lines.append(" & ".join(cell(v) for v in r) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    with open(os.path.join(REPORT, "tables", name + ".tex"), "w") as f:
        f.write("\n".join(lines) + "\n")


def write_tables(out, results, csvs):
    """Build every table the report shows, from the run that just happened."""
    latex_table("methods",
                ["Method", "Objective", "Late hours", "Walk/tech/day",
                 "On time", "Urgent on time", "Avg waiting"],
                [[METHOD_LABEL[m],
                  f"{r['objective']:,.0f}",
                  f"{r['weighted_tardiness']:,.0f}",
                  f"{r['travel_per_tech_day']:.1f} min",
                  f"{r['sla_met_pct']:.1f}\\%",
                  f"{r['by_priority'][1]['sla_met_pct']:.1f}\\%",
                  f"{r['mean_backlog']:.1f}"]
                 for m, r in results.items()])

    short_crew = {"4 electrical / 4 plumbing / 1 carpentry (9)":
                  "4 elec / 4 plumb / 1 carp (9)"}
    latex_table("crew",
                ["Crew", "People", "Objective", "On time", "Urgent",
                 "Walk/tech/day", "Queue"],
                [[short_crew.get(label, label), r["crew"],
                  f"{r['objective']:,.0f}",
                  f"{r['sla_met_pct']:.1f}\\%",
                  f"{r['by_priority'][1]['sla_met_pct']:.1f}\\%",
                  f"{r['travel_per_tech_day']:.1f} min",
                  f"{r['mean_backlog']:.1f}"]
                 for label, r in out["crew"].items()])

    srows = []
    for load in LOADS:
        for m in ("fifo", "savings+improve"):
            r = out["surge"][f"{load}-{m}"]
            srows.append([load, METHOD_LABEL[m],
                          f"{r['sla_met_pct']:.1f}\\%",
                          f"{r['by_priority'][1]['sla_met_pct']:.1f}\\%",
                          f"{r['mean_backlog']:.1f}", r["unfinished_at_end"]])
    latex_table("surge",
                ["Complaints", "Method", "On time", "Urgent on time",
                 "Avg waiting", "Unfinished at the end"], srows,
                align="llrrrr")

    latex_table("grid",
                ["Complaints/day", "Per trade", "Crew", "Objective",
                 "On time", "Urgent on time", "Avg waiting"],
                [[load, per, per * 3,
                  f"{out['grid'][f'{load}-{per}']['objective']:,.0f}",
                  f"{out['grid'][f'{load}-{per}']['sla_met_pct']:.1f}\\%",
                  f"{out['grid'][f'{load}-{per}']['by_priority'][1]['sla_met_pct']:.1f}\\%",
                  f"{out['grid'][f'{load}-{per}']['mean_backlog']:.1f}"]
                 for load in GRID_LOADS for per in GRID_CREWS])

    latex_table("bb",
                ["Jobs", "Done", "Optimum", "Savings", "Sav.+imp.",
                 "Gap", "Nodes", "Nodes, arb."],
                [[e["n"], e["served"], f"{e['optimum']:.3f}",
                  f"{e['savings']:.3f}",
                  f"{e['heuristic']:.3f}", f"{e['gap']:.1f}\\%",
                  f"{e['nodes_warm']:,}", f"{e['nodes_arb_cold']:,}"]
                 for e in out["exact"]])

    srows = []
    for row in csvs["sensitivity"][1:]:
        srows.append([row[0], row[1], row[2], f"{row[3]:,.0f}",
                      f"{row[4]:.1f} min", f"{row[5]:.1f}\\%"])
    latex_table("sensitivity",
                ["Assumption", "Value", "Method", "Objective",
                 "Walk/tech/day", "On time"], srows, align="llLrrr".replace("L", "l"))

    latex_table("assumptions",
                ["What", "Value we used", "Where it comes from"],
                [["Working day", f"{inst.WORKING_MINUTES_PER_DAY} minutes",
                  "09:00 to 17:30 with an hour for lunch"],
                 ["Walking speed", "75 m/min",
                  "4.5 km/h, an unhurried pace with a toolbag"],
                 ["Detour factor", f"{campus_mod.DETOUR_FACTOR}",
                  "paths go around lawns, not through them"],
                 ["Tunnel penalty", f"{campus_mod.TUNNEL_PENALTY_MIN} minutes",
                  "down the ramp and back up"],
                 ["Complaints per day", f"{inst.TICKETS_PER_DAY} on average",
                  "assumed; varied in Section 9"],
                 ["Share from dorms", f"{int(inst.DORM_SHARE*100)}\\%",
                  "dorms hold most of the people"],
                 ["Trade mix", "45 / 35 / 20\\%",
                  "electrical, plumbing, carpentry"],
                 ["Repair time", "22 / 38 / 30 min typical",
                  "by trade, drawn from a lognormal"],
                 ["Urgent share", "15\\%", "priority 1 of 3"],
                 ["Promise to the complainant", "4 h / 1 day / 3 days",
                  "by priority"],
                 ["Dorm access", "40\\% any time, 30\\% morning, 30\\% afternoon",
                  "somebody has to open the door"],
                 ["Cost of a walking minute", f"{dispatch.ALPHA}",
                  "relative to one weighted hour late"]],
                align="llp{58mm}")


def write_numbers(out, results):
    """Write report/numbers.tex so the report quotes the code, not a memory."""
    os.makedirs(REPORT, exist_ok=True)
    n = {}
    c = out["campus"]
    n["Locations"] = c["locations"]
    n["ComplaintSites"] = c["complaint_sites"]
    n["Dorms"] = c["dorms"]
    n["NewCampus"] = c["new_campus"]
    n["OldCampus"] = c["old_campus"]
    n["TunnelMetres"] = c["tunnel_m"]
    n["MeanWalk"] = c["mean_walk"]
    n["MeanSameCampus"] = c["mean_same_campus"]
    n["MeanCrossCampus"] = c["mean_cross_campus"]
    n["MaxWalk"] = c["max_walk"]

    short = {"fifo": "Fifo", "savings": "Sav", "priority": "Pri",
             "savings+improve": "Imp"}
    for m, key in short.items():
        r = out["methods"][m]
        n[key + "Obj"] = r["objective"]
        n[key + "Tard"] = r["weighted_tardiness"]
        n[key + "Travel"] = r["travel_per_tech_day"]
        n[key + "Sla"] = r["sla_met_pct"]
        n[key + "Urgent"] = r["by_priority"][1]["sla_met_pct"]
        n[key + "UrgentWait"] = r["by_priority"][1]["mean_wait_h"]
        n[key + "UrgentNinety"] = r["by_priority"][1]["p90_wait_h"]
        n[key + "Backlog"] = r["mean_backlog"]
        n[key + "Closed"] = r["completed"]
        n[key + "UrgentLate"] = r["urgent_late"]
        n[key + "UrgentUnavoidable"] = r["urgent_late_but_impossible"]
        n[key + "UrgentAvoidable"] = r["urgent_avoidable_misses"]
    n["UrgentTotal"] = out["methods"]["savings+improve"]["urgent_total"]
    n["UrgentImpossible"] = out["methods"]["savings+improve"]["urgent_impossible"]

    fifo, imp = out["methods"]["fifo"], out["methods"]["savings+improve"]
    n["TravelCutPct"] = round(100 * (fifo["travel_per_tech_day"]
                                     - imp["travel_per_tech_day"])
                              / fifo["travel_per_tech_day"], 1)
    n["ObjCutPct"] = round(100 * (fifo["objective"] - imp["objective"])
                           / fifo["objective"], 1)
    n["WalkSavedPerDay"] = round((fifo["travel_per_tech_day"]
                                  - imp["travel_per_tech_day"]) * imp["crew"], 0)

    ex = out["exact"]
    n["BbMaxTickets"] = max(e["n"] for e in ex)
    n["BbGapWorst"] = max(e["gap"] for e in ex)
    biggest = [e for e in ex if e["n"] == n["BbMaxTickets"]][0]
    n["BbServed"] = biggest["served"]
    n["BbNodesArbCold"] = f"{biggest['nodes_arb_cold']:,}"
    n["BbNodesArbWarm"] = f"{biggest['nodes_arb_warm']:,}"
    n["BbOrderCutPct"] = round(100 * (biggest["nodes_arb_cold"] - biggest["nodes_cold"])
                               / biggest["nodes_arb_cold"], 1)
    n["BbWarmCutPct"] = round(100 * (biggest["nodes_cold"] - biggest["nodes_warm"])
                              / biggest["nodes_cold"], 1)
    n["BbNodesWarm"] = f"{biggest['nodes_warm']:,}"
    n["BbNodesCold"] = f"{biggest['nodes_cold']:,}"
    n["BbNodeCutPct"] = round(100 * (biggest["nodes_cold"] - biggest["nodes_warm"])
                              / biggest["nodes_cold"], 0)
    n["BbSeconds"] = biggest["seconds"]
    n["BbSavWorstGap"] = max(e["savings_gap"] for e in ex)
    worst = max(ex, key=lambda e: e["savings_gap"])
    n["BbSavWorstJobs"] = worst["n"]
    n["BbSavWorstTimes"] = round(worst["savings"] / worst["optimum"], 1)

    for label, r in out["crew"].items():
        if label.startswith("2 "):
            key = "CrewSix"
        elif label.startswith("3 "):
            key = "CrewNine"
        elif label.startswith("4 of"):
            key = "CrewTwelve"
        elif label.startswith("5 of"):
            key = "CrewFifteen"
        else:
            key = "CrewRebal"
        n[key + "Obj"] = r["objective"]
        n[key + "Sla"] = r["sla_met_pct"]
        n[key + "Urgent"] = r["by_priority"][1]["sla_met_pct"]

    for key, tag in (("58-fifo", "SurgeLowFifo"), ("58-savings+improve", "SurgeLowImp"),
                     ("85-fifo", "SurgeHighFifo"),
                     ("85-savings+improve", "SurgeHighImp")):
        r = out["surge"][key]
        n[tag + "Sla"] = r["sla_met_pct"]
        n[tag + "Backlog"] = r["mean_backlog"]
        n[tag + "Urgent"] = r["by_priority"][1]["sla_met_pct"]

    # LaTeX control sequences are letters only, so a macro cannot be called
    # \NLoad58Sla. Numbers in macro names are spelled out instead.
    WORD = {3: "Three", 4: "Four", 5: "Five", 40: "Forty", 50: "Fifty",
            58: "FiftyEight", 70: "Seventy", 85: "EightyFive",
            100: "Hundred", 110: "OneHundredTen"}

    # the load sweep: where the optimised plan starts to give way
    n["LoadMin"] = min(LOADS)
    n["LoadMax"] = max(LOADS)
    for load in LOADS:
        r = out["surge"][f"{load}-savings+improve"]
        n[f"Load{WORD[load]}Sla"] = r["sla_met_pct"]
        n[f"Load{WORD[load]}Urgent"] = r["by_priority"][1]["sla_met_pct"]
        n[f"Load{WORD[load]}Backlog"] = r["mean_backlog"]
        f = out["surge"][f"{load}-fifo"]
        n[f"Load{WORD[load]}FifoSla"] = f["sla_met_pct"]
    coping = [l for l in LOADS
              if out["surge"][f"{l}-savings+improve"]["mean_backlog"] < 5]
    n["LoadLastCoping"] = max(coping) if coping else min(LOADS)

    # the crew-against-load grid
    for load in GRID_LOADS:
        for per in GRID_CREWS:
            r = out["grid"][f"{load}-{per}"]
            tag = f"Grid{WORD[load]}x{WORD[per]}"
            n[tag + "Obj"] = f"{round(r['objective']):,}"
            n[tag + "Sla"] = r["sla_met_pct"]
            n[tag + "Urgent"] = r["by_priority"][1]["sla_met_pct"]
            n[tag + "Backlog"] = r["mean_backlog"]

    def smallest_ok(load):
        """Fewest technicians per trade that keeps the queue under control."""
        for per in GRID_CREWS:
            if out["grid"][f"{load}-{per}"]["mean_backlog"] < 5:
                return per
        return None
    for load in GRID_LOADS:
        got = smallest_ok(load)
        n[f"Need{WORD[load]}"] = got * 3 if got else "more than 15"

    sd = out["seeds"]
    n["SeedCount"] = len(SEEDS)
    n["SeedImpMin"] = sd["savings+improve"]["min"]
    n["SeedImpMax"] = sd["savings+improve"]["max"]
    n["SeedFifoMin"] = sd["fifo"]["min"]
    n["SeedFifoMax"] = sd["fifo"]["max"]

    one = out["one_day"]
    n["DayTickets"] = one["tickets"]
    n["DayFifoTravel"] = one["fifo"]["travel"]
    n["DayImpTravel"] = one["savings+improve"]["travel"]
    n["Days"] = DAYS
    n["TicketsPerDay"] = inst.TICKETS_PER_DAY
    n["WorkingMinutes"] = inst.WORKING_MINUTES_PER_DAY
    n["Alpha"] = dispatch.ALPHA

    # what pricing walking is actually worth: compare the best method with
    # alpha at its normal value against alpha switched off entirely
    zero = [x for x in out["sensitivity"]
            if x["what"] == "alpha" and float(x["value"]) == 0.0
            and x["method"] == "savings+improve"][0]
    n["AlphaZeroTravel"] = zero["travel"]
    n["AlphaWorthMinutes"] = round(zero["travel"]
                                   - imp["travel_per_tech_day"], 1)

    lines = ["% Generated by src/study.py - do not edit by hand.",
             "% Rerun 'python3 run.py' to refresh these numbers."]
    for k, v in n.items():
        lines.append(f"\\newcommand{{\\N{k}}}{{{v}}}")
    with open(os.path.join(REPORT, "numbers.tex"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return n


if __name__ == "__main__":
    main()
