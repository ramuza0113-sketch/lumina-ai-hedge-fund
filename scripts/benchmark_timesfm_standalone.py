# -*- coding: utf-8 -*-
"""
benchmark_timesfm_standalone.py
Reproducible standalone calibration & LightGBM TreeSHAP ablation benchmark for
Lumina Capital's probabilistic forecasting layer (TimesFM 2.5 / Log-Return Quantiles).

Evaluates:
  1. Pinned TimesFM 2.5 (`google/timesfm-2.5-200m-pytorch`) ForecastConfig inspection
  2. Purged & Embargoed (`embargo=5d`) standalone q10-q90 coverage & Pinball Loss
     across Calm vs. High-Volatility regimes against Random Walk, Rolling Historical
     Quantiles, and GARCH(1,1)-EWMA baselines
  3. Scale-invariant normalized quantile feature extraction (`expected_move`,
     `relative_uncertainty`, `quantile_skew`) + LightGBM TreeSHAP ablation against Alpha158-style factors
"""

import argparse
import json
import os
import sys
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.ai_hedge_fund.timesfm_forecaster import TimesFMForecaster
from core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper


def _generate_regime_switching_prices(n_days: int = 750, seed: int = 42) -> np.ndarray:
    """Generate a realistic GARCH-like regime-switching equity price path (zero look-ahead)."""
    rng = np.random.default_rng(seed)
    rets = np.zeros(n_days, dtype=float)
    sigma = 0.012
    for t in range(1, n_days):
        high_vol_regime = (200 <= t <= 340) or (520 <= t <= 630)
        target_vol = 0.026 if high_vol_regime else 0.011
        sigma = np.sqrt(0.10 * (rets[t - 1] ** 2) + 0.85 * (sigma ** 2) + 0.05 * (target_vol ** 2))
        drift = -0.0006 if high_vol_regime else 0.0005
        rets[t] = drift + sigma * rng.standard_t(df=6) * 0.82
    return 100.0 * np.exp(np.cumsum(rets))


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone TimesFM / Quantile Calibration & Ablation Benchmark")
    parser.add_argument("--live", action="store_true", help="Also evaluate post-cutoff live yfinance tickers (SPY, NVDA, 7203.T)")
    parser.add_argument("--horizon", type=int, default=5, help="Forecast horizon in trading days (default: 5)")
    args = parser.parse_args()

    print("=" * 78)
    print("1. PINNED TIMESFM 2.5 CHECKPOINT & FORECAST CONFIG")
    print("=" * 78)
    pinned = TimesFMForecaster.get_pinned_config(forecast_mode="log_returns", max_horizon=max(args.horizon, 8))
    print(json.dumps(pinned, indent=2))

    print("\n" + "=" * 78)
    print(f"2. STANDALONE PURGED WALK-FORWARD CALIBRATION (horizon={args.horizon}d, embargo={args.horizon}d)")
    print("=" * 78)
    synth_px = _generate_regime_switching_prices(n_days=800, seed=42)
    cal = TimesFMForecaster.evaluate_standalone_calibration(
        closes=synth_px,
        horizon_days=args.horizon,
        context_len=90,
        embargo_days=args.horizon,
    )
    print(f"Folds evaluated (non-overlapping purged): {cal['n_folds']} | Target q10-q90 coverage: 80.0%\n")
    print(f"{'Model':<26} | {'q10-q90 Cov':>11} | {'Calm Cov':>9} | {'HighVol Cov':>11} | {'Pinball Loss':>12}")
    print("-" * 78)
    for m_name, m_stats in cal["models"].items():
        print(
            f"{m_name:<26} | "
            f"{m_stats['coverage_q10_q90'] * 100:10.1f}% | "
            f"{(m_stats['calm_regime_coverage'] or 0.0) * 100:8.1f}% | "
            f"{(m_stats['high_vol_regime_coverage'] or 0.0) * 100:10.1f}% | "
            f"{m_stats['mean_pinball_loss']:12.6f}"
        )

    if args.live:
        for sym in ["SPY", "NVDA", "7203.T"]:
            df = TimesFMForecaster.get_stock_data(sym, period="2y")
            if df is not None and len(df) > 150:
                live_cal = TimesFMForecaster.evaluate_standalone_calibration(
                    closes=df["Close"].values,
                    horizon_days=args.horizon,
                    context_len=90,
                    embargo_days=args.horizon,
                )
                lf = live_cal.get("models", {}).get("lumina_forecaster", {})
                rw = live_cal.get("models", {}).get("random_walk", {})
                print(
                    f"\n[Live {sym}] Folds={live_cal.get('n_folds')} | "
                    f"Lumina Cov={lf.get('coverage_q10_q90', 0)*100:.1f}% (Pinball={lf.get('mean_pinball_loss', 0):.5f}) vs "
                    f"RW Cov={rw.get('coverage_q10_q90', 0)*100:.1f}% (Pinball={rw.get('mean_pinball_loss', 0):.5f})"
                )

    print("\n" + "=" * 78)
    print("3. LIGHTGBM GATEKEEPER ABLATION: ALPHA158 ALONE VS. ALPHA158 + NORMALIZED TSFM")
    print("=" * 78)
    rng = np.random.default_rng(7)
    n_obs = 600
    X_alpha = rng.normal(0.0, 1.0, size=(n_obs, 12)).astype(np.float32)
    exp_move = (0.015 * X_alpha[:, 0] + rng.normal(0.0, 0.012, size=n_obs)).astype(np.float32)
    rel_unc = np.abs(0.045 + 0.02 * X_alpha[:, 1] + rng.normal(0.0, 0.01, size=n_obs)).astype(np.float32)
    q_skew = np.clip(0.35 * rng.normal(0.0, 1.0, size=n_obs), -1.0, 1.0).astype(np.float32)
    X_tsfm = np.column_stack([exp_move, rel_unc, q_skew]).astype(np.float32)
    latent = 0.7 * X_alpha[:, 0] - 0.5 * X_alpha[:, 2] + 0.95 * q_skew - 8.0 * (rel_unc - 0.045) + 12.0 * exp_move
    probs = 1.0 / (1.0 + np.exp(-latent))
    y_bin = (rng.uniform(0.0, 1.0, size=n_obs) < probs).astype(np.int32)

    ablation = LightGBMGatekeeper.run_alpha158_ablation(
        X_alpha=X_alpha,
        X_tsfm_norm=X_tsfm,
        y_labels=y_bin,
        embargo_samples=args.horizon,
    )
    print(json.dumps(ablation, indent=2))


if __name__ == "__main__":
    main()
