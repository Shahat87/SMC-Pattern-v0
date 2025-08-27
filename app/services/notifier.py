from app.models.db import get_conn

def save_alert_record(event_id: int, image_path: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (event_id, image_path) VALUES (?,?)",
        (event_id, image_path),
    )
    conn.commit()

# For future: implement Telegram sender here using python-telegram-bot