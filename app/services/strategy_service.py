def generate_signal(df):
    df['signal'] = 0

    # BUY condition
    df.loc[
        (df['close'] > df['ma_10']) &
        (df['ma_10'] > df['ma_20']),
        'signal'
    ] = 1

    # SELL condition
    df.loc[
        (df['close'] < df['ma_10']) &
        (df['ma_10'] < df['ma_20']),
        'signal'
    ] = -1

    return df