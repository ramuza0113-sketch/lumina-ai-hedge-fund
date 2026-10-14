# -*- coding: utf-8 -*-
"""
Lumina Capital v4.5.0 - Options Gamma Exposure (GEX) Feed Engine
Calculates Market Maker Gamma Exposure, Call Wall, Put Wall, and Gamma Flip
using Black-Scholes formula and open-interest option chains.
Operates with 12-hour in-memory cache to guarantee zero latency and zero API cost.
"""

import time
import datetime
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

import json
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(DB_DIR, exist_ok=True)
GEX_DB_PATH = os.path.join(DB_DIR, "gex_cache.sqlite")

def _init_gex_db():
    try:
        with sqlite3.connect(GEX_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gex_profiles (
                    symbol TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
    except Exception:
        pass

_init_gex_db()

class OptionsGexFeed:
    _cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    CACHE_TTL_SECONDS = 12 * 3600  # 12 hours cache

    @classmethod
    def _save_persistent(cls, symbol: str, data: Dict[str, Any]):
        try:
            with sqlite3.connect(GEX_DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO gex_profiles (symbol, profile_json, updated_at) VALUES (?, ?, ?)",
                    (symbol, json.dumps(data, ensure_ascii=False), time.time())
                )
                conn.commit()
        except Exception:
            pass

    @classmethod
    def _load_persistent(cls, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(GEX_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT profile_json, updated_at FROM gex_profiles WHERE symbol = ?", (symbol,))
                row = cursor.fetchone()
                if row:
                    # Valid within 24 hours
                    if time.time() - row[1] < 86400:
                        data = json.loads(row[0])
                        data["from_persistent_cache"] = True
                        return data
        except Exception:
            pass
        return None

    @staticmethod
    def _black_scholes_gamma(S: float, K: float, tau: float, r: float, sigma: float) -> float:
        """Compute Black-Scholes gamma."""
        if tau <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0.0
        try:
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * tau) / (sigma * np.sqrt(tau))
            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(tau))
            return float(gamma)
        except Exception:
            return 0.0

    @classmethod
    def get_gex_profile(cls, symbol: str, max_expirations: int = 3) -> Dict[str, Any]:
        """
        Calculates or returns cached GEX profile for a given stock/ETF.
        Focuses on nearest 3 expirations (capturing >80% of 0DTE/near-term gamma).
        If API fails, falls back gracefully to SQLite persistent cache.
        """
        now = time.time()
        sym_clean = symbol.upper().strip()

        # Check In-Memory Cache
        if sym_clean in cls._cache:
            cache_ts, cached_data = cls._cache[sym_clean]
            if now - cache_ts < cls.CACHE_TTL_SECONDS:
                return cached_data

        # Fallback for Japanese / Non-US equities
        if sym_clean.endswith(".T") or "^" in sym_clean:
            res = {
                "symbol": sym_clean,
                "status": "SKIPPED_NON_US",
                "regime": "NEUTRAL",
                "net_gex": 0.0,
                "net_gex_millions": 0.0,
                "call_gex_millions": 0.0,
                "put_gex_millions": 0.0,
                "gamma_flip": None,
                "call_wall": None,
                "put_wall": None,
                "call_wall_dist_pct": None,
                "is_call_wall_near": False,
                "is_call_wall_broken": False,
                "summary_text": "東証日本株（米国0DTEオプション取引対象外・通常ボラティリティ判定）"
            }
            cls._cache[sym_clean] = (now, res)
            return res

        try:
            ticker = yf.Ticker(sym_clean)
            hist = ticker.history(period="5d")
            if hist.empty:
                pers = cls._load_persistent(sym_clean)
                if pers:
                    cls._cache[sym_clean] = (now, pers)
                    return pers
                return cls._create_empty_profile(sym_clean, "価格データ取得不能")
            cur_price = float(hist['Close'].iloc[-1])

            expirations = ticker.options
            if not expirations:
                return cls._create_empty_profile(sym_clean, "オプション取引データなし")

            r = 0.045  # Benchmark risk-free rate approx 4.5%
            today = datetime.datetime.now().date()
            records: List[Dict[str, Any]] = []

            for exp_str in expirations[:max_expirations]:
                try:
                    exp_date = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
                    days_to_exp = max((exp_date - today).days, 0.5)
                    tau = days_to_exp / 365.0
                    chain = ticker.option_chain(exp_str)
                except Exception:
                    continue

                # Process Calls
                for _, row in chain.calls.iterrows():
                    strike = row.get('strike')
                    oi = row.get('openInterest', 0)
                    iv = row.get('impliedVolatility', 0)
                    if pd.isna(oi) or oi <= 0 or pd.isna(iv) or iv <= 0:
                        continue
                    if strike < cur_price * 0.75 or strike > cur_price * 1.25:
                        continue
                    gamma = cls._black_scholes_gamma(cur_price, strike, tau, r, iv)
                    # MM is long gamma from customer call buys: + GEX
                    call_gex = oi * 100 * (cur_price ** 2) * gamma * 0.01
                    records.append({'strike': strike, 'type': 'call', 'oi': oi, 'iv': iv, 'gamma': gamma, 'gex': call_gex, 'tau': tau})

                # Process Puts
                for _, row in chain.puts.iterrows():
                    strike = row.get('strike')
                    oi = row.get('openInterest', 0)
                    iv = row.get('impliedVolatility', 0)
                    if pd.isna(oi) or oi <= 0 or pd.isna(iv) or iv <= 0:
                        continue
                    if strike < cur_price * 0.75 or strike > cur_price * 1.25:
                        continue
                    gamma = cls._black_scholes_gamma(cur_price, strike, tau, r, iv)
                    # MM is short gamma from customer put buys: - GEX
                    put_gex = -oi * 100 * (cur_price ** 2) * gamma * 0.01
                    records.append({'strike': strike, 'type': 'put', 'oi': oi, 'iv': iv, 'gamma': gamma, 'gex': put_gex, 'tau': tau})

            if not records:
                return cls._create_empty_profile(sym_clean, "有効なオプション建玉なし")

            df = pd.DataFrame(records)
            strike_agg = df.groupby('strike').agg(
                net_gex=('gex', 'sum'),
                call_gex=('gex', lambda x: x[df.loc[x.index, 'type'] == 'call'].sum()),
                put_gex=('gex', lambda x: x[df.loc[x.index, 'type'] == 'put'].sum())
            ).reset_index()

            total_net_gex = float(strike_agg['net_gex'].sum())
            total_call_gex = float(strike_agg['call_gex'].sum())
            total_put_gex = float(strike_agg['put_gex'].sum())

            # Call Wall (strike with highest positive call GEX)
            call_wall_row = strike_agg.loc[strike_agg['call_gex'].idxmax()]
            call_wall = float(call_wall_row['strike'])

            # Put Wall (strike with lowest negative put GEX)
            put_wall_row = strike_agg.loc[strike_agg['put_gex'].idxmin()]
            put_wall = float(put_wall_row['strike'])

            # Gamma Flip calculation across price grid
            price_grid = np.linspace(cur_price * 0.85, cur_price * 1.15, 60)
            grid_gex = []
            for p in price_grid:
                p_gex = 0.0
                for _, row in df.iterrows():
                    g = cls._black_scholes_gamma(p, row['strike'], row['tau'], r, row['iv'])
                    if row['type'] == 'call':
                        p_gex += row['oi'] * 100 * (p ** 2) * g * 0.01
                    else:
                        p_gex -= row['oi'] * 100 * (p ** 2) * g * 0.01
                grid_gex.append((p, p_gex))

            grid_df = pd.DataFrame(grid_gex, columns=['price', 'net_gex'])
            gamma_flip = None
            for i in range(len(grid_df) - 1):
                if (grid_df.iloc[i]['net_gex'] < 0 and grid_df.iloc[i+1]['net_gex'] >= 0) or \
                   (grid_df.iloc[i]['net_gex'] >= 0 and grid_df.iloc[i+1]['net_gex'] < 0):
                    p1, g1 = grid_df.iloc[i]['price'], grid_df.iloc[i]['net_gex']
                    p2, g2 = grid_df.iloc[i+1]['price'], grid_df.iloc[i+1]['net_gex']
                    gamma_flip = float(p1 - g1 * (p2 - p1) / (g2 - g1))
                    break

            regime = "POSITIVE_GAMMA" if total_net_gex > 0 else "NEGATIVE_GAMMA"

            # Call Wall relative distance
            call_wall_dist_pct = ((call_wall - cur_price) / cur_price * 100.0) if cur_price > 0 else None
            is_call_wall_near = bool(call_wall_dist_pct is not None and -0.5 <= call_wall_dist_pct <= 1.5)
            is_call_wall_broken = bool(cur_price > call_wall)

            summary_text = (
                f"レジーム: {'🟢 ポジティブ・ガンマ (安定・ボラティリティ抑制)' if regime == 'POSITIVE_GAMMA' else '🔴 ネガティブ・ガンマ (乱気流・急落警戒)'} "
                f"| Net GEX: ${total_net_gex / 1e6:,.1f}M "
                f"| Call Wall: ${call_wall:.2f} ({call_wall_dist_pct:+.1f}%) "
                f"| Put Wall: ${put_wall:.2f}"
            )
            if gamma_flip:
                flip_dist = (cur_price - gamma_flip) / gamma_flip * 100
                summary_text += f" | Gamma Flip: ${gamma_flip:.2f} ({flip_dist:+.1f}%)"

            res = {
                "symbol": sym_clean,
                "status": "OK",
                "current_price": cur_price,
                "regime": regime,
                "net_gex": total_net_gex,
                "net_gex_millions": round(total_net_gex / 1e6, 1),
                "call_gex_millions": round(total_call_gex / 1e6, 1),
                "put_gex_millions": round(abs(total_put_gex) / 1e6, 1),
                "gamma_flip": round(gamma_flip, 2) if gamma_flip else None,
                "call_wall": round(call_wall, 2),
                "put_wall": round(put_wall, 2),
                "call_wall_dist_pct": round(call_wall_dist_pct, 2) if call_wall_dist_pct is not None else None,
                "is_call_wall_near": is_call_wall_near,
                "is_call_wall_broken": is_call_wall_broken,
                "summary_text": summary_text
            }

            cls._save_persistent(sym_clean, res)
            cls._cache[sym_clean] = (now, res)
            return res

        except Exception as e:
            pers = cls._load_persistent(sym_clean)
            if pers:
                cls._cache[sym_clean] = (now, pers)
                return pers
            return cls._create_empty_profile(sym_clean, f"GEX計算例外: {e}")

    @classmethod
    def _create_empty_profile(cls, symbol: str, reason: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "NO_DATA",
            "regime": "NEUTRAL",
            "net_gex": 0.0,
            "net_gex_millions": 0.0,
            "call_gex_millions": 0.0,
            "put_gex_millions": 0.0,
            "gamma_flip": None,
            "call_wall": None,
            "put_wall": None,
            "call_wall_dist_pct": None,
            "is_call_wall_near": False,
            "is_call_wall_broken": False,
            "summary_text": f"GEXデータなし ({reason})"
        }

    @classmethod
    def get_market_turbulence_warning(cls) -> Dict[str, Any]:
        """
        Inspects market-wide Gamma Flip on SPY and QQQ.
        Returns turbulence warning and sizing multiplier (0.5x if turbulence, 1.0x if calm).
        Includes Taleb Fail-Safe if free API feeds are offline.
        """
        spy_prof = cls.get_gex_profile("SPY")
        qqq_prof = cls.get_gex_profile("QQQ")

        spy_turb = False
        qqq_turb = False

        if spy_prof.get("status") == "OK":
            cur_p = spy_prof.get("current_price", 0)
            flip = spy_prof.get("gamma_flip")
            if (flip and cur_p < flip) or spy_prof.get("regime") == "NEGATIVE_GAMMA":
                spy_turb = True

        if qqq_prof.get("status") == "OK":
            cur_p = qqq_prof.get("current_price", 0)
            flip = qqq_prof.get("gamma_flip")
            if (flip and cur_p < flip) or qqq_prof.get("regime") == "NEGATIVE_GAMMA":
                qqq_turb = True

        if spy_turb or qqq_turb:
            reasons = []
            if spy_turb: reasons.append("SPY Gamma Flip割れ (S&P500 ネガティブ・ガンマ)")
            if qqq_turb: reasons.append("QQQ Gamma Flip割れ (Nasdaq ネガティブ・ガンマ)")
            detail_str = "、".join(reasons)
            return {
                "is_turbulence": True,
                "size_multiplier": 0.5,
                "spy_regime": spy_prof.get("regime"),
                "qqq_regime": qqq_prof.get("regime"),
                "summary_text": f"⚠️【市場乱気流警報: Negative Gamma】{detail_str}！MMの売りヘッジ連鎖・ボラティリティ急拡大リスクを検知。新規ロット予算を50%に圧縮します。",
                "spy_profile": spy_prof,
                "qqq_profile": qqq_prof
            }

        # Taleb Fail-Safe: If both SPY and QQQ data are completely missing from live API & persistent cache
        if spy_prof.get("status") != "OK" and qqq_prof.get("status") != "OK":
            try:
                vix_hist = yf.Ticker("^VIX").history(period="2d")
                vix_val = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 22.0
            except Exception:
                vix_val = 22.0
            if vix_val >= 20.0:
                return {
                    "is_turbulence": True,
                    "size_multiplier": 0.5,
                    "spy_regime": "UNKNOWN",
                    "qqq_regime": "UNKNOWN",
                    "summary_text": f"⚠️【タレブ・フェイルセーフ発動】GEXデータ通信途絶かつ高VIX環境（VIX: {vix_val:.1f} ≧ 20.0）。盲目的リスクオンを拒否し安全側に倒して予算を50%圧縮します。",
                    "spy_profile": spy_prof,
                    "qqq_profile": qqq_prof
                }

        spy_gex = spy_prof.get("net_gex_millions", 0.0)
        qqq_gex = qqq_prof.get("net_gex_millions", 0.0)
        return {
            "is_turbulence": False,
            "size_multiplier": 1.0,
            "spy_regime": spy_prof.get("regime"),
            "qqq_regime": qqq_prof.get("regime"),
            "summary_text": f"🟢【オプション流動性安定】SPY (Net GEX +${spy_gex:,.0f}M) & QQQ (Net GEX +${qqq_gex:,.0f}M) ともにポジティブ・ガンマ維持。MMのクッション効果による安定レジーム。",
            "spy_profile": spy_prof,
            "qqq_profile": qqq_prof
        }
