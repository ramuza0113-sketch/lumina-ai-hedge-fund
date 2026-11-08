# -*- coding: utf-8 -*-
"""
Formal Verification & Cross-Asset Microstructure Suite (Hashimoto 2026d, WP-2026-04)
------------------------------------------------------------------------------------
Pytest suite validating:
  1. Theorem 1: Microsoft Z3 SMT Formal Proofs (QF_LIRA) & SQL AST Schema Parity (UNSAT)
  2. Theorem 2: Friday Afternoon (11:00 ET+) Cross-Asset Exit Divergence (Equity 0.75x vs. Gold 1.00x)
  3. Proposition 1: Cross-Sectional 30m Opening Range Compression Gate (< 0.75%) & Pre-10:00 ET Guard
"""

import math
import os
import sys
import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.ai_hedge_fund.cis_flow_sniper import CisFlowSniper
from scripts.run_4stage_formal_audit import (
    run_stage1_static_syntax_audit,
    run_stage2_sql_ast_schema_audit,
    run_stage3_z3_smt_theorem_prover,
    run_stage4_boundary_microstructure_audit,
)


def test_stage1_and_stage2_sql_ast_schema_parity():
    """Verify static syntax and SQL AST EXPLAIN QUERY PLAN parity across all core modules."""
    ok1, info1 = run_stage1_static_syntax_audit()
    assert ok1, f"Stage 1 static syntax audit failed: {info1}"

    ok2, info2 = run_stage2_sql_ast_schema_audit()
    assert ok2, f"Stage 2 SQL AST schema audit failed: {info2}"
    assert info2["queries_verified"] > 0


def test_theorem1_z3_smt_formal_invariants_unsat():
    """Verify that all 5 Z3 SMT execution/risk invariants return UNSAT (0 counterexamples)."""
    ok3, z3_results = run_stage3_z3_smt_theorem_prover()
    assert ok3, f"Z3 SMT solver found counterexample(s): {z3_results}"
    for inv_name, status in z3_results.items():
        assert status == "unsat", f"Invariant {inv_name} did not return unsat: {status}"


def test_theorem2_friday_afternoon_cross_asset_exit_divergence():
    """
    Verify Theorem 2: On Fridays at or after 11:00 ET with positive unrealized PnL,
    US Equities tighten trailing stop distance to 0.75x while Precious Metals (XAUUSD)
    preserve full 1.00x trailing stop distance.
    """
    # Friday 11:00 ET+ with unrealized profit
    assert math.isclose(
        CisFlowSniper.compute_friday_afternoon_trail_multiplier("EQUITY", weekday=4, et_hour=11, unrealized_pnl=250.0),
        0.75,
    )
    assert math.isclose(
        CisFlowSniper.compute_friday_afternoon_trail_multiplier("METAL", weekday=4, et_hour=11, unrealized_pnl=250.0),
        1.00,
    )
    # Friday before 11:00 ET or non-Friday or negative unrealized PnL -> 1.00x
    assert math.isclose(
        CisFlowSniper.compute_friday_afternoon_trail_multiplier("EQUITY", weekday=4, et_hour=10, unrealized_pnl=250.0),
        1.00,
    )
    assert math.isclose(
        CisFlowSniper.compute_friday_afternoon_trail_multiplier("EQUITY", weekday=3, et_hour=14, unrealized_pnl=250.0),
        1.00,
    )
    assert math.isclose(
        CisFlowSniper.compute_friday_afternoon_trail_multiplier("EQUITY", weekday=4, et_hour=13, unrealized_pnl=-10.0),
        1.00,
    )


def test_proposition1_opening_range_compression_gate_and_pre10_guard():
    """
    Verify Proposition 1: Cross-sectional 30m ORB median < 0.75% blocks non-breakout chop
    during 10:00–11:29 ET while allowing volume-confirmed breakouts (RVOL >= 1.50) and
    never misfiring on incomplete pre-10:00 ET ranges.
    """
    df_incomplete = pd.DataFrame({
        "open": [100.0, 100.1, 100.2],
        "high": [100.2, 100.3, 100.3],
        "low": [99.9, 100.0, 100.1],
        "close": [100.1, 100.2, 100.2],
        "volume": [1000, 1200, 1100],
    })
    assert CisFlowSniper.compute_30m_orb_width_pct(df_incomplete) is None

    df_complete = pd.DataFrame({
        "open": [100.0] * 6,
        "high": [100.2, 100.3, 100.4, 100.5, 100.4, 100.3],
        "low": [99.9, 99.95, 100.0, 100.1, 100.0, 99.95],
        "close": [100.1] * 6,
        "volume": [1000] * 6,
    })
    orb_pct = CisFlowSniper.compute_30m_orb_width_pct(df_complete)
    assert orb_pct is not None and math.isclose(orb_pct, 0.60, rel_tol=1e-4)

    ok4, info4 = run_stage4_boundary_microstructure_audit()
    assert ok4, f"Stage 4 boundary microstructure check failed: {info4}"
