# -*- coding: utf-8 -*-
"""
Integration & Contract Tests covering GitHub Issues #5, #6, #7, #8, and #9:
1. Issue #5: Method existence & end-to-end wiring for `get_market_breadth_regime`,
   `compute_symbol_summary`, and `get_order_book`.
2. Issue #6: Producer-to-consumer dictionary key contracts across `MacroLiquidityFeed`,
   `OptionsGexFeed`, `PortfolioManagerAgent`, `RiskManagerAgent`, `FactorOntology`, and `MarketScreener`.
3. Issue #7: Honest backend attribution when `timesfm`/`chronos` are not installed,
   plus root-sum-of-squares log-return quantile aggregation and model-quantile tail probabilities.
4. Issue #8: Neutral/unknown fallbacks when market data fails or track record is empty.
5. Issue #9: Genuine 3-leg `ib.bracketOrder` submission, `orderStatus` validation,
   and accurate single-order messaging in `IBKRClient.place_order`.
"""

import datetime
import os
import sys
import tempfile
import types
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd

from core.ai_hedge_fund.alpha158_engine import Alpha158Engine
from core.ai_hedge_fund.broker_client import (
    BaseBrokerClient,
    PaperTradingEngine,
    IBKRClient,
    KabuStationClient,
    fetch_level2_order_book,
)
from core.ai_hedge_fund.chronos_forecaster import ChronosForecaster
from core.ai_hedge_fund.dual_quantum_forecaster import DualQuantumForecaster
from core.ai_hedge_fund.factor_ontology import FactorOntology
from core.ai_hedge_fund.forecast_tracker import ForecastTracker
from core.ai_hedge_fund.fund_tear_sheet import FundTearSheet
from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
from core.ai_hedge_fund.macro_liquidity_feed import MacroLiquidityFeed
from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.market_screener import MarketScreener
from core.ai_hedge_fund.quant_reporter import QuantReporter
from core.ai_hedge_fund.timesfm_forecaster import TimesFMForecaster
from core.ai_hedge_fund.agents.portfolio_manager_agent import PortfolioManagerAgent
from core.ai_hedge_fund.agents.risk_manager_agent import RiskManagerAgent


def _make_synthetic_ohlcv(n: int = 120, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    closes = 150.0 * np.exp(np.cumsum(rng.normal(0.001, 0.015, size=n)))
    opens = closes * (1.0 + rng.normal(0.0, 0.003, size=n))
    highs = np.maximum(opens, closes) * (1.0 + np.abs(rng.normal(0.004, 0.002, size=n)))
    lows = np.minimum(opens, closes) * (1.0 - np.abs(rng.normal(0.004, 0.002, size=n)))
    vols = rng.integers(500_000, 3_000_000, size=n).astype(float)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
        index=dates,
    )


# ==============================================================================
# Issue #5: Defined methods & end-to-end execution paths
# ==============================================================================
def test_issue5_methods_exist_and_connect_to_ontology():
    # 1. MarketScreener.get_market_breadth_regime()
    MarketScreener._last_market_breadth = 0.40
    bear_reg = MarketScreener.get_market_breadth_regime()
    assert bear_reg["regime"] == "BEAR_CASH_SHIELD"
    assert bear_reg["max_slots_cap"] == 2

    MarketScreener._last_market_breadth = 0.72
    bull_reg = MarketScreener.get_market_breadth_regime()
    assert bull_reg["regime"] == "BULL_EXPANSION"
    assert bull_reg["max_slots_cap"] == 6

    # 2. Alpha158Engine.compute_symbol_summary() -> FactorOntology.build_ontology_bundle()
    synth_df = _make_synthetic_ohlcv(120)
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = synth_df
    with patch("yfinance.Ticker", return_value=fake_ticker):
        a158 = Alpha158Engine.compute_symbol_summary("NVDA")

    assert isinstance(a158.get("composite_z_score"), float)
    kf = a158.get("key_factors", {})
    assert all(k in kf for k in ("ROC_20", "RSV_20", "VMA_RATIO_20", "STD_20"))

    bundle = FactorOntology.build_ontology_bundle(
        stock_data={"symbol": "NVDA", "pe_trailing": 28.0, "roe": 24.0, "piotroski_f_score": 8},
        alpha158_summary=a158,
    )
    factor_ids = {entry["factor_id"] for entry in bundle["factors"]}
    assert {"alpha158_z_score", "roc_20", "rsv_20", "vol_spike_20", "volatility_20", "piotroski_f_score"}.issubset(factor_ids)

    # 3. get_order_book() on all BaseBrokerClient subclasses
    for cls_obj in (BaseBrokerClient, PaperTradingEngine, IBKRClient, KabuStationClient):
        assert hasattr(cls_obj, "get_order_book")

    intraday_df = _make_synthetic_ohlcv(40, seed=11)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_file = os.path.join(tmpdir, "paper_test.db")
        eng = PaperTradingEngine(db_path=db_file)
        with patch("yfinance.download", return_value=intraday_df):
            ob = eng.get_order_book("NVDA", depth=10)
        assert ob["depth_levels"] == 10
        assert "ofi_analysis" in ob
        assert "deep_ofi_score" in ob["ofi_analysis"]


# ==============================================================================
# Issue #6: Feed-to-Agent dictionary key alignment
# ==============================================================================
def test_issue6_macro_gex_and_cro_veto_key_alignment():
    # 1. MacroLiquidityFeed failure fallback -> neutral regime (NOT bullish!)
    MacroLiquidityFeed._cache.clear()
    with patch("pandas.read_csv", side_effect=RuntimeError("offline")):
        fb_macro = MacroLiquidityFeed.get_macro_status()
    assert fb_macro["regime"] == "NEUTRAL"
    assert fb_macro["net_liquidity_trend"] == "FLAT"
    assert fb_macro["liquidity_crunch"] is False

    reg_neutral = PortfolioManagerAgent.detect_market_regime({"macro_liquidity": fb_macro, "options_gex": {}})
    assert "中立" in reg_neutral["regime_name"]

    # 2. RISK_ON vs RISK_OFF regime classification
    reg_bull = PortfolioManagerAgent.detect_market_regime(
        {"macro_liquidity": {"regime": "RISK_ON", "net_liquidity_trend": "EXPANDING"}, "options_gex": {}}
    )
    assert "強気" in reg_bull["regime_name"]

    reg_tight = PortfolioManagerAgent.detect_market_regime(
        {"macro_liquidity": {"regime": "RISK_OFF", "net_liquidity_trend": "SHRINKING"}, "options_gex": {}}
    )
    assert "収縮" in reg_tight["regime_name"]

    # 3. OptionsGexFeed middle-dot "ネガティブ・ガンマ" & "乱気流警報" trigger turbulence + CRO liquidity-shock veto
    gex_turb = {
        "is_turbulence": True,
        "market_turbulence": "⚠️【市場乱気流警報: Negative Gamma】SPY Gamma Flip割れ (S&P500 ネガティブ・ガンマ)",
    }
    reg_turb = PortfolioManagerAgent.detect_market_regime({"macro_liquidity": fb_macro, "options_gex": gex_turb})
    assert "乱流" in reg_turb["regime_name"]

    cro_liq_veto = RiskManagerAgent.evaluate_risk(
        stock_data={"current_price": 100.0, "currency": "USD", "history_metrics": {"volatility_annualized_pct": 22.0}},
        analyst_results=[{"stance": "BULLISH"}] * 6,
        context_data={
            "macro_liquidity": {"regime": "RISK_OFF", "liquidity_crunch": True},
            "options_gex": gex_turb,
        },
    )
    assert cro_liq_veto["stance"] == "VETO"
    assert cro_liq_veto["max_allocation_pct"] == 0.0

    # 4. CRO OOD contradiction veto using council's `dual_quantum` + `deep_ofi` keys
    cro_ood_veto = RiskManagerAgent.evaluate_risk(
        stock_data={
            "current_price": 100.0,
            "currency": "USD",
            "piotroski_f_score": 4,
            "roe": 8.0,
            "history_metrics": {"volatility_annualized_pct": 22.0, "sma_200": 95.0},
        },
        analyst_results=[{"stance": "BULLISH"}] * 5,
        context_data={
            "macro_liquidity": fb_macro,
            "options_gex": {"is_turbulence": False},
            "dual_quantum": {"consensus_status": "DOUBLE_BULLISH", "ensemble_expected_return_pct": 4.5},
            "deep_ofi": {"deep_ofi_score": -52.0},
        },
    )
    assert cro_ood_veto["stance"] == "VETO"
    assert cro_ood_veto["max_allocation_pct"] == 0.0


# ==============================================================================
# Issue #7: Backend attribution & log-return quantile aggregation
# ==============================================================================
def test_issue7_fallback_labels_and_log_return_quantile_scaling():
    synth_df = _make_synthetic_ohlcv(140, seed=21)
    with patch.object(TimesFMForecaster, "get_stock_data", return_value=synth_df), patch.object(
        TimesFMForecaster, "get_openbb_consensus", return_value={}
    ), patch.object(TimesFMForecaster, "_infer_native_timesfm_trajectory", return_value=None), patch.object(
        ChronosForecaster, "get_pipeline", return_value=None
    ), patch.object(ChronosForecaster, "get_stock_data", return_value=synth_df):
        dq = DualQuantumForecaster.forecast("AAPL", horizon_days=5)

    assert dq["is_foundation_ensemble"] is False
    assert dq["backends"]["google_timesfm"] == "parametric_log_return_fallback"
    assert dq["backends"]["amazon_chronos"] == "parametric_autoregressive_fallback"
    assert "パラメトリック" in dq["models"]["google_timesfm"]["summary_text"]
    assert "パラメトリック" in dq["models"]["amazon_chronos"]["summary_text"]
    assert "Google TimesFM と Amazon Chronos の双方が上昇予測で完全合意" not in dq["summary_desc"]

    # Verify native log-return mode uses root-sum-of-squares (sqrt(h)) instead of linear h summation
    fake_model = MagicMock()
    # Constant step median = 0.0, step 10% = -0.02, step 90% = +0.02 across 4 steps
    # Linear sum would give -0.08 / +0.08; RSS gives -0.02*sqrt(4) = -0.04 / +0.04
    fake_point = np.zeros((1, 4), dtype=np.float32)
    fake_quant = np.zeros((1, 4, 9), dtype=np.float32)
    fake_quant[0, :, 1] = -0.02
    fake_quant[0, :, 8] = 0.02
    fake_model.forecast.return_value = (fake_point, fake_quant)

    closes = np.full(60, 100.0, dtype=float)
    with patch.object(TimesFMForecaster, "_get_native_timesfm_model", return_value=fake_model):
        traj = TimesFMForecaster._infer_native_timesfm_trajectory(
            closes=closes,
            horizon_days=4,
            now=datetime.datetime(2026, 11, 20),
            forecast_mode="log_returns",
        )
    assert traj is not None
    expected_upper = round(100.0 * float(np.exp(0.04)), 2)  # ~104.08 (NOT 108.33!)
    assert np.isclose(traj[-1]["upper_80"], expected_upper, atol=0.05)


# ==============================================================================
# Issue #8: Neutral / unknown defaults on missing data or empty track record
# ==============================================================================
def test_issue8_neutral_fallbacks_when_data_or_track_record_missing():
    LeadLagAnalyzer._cache.clear()
    with patch("yfinance.download", return_value=pd.DataFrame()):
        ll_fail = LeadLagAnalyzer.analyze_lead_lag("NVDA")
    assert ll_fail["lead_lag_signal"] == "UNKNOWN"
    assert ll_fail["is_statistically_significant"] is False
    assert ll_fail["correlation"] is None
    assert ll_fail["granger_pvalue"] is None

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_file = os.path.join(tmpdir, "empty_track.db")
        eng = PaperTradingEngine(db_path=db_file)
        with patch.object(eng, "get_usdjpy_rate", return_value=155.0), patch.object(
            eng,
            "get_portfolio_summary",
            return_value={
                "usdjpy_rate": 155.0,
                "total_equity_jpy": 1000000.0,
                "total_portfolio_value_usd": 6451.61,
                "total_realized_pnl_usd": 0.0,
                "total_unrealized_pnl_usd": 0.0,
            },
        ):
            kpis = FundTearSheet.generate_tear_sheet(broker=eng, save_image=False)
            assert kpis["has_track_record"] is False
            assert kpis["total_trades_count"] == 0
            assert kpis["win_rate_pct"] is None
            assert kpis["sharpe_ratio"] is None

            q_rep = QuantReporter.compute_metrics(pd.Series(dtype=float), broker_engine=eng)
            assert q_rep["has_track_record"] is False
            assert q_rep["closed_trades"] == 0
            assert q_rep["win_rate"] is None
            assert "4.58" not in q_rep["summary_line"]

    with patch.object(ForecastTracker, "load_history", return_value=[]):
        ft = ForecastTracker.get_track_record_summary()
    assert ft["has_track_record"] is False
    assert ft["verified_count"] == 0
    assert ft["accuracy_rate_pct"] is None
    assert "83.3" not in ft["note_markdown"]


# ==============================================================================
# Issue #9: IBKRClient.place_order 3-leg bracketOrder & orderStatus check
# ==============================================================================
def test_issue9_ibkr_bracket_order_and_status_check():
    fake_ib = MagicMock()
    fake_ib.isConnected.return_value = True

    def _mk_order(oid: int, otype: str):
        o = types.SimpleNamespace(orderId=oid, orderType=otype, lmtPrice=100.0, tif="DAY")
        return o

    fake_ib.bracketOrder.return_value = [
        _mk_order(101, "LMT"),
        _mk_order(102, "LMT"),
        _mk_order(103, "STP"),
    ]

    placed_orders = []

    def _place_order_side_effect(contract, order):
        placed_orders.append(order)
        return types.SimpleNamespace(
            order=order,
            orderStatus=types.SimpleNamespace(status="Submitted"),
        )

    fake_ib.placeOrder.side_effect = _place_order_side_effect

    fake_ib_insync = types.SimpleNamespace(
        Stock=lambda *args, **kwargs: types.SimpleNamespace(symbol=args[0]),
        LimitOrder=lambda action, qty, lmt: _mk_order(201, "LMT"),
        MarketOrder=lambda action, qty: _mk_order(202, "MKT"),
    )

    client = IBKRClient(host="127.0.0.1", port=7497, client_id=99)
    with patch.object(client, "_get_connection", return_value=fake_ib), patch.dict(
        sys.modules, {"ib_insync": fake_ib_insync}
    ), patch.object(MarketDataFeed, "get_realtime_price", return_value=150.0):
        # 1. Full 3-leg bracket order on BUY with target_price + stop_loss_price
        res_b = client.place_order(
            symbol="NVDA",
            side="BUY",
            quantity=5,
            order_type="MARKET",
            target_price=180.0,
            stop_loss_price=135.0,
        )
        assert res_b["success"] is True
        assert res_b["type"] == "SERVER_SIDE_BRACKET_OCO"
        assert len(placed_orders) == 3
        assert placed_orders[0].orderType == "MKT"
        assert placed_orders[1].tif == "GTC"
        assert placed_orders[2].tif == "GTC"

        # 2. Single order with only stop_loss_price must NOT claim bracket in message
        placed_orders.clear()
        res_s = client.place_order(
            symbol="NVDA",
            side="BUY",
            quantity=5,
            order_type="MARKET",
            stop_loss_price=135.0,
        )
        assert res_s["success"] is True
        assert len(placed_orders) == 1
        assert "ブラケット" not in res_s["message"]

        # 3. Cancelled orderStatus returns success=False
        fake_ib.placeOrder.side_effect = lambda c, o: types.SimpleNamespace(
            order=o,
            orderStatus=types.SimpleNamespace(status="Cancelled"),
        )
        res_cancel = client.place_order(symbol="NVDA", side="BUY", quantity=5, order_type="MARKET")
        assert res_cancel["success"] is False


# ==============================================================================
# Issue #10: GEMINI_API_KEY -> google_api_key wiring across state_manager & agents
# ==============================================================================
def test_issue10_gemini_api_key_reaches_agents(monkeypatch):
    import google
    from core import state_manager
    from core.ai_hedge_fund.agents.buffett_agent import BuffettAgent

    monkeypatch.setenv("GEMINI_API_KEY", "test_placeholder_gemini_key_123")
    cfg = state_manager.load_app_settings()
    assert cfg["gemini_api_key"] == "test_placeholder_gemini_key_123"
    assert cfg["google_api_key"] == "test_placeholder_gemini_key_123"

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = types.SimpleNamespace(
        text='{"stance": "BULLISH", "score": 82, "dialogue": "Strong moat"}'
    )
    mock_client_cls = MagicMock(return_value=fake_client)
    fake_genai_types = types.ModuleType("google.genai.types")
    fake_genai_types.GenerateContentConfig = MagicMock(return_value={})
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = mock_client_cls
    fake_genai.types = fake_genai_types

    monkeypatch.setattr(google, "genai", fake_genai, raising=False)
    with patch.dict(
        sys.modules,
        {"google.genai": fake_genai, "google.genai.types": fake_genai_types},
    ):
        res = BuffettAgent._call_gemini_json("Evaluate KO")
    mock_client_cls.assert_called_once_with(api_key="test_placeholder_gemini_key_123")
    assert res is not None
    assert res["stance"] == "BULLISH"


# ==============================================================================
# Issue #11: Dividend yield scale (no 100x inflation on LMT / MSFT / NVDA / TSE)
# ==============================================================================
def test_issue11_dividend_yield_scale_normalization():
    MarketDataFeed._cache.clear()
    synth_df = _make_synthetic_ohlcv(60, seed=31)

    # Case A: LMT in yfinance 1.8.0 (dividendYield=2.49 [%], trailingAnnualDividendYield=0.0239 [fraction])
    fake_lmt = MagicMock()
    fake_lmt.info = {
        "currentPrice": 520.0,
        "currency": "USD",
        "dividendYield": 2.49,
        "trailingAnnualDividendYield": 0.0239,
        "dividendRate": 12.60,
    }
    fake_lmt.history.return_value = synth_df
    with patch("yfinance.Ticker", return_value=fake_lmt):
        d_lmt = MarketDataFeed.get_stock_data("LMT", force_refresh=True)
    assert 2.30 <= d_lmt["dividend_yield"] <= 2.60  # NOT 249.0!

    # Case B: Ultra-low dividend tech stock (NVDA: 0.02% yield -> must NOT become 2.0%)
    fake_nvda = MagicMock()
    fake_nvda.info = {
        "currentPrice": 140.0,
        "currency": "USD",
        "dividendYield": 0.03,
        "trailingAnnualDividendYield": 0.00028,
        "dividendRate": 0.04,
    }
    fake_nvda.history.return_value = synth_df
    with patch("yfinance.Ticker", return_value=fake_nvda):
        d_nvda = MarketDataFeed.get_stock_data("NVDA", force_refresh=True)
    assert 0.01 <= d_nvda["dividend_yield"] <= 0.10  # ~0.03%, NOT 3.0%!

    # Case C: Corrupt >25% outlier rejected safely to 0.0
    fake_bad = MagicMock()
    fake_bad.info = {"currentPrice": 10.0, "currency": "USD", "dividendYield": 249.0}
    fake_bad.history.return_value = synth_df
    with patch("yfinance.Ticker", return_value=fake_bad):
        d_bad = MarketDataFeed.get_stock_data("BADX", force_refresh=True)
    assert d_bad["dividend_yield"] == 0.0


# ==============================================================================
# Additional Cross-Module Contract Guard: LightGBMGatekeeper, OpenBBProvider & MarketDataFeed
# ==============================================================================
def test_lightgbm_openbb_and_stock_data_contracts():
    from core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper
    from core.openbb_provider import OpenBBProvider

    # 1. LightGBMGatekeeper must handle correlation=None & pe_trailing=None cleanly
    res_lgb = LightGBMGatekeeper.evaluate_gate(
        ticker="NVDA",
        dual_quantum={"consensus_status": "NEUTRAL", "current_price": 100.0, "models": {}},
        lead_lag_data={"lead_lag_signal": "UNKNOWN", "correlation": None},
        context_data={
            "macro_liquidity": {"regime": "RISK_OFF"},
            "options_gex": {"is_turbulence": True, "market_turbulence": "⚠️【市場乱気流警報: Negative Gamma】"},
        },
        stock_data={"pe_trailing": None, "roe": None},
    )
    assert isinstance(res_lgb["win_probability"], float)

    # 2. OpenBBProvider must return neutral/unknown fallbacks (not "+15%..+30%" or score=75) when offline
    with patch.object(OpenBBProvider, "_get_cached_data", return_value=None), patch.object(
        OpenBBProvider, "_set_cached_data", return_value=None
    ), patch.object(OpenBBProvider, "_get_obb", return_value=None), patch(
        "yfinance.Ticker"
    ) as mock_tk, patch("pandas.read_csv", side_effect=RuntimeError("offline")):
        mock_tk.return_value.info = {}
        mock_tk.return_value.history.return_value = pd.DataFrame()
        cathie = OpenBBProvider.get_cathie_growth_intel("AAPL")
        mom = OpenBBProvider.get_momentum_intel("AAPL")
        soros = OpenBBProvider.get_soros_macro_intel()
    assert "+15.0%" not in cathie["target_upside_pct"]
    assert mom["can_slim_score"] == 50
    assert "5.28%" not in soros["us_10y_yield"]
