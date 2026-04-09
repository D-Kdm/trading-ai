import pandas as pd

def convert_to_dataframe(response):
    candles = response.get("candles", [])

    df = pd.DataFrame(candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume"
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)

    return df


def add_features(df):
    # 1. Returns
    df['returns'] = df['close'].pct_change()

    # 2. Moving Averages
    df['ma_10'] = df['close'].rolling(window=10).mean()
    df['ma_20'] = df['close'].rolling(window=20).mean()

    # 3. Volatility
    df['volatility'] = df['returns'].rolling(window=10).std()

    # 4. Price difference
    df['price_diff'] = df['close'] - df['open']

    # 5. Momentum
    df['momentum'] = df['close'] - df['close'].shift(5)

    df.dropna(inplace=True)

    return df