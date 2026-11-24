"""
Runs the dispatcher over many simulated days and records what happened.

A single day tells you very little, because a day can be lucky or unlucky.
What matters is how a method behaves over a term's worth of days, with
yesterday's unfinished work still sitting in today's queue. That carryover is
the whole reason an apparently small daily difference matters: a method that
leaves three tickets undone every day does not stay three tickets behind, it
falls further behind every day.

Every method is given exactly the same stream of complaints, generated from
the same random seed, so any difference in the results is caused by the
dispatching and nothing else.
"""

import random
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import campus as campus_mod
import instance as inst
import dispatch
from instance import WORKING_MINUTES_PER_DAY as DAY


def simulate(method, campus, days=30, per_trade=3, crew_mix=None,
             tickets_per_day=inst.TICKETS_PER_DAY, seed=2026, alpha=dispatch.ALPHA):
    """
    Run one method over a number of days.

    crew_mix, if given, overrides per_trade: it is a dict like
    {"electrical": 4, "plumbing": 4, "carpentry": 1}.
    """
    walk = campus["walk"]
    if crew_mix:
        team = []
        for trade, n in crew_mix.items():
            for k in range(n):
                team.append({"name": f"{trade[:4]}-{k+1}", "trade": trade,
                             "home": campus["depot"][trade]})
    else:
        team = inst.crew(campus, per_trade)
    home_of = dispatch.homes(team)

    solver = dispatch.METHODS[method]
    rng = random.Random(seed)

    backlog = []
    next_id = 0
    completed = []
    per_day = []

    for day in range(days):
        new, next_id = inst.generate_day(day, rng, campus,
                                         tickets_per_day, next_id)
        queue = backlog + new

        plan, deferred = solver(queue, team, walk, day, alpha)

        travel = dispatch.plan_travel(plan, walk, day, home_of)
        done_today = 0
        for name, route in plan.items():
            ok, _, finish = dispatch.run_route(route, walk, day, home_of[name])
            if not ok:
                raise RuntimeError(f"{method} produced an infeasible route")
            for tk in route:
                tk.done_abs = finish[tk.tid]
                completed.append(tk)
                done_today += 1

        backlog = deferred
        per_day.append({
            "day": day,
            "raised": len(new),
            "queue": len(queue),
            "done": done_today,
            "backlog": len(backlog),
            "travel_min": round(travel, 1),
            "weighted_tardiness": round(sum(
                tk.weight * tk.tardiness_hours(tk.done_abs)
                for route in plan.values() for tk in route), 2),
        })

    return summarise(method, completed, backlog, per_day, team, days)


def summarise(method, completed, backlog, per_day, team, days):
    """Turn the raw run into the numbers that go in the report."""
    by_prio = {}
    for p in (1, 2, 3):
        got = [t for t in completed if t.priority == p]
        waits = [(t.done_abs - t.raised_day * DAY) / 60 for t in got]
        met = sum(1 for t in got if t.done_abs <= t.due_abs)
        by_prio[p] = {
            "n": len(got),
            "sla_met_pct": round(100 * met / len(got), 1) if got else None,
            "mean_wait_h": round(statistics.mean(waits), 2) if waits else None,
            "p90_wait_h": round(sorted(waits)[int(0.9 * (len(waits) - 1))], 2)
                          if waits else None,
            "max_wait_h": round(max(waits), 2) if waits else None,
        }

    # Why do urgent tickets still miss their deadline? Some of them never had
    # a chance: if a complaint can only be accessed in the afternoon and the
    # repair itself is long, then even a technician already standing at the
    # door cannot finish it within the four hours we promised. Those breaches
    # are built into the promise, not caused by the dispatching, and it is
    # worth separating the two.
    from instance import PRIORITY
    urgent = [t for t in completed if t.priority == 1]
    late_urgent = [t for t in urgent if t.done_abs > t.due_abs]
    impossible = [t for t in urgent
                  if t.win_start + t.service > PRIORITY[1]["sla"]]
    late_and_impossible = [t for t in late_urgent
                           if t.win_start + t.service > PRIORITY[1]["sla"]]

    total_tard = sum(t.weight * t.tardiness_hours(t.done_abs) for t in completed)
    travel = sum(d["travel_min"] for d in per_day)
    met_all = sum(1 for t in completed if t.done_abs <= t.due_abs)

    return {
        "method": method,
        "days": days,
        "crew": len(team),
        "completed": len(completed),
        "unfinished_at_end": len(backlog),
        "weighted_tardiness": round(total_tard, 1),
        "travel_min": round(travel, 1),
        "travel_per_tech_day": round(travel / (len(team) * days), 1),
        "sla_met_pct": round(100 * met_all / len(completed), 1) if completed else None,
        "objective": round(total_tard + dispatch.ALPHA * travel, 1),
        "by_priority": by_prio,
        "final_backlog": len(backlog),
        "mean_backlog": round(statistics.mean(d["backlog"] for d in per_day), 1),
        "urgent_total": len(urgent),
        "urgent_late": len(late_urgent),
        "urgent_impossible": len(impossible),
        "urgent_late_but_impossible": len(late_and_impossible),
        "urgent_avoidable_misses": len(late_urgent) - len(late_and_impossible),
        "per_day": per_day,
    }


def compare_methods(campus, **kw):
    """Run every method on the same ticket stream."""
    return {m: simulate(m, campus, **kw) for m in dispatch.METHODS}


def one_day_plans(campus, day=0, per_trade=3, seed=2026,
                  tickets_per_day=inst.TICKETS_PER_DAY):
    """
    Produce the plans for a single day under each method, for the map
    figures and the worked example in the report.
    """
    walk = campus["walk"]
    team = inst.crew(campus, per_trade)
    home_of = dispatch.homes(team)
    rng = random.Random(seed)

    # Draw days until we get one with a typical number of complaints. The
    # first day of a given seed can easily be unusually busy or unusually
    # quiet, and a worked example should show an ordinary day rather than an
    # outlier that flatters or embarrasses the method.
    tid = 0
    for d in range(60):
        tickets, tid = inst.generate_day(day, rng, campus, tickets_per_day, tid)
        if abs(len(tickets) - tickets_per_day) <= 3:
            break
    out = {}
    for name, fn in dispatch.METHODS.items():
        plan, deferred = fn(tickets, team, walk, day)
        out[name] = {
            "plan": plan,
            "deferred": deferred,
            "cost": round(dispatch.plan_cost(plan, deferred, walk, day,
                                             home_of), 2),
            "travel": round(dispatch.plan_travel(plan, walk, day, home_of), 1),
            "done": sum(len(r) for r in plan.values()),
        }
    return tickets, team, out


if __name__ == "__main__":
    c = campus_mod.build()
    print("running 30 days for each method ...\n")
    results = compare_methods(c, days=30)

    hdr = (f"{'method':17s} {'objective':>10s} {'w.tardiness':>12s} "
           f"{'travel/tech/day':>16s} {'SLA met':>8s} {'backlog':>8s}")
    print(hdr)
    print("-" * len(hdr))
    for m, r in results.items():
        print(f"{m:17s} {r['objective']:10.1f} {r['weighted_tardiness']:12.1f} "
              f"{r['travel_per_tech_day']:16.1f} {r['sla_met_pct']:7.1f}% "
              f"{r['mean_backlog']:8.1f}")

    print("\nurgent (priority 1) tickets only:")
    for m, r in results.items():
        p = r["by_priority"][1]
        print(f"  {m:17s} SLA met {p['sla_met_pct']:5.1f}%   "
              f"mean wait {p['mean_wait_h']:5.2f} h   "
              f"90th percentile {p['p90_wait_h']:5.2f} h")
