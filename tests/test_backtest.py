import pandas as pd
import pytest

from app.services.backtest_service import ai_positions, run_backtest, split_trades


def test_always_long_without_costs_matches_buy_and_hold():
    close = pd.Series([100, 101, 103, 102, 105], dtype=float)
    stats, equity = run_backtest(close, pd.Series(1, index=close.index), cost=0)
    # Position decided at candle 0's close starts earning from candle 1
    assert equity.iloc[-1] == pytest.approx(105 / 100)
    assert stats["trades"] == 1


def test_no_look_ahead_a_signal_on_the_last_candle_earns_nothing():
    close = pd.Series([100, 100, 100, 120], dtype=float)
    # Go long only at the close of the big up-candle -> must NOT get its +20%
    position = pd.Series([0, 0, 0, 1])
    _, equity = run_backtest(close, position, cost=0)
    assert equity.iloc[-1] == pytest.approx(1.0)


def test_short_position_profits_when_price_falls():
    close = pd.Series([100, 90], dtype=float)
    _, equity = run_backtest(close, pd.Series([-1, -1]), cost=0)
    assert equity.iloc[-1] == pytest.approx(1.10)


def test_costs_are_charged_on_each_position_change():
    close = pd.Series([100] * 6, dtype=float)                 # flat price
    position = pd.Series([1, 1, -1, -1, 0, 0])                # enter, flip (2 units), exit
    _, equity = run_backtest(close, position, cost=0.001)
    assert equity.iloc[-1] == pytest.approx((1 - 0.001) * (1 - 0.002) * (1 - 0.001))


def test_split_trades_counts_each_run_of_same_position():
    returns = pd.Series([0.0, 0.01, 0.02, -0.01, 0.0, 0.03])
    held = pd.Series([0, 1, 1, -1, 0, 1])
    trades = split_trades(returns, held)
    assert len(trades) == 3
    assert trades[0] == pytest.approx(1.01 * 1.02 - 1)


def test_ai_positions_use_confidence_thresholds():
    prob = pd.Series([0.7, 0.5, 0.3])
    assert ai_positions(prob, buy=0.55, sell=0.45).tolist() == [1, 0, -1]
