# Dispatching the dorm maintenance crew

An optimisation model for the IIMA Estate Office: given the maintenance
complaints waiting at the start of a day, decide which technician takes which
jobs and in what order.

Built for the Operations Management & Logistics group project. The campus
geometry is real, taken from OpenStreetMap. The complaints are synthetic, and
every assumption behind them sits in one file so anybody with the Estate
Office's real figures can swap them in and rerun the study.

**[Read the report](report/report.pdf)** · **[Project page](docs/index.html)**

## The result in one paragraph

The Estate Office currently works its queue roughly in the order complaints
arrive. Over 30 simulated days that wastes about a third of the crew's
walking and closes only 41% of urgent complaints within the promised four
hours. Planning the day properly — Clarke and Wright's savings heuristic to
build the routes, then 2-opt and Or-opt to improve them — cuts walking from
28.4 to 19.4 minutes per technician per day and raises urgent compliance to
86%, with no extra staff. Of the urgent complaints still closed late, all but
one were impossible for anyone to close on time: the room can only be opened
in the afternoon and the repair runs past the deadline. That remaining failure
is a problem with the promise, not with the plan.

## Running it

```
python3 run.py
```

Nothing to install. Plain Python 3, standard library only, about a minute to
run. It rebuilds the walking network, runs every experiment, redraws the
figures, writes the Excel workbook, compiles the report (if you have
`pdflatex`) and regenerates the web page.

You can also run the pieces on their own, each of which prints something
useful:

```
python3 src/campus.py      # the walking network and some sanity checks
python3 src/instance.py    # one day of generated complaints
python3 src/experiment.py  # the four methods over 30 days
python3 src/exact.py       # branch and bound against the heuristics
```

## What's here

```
run.py                  rebuild everything
src/campus.py           walking network from the map data, Dijkstra
src/instance.py         complaint generator and every assumption
src/dispatch.py         the four planning methods
src/exact.py            branch and bound, for checking the heuristics
src/experiment.py       the multi-day simulation
src/study.py            runs all the experiments, writes all the outputs
src/figures.py          the maps and charts
src/draw.py             a small canvas that writes both SVG and TikZ
src/xlsx.py             a minimal Excel writer, so there is no dependency
src/site_page.py        builds the project web page
data/                   cached OpenStreetMap extract
out/results/            every table, as CSV, plus summary.json
out/figures/            every figure, as SVG and TikZ
out/dispatch-model.xlsx the results as a workbook
report/                 the written report
docs/                   the web page, ready for GitHub Pages
```

## The model

A technician's day is a route out of the Estate Office and back. The model
minimises

```
sum over jobs of (priority weight x hours late)  +  0.05 x walking minutes
```

subject to: each job done once, by a technician of the matching trade; nobody
starts a job before its access window opens or after it shuts; everyone back
at the depot by the end of the shift. Jobs that do not fit stay in the queue
and reappear the next day, so falling behind compounds.

Urgent complaints carry a weight of 10 and are promised four hours, normal
ones weigh 4 and are promised a working day, minor ones weigh 1 and are
promised three days. Walking is priced low on purpose: it breaks ties, it does
not drive the answer.

### Why the campus matters

A main road splits the campus and there is no crossing at road level. The
Estate Office is on the old campus; 19 of the 29 complaint sites are dorms on
the new campus. Walking times are built so that the only way across is the
walkway tunnel, which makes a cross-campus trip about 11 minutes against 2
minutes for one that stays on one side. Every technician starts the day on the
wrong side of the road, which is exactly what makes bundling worth doing.

### The four methods

| Method | What it does |
| --- | --- |
| `fifo` | Work the queue in arrival order. The baseline. |
| `savings` | Clarke and Wright: merge the pairs of jobs that save the most walking, checking the shift, the windows and the trade at every merge. |
| `priority` | Insert jobs one at a time, taking whichever gives the most urgency per extra minute of walking. |
| `savings+improve` | Savings, then 2-opt and Or-opt, including moving short runs of jobs between technicians. |

## Changing the assumptions

Everything you would want to argue with is at the top of `src/instance.py`:
complaints per day, the split between trades, repair times, how often each
priority comes up, what we promised for each, and the mix of access windows.
`src/campus.py` holds the walking speed, the detour factor and the tunnel
penalty, and `ALPHA` in `src/dispatch.py` sets what a minute of walking is
worth. Change any of them and rerun; the report quotes
`report/numbers.tex`, which is regenerated on every run, so the write-up
updates itself rather than going stale.

The assumption most worth replacing with real data is the access-window mix,
because the study shows it is what limits the result.

## What this does not do

Repair times are assumed known when the day is planned; in reality a
twenty-minute job sometimes takes ninety. The plan is made in the morning and
not revised, so a genuinely urgent complaint raised at eleven waits for the
next day. The exact check covers one technician with up to 10 jobs, not the
full nine-technician problem, which would need a proper mixed-integer solver.

## Credits

Campus geometry © OpenStreetMap contributors, used under the ODbL. Complaint
data is synthetic and does not describe any real person, room or ticket.
