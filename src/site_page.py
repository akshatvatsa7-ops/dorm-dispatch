"""
Builds the project web page in docs/, ready for GitHub Pages.

The page is generated from the same results file that the report quotes, so
the two cannot disagree. The figures are inlined as SVG, which keeps the
whole thing to a single file with no assets to go missing.
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
FIGS = os.path.join(ROOT, "out", "figures")
DOCS = os.path.join(ROOT, "docs")

METHOD_LABEL = {
    "fifo": "First come, first served",
    "savings": "Clarke–Wright savings",
    "priority": "Priority insertion",
    "savings+improve": "Savings + 2-opt/Or-opt",
}


def svg(name):
    with open(os.path.join(FIGS, name + ".svg")) as f:
        return f.read()


def table(header, rows, highlight_last=True):
    out = ["<table><thead><tr>"]
    out += [f"<th>{h}</th>" for h in header]
    out.append("</tr></thead><tbody>")
    for i, r in enumerate(rows):
        cls = ' class="best"' if (highlight_last and i == len(rows) - 1) else ""
        out.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


CSS = """
:root{
  --bg:#FFFFFF; --panel:#F7F8FA; --ink:#15181C; --muted:#5C6672;
  --line:#E2E6EB; --accent:#1F4E79; --good:#2E7D32; --warn:#C62828;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#13161A; --panel:#1B1F25; --ink:#ECEFF3; --muted:#9AA5B1;
    --line:#2A2F37; --accent:#7FB2E5; --good:#7BC47F; --warn:#F08A8A;
  }
}
:root[data-theme="dark"]{
  --bg:#13161A; --panel:#1B1F25; --ink:#ECEFF3; --muted:#9AA5B1;
  --line:#2A2F37; --accent:#7FB2E5; --good:#7BC47F; --warn:#F08A8A;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif;}
.wrap{max-width:880px;margin:0 auto;padding:0 16px 80px}
header{padding:56px 0 28px;border-bottom:1px solid var(--line);margin-bottom:28px}
h1{font-size:2.1rem;line-height:1.15;margin:0 0 10px;letter-spacing:-0.02em}
.sub{color:var(--muted);font-size:1.05rem;margin:0}
.downloads{margin:18px 0 0;display:flex;flex-wrap:wrap;gap:10px}
.downloads a{display:inline-block;padding:7px 14px;border:1px solid var(--line);border-radius:999px;font-size:.92rem;text-decoration:none;color:var(--ink);background:var(--panel)}
.downloads a:hover{border-color:var(--accent);color:var(--accent)}
h2{font-size:1.3rem;margin:44px 0 10px;letter-spacing:-0.01em}
h3{font-size:1.02rem;margin:26px 0 6px}
p{margin:0 0 14px}
a{color:var(--accent)}
.lede{font-size:1.1rem;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px;margin:26px 0 8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px}
.stat .n{font-size:1.65rem;font-weight:650;letter-spacing:-0.02em;
  display:block;line-height:1.1}
.stat .l{color:var(--muted);font-size:0.83rem;display:block;margin-top:4px}
.good{color:var(--good)} .warn{color:var(--warn)}
/* Figures keep a light backing in both themes: the SVGs are drawn with
   dark ink and would disappear on a dark panel. */
figure{margin:22px 0;background:#FFFFFF;border:1px solid var(--line);
  border-radius:12px;padding:14px}
figure svg{display:block;width:100%;height:auto}
figcaption{color:#5C6672;font-size:0.87rem;margin-top:10px}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:0.9rem}
th,td{text-align:right;padding:8px 10px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600;font-size:0.8rem;text-transform:uppercase;
  letter-spacing:0.04em}
tr.best td{font-weight:650}
code{background:var(--panel);border:1px solid var(--line);border-radius:5px;
  padding:1px 5px;font-size:0.88em}
pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:14px;overflow-x:auto;font-size:0.85rem}
ul{padding-left:20px} li{margin:6px 0}
.note{border-left:3px solid var(--accent);background:var(--panel);
  padding:12px 16px;border-radius:0 8px 8px 0;margin:18px 0}
footer{margin-top:50px;padding-top:20px;border-top:1px solid var(--line);
  color:var(--muted);font-size:0.86rem}
@media(max-width:600px){h1{font-size:1.65rem}body{font-size:15px}}
"""


def build():
    with open(os.path.join(ROOT, "out", "results", "summary.json")) as f:
        d = json.load(f)

    m = d["methods"]
    fifo, imp = m["fifo"], m["savings+improve"]
    c = d["campus"]

    method_rows = [
        [METHOD_LABEL[k],
         f"{float(m[k]['objective']):,.0f}",
         f"{float(m[k]['travel_per_tech_day']):.1f} min",
         f"{float(m[k]['sla_met_pct']):.1f}%",
         f"{float(m[k]['by_priority']['1']['sla_met_pct']):.1f}%",
         f"{float(m[k]['mean_backlog']):.1f}"]
        for k in ("fifo", "savings", "priority", "savings+improve")]

    crew_rows = [[label,
                  r["crew"],
                  f"{float(r['objective']):,.0f}",
                  f"{float(r['sla_met_pct']):.1f}%",
                  f"{float(r['by_priority']['1']['sla_met_pct']):.1f}%"]
                 for label, r in d["crew"].items()]

    bb_rows = [[e["n"], f"{float(e['optimum']):.3f}",
                f"{float(e['heuristic']):.3f}", f"{float(e['gap']):.1f}%",
                f"{int(e['nodes_warm']):,}", f"{int(e['nodes_cold']):,}"]
               for e in d["exact"]]

    travel_cut = 100 * (float(fifo["travel_per_tech_day"])
                        - float(imp["travel_per_tech_day"])) \
        / float(fifo["travel_per_tech_day"])

    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dorm Maintenance Dispatch</title>
<meta name="description" content="An optimisation model for dispatching the
IIMA Estate Office maintenance crew, built on the real campus map.">
<style>{CSS}</style>
</head><body><div class="wrap">

<header>
<h1>Dispatching the dorm maintenance crew</h1>
<p class="sub">An optimisation model for the IIMA Estate Office, built on the
real campus map and run on synthetic complaint data.</p>
<p class="downloads"><a href="report.pdf">Full report (PDF)</a>
<a href="explainer.pdf">How it works, in 4 pages</a>
<a href="dorm-dispatch.pptx">Slides</a>
<a href="dispatch-model.xlsx">Results workbook</a>
<a href="https://github.com/akshatvatsa7-ops/dorm-dispatch">Code on GitHub</a></p>
</header>

<p class="lede">The Estate Office gets maintenance complaints all day and works
them roughly in the order they arrive. That wastes a lot of walking, and it
means an urgent complaint can sit behind twenty trivial ones. This project
plans the day instead.</p>

<div class="stats">
  <div class="stat"><span class="n good">{travel_cut:.0f}%</span>
    <span class="l">less walking</span></div>
  <div class="stat"><span class="n good">{float(fifo['by_priority']['1']['sla_met_pct']):.0f}%
    &rarr; {float(imp['by_priority']['1']['sla_met_pct']):.0f}%</span>
    <span class="l">urgent complaints closed on time</span></div>
  <div class="stat"><span class="n">{float(imp['by_priority']['1']['mean_wait_h']):.1f} h</span>
    <span class="l">average wait for an urgent job, down from
    {float(fifo['by_priority']['1']['mean_wait_h']):.1f} h</span></div>
  <div class="stat"><span class="n">0</span>
    <span class="l">extra technicians needed</span></div>
</div>

<h2>Why the campus makes this hard</h2>
<p>A main road cuts the campus in two and there is no crossing at road level,
so every trip between the two halves goes through the walkway tunnel and takes
about {c['mean_cross_campus']} minutes, against {c['mean_same_campus']} minutes
for a trip that stays on one side.</p>
<p>The crews make that worse without meaning to, because they are not in one
place. The electricians work out of a store room in Dorm 7 on the main campus;
the plumbers and carpenters share one in Dorm 24 on the new campus. So the two
groups start each morning on opposite sides of the road, and for each of them
about half the campus is on the far side of the tunnel. The same job is cheap
for one trade and expensive for another, which means a sensible bundle of work
for the electricians is not a sensible bundle for the plumbers.</p>

<figure>{svg("campus")}
<figcaption>The campus as the model sees it. Coordinates come from
OpenStreetMap. Nothing crosses the road except the tunnel, so walking times
are worked out with Dijkstra's algorithm over a network that reflects
that.</figcaption></figure>

<h2>What the model decides</h2>
<p>Given the complaints waiting at the start of a day, it decides which
technician takes which jobs and in what order. A technician can only be given
work in their own trade, every job has a window during which somebody is there
to open the door, and everyone has to be back at their own trade's store room
by the end of the shift. What it minimises is weighted lateness, with a small charge for walking
so that walking breaks ties rather than driving the answer:</p>
<pre>minimise   sum of (weight x hours late)  +  0.05 x walking minutes</pre>
<p>Urgent complaints carry a weight of 10, normal ones 4, minor ones 1.
Anything not done today stays in the queue and shows up tomorrow, so falling
behind compounds.</p>

<h2>Four ways to plan the day</h2>
<p>Each method was built to show up what the previous one was missing.
<strong>First come, first served</strong> is the baseline. <strong>Clarke and
Wright's savings heuristic</strong> starts with one trip per job and merges the
pairs that save the most walking, which on this campus naturally bundles
new-campus work into a single trip through the tunnel. <strong>Priority
insertion</strong> adds jobs one at a time, picking whichever gives the most
urgency per extra minute of walking. The last method takes the savings plan and
improves it with <strong>2-opt</strong>, which untangles crossings, and
<strong>Or-opt</strong>, which moves short runs of jobs around and, crucially,
between technicians.</p>

<figure>{svg("routes_fifo")}
<figcaption>First come, first served: three electricians, one ordinary day.
The routes criss-cross and cross the tunnel repeatedly.</figcaption></figure>

<figure>{svg("routes_improved")}
<figcaption>The same three electricians and the same complaints after savings
merging and improvement. Each crosses once, works a cluster, comes
back.</figcaption></figure>

<h2>Results over {d['methods']['fifo']['days']} days</h2>
<p>Every method sees exactly the same complaints, so the differences come from
the dispatching and nothing else.</p>
{table(["Method", "Objective", "Walk/tech/day", "On time", "Urgent on time",
        "Avg waiting"], method_rows)}

<figure>{svg("sla")}
<figcaption>Share of complaints closed within the promised time. The
difference is almost entirely about urgent work.</figcaption></figure>

<figure>{svg("backlog")}
<figcaption>Complaints still unfinished at the end of each day. The baseline
never clears its queue.</figcaption></figure>

<h2>Is it actually any good?</h2>
<p>For a single technician with up to {max(e['n'] for e in d['exact'])} jobs we
can find the true optimum by branch and bound and check. Savings plus
improvement matched the optimum on every instance. Starting the search from
the heuristic's answer also cut the number of nodes explored by more than
half, which is the practical reason heuristics matter inside exact
methods.</p>
{table(["Jobs", "Optimum", "Savings + improve", "Gap", "Nodes, warm",
        "Nodes, cold"], bb_rows, highlight_last=False)}

<h2>How many technicians?</h2>
{table(["Crew", "People", "Objective", "On time", "Urgent on time"],
       crew_rows, highlight_last=False)}
<p>Six is not enough and the backlog runs away. Nine is enough. Twelve buys
almost nothing. The last row was a surprise we kept in: carpentry looks like
the idle trade, so we tried moving a carpenter's post to the busier trades at
the same headcount, and it was far worse. With one carpenter that trade
becomes a bottleneck and never recovers. The idle time was the buffer.</p>

<div class="note">
<h3 style="margin-top:0">The most useful finding</h3>
<p style="margin-bottom:0">Of the {d['methods']['savings+improve']['urgent_total']}
urgent complaints raised over the month,
{d['methods']['savings+improve']['urgent_impossible']} could never have met the
four-hour promise, no matter who was sent: the room can only be accessed in the
afternoon and the repair runs past the deadline. The optimised plan closed
{d['methods']['savings+improve']['urgent_late']} urgent complaints late, and
all {d['methods']['savings+improve']['urgent_late_but_impossible']} of them
were of exactly that kind. The two numbers are the same number: every urgent
complaint that could have been closed on time was closed on time, and there is
nothing left for a better algorithm to find. What remains is a problem with
the promise rather than with the plan.</p></div>

<h2>What we would tell the Estate Office</h2>
<ul>
<li>Plan the day in the morning instead of working the queue as it arrives.
  Worth {round(100 * (d['methods']['fifo']['travel_per_tech_day'] - d['methods']['savings+improve']['travel_per_tech_day']) / d['methods']['fifo']['travel_per_tech_day'], 1)}% of the crew's walking and more than double the
  share of urgent complaints closed on time, with no extra staff.</li>
<li>Bundle by campus, and remember each trade has its own far side. The
  electricians should be batching new-campus work and the plumbers and
  carpenters main-campus work, crossing in opposite directions.</li>
<li>Do not hire. Nine technicians is enough for this load.</li>
<li>Do not rebalance the trades to match average workload. The quiet trade is
  quiet on average, not on a bad day.</li>
<li>Change the promise or change the access for complaints that can only be
  reached in the afternoon. No amount of scheduling fixes those.</li>
</ul>

<h2>Running it yourself</h2>
<p>Plain Python, no libraries to install. The whole study takes under a
minute.</p>
<pre>git clone &lt;this repository&gt;
cd dorm-dispatch
python3 run.py</pre>
<p>That rebuilds the walking network from the cached map data, runs every
experiment, redraws the figures, writes the Excel workbook and regenerates
every number quoted in the report. All the assumptions live in one file,
<code>src/instance.py</code>, so anyone with the Estate Office's real figures
can put them in and rerun.</p>

<footer>
Built for the Operations Management &amp; Logistics group project.
Campus geometry from OpenStreetMap, &copy; OpenStreetMap contributors, ODbL.
Complaint data is synthetic. Study runtime {d['runtime_seconds']} s.
</footer>

</div></body></html>"""

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w") as f:
        f.write(html)

    # copy the downloadable artefacts next to the page
    for src, dst in ((os.path.join(ROOT, "report", "report.pdf"), "report.pdf"),
                     (os.path.join(ROOT, "report", "explainer.pdf"),
                      "explainer.pdf"),
                     (os.path.join(ROOT, "slides", "dorm-dispatch.pptx"),
                      "dorm-dispatch.pptx"),
                     (os.path.join(ROOT, "out", "dispatch-model.xlsx"),
                      "dispatch-model.xlsx")):
        if os.path.exists(src):
            shutil.copy(src, os.path.join(DOCS, dst))
    return os.path.join(DOCS, "index.html")


if __name__ == "__main__":
    print("wrote", build())
