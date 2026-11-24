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

from dispatch import ALPHA, DEPOT, run_route, route_cost
from instance import WORKING_MINUTES_PER_DAY


class Counter:
    def __init__(self):
        self.nodes = 0
        self.fathomed = 0


def _cheapest_entry(walk, sites, candidates):
    """
    For each job still to do, the cheapest walk into it from anywhere we might
    plausibly be. Summed, this is a floor on the travel still to come.
    """
    total = 0.0
    for j in candidates:
        best = min(walk[i][sites[j]]
                   for i in set([DEPOT] + [sites[k] for k in candidates])
                   if i != sites[j])
        total += best
    return total


def solve_exact(tickets, walk, day, alpha=ALPHA, incumbent_route=None,
                time_limit=60.0, nearest_first=True):
    """
    Find the cheapest feasible order for one technician to do these tickets.

    Returns a dict with the best route, its cost, how many nodes the search
    looked at, and whether it finished or ran out of time.
    """
    n = len(tickets)
    sites = [t.site for t in tickets]
    day_start = day * WORKING_MINUTES_PER_DAY

    best = {"route": None, "cost": float("inf")}
    if incumbent_route is not None:
        c = route_cost(incumbent_route, walk, day, alpha)
        if c is not None:
            best = {"route": list(incumbent_route), "cost": c}

    counter = Counter()
    start_time = time.time()
    timed_out = [False]

    def recurse(order, remaining, here, now, travel, late):
        counter.nodes += 1
        if time.time() - start_time > time_limit:
            timed_out[0] = True
            return

        if not remaining:
            total_travel = travel + walk[here][DEPOT]
            if now + walk[here][DEPOT] > WORKING_MINUTES_PER_DAY:
                return
            cost = late + alpha * total_travel
            if cost < best["cost"]:
                best["route"] = [tickets[i] for i in order]
                best["cost"] = cost
            return

        # --- the bound -------------------------------------------------
        travel_floor = alpha * (travel + _cheapest_entry(walk, sites, remaining))
        late_floor = 0.0
        for j in remaining:
            tk = tickets[j]
            earliest_done = max(now, tk.win_start) + tk.service
            late_floor += tk.weight * max(0.0,
                                          day_start + earliest_done - tk.due_abs) / 60.0
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

    recurse([], list(range(n)), DEPOT, 0.0, 0.0, 0.0)

    return {
        "route": best["route"],
        "cost": round(best["cost"], 3) if best["route"] else None,
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
    one = [{"name": "tech-1", "trade": trade}]

    rows = []
    heuristic_routes = {}
    for name, fn in dispatch.METHODS.items():
        plan, deferred = fn(pool, one, walk, day, alpha)
        route = plan["tech-1"]
        c = route_cost(route, walk, day, alpha)
        heuristic_routes[name] = route
        rows.append({"method": name, "cost": round(c, 3) if c else None,
                     "served": len(route), "deferred": len(deferred)})

    # Three runs of the same search, to separate what the bound is worth
    # from what a good starting solution is worth.
    warm = solve_exact(pool, walk, day, alpha,
                       incumbent_route=heuristic_routes["savings+improve"])
    cold = solve_exact(pool, walk, day, alpha, incumbent_route=None)
    naive = solve_exact(pool, walk, day, alpha, incumbent_route=None,
                        nearest_first=False)
    naive_warm = solve_exact(pool, walk, day, alpha, nearest_first=False,
                             incumbent_route=heuristic_routes["savings+improve"])

    for r in rows:
        if r["cost"] is not None and warm["cost"]:
            r["gap_pct"] = round(100 * (r["cost"] - warm["cost"]) / warm["cost"], 1)
    return {"instance": pool, "heuristics": rows, "exact": warm,
            "exact_cold": cold, "exact_naive": naive,
            "exact_naive_warm": naive_warm, "trade": trade}


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
