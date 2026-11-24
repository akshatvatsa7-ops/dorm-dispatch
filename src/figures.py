"""
Draws the figures: the campus map, the route maps, and the result charts.

Each figure is written twice, once as .svg for the web page and once as
.tikz for the report, from a single description. See draw.py.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import campus as campus_mod
from draw import Canvas, ROUTE_COLOURS, tikz_colour_preamble

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out", "figures")

MAP_W, MAP_H = 168.0, 86.0
CHART_W, CHART_H = 150.0, 70.0


def projector(coords, extra=(), width=MAP_W, height=MAP_H, pad=7.0):
    """
    Build a function turning (lat, lon) into millimetres on the canvas.

    Longitude is squeezed by cos(latitude) so the map keeps its true shape,
    and the whole thing is scaled to fit the canvas with a margin.
    """
    pts = list(coords) + list(extra)
    lat0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))

    xs = [p[1] * k for p in pts]
    ys = [p[0] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)

    sx = (width - 2 * pad) / (x1 - x0)
    sy = (height - 2 * pad) / (y1 - y0)
    s = min(sx, sy)
    ox = (width - (x1 - x0) * s) / 2
    oy = (height - (y1 - y0) * s) / 2

    def project(lat, lon):
        return (ox + (lon * k - x0) * s, oy + (lat - y0) * s)

    return project


def base_map(c, label_all=True):
    """The campus itself: road, tunnel, and every location."""
    cv = Canvas(MAP_W, MAP_H)
    mouths = [c["tunnel"]["new"], c["tunnel"]["old"]]
    P = projector(c["coords"], mouths)

    # the main road, drawn as a band down the middle of the campus
    rx, _ = P(c["coords"][0][0], campus_mod.ROAD_LON)
    cv.line(rx, 4, rx, MAP_H - 4, colour="road", width=2.4, opacity=0.5)
    cv.text(rx, MAP_H - 2.0, "main road", colour="muted", size=2.0)

    # the tunnel: the only way across
    a, b = P(*mouths[0]), P(*mouths[1])
    cv.line(*a, *b, colour="tunnel", width=0.8)
    cv.circle(*a, 0.7, fill="tunnel")
    cv.circle(*b, 0.7, fill="tunnel")
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    cv.text(mid[0] + 6, mid[1] - 4.0, "walkway tunnel", colour="tunnel", size=2.1,
            bold=True)

    cv.text(8, MAP_H - 6, "NEW CAMPUS", colour="muted", size=2.6,
            anchor="left", bold=True)
    cv.text(MAP_W - 8, MAP_H - 6, "OLD CAMPUS", colour="muted", size=2.6,
            anchor="right", bold=True)

    for i, (lat, lon) in enumerate(c["coords"]):
        x, y = P(lat, lon)
        cat = c["category"][i]
        if cat == "depot":
            cv.circle(x, y, 1.5, fill="depot")
            cv.text(x, y - 3.4, "ESTATE OFFICE", colour="depot", size=2.1,
                    bold=True)
        else:
            cv.circle(x, y, 0.95, fill=cat, edge="paper", width=0.15)
            # The 19 dorms sit in one tight cluster, so labelling each of
            # them turns the map into a smudge. They are annotated as a
            # group instead; the route figures number the stops in visiting
            # order, which is what actually matters there.
            if label_all and cat != "dorm":
                cv.text(x + 1.6, y, c["short"][i], colour="muted", size=1.9,
                        anchor="left")

    if label_all:
        dorm_pts = [P(*c["coords"][i]) for i, cat in enumerate(c["category"])
                    if cat == "dorm"]
        cx = sum(p[0] for p in dorm_pts) / len(dorm_pts)
        ylo = min(p[1] for p in dorm_pts)
        cv.text(cx, ylo - 4.0, f"{len(dorm_pts)} dormitories", colour="dorm",
                size=2.2, bold=True)
    return cv, P


def fig_campus(c):
    cv, _ = base_map(c)
    # legend
    x, y = 6, 8
    for cat, label in (("dorm", "dormitory"), ("office", "academic / office"),
                       ("facility", "facility"), ("depot", "depot")):
        cv.circle(x, y, 1.0, fill=cat)
        cv.text(x + 2.0, y, label, colour="muted", size=2.0, anchor="left")
        x += 26
    return cv


def fig_routes(c, plan, team, trade, title):
    """Draw the routes of all technicians of one trade for a single day."""
    cv, P = base_map(c, label_all=False)
    depot = P(*c["coords"][0])
    names = [m["name"] for m in team if m["trade"] == trade]
    mouth = {"new": P(*c["tunnel"]["new"]), "old": P(*c["tunnel"]["old"])}

    def leg(i, j):
        """
        The drawn path from location i to location j. If the two are on
        opposite sides of the road the walk has to go through the tunnel,
        so the line is drawn that way rather than straight across, which
        would suggest a crossing that does not exist.
        """
        zi, zj = c["zone"][i], c["zone"][j]
        a, b = P(*c["coords"][i]), P(*c["coords"][j])
        if zi == zj:
            return [a, b]
        return [a, mouth[zi], mouth[zj], b]

    for k, name in enumerate(names):
        route = plan[name]
        if not route:
            continue
        colour = ROUTE_COLOURS[k % len(ROUTE_COLOURS)]
        stops = [0] + [t.site for t in route] + [0]
        pts = [P(*c["coords"][0])]
        for a, b in zip(stops, stops[1:]):
            pts.extend(leg(a, b)[1:])
        cv.polyline(pts, colour=colour, width=0.45, opacity=0.9)
        for step, t in enumerate(route, start=1):
            x, y = P(*c["coords"][t.site])
            cv.circle(x, y, 1.35, fill=colour, edge="paper", width=0.25)
            cv.text(x, y, str(step), colour="paper", size=1.6, bold=True)

    cv.text(MAP_W / 2, 3.0, title, colour="ink", size=2.6, bold=True)
    x, y = 6, MAP_H - 11
    for k, name in enumerate(names):
        cv.line(x, y, x + 4, y, colour=ROUTE_COLOURS[k % len(ROUTE_COLOURS)],
                width=0.5)
        cv.text(x + 5, y, name, colour="muted", size=2.0, anchor="left")
        y -= 3.4
    return cv


def _axes(cv, x0, y0, w, h, ymax, ylabel, xlabel, yticks=5):
    cv.line(x0, y0, x0, y0 + h, colour="faint", width=0.25)
    cv.line(x0, y0, x0 + w, y0, colour="faint", width=0.25)
    for i in range(yticks + 1):
        v = ymax * i / yticks
        y = y0 + h * i / yticks
        cv.line(x0 - 1, y, x0, y, colour="faint", width=0.2)
        if i:
            cv.line(x0, y, x0 + w, y, colour="faint", width=0.12, opacity=0.7)
        cv.text(x0 - 2, y, f"{v:g}", colour="muted", size=2.0, anchor="right")
    cv.text(x0 - 1, y0 + h + 4.5, ylabel, colour="muted", size=2.1,
            anchor="left")
    cv.text(x0 + w / 2, y0 - 7, xlabel, colour="muted", size=2.1)


def fig_backlog(results):
    """Tickets still waiting at the end of each day, for each method."""
    cv = Canvas(CHART_W, CHART_H)
    x0, y0 = 16, 12
    w, h = CHART_W - 34, CHART_H - 26
    days = len(next(iter(results.values()))["per_day"])
    ymax = max(d["backlog"] for r in results.values() for d in r["per_day"])
    ymax = max(5, math.ceil(ymax / 5) * 5)
    _axes(cv, x0, y0, w, h, ymax, "tickets waiting", "day")

    ends = []
    for k, (name, r) in enumerate(results.items()):
        pts = []
        for d in r["per_day"]:
            x = x0 + w * d["day"] / max(1, days - 1)
            y = y0 + h * d["backlog"] / ymax
            pts.append((x, y))
        cv.polyline(pts, colour=ROUTE_COLOURS[k], width=0.4)
        ends.append([pts[-1][1], name, ROUTE_COLOURS[k]])

    # push the labels apart vertically so they stay readable when two
    # methods finish at a similar backlog
    ends.sort()
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < 3.2:
            ends[i][0] = ends[i - 1][0] + 3.2
    for y, name, col in ends:
        cv.text(x0 + w + 1.5, y, name, colour=col, size=1.9, anchor="left")
    for i in (0, days // 2, days - 1):
        cv.text(x0 + w * i / max(1, days - 1), y0 - 3, str(i + 1),
                colour="muted", size=2.0)
    return cv


def fig_sla(results):
    """Share of tickets closed inside the promised time, by priority."""
    cv = Canvas(CHART_W, CHART_H)
    x0, y0 = 16, 12
    w, h = CHART_W - 30, CHART_H - 30
    _axes(cv, x0, y0, w, h, 100, "closed on time (%)", "priority", yticks=4)

    methods = list(results)
    group_w = w / 3
    bar_w = group_w / (len(methods) + 1.6)
    labels = {1: "urgent", 2: "normal", 3: "minor"}
    for gi, prio in enumerate((1, 2, 3)):
        gx = x0 + gi * group_w
        for mi, m in enumerate(methods):
            v = results[m]["by_priority"][prio]["sla_met_pct"] or 0
            bx = gx + bar_w * (mi + 0.8)
            cv.rect(bx, y0, bar_w * 0.85, h * v / 100,
                    fill=ROUTE_COLOURS[mi], edge=None)
            cv.text(bx + bar_w * 0.42, y0 + h * v / 100 + 1.6, f"{v:.0f}",
                    colour="muted", size=1.7)
        cv.text(gx + group_w / 2, y0 - 3, labels[prio], colour="muted", size=2.1)

    lx = x0
    for mi, m in enumerate(methods):
        cv.rect(lx, CHART_H - 5.5, 2.4, 2.4, fill=ROUTE_COLOURS[mi], edge=None)
        cv.text(lx + 3.2, CHART_H - 4.3, m, colour="muted", size=1.9,
                anchor="left")
        lx += 7 + 1.5 * len(m)
    return cv


def save(cv, name):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(cv.to_svg())
    with open(os.path.join(OUT, name + ".tikz"), "w") as f:
        f.write(cv.to_tikz())
    return name


def build_all(c, results, day_plans, team):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "colours.tex"), "w") as f:
        f.write(tikz_colour_preamble())

    made = [save(fig_campus(c), "campus")]
    made.append(save(fig_routes(c, day_plans["fifo"]["plan"], team,
                                "electrical",
                                "First come, first served: the three electricians"),
                     "routes_fifo"))
    made.append(save(fig_routes(c, day_plans["savings+improve"]["plan"], team,
                                "electrical",
                                "After savings and improvement: the same three electricians"),
                     "routes_improved"))
    made.append(save(fig_backlog(results), "backlog"))
    made.append(save(fig_sla(results), "sla"))
    return made


if __name__ == "__main__":
    import experiment

    c = campus_mod.build()
    print("simulating ...")
    results = experiment.compare_methods(c, days=30)
    tickets, team, plans = experiment.one_day_plans(c)
    made = build_all(c, results, plans, team)
    print("wrote:", ", ".join(made))
