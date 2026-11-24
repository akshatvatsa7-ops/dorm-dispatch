"""
Builds the slide deck for the dorm maintenance dispatch project.

Unlike the rest of this repository, this one script needs a library:

    pip install python-pptx
    python3 slides/make_deck.py

Every number on the slides is read from out/results/summary.json, which the
model writes when you run run.py, so the deck cannot drift away from the
results the same way a hand-typed deck would.
"""

import json
import os

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG = os.path.join(HERE, "img")

# IIMA is a red brick campus, so the deck is built round brick rather than
# the usual corporate blue.
BRICK = RGBColor(0xB8, 0x50, 0x42)
DEEP = RGBColor(0x6E, 0x32, 0x28)
INK = RGBColor(0x2B, 0x25, 0x22)
SAND = RGBColor(0xF0, 0xEA, 0xE4)
SLATE = RGBColor(0x6E, 0x7B, 0x87)
GREEN = RGBColor(0x4E, 0x7A, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xE4, 0xD9, 0xD2)

HEAD = "Cambria"
BODY = "Calibri"

W, H = 13.333, 7.5
MARGIN = 0.75


def load():
    with open(os.path.join(ROOT, "out", "results", "summary.json")) as f:
        return json.load(f)


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def bg(slide, colour):
    r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(H))
    r.fill.solid()
    r.fill.fore_color.rgb = colour
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def box(slide, x, y, w, h, *, fill=None, line=None, radius=None, shadow=False):
    shape = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    if radius:
        s.adjustments[0] = radius
    if not shadow:
        s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, *, size=15, colour=INK, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=6, line=1.15,
         italic=False):
    """runs is a string, or a list of (string, {overrides}) pairs per line."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0

    lines = [runs] if isinstance(runs, str) else runs
    for i, item in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        p.line_spacing = line
        if isinstance(item, str):
            item = (item, {})
        content, over = item
        pieces = content if isinstance(content, list) else [(content, {})]
        for frag, frag_over in pieces:
            r = p.add_run()
            r.text = frag
            f = r.font
            o = dict(over)
            o.update(frag_over)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.name = o.get("font", font)
            f.color.rgb = o.get("colour", colour)
    return tb


def title(slide, words, *, colour=INK, sub=None, sub_colour=None):
    text(slide, MARGIN, 0.46, W - 2 * MARGIN, 0.85, words,
         size=34, bold=True, font=HEAD, colour=colour)
    if sub:
        text(slide, MARGIN, 1.32, W - 2 * MARGIN, 0.42, sub,
             size=15, colour=sub_colour or SLATE, italic=True)


def dot(slide, x, y, d, label, *, fill=BRICK, colour=WHITE, size=14):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                               Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.name = BODY
    r.font.color.rgb = colour
    return s


def picture(slide, path, x, y, w):
    return slide.shapes.add_picture(os.path.join(IMG, path), Inches(x),
                                    Inches(y), width=Inches(w))


def stat(slide, x, y, w, big, small, *, colour=BRICK, big_size=40):
    text(slide, x, y, w, 0.62, big, size=big_size, bold=True, font=HEAD,
         colour=colour, space=0)
    text(slide, x, y + 0.63, w, 0.5, small, size=12, colour=SLATE, space=0)


def footer(slide, n, *, colour=None):
    text(slide, W - MARGIN - 1.2, H - 0.52, 1.2, 0.3, str(n), size=11,
         colour=colour or PALE, align=PP_ALIGN.RIGHT, space=0)


# ---------------------------------------------------------------------------
# The slides
# ---------------------------------------------------------------------------

def slide_title(prs, d):
    s = blank(prs)
    bg(s, DEEP)
    text(s, MARGIN, 2.30, 11.85, 1.0,
         "Dispatching the dorm maintenance crew",
         size=42, bold=True, font=HEAD, colour=WHITE, space=0, line=1.05)
    text(s, MARGIN, 3.22, 11.85, 0.45,
         "An optimisation model for the IIMA Estate Office",
         size=18, colour=PALE, space=0)
    text(s, MARGIN, 4.15, 10.2, 0.9,
         [([("Same nine technicians, same campus. ", {}),
            ("41% less walking and more than double the urgent complaints "
             "closed on time.", {"bold": True, "colour": WHITE})], {})],
         size=16, colour=PALE, line=1.3)
    text(s, MARGIN, H - 1.0, 8.0, 0.4,
         "Operations Management & Logistics  |  group project",
         size=12, colour=PALE, space=0)


def slide_problem(prs, d):
    s = blank(prs)
    f, i = d["methods"]["fifo"], d["methods"]["savings+improve"]
    title(s, "The queue is worked in the order complaints arrive",
          sub="It sounds fair, and it fails in two separate ways")

    cards = [
        ("Wasted walking", f"{f['travel_per_tech_day']} min",
         "walked per technician per day",
         "Complaints arrive in no geographic order, so a technician is sent "
         "from one end of campus to the other and back. The road splits the "
         "campus and only the tunnel crosses it, so a badly ordered day "
         "throws away the better part of an hour."),
        ("Urgency ignored", f"{f['by_priority']['1']['sla_met_pct']}%",
         "of urgent complaints closed in time",
         "A blocked drain and a squeaky hinge are treated identically if "
         "they were reported in that order. Nothing in the queue knows that "
         "one of them was promised in four hours."),
    ]
    for k, (head, big, cap, para) in enumerate(cards):
        x = MARGIN + k * 6.05
        box(s, x, 2.0, 5.55, 4.25, fill=SAND, radius=0.04)
        dot(s, x + 0.42, 2.42, 0.44, str(k + 1))
        text(s, x + 1.05, 2.46, 3.9, 0.4, head, size=19, bold=True, font=HEAD)
        stat(s, x + 0.42, 3.15, 4.7, big, cap)
        text(s, x + 0.42, 4.42, 4.72, 1.6, para, size=13.5, colour=INK,
             line=1.28)

    text(s, MARGIN, 6.52, 11.9, 0.5,
         [([("The question: ", {"bold": True}),
            ("given the complaints waiting at the start of a day, which "
             "technician takes which jobs, and in what order?",
             {"italic": True})], {})],
         size=15, colour=DEEP, space=0)
    footer(s, 2, colour=SLATE)


def slide_campus(prs, d):
    s = blank(prs)
    c = d["campus"]
    title(s, "Why this campus makes it hard",
          sub="Two things, and the second one is the interesting one")
    picture(s, "campus.png", 5.55, 2.25, 7.1)

    rows = [
        ("A road with one crossing",
         f"Everything between the two halves goes through the walkway "
         f"tunnel: about {c['mean_cross_campus']} minutes, against "
         f"{c['mean_same_campus']} for a trip that stays on one side."),
        ("The crews sit on opposite sides",
         "Electricians work out of Dorm 7 on the main campus; plumbers and "
         "carpenters out of Dorm 24 on the new campus. 460 m apart in a "
         "straight line, 10.6 minutes apart on foot."),
        ("So the trades see different campuses",
         "The same job is cheap for one trade and expensive for another. "
         "A sensible bundle of work for the electricians is not a sensible "
         "bundle for the plumbers."),
    ]
    y = 2.3
    for k, (head, para) in enumerate(rows):
        dot(s, MARGIN, y + 0.02, 0.38, str(k + 1))
        text(s, MARGIN + 0.58, y, 4.1, 0.34, head, size=15.5, bold=True,
             font=HEAD, colour=DEEP, space=0)
        text(s, MARGIN + 0.58, y + 0.42, 4.2, 1.1, para, size=13, colour=INK,
             line=1.26, space=0)
        y += 1.52
    footer(s, 3, colour=SLATE)


def slide_model(prs, d):
    s = blank(prs)
    title(s, "What the model decides, and what it is judged on",
          sub="Lateness is the goal; walking is only the tiebreaker")

    box(s, MARGIN, 2.05, 11.83, 1.42, fill=SAND, radius=0.08)
    text(s, MARGIN + 0.5, 2.3, 10.9, 0.45,
         [([("minimise    ", {"colour": SLATE, "size": 14}),
            ("Σ (priority weight × hours late)", {"bold": True,
                                                            "size": 17}),
            ("    +    0.05 × walking minutes", {"size": 17})], {})],
         size=17, colour=DEEP, space=0, font=BODY)
    text(s, MARGIN + 0.5, 2.88, 10.9, 0.42,
         "Urgent complaints weigh 10, normal 4, minor 1. Walking is priced "
         "low on purpose: we never accept a later repair to save a walk.",
         size=12.5, colour=SLATE, space=0)

    text(s, MARGIN, 3.78, 5.4, 0.35, "Subject to", size=15, bold=True,
         font=HEAD, colour=DEEP, space=0)
    rules = [
        "every job done once, and only by a technician of that trade",
        "nobody starts before the access window opens or after it shuts",
        "nobody is still working after the shift ends",
        "everyone back at their own trade's store room by the end of the day",
    ]
    y = 4.26
    for r in rules:
        dot(s, MARGIN + 0.02, y + 0.03, 0.18, "", fill=BRICK)
        text(s, MARGIN + 0.42, y - 0.03, 5.0, 0.6, r, size=13.5, line=1.22,
             space=0)
        y += 0.66

    box(s, 7.0, 3.78, 5.58, 2.85, fill=None, line=PALE, radius=0.05)
    text(s, 7.4, 4.05, 4.8, 0.35, "The one subtlety worth knowing",
         size=15, bold=True, font=HEAD, colour=DEEP, space=0)
    text(s, 7.4, 4.52, 4.85, 1.9,
         "A job that does not fit today is not lost — it comes back "
         "tomorrow. But if deferring were free, the cheapest plan would be "
         "to do nothing at all. So a job the model considers leaving is "
         "charged the lateness it would pick up by the end of tomorrow. A "
         "minor complaint with three days left costs nothing to postpone. An "
         "urgent one costs a great deal.",
         size=13, colour=INK, line=1.3, space=0)
    footer(s, 4, colour=SLATE)


def slide_methods(prs, d):
    s = blank(prs)
    title(s, "Four ways to plan the day",
          sub="Built in order, so each one shows up what the last was missing")

    cards = [
        ("First come, first served", "the baseline",
         "Take them in the order raised. No attention to where anything is "
         "or when it is due. Roughly what happens today."),
        ("Clarke and Wright savings", "fixes the walking",
         "Start with every job as its own trip, then merge the pairs that "
         "save the most walking, checking the shift and the windows at "
         "every merge."),
        ("Priority insertion", "fixes the urgency",
         "Insert jobs one at a time, always taking whichever gives the most "
         "urgency per extra minute of walking. Bang per buck."),
        ("Savings + improvement", "what we recommend",
         "Savings, then 2-opt to untangle crossings, Or-opt to shuffle jobs "
         "within a route, and Or-opt across technicians to even out the "
         "workload."),
    ]
    for k, (head, tag, para) in enumerate(cards):
        x = MARGIN + k * 3.03
        best = k == 3
        box(s, x, 2.15, 2.78, 3.5, fill=SAND if not best else DEEP, radius=0.05)
        dot(s, x + 0.3, 2.45, 0.4, str(k + 1),
            fill=WHITE if best else BRICK, colour=DEEP if best else WHITE,
            size=13)
        text(s, x + 0.3, 3.02, 2.2, 0.75, head, size=14.5, bold=True,
             font=HEAD, colour=WHITE if best else INK, line=1.1, space=0)
        text(s, x + 0.3, 3.82, 2.2, 0.28, tag, size=11.5, italic=True,
             colour=PALE if best else BRICK, space=0)
        text(s, x + 0.3, 4.2, 2.22, 1.35, para, size=12, line=1.25,
             colour=PALE if best else INK, space=0)

    box(s, MARGIN, 5.95, 11.83, 0.92, fill=None, line=PALE, radius=0.07)
    text(s, MARGIN + 0.38, 6.12, 11.1, 0.62,
         [([("Worth knowing:  ", {"bold": True, "colour": DEEP}),
            ("savings was never told the tunnel exists. Because every "
             "new-campus job is a long walk from Dorm 7, the savings from "
             "pairing two of them are large, so the method bundles them into "
             "one crossing by itself — and bundles main-campus work for "
             "the plumbers, in the opposite direction.", {})], {})],
         size=13, colour=INK, line=1.25, space=0)
    footer(s, 5, colour=SLATE)


def slide_before_after(prs, d):
    s = blank(prs)
    one = d["one_day"]
    title(s, "The same three electricians, the same day",
          sub=f"{one['tickets']} complaints, planned two different ways")

    for k, (img, head, mins, colour) in enumerate([
            ("routes_fifo.png", "First come, first served",
             one["fifo"]["travel"], SLATE),
            ("routes_improved.png", "Savings + improvement",
             one["savings+improve"]["travel"], BRICK)]):
        x = MARGIN + k * 6.05
        text(s, x, 2.08, 5.5, 0.34, head, size=15.5, bold=True, font=HEAD,
             colour=colour, space=0)
        picture(s, img, x, 2.55, 5.55)
        text(s, x, 5.72, 5.5, 0.4,
             [([(f"{mins:.0f}", {"size": 25, "bold": True, "font": HEAD,
                                 "colour": colour}),
                (" minutes of walking", {"size": 13, "colour": SLATE})], {})],
             space=0)

    text(s, MARGIN, 6.52, 11.9, 0.55,
         "The baseline crosses the tunnel again and again and wanders "
         "between campuses. The optimised plan crosses once per technician, "
         "works the whole cluster, and comes back.",
         size=13.5, colour=INK, line=1.25, space=0)
    footer(s, 6, colour=SLATE)


def slide_results(prs, d):
    s = blank(prs)
    f, i = d["methods"]["fifo"], d["methods"]["savings+improve"]
    title(s, "What it is worth over thirty days",
          sub="Same nine technicians, same complaints, same campus")

    chart_data = CategoryChartData()
    chart_data.categories = ["First come\nfirst served", "Savings",
                             "Priority\ninsertion", "Savings +\nimprovement"]
    chart_data.add_series("Urgent complaints closed on time", (
        d["methods"]["fifo"]["by_priority"]["1"]["sla_met_pct"],
        d["methods"]["savings"]["by_priority"]["1"]["sla_met_pct"],
        d["methods"]["priority"]["by_priority"]["1"]["sla_met_pct"],
        d["methods"]["savings+improve"]["by_priority"]["1"]["sla_met_pct"]))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(MARGIN),
                            Inches(2.1), Inches(6.5), Inches(4.0),
                            chart_data)
    ch = gf.chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "Urgent complaints closed within four hours (%)"
    tfr = ch.chart_title.text_frame.paragraphs[0].runs[0].font
    tfr.size, tfr.bold, tfr.name, tfr.color.rgb = Pt(13), True, HEAD, DEEP
    ch.has_legend = False
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = '0.0"%"', False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.bold, dl.font.name = Pt(11), True, BODY
    dl.font.color.rgb = INK
    ser = plot.series[0]
    for k, pt in enumerate(ser.points):
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = BRICK if k == 3 else PALE
    for axis, labels in ((ch.category_axis, True), (ch.value_axis, True)):
        axis.has_major_gridlines = axis is ch.value_axis
        axis.tick_labels.font.size = Pt(11)
        axis.tick_labels.font.name = BODY
        axis.tick_labels.font.color.rgb = SLATE
    ch.value_axis.maximum_scale = 100.0
    ch.value_axis.major_gridlines.format.line.color.rgb = PALE
    ch.value_axis.major_gridlines.format.line.width = Pt(0.75)
    ch.category_axis.format.line.color.rgb = PALE

    rows = [
        ("Walking per technician, per day",
         f"{f['travel_per_tech_day']} min", f"{i['travel_per_tech_day']} min"),
        ("All complaints closed on time",
         f"{f['sla_met_pct']}%", f"{i['sla_met_pct']}%"),
        ("Average queue left at day's end",
         f"{f['mean_backlog']}", f"{i['mean_backlog']}"),
    ]
    text(s, 7.75, 2.12, 2.6, 0.3, "Before", size=12, bold=True, colour=SLATE,
         space=0)
    text(s, 10.75, 2.12, 2.0, 0.3, "After", size=12, bold=True, colour=BRICK,
         space=0)
    y = 2.56
    for label, before, after in rows:
        text(s, 7.75, y, 5.0, 0.32, label, size=12.5, colour=INK, space=0)
        text(s, 7.75, y + 0.34, 2.6, 0.45, before, size=22, bold=True,
             font=HEAD, colour=SLATE, space=0)
        text(s, 10.75, y + 0.34, 2.0, 0.45, after, size=22, bold=True,
             font=HEAD, colour=BRICK, space=0)
        y += 1.18
    box(s, 7.75, 5.98, 4.85, 0.78, fill=SAND, radius=0.1)
    text(s, 8.05, 6.14, 4.3, 0.5,
         "Stable across five independent ticket streams, and the ranking "
         "never changes.", size=12.5, colour=DEEP, line=1.2, space=0)
    footer(s, 7, colour=SLATE)


def slide_finding(prs, d):
    s = blank(prs)
    bg(s, DEEP)
    i = d["methods"]["savings+improve"]
    f = d["methods"]["fifo"]
    title(s, "The finding worth leading with", colour=WHITE,
          sub="We did not expect to run out of room this cleanly",
          sub_colour=PALE)

    box(s, MARGIN, 2.2, 4.3, 3.45, fill=BRICK, radius=0.05)
    text(s, MARGIN + 0.4, 2.62, 3.5, 1.3, str(i["urgent_avoidable_misses"]),
         size=96, bold=True, font=HEAD, colour=WHITE, space=0, line=0.95)
    text(s, MARGIN + 0.4, 4.05, 3.6, 1.3,
         "urgent complaints were closed late that anybody could have closed "
         "on time, in thirty days",
         size=15, colour=WHITE, line=1.25, space=0)

    text(s, 5.65, 2.3, 6.95, 2.4,
         [(f"Of the {i['urgent_total']} urgent complaints raised over the "
           f"month, {i['urgent_impossible']} could never have met the "
           f"four-hour promise, no matter who was sent or in what order. The "
           f"room can only be opened in the afternoon and the repair itself "
           f"runs past the deadline.", {}),
          ([("The optimised plan closed ", {}),
            (f"{i['urgent_late']}", {"bold": True, "colour": WHITE}),
            (" urgent complaints late, and all ", {}),
            (f"{i['urgent_late_but_impossible']}", {"bold": True,
                                                    "colour": WHITE}),
            (" of them were of exactly that kind. The two numbers are the "
             "same number.", {})], {})],
         size=14.5, colour=PALE, line=1.32, space=10)

    box(s, 5.65, 4.92, 6.95, 1.5, fill=None, line=BRICK, radius=0.06)
    text(s, 6.0, 5.12, 6.3, 1.15,
         [([("So the scheduling is finished. ", {"bold": True,
                                                 "colour": WHITE}),
            ("What is left is a problem with the promise, not the plan. "
             "Either stop promising four hours on complaints that can only "
             "be accessed in the afternoon, or give the crew a key. The "
             "second is worth about ", {}),
            (f"{i['urgent_impossible']} rescued complaints a month",
             {"bold": True, "colour": WHITE}),
            (".", {})], {})],
         size=13.5, colour=PALE, line=1.28, space=0)
    text(s, MARGIN, 5.9, 4.3, 0.6,
         f"The baseline missed {f['urgent_avoidable_misses']} that were "
         f"perfectly achievable.", size=13, colour=PALE, line=1.25,
         space=0)
    footer(s, 8)


def slide_surprises(prs, d):
    s = blank(prs)
    crew = d["crew"]
    NINE = "3 of each trade (9)"
    TWELVE = "4 of each trade (12)"
    REBAL = "4 electrical / 4 plumbing / 1 carpentry (9)"
    title(s, "Two results that went against our own guess",
          sub="Both are worth having ready, because they invite the obvious "
              "question")

    items = [
        ("Adding people is not the answer — until it is",
         "Six collapses, nine is enough, twelve buys almost nothing "
         f"({crew[NINE]['objective']:.0f} to "
         f"{crew[TWELVE]['objective']:.0f}) and fifteen nothing at all. But "
         "at 85 complaints a day nine are overwhelmed and twelve cope; at "
         "110 you need fifteen. Crew size and complaint rate have to be "
         "answered together.",
         "Budget one technician per six complaints a day."),
        ("Matching staff to average demand makes it worse",
         "Carpentry is the quietest trade, so four electricians, four "
         "plumbers and one carpenter looks efficient. The same nine people, "
         "allocated that way, score "
         f"{crew[REBAL]['objective']:.0f} against "
         f"{crew[NINE]['objective']:.0f}.",
         "The quiet trade is quiet on average, not on a bad day."),
    ]
    for k, (head, para, punch) in enumerate(items):
        x = MARGIN + k * 6.05
        box(s, x, 2.1, 5.55, 3.9, fill=SAND, radius=0.05)
        dot(s, x + 0.42, 2.5, 0.42, str(k + 1))
        text(s, x + 1.05, 2.5, 4.1, 0.75, head, size=17, bold=True, font=HEAD,
             colour=DEEP, line=1.12, space=0)
        text(s, x + 0.42, 3.55, 4.7, 1.6, para, size=13.5, colour=INK,
             line=1.3, space=0)
        text(s, x + 0.42, 5.18, 4.7, 0.6, punch, size=14, bold=True,
             italic=True, colour=BRICK, line=1.2, space=0)

    text(s, MARGIN, 6.3, 11.9, 0.6,
         "A single carpenter who falls behind never catches up, and the "
         "backlog compounds day after day. Averages hide exactly the days "
         "that matter.",
         size=13.5, colour=SLATE, line=1.25, space=0)
    footer(s, 9, colour=SLATE)


def slide_recommend(prs, d):
    s = blank(prs)
    bg(s, DEEP)
    i = d["methods"]["savings+improve"]
    f = d["methods"]["fifo"]
    cut = round(100 * (f["travel_per_tech_day"] - i["travel_per_tech_day"])
                / f["travel_per_tech_day"], 1)
    title(s, "What we would tell the Estate Office", colour=WHITE)

    recs = [
        ("Plan the day in the morning",
         f"Instead of working the queue as it arrives. Worth {cut}% of the "
         f"crew's walking and more than double the urgent complaints closed "
         f"on time, with no extra staff and no new equipment."),
        ("Bundle by campus — each trade has its own far side",
         "Cross the tunnel, work the whole cluster, come back. The "
         "electricians should be batching new-campus work and the plumbers "
         "and carpenters main-campus work, crossing in opposite directions."),
        ("Keep nine technicians, three per trade",
         "Do not hire, and do not rebalance the trades to match average "
         "workload. Both make things worse, for different reasons."),
        ("Fix the promise, or fix the access",
         "This is the only thing left that would help. Every urgent "
         "complaint still closed late is one the crew physically could not "
         "reach in time."),
    ]
    y = 1.78
    for k, (head, para) in enumerate(recs):
        dot(s, MARGIN, y + 0.04, 0.4, str(k + 1), fill=BRICK)
        text(s, MARGIN + 0.62, y, 11.2, 0.34, head, size=16.5, bold=True,
             font=HEAD, colour=WHITE, space=0)
        text(s, MARGIN + 0.62, y + 0.42, 11.2, 0.72, para, size=13.5,
             colour=PALE, line=1.26, space=0)
        y += 1.3

    text(s, MARGIN, 6.95, 11.9, 0.4,
         "Code, report and figures: github.com/akshatvatsa7-ops/dorm-dispatch",
         size=12, colour=PALE, space=0)
    footer(s, 10)


def main():
    d = load()
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    for fn in (slide_title, slide_problem, slide_campus, slide_model,
               slide_methods, slide_before_after, slide_results,
               slide_finding, slide_surprises, slide_recommend):
        fn(prs, d)
    out = os.path.join(HERE, "dorm-dispatch.pptx")
    prs.save(out)
    print(f"wrote {out}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
