# src/plugins/chatbot/time_utils.py
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def today_start_utc() -> datetime:
    now_ist = datetime.now(IST)
    start_ist = datetime(year=now_ist.year, month=now_ist.month, day=now_ist.day, tzinfo=IST)
    return start_ist.astimezone(timezone.utc)

def yesterday_bounds_utc():
    now_ist = datetime.now(IST)
    today_ist = datetime(year=now_ist.year, month=now_ist.month, day=now_ist.day, tzinfo=IST)
    y_start = (today_ist - timedelta(days=1)).astimezone(timezone.utc)
    y_end = today_ist.astimezone(timezone.utc)
    return y_start, y_end

def this_week_start_utc():
    now_ist = datetime.now(IST)
    # Monday as start-of-week; adjust if you prefer Sunday
    week_start_ist = (now_ist - timedelta(days=now_ist.weekday()))
    week_start_ist = datetime(week_start_ist.year, week_start_ist.month, week_start_ist.day, tzinfo=IST)
    return week_start_ist.astimezone(timezone.utc)

def last_week_bounds_utc():
    this_week_utc = this_week_start_utc()
    last_week_start_utc = this_week_utc - timedelta(days=7)
    return last_week_start_utc, this_week_utc

def this_month_start_utc():
    now_ist = datetime.now(IST)
    mstart_ist = datetime(now_ist.year, now_ist.month, 1, tzinfo=IST)
    return mstart_ist.astimezone(timezone.utc)

def last_month_bounds_utc():
    now_ist = datetime.now(IST)
    first_day_ist = datetime(now_ist.year, now_ist.month, 1, tzinfo=IST)
    # previous month
    if first_day_ist.month == 1:
        prev = datetime(first_day_ist.year-1, 12, 1, tzinfo=IST)
    else:
        prev = datetime(first_day_ist.year, first_day_ist.month-1, 1, tzinfo=IST)
    return prev.astimezone(timezone.utc), first_day_ist.astimezone(timezone.utc)