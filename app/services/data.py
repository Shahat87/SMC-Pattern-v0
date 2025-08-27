from __future__ import annotations

"""Data provider abstraction for OHLCV.

Current implementation returns a synthetic series for demo. You can replace
`get_ohlcv_df` with a ccxt-backed fetcher later.
"""

from datetime import datetime, timedelta
import os
import numpy as np

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


def _synthetic_df(symbol: str, timeframe: str, limit: int = 150):
    if pd is None:
        return None
    now = datetime.utcnow()
    tf_map = {'1m': 1, '2m': 2, '3m': 3, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '2h': 120, '4h': 240, '1d': 60 * 24}
    step = tf_map.get(timeframe, 5)
    idx = [now - timedelta(minutes=step * (limit - i)) for i in range(limit)]
    rng = np.random.default_rng(abs(hash(symbol + timeframe)) % (2**32))
    prices = np.cumsum(rng.normal(0, 0.5, size=limit)) + 100
    opens = prices + rng.normal(0, 0.2, size=limit)
    highs = np.maximum(opens, prices) + rng.random(size=limit) * 0.5
    lows = np.minimum(opens, prices) - rng.random(size=limit) * 0.5
    closes = prices
    vols = rng.integers(100, 1000, size=limit)
    return pd.DataFrame({'Open': opens, 'High': highs, 'Low': lows, 'Close': closes, 'Volume': vols}, index=pd.DatetimeIndex(idx))


def get_ohlcv_df(symbol: str, timeframe: str, limit: int = 150):
    """Return OHLCV as pandas DataFrame. Tries ccxt if available, else synthetic.

    Env:
      - EXCHANGE_ID (default: binance)
      - EXCHANGE_API_KEY / EXCHANGE_API_SECRET (optional)
    """
    # Try ccxt
    try:
        import ccxt  # type: ignore
        if pd is None:
            return None
        ex_id = os.getenv('EXCHANGE_ID', 'binance')
        cls = getattr(ccxt, ex_id, None)
        if cls is None:
            return _synthetic_df(symbol, timeframe, limit)
        opts = {
            'apiKey': os.getenv('EXCHANGE_API_KEY'),
            'secret': os.getenv('EXCHANGE_API_SECRET'),
            'enableRateLimit': True,
        }
        exchange = cls({k: v for k, v in opts.items() if v is not None})
        # Some exchanges need markets loaded before fetch
        try:
            exchange.load_markets()
        except Exception:
            pass
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not data:
            return _synthetic_df(symbol, timeframe, limit)
        ts = [row[0] for row in data]
        idx = pd.to_datetime(ts, unit='ms')
        df = pd.DataFrame({
            'Open': [row[1] for row in data],
            'High': [row[2] for row in data],
            'Low': [row[3] for row in data],
            'Close': [row[4] for row in data],
            'Volume': [row[5] for row in data],
        }, index=idx)
        return df
    except Exception:
        return _synthetic_df(symbol, timeframe, limit)

