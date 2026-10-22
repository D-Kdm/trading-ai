import numpy as np
import pandas as pd


def convert_to_dataframe(response):
    candles = response.get("candles", [])

    df = pd.DataFrame(candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume"
    ])

    # Fyers can return the same candle twice (e.g. today's candles) and not always in
    # order. Duplicates would make the model see some candles twice, and the chart
    # can't draw repeated times - so keep one copy of each, oldest first.
    df = df.drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp")

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)

    return df


def rsi(close, period=14):
    """Relative Strength Index (0-100). Above 70 = 'overbought', below 30 = 'oversold'."""
    change = close.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    # Wilder's smoothing = exponential average with alpha 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def add_features(df):
    df = df.copy()
    close = df['close']

    # ---------- Basic features (also shown on the dashboard) ----------
    # 1. Returns: % change from the previous candle
    df['returns'] = close.pct_change()

    # 2. Moving Averages: average price of the last 10 / 20 candles
    df['ma_10'] = close.rolling(window=10).mean()
    df['ma_20'] = close.rolling(window=20).mean()

    # 3. Volatility: how much returns jump around
    df['volatility'] = df['returns'].rolling(window=10).std()

    # 4. Price difference and 5. Momentum (in rupees)
    df['price_diff'] = close - df['open']
    df['momentum'] = close - close.shift(5)

    # ---------- Technical indicators ----------
    # RSI: strength of recent gains vs losses
    df['rsi_14'] = rsi(close)

    # MACD: difference between a fast and slow exponential average
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # Bollinger Bands: MA 20 +/- 2 standard deviations
    std_20 = close.rolling(window=20).std()
    df['bb_upper'] = df['ma_20'] + 2 * std_20
    df['bb_lower'] = df['ma_20'] - 2 * std_20

    # ATR: average size of a candle's full range (including gaps)
    prev_close = close.shift(1)
    true_range = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df['atr_14'] = true_range.rolling(window=14).mean()

    # ---------- Model features ----------
    # The model gets RATIOS, not raw prices. A raw price like 2,900 means nothing
    # to the model once the stock moves to 3,100 - but "1% above its average" always
    # means the same thing. That is why these are all percentages or ratios.
    df['returns_3'] = close.pct_change(3)
    df['dist_ma10'] = close / df['ma_10'] - 1
    df['ma_spread'] = df['ma_10'] / df['ma_20'] - 1
    df['body_pct'] = df['price_diff'] / df['open']
    df['momentum_pct'] = close / close.shift(5) - 1
    df['macd_hist_pct'] = df['macd_hist'] / close
    # 0 = at the lower band, 1 = at the upper band
    df['bb_pct'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['ma_20']
    df['atr_pct'] = df['atr_14'] / close
    # >1 means more trading than usual
    # (indices have no volume -> treat as "normal" = 1)
    avg_volume = df['volume'].rolling(window=20).mean().replace(0, np.nan)
    df['vol_ratio'] = (df['volume'] / avg_volume).fillna(1)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)

    return df
