"""
A very small drawing canvas that can write itself out as either SVG or TikZ.

The report is built with LaTeX and the web page is HTML, and they want
different file formats for the same picture. Rather than draw everything
twice, a figure is described once against this canvas and then written out in
both formats. Nothing here is clever: it supports lines, circles, text and
rectangles, which is all the figures in this project need.

Coordinates are in millimetres with y pointing up, which is how TikZ thinks.
The SVG writer flips y for us.
"""

PALETTE = {
    "ink":      "#1A1A1A",
    "muted":    "#6B7280",
    "faint":    "#D1D5DB",
    "paper":    "#FFFFFF",
    "accent":   "#1F4E79",
    "dorm":     "#2E7D32",
    "office":   "#6A4C93",
    "facility": "#B26500",
    "depot":    "#C62828",
    "road":     "#9AA3AC",
    "tunnel":   "#1F4E79",
    "r1":       "#1F4E79",
    "r2":       "#C62828",
    "r3":       "#2E7D32",
    "r4":       "#B26500",
    "r5":       "#6A4C93",
    "r6":       "#00796B",
    "r7":       "#AD1457",
    "r8":       "#5D4037",
    "r9":       "#37474F",
}

ROUTE_COLOURS = ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"]


class Canvas:
    def __init__(self, width, height, pad=4):
        self.w = width
        self.h = height
        self.pad = pad
        self.items = []

    # -- primitives ------------------------------------------------------
    def line(self, x1, y1, x2, y2, colour="ink", width=0.3, dash=None,
             opacity=1.0):
        self.items.append(("line", x1, y1, x2, y2, colour, width, dash, opacity))

    def polyline(self, pts, colour="ink", width=0.3, dash=None, opacity=1.0):
        for i in range(len(pts) - 1):
            self.line(*pts[i], *pts[i + 1], colour, width, dash, opacity)

    def circle(self, x, y, r, fill="ink", edge=None, width=0.2, opacity=1.0):
        self.items.append(("circle", x, y, r, fill, edge, width, opacity))

    def rect(self, x, y, w, h, fill=None, edge="ink", width=0.2, opacity=1.0):
        self.items.append(("rect", x, y, w, h, fill, edge, width, opacity))

    def text(self, x, y, s, colour="ink", size=2.2, anchor="middle",
             bold=False):
        self.items.append(("text", x, y, s, colour, size, anchor, bold))

    # -- output ----------------------------------------------------------
    def to_svg(self):
        """Write the canvas as a standalone SVG document."""
        px = 3.78  # millimetres to CSS pixels
        W, H = self.w * px, self.h * px

        def X(x):
            return round(x * px, 2)

        def Y(y):
            return round((self.h - y) * px, 2)

        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
            f'width="100%" role="img">',
            f'<rect width="{W:.0f}" height="{H:.0f}" fill="none"/>',
        ]
        for it in self.items:
            kind = it[0]
            if kind == "line":
                _, x1, y1, x2, y2, col, w, dash, op = it
                d = f' stroke-dasharray="{dash[0]*px:.1f},{dash[1]*px:.1f}"' if dash else ""
                out.append(
                    f'<line x1="{X(x1)}" y1="{Y(y1)}" x2="{X(x2)}" y2="{Y(y2)}" '
                    f'stroke="{PALETTE[col]}" stroke-width="{w*px:.2f}" '
                    f'stroke-linecap="round" opacity="{op}"{d}/>')
            elif kind == "circle":
                _, x, y, r, fill, edge, w, op = it
                e = f' stroke="{PALETTE[edge]}" stroke-width="{w*px:.2f}"' if edge else ""
                out.append(
                    f'<circle cx="{X(x)}" cy="{Y(y)}" r="{r*px:.2f}" '
                    f'fill="{PALETTE[fill] if fill else "none"}" opacity="{op}"{e}/>')
            elif kind == "rect":
                _, x, y, w_, h_, fill, edge, w, op = it
                f = PALETTE[fill] if fill else "none"
                e = f' stroke="{PALETTE[edge]}" stroke-width="{w*px:.2f}"' if edge else ""
                out.append(
                    f'<rect x="{X(x)}" y="{Y(y + h_)}" width="{w_*px:.2f}" '
                    f'height="{h_*px:.2f}" fill="{f}" opacity="{op}"{e}/>')
            elif kind == "text":
                _, x, y, s, col, size, anchor, bold = it
                a = {"middle": "middle", "left": "start", "right": "end"}[anchor]
                b = ' font-weight="600"' if bold else ""
                out.append(
                    f'<text x="{X(x)}" y="{Y(y) + size*px*0.35:.2f}" '
                    f'text-anchor="{a}" font-size="{size*px:.1f}" '
                    f'font-family="Inter, Helvetica, Arial, sans-serif" '
                    f'fill="{PALETTE[col]}"{b}>{_esc(s)}</text>')
        out.append("</svg>")
        return "\n".join(out)

    def to_tikz(self):
        """Write the canvas as a TikZ picture for inclusion in the report."""
        out = [r"\begin{tikzpicture}[x=1mm,y=1mm]"]
        out.append(f"\\useasboundingbox (0,0) rectangle ({self.w},{self.h});")
        for it in self.items:
            kind = it[0]
            if kind == "line":
                _, x1, y1, x2, y2, col, w, dash, op = it
                opts = [f"draw=fig{col}", f"line width={w}mm", "line cap=round"]
                if dash:
                    opts.append(f"dash pattern=on {dash[0]}mm off {dash[1]}mm")
                if op < 1:
                    opts.append(f"opacity={op}")
                out.append(f"\\draw[{','.join(opts)}] ({x1:.2f},{y1:.2f}) -- "
                           f"({x2:.2f},{y2:.2f});")
            elif kind == "circle":
                _, x, y, r, fill, edge, w, op = it
                opts = []
                if fill:
                    opts.append(f"fill=fig{fill}")
                if edge:
                    opts += [f"draw=fig{edge}", f"line width={w}mm"]
                if op < 1:
                    opts.append(f"opacity={op}")
                out.append(f"\\filldraw[{','.join(opts)}] ({x:.2f},{y:.2f}) "
                           f"circle ({r:.2f}mm);")
            elif kind == "rect":
                _, x, y, w_, h_, fill, edge, w, op = it
                opts = []
                if fill:
                    opts.append(f"fill=fig{fill}")
                if edge:
                    opts += [f"draw=fig{edge}", f"line width={w}mm"]
                if op < 1:
                    opts.append(f"opacity={op}")
                out.append(f"\\filldraw[{','.join(opts)}] ({x:.2f},{y:.2f}) "
                           f"rectangle ({x+w_:.2f},{y+h_:.2f});")
            elif kind == "text":
                _, x, y, s, col, size, anchor, bold = it
                a = {"middle": "", "left": "west", "right": "east"}[anchor]
                anchor_opt = f"anchor={a}," if a else ""
                pt = max(3, size * 2.6)
                body = _tex(s)
                if bold:
                    body = r"\bfseries " + body
                out.append(
                    f"\\node[{anchor_opt}text=fig{col},inner sep=0pt,"
                    f"font=\\fontsize{{{pt:.1f}}}{{{pt*1.2:.1f}}}\\selectfont] "
                    f"at ({x:.2f},{y:.2f}) {{{body}}};")
        out.append(r"\end{tikzpicture}")
        return "\n".join(out)


def tikz_colour_preamble():
    """The \\definecolor lines the TikZ figures need."""
    lines = []
    for name, hexcode in PALETTE.items():
        lines.append(f"\\definecolor{{fig{name}}}{{HTML}}{{{hexcode[1:]}}}")
    return "\n".join(lines)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _tex(s):
    s = str(s)
    for a, b in (("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#")):
        s = s.replace(a, b)
    return s
