#!/usr/bin/env python3
"""
compare.py — diff two style-drift snapshots and render BEFORE/AFTER report.

Usage:
  compare.py <before.json> <after.json>                    # text report to stdout
  compare.py <before.json> <after.json> --pdf <output.pdf> # also render PDF

The PDF report reuses extract-toolkit's PreviewCanvas DSL so the visual
mocks look the same as the toolkit doc.
"""
import json
import sys
from pathlib import Path
from typing import Optional


GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─── Delta helpers ──────────────────────────────────────────────────────────
def _delta(before: int, after: int) -> str:
    """Format an absolute delta with color (down = green, up = red)."""
    if before == after:
        return f"  ={DIM}0{RESET}"
    d = after - before
    if d < 0:
        return f"  {GREEN}{d:+d}{RESET}"
    return f"  {RED}{d:+d}{RESET}"


def _arrow(before: int, after: int, name: str) -> str:
    return f"  {BOLD}{name:30s}{RESET}  {before:5d}  →  {after:5d}{_delta(before, after)}"


def diff_deviations(before: dict, after: dict) -> list[tuple[str, int, int, int]]:
    """Return list of (key, before_count, after_count, file_count_delta)."""
    rows = []
    devs_before = before.get("deviations", {})
    devs_after  = after.get("deviations", {})
    for key in sorted(set(devs_before) | set(devs_after)):
        bf = devs_before.get(key, {})
        af = devs_after.get(key, {})
        bf_total = bf.get("total_hits", bf.get("file_count", 0))
        af_total = af.get("total_hits", af.get("file_count", 0))
        rows.append((key, bf_total, af_total, af.get("file_count", 0) - bf.get("file_count", 0)))
    return rows


def diff_primitive_adoption(before: dict, after: dict) -> list[tuple[str, int, int]]:
    rows = []
    bf = before.get("primitive_adoption", {})
    af = after.get("primitive_adoption", {})
    for name in sorted(set(bf) | set(af)):
        rows.append((name, bf.get(name, 0), af.get(name, 0)))
    return rows


def diff_good_news(before: dict, after: dict) -> list[tuple[str, int, int]]:
    rows = []
    bf = before.get("good_news", {})
    af = after.get("good_news", {})
    for key in sorted(set(bf) | set(af)):
        rows.append((key, bf.get(key, 0), af.get(key, 0)))
    return rows


def file_set_diff(before: dict, after: dict, dev_key: str) -> tuple[list[str], list[str]]:
    """Return (resolved_files, new_files) — files in BEFORE but not AFTER, and vice versa."""
    bf = set((before.get("deviations", {}).get(dev_key) or {}).get("files", []))
    af = set((after.get("deviations", {}).get(dev_key) or {}).get("files", []))
    return sorted(bf - af), sorted(af - bf)


# ─── Text report ────────────────────────────────────────────────────────────
def render_text(before: dict, after: dict) -> str:
    lines = []
    b_meta = before.get("toolkit") or {}
    a_meta = after.get("toolkit") or {}
    bv = b_meta.get("version") or "?"
    av = a_meta.get("version") or "?"

    lines.append("")
    lines.append(f"{BOLD}== Style-drift BEFORE → AFTER =={RESET}")
    lines.append(f"  Layout:   {after.get('layout', '?')}")
    lines.append(f"  Toolkit:  {bv}  →  {av}")
    lines.append(f"  BEFORE @ {before.get('timestamp', '?')}")
    lines.append(f"  AFTER  @ {after.get('timestamp', '?')}")
    lines.append("")

    lines.append(f"{BOLD}Deviations (total hits){RESET}")
    for key, bf, af, _ in diff_deviations(before, after):
        lines.append(_arrow(bf, af, key))
    lines.append("")

    primitives = diff_primitive_adoption(before, after)
    if primitives:
        lines.append(f"{BOLD}Primitive adoption (import count){RESET}")
        for name, bf, af in primitives:
            lines.append(_arrow(bf, af, name))
        lines.append("")

    good = diff_good_news(before, after)
    if good:
        lines.append(f"{BOLD}Good-news metrics{RESET}")
        for k, bf, af in good:
            # For good-news metrics, up = green (more adoption is good)
            if af > bf:
                col = GREEN
            elif af < bf:
                col = RED
            else:
                col = DIM
            d = af - bf
            d_str = f"  {col}{d:+d}{RESET}" if d != 0 else f"  {DIM}0{RESET}"
            lines.append(f"  {BOLD}{k:30s}{RESET}  {bf:5d}  →  {af:5d}{d_str}")
        lines.append("")

    # Top file movements per deviation
    for key, bf, af, _ in diff_deviations(before, after):
        if bf == af == 0:
            continue
        resolved, new = file_set_diff(before, after, key)
        if not resolved and not new:
            continue
        lines.append(f"{BOLD}{key}{RESET}")
        for f in resolved[:8]:
            lines.append(f"  {GREEN}- {f}{RESET}  (resolved)")
        if len(resolved) > 8:
            lines.append(f"  {DIM}  …and {len(resolved) - 8} more resolved{RESET}")
        for f in new[:8]:
            lines.append(f"  {RED}+ {f}{RESET}  (regression)")
        if len(new) > 8:
            lines.append(f"  {DIM}  …and {len(new) - 8} more new{RESET}")
        lines.append("")

    return "\n".join(lines)


# ─── PDF report ─────────────────────────────────────────────────────────────
def render_pdf(before: dict, after: dict, out_path: Path) -> None:
    sys.path.insert(0, str(Path.home() / ".claude/skills/extract-toolkit/scripts"))
    import build_toolkit as bt
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        BaseDocTemplate, Flowable, Frame, PageBreak, PageTemplate,
        Paragraph, Spacer, Table, TableStyle, NextPageTemplate,
    )

    GREEN_HEX = rl_colors.HexColor("#047857")
    RED_HEX   = rl_colors.HexColor("#B91C1C")
    GRAY_HEX  = rl_colors.HexColor("#94A3B8")

    styles_ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=22, leading=28,
        spaceAfter=8, textColor=bt.SLATE_900)
    H2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=14, leading=18,
        spaceBefore=14, spaceAfter=4, textColor=bt.SLATE_900)
    BODY = ParagraphStyle("Body", parent=styles_ss["BodyText"], fontName="Helvetica",
        fontSize=10, leading=14, spaceAfter=4, textColor=bt.SLATE_700)
    SMALL = ParagraphStyle("Small", parent=styles_ss["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=bt.SLATE_500)
    CODE = ParagraphStyle("Code", parent=styles_ss["Code"], fontName="Courier",
        fontSize=8, leading=11, leftIndent=6, rightIndent=6,
        textColor=bt.SLATE_900, backColor=bt.SLATE_50, borderPadding=5,
        borderColor=bt.SLATE_200, borderWidth=0.5, spaceAfter=4)
    COVER_TITLE = ParagraphStyle("CT", fontName="Helvetica-Bold",
        fontSize=30, leading=36, textColor=bt.SLATE_900)
    COVER_SUB = ParagraphStyle("CS", fontName="Helvetica",
        fontSize=13, leading=18, textColor=bt.SLATE_500)

    class ReportDoc(BaseDocTemplate):
        def __init__(self, fn, **kw):
            BaseDocTemplate.__init__(self, fn, **kw)
            frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            self.addPageTemplates([
                PageTemplate(id="cover", frames=[frame], onPage=self._cover),
                PageTemplate(id="body",  frames=[frame], onPage=self._body),
            ])
        def _cover(self, c, doc):
            c.saveState()
            c.setFillColor(bt.ZINC_50); c.rect(0, 0, LETTER[0], LETTER[1], stroke=0, fill=1)
            c.setFillColor(bt.INDIGO);  c.rect(0, LETTER[1] - 1.6 * inch, 0.45 * inch, 1.6 * inch, stroke=0, fill=1)
            c.restoreState()
        def _body(self, c, doc):
            c.saveState()
            c.setStrokeColor(bt.SLATE_200); c.setLineWidth(0.4)
            c.line(doc.leftMargin, LETTER[1] - 0.55 * inch,
                   LETTER[0] - doc.rightMargin, LETTER[1] - 0.55 * inch)
            c.setFont("Helvetica", 8.5); c.setFillColor(bt.SLATE_500)
            c.drawString(doc.leftMargin, LETTER[1] - 0.42 * inch, "Style-drift · BEFORE → AFTER")
            bf_v = (before.get("toolkit") or {}).get("version") or "?"
            af_v = (after.get("toolkit")  or {}).get("version") or "?"
            c.drawRightString(LETTER[0] - doc.rightMargin, LETTER[1] - 0.42 * inch,
                              f"{bf_v} → {af_v}")
            c.setFont("Helvetica", 8); c.setFillColor(bt.SLATE_400)
            c.drawString(doc.leftMargin, 0.4 * inch, "auto-generated by compare.py")
            c.drawRightString(LETTER[0] - doc.rightMargin, 0.4 * inch, f"{doc.page}")
            c.restoreState()

    def _bar(c, x, y, w, h, fraction, fill_color):
        c.setFillColor(bt.SLATE_100)
        c.roundRect(x, y, w, h, 2, stroke=0, fill=1)
        if fraction > 0:
            c.setFillColor(fill_color)
            c.roundRect(x, y, max(2, w * min(1.0, fraction)), h, 2, stroke=0, fill=1)

    class DeviationBars(Flowable):
        def __init__(self, rows, width=6.5 * inch):
            Flowable.__init__(self)
            self.rows = rows
            self.width = width
            row_h = 22
            self.height = row_h * len(rows) + 8
            self.row_h = row_h
            self.max_value = max((max(b, a) for _, b, a, _ in rows), default=1) or 1

        def wrap(self, aw, ah):
            self.width = aw
            return (aw, self.height)

        def draw(self):
            c = self.canv
            label_w = 1.7 * inch
            counts_w = 1.0 * inch
            bar_area = self.width - label_w - counts_w - 12
            for i, (key, bf, af, _) in enumerate(self.rows):
                y = self.height - 4 - (i + 1) * self.row_h
                c.setFillColor(bt.SLATE_700); c.setFont("Helvetica", 9)
                c.drawString(0, y + 6, key.replace("_", " "))
                # before bar (red)
                _bar(c, label_w, y + 11, bar_area, 5, bf / self.max_value, RED_HEX)
                # after bar (green) below
                _bar(c, label_w, y + 4,  bar_area, 5, af / self.max_value, GREEN_HEX)
                # counts
                c.setFont("Helvetica", 8.5); c.setFillColor(RED_HEX)
                c.drawString(label_w + bar_area + 8, y + 11, f"{bf:>4d}")
                c.setFillColor(GREEN_HEX)
                c.drawString(label_w + bar_area + 8, y + 4,  f"{af:>4d}")
                # delta
                d = af - bf
                if d == 0:
                    c.setFillColor(GRAY_HEX); s = "  ±0"
                elif d < 0:
                    c.setFillColor(GREEN_HEX); s = f" {d:+d}"
                else:
                    c.setFillColor(RED_HEX); s = f" {d:+d}"
                c.setFont("Helvetica-Bold", 8.5)
                c.drawString(label_w + bar_area + 40, y + 8, s)

    class AdoptionGrid(Flowable):
        def __init__(self, rows, width=6.5 * inch):
            Flowable.__init__(self)
            self.rows = rows
            self.width = width
            row_h = 18
            self.height = row_h * len(rows) + 8
            self.row_h = row_h
            self.max_value = max((max(b, a) for _, b, a in rows), default=1) or 1

        def wrap(self, aw, ah):
            self.width = aw
            return (aw, self.height)

        def draw(self):
            c = self.canv
            label_w = 1.5 * inch
            counts_w = 1.0 * inch
            bar_area = self.width - label_w - counts_w - 12
            for i, (name, bf, af) in enumerate(self.rows):
                y = self.height - 4 - (i + 1) * self.row_h
                c.setFillColor(bt.SLATE_700); c.setFont("Helvetica-Bold", 9)
                c.drawString(0, y + 4, name)
                # background bar
                c.setFillColor(bt.SLATE_100)
                c.roundRect(label_w, y + 4, bar_area, 8, 2, stroke=0, fill=1)
                # after (overlays)
                fill_color = bt.INDIGO if af > 0 else GRAY_HEX
                c.setFillColor(fill_color)
                if af > 0:
                    c.roundRect(label_w, y + 4, max(2, bar_area * (af / self.max_value)), 8, 2, stroke=0, fill=1)
                # before tick (vertical line at the bf position)
                if bf > 0:
                    bx = label_w + bar_area * (bf / self.max_value)
                    c.setStrokeColor(bt.SLATE_500); c.setLineWidth(0.8)
                    c.line(bx, y + 2, bx, y + 14)
                # counts
                d = af - bf
                if d > 0:
                    col = GREEN_HEX; s = f"+{d}"
                elif d < 0:
                    col = RED_HEX; s = f"{d}"
                else:
                    col = GRAY_HEX; s = "±0"
                c.setFont("Helvetica", 8); c.setFillColor(bt.SLATE_500)
                c.drawString(label_w + bar_area + 8, y + 5, f"{bf} → {af}")
                c.setFont("Helvetica-Bold", 8); c.setFillColor(col)
                c.drawString(label_w + bar_area + 44, y + 5, s)

    # ── Build story ─────────────────────────────────────────────────────────
    bf_meta = before.get("toolkit") or {}
    af_meta = after.get("toolkit") or {}
    bv = bf_meta.get("version") or "?"
    av = af_meta.get("version") or "?"

    story = []

    # COVER
    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph("Style-Drift", COVER_SUB))
    story.append(Spacer(1, 6))
    story.append(Paragraph("BEFORE &amp; AFTER", COVER_TITLE))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"Auto-generated delta report comparing two style-drift snapshots. "
        f"Toolkit: <b>{bv}</b> → <b>{av}</b>. "
        f"Layout: {after.get('layout','?')}.",
        COVER_SUB))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"<font color='#94A3B8'>BEFORE captured {before.get('timestamp','?')} · "
        f"AFTER captured {after.get('timestamp','?')}</font>", SMALL))
    story.append(Spacer(1, 0.7 * inch))

    # Top-line numbers
    rows = diff_deviations(before, after)
    total_bf = sum(b for _, b, _, _ in rows)
    total_af = sum(a for _, _, a, _ in rows)
    net = total_af - total_bf
    summary_cells = [
        ["", "Before", "After", "Δ"],
        ["Total deviation hits",          f"{total_bf}", f"{total_af}",
         f"{net:+d}" if net != 0 else "0"],
    ]
    pa = diff_primitive_adoption(before, after)
    if pa:
        pa_bf = sum(b for _, b, _ in pa)
        pa_af = sum(a for _, _, a in pa)
        d = pa_af - pa_bf
        summary_cells.append(["Primitive imports (total)", f"{pa_bf}", f"{pa_af}",
                              f"{d:+d}" if d != 0 else "0"])
    t = Table(summary_cells, colWidths=[2.6 * inch, 1.1 * inch, 1.1 * inch, 0.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), bt.SLATE_100),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("FONT", (-1, 1), (-1, -1), "Helvetica-Bold", 10),
        ("TEXTCOLOR", (1, 1), (1, -1), RED_HEX),
        ("TEXTCOLOR", (2, 1), (2, -1), GREEN_HEX),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, bt.SLATE_400),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, bt.SLATE_200),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t)
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # Deviations bar chart
    story.append(Paragraph("Deviation hits — BEFORE vs AFTER", H1))
    story.append(Paragraph(
        "<font color='#B91C1C'><b>Red bar</b></font> = BEFORE total hits, "
        "<font color='#047857'><b>green bar</b></font> = AFTER total hits, "
        "scaled to the largest single metric.",
        BODY))
    story.append(Spacer(1, 6))
    story.append(DeviationBars(rows))
    story.append(Spacer(1, 14))

    # Per-class detail (resolved + new)
    story.append(Paragraph("Per-class file movement", H1))
    for key, bf, af, _ in rows:
        if bf == af == 0:
            continue
        resolved, new = file_set_diff(before, after, key)
        if not resolved and not new:
            continue
        story.append(Paragraph(key.replace("_", " "), H2))
        if resolved:
            story.append(Paragraph(
                f"<font color='#047857'><b>Resolved ({len(resolved)})</b></font>", BODY))
            for f in resolved[:10]:
                story.append(Paragraph(
                    f"<font face='Courier' color='#047857'>− {f}</font>", SMALL))
            if len(resolved) > 10:
                story.append(Paragraph(
                    f"<font color='#94A3B8'>…and {len(resolved) - 10} more</font>", SMALL))
        if new:
            story.append(Paragraph(
                f"<font color='#B91C1C'><b>Regressions ({len(new)})</b></font>", BODY))
            for f in new[:10]:
                story.append(Paragraph(
                    f"<font face='Courier' color='#B91C1C'>+ {f}</font>", SMALL))
            if len(new) > 10:
                story.append(Paragraph(
                    f"<font color='#94A3B8'>…and {len(new) - 10} more</font>", SMALL))
        story.append(Spacer(1, 6))

    # Primitive adoption
    if pa:
        story.append(PageBreak())
        story.append(Paragraph("Primitive adoption — BEFORE → AFTER", H1))
        story.append(Paragraph(
            "Per-primitive count of files importing it from "
            "<font face='Courier'>@/components/ui/&lt;name&gt;</font>. "
            "Solid bar = AFTER value, tick mark = BEFORE position.",
            BODY))
        story.append(Spacer(1, 6))
        story.append(AdoptionGrid(pa))

    # Good-news metrics
    good = diff_good_news(before, after)
    if good:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Good-news metrics", H2))
        gn_cells = [["Metric", "Before", "After", "Δ"]]
        for k, bf, af in good:
            d = af - bf
            d_str = f"{d:+d}" if d != 0 else "0"
            gn_cells.append([k.replace("_", " "), str(bf), str(af), d_str])
        gt = Table(gn_cells, colWidths=[2.8 * inch, 1.0 * inch, 1.0 * inch, 0.7 * inch])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), bt.SLATE_100),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, bt.SLATE_400),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, bt.SLATE_200),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(gt)

    # Build
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = ReportDoc(str(out_path), pagesize=LETTER,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.85 * inch, bottomMargin=0.7 * inch,
        title="Style-drift · BEFORE → AFTER")
    doc.build(story)


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__.strip(), file=sys.stderr); sys.exit(2)
    before_path = Path(args[0])
    after_path  = Path(args[1])
    pdf_path: Optional[Path] = None
    i = 2
    while i < len(args):
        if args[i] == "--pdf":
            pdf_path = Path(args[i + 1]); i += 2
        else:
            print(f"Unknown flag: {args[i]}", file=sys.stderr); sys.exit(2)

    before = json.loads(before_path.read_text())
    after  = json.loads(after_path.read_text())

    print(render_text(before, after))
    if pdf_path:
        render_pdf(before, after, pdf_path)
        size = pdf_path.stat().st_size
        print(f"\nPDF: {pdf_path}  ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
