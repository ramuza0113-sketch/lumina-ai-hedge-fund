# -*- coding: utf-8 -*-
import numpy as np
from core.ai_hedge_fund.timesfm_forecaster import TimesFMForecaster
from core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper


def test_pinned_timesfm_config_modes():
    cfg_ret = TimesFMForecaster.get_pinned_config(forecast_mode="log_returns", max_horizon=8)
    assert cfg_ret["checkpoint"] == "google/timesfm-2.5-200m-pytorch"
    assert cfg_ret["forecast_config"]["infer_is_positive"] is False
    assert cfg_ret["forecast_config"]["use_continuous_quantile_head"] is True
    assert cfg_ret["forecast_config"]["fix_quantile_crossing"] is True

    cfg_px = TimesFMForecaster.get_pinned_config(forecast_mode="price_levels", max_horizon=8)
    assert cfg_px["forecast_config"]["infer_is_positive"] is True


def test_normalized_quantile_features_invariance_and_skew():
    f_base = TimesFMForecaster.compute_normalized_quantile_features(100.0, 95.0, 101.0, 110.0)
    f_scaled = TimesFMForecaster.compute_normalized_quantile_features(1000.0, 950.0, 1010.0, 1100.0)
    assert np.isclose(f_base["expected_move"], f_scaled["expected_move"])
    assert np.isclose(f_base["relative_uncertainty"], f_scaled["relative_uncertainty"])
    assert np.isclose(f_base["quantile_skew"], f_scaled["quantile_skew"])
    assert f_base["quantile_skew"] > 0.0  # upper wing (9.0) > lower wing (6.0)


def test_standalone_purged_calibration_and_ablation():
    rng = np.random.default_rng(123)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.014, size=450)))
    cal = TimesFMForecaster.evaluate_standalone_calibration(closes, horizon_days=5, context_len=90, embargo_days=5)
    assert cal["status"] == "OK"
    assert cal["n_folds"] >= 30
    lf = cal["models"]["lumina_forecaster"]
    assert 0.55 <= lf["coverage_q10_q90"] <= 0.98
    assert lf["mean_pinball_loss"] > 0.0

    X_a = rng.normal(size=(240, 8)).astype(np.float32)
    X_t = rng.normal(size=(240, 3)).astype(np.float32)
    y = (X_a[:, 0] + 1.2 * X_t[:, 2] > 0.0).astype(np.int32)
    abl = LightGBMGatekeeper.run_alpha158_ablation(X_a, X_t, y, embargo_samples=5)
    assert abl["status"] == "OK"
    assert "quantile_skew" in abl["tsfm_shap_share_pct"]
