# -*- coding: utf-8 -*-
"""
deep_ofi_analyzer.py - Deep Multi-Level Order Flow Imbalance (OFI) & Microstructure Analyzer

Implements Rama Cont et al. (2014) multi-level order flow imbalance formulation
extended for deep order book (Level 1 to 10).
Detects:
1. Multi-Level Weighted OFI Score (-100 to +100)
2. Spoofing Cancellation (見せ板だまし・急激な板引っ込め)
3. Iceberg Order Accumulation (大口のアイスバーグステルス買い集め)
4. Order Book Center-of-Mass (BVWP / AVWP) acceleration
5. Liquidity Hole (板の真空地帯・ブレイク直後の急騰余地)
"""

import time
import math
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field


@dataclass
class OrderBookLevel:
    price: float
    size: int
    orders: Optional[int] = None


@dataclass
class OrderBookSnapshot:
    timestamp: float
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)


class DeepOFIAnalyzer:
    """
    High-performance, event-driven analyzer for Level 2 (10-level) order book data.
    Designed to feed into cis_flow_sniper.py for ultra-low latency decision making.
    """

    def __init__(self, symbol: str = "GENERIC", max_history: int = 40, alpha_decay: float = 0.25):
        self.symbol = symbol
        self.max_history = max_history
        self.alpha_decay = alpha_decay  # Decay weight for deeper levels: w_k = exp(-alpha * k)
        self.history: deque[OrderBookSnapshot] = deque(maxlen=max_history)
        self.cum_trades: deque[Dict[str, Any]] = deque(maxlen=100)
        
        # Smoothed metrics
        self.ema_ofi: float = 0.0
        self.last_bvwp: float = 0.0
        self.last_avwp: float = 0.0

    @staticmethod
    def _is_jst_premarket(ts: float) -> bool:
        """Returns True if timestamp falls in TSE pre-open window (08:00:00 - 08:59:59 JST)."""
        import datetime
        jst = datetime.timezone(datetime.timedelta(hours=9))
        dt_jst = datetime.datetime.fromtimestamp(ts, tz=jst)
        return dt_jst.hour == 8

    @staticmethod
    def _safe_pos_float(val: Any) -> float:
        try:
            f = float(val or 0.0)
            return f if (math.isfinite(f) and f > 0.0) else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_pos_int(val: Any) -> int:
        try:
            f = float(val or 0)
            return int(f) if (math.isfinite(f) and f > 0.0) else 0
        except (TypeError, ValueError, OverflowError):
            return 0

    def update(
        self,
        bids: List[Dict[str, Any]],
        asks: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
        trades: Optional[List[Dict[str, Any]]] = None,
        is_special_quote: bool = False,
        bar_microstructure: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingests a new order book snapshot (up to 10 rows of bids/asks).
        Returns comprehensive microstructure & OFI analysis metrics.
        Includes TSE Pre-Market (08:00-08:59 JST) Fake Order Book & Special Quote (特買・特売) Quarantine Guard.
        """
        ts = timestamp if (timestamp is not None and math.isfinite(float(timestamp))) else time.time()
        
        # Clean and sort bids (descending) & asks (ascending) with NaN/Inf immunity
        clean_bids = []
        for b in (bids or []):
            bp = self._safe_pos_float(b.get("price", 0.0))
            bs = self._safe_pos_int(b.get("size", 0))
            if bp > 0.0 and bs > 0:
                clean_bids.append(OrderBookLevel(price=round(bp, 4 if bp < 1.0 else 2), size=bs, orders=b.get("orders")))
        clean_bids.sort(key=lambda x: x.price, reverse=True)

        clean_asks = []
        for a in (asks or []):
            ap = self._safe_pos_float(a.get("price", 0.0))
            as_ = self._safe_pos_int(a.get("size", 0))
            if ap > 0.0 and as_ > 0:
                clean_asks.append(OrderBookLevel(price=round(ap, 4 if ap < 1.0 else 2), size=as_, orders=a.get("orders")))
        clean_asks.sort(key=lambda x: x.price, reverse=False)

        trade_list = []
        for tr in (trades or []):
            tp = self._safe_pos_float(tr.get("price", 0.0))
            ts_sz = self._safe_pos_int(tr.get("size", 0))
            if tp > 0.0 and ts_sz > 0:
                trade_list.append({"price": tp, "size": ts_sz, "side": tr.get("side", "")})
        snapshot = OrderBookSnapshot(timestamp=ts, bids=clean_bids, asks=clean_asks, trades=trade_list)

        # 🛡️ TSE Pre-Market (08:00-08:59 JST) & Special Quote (特別気配: 特買・特売 / Crossed Book) Quarantine Guard
        is_crossed_book = bool(clean_bids and clean_asks and clean_bids[0].price >= clean_asks[0].price)
        is_one_sided_freeze = bool((not clean_bids or not clean_asks) and len(trade_list) == 0)
        is_tse_preopen = self.symbol.endswith(".T") and self._is_jst_premarket(ts)

        if is_special_quote or is_crossed_book or is_one_sided_freeze or is_tse_preopen:
            # Flush history & EMA so pre-open fake walls / special quotes never contaminate 09:00 Zaraba open
            self.history.clear()
            self.ema_ofi = 0.0
            self.last_bvwp = 0.0
            self.last_avwp = 0.0
            q_metrics = self._default_metrics(snapshot)
            q_metrics["summary_signal"] = "PREMARKET_SPECIAL_QUOTE_QUARANTINED"
            q_metrics["confidence_boost"] = -50
            q_metrics["is_premarket_quarantined"] = True
            return q_metrics

        # If transitioning across TSE 09:00 JST opening bell, purge any stale pre-market snapshots
        if self.symbol.endswith(".T") and len(self.history) > 0:
            if self._is_jst_premarket(self.history[-1].timestamp) and not self._is_jst_premarket(ts):
                self.history.clear()
                self.ema_ofi = 0.0
                self.last_bvwp = 0.0
                self.last_avwp = 0.0

        self.history.append(snapshot)
        for tr in trade_list:
            self.cum_trades.append(tr)

        # If not enough history, return default metrics
        if len(self.history) < 2:
            return self._default_metrics(snapshot)

        prev_snapshot = self.history[-2]
        return self._compute_metrics(snapshot, prev_snapshot, bar_microstructure=bar_microstructure)

    @staticmethod
    def compute_60level_decay_metrics(
        imb10: float,
        imb60: float,
        side: str = "BUY",
        upper_wick: float = 0.0,
        lower_wick: float = 0.0,
        open_rvol: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Computes Cont (2014) 60-level exponential decay-weighted OFI (68% near-book 1..10 + 32% deep-book 11..60)
        and detects Liquidity Vacuum breakouts (minimal opposing wick + strong decay OFI + high RVOL).
        """
        i10 = float(imb10 if (imb10 is not None and math.isfinite(float(imb10))) else 50.0)
        i60 = float(imb60 if (imb60 is not None and math.isfinite(float(imb60))) else i10)
        uw = float(upper_wick if (upper_wick is not None and math.isfinite(float(upper_wick))) else 0.20)
        lw = float(lower_wick if (lower_wick is not None and math.isfinite(float(lower_wick))) else 0.20)
        rv = float(open_rvol if (open_rvol is not None and math.isfinite(float(open_rvol))) else 1.0)
        decay_ofi_pct = round(0.68 * i10 + 0.32 * i60, 2)
        s_up = str(side or "BUY").upper()
        is_liq_vacuum = bool(
            (s_up in ("BUY", "LONG") and decay_ofi_pct >= 58.0 and uw <= 0.22 and rv >= 1.35)
            or (s_up == "SHORT" and decay_ofi_pct <= 42.0 and lw <= 0.22 and rv >= 1.35)
        )
        return {
            "decay_ofi_pct": decay_ofi_pct,
            "is_liquidity_vacuum": is_liq_vacuum,
            "boost_mult": 1.06 if is_liq_vacuum else 1.0,
        }

    def _compute_metrics(
        self,
        curr: OrderBookSnapshot,
        prev: OrderBookSnapshot,
        bar_microstructure: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculates multi-level OFI, spoofing, iceberg, center of mass, and liquidity vacuum."""
        depth = min(60, len(curr.bids), len(prev.bids), len(curr.asks), len(prev.asks))
        if depth == 0:
            return self._default_metrics(curr)

        dt = max(0.01, curr.timestamp - prev.timestamp)

        # 1. Multi-Level OFI (Cont et al. 2014 extension)
        raw_bid_ofi = 0.0
        raw_ask_ofi = 0.0
        total_weight = 0.0

        for k in range(depth):
            weight = math.exp(-self.alpha_decay * k)
            total_weight += weight

            # Bid side flow
            p_curr_b = curr.bids[k].price
            s_curr_b = curr.bids[k].size
            p_prev_b = prev.bids[k].price
            s_prev_b = prev.bids[k].size

            if p_curr_b > p_prev_b:
                delta_b = s_curr_b
            elif p_curr_b == p_prev_b:
                delta_b = s_curr_b - s_prev_b
            else:
                delta_b = -s_prev_b
            raw_bid_ofi += weight * delta_b

            # Ask side flow
            p_curr_a = curr.asks[k].price
            s_curr_a = curr.asks[k].size
            p_prev_a = prev.asks[k].price
            s_prev_a = prev.asks[k].size

            if p_curr_a < p_prev_a:
                delta_a = s_curr_a
            elif p_curr_a == p_prev_a:
                delta_a = s_curr_a - s_prev_a
            else:
                delta_a = -s_prev_a
            raw_ask_ofi += weight * delta_a

        net_raw_ofi = raw_bid_ofi - raw_ask_ofi
        
        # Normalization factor based on average depth size
        avg_depth_size = max(100.0, (sum(b.size for b in curr.bids[:depth]) + sum(a.size for a in curr.asks[:depth])) / (2 * depth))
        normalized_ofi = (net_raw_ofi / (avg_depth_size * (total_weight or 1.0))) * 100.0
        normalized_ofi = max(-100.0, min(100.0, normalized_ofi))

        # Blend with real intraday bar volume-weighted OFI if available
        if bar_microstructure and "bar_ofi_score" in bar_microstructure:
            bar_ofi = float(bar_microstructure["bar_ofi_score"])
            normalized_ofi = max(-100.0, min(100.0, 0.55 * normalized_ofi + 0.45 * bar_ofi))

        # Exponential moving average smoothing
        self.ema_ofi = 0.65 * normalized_ofi + 0.35 * self.ema_ofi

        # 2. Spoofing Cancellation Detection (Level 2 to 10 + Real Bar Wick/Volume Bull & Bear Trap Detection)
        spoof_buy_detected, spoof_buy_details = self._detect_spoofing(
            curr.bids, prev.bids, side="bid", dt=dt, recent_trades=curr.trades
        )
        spoof_sell_detected, spoof_sell_details = self._detect_spoofing(
            curr.asks, prev.asks, side="ask", dt=dt, recent_trades=curr.trades
        )

        if bar_microstructure:
            if not spoof_buy_detected and bar_microstructure.get("is_real_bull_trap"):
                spoof_buy_detected = True
                spoof_buy_details = dict(bar_microstructure.get("bull_trap_details") or {})
            if not spoof_sell_detected and bar_microstructure.get("is_real_bear_trap"):
                spoof_sell_detected = True
                spoof_sell_details = dict(bar_microstructure.get("bear_trap_details") or {})

        # 3. Iceberg Order Accumulation & Distribution Detection
        iceberg_detected, iceberg_details = self._detect_iceberg(curr, prev)
        iceberg_sell_detected = False
        iceberg_sell_details: Dict[str, Any] = {}
        if bar_microstructure:
            if not iceberg_detected and bar_microstructure.get("is_real_iceberg_buy"):
                iceberg_detected = True
                iceberg_details = dict(bar_microstructure.get("iceberg_buy_details") or {})
            if bar_microstructure.get("is_real_iceberg_sell"):
                iceberg_sell_detected = True
                iceberg_sell_details = dict(bar_microstructure.get("iceberg_sell_details") or {})

        # 4. Center of Mass (BVWP & AVWP) & Velocity
        bvwp = sum(b.price * b.size for b in curr.bids[:depth]) / max(1, sum(b.size for b in curr.bids[:depth]))
        avwp = sum(a.price * a.size for a in curr.asks[:depth]) / max(1, sum(a.size for a in curr.asks[:depth]))
        bvwp_velocity = ((bvwp - self.last_bvwp) / dt) if self.last_bvwp > 0 else 0.0
        self.last_bvwp = bvwp
        self.last_avwp = avwp

        # 5. Liquidity Hole (Vacuum) Detection
        mid_price = (curr.bids[0].price + curr.asks[0].price) / 2.0
        spread = round(curr.asks[0].price - curr.bids[0].price, 2)
        top5_ask_size = sum(a.size for a in curr.asks[:min(5, len(curr.asks))])
        top5_bid_size = sum(b.size for b in curr.bids[:min(5, len(curr.bids))])
        
        liquidity_hole_above = top5_ask_size < (top5_bid_size * 0.35) and spread <= 0.05
        liquidity_hole_below = top5_bid_size < (top5_ask_size * 0.35) and spread <= 0.05

        # 6. Synthesized Regime / Signal
        summary_signal, confidence_boost = self._synthesize_signal(
            ofi=self.ema_ofi,
            spoof_buy=spoof_buy_detected,
            spoof_sell=spoof_sell_detected,
            iceberg=iceberg_detected,
            bvwp_velocity=bvwp_velocity,
            liquidity_hole_above=liquidity_hole_above
        )

        return {
            "symbol": self.symbol,
            "timestamp": curr.timestamp,
            "mid_price": round(mid_price, 2),
            "spread": spread,
            "depth_levels": depth,
            "raw_ofi": round(net_raw_ofi, 2),
            "deep_ofi_score": round(self.ema_ofi, 1),
            "is_spoof_buy_wall": spoof_buy_detected,
            "spoof_buy_details": spoof_buy_details,
            "is_spoof_sell_wall": spoof_sell_detected,
            "spoof_sell_details": spoof_sell_details,
            "is_iceberg_accumulation": iceberg_detected,
            "iceberg_details": iceberg_details,
            "is_iceberg_distribution": iceberg_sell_detected,
            "iceberg_sell_details": iceberg_sell_details,
            "bid_center_of_mass": round(bvwp, 2),
            "ask_center_of_mass": round(avwp, 2),
            "bvwp_velocity": round(bvwp_velocity, 4),
            "liquidity_hole_above": liquidity_hole_above,
            "liquidity_hole_below": liquidity_hole_below,
            "summary_signal": summary_signal,
            "confidence_boost": confidence_boost,
            "bids_snapshot": [{"price": b.price, "size": b.size} for b in curr.bids[:depth]],
            "asks_snapshot": [{"price": a.price, "size": a.size} for a in curr.asks[:depth]],
        }

    def _detect_spoofing(
        self,
        curr_levels: List[OrderBookLevel],
        prev_levels: List[OrderBookLevel],
        side: str = "bid",
        dt: float = 1.0,
        recent_trades: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detects sudden disappearance of a large wall at levels 2 to 10 without trade volume.
        Includes Visible Window Scroll-Out Guard & Time-Delta Guard so rising prices that scroll
        old bid levels below the top-10 window (or stale 15-minute cycle snapshots) are never
        misclassified as spoofing cancellations.
        """
        if not curr_levels or not prev_levels:
            return False, {}
        # Spoofing pulls occur in sub-second to a few seconds; ignore stale cross-cycle snapshots (> 15s)
        if dt > 15.0:
            return False, {}

        prev_map = {lvl.price: lvl.size for lvl in prev_levels[1:10]}
        curr_map = {lvl.price: lvl.size for lvl in curr_levels}

        if side == "bid":
            curr_best_bid = curr_levels[0].price
            curr_lowest_bid = curr_levels[-1].price
        else:
            curr_best_ask = curr_levels[0].price
            curr_highest_ask = curr_levels[-1].price

        median_size = (
            sorted([lvl.size for lvl in prev_levels])[len(prev_levels) // 2]
            if prev_levels else 100
        )

        trades_list = recent_trades or []

        for price, prev_size in prev_map.items():
            # Visible Window Scroll-Out & Crossed-Level Guard:
            # - For bids: if price < curr_lowest_bid, the stock rallied and this level simply scrolled
            #   below the visible window (NOT cancelled). If price > curr_best_bid, price moved down through it.
            # - For asks: if price > curr_highest_ask, the stock dropped and this level scrolled above
            #   the visible window. If price < curr_best_ask, price rose through it.
            if side == "bid":
                if price < curr_lowest_bid or price > curr_best_bid:
                    continue
            else:
                if price > curr_highest_ask or price < curr_best_ask:
                    continue

            # A wall must have been at least 2.2x median size to be considered an intentional spoof wall
            if prev_size >= max(500, int(median_size * 2.2)):
                curr_size = curr_map.get(price, 0)
                exec_size = sum(
                    int(tr.get("size", 0))
                    for tr in trades_list
                    if abs(float(tr.get("price", 0.0)) - price) <= 0.005
                )
                cancelled_size = max(0, prev_size - curr_size - exec_size)
                cancellation_ratio = cancelled_size / prev_size if prev_size > 0 else 0.0

                # If canceled by > 55% between consecutive snapshots without execution
                if cancellation_ratio >= 0.55:
                    return True, {
                        "wall_price": price,
                        "prev_size": prev_size,
                        "curr_size": curr_size,
                        "cancelled_size": cancelled_size,
                        "cancellation_ratio": round(cancellation_ratio, 2),
                        "side": side,
                        "reason": f"Level {side} wall at ${price:.2f} vanished by {cancellation_ratio*100:.0f}% (Potential spoofing trap)"
                    }
        return False, {}

    def _detect_iceberg(
        self,
        curr: OrderBookSnapshot,
        prev: OrderBookSnapshot
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detects iceberg accumulation: heavy selling consumed into bid, yet bid depth replenishes immediately.
        """
        if not curr.bids or not prev.bids:
            return False, {}

        best_bid_curr = curr.bids[0]
        best_bid_prev = prev.bids[0]

        # Check recent trade volume on bid (sell aggressor hits bid)
        recent_sells = sum(
            tr.get("size", 0) for tr in curr.trades
            if tr.get("side") in ("SELL", "sell", "bid_hit") or tr.get("price", 0) <= best_bid_prev.price
        )

        # If substantial sell volume was absorbed (> 1,000 shares or > 2x best bid size)
        if recent_sells >= max(500, best_bid_prev.size * 1.5):
            # Did the bid price hold or rise, and is the bid size still thick?
            if best_bid_curr.price >= best_bid_prev.price and best_bid_curr.size >= best_bid_prev.size * 0.7:
                return True, {
                    "absorbed_shares": recent_sells,
                    "best_bid_held": best_bid_curr.price,
                    "bid_size": best_bid_curr.size,
                    "reason": f"Heavy selling ({recent_sells} shares) absorbed at ${best_bid_curr.price:.2f} without dropping best bid"
                }

        return False, {}

    def _synthesize_signal(
        self,
        ofi: float,
        spoof_buy: bool,
        spoof_sell: bool,
        iceberg: bool,
        bvwp_velocity: float,
        liquidity_hole_above: bool
    ) -> Tuple[str, int]:
        """
        Synthesizes a master tactical recommendation for the execution engine.
        """
        # Critical warning: Trap avoidance takes highest priority
        if spoof_buy:
            return "SPOOF_TRAP_ABORT", -50  # Abort long immediately

        if iceberg:
            return "ICEBERG_STEALTH_BUY", +35

        if ofi >= 45.0 and bvwp_velocity > 0.01:
            if liquidity_hole_above:
                return "AGGRESSIVE_BREAKOUT_SURGE", +30
            return "STRONG_BUY_PRESSURE", +20

        if ofi <= -45.0:
            if spoof_sell:
                return "SPOOF_SELL_WALL_OPPORTUNITY", +15  # Fake resistance, might break upwards
            return "HEAVY_SELLING_PRESSURE", -30

        return "NEUTRAL_FLOW", 0

    def _default_metrics(self, curr: OrderBookSnapshot) -> Dict[str, Any]:
        """Default return structure when insufficient snapshots exist."""
        mid = (curr.bids[0].price + curr.asks[0].price) / 2.0 if curr.bids and curr.asks else 100.0
        return {
            "symbol": self.symbol,
            "timestamp": curr.timestamp,
            "mid_price": round(mid, 2),
            "spread": round(curr.asks[0].price - curr.bids[0].price, 2) if curr.bids and curr.asks else 0.01,
            "depth_levels": min(len(curr.bids), len(curr.asks)),
            "raw_ofi": 0.0,
            "deep_ofi_score": 0.0,
            "is_spoof_buy_wall": False,
            "spoof_buy_details": {},
            "is_spoof_sell_wall": False,
            "spoof_sell_details": {},
            "is_iceberg_accumulation": False,
            "iceberg_details": {},
            "bid_center_of_mass": mid,
            "ask_center_of_mass": mid,
            "bvwp_velocity": 0.0,
            "liquidity_hole_above": False,
            "liquidity_hole_below": False,
            "summary_signal": "INITIALIZING",
            "confidence_boost": 0,
            "bids_snapshot": [{"price": b.price, "size": b.size} for b in curr.bids],
            "asks_snapshot": [{"price": a.price, "size": a.size} for a in curr.asks],
        }


# ==============================================================================
# Self-Test / Verification Suite
# ==============================================================================
if __name__ == "__main__":
    print("Testing DeepOFIAnalyzer...")
    analyzer = DeepOFIAnalyzer("TSLA", alpha_decay=0.25)

    # 1. Base snapshot (steady book)
    t0 = time.time()
    bids0 = [{"price": 200.0 - i * 0.1, "size": 1000 + i * 200} for i in range(10)]
    asks0 = [{"price": 200.1 + i * 0.1, "size": 1000 + i * 200} for i in range(10)]
    m0 = analyzer.update(bids0, asks0, timestamp=t0)
    print("Snapshot 0:", m0["summary_signal"], "OFI:", m0["deep_ofi_score"])

    # 2. Spoofing scenario: Huge wall at Level 3 ($199.80: 10,000 shares) suddenly disappears
    bids1 = [dict(b) for b in bids0]
    bids1[2]["size"] = 12000  # Massive wall added
    m1 = analyzer.update(bids1, asks0, timestamp=t0 + 0.2)
    print("Snapshot 1 (Wall added): OFI:", m1["deep_ofi_score"])

    bids2 = [dict(b) for b in bids0]
    bids2[2]["size"] = 500  # Wall vanishes (96% cancellation)
    m2 = analyzer.update(bids2, asks0, timestamp=t0 + 0.4)
    print("Snapshot 2 (Wall cancelled):", m2["summary_signal"], "Spoof Alert:", m2["is_spoof_buy_wall"])
    assert m2["is_spoof_buy_wall"] is True, "Failed to detect spoof buy wall!"

    # 3. Iceberg accumulation test: selling hits bid, but bid replenishes
    bids3 = [{"price": 200.0 - i * 0.1, "size": 3000} for i in range(10)]
    trades_absorbed = [{"price": 200.0, "size": 4000, "side": "SELL"}]
    m3 = analyzer.update(bids3, asks0, timestamp=t0 + 0.6, trades=trades_absorbed)
    print("Snapshot 3 (Iceberg):", m3["summary_signal"], "Iceberg Alert:", m3["is_iceberg_accumulation"])
    assert m3["is_iceberg_accumulation"] is True, "Failed to detect iceberg absorption!"

    print("ALL TESTS PASSED SUCCESSFULLY! DeepOFIAnalyzer is fully operational.")
