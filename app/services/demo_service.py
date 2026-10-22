"""
Realistic-looking DEMO candles, used when Fyers is not connected
(no access token yet, market data unavailable, etc.).

The output has exactly the same shape as Fyers' history() response,
so the rest of the app can't tell the difference.
"""
from datetime import datetime, timedelta, timezone
import numpy as np

# Rough starting prices so each demo stock looks believable
BASE_PRICES = {
    "NSE:RELIANCE-EQ": 2900,
    "NSE:TCS-EQ": 4100,
    "NSE:INFY-EQ": 1850,
    "NSE:HDFCBANK-EQ": 1700,
    "NSE:SBIN-EQ": 820,
}


def market_timestamps(n):
    """The last n 5-minute candle times during NSE hours (Mon-Fri, 9:15-15:30 IST)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    day = now.date()
    times = []
    while len(times) < n:
        if day.weekday() < 5:                     # 0-4 = Monday-Friday
            open_ = datetime(day.year, day.month, day.day, 9, 15, tzinfo=ist)
            slots = [open_ + timedelta(minutes=5 * i) for i in range(75)]   # 75 candles per day
            times = [int(t.timestamp()) for t in slots if t <= now] + times
        day -= timedelta(days=1)
    return times[-n:]


def generate_demo_response(symbol="NSE:RELIANCE-EQ", n=600):
    # Same symbol -> same seed -> same chart every time (nice for videos)
    rng = np.random.default_rng(sum(ord(c) for c in symbol))
    price = BASE_PRICES.get(symbol, 1000)

    times = market_timestamps(n)

    candles = []
    drift = 0.0
    for i, t in enumerate(times):
        # New trading day -> price "gaps" a little from yesterday's close
        if i > 0 and t - times[i - 1] > 300:
            price *= 1 + rng.normal(0, 0.004)

        # Every 60 candles the "trend" changes, so the chart has up and down phases
        if i % 60 == 0:
            drift = rng.normal(0, 0.0004)

        open_ = price
        close = open_ * (1 + rng.normal(drift, 0.0015))   # next price = small random move
        high = max(open_, close) * (1 + abs(rng.normal(0, 0.0006)))
        low = min(open_, close) * (1 - abs(rng.normal(0, 0.0006)))
        volume = int(rng.lognormal(10, 0.5))

        candles.append([t, round(open_, 2), round(high, 2),
                        round(low, 2), round(close, 2), volume])
        price = close                                       # next candle opens here

    return {"s": "ok", "candles": candles}
