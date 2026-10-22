import numpy as np
import pandas as pd

from app.models.train_model import FEATURES
from app.services.data_service import add_features, convert_to_dataframe, rsi
from app.services.demo_service import generate_demo_response


def demo_df(n=400):
    return add_features(convert_to_dataframe(generate_demo_response(n=n)))


def test_rsi_stays_between_0_and_100():
    close = pd.Series(np.random.default_rng(1).normal(0, 1, 500).cumsum() + 100)
    values = rsi(close)
    assert values.between(0, 100).all()


def test_rsi_is_high_when_price_only_rises():
    close = pd.Series(np.arange(100, 200, dtype=float))
    assert rsi(close).iloc[-1] > 99


def test_all_model_features_exist_without_gaps():
    df = demo_df()
    assert set(FEATURES) <= set(df.columns)
    assert not df[FEATURES].isna().any().any()
    assert np.isfinite(df[FEATURES].to_numpy()).all()


def test_bollinger_bands_surround_the_average():
    df = demo_df()
    assert (df["bb_upper"] >= df["ma_20"]).all()
    assert (df["bb_lower"] <= df["ma_20"]).all()


def test_demo_candles_are_valid_and_in_market_hours():
    candles = generate_demo_response(n=300)["candles"]
    for t, o, h, l, c, v in candles:
        assert l <= min(o, c) and h >= max(o, c)
        ist = pd.Timestamp(t, unit="s", tz="UTC").tz_convert("Asia/Kolkata")
        assert ist.weekday() < 5
        assert (9, 15) <= (ist.hour, ist.minute) <= (15, 25)


def test_duplicate_and_unordered_candles_are_cleaned():
    raw = {"candles": [
        [300, 1, 1, 1, 1, 10],
        [0, 1, 1, 1, 1, 10],
        [300, 2, 2, 2, 2, 20],     # same time again (newer copy)
    ]}
    df = convert_to_dataframe(raw)
    assert df["timestamp"].tolist() == [0, 300]
    assert df["close"].iloc[-1] == 2
