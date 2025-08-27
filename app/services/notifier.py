from app.models.db import get_conn
import os


def save_alert_record(event_id: int, image_path: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (event_id, image_path) VALUES (?,?)",
        (event_id, image_path),
    )
    conn.commit()


def send_telegram_alert(text: str, image_path: str | None = None) -> None:
    """Try to send a Telegram message with optional photo. Fails gracefully."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    try:
        from telegram import Bot  # type: ignore
        bot = Bot(token=token)
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                bot.send_photo(chat_id=chat_id, photo=f, caption=text)
        else:
            bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        # Silently ignore; logging could be added later
        return
