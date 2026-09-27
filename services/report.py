"""Self-contained monthly HTML report generator (inline CSS/SVG, no CDN, no network)."""
import calendar
import datetime as dt
from decimal import Decimal
from pathlib import Path

import db
from services import enhancements


def _bar_svg(daily: list[dict], width: int = 560, height: int = 160) -> str:
    """Render a simple inline SVG bar chart of daily expenses."""
    if not daily:
        return "<svg></svg>"
    values = [float(d["expense"]) for d in daily]
    max_v = max(values) or 1.0
    bar_w = width / max(len(values), 1)
    bars = []
    for i, v in enumerate(values):
        h = (v / max_v) * (height - 20)
        x = i * bar_w + 2
        y = height - h
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 4:.1f}" height="{h:.1f}" fill="#EF5350" />')
    return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def _pie_svg(cats: list[dict], size: int = 220) -> str:
    """Render a simple inline SVG pie chart of category expense totals."""
    total = sum((c["total"] for c in cats), Decimal("0.00"))
    if not cats or total == 0:
        return f'<svg width="{size}" height="{size}"><circle cx="{size/2}" cy="{size/2}" r="{size/2-4}" fill="#E0E0E0"/></svg>'
    cx, cy, r = size / 2, size / 2, size / 2 - 4
    import math

    start_angle = 0.0
    paths = []
    for c in cats:
        frac = float(c["total"] / total)
        end_angle = start_angle + frac * 360
        x1 = cx + r * math.cos(math.radians(start_angle))
        y1 = cy + r * math.sin(math.radians(start_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        large_arc = 1 if (end_angle - start_angle) > 180 else 0
        color = c.get("color") or "#9E9E9E"
        paths.append(
            f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large_arc} 1 {x2:.1f},{y2:.1f} Z" fill="{color}" />'
        )
        start_angle = end_angle
    return f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">{"".join(paths)}</svg>'


def build_report(year: int | None = None, month: int | None = None) -> str:
    """Build a self-contained monthly HTML report and return its file path."""
    today = dt.date.today()
    year = year or today.year
    month = month or today.month
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"

    totals = db.month_totals(year, month)
    cats = db.category_totals(start, end)
    daily = db.daily_totals(start, end)
    txns = db.list_transactions(start, end)
    month_label = dt.date(year, month, 1).strftime("%B %Y")

    rows_html = "".join(
        f"<tr><td>{t['date']}</td><td>{t.get('category_name') or ''}</td>"
        f"<td>{t.get('account_name') or ''}</td><td>{t['type']}</td>"
        f"<td style='text-align:right'>{enhancements.inr(t['amount'])}</td>"
        f"<td>{t.get('note') or ''}</td></tr>"
        for t in txns
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MyMoney Report — {month_label}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
h1 {{ margin-bottom: 4px; }}
.stats {{ display: flex; gap: 16px; margin: 16px 0; }}
.card {{ flex: 1; border: 1px solid #ddd; border-radius: 10px; padding: 12px; text-align: center; }}
.card .label {{ font-size: 11px; color: #777; }}
.card .value {{ font-size: 20px; font-weight: bold; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #eee; font-size: 13px; text-align: left; }}
.charts {{ display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }}
</style></head>
<body>
<h1>MyMoney Report</h1>
<p>{month_label}</p>
<div class="stats">
  <div class="card"><div class="label">EXPENSE</div><div class="value" style="color:#EF5350">{enhancements.inr(totals['expense'])}</div></div>
  <div class="card"><div class="label">INCOME</div><div class="value" style="color:#26A69A">{enhancements.inr(totals['income'])}</div></div>
  <div class="card"><div class="label">TOTAL</div><div class="value">{enhancements.inr(totals['total'])}</div></div>
</div>
<div class="charts">
  {_pie_svg(cats)}
  {_bar_svg(daily)}
</div>
<h2>Transactions</h2>
<table>
<tr><th>Date</th><th>Category</th><th>Account</th><th>Type</th><th>Amount</th><th>Note</th></tr>
{rows_html}
</table>
</body></html>"""

    out_dir = Path(db.DB_PATH).parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"mymoney_report_{year:04d}_{month:02d}.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


if __name__ == "__main__":
    import tempfile

    path = build_report(2024, 1)
    assert Path(path).exists()
    print("OK")