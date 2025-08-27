from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import mplfinance as mpf  # type: ignore
    import pandas as pd  # type: ignore
    MPL_AVAILABLE = True
except Exception:
    MPL_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


def _ensure_dir() -> Path:
    img_dir = Path('storage/images')
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir


def render_chart_png(symbol: str, timeframe: str, ohlcv_df: Optional["pd.DataFrame"], out_name: str) -> str:
    """Render a chart to PNG if mplfinance available; fallback to simple PIL text image.

    Returns web path (forward slashes).
    """
    img_dir = _ensure_dir()
    fpath = img_dir / f"{out_name}.png"

    if MPL_AVAILABLE and ohlcv_df is not None and not ohlcv_df.empty:
        try:
            mpf.plot(
                ohlcv_df,
                type='candle',
                style='charles',
                volume=False,
                savefig=dict(fname=str(fpath), dpi=120, bbox_inches='tight'),
                tight_layout=True,
            )
            return str(fpath).replace('\\', '/')
        except Exception:
            pass

    # Fallback: simple text image
    if Image is not None:
        img = Image.new('RGB', (800, 400), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        text = f"{symbol} {timeframe}\n{datetime.utcnow().isoformat()}Z"
        draw.text((20, 20), text, fill=(220, 220, 220))
        img.save(fpath)
    else:
        # absolute last resort: write a .txt renamed as .png (not ideal)
        fpath.write_text(
            f"Placeholder image for {symbol} {timeframe} at {datetime.utcnow().isoformat()}Z\n",
            encoding='utf-8',
        )
    return str(fpath).replace('\\', '/')


def render_placeholder_chart(symbol: str, timeframe: str, event_id: int) -> str:
    return render_chart_png(symbol, timeframe, None, f"event_{event_id}_{symbol.replace('/', '-')}_{timeframe}")
