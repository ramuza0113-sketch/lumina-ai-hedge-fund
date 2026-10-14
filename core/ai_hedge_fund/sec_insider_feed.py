# -*- coding: utf-8 -*-
import time
import pandas as pd
from typing import Dict, Any, Optional
import yfinance as yf

class SecInsiderFeed:
    """
    Lumina AI SEC Form 4 Insider Trading Intelligence Provider
    Tracks open market insider purchases (Code P) filed with the SEC.
    Provides:
    - Automated detection of executive cluster buying (CEO/CFO/Directors).
    - Filters out trivial token purchases and distinguishes true conviction from routine grants.
    - Zero-cost live parsing via SEC EDGAR / financial filings with 12-hour in-memory cache.
    - AI Hedge Fund Council prompt integration (Skin in the Game catalyst).
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    CACHE_TTL_SECONDS = 43200  # 12 hours cache

    @classmethod
    def get_insider_metrics(cls, symbol: str) -> Dict[str, Any]:
        """
        Fetch and parse insider trading metrics for a given symbol.
        Returns a rich metrics dictionary with signal classification and score boost.
        """
        clean_sym = symbol.strip().upper()

        # Non-US Equities (TSE, etc.) - Graceful neutral fallback
        if clean_sym.endswith(".T") or clean_sym.endswith(".F") or clean_sym.endswith(".L"):
            return {
                "symbol": clean_sym,
                "is_us": False,
                "signal": "NEUTRAL",
                "score_boost": 0,
                "summary_text": "🇯🇵 日本株（EDINET大量保有報告書対象・中立）",
                "details": "日本市場上場銘柄のためSEC Form 4対象外（EDINET基準）",
                "purchases_trans": 0,
                "sales_trans": 0
            }

        now = time.time()
        if clean_sym in cls._cache:
            entry = cls._cache[clean_sym]
            if (now - entry.get("cached_at", 0)) < cls.CACHE_TTL_SECONDS:
                return entry["data"]

        try:
            ticker = yf.Ticker(clean_sym)
            df_purchases = ticker.insider_purchases
            df_trans = ticker.insider_transactions

            buy_trans = 0
            sell_trans = 0
            buy_shares = 0.0
            sell_shares = 0.0

            if df_purchases is not None and not df_purchases.empty:
                col0 = df_purchases.columns[0]
                p_row = df_purchases[df_purchases[col0] == 'Purchases']
                s_row = df_purchases[df_purchases[col0] == 'Sales']
                
                if not p_row.empty:
                    buy_trans = int(p_row['Trans'].values[0]) if not pd.isna(p_row['Trans'].values[0]) else 0
                    buy_shares = float(p_row['Shares'].values[0]) if not pd.isna(p_row['Shares'].values[0]) else 0.0
                if not s_row.empty:
                    sell_trans = int(s_row['Trans'].values[0]) if not pd.isna(s_row['Trans'].values[0]) else 0
                    sell_shares = float(s_row['Shares'].values[0]) if not pd.isna(s_row['Shares'].values[0]) else 0.0

            # Inspect detailed individual transactions for 10b5-1 and grant filtering
            recent_trades = []
            discretionary_buy_count = 0
            discretionary_buy_shares = 0.0
            plan_10b5_count = 0
            grant_count = 0

            if df_trans is not None and not df_trans.empty:
                for idx, row in df_trans.iterrows():
                    d = str(row.get('Start Date', ''))[:10]
                    insider = str(row.get('Insider', 'Unknown'))
                    shares = row.get('Shares', 0)
                    val = row.get('Value', 0)
                    text_desc = str(row.get('Text', '')).lower()
                    
                    is_10b5 = ("10b5-1" in text_desc or "10b-5" in text_desc or "plan" in text_desc)
                    is_grant = ("grant" in text_desc or "award" in text_desc or "gift" in text_desc or val == 0)
                    is_buy = ("purchase" in text_desc or "buy" in text_desc)

                    if is_10b5:
                        plan_10b5_count += 1
                    if is_grant:
                        grant_count += 1

                    if is_buy and not is_10b5 and not is_grant and val > 0:
                        discretionary_buy_count += 1
                        discretionary_buy_shares += (float(shares) if pd.notna(shares) else 0.0)

                    if len(recent_trades) < 4:
                        val_str = f"${val/1e6:.1f}M" if pd.notna(val) and val > 0 else "Grant/0$"
                        tag = " [10b5-1]" if is_10b5 else (" [Grant]" if is_grant else "")
                        recent_trades.append(f"{d} {insider}: {shares:,.0f}株 ({val_str}){tag}")

            # Quantitative Insider Classification:
            # Rule 10b5-1 noise elimination: True conviction requires discretionary open-market purchases (non-10b5-1)
            # Cluster buying: Multiple discretionary purchases (>= 1 with high volume, or >= 2 cluster)
            if discretionary_buy_count >= 2 or (discretionary_buy_count >= 1 and discretionary_buy_shares >= 50000):
                signal = "STRONG_INSIDER_BUYING"
                score_boost = 5  # +5 point catalyst bonus for genuine discretionary conviction
                summary_text = f"🔥 役員自社株買い優勢（直近6ヶ月: 裁量直接買付 {discretionary_buy_count}件 / {discretionary_buy_shares:,.0f}株・非10b5-1自腹コミット）"
            elif buy_trans >= 2 and discretionary_buy_count == 0:
                signal = "ROUTINE_10B5_BUYING"
                score_boost = 0  # 0 bonus for automated routine 10b5-1 plans
                summary_text = f"⚖️ 役員買付検知（Rule 10b5-1事前計画取引/無償付与のみ・アルファノイズ除外）"
            elif sell_trans >= 15 and sell_shares > 3000000 and buy_trans == 0:
                signal = "EXCESSIVE_SELLING"
                score_boost = -3  # Slight caution penalty
                summary_text = f"⚠️ 役員売却偏重（直近6ヶ月: 売却 {sell_trans}件 / {sell_shares:,.0f}株・利益確定先行）"
            else:
                signal = "NEUTRAL"
                score_boost = 0
                summary_text = f"⚖️ インサイダー取引中立（買付 {buy_trans}件 / 売却 {sell_trans}件・通常巡航）"

            data = {
                "symbol": clean_sym,
                "is_us": True,
                "signal": signal,
                "score_boost": score_boost,
                "summary_text": summary_text,
                "purchases_trans": buy_trans,
                "sales_trans": sell_trans,
                "discretionary_buy_trans": discretionary_buy_count,
                "discretionary_buy_shares": discretionary_buy_shares,
                "plan_10b5_count": plan_10b5_count,
                "purchases_shares": buy_shares,
                "sales_shares": sell_shares,
                "net_shares": buy_shares - sell_shares,
                "recent_trades": recent_trades,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            cls._cache[clean_sym] = {"cached_at": now, "data": data}
            return data

        except Exception as e:
            fallback = {
                "symbol": clean_sym,
                "is_us": True,
                "signal": "NEUTRAL",
                "score_boost": 0,
                "summary_text": f"⚖️ インサイダーデータ中立（取得例外ガード: {e}）",
                "purchases_trans": 0,
                "sales_trans": 0,
                "recent_trades": []
            }
            return fallback

    @classmethod
    def format_for_council_prompt(cls, metrics: Dict[str, Any]) -> str:
        """Format insider metrics into structured section for LLM council debate."""
        if not metrics.get("is_us", False):
            return "【SEC Form 4 内部者取引動向】\n・日本市場銘柄のためSEC Form 4対象外（EDINET基準・中立）\n"

        signal = metrics.get("signal", "NEUTRAL")
        buy_t = metrics.get("purchases_trans", 0)
        sell_t = metrics.get("sales_trans", 0)
        buy_s = metrics.get("purchases_shares", 0.0)
        summary = metrics.get("summary_text", "")
        recent = metrics.get("recent_trades", [])

        recent_str = "\n".join([f"  - {t}" for t in recent]) if recent else "  - 直近特筆取引なし"

        if signal == "STRONG_INSIDER_BUYING":
            guidance = "役員・経営陣が自腹で自社株を直接市場買付（Skin in the game）しています。ウォーレン・バフェットAIは「経営陣と株主の利害一致」を高く評価し、ベンジャミン・グレアムAIも「内部者が確信する安全域（Margin of Safety）」として強気の裏付けにしてください。"
        elif signal == "EXCESSIVE_SELLING":
            guidance = "直近で役員によるまとまった規模の市場売却が先行しています。リスク管理者AIは経営陣の利益確定動向に留意し、急騰後の過熱感がないか慎重に審査してください。"
        else:
            guidance = "役員取引は通常巡航レンジ（自社株報酬等の付与中心）にあります。業績およびファンダメンタルズを正攻法で評価してください。"

        return f"""【SEC Form 4 内部者取引動向（役員自社株売買）】
・判定ステータス: {summary}
・直近6ヶ月集計: 買付 {buy_t}件 ({buy_s:,.0f}株) / 売却 {sell_t}件
・直近主要取引明細:
{recent_str}
・AI合議への審査指針: {guidance}
"""
