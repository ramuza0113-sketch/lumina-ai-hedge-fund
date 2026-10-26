# -*- coding: utf-8 -*-
"""
Cis Flow Sniper & False Breakdown Shield Engine
------------------------------------------------
Level 2 気配板、出来高プロファイルPOC、VWAP、OFI（注文流不均衡）を統合し、
ストップ狩り防止（ATR 0.8%〜1.2%呼吸バッファ）を備えた
デイトレ専用の高精度スナイパー執行エンジン。
"""

import math
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from core.ai_hedge_fund.volume_clock_sampler import VolumeClockSampler

logger = logging.getLogger("cis_flow_sniper")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class CisFlowSniper:
    """
    cis需給スナイパー ＆ ストップ狩り防止判定エンジン
    """

    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        return df

    @staticmethod
    def compute_poc(lows: np.ndarray, highs: np.ndarray, closes: np.ndarray, volumes: np.ndarray, num_bins: int = 25) -> float:
        """
        直近ウィンドウの出来高プロファイルPOC（Point of Control: 最大商い価格帯）を算出
        """
        if len(closes) == 0:
            return 0.0
        typical_prices = (highs + lows + closes) / 3.0
        min_p, max_p = float(np.min(lows)), float(np.max(highs))
        if max_p <= min_p:
            return float(closes[-1])
        bins = np.linspace(min_p, max_p, num_bins)
        bin_indices = np.digitize(typical_prices, bins)
        vol_per_bin = np.zeros(len(bins), dtype=np.float64)
        np.add.at(vol_per_bin, np.clip(bin_indices, 0, len(bins) - 1), volumes)
        max_idx = int(np.argmax(vol_per_bin))
        return float(bins[min(max_idx, len(bins) - 1)])

    @classmethod
    def compute_vwap(cls, df: pd.DataFrame) -> pd.Series:
        """
        当日セッションのVWAP（出来高加重平均価格）を算出
        """
        df = cls._normalize_df(df)
        try:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
            volume = df["volume"]
            
            # 日付ごとのグループ化（日中VWAP）
            if isinstance(df.index, pd.DatetimeIndex):
                dates = df.index.date
                vwap_series = pd.Series(index=df.index, dtype=float)
                for d in np.unique(dates):
                    mask = (dates == d)
                    tp = typical_price[mask]
                    v = volume[mask]
                    cum_vol = v.cumsum()
                    cum_vp = (tp * v).cumsum()
                    vwap_series[mask] = np.where(cum_vol > 0, cum_vp / cum_vol, tp)
                return vwap_series
            else:
                cum_vol = volume.cumsum()
                cum_vp = (typical_price * volume).cumsum()
                return np.where(cum_vol > 0, cum_vp / cum_vol, typical_price)
        except Exception as e:
            logger.warning(f"VWAP計算エラー: {e}")
            return (df["high"] + df["low"] + df["close"]) / 3.0

    @classmethod
    def compute_atr(cls, df: pd.DataFrame, period: int = 14) -> float:
        """
        短期ATR（Average True Range: 平均実質変動幅）を算出
        """
        df = cls._normalize_df(df)
        try:
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values
            n = len(df)
            if n < 2:
                return float((high[-1] - low[-1]) if n == 1 else 1.0)

            tr_list = []
            for i in range(1, n):
                hl = high[i] - low[i]
                hc = abs(high[i] - close[i - 1])
                lc = abs(low[i] - close[i - 1])
                tr_list.append(max(hl, hc, lc))

            window = min(period, len(tr_list))
            return float(np.mean(tr_list[-window:])) if window > 0 else 1.0
        except Exception as e:
            logger.warning(f"ATR計算エラー: {e}")
            return 1.0

    @classmethod
    def evaluate_sniper_setup(
        cls,
        symbol: str,
        df: pd.DataFrame,
        order_book: Optional[Dict[str, Any]] = None,
        min_risk_reward: float = 1.5,
        atr_buffer_mult: float = 0.8,
        lookback_window: int = 30,
        use_volume_clock: bool = True
    ) -> Dict[str, Any]:
        """
        スナイパーエントリーおよびストップ狩り防止OCOブラケット価格を評価
        （v6.4.3: Cache-Resident SoA 出来高クロック VolumeClockSampler ＆ 情報流速 flow_velocity 統合）
        """
        df = cls._normalize_df(df)
        if df is None or len(df) < lookback_window:
            return {"triggered": False, "reason": "データ不足"}

        # ⚡ SoA 出来高クロック（Volume Bars）への変換とノイズ除去
        clock_mode = "WALL_CLOCK"
        active_df = df
        if use_volume_clock:
            try:
                vol_df = VolumeClockSampler.to_volume_bars(df, bars_per_day=32)
                if vol_df is not None and len(vol_df) >= max(20, lookback_window):
                    active_df = vol_df
                    clock_mode = "VOLUME_CLOCK_SOA"
            except Exception as e_vc:
                logger.warning(f"[{symbol}] VolumeClock変換フォールバック: {e_vc}")

        eff_lookback = min(lookback_window, len(active_df) - 2)
        closes = active_df["close"].to_numpy(dtype=np.float64)
        opens = active_df["open"].to_numpy(dtype=np.float64)
        highs = active_df["high"].to_numpy(dtype=np.float64)
        lows = active_df["low"].to_numpy(dtype=np.float64)
        volumes = active_df["volume"].to_numpy(dtype=np.float64)

        cur_close = float(closes[-1])
        cur_open = float(opens[-1])
        cur_high = float(highs[-1])
        cur_low = float(lows[-1])
        cur_vol = float(volumes[-1])

        # 1. VWAP環境認識 (pandas-ta 思想: VWAPより上は大口優勢)
        vwap_series = cls.compute_vwap(df)
        cur_vwap = float(vwap_series.iloc[-1])
        is_above_vwap = cur_close >= (cur_vwap * 0.998) # わずかな誤差許容

        # 2. 直近ウィンドウの需給の壁 ＆ 出来高プロファイルPOC (HFT-Orderbook 思想)
        hist_lows = lows[-eff_lookback - 1 : -1]
        hist_highs = highs[-eff_lookback - 1 : -1]
        hist_closes = closes[-eff_lookback - 1 : -1]
        hist_vols = volumes[-eff_lookback - 1 : -1]
        support_wall = float(np.min(hist_lows))
        resistance_wall = float(np.max(hist_highs))
        poc_wall = cls.compute_poc(hist_lows, hist_highs, hist_closes, hist_vols)

        # Level 2板情報からの大口壁の補正および深層OFI解析
        l2_bid_wall = None
        l2_ask_wall = None
        ofi_analysis = {}
        if order_book:
            bids = order_book.get("bids", [])
            asks = order_book.get("asks", [])
            ofi_analysis = order_book.get("ofi_analysis") or {}
            if bids:
                max_b = max(bids, key=lambda x: x.get("size", 0))
                l2_bid_wall = max_b.get("price")
            if asks:
                max_a = max(asks, key=lambda x: x.get("size", 0))
                l2_ask_wall = max_a.get("price")

        # 3. 【深層OFI防衛①】見せ板（スプーフィング）トラップの回避
        if ofi_analysis.get("is_spoof_buy_wall"):
            spoof_info = ofi_analysis.get("spoof_buy_details") or {}
            return {
                "triggered": False,
                "reason": f"⚠️ 見せ板（スプーフィング）急キャンセル検知: だましトラップ回避 ({spoof_info.get('reason', '買い壁急消滅')})",
                "is_spoof_trap": True,
                "cur_price": cur_close,
                "clock_mode": clock_mode,
                "ofi_analysis": ofi_analysis
            }

        # 最終的な防衛壁
        effective_support = l2_bid_wall if (l2_bid_wall and abs(l2_bid_wall - support_wall) / cur_close < 0.03) else support_wall
        effective_resistance = l2_ask_wall if (l2_ask_wall and abs(l2_ask_wall - resistance_wall) / cur_close < 0.03) else resistance_wall

        # 4. 出来高クロック情報流速（Flow Velocity）＆ 出来高急増判定
        avg_vol = float(np.mean(volumes[-20:-1])) if len(volumes) >= 21 else cur_vol
        vol_ratio = (cur_vol / avg_vol) if avg_vol > 0 else 1.0
        if "flow_velocity" in active_df.columns:
            flow_velocity = float(active_df["flow_velocity"].iloc[-1])
        else:
            flow_velocity = vol_ratio

        effective_flow_ratio = max(vol_ratio, flow_velocity)
        is_bullish_bar = cur_close > cur_open
        is_volume_spike = (effective_flow_ratio >= 1.80) and is_bullish_bar

        # 5. ストップ狩りリクレイム（Sweep & Reclaim）の判定
        is_reclaim = (cur_low < effective_support) and (cur_close > effective_support) and (effective_flow_ratio >= 1.50)

        # 6. 支持壁またはPOC（最大出来高価格帯）からの反発エントリー条件
        dist_to_support_pct = ((cur_close - effective_support) / cur_close) * 100.0
        dist_to_poc_pct = ((cur_close - poc_wall) / cur_close) * 100.0 if poc_wall > 0 else 99.0
        is_near_wall_or_poc = (0.15 <= dist_to_support_pct <= 2.5) or (0.05 <= dist_to_poc_pct <= 1.6)
        is_bounce_zone = is_near_wall_or_poc and is_volume_spike and is_above_vwap

        # 7. 【深層OFI好機②】アイスバーグ買い集め & 板重心上方加速のトリガー連携
        is_iceberg = ofi_analysis.get("is_iceberg_accumulation", False)
        deep_ofi_score = ofi_analysis.get("deep_ofi_score", 0.0)
        bvwp_vel = ofi_analysis.get("bvwp_velocity", 0.0)

        is_front_run = (deep_ofi_score >= 45.0) and (bvwp_vel > 0.01) and (dist_to_support_pct <= 2.5) and is_above_vwap
        is_iceberg_trigger = is_iceberg and (dist_to_support_pct <= 2.5) and is_above_vwap

        triggered = is_bounce_zone or is_reclaim or is_iceberg_trigger or is_front_run
        
        if is_reclaim:
            trigger_type = "RECLAIM_AFTER_SWEEP"
        elif is_iceberg_trigger:
            trigger_type = "ICEBERG_STEALTH_REBOUND"
        elif is_front_run:
            trigger_type = "OFI_MOMENTUM_FRONT_RUN"
        elif is_bounce_zone:
            trigger_type = "VOL_CLOCK_WHALE_BOUNCE" if clock_mode == "VOLUME_CLOCK_SOA" else "BOUNCE_FROM_SUPPORT"
        else:
            trigger_type = "NONE"

        if not triggered:
            return {
                "triggered": False,
                "reason": "トリガー未成立",
                "clock_mode": clock_mode,
                "cur_price": cur_close,
                "cur_vwap": round(cur_vwap, 2),
                "is_above_vwap": is_above_vwap,
                "vol_ratio": round(effective_flow_ratio, 2),
                "flow_velocity": round(flow_velocity, 2),
                "poc_wall": round(poc_wall, 2),
                "support_wall": round(effective_support, 2),
                "resistance_wall": round(effective_resistance, 2),
                "dist_to_support_pct": round(dist_to_support_pct, 2),
                "ofi_analysis": ofi_analysis
            }

        # 6. 【最重要】動的アダプティブATRバッファ（0.8x〜1.2x）によるストップ狩り防止損切り・利確価格の算出
        atr = cls.compute_atr(active_df, period=14)
        atr_pct = (atr / cur_close) if cur_close > 0 else 0.01

        # 銘柄ボラティリティ判定（TSLA, NVDA等の高ボラ銘柄、またはATR%が0.7%以上）
        is_high_vol = symbol.upper() in ["TSLA", "NVDA", "AMD", "PLTR", "ARM"] or (atr_pct >= 0.007)

        # 時間帯判定: 米国開場直後（日本時間 22:30〜23:15 / 冬23:30〜00:15 JST）または東証寄り付き（09:00〜09:45 JST）
        import datetime
        now_dt = datetime.datetime.now()
        cur_h = now_dt.hour
        cur_m = now_dt.minute
        is_us_open_rush = (cur_h == 22 and cur_m >= 30) or (cur_h == 23 and cur_m <= 15) or (cur_h == 0 and cur_m <= 15)
        is_jp_open_rush = (cur_h == 9 and cur_m <= 45)
        is_opening_rush = is_us_open_rush or is_jp_open_rush

        # 0.8x 〜 1.2x 動的マルチプライヤー決定
        if atr_buffer_mult != 0.8:
            effective_mult = atr_buffer_mult
        elif is_high_vol and is_opening_rush:
            effective_mult = 1.20  # 【最大防衛】高ボラ株の寄り付き乱気流は最も深いストップ狩り対策
        elif is_high_vol or is_opening_rush:
            effective_mult = 1.00  # 【中間防衛】高ボラ株の通常時、または低ボラ株の寄り付き
        else:
            effective_mult = 0.80  # 【損小利大最優先】低ボラ株の日中安定期はタイトに維持

        atr_buffer = atr * effective_mult

        # 損切りライン: 買い壁から 動的ATRバッファ（0.8x〜1.2x）を引いた安全位置！
        stop_loss_price = round(effective_support - atr_buffer, 2)
        # 万が一計算で買値以上になってしまった場合のセーフティ
        if stop_loss_price >= cur_close:
            stop_loss_price = round(cur_close * 0.985, 2)

        # 利確ライン: 直近売り壁の0.3%手前
        take_profit_price = round(effective_resistance * 0.997, 2)
        if take_profit_price <= cur_close:
            take_profit_price = round(cur_close * 1.025, 2)

        risk_amount = cur_close - stop_loss_price
        reward_amount = take_profit_price - cur_close

        # リスクリワード比フィルター (損小利大が1.5倍未満なら見送り)
        if risk_amount <= 0 or reward_amount <= 0:
            return {"triggered": False, "reason": "リスクリワード算出不可", "clock_mode": clock_mode}

        rr_ratio = reward_amount / risk_amount
        if rr_ratio < min_risk_reward:
            return {
                "triggered": False,
                "reason": f"リスクリワード不足 (RR: {rr_ratio:.2f} < 最低 {min_risk_reward}倍)",
                "clock_mode": clock_mode,
                "cur_price": cur_close,
                "take_profit": take_profit_price,
                "stop_loss": stop_loss_price
            }

        return {
            "triggered": True,
            "signal": "BUY",
            "trigger_type": trigger_type,
            "clock_mode": clock_mode,
            "symbol": symbol,
            "cur_price": cur_close,
            "entry_price": cur_close,
            "target_price": take_profit_price,
            "take_profit_price": take_profit_price,
            "stop_loss_price": stop_loss_price,
            "reason": f"需給壁反発({trigger_type} / 流速{effective_flow_ratio:.2f}x) / 動的バッファ {effective_mult:.2f}x ATR",
            "risk_reward_ratio": round(rr_ratio, 2),
            "expected_gain_pct": round((take_profit_price / cur_close - 1.0) * 100, 2),
            "expected_loss_pct": round((1.0 - stop_loss_price / cur_close) * 100, 2),
            "atr": round(atr, 2),
            "atr_buffer": round(atr_buffer, 2),
            "atr_buffer_mult": effective_mult,
            "buffer_desc": f"{effective_mult:.2f}x ATR",
            "support_wall": round(effective_support, 2),
            "resistance_wall": round(effective_resistance, 2),
            "poc_wall": round(poc_wall, 2),
            "cur_vwap": round(cur_vwap, 2),
            "vol_ratio": round(effective_flow_ratio, 2),
            "flow_velocity": round(flow_velocity, 2),
            "strategy": "DAY_CIS_SNIPER",
            "ofi_analysis": ofi_analysis,
            "deep_ofi_score": ofi_analysis.get("deep_ofi_score", 0.0)
        }
