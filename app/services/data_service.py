import pandas as pd

def convert_to_dataframe(response):
    candles = response.get("candles", [])

    df = pd.DataFrame(candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume"
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)

    return df