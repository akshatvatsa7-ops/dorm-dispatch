"""
Generates the maintenance complaints the dispatcher has to deal with.

Nobody is going to hand us the Estate Office's real ticket log, so we generate
tickets ourselves. The point is not to guess the true numbers but to build a
generator whose assumptions are all written down and all easy to change, so
that anyone can rerun the study with their own figures. Every number below is
stated as an assumption in the report.

A ticket is one complaint. It carries:

    where       which building it is in
    trade       electrical, plumbing or carpentry - only a technician of that
                trade can do the job
    priority    1 urgent, 2 normal, 3 minor, which sets both how heavily
                lateness is punished and how soon the job is due
    service     how long the repair itself takes, in minutes
    window      the stretch of the day during which somebody is there to open
                the door
    due         the deadline, in minutes of working time from when the
                complaint was raised

The working day
---------------
The crew works 09:00 to 17:30 with an hour for lunch, so 450 working minutes.
We measure time in working minutes from the start of the day, so t = 0 is
09:00 and t = 450 is 17:30, with lunch simply left out of the clock. Day d of
the simulation starts at absolute time d * 450, which is what lets a ticket
left undone on Monday keep accumulating lateness on Tuesday.
"""

import random
from dataclasses import dataclass, field

WORKING_MINUTES_PER_DAY = 450          # 09:00-17:30 less an hour for lunch

TRADES = ("electrical", "plumbing", "carpentry")

# What share of complaints fall to each trade. Electrical dominates: lights,
# fans, sockets and switches are the bulk of what a dorm reports.
TRADE_MIX = {"electrical": 0.45, "plumbing": 0.35, "carpentry": 0.20}

# Typical repair time per trade, in minutes: (median, spread).
# Plumbing takes longest because it usually means shifting a fitting.
SERVICE_TIME = {
    "electrical": (22, 0.45),
    "plumbing":   (38, 0.50),
    "carpentry":  (30, 0.45),
}
SERVICE_MIN, SERVICE_MAX = 10, 110

# Priority classes.
#   share   how often this priority comes up
#   weight  how heavily a minute of lateness counts in the objective
#   sla     how many working minutes we promised the complainant
PRIORITY = {
    1: {"share": 0.15, "weight": 10, "sla": 240,  "label": "urgent"},
    2: {"share": 0.55, "weight": 4,  "sla": 450,  "label": "normal"},
    3: {"share": 0.30, "weight": 1,  "sla": 1350, "label": "minor"},
}

# Expected number of new complaints raised per day across the whole campus.
TICKETS_PER_DAY = 58

# Of those, this share come from the dorms rather than offices and facilities.
DORM_SHARE = 0.85

# Access windows. A dorm room needs its occupant there to open the door, and
# students are in class for much of the day; offices and public areas can be
# worked on any time the crew is on shift.
WINDOW_PATTERNS = {
    "anytime":   (0, WORKING_MINUTES_PER_DAY),
    "morning":   (0, 180),                        # 09:00-12:00
    "afternoon": (210, WORKING_MINUTES_PER_DAY),  # 13:30-17:30
}
DORM_WINDOW_MIX = {"anytime": 0.40, "morning": 0.30, "afternoon": 0.30}


@dataclass
class Ticket:
    tid: int
    site: int                 # index into the campus location list
    trade: str
    priority: int
    service: float            # minutes of actual repair work
    win_start: float          # earliest the technician can start, within a day
    win_end: float            # latest the repair can still be started
    raised_day: int
    due_abs: float            # absolute deadline in working minutes
    # filled in once the ticket is scheduled
    done_abs: float = field(default=None)
    done_by: str = field(default=None)

    @property
    def weight(self):
        return PRIORITY[self.priority]["weight"]

    def tardiness_hours(self, completion_abs):
        """How many working hours late this ticket was, never negative."""
        return max(0.0, completion_abs - self.due_abs) / 60.0


def _pick(rng, shares):
    """Draw a key from {key: probability}."""
    r = rng.random()
    acc = 0.0
    for k, p in shares.items():
        acc += p
        if r <= acc:
            return k
    return k


def _service_time(rng, trade):
    median, spread = SERVICE_TIME[trade]
    t = rng.lognormvariate(0, spread) * median
    return round(min(SERVICE_MAX, max(SERVICE_MIN, t)))


def generate_day(day, rng, campus, tickets_per_day=TICKETS_PER_DAY,
                 next_id=0):
    """
    Draw one day's new complaints.

    Complaints are spread over the campus in proportion to how many people
    use each building, which is why dorms generate most of them. Within a
    building the number raised on any given day is Poisson, which is the
    standard way to model independent events arriving at a steady average
    rate.
    """
    cats = campus["category"]
    dorms = [i for i, c in enumerate(cats) if c == "dorm"]
    others = [i for i, c in enumerate(cats) if c in ("office", "facility")]

    lam_dorm = tickets_per_day * DORM_SHARE / len(dorms)
    lam_other = tickets_per_day * (1 - DORM_SHARE) / len(others)

    tickets = []
    tid = next_id
    for group, lam in ((dorms, lam_dorm), (others, lam_other)):
        for site in group:
            for _ in range(_poisson(rng, lam)):
                trade = _pick(rng, TRADE_MIX)
                prio = _pick(rng, {k: v["share"] for k, v in PRIORITY.items()})
                if cats[site] == "dorm":
                    pattern = _pick(rng, DORM_WINDOW_MIX)
                else:
                    pattern = "anytime"
                ws, we = WINDOW_PATTERNS[pattern]
                tickets.append(Ticket(
                    tid=tid,
                    site=site,
                    trade=trade,
                    priority=prio,
                    service=_service_time(rng, trade),
                    win_start=ws,
                    win_end=we,
                    raised_day=day,
                    due_abs=day * WORKING_MINUTES_PER_DAY + PRIORITY[prio]["sla"],
                ))
                tid += 1
    rng.shuffle(tickets)
    return tickets, tid


def _poisson(rng, lam):
    """Number of events in one period, by Knuth's method."""
    import math
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def crew(per_trade=3):
    """
    The technicians available. Each one can only do jobs in their own trade,
    which is what makes the assignment part of the problem bite.
    """
    out = []
    for trade in TRADES:
        for k in range(per_trade):
            out.append({"name": f"{trade[:4]}-{k+1}", "trade": trade})
    return out


def summarise(tickets):
    """A few counts, for printing and for the report tables."""
    by_trade = {t: 0 for t in TRADES}
    by_prio = {p: 0 for p in PRIORITY}
    work = {t: 0.0 for t in TRADES}
    for t in tickets:
        by_trade[t.trade] += 1
        by_prio[t.priority] += 1
        work[t.trade] += t.service
    return {"n": len(tickets), "by_trade": by_trade, "by_priority": by_prio,
            "repair_minutes_by_trade": {k: round(v) for k, v in work.items()}}


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import campus as campus_mod

    c = campus_mod.build()
    rng = random.Random(7)
    tickets, _ = generate_day(0, rng, c)
    s = summarise(tickets)
    print(f"tickets raised on day 0: {s['n']}")
    print(f"  by trade:    {s['by_trade']}")
    print(f"  by priority: {s['by_priority']}")
    print(f"  repair work: {s['repair_minutes_by_trade']} minutes")

    team = crew(3)
    print(f"\ncrew of {len(team)}: {[t['name'] for t in team]}")
    for trade in TRADES:
        n = sum(1 for t in team if t["trade"] == trade)
        capacity = n * WORKING_MINUTES_PER_DAY
        demand = s["repair_minutes_by_trade"][trade]
        print(f"  {trade:11s} {n} technicians, {capacity} min available, "
              f"{demand} min of repair work "
              f"({100*demand/capacity:.0f}% before any walking)")
