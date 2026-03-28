from datetime import date, datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))


def now_iso():
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def today_str():
    return date.today().isoformat()
