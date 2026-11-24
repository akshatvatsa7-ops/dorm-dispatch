"""
The dispatcher: given a day's tickets and a crew, decide who goes where and
in what order.

Four methods are implemented, in increasing order of effort:

  fifo             work the queue in the order complaints came in. This is
                   the baseline - roughly what happens today.
  savings          Clarke and Wright's savings heuristic, adapted so that a
                   merge is only accepted if the resulting route still fits
                   the shift, respects every access window, and stays within
                   the technician's trade.
  priority         insert tickets one at a time, always taking the one with
                   the best urgency per extra minute of walking. This is the
                   bang-to-buck idea from the profit-maximising tour.
  savings+improve  run savings, then improve the result with 2-opt inside a
                   route and Or-opt both inside and across routes.

Everything is judged by the same objective:

    cost  =  sum over tickets of  (weight x hours late)  +  alpha x walking minutes

A minute of walking is worth far less than an hour of lateness on an urgent
complaint, which is the point: walking is the tiebreaker, service is the goal.
"""

from instance import WORKING_MINUTES_PER_DAY, TRADES

# What one minute of walking costs relative to one weighted hour of lateness.
ALPHA = 0.05

DEPOT = 0


# ---------------------------------------------------------------------------
# Evaluating a route
# ---------------------------------------------------------------------------

def run_route(route, walk, day):
    """
    Walk through a technician's day minute by minute and see what happens.

    Returns (feasible, travel_minutes, finish_times) where finish_times maps
    each ticket to the absolute working minute at which it was completed.
    A route is infeasible if the technician reaches a job after its access
    window has shut, or cannot get back to the depot by the end of the shift.
    """
    t = 0.0
    travel = 0.0
    here = DEPOT
    finish = {}
    day_start = day * WORKING_MINUTES_PER_DAY

    for tk in route:
        leg = walk[here][tk.site]
        travel += leg
        arrive = t + leg
        start = max(arrive, tk.win_start)
        if start > tk.win_end:
            return False, 0.0, {}            # turned up after the door shut
        done = start + tk.service
        if done > WORKING_MINUTES_PER_DAY:
            return False, 0.0, {}            # ran past the end of the shift
        finish[tk.tid] = day_start + done
        t = done
        here = tk.site

    back = walk[here][DEPOT]
    travel += back
    if t + back > WORKING_MINUTES_PER_DAY:
        return False, 0.0, {}                # could not get home in time
    return True, travel, finish


def route_cost(route, walk, day, alpha=ALPHA):
    """Objective contribution of one route. Returns None if infeasible."""
    ok, travel, finish = run_route(route, walk, day)
    if not ok:
        return None
    late = sum(tk.weight * tk.tardiness_hours(finish[tk.tid]) for tk in route)
    return late + alpha * travel


def deferral_cost(ticket, day):
    """
    What it costs to leave a ticket for another day.

    If we do not do it today the earliest it realistically gets done is
    sometime tomorrow, so we charge it the lateness it would pick up by the
    end of tomorrow. Without this the optimiser would happily defer
    everything, since an unscheduled ticket costs nothing today.
    """
    projected = (day + 2) * WORKING_MINUTES_PER_DAY
    return ticket.weight * max(0.0, projected - ticket.due_abs) / 60.0


def plan_cost(plan, deferred, walk, day, alpha=ALPHA):
    """Total objective for a whole day: every route, plus what we put off."""
    total = 0.0
    for route in plan.values():
        c = route_cost(route, walk, day, alpha)
        if c is None:
            return None
        total += c
    total += sum(deferral_cost(t, day) for t in deferred)
    return total


def plan_travel(plan, walk, day):
    return sum(run_route(r, walk, day)[1] for r in plan.values())


# ---------------------------------------------------------------------------
# Method 1: first come, first served
# ---------------------------------------------------------------------------

def solve_fifo(tickets, team, walk, day, alpha=ALPHA):
    """
    The baseline. Take complaints in the order they were raised and give each
    one to the technician of the right trade who is free earliest. No thought
    is given to where the job is, which is exactly the problem.
    """
    plan = {m["name"]: [] for m in team}
    deferred = []
    queue = sorted(tickets, key=lambda t: (t.raised_day, t.tid))

    for tk in queue:
        candidates = [m for m in team if m["trade"] == tk.trade]
        placed = False
        # try the technician with the least work so far
        for m in sorted(candidates,
                        key=lambda m: sum(x.service for x in plan[m["name"]])):
            trial = plan[m["name"]] + [tk]
            if run_route(trial, walk, day)[0]:
                plan[m["name"]] = trial
                placed = True
                break
        if not placed:
            deferred.append(tk)
    return plan, deferred


# ---------------------------------------------------------------------------
# Method 2: Clarke and Wright savings
# ---------------------------------------------------------------------------

def solve_savings(tickets, team, walk, day, alpha=ALPHA):
    """
    Clarke and Wright, one trade at a time.

    Start with every ticket on its own out-and-back trip from the depot. The
    saving from doing i and j on the same trip instead of two separate ones is

        s_ij = walk[depot][i] + walk[depot][j] - walk[i][j]

    Work down the savings list, merging two routes whenever the merge is
    legal. Because the depot is on the old campus and most dorms are on the
    new campus, walk[depot][i] is large for nearly every ticket, so the
    savings are large too: the heuristic is strongly pushed towards bundling
    dorm visits into one trip across the tunnel, which is precisely what a
    sensible human dispatcher would do.
    """
    plan = {m["name"]: [] for m in team}
    deferred = []

    for trade in TRADES:
        crew_here = [m["name"] for m in team if m["trade"] == trade]
        jobs = [t for t in tickets if t.trade == trade]
        if not jobs:
            continue

        routes = []
        for tk in jobs:
            if run_route([tk], walk, day)[0]:
                routes.append([tk])
            else:
                deferred.append(tk)          # cannot be done at all today

        savings = []
        for a in range(len(jobs)):
            for b in range(a + 1, len(jobs)):
                i, j = jobs[a], jobs[b]
                s = walk[DEPOT][i.site] + walk[DEPOT][j.site] - walk[i.site][j.site]
                savings.append((s, a, b))
        savings.sort(reverse=True)

        where = {id(r[0]): k for k, r in enumerate(routes)}

        def find(tk):
            for k, r in enumerate(routes):
                if r and tk in r:
                    return k
            return None

        for s, a, b in savings:
            i, j = jobs[a], jobs[b]
            ri, rj = find(i), find(j)
            if ri is None or rj is None or ri == rj:
                continue
            A, B = routes[ri], routes[rj]
            # both tickets must still be at an end of their route, which is
            # what "adjacent to the depot" means once the depot is dropped
            merged = None
            for cand in ([A + B] if (A[-1] is i and B[0] is j) else []) + \
                        ([B + A] if (B[-1] is j and A[0] is i) else []) + \
                        ([A + B[::-1]] if (A[-1] is i and B[-1] is j) else []) + \
                        ([A[::-1] + B] if (A[0] is i and B[0] is j) else []):
                if run_route(cand, walk, day)[0]:
                    merged = cand
                    break
            if merged is None:
                continue
            routes[ri] = merged
            routes[rj] = []

        routes = [r for r in routes if r]
        routes = _assign_routes_to_crew(routes, crew_here, plan, deferred, day)

    return plan, deferred


def _assign_routes_to_crew(routes, crew_here, plan, deferred, day):
    """
    Savings merging does not know how many technicians exist, so it can come
    back with more routes than we have people. We keep the most valuable
    routes - the ones carrying the most urgent work - and defer the rest.
    """
    routes.sort(key=lambda r: sum(deferral_cost(t, day) for t in r),
                reverse=True)
    for k, name in enumerate(crew_here):
        if k < len(routes):
            plan[name] = routes[k]
    for extra in routes[len(crew_here):]:
        deferred.extend(extra)
    return routes


# ---------------------------------------------------------------------------
# Method 3: priority insertion (bang to buck)
# ---------------------------------------------------------------------------

def cheapest_insertion(route, tk, walk, day, alpha=ALPHA):
    """
    Find where in an existing route a ticket fits most cheaply.
    Returns (extra_cost, new_route) or None if it does not fit anywhere.
    """
    base = route_cost(route, walk, day, alpha)
    if base is None:
        return None
    best = None
    for pos in range(len(route) + 1):
        cand = route[:pos] + [tk] + route[pos:]
        c = route_cost(cand, walk, day, alpha)
        if c is None:
            continue
        if best is None or c - base < best[0]:
            best = (c - base, cand)
    return best


def solve_priority(tickets, team, walk, day, alpha=ALPHA):
    """
    Build the routes by repeatedly inserting whichever ticket gives the most
    urgency for the least extra walking.

    For each unplaced ticket we work out the cheapest way to slot it into any
    technician's route, which costs delta minutes. We then pick the ticket
    with the largest ratio of what we avoid by doing it today, to what it
    costs to fit in. This is the bang-to-buck rule, and it is what makes the
    method naturally sensible when there is more work than time: the urgent
    jobs go in first and the minor ones are the ones left over.
    """
    plan = {m["name"]: [] for m in team}
    deferred = []
    remaining = list(tickets)

    while remaining:
        best = None
        for tk in remaining:
            value = deferral_cost(tk, day) + tk.weight * 0.1
            for m in team:
                if m["trade"] != tk.trade:
                    continue
                got = cheapest_insertion(plan[m["name"]], tk, walk, day, alpha)
                if got is None:
                    continue
                delta, cand = got
                ratio = value / max(delta, 0.01)
                if best is None or ratio > best[0]:
                    best = (ratio, tk, m["name"], cand)
        if best is None:
            deferred.extend(remaining)
            break
        _, tk, name, cand = best
        plan[name] = cand
        remaining.remove(tk)

    return plan, deferred


# ---------------------------------------------------------------------------
# Method 4: improvement heuristics
# ---------------------------------------------------------------------------

def two_opt(route, walk, day, alpha=ALPHA):
    """
    Reverse a stretch of the route and keep the result if it is better.

    On a map this removes crossings: if the route doubles back on itself,
    flipping the segment between the two crossing edges untangles it. With
    access windows a reversal often breaks feasibility, so every candidate is
    re-checked rather than assumed valid.
    """
    best = route_cost(route, walk, day, alpha)
    if best is None:
        return route, best
    improved = True
    while improved:
        improved = False
        for i in range(len(route) - 1):
            for j in range(i + 2, len(route) + 1):
                cand = route[:i] + route[i:j][::-1] + route[j:]
                c = route_cost(cand, walk, day, alpha)
                if c is not None and c < best - 1e-9:
                    route, best, improved = cand, c, True
    return route, best


def or_opt_within(route, walk, day, alpha=ALPHA, max_chain=3):
    """
    Lift out a run of one to three consecutive jobs and reinsert it elsewhere
    in the same route. Cheaper than 2-opt and it does not disturb the order
    of everything else, which matters when access windows are tight.
    """
    best = route_cost(route, walk, day, alpha)
    if best is None:
        return route, best
    improved = True
    while improved:
        improved = False
        for size in range(1, max_chain + 1):
            for i in range(len(route) - size + 1):
                chunk = route[i:i + size]
                rest = route[:i] + route[i + size:]
                for pos in range(len(rest) + 1):
                    if pos == i:
                        continue
                    cand = rest[:pos] + chunk + rest[pos:]
                    c = route_cost(cand, walk, day, alpha)
                    if c is not None and c < best - 1e-9:
                        route, best, improved = cand, c, True
                        break
                if improved:
                    break
            if improved:
                break
    return route, best


def or_opt_across(plan, team, walk, day, alpha=ALPHA, max_chain=2):
    """
    Move a short run of jobs from one technician to another of the same trade.

    This is the move that matters most in practice. Savings merging balances
    routes by geography but not by workload, so one technician can end up
    with a packed day while a colleague has an empty afternoon. Shifting a
    couple of jobs across fixes that.
    """
    trade_of = {m["name"]: m["trade"] for m in team}
    improved = True
    while improved:
        improved = False
        for src in plan:
            for dst in plan:
                if src == dst or trade_of[src] != trade_of[dst]:
                    continue
                for size in range(1, max_chain + 1):
                    for i in range(len(plan[src]) - size + 1):
                        chunk = plan[src][i:i + size]
                        new_src = plan[src][:i] + plan[src][i + size:]
                        c_src_old = route_cost(plan[src], walk, day, alpha)
                        c_dst_old = route_cost(plan[dst], walk, day, alpha)
                        c_src_new = route_cost(new_src, walk, day, alpha)
                        if c_src_new is None:
                            continue
                        best_dst = None
                        for pos in range(len(plan[dst]) + 1):
                            cand = plan[dst][:pos] + chunk + plan[dst][pos:]
                            c = route_cost(cand, walk, day, alpha)
                            if c is not None and (best_dst is None or c < best_dst[0]):
                                best_dst = (c, cand)
                        if best_dst is None:
                            continue
                        before = c_src_old + c_dst_old
                        after = c_src_new + best_dst[0]
                        if after < before - 1e-9:
                            plan[src] = new_src
                            plan[dst] = best_dst[1]
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return plan


def improve(plan, deferred, team, walk, day, alpha=ALPHA):
    """
    Polish a plan: first shuffle work between technicians, then tidy each
    individual route with 2-opt and Or-opt. Repeat until nothing improves.
    We also try to rescue deferred tickets, since a tidier route may have
    opened up room for one.
    """
    for _ in range(3):
        before = plan_cost(plan, deferred, walk, day, alpha)
        plan = or_opt_across(plan, team, walk, day, alpha)
        for name in plan:
            plan[name], _ = two_opt(plan[name], walk, day, alpha)
            plan[name], _ = or_opt_within(plan[name], walk, day, alpha)
        plan, deferred = rescue_deferred(plan, deferred, team, walk, day, alpha)
        after = plan_cost(plan, deferred, walk, day, alpha)
        if after is None or before is None or after > before - 1e-6:
            break
    return plan, deferred


def rescue_deferred(plan, deferred, team, walk, day, alpha=ALPHA):
    """Try to squeeze leftover tickets in, most urgent first."""
    still = []
    for tk in sorted(deferred, key=lambda t: -deferral_cost(t, day)):
        best = None
        for m in team:
            if m["trade"] != tk.trade:
                continue
            got = cheapest_insertion(plan[m["name"]], tk, walk, day, alpha)
            if got is None:
                continue
            delta, cand = got
            if delta < deferral_cost(tk, day) and (best is None or delta < best[0]):
                best = (delta, m["name"], cand)
        if best is None:
            still.append(tk)
        else:
            plan[best[1]] = best[2]
    return plan, still


def solve_savings_improved(tickets, team, walk, day, alpha=ALPHA):
    plan, deferred = solve_savings(tickets, team, walk, day, alpha)
    return improve(plan, deferred, team, walk, day, alpha)


METHODS = {
    "fifo": solve_fifo,
    "savings": solve_savings,
    "priority": solve_priority,
    "savings+improve": solve_savings_improved,
}
