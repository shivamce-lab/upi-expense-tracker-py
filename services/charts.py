"""Pure chart-building functions. Data comes only from db.py helpers, never raw SQL."""
import calendar
import datetime as dt
from decimal import Decimal


import flet as ft
import flet_charts as fch


import db




def _empty_bar(height: int = 220) -> fch.BarChart:
    """A flat placeholder bar chart used when there is no data."""
    return fch.BarChart(
        groups=[fch.BarChartGroup(x=0, rods=[fch.BarChartRod(from_y=0, to_y=1, width=20, color=ft.Colors.GREY_300)])],
        max_y=1,
        height=height,
        interactive=False,
    )




def weekly_bar(start_date: str | None = None) -> fch.BarChart:
    """Sun-to-Sat expense bar chart for the week containing start_date (default today)."""
    if start_date is None:
        base = dt.date.today()
    else:
        base = dt.date.fromisoformat(start_date)
    sunday = base - dt.timedelta(days=(base.weekday() + 1) % 7)
    days = [sunday + dt.timedelta(days=i) for i in range(7)]
    labels = ["S", "M", "T", "W", "T", "F", "S"]


    daily = db.daily_totals(days[0].isoformat(), days[-1].isoformat())
    by_date = {d["date"]: d["expense"] for d in daily}


    values = [float(by_date.get(day.isoformat(), Decimal("0.00"))) for day in days]
    if all(v == 0 for v in values):
        return _empty_bar()


    max_val = max(values)
    max_y = max_val * 1.2 if max_val > 0 else 10


    groups = []
    for i, v in enumerate(values):
        groups.append(
            fch.BarChartGroup(
                x=i,
                rods=[
                    fch.BarChartRod(
                        from_y=0,
                        to_y=v,
                        width=18,
                        color=ft.Colors.BLUE_400,
                        border_radius=4,
                    )
                ],
            )
        )


    return fch.BarChart(
        groups=groups,
        max_y=max_y,
        height=220,
        interactive=True,
        bottom_axis=fch.ChartAxis(
            labels=[fch.ChartAxisLabel(value=i, label=ft.Text(labels[i], size=11)) for i in range(7)],
            label_size=20,
        ),
        left_axis=fch.ChartAxis(label_size=40),
    )




def monthly_line(year: int | None = None, month: int | None = None) -> fch.LineChart:
    """Curved blue line chart with one point per day of the given month (default current)."""
    today = dt.date.today()
    year = year or today.year
    month = month or today.month
    last_day = calendar.monthrange(year, month)[1]
    start = dt.date(year, month, 1).isoformat()
    end = dt.date(year, month, last_day).isoformat()


    daily = db.daily_totals(start, end)
    points = [fch.LineChartDataPoint(i + 1, float(d["expense"])) for i, d in enumerate(daily)]


    if not points or all(p.y == 0 for p in points):
        points = [fch.LineChartDataPoint(1, 0), fch.LineChartDataPoint(last_day, 0)]
        max_y = 10
    else:
        max_y = max(p.y for p in points) * 1.2 or 10


    data_series = [
        fch.LineChartData(
            points=points,
            stroke_width=3,
            color=ft.Colors.BLUE_400,
            curved=True,
            rounded_stroke_cap=True,
            below_line_bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.LIGHT_BLUE_200),
        )
    ]


    return fch.LineChart(
        data_series=data_series,
        min_y=0,
        max_y=max_y,
        min_x=1,
        max_x=last_day,
        height=220,
        left_axis=fch.ChartAxis(label_size=40),
        bottom_axis=fch.ChartAxis(label_size=20),
    )




def month_over_month() -> fch.BarChart:
    """Amber bar chart of the current month plus the 5 preceding months (6 bars total)."""
    today = dt.date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()


    values = []
    labels = []
    for y, m in months:
        totals = db.month_totals(y, m)
        values.append(float(totals["expense"]))
        labels.append(dt.date(y, m, 1).strftime("%b"))


    max_val = max(values) if values else 0
    max_y = max_val * 1.2 if max_val > 0 else 10


    groups = []
    for i, v in enumerate(values):
        groups.append(
            fch.BarChartGroup(
                x=i,
                rods=[
                    fch.BarChartRod(
                        from_y=0,
                        to_y=v,
                        width=22,
                        color=ft.Colors.AMBER_400,
                        border_radius=4,
                    )
                ],
            )
        )


    return fch.BarChart(
        groups=groups,
        max_y=max_y,
        height=220,
        interactive=True,
        bottom_axis=fch.ChartAxis(
            labels=[fch.ChartAxisLabel(value=i, label=ft.Text(labels[i], size=11)) for i in range(len(labels))],
            label_size=20,
        ),
        left_axis=fch.ChartAxis(label_size=40),
    )




def category_pie(start: str, end: str) -> fch.PieChart:
    """Pie chart of expense category totals in [start, end], with a center total label."""
    cats = db.category_totals(start, end)
    total = sum((c["total"] for c in cats), Decimal("0.00"))


    if not cats or total == 0:
        return fch.PieChart(
            sections=[fch.PieChartSection(value=1, color=ft.Colors.GREY_200, radius=60)],
            sections_space=2,
            center_space_radius=50,
            height=220,
        )


    sections = []
    for c in cats:
        pct = float(c["total"] / total) * 100 if total else 0
        sections.append(
            fch.PieChartSection(
                value=float(c["total"]),
                title=f"{pct:.0f}%",
                title_style=ft.TextStyle(size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                color=c["color"] or "#9E9E9E",
                radius=60,
            )
        )


    return fch.PieChart(
        sections=sections,
        sections_space=2,
        center_space_radius=50,
        height=220,
    )
