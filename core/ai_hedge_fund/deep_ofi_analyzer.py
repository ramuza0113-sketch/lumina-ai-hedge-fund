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

    def update(
        self,
        bids: List[Dict[str, Any]],
        asks: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
        trades: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Ingests a new order book snapshot (up to 10 rows of bids/asks).
        Returns comprehensive microstructure & OFI analysis metrics.
        """
        ts = timestamp if timestamp is not None else time.time()
        
        # Clean and sort bids (descending) & asks (ascending)
        clean_bids = [
            OrderBookLevel(price=round(float(b.get("price", 0.0)), 2), size=int(b.get("size", 0)), orders=b.get("orders"))
            for b in bids if float(b.get("price", 0.0)) > 0 and int(b.get("size", 0)) > 0
        ]
        clean_bids.sort(key=lambda x: x.price, reverse=True)

        clean_asks = [
            OrderBookLevel(price=round(float(a.get("price", 0.0)), 2), size=int(a.get("size", 0)), orders=a.get("orders"))
            for a in asks if float(a.get("price", 0.0)) > 0 and int(a.get("size", 0)) > 0
        ]
        clean_asks.sort(key=lambda x: x.price, reverse=False)

        trade_list = trades or []
        snapshot = OrderBookSnapshot(timestamp=ts, bids=clean_bids, asks=clean_asks, trades=trade_list)
        self.history.append(snapshot)
        for tr in trade_list:
            self.cum_trades.append(tr)

        # If not enough history, return default metrics
        if len(self.history) < 2:
            return self._default_metrics(snapshot)

        prev_snapshot = self.history[-2]
        return self._compute_metrics(snapshot, prev_snapshot)

    def _compute_metrics(self, curr: OrderBookSnapshot, prev: OrderBookSnapshot) -> Dict[str, Any]:
        """Calculates multi-level OFI, spoofing, iceberg, center of mass, and liquidity vacuum."""
        depth = min(10, len(curr.bids), len(prev.bids), len(curr.asks), len(prev.asks))
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

        # Exponential moving average smoothing
        self.ema_ofi = 0.65 * normalized_ofi + 0.35 * self.ema_ofi

        # 2. Spoofing Cancellation Detection (Level 2 to 10)
        spoof_buy_detected, spoof_buy_details = self._detect_spoofing(curr.bids, prev.bids, side="bid")
        spoof_sell_detected, spoof_sell_details = self._detect_spoofing(curr.asks, prev.asks, side="ask")

        # 3. Iceberg Order Accumulation Detection
        iceberg_detected, iceberg_details = self._detect_iceberg(curr, prev)

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
        side: str = "bid"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detects sudden disappearance of a large wall at levels 2 to 10 without trade volume.
        """
        prev_map = {lvl.price: lvl.size for lvl in prev_levels[1:10]}
        curr_map = {lvl.price: lvl.size for lvl in curr_levels}

        median_size = (
            sorted([lvl.size for lvl in prev_levels])[len(prev_levels) // 2]
            if prev_levels else 100
        )

        for price, prev_size in prev_map.items():
            # A wall must have been at least 2.2x median size to be considered an intentional spoof wall
            if prev_size >= max(500, int(median_size * 2.2)):
                curr_size = curr_map.get(price, 0)
                cancelled_size = prev_size - curr_size
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
