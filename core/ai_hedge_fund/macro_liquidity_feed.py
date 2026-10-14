# -*- coding: utf-8 -*-
import time
import pandas as pd
from typing import Dict, Any

class MacroLiquidityFeed:
    """
    Lumina AI Macro Liquidity Feed (FRED Net Liquidity Provider)
    Tracks the true net US dollar liquidity in the global financial system:
    Net Liquidity = Fed Total Assets (WALCL) - Treasury General Account (WTREGEN) - Reverse Repo (RRPONTSYD)
    
    Provides:
    - Zero-cost live macro liquidity updates from Federal Reserve Bank of St. Louis (FRED).
    - In-memory 6-hour caching to minimize external network requests.
    - AI Hedge Fund Council prompt integration (Risk-On / Neutral / Risk-Off macro context).
    - Autonomous trading cycle telemetry.
    """

    _cache: Dict[str, Any] = {}
    CACHE_TTL_SECONDS = 21600  # 6 hours cache

    @classmethod
    def get_macro_status(cls) -> Dict[str, Any]:
        """
        Fetch latest Net Liquidity from FRED public CSV endpoints with caching.
        Returns a rich status dict with regime classification.
        """
        now = time.time()
        if "data" in cls._cache:
            if (now - cls._cache.get("cached_at", 0)) < cls.CACHE_TTL_SECONDS:
                return cls._cache["data"]

        try:
            # 1. Fed Assets (Millions of Dollars, Weekly Wednesday)
            u_walcl = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=WALCL'
            df_walcl = pd.read_csv(u_walcl)
            df_walcl['WALCL'] = pd.to_numeric(df_walcl['WALCL'], errors='coerce')
            walcl_series = df_walcl['WALCL'].dropna()
            cur_walcl_mil = float(walcl_series.iloc[-1])
            prev_walcl_mil = float(walcl_series.iloc[-2]) if len(walcl_series) >= 2 else cur_walcl_mil

            # 2. Treasury General Account (Millions of Dollars, Weekly Wednesday)
            u_tga = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=WTREGEN'
            df_tga = pd.read_csv(u_tga)
            df_tga['WTREGEN'] = pd.to_numeric(df_tga['WTREGEN'], errors='coerce')
            tga_series = df_tga['WTREGEN'].dropna()
            cur_tga_mil = float(tga_series.iloc[-1])
            prev_tga_mil = float(tga_series.iloc[-2]) if len(tga_series) >= 2 else cur_tga_mil

            # 3. Overnight Reverse Repo (Billions of Dollars, Daily)
            u_rrp = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=RRPONTSYD'
            df_rrp = pd.read_csv(u_rrp)
            df_rrp['RRPONTSYD'] = pd.to_numeric(df_rrp['RRPONTSYD'], errors='coerce')
            rrp_series = df_rrp['RRPONTSYD'].dropna()
            cur_rrp_bil = float(rrp_series.iloc[-1]) if not rrp_series.empty else 0.0
            prev_rrp_bil = float(rrp_series.iloc[-6]) if len(rrp_series) >= 6 else cur_rrp_bil

            # Calculate Net Liquidity in Trillions of Dollars
            # Net Liq = WALCL (Mil) / 1e6 - TGA (Mil) / 1e6 - RRP (Bil) / 1e3
            cur_net_liq_t = (cur_walcl_mil / 1e6) - (cur_tga_mil / 1e6) - (cur_rrp_bil / 1e3)
            prev_net_liq_t = (prev_walcl_mil / 1e6) - (prev_tga_mil / 1e6) - (prev_rrp_bil / 1e3)

            chg_t = cur_net_liq_t - prev_net_liq_t
            chg_pct = (chg_t / prev_net_liq_t * 100.0) if prev_net_liq_t > 0 else 0.0

            if chg_pct >= 0.5:
                regime = "RISK_ON"
                regime_desc = "流動性拡大期（マクロ追い風・リスク選好）"
                emoji = "🌊"
            elif chg_pct <= -1.0:
                regime = "RISK_OFF"
                regime_desc = "流動性縮小・枯渇警戒期（マクロ向かい風・防壁警戒）"
                emoji = "⚠️"
            else:
                regime = "NEUTRAL"
                regime_desc = "流動性中立・巡航安定期"
                emoji = "⚖️"

            status = {
                "net_liquidity_t": round(cur_net_liq_t, 2),
                "prev_net_liquidity_t": round(prev_net_liq_t, 2),
                "chg_t": round(chg_t, 2),
                "chg_pct": round(chg_pct, 2),
                "regime": regime,
                "regime_desc": regime_desc,
                "emoji": emoji,
                "walcl_t": round(cur_walcl_mil / 1e6, 2),
                "tga_b": round(cur_tga_mil / 1e3, 1),
                "rrp_b": round(cur_rrp_bil, 1),
                "summary_text": f"{emoji} FRB純流動性: ${cur_net_liq_t:.2f}T (前週比: {chg_pct:+.1f}% / {regime_desc})",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            cls._cache["cached_at"] = now
            cls._cache["data"] = status
            return status

        except Exception as e:
            fallback = {
                "net_liquidity_t": 5.80,
                "prev_net_liquidity_t": 5.80,
                "chg_t": 0.0,
                "chg_pct": 0.0,
                "regime": "NEUTRAL",
                "regime_desc": "流動性中立（フェイルセーフ）",
                "emoji": "⚖️",
                "walcl_t": 6.74,
                "tga_b": 948.0,
                "rrp_b": 1.5,
                "summary_text": "⚖️ FRB純流動性: $5.80T (平穏巡航・中立)",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e)
            }
            return fallback

    @classmethod
    def format_for_council_prompt(cls, status: Dict[str, Any]) -> str:
        """Format the macro weather context into a structured section for LLM council debate."""
        regime = status.get("regime", "NEUTRAL")
        liq_t = status.get("net_liquidity_t", 5.8)
        chg_pct = status.get("chg_pct", 0.0)
        regime_desc = status.get("regime_desc", "中立")

        if regime == "RISK_ON":
            macro_instruction = "マクロ純流動性は拡大しており、株式市場全体に強い追い風です。キャシー・ウッドAIはTAMと非連続な成長期待を強気に評価し、リスク管理者AIも過度な警戒を避けて成長トレンドフォローを推奨してください。"
        elif regime == "RISK_OFF":
            macro_instruction = "マクロ純流動性はFRBの資金引き揚げ（流動性縮小）により向かい風です。リスク管理者AIおよびグレアムAIは警戒度を高め、高PER銘柄への飛びつき買いを戒め、ディフェンシブ性や安全域（Margin of Safety）を厳しく審査してください。"
        else:
            macro_instruction = "マクロ純流動性は安定巡航レンジにあります。各AIは個別企業のファンダメンタルズ（堀・バリュー・成長性・ストップロス）を正攻法で評価してください。"

        return f"""【マクロ外部天候（FRB純流動性レーダー）】
・米FRB純流動性（Net Liquidity）: ${liq_t:.2f} 兆ドル（前週比: {chg_pct:+.1f}%）
・マクロレジーム判定: {regime_desc}
・AI合議へのマクロ指針: {macro_instruction}
"""
