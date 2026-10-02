"""Page layout, styles and a small diagram toolkit for the Ledgerline guide PDF.

Content lives in build_guide.py; this file only knows how to draw things.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ---------------------------------------------------------------------------
# Fonts: macOS system fonts with arrows and box-drawing characters.
# ---------------------------------------------------------------------------
SUPP = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Body", SUPP + "Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", SUPP + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", SUPP + "Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", SUPP + "Arial Bold Italic.ttf"))
pdfmetrics.registerFontFamily(
    "Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic"
)
pdfmetrics.registerFont(TTFont("Mono", "/System/Library/Fonts/Menlo.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("Mono-Bold", "/System/Library/Fonts/Menlo.ttc", subfontIndex=1))
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")

# ---------------------------------------------------------------------------
# Colours: one per role, reused in every diagram so the reader learns them.
# ---------------------------------------------------------------------------
INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#5f6b7a")
RULE = colors.HexColor("#d5dbe3")
CODE_BG = colors.HexColor("#f4f6f8")
ACCENT = colors.HexColor("#1d4e89")

CLIENT = colors.HexColor("#d9ecf2")  # the AI app / demo client
CLIENT_EDGE = colors.HexColor("#2b7a99")
PROXY = colors.HexColor("#e3e1f5")  # Ledgerline
PROXY_EDGE = colors.HexColor("#4b3f9e")
SERVER = colors.HexColor("#f8ead2")  # tool servers
SERVER_EDGE = colors.HexColor("#b07419")
DATA = colors.HexColor("#e5f1df")  # files: lock, log, fixtures
DATA_EDGE = colors.HexColor("#4f8a3c")
FUTURE = colors.HexColor("#f1f2f4")  # not built yet
FUTURE_EDGE = colors.HexColor("#9aa4b1")
DANGER = colors.HexColor("#b3261e")
DANGER_BG = colors.HexColor("#fbe3e1")
OK = colors.HexColor("#2e7d32")
NOTE_BG = colors.HexColor("#fff8dc")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Text styles
# ---------------------------------------------------------------------------
BODY = ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.4, leading=11.2, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.4, leading=10.8, spaceAfter=0)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, fontName="Body-Bold", textColor=colors.white)
H1 = ParagraphStyle(
    "h1",
    fontName="Body-Bold",
    fontSize=20,
    leading=25,
    textColor=ACCENT,
    spaceBefore=4,
    spaceAfter=10,
    keepWithNext=1,
)
H2 = ParagraphStyle(
    "h2",
    fontName="Body-Bold",
    fontSize=13.5,
    leading=18,
    textColor=ACCENT,
    spaceBefore=12,
    spaceAfter=6,
    keepWithNext=1,
)
H3 = ParagraphStyle(
    "h3",
    fontName="Body-Bold",
    fontSize=10.8,
    leading=14,
    textColor=INK,
    spaceBefore=8,
    spaceAfter=4,
    keepWithNext=1,
)
CODE = ParagraphStyle("code", fontName="Mono", fontSize=7.6, leading=10, textColor=INK)
CAPTION = ParagraphStyle("caption", parent=SMALL, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=3)
TITLE = ParagraphStyle("title", fontName="Body-Bold", fontSize=34, leading=40, textColor=ACCENT)
SUBTITLE = ParagraphStyle("subtitle", fontName="Body", fontSize=14, leading=19, textColor=MUTED)


# ---------------------------------------------------------------------------
# Mini markup: `code` and **bold** inside ordinary text.
# ---------------------------------------------------------------------------
def md(text: str) -> str:
    """Escape text for ReportLab and turn `code` into monospace and **x** into bold."""
    parts = text.split("`")
    out = []
    for i, part in enumerate(parts):
        if i % 2:  # inside backticks
            out.append(f'<font name="Mono" size="8.3" color="#8a2d0b">{escape(part)}</font>')
        else:
            seg = escape(part)
            seg = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", seg)
            seg = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<i>\1</i>", seg)
            seg = seg.replace("⚠", '<font name="Mono">⚠</font>')  # the body font has no warning sign
            out.append(seg)
    return "".join(out)


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(md(text), style)


def bullets(items: Sequence[str], style: ParagraphStyle = BULLET) -> list[Flowable]:
    return [Paragraph(md(item), style, bulletText="•") for item in items]


def numbered(items: Sequence[str]) -> list[Flowable]:
    return [Paragraph(md(item), BULLET, bulletText=f"{i}.") for i, item in enumerate(items, 1)]


def code(text: str, title: str | None = None) -> Flowable:
    """A shaded code block. Text is shown exactly as written."""
    block = Preformatted(text.strip("\n"), CODE)
    rows: list[list[Flowable]] = []
    if title:
        rows.append(
            [Paragraph(md(title), ParagraphStyle("ct", parent=SMALL, fontName="Body-Bold", textColor=MUTED))]
        )
    rows.append([block])
    t = Table(rows, colWidths=[CONTENT_W])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return KeepTogether([t, Spacer(1, 6)])


def table(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    head_bg: colors.Color = ACCENT,
) -> Table:
    """A striped table whose cells understand the md() markup."""
    data = [[Paragraph(md(h), CELL_HEAD) for h in header]]
    data += [[Paragraph(md(c), CELL) for c in row] for row in rows]
    total = sum(widths)
    t = Table(data, colWidths=[w / total * CONTENT_W for w in widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), head_bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f9fb")))
    t.setStyle(TableStyle(style))
    return t


def callout(text: str, kind: str = "note") -> Table:
    """A coloured box for tips (note), warnings (warn) and Java comparisons (java)."""
    bg, edge, label = {
        "note": (NOTE_BG, colors.HexColor("#c9a227"), "Note"),
        "warn": (DANGER_BG, DANGER, "Watch out"),
        "java": (colors.HexColor("#e8f0fb"), ACCENT, "Coming from Java"),
        "ok": (colors.HexColor("#e6f4ea"), OK, "Key idea"),
    }[kind]
    para = Paragraph(f'<font name="Body-Bold" color="{edge.hexval()}">{label}: </font>' + md(text), CELL)
    t = Table([[para]], colWidths=[CONTENT_W])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def figure(drawing: Drawing, caption: str) -> KeepTogether:
    return KeepTogether([drawing, Paragraph(md(caption), CAPTION)])


# ---------------------------------------------------------------------------
# Diagram toolkit
# ---------------------------------------------------------------------------
def _text_lines(
    d: Drawing, cx: float, top: float, lines: Sequence[str], size: float, font: str, color: colors.Color
) -> None:
    for i, line in enumerate(lines):
        d.add(
            String(
                cx,
                top - (i + 1) * (size + 2.2),
                line,
                fontName=font,
                fontSize=size,
                fillColor=color,
                textAnchor="middle",
            )
        )


def box(
    d: Drawing,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: Sequence[str] = (),
    fill: colors.Color = PROXY,
    edge: colors.Color = PROXY_EDGE,
    title_size: float = 8.6,
    line_size: float = 6.9,
    dashed: bool = False,
    mono_lines: bool = True,
) -> tuple[float, float, float, float]:
    """A rounded box with a bold title and optional small lines underneath. (x, y) is bottom-left."""
    d.add(
        Rect(
            x,
            y,
            w,
            h,
            rx=4,
            ry=4,
            fillColor=fill,
            strokeColor=edge,
            strokeWidth=0.9,
            strokeDashArray=[3, 2] if dashed else None,
        )
    )
    block_h = (title_size + 2.2) + len(lines) * (line_size + 2.2)
    top = y + h / 2 + block_h / 2
    _text_lines(d, x + w / 2, top, [title], title_size, "Body-Bold", INK)
    _text_lines(
        d, x + w / 2, top - (title_size + 2.2), lines, line_size, "Mono" if mono_lines else "Body", MUTED
    )
    return x, y, w, h


def arrow(
    d: Drawing,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    label: str | None = None,
    color: colors.Color = INK,
    dashed: bool = False,
    label_dy: float = 3,
    label_dx: float = 0,
    size: float = 6.6,
    both: bool = False,
) -> None:
    """A straight arrow from (x1, y1) to (x2, y2), with an optional label at its middle."""
    import math

    d.add(
        Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=0.9, strokeDashArray=[3, 2] if dashed else None)
    )
    ends = [(x1, y1, x2, y2)] + ([(x2, y2, x1, y1)] if both else [])
    for ax, ay, bx, by in ends:
        angle = math.atan2(by - ay, bx - ax)
        hl, hw = 6.0, 2.7
        p1 = (
            bx - hl * math.cos(angle) + hw * math.sin(angle),
            by - hl * math.sin(angle) - hw * math.cos(angle),
        )
        p2 = (
            bx - hl * math.cos(angle) - hw * math.sin(angle),
            by - hl * math.sin(angle) + hw * math.cos(angle),
        )
        d.add(
            Polygon([bx, by, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color, strokeWidth=0.5)
        )
    if label:
        d.add(
            String(
                (x1 + x2) / 2 + label_dx,
                (y1 + y2) / 2 + label_dy,
                label,
                fontName="Body",
                fontSize=size,
                fillColor=color,
                textAnchor="middle",
            )
        )


def elbow(
    d: Drawing,
    points: Sequence[tuple[float, float]],
    label: str | None = None,
    color: colors.Color = INK,
    dashed: bool = False,
) -> None:
    """A polyline arrow through several points (arrowhead on the last segment)."""
    for (ax, ay), (bx, by) in itertools.pairwise(points[:-1]):
        d.add(
            Line(
                ax, ay, bx, by, strokeColor=color, strokeWidth=0.9, strokeDashArray=[3, 2] if dashed else None
            )
        )
    (ax, ay), (bx, by) = points[-2], points[-1]
    arrow(d, ax, ay, bx, by, color=color, dashed=dashed)
    if label:
        mx, my = points[len(points) // 2]
        d.add(String(mx + 3, my + 3, label, fontName="Body", fontSize=6.6, fillColor=color))


def diamond(
    d: Drawing, cx: float, cy: float, w: float, h: float, lines: Sequence[str], fill: colors.Color = NOTE_BG
) -> None:
    d.add(
        Polygon(
            [cx, cy + h / 2, cx + w / 2, cy, cx, cy - h / 2, cx - w / 2, cy],
            fillColor=fill,
            strokeColor=colors.HexColor("#c9a227"),
            strokeWidth=0.9,
        )
    )
    block = len(lines) * 9.2
    _text_lines(d, cx, cy + block / 2, lines, 7, "Body", INK)


def label(
    d: Drawing,
    x: float,
    y: float,
    text: str,
    size: float = 7,
    color: colors.Color = MUTED,
    anchor: str = "start",
    bold: bool = False,
) -> None:
    d.add(
        String(
            x,
            y,
            text,
            fontName="Body-Bold" if bold else "Body",
            fontSize=size,
            fillColor=color,
            textAnchor=anchor,
        )
    )


def legend(d: Drawing, x: float, y: float, items: Sequence[tuple[str, colors.Color, colors.Color]]) -> None:
    for i, (name, fill, edge) in enumerate(items):
        xx = x + i * 92
        d.add(Rect(xx, y, 10, 8, fillColor=fill, strokeColor=edge, strokeWidth=0.7))
        label(d, xx + 14, y + 1, name, size=6.8, color=INK)


# --- Sequence diagrams -------------------------------------------------------
@dataclass
class Msg:
    src: str
    dst: str
    text: str
    kind: str = "call"  # call | reply | blocked | proxy


@dataclass
class Note:
    over: tuple[str, ...]
    text: str
    kind: str = "note"  # note | danger | ok


@dataclass
class Divider:
    text: str


def sequence(
    participants: Sequence[tuple[str, str, colors.Color, colors.Color]],
    steps: Sequence[Msg | Note | Divider],
    width: float = CONTENT_W,
) -> Drawing:
    """Draw a UML-style sequence diagram.

    participants: (key, title, fill, edge). Messages flow top to bottom.
    """
    head_h, row, top_pad = 30.0, 17.0, 8.0
    heights = [(row + 4 if isinstance(s, Note) else row) for s in steps]
    height = top_pad + head_h + sum(heights) + 14
    d = Drawing(width, height)
    n = len(participants)
    gap = width / n
    xs = {key: gap * (i + 0.5) for i, (key, *_rest) in enumerate(participants)}

    top = height - top_pad
    for key, title, fill, edge in participants:
        w = min(gap - 10, 128)
        box(d, xs[key] - w / 2, top - head_h, w, head_h, title, fill=fill, edge=edge, title_size=8)
        d.add(
            Line(
                xs[key],
                top - head_h,
                xs[key],
                6,
                strokeColor=FUTURE_EDGE,
                strokeWidth=0.6,
                strokeDashArray=[2, 2],
            )
        )

    y = top - head_h - 6
    for step, h in zip(steps, heights, strict=True):
        y -= h
        if isinstance(step, Msg):
            color = {"call": INK, "reply": MUTED, "blocked": DANGER, "proxy": PROXY_EDGE}[step.kind]
            x1, x2 = xs[step.src], xs[step.dst]
            if x1 == x2:  # message to self: a note beside the lifeline, sized to its text
                tw = pdfmetrics.stringWidth(step.text, "Body", 6.6) + 8
                bx = x1 + 4 if x1 + 4 + tw <= width - 2 else x1 - 4 - tw
                d.add(
                    Rect(bx, y + 2, tw, row - 5, fillColor=colors.white, strokeColor=color, strokeWidth=0.6)
                )
                label(d, bx + 4, y + 6.5, step.text, size=6.6, color=color)
            else:
                arrow(
                    d,
                    x1,
                    y + 4,
                    x2 + (-1 if x2 > x1 else 1),
                    y + 4,
                    step.text,
                    color=color,
                    dashed=step.kind == "reply",
                    label_dy=3,
                )
        elif isinstance(step, Note):
            keys = [xs[k] for k in step.over]
            left, right = min(keys) - gap * 0.42, max(keys) + gap * 0.42
            bg = {"note": NOTE_BG, "danger": DANGER_BG, "ok": colors.HexColor("#e6f4ea")}[step.kind]
            edge = {"note": colors.HexColor("#c9a227"), "danger": DANGER, "ok": OK}[step.kind]
            d.add(Rect(left, y + 1, right - left, row + 1, fillColor=bg, strokeColor=edge, strokeWidth=0.6))
            d.add(
                String(
                    (left + right) / 2,
                    y + 7,
                    step.text,
                    fontName="Body",
                    fontSize=6.8,
                    fillColor=INK,
                    textAnchor="middle",
                )
            )
        else:
            d.add(Line(4, y + 7, width - 4, y + 7, strokeColor=RULE, strokeWidth=0.6))
            d.add(
                Rect(
                    width / 2 - 95, y + 1, 190, 12, fillColor=colors.white, strokeColor=RULE, strokeWidth=0.6
                )
            )
            d.add(
                String(
                    width / 2,
                    y + 4,
                    step.text,
                    fontName="Body-Bold",
                    fontSize=6.8,
                    fillColor=MUTED,
                    textAnchor="middle",
                )
            )
    return d


# ---------------------------------------------------------------------------
# Document template with header, footer and table of contents
# ---------------------------------------------------------------------------
class Heading(Paragraph):
    """A heading that registers itself in the table of contents."""

    def __init__(self, text: str, level: int) -> None:
        style = {0: H1, 1: H2, 2: H3}[level]
        super().__init__(md(text), style)
        self.toc_level = level
        self.toc_text = re.sub(r"[`*]", "", text)


class GuideDoc(BaseDocTemplate):
    def __init__(self, filename: str, title: str, version: str) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN + 6,
            bottomMargin=MARGIN,
            title=title,
            author="Puneet Shetty",
            subject="Ledgerline architecture and flow guide",
        )
        self.version = version
        frame = Frame(
            MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN - 6, id="body", leftPadding=0, rightPadding=0
        )
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[frame], onPage=lambda c, d: None),
                PageTemplate(id="page", frames=[frame], onPage=self._decorate),
            ]
        )

    def _decorate(self, canvas, doc) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 4, "Ledgerline — how it works, phase by phase")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 4, f"v{self.version}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - MARGIN + 1, PAGE_W - MARGIN, PAGE_H - MARGIN + 1)
        canvas.drawCentredString(PAGE_W / 2, MARGIN - 18, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Heading) and flowable.toc_level < 2:
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.toc_text, key, level=flowable.toc_level)
            self.notify("TOCEntry", (flowable.toc_level, flowable.toc_text, self.page, key))


def make_toc() -> TableOfContents:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName="Body-Bold", fontSize=10, leading=15, leftIndent=0, textColor=INK),
        ParagraphStyle("toc1", fontName="Body", fontSize=8.8, leading=12, leftIndent=14, textColor=MUTED),
    ]
    toc.dotsMinLevel = 0
    return toc
