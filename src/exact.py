"""
An exact solver for one technician's day, by branch and bound.

The heuristics in dispatch.py are fast but come with no guarantee. To know
how good they actually are we need something to compare them against, so
here we solve a small version of the problem exactly: one technician, one
trade, a handful of tickets, every possible order considered.

How the search works
--------------------
A node of the search tree is a partial route - the jobs done so far, in
order. Its children are the ways of appending one more unvisited job. A full
route is a leaf. Searching every leaf is hopeless (ten jobs already give
3.6 million orders), so at every node we compute a lower bound on the best
any completion of that partial route could achieve. If that bound is already
worse than the best full route found so far, the whole branch is thrown away
without being explored - it has been fathomed.

The bound has two parts, and both are deliberately easy to justify:

  travel    every job still to do must be reached from somewhere, so the
            cheapest walk into it is a floor on what that leg can cost. We
            add up those cheapest legs.
  lateness  a job still to do cannot possibly finish before the current time
            plus its own repair time, so if that is already past its deadline
            the lateness is unavoidable and can be added to the bound.

Both ignore the ordering, which is exactly why they are cheap to compute and
why they never overstate the true cost.

The incumbent
-------------
We start the search already holding the answer the heuristic produced. That
is the incumbent, and it lets the bound start fathoming immediately rather
than waiting for the search to stumble on a good route by itself. Running the
same search with and without it shows how much the heuristic is worth, which
is reported at the bottom of this file.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatch import ALPHA, run_route, route_cost, deferral_cost
from instance import WORKING_MINUTES_PER_DAY


class Counter:
    def __init__(self):
        self.nodes = 0
        self.fathomed = 0


def solve_exact(tickets, walk, day, home, alpha=ALPHA, incumbent_route=None,
                time_limit=60.0, nearest_first=True):
    """
    Find the cheapest feasible order for one technician to do these tickets.

    'home' is the store room the technician leaves from and returns to, so the
    same set of jobs has a different optimum for an electrician working out of
    Dorm 7 than for a plumber working out of Dorm 24.

    Returns a dict with the best route, its cost, how many nodes the search
    looked at, and whether it finished or ran out of time.
    """
    n = len(tickets)
    sites = [t.site for t in tickets]
    day_start = day * WORKING_MINUTES_PER_DAY

    # What each ticket costs if we simply do not get to it today. The
    # technician is allowed to leave jobs undone - that is a real option, and
    # the heuristics take it - so the search has to be allowed to take it too,
    # otherwise we would be comparing against an "optimum" that is solving a
    # different and harder problem than the heuristics are.
    defer = [deferral_cost(t, day) for t in tickets]

    best = {"route": None, "cost": float("inf"), "deferred": None}
    if incumbent_route is not None:
        c = route_cost(incumbent_route, walk, day, home, alpha)
        if c is not None:
            left = [t for t in tickets if t not in incumbent_route]
            best = {"route": list(incumbent_route),
                    "cost": c + sum(deferral_cost(t, day) for t in left),
                    "deferred": left}

    counter = Counter()
    start_time = time.time()
    timed_out = [False]

    def recurse(order, remaining, here, now, travel, late):
        counter.nodes += 1
        if time.time() - start_time > time_limit:
            timed_out[0] = True
            return

        # Stopping here and deferring whatever is left is itself a complete,
        # legal plan, so every node is a candidate answer and not just the
        # ones that have run out of jobs.
        back = walk[here][home]
        if now + back <= WORKING_MINUTES_PER_DAY:
            cost = late + alpha * (travel + back) + sum(defer[j] for j in remaining)
            if cost < best["cost"]:
                best["route"] = [tickets[i] for i in order]
                best["cost"] = cost
                best["deferred"] = [tickets[j] for j in remaining]

        if not remaining:
            return

        # --- the bound -------------------------------------------------
        # Two parts, both of which have to be true of any way of finishing
        # from here.
        #
        # Travel: whatever has been walked already, plus the walk home. The
        # walking times come from a shortest-path calculation, so going
        # anywhere else first and then home can only cost more.
        #
        # Lateness: each job still open will either be done today, and the
        # earliest it could possibly finish gives its smallest possible
        # lateness, or be left for tomorrow at its deferral cost. Whichever
        # of the two is cheaper is a floor on what that job will cost.
        travel_floor = alpha * (travel + back)
        late_floor = 0.0
        for j in remaining:
            tk = tickets[j]
            earliest_done = max(now, tk.win_start) + tk.service
            if_done = tk.weight * max(0.0,
                                      day_start + earliest_done - tk.due_abs) / 60.0
            late_floor += min(if_done, defer[j])
        if late + travel_floor + late_floor >= best["cost"]:
            counter.fathomed += 1
            return
        # ---------------------------------------------------------------

        # Which child to explore first. Going to the nearest job first means
        # the search dives straight towards a sensible route and finds a good
        # incumbent on its own; exploring in arbitrary order instead shows
        # how much that choice is worth.
        if nearest_first:
            order_by_near = sorted(remaining, key=lambda j: walk[here][sites[j]])
        else:
            order_by_near = list(remaining)
        for j in order_by_near:
            tk = tickets[j]
            arrive = now + walk[here][sites[j]]
            begin = max(arrive, tk.win_start)
            if begin > tk.win_end:
                continue
            done = begin + tk.service
            if done > WORKING_MINUTES_PER_DAY:
                continue
            recurse(order + [j], [k for k in remaining if k != j],
                    sites[j], done,
                    travel + walk[here][sites[j]],
                    late + tk.weight * max(0.0, day_start + done - tk.due_abs) / 60.0)

    recurse([], list(range(n)), home, 0.0, 0.0, 0.0)

    return {
        "route": best["route"],
        "deferred": best["deferred"],
        "served": len(best["route"]) if best["route"] is not None else 0,
        "cost": round(best["cost"], 3) if best["route"] is not None else None,
        "nodes": counter.nodes,
        "fathomed": counter.fathomed,
        "seconds": round(time.time() - start_time, 2),
        "complete": not timed_out[0],
        "n_tickets": n,
    }


def benchmark(campus, day=0, seed=2026, n_jobs=9, trade="electrical",
              tickets_per_day=None, alpha=ALPHA):
    """
    Build a small single-technician instance, solve it exactly, and compare
    the heuristics against the optimum.
    """
    import random
    import instance as inst
    import dispatch

    walk = campus["walk"]
    rng = random.Random(seed)
    tickets, _ = inst.generate_day(day, rng, campus,
                                   tickets_per_day or inst.TICKETS_PER_DAY)
    pool = [t for t in tickets if t.trade == trade][:n_jobs]
    home = campus["depot"][trade]
    one = [{"name": "tech-1", "trade": trade, "home": home}]

    rows = []
    heuristic_routes = {}
    for name, fn in dispatch.METHODS.items():
        plan, deferred = fn(pool, one, walk, day, alpha)
        route = plan["tech-1"]
        # The whole cost of the decision, not just the cost of the route: a
        # method that quietly leaves three jobs undone has to be charged for
        # them, or it would look better than one that did the work.
        c = dispatch.plan_cost(plan, deferred, walk, day,
                               {"tech-1": home}, alpha)
        heuristic_routes[name] = route
        rows.append({"method": name, "cost": round(c, 3) if c is not None else None,
                     "served": len(route), "deferred": len(deferred)})

    # Three runs of the same search, to separate what the bound is worth
    # from what a good starting solution is worth.
    warm = solve_exact(pool, walk, day, home, alpha,
                       incumbent_route=heuristic_routes["savings+improve"])
    cold = solve_exact(pool, walk, day, home, alpha, incumbent_route=None)
    naive = solve_exact(pool, walk, day, home, alpha, incumbent_route=None,
                        nearest_first=False)
    naive_warm = solve_exact(pool, walk, day, home, alpha, nearest_first=False,
                             incumbent_route=heuristic_routes["savings+improve"])

    for r in rows:
        if r["cost"] is not None and warm["cost"]:
            r["gap_pct"] = round(100 * (r["cost"] - warm["cost"]) / warm["cost"], 1)
    return {"instance": pool, "heuristics": rows, "exact": warm,
            "exact_cold": cold, "exact_naive": naive,
            "exact_naive_warm": naive_warm, "trade": trade,
            "home": home, "home_name": campus["names"][home]}


if __name__ == "__main__":
    import campus as campus_mod

    c = campus_mod.build()
    for n in (7, 8, 9, 10):
        b = benchmark(c, n_jobs=n)
        e, cold = b["exact"], b["exact_cold"]
        print(f"\n{n} tickets, one electrician")
        print(f"  exact optimum      {e['cost']:8.3f}   "
              f"{e['nodes']:>9,} nodes   {e['seconds']:5.2f}s"
              f"{'' if e['complete'] else '  (TIMED OUT)'}")
        print(f"  nodes explored:  nearest-first dive, warm start "
              f"{e['nodes']:>8,}")
        print(f"                   nearest-first dive, cold start "
              f"{cold['nodes']:>8,}")
        print(f"                   arbitrary order,    warm start "
              f"{b['exact_naive_warm']['nodes']:>8,}")
        print(f"                   arbitrary order,    cold start "
              f"{b['exact_naive']['nodes']:>8,}")
        for r in b["heuristics"]:
            gap = r.get("gap_pct")
            print(f"  {r['method']:17s} {r['cost']:8.3f}"
                  f"   gap {gap:5.1f}%" if gap is not None else "")
