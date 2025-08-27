from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.models.db import init_db, get_conn
from app.services.patterns_engine import load_patterns_from_dir, parse_yaml
from app.services.renderer import render_placeholder_chart, render_chart_png
from app.services.scanner import run_scan
from app.services.scheduler import start_scheduler
import yaml
import os

APP_DIR = Path(__file__).parent
ROOT = APP_DIR.parent

app = FastAPI(title="SMC Pattern Scanner (Skeleton)")
app.mount("/static", StaticFiles(directory=APP_DIR / "web" / "static"), name="static")
app.mount("/storage", StaticFiles(directory=ROOT / "storage"), name="storage")

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
@app.get("/patterns/table2", response_class=HTMLResponse)
def patterns_table2():
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.id, p.name, p.version, p.is_active, (SELECT COUNT(1) FROM pattern_media m WHERE m.pattern_id=p.id) AS media_ct FROM patterns p ORDER BY p.id DESC"
    ).fetchall()
    html = ['<table><tr><th>ID</th><th>Name</th><th>Version</th><th>Active</th><th>Media</th><th>Actions</th></tr>']
    for r in rows:
        active = '✅' if r['is_active'] else '❌'
        media_btn = f"<button class='btn' hx-get='/patterns/media/{r['id']}' hx-target='#media_{r['id']}' hx-swap='innerHTML'>View</button>"
        html.append(
            f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['version']}</td><td>{active}</td><td>{r['media_ct']}</td><td>{media_btn}</td></tr>"
        )
        html.append(f"<tr><td colspan='6'><div id='media_{r['id']}'></div></td></tr>")
    html.append("</table>")
    return HTMLResponse("".join(html))

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

@app.post("/patterns/media/upload", response_class=HTMLResponse)
async def patterns_media_upload(pattern_id: int = Form(...), file: UploadFile = File(...)):
    content = await file.read()
    safe_name = f"p{pattern_id}_" + os.path.basename(file.filename).replace(' ', '_')
    out_dir = ROOT / "storage" / "patterns"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / safe_name
    out_path.write_bytes(content)
    width = height = None
    mime = file.content_type or "image/png"
    try:
        from PIL import Image  # type: ignore
        with Image.open(out_path) as img:
            width, height = img.size
    except Exception:
        pass
    conn = get_conn()
    conn.execute(
        "INSERT INTO pattern_media (pattern_id, kind, filename, mime, width, height) VALUES (?,?,?,?,?,?)",
        (pattern_id, 'template', f"storage/patterns/{safe_name}", mime, width, height),
    )
    conn.commit()
    return patterns_table2()

@app.get("/patterns/media/{pattern_id}", response_class=HTMLResponse)
def patterns_media(pattern_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, filename, width, height, created_at FROM pattern_media WHERE pattern_id=? ORDER BY id DESC",
        (pattern_id,),
    ).fetchall()
    if not rows:
        return HTMLResponse("<div class='card'>No media uploaded for this pattern.</div>")
    cells = []
    for r in rows:
        src = '/' + str(r['filename']).replace('\\', '/')
        cells.append(
            f"<div style='display:inline-block;margin:6px;text-align:center'>"
            f"<a href='{src}' target='_blank'><img src='{src}' style='max-width:220px;max-height:140px;display:block'></a>"
            f"<div class='muted'>#{r['id']} {r['width']}x{r['height']}</div>"
            f"</div>"
        )
    return HTMLResponse("<div class='card'>" + "".join(cells) + "</div>")

@app.get("/watchlist/table2", response_class=HTMLResponse)
def watchlist_table2():
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
            f"<td><input form='f{rid}' name='threshold' value='{r['threshold']}' type='number' step='0.01' style='width:80px'></td>"
            f"<td><input form='f{rid}' name='min_vol_usd' value='{r['min_vol_usd']}' type='number' step='1' style='width:110px'></td>"
            f"<td>{active_icon}</td>"
            f"<td>"
            f"<form id='f{rid}' hx-post='/watchlist/update2/{rid}' hx-include='input[form=\"f{rid}\"]' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>Save</button></form> "
            f"<form hx-post='/scan/run2' hx-target='#scan_result' hx-swap='innerHTML' style='display:inline'><input type='hidden' name='symbol' value='{r['symbol']}'><input type='hidden' name='timeframe' value='{r['timeframe']}'><button class='btn' type='submit'>Scan</button></form> "
            f"<form hx-post='/watchlist/toggle/{rid}' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>{toggle_label}</button></form> "
            f"<form hx-post='/watchlist/delete/{rid}' hx-target='#watchlist_table' hx-swap='outerHTML' style='display:inline'><button class='btn' type='submit'>Delete</button></form>"
            f"</td></tr>"
        )
    html.append("</table>")
    return HTMLResponse("".join(html))

@app.post("/watchlist/update2/{id}", response_class=HTMLResponse)
async def watchlist_update2(id: int, threshold: str = Form(...), min_vol_usd: str = Form(...)):
    def _to_float(s: str, default: float) -> float:
        try:
            return float(s.replace(',', '.'))
        except Exception:
            return default
    th = _to_float(threshold, 0.7)
    mv = _to_float(min_vol_usd, 3e7)
    conn = get_conn()
    conn.execute(
        "UPDATE watchlist SET threshold=?, min_vol_usd=? WHERE id=?",
        (th, mv, id),
    )
    conn.commit()
    return watchlist_table2()

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
        img_src = str(r['image_path']).replace('\\', '/') if r['image_path'] else None
        img = f"<a href='/{img_src}' target='_blank'>open</a>" if img_src else "-"
        html.append(f"<tr><td>{r['id']}</td><td>{r['sent_at']}</td><td>{r['symbol']}</td><td>{r['timeframe']}</td><td>{r['pattern_name']}</td><td>{r['score']:.2f}</td><td>{img}</td></tr>")
    html.append("</table>")
    return HTMLResponse(''.join(html))

@app.get("/alerts/table2", response_class=HTMLResponse)
def alerts_table2():
    conn = get_conn()
    rows = conn.execute(
        "SELECT a.id, a.sent_at, e.symbol, e.timeframe, e.pattern_name, e.score, a.image_path "
        "FROM alerts a JOIN events e ON a.event_id=e.id ORDER BY a.id DESC LIMIT 50"
    ).fetchall()
    html = ['<table><tr><th>ID</th><th>Time</th><th>Pair</th><th>TF</th><th>Pattern</th><th>Score</th><th>Image</th></tr>']
    for r in rows:
        img_src = str(r['image_path']).replace('\\', '/') if r['image_path'] else None
        img = f"<a href='/{img_src}' target='_blank'>open</a>" if img_src else "-"
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

@app.post("/scan/run2", response_class=HTMLResponse)
async def scan_run2(symbol: str = Form(...), timeframe: str = Form(...)):
    try:
        name, score, eff_threshold, img_path = run_scan(symbol, timeframe)
    except Exception as e:
        return HTMLResponse(f"<div class='card'>Scan error: {e}</div>")
    status = 'sent' if score >= eff_threshold else 'ignored'
    html = f"""
    <div class='card'>
      <div>✅ Scan complete for <b>{symbol} {timeframe}</b>.</div>
      <div>Pattern: <b>{name}</b> | Score: {score:.2f} | Threshold: {eff_threshold:.2f} | Decision: {status}</div>
      <div>Image: <a href='/{img_path}' target='_blank'>open</a></div>
    </div>
    """
    return HTMLResponse(html)

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---- App startup: ensure DB and folders ----
init_db()
start_scheduler()
