# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Deterministic Mathematical Metrics Engine (FinRobot Inspired)
Calculates objective quantitative indicators using pure Python, NumPy, and Pandas.
Completely eliminates numerical hallucinations from LLM agents.
"""

import itertools
import math
import time
from typing import Dict, Any, List, Optional, Tuple
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

    @staticmethod
    def evaluate_slippage_proof_pyramiding_bound(
        alpha: float = 0.30,
        delta_lock_pct: float = 0.0135,
        delta_buf_pct: float = 0.0040,
        round_trip_cost_pct: float = 0.0010,
        expected_slippage_pct: float = 0.0035,
        initial_sl_pct: float = 0.0150,
    ) -> Dict[str, Any]:
        """
        Implements Theorem 2 (Slippage-Proof Pyramiding Boundary Inequality) from:
        Hashimoto, K. (2026). "Eliminating Polarity Hallucinations and Order Book Horizon
        Truncation Bias in Autonomous Multi-Agent Quantitative Systems", Zenodo.
        DOI: 10.5281/zenodo.23935930

        Computes the closed-form maximum tolerable stop-loss slippage (delta_slip_max)
        and worst-case realized payoff (in R-multiples) when scaling into a winning position.
        """
        alpha = max(0.0, float(alpha))
        delta_lock_net = float(delta_lock_pct) - float(delta_buf_pct)
        denom = 1.0 + alpha
        numerator = delta_lock_net - (alpha * float(delta_buf_pct)) - (denom * float(round_trip_cost_pct))
        delta_slip_max = numerator / denom if denom > 0 else 0.0

        worst_case_net_return_pct = numerator - (denom * float(expected_slippage_pct))
        worst_case_r_multiple = (
            worst_case_net_return_pct / float(initial_sl_pct)
            if float(initial_sl_pct) > 0 else 0.0
        )

        return {
            "alpha_scale_in_ratio": round(alpha, 4),
            "delta_lock_net_pct": round(delta_lock_net * 100.0, 4),
            "max_tolerable_slippage_pct": round(delta_slip_max * 100.0, 4),
            "worst_case_net_return_pct": round(worst_case_net_return_pct * 100.0, 4),
            "worst_case_r_multiple": round(worst_case_r_multiple, 4),
            "is_slippage_proof": bool(worst_case_net_return_pct > 0.0 and expected_slippage_pct < delta_slip_max),
        }

    @staticmethod
    def compute_deflated_sharpe_ratio(
        best_sr_annual: float,
        daily_returns: np.ndarray,
        trial_srs_annual: List[float],
    ) -> Dict[str, float]:
        """
        Implements Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio (DSR).
        Corrects for multiple-testing selection bias (Euler-Mascheroni expected maximum SR0)
        and non-Normal return moments (sample skewness gamma_3 and sample kurtosis gamma_4).
        """
        from scipy.stats import norm, skew, kurtosis

        rets = np.asarray(daily_returns, dtype=float)
        T = max(len(rets), 2)
        N = max(len(trial_srs_annual), 2)

        sr_hat_daily = float(best_sr_annual) / math.sqrt(252.0)
        trials_daily = np.asarray(trial_srs_annual, dtype=float) / math.sqrt(252.0)
        var_trials_daily = float(np.var(trials_daily, ddof=1)) if len(trials_daily) > 1 else 0.0005

        euler_gamma = 0.5772156649015329
        z1 = float(norm.ppf(1.0 - 1.0 / N))
        z2 = float(norm.ppf(1.0 - 1.0 / (N * math.e)))
        sr0_daily = math.sqrt(max(var_trials_daily, 1e-10)) * ((1.0 - euler_gamma) * z1 + euler_gamma * z2)

        g3 = float(skew(rets)) if len(rets) > 2 else 0.0
        g4 = float(kurtosis(rets, fisher=False)) if len(rets) > 3 else 3.0

        denom = math.sqrt(max(1.0 - g3 * sr_hat_daily + ((g4 - 1.0) / 4.0) * (sr_hat_daily ** 2), 1e-8))
        z_dsr = ((sr_hat_daily - sr0_daily) * math.sqrt(T - 1)) / denom
        dsr_prob = float(norm.cdf(z_dsr))

        return {
            "dsr_probability": round(dsr_prob, 4),
            "dsr_pct": round(dsr_prob * 100.0, 2),
            "sr0_hurdle_annual": round(sr0_daily * math.sqrt(252.0), 4),
            "skewness": round(g3, 4),
            "kurtosis": round(g4, 4),
            "n_trials": N,
            "n_observations": T,
        }

    @staticmethod
    def compute_cpcv_and_pbo(
        block_sr_matrix: np.ndarray,
        n_test_blocks: int = 2,
    ) -> Dict[str, Any]:
        """
        Implements Lopez de Prado (2018) Combinatorial Purged Cross-Validation (CPCV)
        and Probability of Backtest Overfitting (PBO) across C(N, k) splits.
        Expects `block_sr_matrix` of shape (M_configs, N_blocks), where row 0 is the baseline strategy.
        """
        mat = np.asarray(block_sr_matrix, dtype=float)
        if mat.ndim != 2 or mat.shape[1] <= n_test_blocks:
            raise ValueError("block_sr_matrix must have shape (M_configs, N_blocks) with N_blocks > n_test_blocks")

        _, n_blocks = mat.shape
        combos = list(itertools.combinations(range(n_blocks), n_test_blocks))
        oos_srs_baseline: List[float] = []
        pbo_under_median_count = 0

        for test_blocks in combos:
            train_blocks = [b for b in range(n_blocks) if b not in test_blocks]
            is_scores = np.mean(mat[:, train_blocks], axis=1)
            oos_scores = np.mean(mat[:, list(test_blocks)], axis=1)

            best_is_idx = int(np.argmax(is_scores))
            winner_oos_sr = float(oos_scores[best_is_idx])
            median_oos_sr = float(np.median(oos_scores))

            if winner_oos_sr < median_oos_sr:
                pbo_under_median_count += 1

            oos_srs_baseline.append(float(oos_scores[0]))

        n_splits = len(combos)
        neg_count = sum(1 for s in oos_srs_baseline if s <= 0.0)
        return {
            "n_splits": n_splits,
            "cpcv_oos_median_sharpe": round(float(np.median(oos_srs_baseline)), 2),
            "cpcv_oos_mean_sharpe": round(float(np.mean(oos_srs_baseline)), 2),
            "negative_oos_paths_count": neg_count,
            "negative_oos_paths_pct": round((neg_count / n_splits) * 100.0, 2),
            "pbo_pct": round((pbo_under_median_count / n_splits) * 100.0, 2),
            "pbo_under_median_splits": pbo_under_median_count,
            "oos_sharpe_distribution": [round(x, 4) for x in oos_srs_baseline],
        }

    @staticmethod
    def compute_walk_forward_efficiency(
        is_cagrs: List[float],
        oos_cagrs: List[float],
        oos_period_returns_pct: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """
        Computes Rolling Walk-Forward Efficiency (WFE = Mean OOS CAGR / Mean IS CAGR)
        and stitched Out-of-Sample cumulative return across rolling WFA windows.
        """
        mean_is = float(np.mean(is_cagrs)) if is_cagrs else 0.0
        mean_oos = float(np.mean(oos_cagrs)) if oos_cagrs else 0.0
        wfe_pct = (mean_oos / max(mean_is, 1e-6)) * 100.0

        stitched_mult = 1.0
        if oos_period_returns_pct:
            for r_pct in oos_period_returns_pct:
                stitched_mult *= (1.0 + float(r_pct) / 100.0)
        stitched_oos_return_pct = (stitched_mult - 1.0) * 100.0

        return {
            "n_windows": len(oos_cagrs),
            "mean_is_cagr_pct": round(mean_is, 2),
            "mean_oos_cagr_pct": round(mean_oos, 2),
            "wfe_pct": round(wfe_pct, 1),
            "stitched_oos_return_pct": round(stitched_oos_return_pct, 2),
        }

    @staticmethod
    def run_monte_carlo_order_shuffle(
        trade_returns_pct: np.ndarray,
        n_runs: int = 10_000,
        slot_weight: float = 0.165,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Executes a 10,000-run Monte Carlo trade-sequence bootstrap and a deterministic
        front-loaded 6-loss stress test (placing the 6 worst trades of the 5-year period
        at Trades #1..#6 on Day 1).
        """
        trades = np.asarray(trade_returns_pct, dtype=float)
        n_trades = len(trades)
        if n_trades == 0:
            return {
                "n_runs": 0,
                "ruin_prob_pct": 0.0,
                "net_loss_prob_pct": 0.0,
                "median_return_pct": 0.0,
                "var_99_max_dd_pct": 0.0,
            }

        rng = np.random.default_rng(seed)
        mc_final_rets = np.zeros(n_runs, dtype=float)
        mc_max_dds = np.zeros(n_runs, dtype=float)
        ruin_50_count = 0
        loss_count = 0

        for i in range(n_runs):
            sampled = rng.choice(trades, size=n_trades, replace=True)
            port_multipliers = 1.0 + (sampled * float(slot_weight))
            eq_path = np.cumprod(port_multipliers)
            eq_full = np.concatenate([[1.0], eq_path])
            pks = np.maximum.accumulate(eq_full)
            dds = (eq_full - pks) / pks * 100.0
            mc_max_dds[i] = abs(float(np.min(dds)))
            mc_final_rets[i] = (eq_full[-1] - 1.0) * 100.0
            if np.min(eq_full) <= 0.50:
                ruin_50_count += 1
            if eq_full[-1] < 1.0:
                loss_count += 1

        sorted_asc = np.sort(trades)
        k_front = min(6, n_trades)
        worst_front_seq = np.concatenate([sorted_asc[:k_front], rng.permutation(sorted_asc[k_front:])])
        wf_eq = np.concatenate([[1.0], np.cumprod(1.0 + worst_front_seq * float(slot_weight))])
        wf_pks = np.maximum.accumulate(wf_eq)
        wf_max_dd = abs(float(np.min((wf_eq - wf_pks) / wf_pks * 100.0)))
        wf_initial_dip = (1.0 - float(np.min(wf_eq[: k_front + 1]))) * 100.0
        wf_final_ret = (wf_eq[-1] - 1.0) * 100.0

        return {
            "n_runs": n_runs,
            "n_trades": n_trades,
            "median_return_pct": round(float(np.median(mc_final_rets)), 2),
            "var_95_return_pct": round(float(np.percentile(mc_final_rets, 5)), 2),
            "var_99_return_pct": round(float(np.percentile(mc_final_rets, 1)), 2),
            "median_max_dd_pct": round(float(np.median(mc_max_dds)), 2),
            "var_95_max_dd_pct": round(float(np.percentile(mc_max_dds, 95)), 2),
            "var_99_max_dd_pct": round(float(np.percentile(mc_max_dds, 99)), 2),
            "ruin_prob_pct": round((ruin_50_count / n_runs) * 100.0, 4),
            "net_loss_prob_pct": round((loss_count / n_runs) * 100.0, 4),
            "front_loaded_6loss_initial_dip_pct": round(wf_initial_dip, 2),
            "front_loaded_6loss_max_dd_pct": round(wf_max_dd, 2),
            "front_loaded_6loss_final_return_pct": round(wf_final_ret, 2),
        }
