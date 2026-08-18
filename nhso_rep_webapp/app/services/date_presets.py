"""Pure date range helpers used by web settings and automation."""

import calendar
from datetime import date, timedelta


def month_range(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def previous_month_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    previous_last = today.replace(day=1) - timedelta(days=1)
    return month_range(previous_last.year, previous_last.month)


def current_fiscal_year_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return date(start_year, 10, 1), date(start_year + 1, 9, 30)


def build_date_presets(today: date | None = None) -> list[dict]:
    today = today or date.today()
    current_start, current_end = month_range(today.year, today.month)
    previous_start, previous_end = previous_month_range(today)
    fiscal_start, fiscal_end = current_fiscal_year_range(today)
    return [
        {
            "id": "current_month",
            "label": "เดือนนี้",
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
        },
        {
            "id": "previous_month",
            "label": "เดือนที่แล้ว",
            "start_date": previous_start.isoformat(),
            "end_date": previous_end.isoformat(),
        },
        {
            "id": "current_fiscal_year",
            "label": "ปีงบประมาณปัจจุบัน",
            "start_date": fiscal_start.isoformat(),
            "end_date": fiscal_end.isoformat(),
        },
    ]
