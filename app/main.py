from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.models.db import init_db, get_conn
from app.services.patterns_engine import load_patterns_from_dir, parse_yaml
from app.services.renderer import render_placeholder_chart
from app.services.scoring import score_simple
from app.services.notifier import save_alert_record
import yaml

APP_DIR = Path(__file__).parent
ROOT = APP_DIR.parent

app = FastAPI(title="SMC Pattern Scanner (Skeleton)")
app.mount("/static", StaticFiles(directory=APP_DIR / "web" / "static"), name="static")

# HTML pages
@app.get("/", response_class=HTMLResponse)
def home():
    return (APP_DIR / "web" / "templates" / "index.html").read_text(encoding="utf-8")

@app.get("/patterns", response_class=HTMLResponse)
def patterns_page():
    return (APP_DIR / "web" / "templates" / "patterns.html").read_text(encoding="utf-8")

@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page():
    return (APP_DIR / "web" / "templates" / "watchlist.html").read_text(encoding="utf-8")

@app.get("/alerts", response_class=HTMLResponse)
def alerts_page():
    return (APP_DIR / "web" / "templates" / "alerts.html").read_text(encoding="utf-8")

@app.get("/scan", response_class=HTMLResponse)
def scan_page():
    return (APP_DIR / "web" / "templates" / "scan.html").read_text(encoding="utf-8")


# --- HTMX Partials ---
@app.get("/patterns/table", response_class=HTMLResponse)
def patterns_table():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, version, is_active FROM patterns ORDER BY id DESC").fetchall()
    html = ['<table><tr><th>ID</th><th>Name</th><th>Version</th><th>Active</th></tr>']
    for r in rows:
        html.append(f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['version']}</td><td>{'✅' if r['is_active'] else '❌'}</td></tr>")
    html.append("</table>")
    return HTMLResponse("".join(html))

@app.post("/patterns/upload", response_class=HTMLResponse)
async def patterns_upload(yaml: str = Form(...)):
    # parse and save
    try:
        d = parse_yaml(yaml)
    except Exception as e:
        return HTMLResponse(f"<div class='card'>❌ YAML error: {e}</div>")

    name = d.get("name", "Unnamed")
    version = str(d.get("version", "1.0"))
    conn = get_conn()
    conn.execute(
        "INSERT INTO patterns (name, version, yaml, is_active) VALUES (?,?,?,?)",
        (name, version, yaml, 1),
    )
    conn.commit()
    return patterns_table()

@app.get("/watchlist/table", response_class=HTMLResponse)
def watchlist_table():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, symbol, timeframe, threshold, min_vol_usd, active FROM watchlist ORDER BY id DESC"
    ).fetchall()
    html = [
        '<table><tr><th>ID</th><th>Symbol</th><th>TF</th><th>Threshold</th><th>MinVolUSD</th><th>Active</th><th>Actions</th></tr>'
    ]
    for r in rows:
        rid = r["id"]
        active_icon = "✅" if r["active"] else "❌"
        toggle_label = "Deactivate" if r["active"] else "Activate"
        html.append(
            f"<tr><td>{rid}</td><td>{r['symbol']}</td><td>{r['timeframe']}</td>"
            f"<td><input form='f{rid}' name='threshold' value='{r['threshold']}' type='number' step='0.01' style='width:70px'></td>"
            f"<td><input form='f{rid}' name='min_vol_usd' value='{r['min_vol_usd']}' type='number' step='1' style='width:100px'></td>"
            f"<td>{active_icon}</td>"
            f"<td>"
            f"<form id='f{rid}' hx-post='/watchlist/update/{rid}' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>Save</button></form> "
            f"<form hx-post='/scan/run' hx-target='#scan_result' hx-swap='innerHTML' style='display:inline'><input type='hidden' name='symbol' value='{r['symbol']}'><input type='hidden' name='timeframe' value='{r['timeframe']}'><button class='btn' type='submit'>Scan</button></form> "
            f"<form hx-post='/watchlist/toggle/{rid}' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>{toggle_label}</button></form> "
            f"<form hx-post='/watchlist/delete/{rid}' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>Delete</button></form>"
            f"</td></tr>"
        )
    html.append("</table>")
    return HTMLResponse("".join(html))

@app.post("/watchlist/add", response_class=HTMLResponse)
async def watchlist_add(symbol: str = Form(...), timeframe: str = Form(...), threshold: float = Form(0.7), min_vol_usd: float = Form(3e7)):
    conn = get_conn()
    conn.execute(
        "INSERT INTO watchlist (symbol, timeframe, threshold, min_vol_usd, active) VALUES (?,?,?,?,1)",
        (symbol, timeframe, threshold, min_vol_usd),
    )
    conn.commit()
    return watchlist_table()

@app.post("/watchlist/toggle/{id}", response_class=HTMLResponse)
def watchlist_toggle(id: int):
    conn = get_conn()
    conn.execute("UPDATE watchlist SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit()
    return watchlist_table()

@app.post("/watchlist/delete/{id}", response_class=HTMLResponse)
def watchlist_delete(id: int):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE id=?", (id,))
    conn.commit()
    return watchlist_table()

@app.post("/watchlist/update/{id}", response_class=HTMLResponse)
async def watchlist_update(id: int, threshold: float = Form(...), min_vol_usd: float = Form(...)):
    conn = get_conn()
    conn.execute(
        "UPDATE watchlist SET threshold=?, min_vol_usd=? WHERE id=?",
        (threshold, min_vol_usd, id),
    )
    conn.commit()
    return watchlist_table()

@app.get("/alerts/table", response_class=HTMLResponse)
def alerts_table():
    conn = get_conn()
    rows = conn.execute(
        "SELECT a.id, a.sent_at, e.symbol, e.timeframe, e.pattern_name, e.score, a.image_path "
        "FROM alerts a JOIN events e ON a.event_id=e.id ORDER BY a.id DESC LIMIT 50"
    ).fetchall()
    html = ['<table><tr><th>ID</th><th>Time</th><th>Pair</th><th>TF</th><th>Pattern</th><th>Score</th><th>Image</th></tr>']
    for r in rows:
        img = f"<a href='/{r['image_path']}' target='_blank'>open</a>" if r["image_path"] else "-"
        html.append(f"<tr><td>{r['id']}</td><td>{r['sent_at']}</td><td>{r['symbol']}</td><td>{r['timeframe']}</td><td>{r['pattern_name']}</td><td>{r['score']:.2f}</td><td>{img}</td></tr>")
    html.append("</table>")
    return HTMLResponse(''.join(html))

@app.post("/scan/run", response_class=HTMLResponse)
async def scan_run(symbol: str = Form(...), timeframe: str = Form(...)):
    # This is a stub: loads patterns and creates a fake "match" with score
    patterns = load_patterns_from_dir(Path("patterns"))
    if not patterns:
        return HTMLResponse("<div class='card'>No patterns found in /patterns. Add a YAML first.</div>")
    # choose the first pattern and compute a simple score
    p = patterns[0]
    score = score_simple(p)
    # create event
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO events (symbol, timeframe, pattern_name, score, status) VALUES (?,?,?,?,?)",
        (symbol, timeframe, p.get('name','Unnamed'), score, 'sent')
    )
    event_id = cur.lastrowid
    # render a placeholder chart image
    img_path = render_placeholder_chart(symbol, timeframe, event_id)
    # record alert
    save_alert_record(event_id, img_path)
    html = f"""
    <div class='card'>
      <div>✅ Scan complete for <b>{symbol} {timeframe}</b>.</div>
      <div>Pattern: <b>{p.get('name','Unnamed')}</b> | Score: {score:.2f}</div>
      <div>Image: <a href='/{img_path}' target='_blank'>open</a></div>
    </div>
    """
    return HTMLResponse(html)

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---- App startup: ensure DB and folders ----
init_db()