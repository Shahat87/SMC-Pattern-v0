from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.models.db import get_conn
from app.services.scanner import run_scan

try:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
    APSCHED_AVAILABLE = True
except Exception:
    APSCHED_AVAILABLE = False


def _load_scan_interval(default_sec: int = 60) -> int:
    cfg_path = Path('config/settings.json')
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding='utf-8'))
            return int(data.get('scan_interval_sec', default_sec))
        except Exception:
            return default_sec
    return default_sec


_scheduler: Optional["BackgroundScheduler"] = None


def start_scheduler() -> None:
    global _scheduler
    if not APSCHED_AVAILABLE:
        return
    if _scheduler is not None:
        return
    interval = _load_scan_interval(60)
    sched = BackgroundScheduler(daemon=True)

    def job():
        conn = get_conn()
        rows = conn.execute(
            "SELECT symbol, timeframe FROM watchlist WHERE active=1"
        ).fetchall()
        for r in rows:
            try:
                run_scan(r['symbol'], r['timeframe'])
            except Exception:
                # ignore failures for robustness
                pass

    sched.add_job(job, 'interval', seconds=interval, id='watchlist_scan', replace_existing=True)
    sched.start()
    _scheduler = sched

