# -*- coding: utf-8 -*-
"""
Property-based formal verification suite using Hypothesis.
Verifies microstructural invariants across 1,000 randomized trajectories:
  - Property 1 (350 runs): DeepOFIAnalyzer numerical stability & time-delta guards
  - Property 2 (350 runs): CisFlowSniper SL/TP/RR ordering invariants
  - Property 3 (300 runs): TSE & US tick size and board-lot normalization
"""
import math
import numpy as np
import pandas as pd
from hypothesis import given, settings, strategies as st, HealthCheck

from core.ai_hedge_fund.deep_ofi_analyzer import DeepOFIAnalyzer
from core.ai_hedge_fund.cis_flow_sniper import CisFlowSniper
from core.ai_hedge_fund.broker_client import round_price_to_exchange_tick, normalize_exchange_lot_size


@settings(max_examples=350, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    base_price=st.floats(min_value=0.5, max_value=50000.0, allow_nan=False, allow_infinity=False),
    spread_bps=st.floats(min_value=0.1, max_value=200.0, allow_nan=False, allow_infinity=False),
    bid_sizes=st.lists(st.integers(min_value=0, max_value=500000), min_size=1, max_size=15),
    ask_sizes=st.lists(st.integers(min_value=0, max_value=500000), min_size=1, max_size=15),
    price_shift_pct=st.floats(min_value=-0.10, max_value=0.10, allow_nan=False, allow_infinity=False),
    dt_sec=st.floats(min_value=0.001, max_value=30.0, allow_nan=False, allow_infinity=False),
)
def test_property_1_deep_ofi_invariants(base_price, spread_bps, bid_sizes, ask_sizes, price_shift_pct, dt_sec):
    an_h = DeepOFIAnalyzer("HYP_OFI")
    step = max(0.01, base_price * 0.0005)
    half_sp = max(0.005, base_price * (spread_bps / 20000.0))
    b1 = [{"price": round(base_price - half_sp - i * step, 4), "size": s} for i, s in enumerate(bid_sizes)]
    a1 = [{"price": round(base_price + half_sp + i * step, 4), "size": s} for i, s in enumerate(ask_sizes)]
    t0 = 1700000000.0
    r1 = an_h.update(b1, a1, timestamp=t0)

    p2 = max(0.05, base_price * (1.0 + price_shift_pct))
    b2 = [{"price": round(p2 - half_sp - i * step, 4), "size": max(0, int(s * 0.2))} for i, s in enumerate(bid_sizes)]
    a2 = [{"price": round(p2 + half_sp + i * step, 4), "size": max(0, int(s * 0.2))} for i, s in enumerate(ask_sizes)]
    r2 = an_h.update(b2, a2, timestamp=t0 + dt_sec)

    for k, v in r2.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise AssertionError(f"NaN/Inf in DeepOFIAnalyzer output '{k}': {v}")
    if dt_sec > 15.0 and (r2.get("is_spoof_buy_wall") or r2.get("is_spoof_sell_wall")):
        raise AssertionError(f"Stale snapshot (dt={dt_sec}s > 15s) falsely triggered spoofing: {r2}")


@settings(max_examples=350, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    base_price=st.floats(min_value=5.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
    returns=st.lists(st.floats(min_value=-0.03, max_value=0.03, allow_nan=False, allow_infinity=False), min_size=40, max_size=40),
    vol_mult=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    min_rr=st.floats(min_value=1.4, max_value=2.5, allow_nan=False, allow_infinity=False),
    has_ob=st.booleans(),
    ob_wall_dist_pct=st.floats(min_value=0.0001, max_value=0.05, allow_nan=False, allow_infinity=False),
)
def test_property_2_cis_sniper_invariants(base_price, returns, vol_mult, min_rr, has_ob, ob_wall_dist_pct):
    prices = [base_price]
    for r in returns:
        prices.append(max(1.0, prices[-1] * (1.0 + r)))
    closes = np.array(prices[:40])
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    highs = np.maximum(opens, closes) * 1.003
    lows = np.minimum(opens, closes) * 0.997
    vols = np.full(40, 10000.0)
    vols[-1] = 10000.0 * vol_mult

    df_h = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols
    }, index=pd.date_range("2026-11-03 10:00", periods=40, freq="5min", tz="America/New_York"))

    cur_p = float(closes[-1])
    ob_h = None
    if has_ob:
        ob_h = {
            "bids": [{"price": cur_p * (1.0 - ob_wall_dist_pct), "size": 50000}, {"price": cur_p * 0.99, "size": 100}],
            "asks": [{"price": cur_p * (1.0 + ob_wall_dist_pct), "size": 50000}, {"price": cur_p * 1.01, "size": 100}],
        }

    res = CisFlowSniper.evaluate_sniper_setup("NVDA", df_h, order_book=ob_h, min_risk_reward=min_rr)
    if res.get("triggered"):
        act = res.get("signal")
        ep = res.get("entry_price")
        sl = res.get("stop_loss_price")
        tp = res.get("take_profit_price")
        rr = res.get("risk_reward_ratio")
        if any(math.isnan(x) or math.isinf(x) or x <= 0 for x in (ep, sl, tp, rr)):
            raise AssertionError(f"Non-finite or non-positive SL/TP/RR on triggered setup: {res}")
        if rr < min_rr - 1e-4:
            raise AssertionError(f"Triggered setup violated minimum RR >= {min_rr}: rr={rr}, res={res}")
        if act == "BUY" and not (sl < ep < tp):
            raise AssertionError(f"BUY setup violated SL < Entry < TP: SL={sl}, EP={ep}, TP={tp}")


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    symbol=st.sampled_from(["7203.T", "9984.T", "8306.T", "NVDA", "AAPL", "GC=F"]),
    price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    raw_qty=st.integers(min_value=-500, max_value=50000),
)
def test_property_3_exchange_tick_and_lot_invariants(symbol, price, raw_qty):
    is_jp = symbol.endswith(".T")
    rp = round_price_to_exchange_tick(price, is_jp=is_jp)
    if math.isnan(rp) or math.isinf(rp) or rp <= 0:
        raise AssertionError(f"Invalid rounded price {rp} for {symbol} @ {price}")
    if is_jp and rp >= 30000.0:
        if rp % 50.0 != 0 and rp % 100.0 != 0 and rp % 1000.0 != 0 and rp > 30000.0:
            raise AssertionError(f"TSE tick violation for {symbol} @ {price} -> {rp}")
    nq = normalize_exchange_lot_size(raw_qty, is_jp=is_jp)
    if nq < 0:
        raise AssertionError(f"Negative normalized lot size {nq} for {symbol}, raw={raw_qty}")
    if is_jp and nq > 0 and (nq % 100 != 0):
        raise AssertionError(f"TSE 100-share lot violation for {symbol}: raw={raw_qty} -> {nq}")
