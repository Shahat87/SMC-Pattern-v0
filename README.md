# SMC Pattern Scanner (Localhost)

A minimal, ready-to-run skeleton for a **pattern-scanning system** with a **localhost dashboard**.
It follows the architecture we discussed (Rule-Based first; vision layer later).

## Quick Start
1) Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
2) Configure environment:
```bash
cp .env.example .env
# Edit .env to set TELEGRAM_BOT_TOKEN/CHAT_ID (optional)
```
3) Run the server:
```bash
uvicorn app.main:app --reload
# Open http://127.0.0.1:8000
```

## What’s included
- **FastAPI** server with REST endpoints and a lightweight HTMX dashboard
- **SQLite** database (created at `storage/events.sqlite`)
- **Patterns DSL (YAML)**: add your pattern files in `patterns/`
- **Watchlist** (pairs & timeframes)
- **Manual scan** (stub) + scoring + alert record
- **Renderer** stub that saves a placeholder chart image (ready to swap with mplfinance)
- **Telegram notifier** stub (no network calls unless you add your token and uncomment)

> This is a runnable skeleton intended to be iterated by Codex into a full implementation.

## Project layout
```
app/
  main.py                # FastAPI app + routers + scheduler hook
  api/                   # REST endpoints used by UI
  services/              # collector/features/patterns/scoring/renderer/notifier
  models/                # sqlite helpers
  web/templates          # HTMX pages
patterns/                # YAML pattern definitions
storage/                 # sqlite file + images
requirements.txt
.env.example
```

## Next steps
- Replace `services/renderer.py` with real chart rendering using `mplfinance` and overlays.
- Implement real primitives in `features.py` and full YAML evaluation in `patterns_engine.py`.
- Add APScheduler job for periodic scans (hook in `main.py` is ready).
- Extend the UI (Backtest page, Pattern Builder editor, etc.).

## New additions
- Pattern media storage: upload template images and link to patterns. Files saved under `storage/patterns/` and served at `/storage/...`.
- Patterns page: second form to upload image by `pattern_id`, and enhanced table showing media count with inline preview.
- Scan v2: new endpoint `/scan/run2` used by the Scan page. Renders a chart (mplfinance if available, otherwise fallback PNG) and compares against uploaded template images using a simple normalized cross-correlation implemented with Pillow+NumPy.
- Thresholding: uses `max(watchlist.threshold, pattern.scoring.threshold_alert)` for decision.
- Telegram: `send_telegram_alert` tries to send if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set; otherwise no-op.
