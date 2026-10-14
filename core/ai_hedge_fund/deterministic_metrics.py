# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Deterministic Mathematical Metrics Engine (FinRobot Inspired)
Calculates objective quantitative indicators using pure Python, NumPy, and Pandas.
Completely eliminates numerical hallucinations from LLM agents.
"""

import math
import time
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import yfinance as yf


class DeterministicMetrics:
    """
    Pure Python Quantitative Computation Engine.
    Ensures that volatility, drawdown, Sharpe ratio, and technical levels
    are 100% mathematically exact before passing to AI Council & Debate.
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    CACHE_TTL = 900  # 15 minutes cache

    @classmethod
    def compute_for_symbol(cls, symbol: str, period: str = "1y") -> Dict[str, Any]:
        """
        Fetches price history and computes verified deterministic metrics for a given symbol.
        """
        norm_sym = symbol.strip().upper()
        cache_key = f"{norm_sym}_{period}"
        now = time.time()

        if cache_key in cls._cache:
            entry = cls._cache[cache_key]
            if now - entry["cached_at"] < cls.CACHE_TTL:
                return entry["data"]

        try:
            ticker = yf.Ticker(norm_sym)
            hist = ticker.history(period=period)
            if hist is not None and not hist.empty and len(hist) >= 5:
                metrics = cls.compute_price_metrics(hist)
                metrics["symbol"] = norm_sym
                cls._cache[cache_key] = {"cached_at": now, "data": metrics}
                return metrics
        except Exception as e:
            print(f"[DeterministicMetrics] Error fetching history for {norm_sym}: {e}")

        empty = cls._empty_metrics()
        empty["symbol"] = norm_sym
        return empty

    @classmethod
    def compute_price_metrics(cls, df_history: pd.DataFrame, risk_free_rate: float = 0.04) -> Dict[str, Any]:
        """
        Computes mathematically verifiable risk and momentum metrics from price history.
        Expects a DataFrame with 'close' (or 'Close') column indexed chronologically.
        """
        if df_history is None or df_history.empty:
            return cls._empty_metrics()

        # Normalize column names
        df = df_history.copy()
        col_map = {c: c.lower() for c in df.columns}
        df.rename(columns=col_map, inplace=True)

        if "close" not in df.columns:
            return cls._empty_metrics()

        closes = df["close"].dropna()
        if len(closes) < 5:
            return cls._empty_metrics()

        current_price = float(closes.iloc[-1])

        # Daily returns
        daily_returns = closes.pct_change().dropna()
        if daily_returns.empty:
            return cls._empty_metrics()

        # 1. 20-Day Annualized Volatility
        recent_returns_20 = daily_returns.tail(20)
        vol_20d = float(recent_returns_20.std() * np.sqrt(252)) if len(recent_returns_20) > 2 else 0.0

        # 2. 1-Year Max Drawdown
        rolling_max = closes.cummax()
        drawdowns = (closes - rolling_max) / rolling_max
        max_drawdown = float(drawdowns.min())  # negative number, e.g. -0.25 (-25%)

        # 3. 1-Year Annualized Return & Sharpe Ratio
        n_days = len(daily_returns)
        if n_days >= 30:
            ann_return = float(daily_returns.mean() * 252)
            ann_vol = float(daily_returns.std() * np.sqrt(252))
            sharpe = float((ann_return - risk_free_rate) / ann_vol) if ann_vol > 1e-4 else 0.0
        else:
            ann_return = 0.0
            sharpe = 0.0

        # 4. 14-Day Relative Strength Index (RSI)
        rsi_14 = cls._calculate_rsi(closes, period=14)

        # 5. 95% Historical Value at Risk (1-Day VaR)
        var_95_daily = float(np.percentile(daily_returns, 5)) if len(daily_returns) >= 20 else -0.03

        # 6. Distance from 52-week High / Low
        high_52w = float(closes.tail(252).max())
        low_52w = float(closes.tail(252).min())
        dist_from_high_pct = float((current_price - high_52w) / high_52w * 100.0)
        dist_from_low_pct = float((current_price - low_52w) / low_52w * 100.0)

        # 7. 20-day vs 50-day Moving Average Trend
        ma_20 = float(closes.tail(20).mean()) if len(closes) >= 20 else current_price
        ma_50 = float(closes.tail(50).mean()) if len(closes) >= 50 else current_price
        trend_label = "上昇トレンド (MA20 > MA50)" if ma_20 >= ma_50 else "下落トレンド (MA20 < MA50)"

        return {
            "current_price": round(current_price, 2),
            "volatility_20d_annualized_pct": round(vol_20d * 100.0, 1),
            "max_drawdown_pct": round(max_drawdown * 100.0, 1),
            "sharpe_ratio_1y": round(sharpe, 2),
            "rsi_14": round(rsi_14, 1),
            "var_95_daily_pct": round(var_95_daily * 100.0, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_from_52w_high_pct": round(dist_from_high_pct, 1),
            "dist_from_52w_low_pct": round(dist_from_low_pct, 1),
            "trend_ma20_ma50": trend_label,
            "ma_20": round(ma_20, 2),
            "ma_50": round(ma_50, 2),
            "data_points": n_days,
            "computation_engine": "Pure Python Deterministic"
        }

    @staticmethod
    def _calculate_rsi(series: pd.Series, period: int = 14) -> float:
        if len(series) < period + 1:
            return 50.0
        delta = series.diff().dropna()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.tail(period).mean()
        avg_loss = loss.tail(period).mean()
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @classmethod
    def _empty_metrics(cls) -> Dict[str, Any]:
        return {
            "current_price": 0.0,
            "volatility_20d_annualized_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio_1y": 0.0,
            "rsi_14": 50.0,
            "var_95_daily_pct": 0.0,
            "high_52w": 0.0,
            "low_52w": 0.0,
            "dist_from_52w_high_pct": 0.0,
            "dist_from_52w_low_pct": 0.0,
            "trend_ma20_ma50": "データ不足",
            "ma_20": 0.0,
            "ma_50": 0.0,
            "data_points": 0,
            "computation_engine": "Pure Python Deterministic (Empty)"
        }
