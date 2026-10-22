"""
Backtesting: "if I had traded this strategy in the past, how would it have done?"

A strategy is just a POSITION for every candle:
   1 = long (bought), -1 = short (sold), 0 = flat (no position)

Golden rule: a decision made at the CLOSE of candle t can only earn the
return of candle t+1. Using candle t's own return would be cheating
("look-ahead bias") and makes any strategy look amazing.
"""
import numpy as np
import pandas as pd
from config import TRADING_COST, CANDLES_PER_YEAR, AI_BUY_THRESHOLD, AI_SELL_THRESHOLD


def run_backtest(close, position, cost=TRADING_COST):
    """
    close:    Series of close prices
    position: Series of positions (1 / 0 / -1), decided at each candle's close
    Returns   (stats dict, equity Series starting at 1.0)
    """
    market_return = close.pct_change().fillna(0)
    held = position.shift(1).fillna(0)          # yesterday's decision earns today's return

    # Pay costs every time the position changes (flat->long = 1 unit, long->short = 2 units)
    turnover = held.diff().abs().fillna(held.abs())
    strategy_return = held * market_return - turnover * cost

    equity = (1 + strategy_return).cumprod()
    return compute_stats(strategy_return, equity, held), equity


def compute_stats(returns, equity, held):
    # Sharpe ratio: average return / risk, scaled to one year. Above 1 is good.
    std = returns.std()
    sharpe = (returns.mean() / std) * np.sqrt(CANDLES_PER_YEAR) if std > 0 else 0.0

    # Max drawdown: worst fall from a previous peak
    drawdown = equity / equity.cummax() - 1

    trades = split_trades(returns, held)
    wins = [t for t in trades if t > 0]

    return {
        "total_return": round(float(equity.iloc[-1] - 1), 4),
        "sharpe": round(float(sharpe), 2),
        "max_drawdown": round(float(drawdown.min()), 4),
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
        "exposure": round(float((held != 0).mean()), 4),   # % of time in the market
    }


def split_trades(returns, held):
    """Profit of each trade. A trade = a run of candles holding the same non-zero position."""
    trades, current, pnl = [], 0, 0.0
    for r, p in zip(returns, held):
        if p != current:
            if current != 0:
                trades.append(pnl)
            current, pnl = p, 0.0
        if p != 0:
            pnl = (1 + pnl) * (1 + r) - 1
    if current != 0:
        trades.append(pnl)
    return trades


def ai_positions(prob_up, buy=AI_BUY_THRESHOLD, sell=AI_SELL_THRESHOLD):
    """Long when the model is confident of UP, short when confident of DOWN, else flat."""
    return pd.Series(np.where(prob_up > buy, 1, np.where(prob_up < sell, -1, 0)), index=prob_up.index)
