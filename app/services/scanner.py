from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from app.models.db import get_conn
from app.services.patterns_engine import load_patterns_from_dir, parse_yaml
from app.services.renderer import render_placeholder_chart, render_chart_png
from app.services.scoring import score_simple, similarity_score
from app.services.notifier import save_alert_record, send_telegram_alert
from app.services.data import get_ohlcv_df


def run_scan(symbol: str, timeframe: str) -> Tuple[str, float, float, str]:
    """Run a single scan for symbol/timeframe.

    Returns: (pattern_name, score, eff_threshold, img_path)
    """
    conn = get_conn()

    # load patterns from DB first
    db_patterns = conn.execute(
        "SELECT id, name, version, yaml, is_active FROM patterns WHERE is_active=1 ORDER BY id DESC"
    ).fetchall()
    patterns = []
    for r in db_patterns:
        try:
            d = parse_yaml(r['yaml'])
            d['__db_id'] = r['id']
            patterns.append(d)
        except Exception:
            continue
    if not patterns:
        patterns = load_patterns_from_dir(Path("patterns"))
        for d in patterns:
            d['__db_id'] = None
    if not patterns:
        raise RuntimeError("No patterns available")

    # Get data and render temporary chart
    df = get_ohlcv_df(symbol, timeframe, limit=150)
    tmp_img = render_chart_png(symbol, timeframe, df, f"scan_{symbol.replace('/', '-')}_{timeframe}")

    best = None
    for p in patterns:
        img_ref = None
        if p.get('__db_id') is not None:
            row = conn.execute(
                "SELECT filename FROM pattern_media WHERE pattern_id=? ORDER BY id DESC LIMIT 1",
                (p['__db_id'],),
            ).fetchone()
            if row:
                img_ref = str(row['filename']).replace('\\', '/')
        if not img_ref:
            continue
        score = similarity_score(tmp_img, img_ref, method='ncc')
        if score is None:
            score = score_simple(p)
        if best is None or score > best[1]:
            best = (p, score, img_ref)

    if best is None:
        p = patterns[0]
        score = score_simple(p)
    else:
        p, score, _ = best

    wl = conn.execute(
        "SELECT threshold FROM watchlist WHERE symbol=? AND timeframe=? LIMIT 1",
        (symbol, timeframe),
    ).fetchone()
    wl_threshold = float(wl['threshold']) if wl else 0.7
    pat_threshold = float(p.get('scoring', {}).get('threshold_alert', 0.7))
    eff_threshold = max(wl_threshold, pat_threshold)
    status = 'sent' if score >= eff_threshold else 'ignored'

    cur = conn.execute(
        "INSERT INTO events (symbol, timeframe, pattern_name, score, status) VALUES (?,?,?,?,?)",
        (symbol, timeframe, p.get('name', 'Unnamed'), float(score), status),
    )
    event_id = cur.lastrowid
    img_path = render_placeholder_chart(symbol, timeframe, event_id)

    if status == 'sent':
        save_alert_record(event_id, img_path)
        send_telegram_alert(
            text=f"{symbol} {timeframe} | {p.get('name','Unnamed')} | score={score:.2f}",
            image_path=img_path,
        )

    return p.get('name', 'Unnamed'), float(score), float(eff_threshold), img_path

