"""CSV, PNG (matplotlib) and PDF (reportlab) exports built from a stored analysis document."""
import csv
import io
import unicodedata
from collections import OrderedDict
from threading import Lock
from xml.sax.saxutils import escape

from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.figure import Figure

from .text import ordinal

YEARLY_COLS = ["year", "events", "heatwave_days", "max_duration", "mean_duration", "mean_intensity", "max_peak", "hot_days", "mean_tmax", "coverage", "usable"]
EVENT_COLS = ["start", "end", "year", "duration", "peak_temp", "mean_temp", "intensity", "severity"]
HEAT = LinearSegmentedColormap.from_list("heat", ["#ffd27a", "#ffa23a", "#ff6a2b", "#e5243b", "#8f0b3a"])


def _csv(rows, cols) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])  # numeric / ISO-date values only
    return buf.getvalue()


def yearly_csv(doc) -> str:
    return _csv(doc["yearly"], YEARLY_COLS)


def events_csv(doc) -> str:
    return _csv(doc["events"], EVENT_COLS)


class _LRU:
    def __init__(self, size=32):
        self.size, self.d, self.lock = size, OrderedDict(), Lock()

    def get(self, k):
        with self.lock:
            if k in self.d:
                self.d.move_to_end(k)
                return self.d[k]

    def put(self, k, v):
        with self.lock:
            self.d[k] = v
            self.d.move_to_end(k)
            while len(self.d) > self.size:
                self.d.popitem(last=False)


_cache = _LRU()


def render_plot(doc, metric="heatwave_days", theme="dark", size=(9.0, 4.2)) -> bytes:
    ck = ("png", doc["key"], metric, theme, size)
    hit = _cache.get(ck)
    if hit:
        return hit
    dark = theme == "dark"
    bg, fg, grid = ("#0a0a0f", "#e9e4dc", "#2a2a33") if dark else ("#ffffff", "#222222", "#dddddd")
    m = doc["trends"]["metrics"][metric]
    years = doc["trends"]["years"]
    fig = Figure(figsize=size, dpi=140, facecolor=bg)
    ax = fig.add_subplot(111, facecolor=bg)
    if m.get("available"):
        vals = [0 if v is None else v for v in m["series"]]
        norm = Normalize(min(vals), max(vals) if max(vals) > min(vals) else min(vals) + 1)
        ax.bar(years, vals, color=[HEAT(norm(v)) for v in vals], width=0.75, zorder=2)
        roll = [float("nan") if v is None else v for v in m["rolling"]]
        ax.plot(years, roll, color="#56b6ff", lw=2.2, label=f"{doc['trends']['rolling_window']}-yr rolling mean", zorder=3)
        mk = m["mann_kendall"]
        p_txt = "p < 0.001" if mk["p_value"] < 0.001 else f"p = {mk['p_value']:.3f}"
        ax.plot(years, m["fit"], color=fg, lw=1.4, ls="--", label=f"Linear fit ({m['linear']['slope_per_decade']:+.2f}/decade); Mann-Kendall {p_txt}", zorder=3)
        ax.legend(frameon=False, labelcolor=fg, fontsize=8, loc="upper left")
    else:
        ax.text(0.5, 0.5, m.get("reason", "No data"), ha="center", va="center", color=fg, transform=ax.transAxes)
    ax.set_title(f"{m['label']} per year", color=fg, fontsize=11, loc="left")
    ax.set_ylabel(m["unit"], color=fg, fontsize=9)
    ax.tick_params(colors=fg, labelsize=8)
    ax.grid(axis="y", color=grid, lw=0.6, zorder=0)
    for s in ax.spines.values():
        s.set_color(grid)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg)
    data = buf.getvalue()
    _cache.put(ck, data)
    return data


def _safe(text) -> str:
    """Built-in PDF fonts only cover Latin-1; fold anything else to ASCII."""
    s = str(text).replace("≥", ">=").replace("→", "to").replace("—", "-").replace("–", "-")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _robustness_table(rob, colors, Table, TableStyle):
    """Grid of percentile x minimum days, one coloured cell per definition tested."""
    tones = {"up": "#fde6e2", "down": "#e1ecfb", "flat": "#f1f4f7", "na": "#ffffff"}
    cells = {(c["percentile"], c["min_days"]): c for c in rob["cells"]}
    rows = [["Hot day is above the"] + [f"{d}+ days in a row" for d in rob["min_days"]]]
    styles = [("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a1330")),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
              ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for r, p in enumerate(rob["percentiles"], start=1):
        row = [f"{ordinal(p)} percentile"]
        for c_i, d in enumerate(rob["min_days"], start=1):
            c = cells.get((p, d))
            if not c or not c["available"]:
                text, tone = "not enough years", "na"
            else:
                tone = "up" if c["trend"] == "increasing" else "down" if c["trend"] == "decreasing" else "flat"
                text = f"{c['sen_per_decade']:+.1f} ({'sig.' if c['significant'] else 'n.s.'}){' *' if c['few_events'] else ''}"
            if c and c["current"]:
                text += " yours"
                styles.append(("BOX", (c_i, r), (c_i, r), 1.2, colors.HexColor("#0a1330")))
            row.append(text)
            styles.append(("BACKGROUND", (c_i, r), (c_i, r), colors.HexColor(tones[tone])))
        rows.append(row)
    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle(styles))
    return t


def render_pdf(doc) -> bytes:
    ck = ("pdf", doc["key"], doc["region"].get("name"))
    hit = _cache.get(ck)
    if hit:
        return hit
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4, keepWithNext=1)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#555555"))
    p = doc["params"]
    name = _safe(doc["region"].get("name") or "Selected region")
    hl = doc["insights"]["headline"]

    out = io.BytesIO()
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Heatwave trend report", author="Heatline")
    st = [Paragraph("Heatwave trend report", h1),
          Paragraph(escape(f"{name}  |  {p['start_year']}-{p['end_year']}  |  {ordinal(p['percentile'])} percentile, {p['min_days']}+ days, {doc['threshold']['method']} threshold"), small),
          Spacer(1, 8), Paragraph("Key finding", h2), Paragraph(escape(_safe(hl["text"])), body), Paragraph("Insights", h2)]
    for b in doc["insights"]["bullets"]:
        st.append(Paragraph("- " + escape(_safe(b)), body))
    for metric in ("heatwave_days", "events"):
        st.append(Spacer(1, 6))
        st.append(Image(io.BytesIO(render_plot(doc, metric, theme="light", size=(8.2, 3.4))), width=174 * mm, height=72 * mm))
    rob = doc.get("robustness")
    if rob and rob.get("cells"):
        st.append(Paragraph("Does the definition change the answer?", h2))
        st.append(Paragraph(escape(_safe(rob["summary"]["text"])), body))
        st.append(Spacer(1, 4))
        st.append(_robustness_table(rob, colors, Table, TableStyle))
        st.append(Paragraph("Each cell is the Sen's slope of heatwave days per year, per decade. sig. means the Mann-Kendall test gives p < 0.05, "
                            "n.s. means it does not. * means fewer than 10 events, so the estimate is fragile. "
                            "'yours' is the setting used for this report.", small))
    st.append(Paragraph("Caveats", h2))
    for c in doc["insights"]["caveats"]:
        st.append(Paragraph("- " + escape(_safe(c)), small))
    st.append(Paragraph("Yearly summary", h2))
    rows = [["Year", "Events", "HW days", "Longest", "Intensity", "Peak C", "Valid data"]]
    for r in doc["yearly"]:
        rows.append([r["year"], r["events"], r["heatwave_days"], r["max_duration"],
                     "-" if r["mean_intensity"] is None else f"{r['mean_intensity']:.1f}",
                     "-" if r["max_peak"] is None else f"{r['max_peak']:.1f}", f"{r['coverage'] * 100:.0f}%"])
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ff6a2b")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f2ec")])]))
    st.append(t)
    st.append(Spacer(1, 8))
    st.append(Paragraph(escape(_safe(f"Source: {doc['meta']['source']}. Generated {doc['meta']['computed_at']}.")), small))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    pdf.build(st, onFirstPage=footer, onLaterPages=footer)
    data = out.getvalue()
    _cache.put(ck, data)
    return data