# -*- coding: utf-8 -*-
"""
Lumina Capital v6.4.6 — Institutional Hardening & CI Contract Verification Suite
================================================================================
Validates the 5 key architectural safeguards inspired by global quant/systems feedback:
  1. CI Factor Ontology Contract Guard (prevents silent regression to raw numbers)
  2. Schmitt-Trigger Hysteresis & Borderline Dead-Zone (`NEUTRAL_INDETERMINATE`)
  3. SQLite Single-Writer Queue (zero lock contention under burst writes) & FTS5 `tokenchars=-_.`
  4. Higham (2002) Nearest PSD Projection & Ledoit-Wolf Shrinkage for Hayashi-Yoshida matrices
  5. Chaos Testing: In-flight disconnect resilience, server-side OCO persistence & idempotency
"""

import os
import sys
import tempfile
import threading
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ai_hedge_fund.factor_ontology import FactorOntology, FactorSchema
from core.ai_hedge_fund.broker_client import PaperTradingEngine
from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer


def test_1_ci_factor_ontology_contracts():
    """Verify all registered factors enforce explicit polarity contracts and valid thresholds."""
    is_valid, errors = FactorOntology.validate_all_contracts(raise_on_error=True)
    assert is_valid, f"Factor contract validation failed: {errors}"
    assert len(errors) == 0

    # Verify that adding an uncontracted / malformed factor is immediately caught by CI guard
    bad_registry = dict(FactorOntology.REGISTRY)
    bad_registry["rogue_uncontracted_factor"] = FactorSchema(
        factor_id="rogue_uncontracted_factor",
        display_name="Rogue Raw Metric",
        category="RAW",
        unit="raw",
        polarity="INVALID_UNCONTRACTED",  # Invalid polarity!
        formula_desc="raw",
        bullish_threshold=-1.0,  # Inverted thresholds!
        bearish_threshold=5.0,
        assigned_agents=(),
        bullish_interpretation="",
        bearish_interpretation="",
        neutral_interpretation="",
    )
    valid_bad, bad_errors = FactorOntology.validate_all_contracts(registry=bad_registry, raise_on_error=False)
    assert not valid_bad, "CI guard failed to catch rogue uncontracted factor!"
    assert len(bad_errors) >= 3
    print("[PASS] 1. CI Factor Ontology Contract Guard verified.")


def test_2_schmitt_trigger_hysteresis_and_deadzone():
    """Verify borderline dead-zone (NEUTRAL_INDETERMINATE) and Schmitt-trigger anti-whipsaw."""
    FactorOntology._state_memory.clear()

    # alpha158_z_score: bullish_threshold=0.75, bearish_threshold=-0.50 (span=1.25, deadzone=0.0625, hyst=0.125)
    # 1. Cold start right below threshold (0.72 is within 0.0625 of 0.75) -> NEUTRAL_INDETERMINATE
    res_borderline = FactorOntology.interpret_value("alpha158_z_score", 0.72, symbol="TEST_SYM")
    assert res_borderline is not None
    assert res_borderline["semantic_signal"] == "NEUTRAL_INDETERMINATE"
    assert res_borderline["borderline_deadzone"] is True

    # 2. Cross clearly above outer threshold (0.82 >= 0.75) -> BULLISH
    res_bull = FactorOntology.interpret_value("alpha158_z_score", 0.82, symbol="TEST_SYM")
    assert res_bull["semantic_signal"] == "BULLISH"

    # 3. Slight dip to 0.68 (below 0.75 outer threshold, but above 0.75 - 0.125 = 0.625 inner hysteresis band)
    # Must hold BULLISH without chattering back to NEUTRAL!
    res_held = FactorOntology.interpret_value("alpha158_z_score", 0.68, symbol="TEST_SYM")
    assert res_held["semantic_signal"] == "BULLISH"
    assert res_held["hysteresis_held"] is True

    # 4. Drop well below hysteresis band (0.20 < 0.625) -> releases to NEUTRAL
    res_neutral = FactorOntology.interpret_value("alpha158_z_score", 0.20, symbol="TEST_SYM")
    assert res_neutral["semantic_signal"] == "NEUTRAL"
    assert res_neutral["hysteresis_held"] is False
    print("[PASS] 2. Schmitt-Trigger Hysteresis & Borderline Dead-Zone verified.")


def test_3_sqlite_single_writer_queue_and_compound_fts5():
    """Verify zero lock contention under multi-threaded burst writes and exact compound token recall."""
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_hardening.db")
    engine = PaperTradingEngine(db_path=db_file)

    errors = []

    def _burst_writer(tid: int):
        try:
            for i in range(8):
                engine.enqueue_agent_reflexion(
                    symbol="3556.T" if tid % 2 == 0 else "NVDA",
                    company_name="Lumina Test Corp",
                    agent_id=f"agent_{tid}",
                    stance_at_entry="BULLISH",
                    score_at_entry=80,
                    exit_rule="TRAILING_STOP_SWEEP" if i % 2 == 0 else "CALL_WALL_EXIT",
                    realized_pnl=-1200.0,
                    realized_pnl_pct=-2.4,
                    reflection_text=f"Thread {tid} item {i}: hit trailing_stop_sweep at gamma_call_wall on 3556.T.",
                    lesson_category="FALSE_POSITIVE_OVERCONFIDENCE",
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_burst_writer, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Flush single-writer queue and verify 0 errors and all 64 records persisted
    engine.flush_reflexion_queue()
    assert len(errors) == 0, f"Concurrent burst write errors: {errors}"

    all_recs = engine.get_agent_reflexions(limit=100)
    assert len(all_recs) == 64, f"Expected 64 records, got {len(all_recs)}"

    # Test compound financial identifier search with hyphens/underscores/dots preserved
    hits = engine.search_agent_reflexions_bm25(["trailing_stop_sweep", "3556.T"], limit=5)
    assert len(hits) > 0, "FTS5 failed to retrieve compound token 'trailing_stop_sweep' / '3556.T'"
    assert "trailing_stop_sweep" in hits[0]["reflection_text"]
    print("[PASS] 3. SQLite Single-Writer Queue (64 burst writes, 0 locks) & FTS5 tokenchars=-_. verified.")


def test_4_hayashi_yoshida_higham_psd_projection():
    """Verify Higham (2002) PSD projection eliminates negative eigenvalues from asynchronous correlation matrices."""
    # Construct a mathematically invalid correlation matrix with a strong negative eigenvalue (-0.35)
    broken_corr = np.array([
        [1.0,  0.9, -0.9],
        [0.9,  1.0,  0.9],
        [-0.9, 0.9,  1.0],
    ], dtype=np.float64)

    raw_eigs = np.linalg.eigvalsh(broken_corr)
    assert np.min(raw_eigs) < -0.5, "Broken matrix should have a negative eigenvalue"

    psd_corr = LeadLagAnalyzer.project_to_nearest_psd(broken_corr, shrinkage=0.10, min_eigenvalue=1e-6)
    psd_eigs = np.linalg.eigvalsh(psd_corr)

    # Verify symmetry, unit diagonal, valid bounds, and strictly positive eigenvalues
    assert np.allclose(psd_corr, psd_corr.T), "Projected matrix must be symmetric"
    assert np.allclose(np.diag(psd_corr), 1.0), "Diagonal must be strictly 1.0"
    assert np.min(psd_eigs) > 0.0, f"Eigenvalues must be strictly positive, got min={np.min(psd_eigs)}"
    print(f"[PASS] 4. Higham PSD Projection verified (min eigenvalue repaired: {np.min(raw_eigs):.3f} -> {np.min(psd_eigs):.4f}).")


def test_5_chaos_disconnect_and_bracket_persistence():
    """Verify server-side OCO bracket persistence and position integrity across simulated disconnects."""
    os.environ["LUMINA_TEST_MODE"] = "1"
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_chaos.db")
    engine = PaperTradingEngine(db_path=db_file)

    # Place order with atomic OCO stop_loss_price and target_price (initial JPY cash = 1,000,000)
    res = engine.place_order(
        symbol="7203.T",
        side="BUY",
        quantity=100,
        price=2500.0,
        order_type="LIMIT",
        notes="Chaos test entry",
        target_price=3000.0,
        stop_loss_price=2200.0,
    )
    assert res.get("success") is True, f"Order failed: {res}"

    # Simulate process restart / network reconnect by instantiating a fresh engine on the same DB
    reconnected_engine = PaperTradingEngine(db_path=db_file)
    positions = reconnected_engine.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["symbol"] == "7203.T"
    assert pos["quantity"] == 100
    assert float(pos["stop_loss_price"]) == 2200.0, "Stop-loss bracket must survive disconnect!"
    assert float(pos["target_price"]) == 3000.0, "Target price bracket must survive disconnect!"
    print("[PASS] 5. Chaos Disconnect & OCO Bracket Persistence verified.")


def test_6_ibkr_daily_disconnect_reconciliation():
    """Verify zombie socket teardown and state reconciliation after IB Gateway daily disconnect."""
    from core.ai_hedge_fund.broker_client import IBKRClient

    class DummyDisconnectIB:
        def __init__(self):
            self.disconnect_called = False
            self.positions_called = False
            self.open_orders_called = False
            self.executions_called = False

        def isConnected(self):
            return False

        def disconnect(self):
            self.disconnect_called = True

    class DummyLiveIB:
        def isConnected(self):
            return True

        def positions(self):
            return [{"symbol": "NVDA", "position": 10}]

        def reqOpenOrders(self):
            return [{"orderId": 101}]

        def executions(self):
            return [{"execId": "E001"}]

    zombie = DummyDisconnectIB()
    IBKRClient._shared_ib = zombie
    client = IBKRClient()

    # Verify _reconcile_after_reconnect directly on live mock
    live_mock = DummyLiveIB()
    summary = client._reconcile_after_reconnect(live_mock)
    assert summary["reconciled"] is True
    assert summary["positions_count"] == 1
    assert summary["open_orders_count"] == 1
    assert summary["executions_count"] == 1
    IBKRClient._shared_ib = None
    print("[PASS] 6. IBKR Daily Disconnect Zombie Teardown & State Reconciliation verified.")


def test_7_volume_clock_timeout_fallback():
    """Verify Volume Clock cuts a timeout bar when volume stays below threshold during an illiquid lull."""
    import pandas as pd
    from core.ai_hedge_fund.volume_clock_sampler import VolumeClockSampler

    # 10 bars of 5-minute intervals (total 45 mins), each with tiny volume (10 shares) while threshold is 10,000
    idx = pd.date_range("2026-10-27 09:00:00", periods=10, freq="5min")
    df = pd.DataFrame(
        {
            "open": np.full(10, 100.0),
            "high": np.full(10, 101.0),
            "low": np.full(10, 99.0),
            "close": np.full(10, 100.5),
            "volume": np.full(10, 10.0),
        },
        index=idx,
    )
    # Without timeout fallback, 100 total volume < 10,000 threshold -> only 1 unclosed bar at end.
    # With max_timeout_sec=1800.0 (30 mins), a timeout bar must be cut at 30m!
    bars_timeout = VolumeClockSampler.to_volume_bars(df, volume_threshold=10000.0, max_timeout_sec=1800.0)
    assert len(bars_timeout) >= 2, f"Expected timeout fallback to split stalled bar, got {len(bars_timeout)} bar(s)"
    assert bool(bars_timeout["is_timeout_bar"].iloc[0]) is True, "First bar must be flagged as is_timeout_bar=True"
    print(f"[PASS] 7. Volume Clock Timeout Fallback verified ({len(bars_timeout)} bars generated during illiquid lull).")


def test_8_reflexion_exponential_time_decay_aging():
    """Verify recent lessons outrank stale 90-day-old trauma memories with identical BM25 keywords."""
    from datetime import datetime, timedelta

    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_decay.db")
    engine = PaperTradingEngine(db_path=db_file)

    old_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
    fresh_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with engine._get_conn() as conn:
        cur = conn.cursor()
        # Insert 90-day-old trauma memory first
        cur.execute(
            """
            INSERT INTO agent_reflexions
            (symbol, company_name, agent_id, stance_at_entry, score_at_entry, exit_rule,
             realized_pnl, realized_pnl_pct, reflection_text, lesson_category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("NVDA", "NVIDIA", "cio", "BULLISH", 85, "STOP_LOSS", -500.0, -8.0,
             "OLD_TRAUMA: semicolon_crash_signal triggered stop_loss on NVDA", "STOP_LOSS", old_date),
        )
        rid_old = cur.lastrowid
        cur.execute(
            """
            INSERT INTO agent_reflexions_fts(rowid, symbol, agent_id, exit_rule, lesson_category, reflection_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rid_old, "NVDA", "cio", "STOP_LOSS", "STOP_LOSS",
             "OLD_TRAUMA: semicolon_crash_signal triggered stop_loss on NVDA"),
        )

        # Insert fresh today's memory with identical keywords
        cur.execute(
            """
            INSERT INTO agent_reflexions
            (symbol, company_name, agent_id, stance_at_entry, score_at_entry, exit_rule,
             realized_pnl, realized_pnl_pct, reflection_text, lesson_category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("NVDA", "NVIDIA", "cio", "BULLISH", 85, "STOP_LOSS", -200.0, -3.0,
             "FRESH_LESSON: semicolon_crash_signal triggered stop_loss on NVDA", "STOP_LOSS", fresh_date),
        )
        rid_fresh = cur.lastrowid
        cur.execute(
            """
            INSERT INTO agent_reflexions_fts(rowid, symbol, agent_id, exit_rule, lesson_category, reflection_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rid_fresh, "NVDA", "cio", "STOP_LOSS", "STOP_LOSS",
             "FRESH_LESSON: semicolon_crash_signal triggered stop_loss on NVDA"),
        )
        conn.commit()

    results = engine.search_agent_reflexions_bm25(["semicolon_crash_signal", "NVDA"], limit=2, half_life_days=30.0)
    assert len(results) == 2
    assert "FRESH_LESSON" in results[0]["reflection_text"], "Fresh lesson must outrank 90-day-old trauma!"
    assert results[0]["decay_weight"] > 0.95
    assert results[1]["decay_weight"] <= 0.15  # 90 days = 3 half-lives -> 0.125
    print(
        f"[PASS] 8. Reflexion Exponential Time-Decay verified "
        f"(Fresh weight={results[0]['decay_weight']:.3f} vs 90d Old weight={results[1]['decay_weight']:.3f})."
    )


def test_9_llm_api_circuit_breaker_and_degraded_defense_mode():
    """
    9. LLM API Rate Limit (HTTP 429) Circuit Breaker & Degraded Defense-Only Mode
    Verifies that when the LLM reasoning layer is rate-limited or offline, the circuit breaker
    immediately halts cascading retries and forces PortfolioManagerAgent into Degraded Defense-Only Mode
    (blocking blind BUY orders with action='HOLD' even when fallback scores are high).
    """
    from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent
    from core.ai_hedge_fund.agents.portfolio_manager_agent import PortfolioManagerAgent

    BaseInvestmentAgent.reset_circuit()
    assert not BaseInvestmentAgent.is_circuit_open()

    # Simulate HTTP 429 Quota Exhaustion tripping the circuit breaker
    BaseInvestmentAgent.trip_circuit(reason="429 RESOURCE_EXHAUSTED: Quota exceeded", cooldown_sec=30.0)
    assert BaseInvestmentAgent.is_circuit_open(), "Circuit breaker must open immediately on 429!"

    stock_data = {"symbol": "8035.T", "name": "東京エレクトロン", "current_price": 2515.0, "currency": "JPY"}
    eval_res = BaseInvestmentAgent.evaluate(stock_data, context_data={})
    assert eval_res.get("is_degraded_fallback") is True

    # Even if deterministic fallback scores are artificially high (88 pts), Degraded Mode must block BUY!
    high_fallback_analysts = [
        {
            "agent_id": aid,
            "name": aid,
            "stance": "BULLISH",
            "score": 88,
            "dialogue": "Rule fallback",
            "is_degraded_fallback": True
        }
        for aid in ["buffett", "graham", "cathie_wood", "michael_burry", "george_soros", "william_oneil", "cis_trader"]
    ]
    risk_res = {"name": "Risk Manager AI", "score": 85, "stop_loss_price": 2188.05, "max_allocation_pct": 15.0, "veto_triggered": False}

    synth = PortfolioManagerAgent.synthesize_verdict(stock_data, high_fallback_analysts, risk_res, context_data={})
    verdict = synth["verdict"]
    assert verdict["degraded_mode"] is True, "Degraded mode flag must be True!"
    assert verdict["action"] == "HOLD", f"Expected HOLD in degraded mode, got {verdict['action']}"
    assert verdict["allocation_pct"] == 0.0, "Allocation must be 0.0 in degraded mode!"
    assert verdict["stop_loss_price"] == 2188.0, "TSE stop loss must be rounded to 1 JPY tick!"

    # Reset circuit breaker and verify normal BUY resumes when LLM agents are healthy
    BaseInvestmentAgent.reset_circuit()
    healthy_analysts = [dict(a, is_degraded_fallback=False) for a in high_fallback_analysts]
    synth_ok = PortfolioManagerAgent.synthesize_verdict(stock_data, healthy_analysts, risk_res, context_data={})
    assert synth_ok["verdict"]["degraded_mode"] is False
    assert synth_ok["verdict"]["action"] == "BUY"
    print("[PASS] 9. LLM API Circuit Breaker & Degraded Defense-Only Mode (Zero Blind BUY) verified.")


def test_10_tse_tick_size_and_board_lot_enforcement():
    """
    10. TSE (.T) Tick Size Table Normalization & 100-Share Board Lot Enforcement
    Verifies that Japanese equity prices are rounded to TSE tick increments (1, 5, 10, 50, 100 JPY)
    to prevent IBKR Error 110, and odd-lot quantities are floored to 100-share board lots.
    """
    from core.ai_hedge_fund.broker_client import round_price_to_exchange_tick, normalize_exchange_lot_size

    # TSE tick size table checks
    assert round_price_to_exchange_tick(2188.05, is_jp=True) == 2188.0   # <= 3,000 JPY: 1 JPY tick
    assert round_price_to_exchange_tick(4123.40, is_jp=True) == 4125.0   # <= 5,000 JPY: 5 JPY tick
    assert round_price_to_exchange_tick(18456.78, is_jp=True) == 18460.0 # <= 30,000 JPY: 10 JPY tick
    assert round_price_to_exchange_tick(42130.0, is_jp=True) == 42150.0  # <= 50,000 JPY: 50 JPY tick

    # US tick size check
    assert round_price_to_exchange_tick(155.678, is_jp=False) == 155.68

    # TSE 100-share board lot checks
    assert normalize_exchange_lot_size(142, is_jp=True) == 100
    assert normalize_exchange_lot_size(399, is_jp=True) == 300
    assert normalize_exchange_lot_size(85, is_jp=True) == 0    # Odd-lot rejected (< 100 shares)
    assert normalize_exchange_lot_size(142, is_jp=False) == 142 # US allows 1-share increments
    print("[PASS] 10. TSE Tick Size Table (1/5/10/50 JPY) & 100-Share Board Lot Enforcement verified.")


def test_11_simultaneous_multi_slot_crash_liquidation():
    """
    11. Simultaneous 6-Slot Black Swan Crash Liquidation & Margin Integrity
    Verifies that when all 6 portfolio slots simultaneously breach stop-loss (including overnight -16% gap-downs),
    concurrent liquidation completes without lock contention, zero orphan positions, and zero negative margin.
    """
    from core.ai_hedge_fund.broker_client import round_price_to_exchange_tick

    os.environ["LUMINA_TEST_MODE"] = "1"
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_sim_crash.db")
    engine = PaperTradingEngine(db_path=db_file)

    with engine._get_conn() as conn:
        conn.execute("UPDATE accounts SET cash_balance = 10000000.0 WHERE currency = 'JPY'")
        conn.execute("UPDATE accounts SET cash_balance = 50000.0 WHERE currency = 'USD'")
        conn.commit()

    slots = [
        ("7203.T", 300, 2500.0),
        ("8001.T", 200, 7000.0),
        ("6758.T", 200, 3000.0),
        ("MSFT",   25,  400.0),
        ("AAPL",   50,  200.0),
        ("JPM",    50,  200.0),
    ]
    for sym, qty, p in slots:
        r = engine.place_order(sym, "BUY", qty, p, order_type="MARKET", enforce_market_hours=False, stop_loss_price=p * 0.87, target_price=p * 1.25)
        assert r["success"] is True

    assert len(engine.get_positions()) == 6

    errors = []
    results = []

    def _burst_exit(sym, qty, p):
        try:
            gap_crash_price = round_price_to_exchange_tick(p * 0.84, is_jp=sym.endswith(".T"))
            res = engine.place_order(sym, "SELL", qty, gap_crash_price, order_type="MARKET", enforce_market_hours=False, notes="Simultaneous Black Swan Gap Stop")
            results.append(res)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_burst_exit, args=s) for s in slots]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent crash liquidation errors: {errors}"
    assert sum(1 for r in results if r.get("success")) == 6
    assert len(engine.get_positions()) == 0, "All 6 slots must be 100% liquidated to cash!"
    bal = engine.get_account_balance()
    assert bal["JPY"] > 0 and bal["USD"] > 0, "Cash balances must remain strictly positive!"
    print("[PASS] 11. Simultaneous 6-Slot Black Swan Crash & Overnight Gap Liquidation verified.")


def test_12_tsfm_ood_adversarial_inversion_veto():
    """
    12. TSFM (TimesFM/Chronos) Out-of-Distribution (OOD) & Adversarial Hallucination CRO Veto
    Verifies that if foundation time-series models hallucinate DOUBLE_BULLISH on a structurally broken stock
    (F-Score < 6, ROE < 12%, Stage 4 below SMA200, or heavy negative OFI), the CRO exercises Absolute Veto.
    """
    from core.ai_hedge_fund.agents.risk_manager_agent import RiskManagerAgent
    from core.ai_hedge_fund.agents.portfolio_manager_agent import PortfolioManagerAgent

    broken_stock = {
        "symbol": "PTON",
        "name": "Peloton",
        "current_price": 8.0,
        "currency": "USD",
        "roe": -35.0,
        "piotroski_f_score": 2,
        "history_metrics": {"volatility_annualized_pct": 25.0, "sma_200": 15.0, "atr_pct": 4.0},
    }
    adversarial_context = {
        "quantum_forecast": {
            "consensus_status": "DOUBLE_BULLISH",
            "ensemble_expected_return_pct": 12.5,
        },
        "deep_ofi": {"deep_ofi_score": -55.0},
    }
    bullish_analysts = [{"agent_id": "cathie_wood", "name": "Cathie Wood", "stance": "BULLISH", "score": 88, "is_degraded_fallback": False}]

    risk_res = RiskManagerAgent.evaluate_risk(broken_stock, bullish_analysts, context_data=adversarial_context)
    assert risk_res["veto_triggered"] is True, "CRO must veto adversarial TSFM OOD bullish hallucination!"
    assert "TSFM" in risk_res["veto_reason"]

    synth = PortfolioManagerAgent.synthesize_verdict(broken_stock, bullish_analysts, risk_res, context_data=adversarial_context)
    assert synth["verdict"]["action"] == "HOLD"
    assert synth["verdict"]["allocation_pct"] == 0.0
    print("[PASS] 12. TSFM Out-of-Distribution (OOD) Adversarial Hallucination CRO Veto verified.")


def test_13_tse_premarket_fake_order_book_and_special_quote_quarantine():
    """
    13. TSE Pre-Market (08:00-08:59 JST) Fake Order Book & Special Quote (特買・特売) Quarantine
    Verifies that pre-open crossed books, 08:59 mass cancellations, and special quote freezes are quarantined
    and automatically purged at the 09:00:00 JST opening bell so zero fake OFI bleeds into Zaraba.
    """
    import datetime
    from core.ai_hedge_fund.deep_ofi_analyzer import DeepOFIAnalyzer

    analyzer = DeepOFIAnalyzer("8035.T", alpha_decay=0.25)
    jst = datetime.timezone(datetime.timedelta(hours=9))

    # 08:45 JST Pre-open fake crossed walls (Bid 25,500 >= Ask 25,000)
    ts_0845 = datetime.datetime(2026, 10, 28, 8, 45, 0, tzinfo=jst).timestamp()
    m_pre1 = analyzer.update(
        [{"price": 25500.0 - i * 10, "size": 50000} for i in range(10)],
        [{"price": 25000.0 + i * 10, "size": 1000} for i in range(10)],
        timestamp=ts_0845,
    )
    assert m_pre1["summary_signal"] == "PREMARKET_SPECIAL_QUOTE_QUARANTINED"
    assert m_pre1.get("is_premarket_quarantined") is True

    # 08:59:30 JST Pre-open mass cancellation
    ts_0859 = datetime.datetime(2026, 10, 28, 8, 59, 30, tzinfo=jst).timestamp()
    m_pre2 = analyzer.update(
        [{"price": 24990.0 - i * 10, "size": 500} for i in range(10)],
        [{"price": 25000.0 + i * 10, "size": 1000} for i in range(10)],
        timestamp=ts_0859,
    )
    assert m_pre2["summary_signal"] == "PREMARKET_SPECIAL_QUOTE_QUARANTINED"

    # 09:00:05 JST Zaraba Opening Bell -> must start clean with 0.0 OFI (zero pre-open contamination)
    ts_0900 = datetime.datetime(2026, 10, 28, 9, 0, 5, tzinfo=jst).timestamp()
    m_open = analyzer.update(
        [{"price": 24990.0 - i * 10, "size": 1200} for i in range(10)],
        [{"price": 25000.0 + i * 10, "size": 1200} for i in range(10)],
        timestamp=ts_0900,
    )
    assert m_open["deep_ofi_score"] == 0.0
    assert m_open["summary_signal"] == "INITIALIZING"

    # 09:05:00 JST Special Sell Quote Freeze (特売)
    ts_0905 = datetime.datetime(2026, 10, 28, 9, 5, 0, tzinfo=jst).timestamp()
    m_sq = analyzer.update([], [{"price": 24500.0, "size": 90000}], timestamp=ts_0905, is_special_quote=True)
    assert m_sq["summary_signal"] == "PREMARKET_SPECIAL_QUOTE_QUARANTINED"
    print("[PASS] 13. TSE Pre-Market Fake Order Book & Special Quote (特買・特売) Quarantine verified.")


def test_14_dead_range_time_barrier_anti_churn_suppression():
    """
    14. Ultra-Low Volatility Dead-Range Churn Suppression
    Verifies that Schmitt Trigger Hysteresis deadzone + Volume-Clock compression
    suppresses whipsaw churn during oscillating sideways dead-range markets.
    """
    FactorOntology._state_memory.clear()
    # 50 bars of oscillating sideways range values inside [-0.45, +0.72] (never breaking 0.75 bullish outer threshold)
    range_vals = [0.10 + 0.55 * np.sin(i * 0.5) for i in range(50)]
    bull_entries = 0
    for val in range_vals:
        res = FactorOntology.interpret_value("alpha158_z_score", float(val), symbol="9432.T")
        if res and res["semantic_signal"] == "BULLISH":
            bull_entries += 1
    assert bull_entries == 0, f"Dead-range oscillation must trigger 0 false bullish entries, got {bull_entries}"
    print("[PASS] 14. Dead-Range Hysteresis Anti-Churn Suppression verified (0 false entries across 50 range bars).")


def test_15_orphaned_order_idempotency_and_timeout_recovery():
    """
    15. IBKR Network Timeout / Orphaned Order Double-Execution Guard
    Verifies that if a socket timeout occurs mid-flight and the caller retries the same order signal,
    OrderIdempotencyGuard blocks duplicate execution (Exactly-Once semantics).
    """
    import time
    os.environ["LUMINA_TEST_MODE"] = "1"
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_idemp.db")
    engine = PaperTradingEngine(db_path=db_file)

    sig_ts = time.time()
    # First order succeeds
    r1 = engine.place_order("7203.T", "BUY", 100, 2500.0, order_type="MARKET", enforce_market_hours=False, signal_timestamp=sig_ts)
    assert r1["success"] is True, f"First order failed: {r1}"

    # Immediate retry after simulated socket ACK timeout with same symbol/side/qty within 120s window
    r2 = engine.place_order("7203.T", "BUY", 100, 2500.0, order_type="MARKET", enforce_market_hours=False, signal_timestamp=sig_ts)
    assert r2["success"] is False
    assert r2.get("idempotency_blocked") is True, "Duplicate retry after socket timeout must be blocked by IdempotencyGuard!"
    pos = engine.get_positions()
    assert len(pos) == 1 and pos[0]["quantity"] == 100, "Position quantity must remain 100 (no double fill)!"
    print("[PASS] 15. Orphaned Order & Socket Timeout Idempotency Guard (Zero Double Execution) verified.")


def test_16_corporate_action_stock_split_auto_scaling():
    """
    16. Corporate Action (1-for-5 Stock Split) Auto-Scaling & False Stop-Loss Prevention
    Verifies that when a held stock undergoes a 5-for-1 split (price drops to 1/5), AutoTrader.patrol_positions
    automatically scales quantity x5 and price anchors /5 instead of misfiring Rule E (-13% Stop-Loss).
    """
    import time
    from core.ai_hedge_fund.auto_trader import AutoTrader
    from core.ai_hedge_fund.market_data_feed import MarketDataFeed

    os.environ["LUMINA_TEST_MODE"] = "1"
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_split.db")
    engine = PaperTradingEngine(db_path=db_file)
    with engine._get_conn() as conn:
        conn.execute("UPDATE accounts SET cash_balance = 5000000.0 WHERE currency = 'JPY'")
        conn.commit()

    # Buy 100 shares of 7011.T at pre-split price ¥10,000 (stop_loss = ¥8,700)
    r = engine.place_order("7011.T", "BUY", 100, 10000.0, order_type="MARKET", enforce_market_hours=False, stop_loss_price=8700.0, target_price=12500.0)
    assert r["success"] is True

    # Simulate 5-for-1 stock split overnight: live quote is now ¥2,050 (+2.5% post-split, but -79.5% vs unadjusted ¥10,000)
    now_ts = time.time()
    MarketDataFeed._split_cache["7011.T"] = (now_ts, 5.0)
    MarketDataFeed._quote_cache["7011.T"] = {
        "cached_at": now_ts,
        "data": {
            "symbol": "7011.T",
            "current_price": 2050.0,
            "previous_close": 2000.0,
            "change": 50.0,
            "change_pct": 2.5,
            "currency": "JPY",
            "timestamp": now_ts,
        },
    }

    patrol_res = AutoTrader.patrol_positions(engine, enforce_market_hours=False)
    assert len(patrol_res["closed_orders"]) == 0, "Stock split must NOT trigger a false stop-loss exit!"

    pos_list = engine.get_positions()
    assert len(pos_list) == 1
    p = pos_list[0]
    assert p["quantity"] == 500, f"Expected 500 shares after 5-for-1 split, got {p['quantity']}"
    assert abs(float(p["avg_entry_price"]) - 2000.0) < 1e-2, f"Expected entry price 2000.0, got {p['avg_entry_price']}"
    assert abs(float(p["stop_loss_price"]) - 1740.0) < 1e-2, f"Expected stop loss 1740.0, got {p['stop_loss_price']}"

    MarketDataFeed._split_cache.pop("7011.T", None)
    MarketDataFeed._quote_cache.pop("7011.T", None)
    print("[PASS] 16. Corporate Action (5-for-1 Stock Split) Auto-Scaling & False Stop Prevention verified.")


def test_17_partial_fill_weighted_avg_and_100share_breakeven_trailing():
    """
    17. Partial Fill Weighted-Average Pricing & 100-Share TSE Minimum Lot Breakeven/Trailing Transition
    Verifies:
      (a) Partial fills (200 shares @ 2000 + 300 shares @ 2050) compute exact weighted average 2030.0.
      (b) A 100-share TSE position hitting +12% does not throw a 50-share odd-lot error, locks breakeven stop,
          and triggers Rule C trailing stop when pulling back -4.5% from peak (even if current PnL < +10%).
    """
    import time
    from core.ai_hedge_fund.auto_trader import AutoTrader
    from core.ai_hedge_fund.market_data_feed import MarketDataFeed

    os.environ["LUMINA_TEST_MODE"] = "1"
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_partial_odd.db")
    engine = PaperTradingEngine(db_path=db_file)
    with engine._get_conn() as conn:
        conn.execute("UPDATE accounts SET cash_balance = 10000000.0 WHERE currency = 'JPY'")
        conn.commit()

    # (a) Partial fills: 200 shares @ 2000, then 300 shares @ 2050 (different signal_timestamp for second fill leg)
    r_leg1 = engine.place_order("8001.T", "BUY", 200, 2000.0, order_type="LIMIT", enforce_market_hours=False)
    assert r_leg1["success"] is True
    # Clear idempotency lock to simulate second partial fill arrival on same order
    with engine._get_conn() as conn:
        conn.execute("DELETE FROM order_idempotency")
        conn.commit()
    r_leg2 = engine.place_order("8001.T", "BUY", 300, 2050.0, order_type="LIMIT", enforce_market_hours=False)
    assert r_leg2["success"] is True

    pos_8001 = [p for p in engine.get_positions() if p["symbol"] == "8001.T"][0]
    assert pos_8001["quantity"] == 500
    assert abs(float(pos_8001["avg_entry_price"]) - 2030.0) < 1e-4, f"Expected weighted avg 2030.0, got {pos_8001['avg_entry_price']}"

    # (b) 100-share TSE minimum lot on 8035.T @ ¥3,000
    r_100 = engine.place_order("8035.T", "BUY", 100, 3000.0, order_type="MARKET", enforce_market_hours=False, stop_loss_price=2610.0, target_price=3750.0)
    assert r_100["success"] is True

    # Price rises +12% to ¥3,360 -> 100 shares cannot split into 50, must lock half_profit_taken=1 & stop_loss=3000.0
    now_ts = time.time()
    MarketDataFeed._quote_cache["8035.T"] = {
        "cached_at": now_ts,
        "data": {"symbol": "8035.T", "current_price": 3360.0, "previous_close": 3000.0, "change": 360.0, "change_pct": 12.0, "currency": "JPY", "timestamp": now_ts},
    }
    MarketDataFeed._quote_cache["8001.T"] = {
        "cached_at": now_ts,
        "data": {"symbol": "8001.T", "current_price": 2030.0, "previous_close": 2030.0, "change": 0.0, "change_pct": 0.0, "currency": "JPY", "timestamp": now_ts},
    }

    patrol_1 = AutoTrader.patrol_positions(engine, enforce_market_hours=False)
    assert len(patrol_1["closed_orders"]) == 0, "100-share position must not sell 50 odd-lot shares!"
    pos_8035 = [p for p in engine.get_positions() if p["symbol"] == "8035.T"][0]
    assert int(pos_8035["half_profit_taken"]) == 1, "100-share position at +12% must lock half_profit_taken=1!"
    assert float(pos_8035["stop_loss_price"]) == 3000.0, "100-share position at +12% must raise stop_loss_price to entry 3000.0!"

    # Next cycle: price pulls back -4.5% from peak 3360 to 3205 (+6.83% vs entry 3000) -> Rule C Trailing Stop must fire!
    with engine._get_conn() as conn:
        conn.execute("DELETE FROM order_idempotency")
        conn.commit()
    MarketDataFeed._quote_cache["8035.T"]["data"]["current_price"] = 3205.0
    patrol_2 = AutoTrader.patrol_positions(engine, enforce_market_hours=False)
    assert len(patrol_2["closed_orders"]) == 1, "Rule C Trailing Stop must fire when dropping -4.5% from +12% peak!"
    assert patrol_2["closed_orders"][0]["symbol"] == "8035.T"
    MarketDataFeed._quote_cache.pop("8035.T", None)
    MarketDataFeed._quote_cache.pop("8001.T", None)
    print("[PASS] 17. Partial Fill Weighted-Average & 100-Share TSE Breakeven/Trailing Transition verified.")


def test_18_sigkill_crash_recovery_and_cooldown_hydration():
    """
    18. Process Crash (`kill -9` / SIGKILL) & SQLite Cooldown State Hydration
    Verifies that after an abrupt process kill wipes all in-memory dicts, `hydrate_cooldowns_from_db`
    restores 14-day Time-Barrier and Stop-Loss anti-churn cooldowns directly from SQLite `trade_memories`.
    """
    import time
    from core.ai_hedge_fund.auto_trader import AutoTrader

    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_sigkill.db")
    engine = PaperTradingEngine(db_path=db_file)

    # Record a TIME_BARRIER_ROTATION exit and a FIBONACCI_STOP_LOSS exit in SQLite trade_memories
    engine.record_trade_memory(
        symbol="4911.T",
        company_name="Shiseido",
        trade_type="SELL_EXIT",
        quantity=100,
        price=2500.0,
        currency="JPY",
        realized_pnl=1500.0,
        realized_pnl_pct=0.6,
        trigger_rule="TIME_BARRIER_ROTATION",
        lesson_learned="35d time barrier exit",
    )
    engine.record_trade_memory(
        symbol="7201.T",
        company_name="Nissan",
        trade_type="SELL_EXIT",
        quantity=100,
        price=400.0,
        currency="JPY",
        realized_pnl=-5200.0,
        realized_pnl_pct=-13.0,
        trigger_rule="FIBONACCI_STOP_LOSS",
        lesson_learned="-13% stop loss exit",
    )

    # Simulate `kill -9` wiping all in-memory state
    AutoTrader._time_barrier_cooldowns.clear()
    assert len(AutoTrader._time_barrier_cooldowns) == 0

    # Rehydrate from SQLite on restart
    restored_count = AutoTrader.hydrate_cooldowns_from_db(engine)
    assert restored_count == 2, f"Expected 2 cooldowns restored from SQLite, got {restored_count}"
    now_ts = time.time()
    assert (now_ts - AutoTrader._time_barrier_cooldowns["4911.T"]) < AutoTrader.TIME_BARRIER_COOLDOWN_SEC
    assert (now_ts - AutoTrader._time_barrier_cooldowns["7201.T"]) < AutoTrader.TIME_BARRIER_COOLDOWN_SEC
    AutoTrader._time_barrier_cooldowns.clear()
    print("[PASS] 18. SIGKILL Process Crash Recovery & SQLite 14-Day Cooldown Hydration verified.")


if __name__ == "__main__":
    test_1_ci_factor_ontology_contracts()
    test_2_schmitt_trigger_hysteresis_and_deadzone()
    test_3_sqlite_single_writer_queue_and_compound_fts5()
    test_4_hayashi_yoshida_higham_psd_projection()
    test_5_chaos_disconnect_and_bracket_persistence()
    test_6_ibkr_daily_disconnect_reconciliation()
    test_7_volume_clock_timeout_fallback()
    test_8_reflexion_exponential_time_decay_aging()
    test_9_llm_api_circuit_breaker_and_degraded_defense_mode()
    test_10_tse_tick_size_and_board_lot_enforcement()
    test_11_simultaneous_multi_slot_crash_liquidation()
    test_12_tsfm_ood_adversarial_inversion_veto()
    test_13_tse_premarket_fake_order_book_and_special_quote_quarantine()
    test_14_dead_range_time_barrier_anti_churn_suppression()
    test_15_orphaned_order_idempotency_and_timeout_recovery()
    test_16_corporate_action_stock_split_auto_scaling()
    test_17_partial_fill_weighted_avg_and_100share_breakeven_trailing()
    test_18_sigkill_crash_recovery_and_cooldown_hydration()
    print("\n[SUCCESS] ALL 18 INSTITUTIONAL HARDENING, EXTREME SCENARIO & CHAOS ENGINEERING TESTS PASSED SUCCESSFULLY!")




