"""In-process daily report scheduler.

Started once by the dashboard server. A single background thread wakes
every 30 s, checks each TL's `report_time` / `report_timezone`, and fires
their Teams webhook at most once per local calendar day.

Design notes:
- Uses `zoneinfo` (Python 3.9+). Falls back to UTC if the configured tz
  can't be resolved.
- Dedup is DB-backed (`users.last_report_sent_on`) so restarts can't
  accidentally double-send.
- We tolerate a ±5 minute firing window (e.g. if the machine was asleep)
  so a configured 18:30 still fires at 18:33 after a wake.
- Only fires for `role='admin'` TLs. Super admin + developers are not
  report recipients in this design.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - stdlib in py3.9+
    ZoneInfo = None  # type: ignore[assignment]


_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Firing tolerance: if we were asleep and wake up 3 min late, still fire.
_WINDOW_MINUTES = 5
_POLL_SECONDS = 30


def _now_in_tz(tz_name: str) -> datetime:
    """Return the current wall-clock datetime in the given IANA tz."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name))
        except Exception:
            pass
    return datetime.utcnow()


def _parse_hhmm(value: str) -> Optional[tuple]:
    if not value:
        return None
    try:
        parts = value.strip().split(":")
        if len(parts) != 2:
            return None
        hh, mm = int(parts[0]), int(parts[1])
        if 0 <= hh < 24 and 0 <= mm < 60:
            return (hh, mm)
    except Exception:
        pass
    return None


def _should_fire(now_local: datetime, hhmm: tuple, last_sent: Optional[date]) -> bool:
    hh, mm = hhmm
    target = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    delta = (now_local - target).total_seconds() / 60.0
    # Within [0, WINDOW_MINUTES] minutes AFTER the target time
    if not (0 <= delta <= _WINDOW_MINUTES):
        return False
    # Not already sent today (local date)
    today_local = now_local.date()
    if last_sent == today_local:
        return False
    return True


def _send_report_for(db, tracker, notifier_mod, tl: dict,
                     dashboard_url: str) -> bool:
    """Build analytics, POST to Teams, mark success. Returns True on success."""
    email = tl["email"]
    tz_name = tl.get("report_timezone") or "Asia/Kolkata"
    now_local = _now_in_tz(tz_name)

    # Use a 1-day window (yesterday's activity through now) to mirror the
    # "daily report" semantics the existing CLI uses.
    summary = tracker.get_analytics_summary(
        viewer_email=email, viewer_role="admin", days=1
    )
    result = notifier_mod.send_team_report(
        webhook_url=tl.get("teams_webhook_url") or "",
        tl_name=tl.get("name") or email,
        tl_email=email,
        summary=summary,
        developer_stats=summary.get("developers", []),
        date_label=now_local.strftime("%A, %d %b %Y"),
        dashboard_url=dashboard_url,
    )
    if result.get("ok"):
        try:
            db.mark_report_sent(email, now_local.date())
        except Exception as e:
            print(f"[Scheduler] mark_report_sent failed for {email}: {e}")
        print(f"[Scheduler] Report sent to {email} (HTTP {result.get('status')})")
        return True
    print(f"[Scheduler] Report FAILED for {email}: HTTP {result.get('status')} — "
          f"{result.get('body')}")
    return False


def _tick(get_db, dashboard_url: str) -> None:
    """Single pass: check every enabled TL and fire if due."""
    try:
        from agent.analytics import get_tracker
        from agent.utils import teams_notifier
    except Exception as e:
        print(f"[Scheduler] import error: {e}")
        return
    try:
        db = get_db()
        tracker = get_tracker(db)
    except Exception as e:
        print(f"[Scheduler] could not acquire DB/tracker: {e}")
        return

    try:
        tls = db.get_tls_with_schedules()
    except Exception as e:
        print(f"[Scheduler] could not list TLs: {e}")
        return

    for tl in tls:
        hhmm = _parse_hhmm(tl.get("report_time") or "")
        if not hhmm:
            continue
        tz_name = tl.get("report_timezone") or "Asia/Kolkata"
        now_local = _now_in_tz(tz_name)
        last_sent = tl.get("last_report_sent_on")
        if hasattr(last_sent, "isoformat"):
            # Postgres returns a datetime.date
            last_sent_date = last_sent if isinstance(last_sent, date) else last_sent.date()
        else:
            last_sent_date = None
        if _should_fire(now_local, hhmm, last_sent_date):
            try:
                _send_report_for(db, tracker, teams_notifier, tl, dashboard_url)
            except Exception as e:
                print(f"[Scheduler] unexpected error for {tl.get('email')}: {e}")


def _loop(get_db, dashboard_url: str) -> None:
    # Small jitter at startup so multiple dashboard restarts don't all
    # slam the webhook at the same second.
    _stop_event.wait(timeout=2.0)
    while not _stop_event.is_set():
        try:
            _tick(get_db, dashboard_url)
        except Exception as e:
            print(f"[Scheduler] tick error: {e}")
        _stop_event.wait(timeout=_POLL_SECONDS)


def start(get_db, dashboard_url: str = "http://localhost:9090") -> None:
    """Start the scheduler thread exactly once.

    `get_db` should be a callable returning a ready DatabaseManager (the
    dashboard already has `_get_db()` for this). We take a getter rather
    than a db instance so restarts / reconnects flow through the shared
    singleton.
    """
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    if os.getenv("CRA_DISABLE_REPORT_SCHEDULER") == "1":
        print("[Scheduler] disabled via CRA_DISABLE_REPORT_SCHEDULER")
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_loop, args=(get_db, dashboard_url),
        name="cra-report-scheduler", daemon=True,
    )
    _scheduler_thread.start()
    print("[Scheduler] Report scheduler started (polls every "
          f"{_POLL_SECONDS}s, fires within {_WINDOW_MINUTES}min window).")


def stop() -> None:
    _stop_event.set()
