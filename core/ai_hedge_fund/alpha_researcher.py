# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Autonomous Alpha Researcher (Phase 3)
Continuously surveys the 100-stock universe during market-closed hours (weekends),
applies quantitative mathematical pre-filtering, and uses Gemini 3.7 Flash
to curate the "Weekly Top 5 Alpha Portfolio Picks" for Monday morning.
"""

import os
import time
import json
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.market_screener import MarketScreener
from core.ai_hedge_fund.agents.portfolio_manager_agent import PortfolioManagerAgent
from core.ai_hedge_fund.macro_liquidity_feed import MacroLiquidityFeed
from core.ai_hedge_fund.options_gex_feed import OptionsGexFeed
from core.state_manager import load_app_settings
from google import genai
from google.genai import types

class AlphaResearcher:
    """
    Autonomous Alpha Discovery Engine:
    Conducts weekend research runs without blocking weekday trading operations.
    Combines 100% free Python fundamental quantitative filtering with
    Gemini 3.7 Flash deep synthesis.
    """

    BRIEFING_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "ai_hedge_fund", "weekly_alpha_briefing.json"
    )

    @classmethod
    def get_latest_briefing(cls) -> Optional[Dict[str, Any]]:
        """Retrieve the cached weekly alpha briefing"""
        try:
            if os.path.exists(cls.BRIEFING_PATH):
                with open(cls.BRIEFING_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[AlphaResearcher] Error reading briefing: {e}")
        return None

    @classmethod
    def get_universe_tickers(cls) -> List[Dict[str, str]]:
        """
        Aggregate the 100-stock universe:
        - Curated themes: Defense/Energy, AI Growth, Value/Dividend, Deep Value, Europe
        - Custom user watchlist
        """
        all_items: List[Dict[str, str]] = []
        seen = set()

        # 1. Add User Custom Watchlist first (Priority)
        custom_items = MarketScreener.get_custom_watchlist()
        for ci in custom_items:
            s = ci.get("symbol", "").strip()
            if s and s not in seen:
                seen.add(s)
                all_items.append({
                    "symbol": s,
                    "name": ci.get("company_name", s),
                    "category": "⭐ ユーザー厳選マイ監視銘柄",
                    "priority": "HIGH"
                })

        # 2. Add Curated Thematic Universes
        for cat_key, items in MarketScreener.UNIVERSE.items():
            for item in items:
                s = item.get("symbol", "").strip()
                if s and s not in seen:
                    seen.add(s)
                    all_items.append({
                        "symbol": s,
                        "name": item.get("name", s),
                        "category": item.get("category", cat_key),
                        "priority": "NORMAL"
                    })

        return all_items

    @classmethod
    def run_research_scan(cls, max_deep_candidates: int = 12) -> Dict[str, Any]:
        """
        Execute the full autonomous alpha discovery workflow:
        1. Fast quantitative scoring on universe (PBR, ROE, FCF, Momentum) - 0 API cost.
        2. Select top candidates.
        3. Gemini 3.7 Flash deep synthesis into Top 5 Weekly Alpha Picks.
        4. Persist to data/ai_hedge_fund/weekly_alpha_briefing.json.
        """
        print("[AlphaResearcher] Starting autonomous alpha exploration...", flush=True)
        universe = cls.get_universe_tickers()
        
        # Step 1: Parallel quantitative evaluation (0 token cost)
        scored_candidates = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_item = {
                executor.submit(cls._evaluate_quant_score, item): item
                for item in universe
            }
            for future in as_completed(future_to_item):
                try:
                    res = future.result()
                    if res:
                        scored_candidates.append(res)
                except Exception as err:
                    pass

        # Sort by quantitative score descending
        scored_candidates.sort(key=lambda x: x.get("quant_score", 0), reverse=True)
        top_candidates = scored_candidates[:max_deep_candidates]

        # Step 1.5: Walk-Forward Backtest on Top Candidates (RD-Agent Statistical Validation)
        try:
            from core.ai_hedge_fund.alpha_backtester import AlphaHypothesisBacktester
            with ThreadPoolExecutor(max_workers=4) as bt_executor:
                bt_futures = {
                    bt_executor.submit(AlphaHypothesisBacktester.test_alpha_hypothesis, cand["symbol"]): cand
                    for cand in top_candidates
                }
                for f in as_completed(bt_futures):
                    c_item = bt_futures[f]
                    try:
                        c_item["backtest"] = f.result()
                    except Exception as err:
                        c_item["backtest"] = AlphaHypothesisBacktester._empty_backtest(c_item["symbol"], f"検証エラー: {err}")
        except Exception as bte:
            print(f"[AlphaResearcher] Backtest validation error: {bte}")

        # Step 2: Fetch Macro Climate & GEX Context
        macro = MacroLiquidityFeed.get_macro_status()
        turb = OptionsGexFeed.get_market_turbulence_warning()
        context_data = {
            "macro_liquidity": macro,
            "options_gex": {"market_turbulence": turb.get("summary_text")}
        }
        regime_info = PortfolioManagerAgent.detect_market_regime(context_data)

        # Step 3: Deep AI Synthesis into Top 5 Alpha Briefing
        briefing = cls._generate_ai_briefing(top_candidates, regime_info)

        # Persist to disk
        try:
            os.makedirs(os.path.dirname(cls.BRIEFING_PATH), exist_ok=True)
            with open(cls.BRIEFING_PATH, "w", encoding="utf-8") as f:
                json.dump(briefing, f, ensure_ascii=False, indent=2)
            print(f"[AlphaResearcher] Briefing generated and saved ({len(briefing.get('top_picks', []))} picks).", flush=True)
        except Exception as e:
            print(f"[AlphaResearcher] Save error: {e}")

        # Step 4: Record Statistically Validated Alpha Hypotheses into Neo4j Knowledge Graph
        try:
            from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            if GraphitiMemoryManager.is_available():
                for p in briefing.get("top_picks", []):
                    bt = p.get("backtest", {})
                    if bt and bt.get("is_statistically_valid"):
                        GraphitiMemoryManager.record_alpha_hypothesis(
                            symbol=p.get("symbol", ""),
                            win_rate_pct=bt.get("win_rate_pct", 0.0),
                            profit_factor=bt.get("profit_factor", 0.0),
                            catalyst=p.get("catalyst", ""),
                            confidence_grade=bt.get("confidence_grade", "ALPHA_PROVEN"),
                            conviction_score=p.get("conviction_score", 80)
                        )
        except Exception as ge:
            print(f"[AlphaResearcher] Neo4j graph recording warning: {ge}")

        # Step 5: Dispatch Push Notification to Master (Discord)
        try:
            from core.ai_hedge_fund.hedge_fund_notifier import HedgeFundNotifier
            HedgeFundNotifier.notify_weekly_alpha_briefing(briefing)
        except Exception as ne:
            print(f"[AlphaResearcher] Discord dispatch warning: {ne}")

        return briefing

    @classmethod
    def _evaluate_quant_score(cls, item: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Pure Python quantitative multi-factor calculation (Free).
        Awards points for Value (PBR/PER), Quality (ROE/CF), and Momentum (20d return).
        """
        symbol = item.get("symbol", "")
        try:
            stock_data = MarketDataFeed.get_stock_data(symbol)
            price = stock_data.get("current_price")
            if not price or price <= 0:
                return None

            pb = stock_data.get("pb_ratio")
            pe = stock_data.get("pe_trailing")
            roe = stock_data.get("roe")
            div_yield = stock_data.get("dividend_yield", 0.0)
            ret_20d = stock_data.get("history_metrics", {}).get("return_20d_pct", 0.0)

            score = 50.0  # Base neutral

            # Factor 1: Value / PBR reform
            if pb and pb > 0:
                if pb < 0.8: score += 15.0
                elif pb < 1.0: score += 10.0
                elif pb < 1.8: score += 4.0
                elif pb > 10.0: score -= 8.0

            # Factor 2: PER
            if pe and pe > 0:
                if pe < 12.0: score += 10.0
                elif pe < 20.0: score += 5.0
                elif pe > 60.0: score -= 6.0

            # Factor 3: Quality / ROE
            if roe:
                if roe > 18.0: score += 14.0
                elif roe > 10.0: score += 8.0
                elif roe < 3.0: score -= 8.0

            # Factor 4: Dividend Yield
            if div_yield:
                if div_yield > 3.8: score += 10.0
                elif div_yield > 2.5: score += 5.0

            # Factor 5: Momentum (20-day trend)
            if ret_20d > 8.0: score += 12.0
            elif ret_20d > 2.0: score += 6.0
            elif ret_20d < -12.0: score -= 8.0

            # Priority boost for custom watchlist
            if item.get("priority") == "HIGH":
                score += 5.0

            final_quant_score = int(max(10, min(99, score)))

            return {
                "symbol": symbol,
                "name": stock_data.get("company_name", item.get("name", symbol)),
                "category": item.get("category", "注目銘柄"),
                "current_price": price,
                "currency": stock_data.get("currency", "JPY"),
                "pb_ratio": pb,
                "pe_trailing": pe,
                "roe": roe,
                "dividend_yield": div_yield,
                "return_20d_pct": ret_20d,
                "quant_score": final_quant_score
            }
        except Exception:
            return None

    @classmethod
    def _generate_ai_briefing(
        cls,
        candidates: List[Dict[str, Any]],
        regime_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize final Weekly Top 5 Alpha Picks using Gemini 3.7 Flash"""
        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        def _fmt_bt(c):
            bt = c.get("backtest", {})
            if bt and bt.get("status") == "SUCCESS":
                return f", 過去2年検証: 勝率{bt.get('win_rate_pct')}% (PF {bt.get('profit_factor')}, {bt.get('confidence_grade')})"
            return ""

        cand_text = "\n".join([
            f"- {c['name']} ({c['symbol']}): 現在値 {c['current_price']} {c['currency']}, "
            f"PBR {c['pb_ratio']}倍, PER {c['pe_trailing']}倍, ROE {c['roe']}%, "
            f"配当利回り {c['dividend_yield']}%, 20日リターン {c['return_20d_pct']}%, クオンツスコア: {c['quant_score']}点"
            f"{_fmt_bt(c)}"
            for c in candidates
        ])

        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"""あなたはヘッジファンド Lumina Capital のCIO（最高投資責任者）です。
市場が閉まっている週末に、日米100銘柄ユニバースから定量スクリーニングと【過去2年Walk-Forwardバックテスト検証】を通過した上位候補群を精査し、
月曜朝の市場オープン時に推奨する【今週の特選アルファ銘柄 Top 5】を決定してください。

【現在の市場レジーム】
{regime_info.get('regime_name')} ({regime_info.get('rationale')})

【定量フィルタ＆統計バックテスト通過上位候補リスト】
{cand_text}

【要求事項】
現在の市場レジームに最も適合し、かつ統計的エッジ（過去検証勝率・PF）とリスクリワード比が優れている上位5銘柄を厳選し、
以下のJSON形式のみで出力してください:
{{
  "weekly_theme": "今週のメイン投資テーマ（例: AI電力特需とPBR1倍割れ改善の二刀流）",
  "cio_outlook": "週初めの相場展望とポートフォリオ運用方針（180〜220文字程度の格調高いCIO声明）",
  "top_picks": [
    {{
      "rank": 1,
      "symbol": "ティッカー",
      "name": "銘柄名",
      "category": "セクター・属性",
      "conviction_score": 92,
      "sponsor_analysts": "推薦アナリスト（例: オニール ＆ キャシー・ウッド）",
      "catalyst": "今週この銘柄を最優先する核心的根拠（100文字程度）",
      "suggested_action": "BUY",
      "target_upside_pct": 18.5,
      "stop_loss_pct": -7.5
    }}
  ]
}}"""

                res = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )

                raw_text = res.text.strip() if res and res.text else "{}"
                if raw_text.startswith("```"):
                    import re
                    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

                ai_res = json.loads(raw_text)
                top_picks = ai_res.get("top_picks", [])
                
                # Enrich picks with live pricing and verified backtest from candidate map
                cand_map = {c["symbol"]: c for c in candidates}
                for p in top_picks:
                    sym = p.get("symbol")
                    if sym in cand_map:
                        p["current_price"] = cand_map[sym].get("current_price")
                        p["currency"] = cand_map[sym].get("currency")
                        p["pb_ratio"] = cand_map[sym].get("pb_ratio")
                        p["pe_trailing"] = cand_map[sym].get("pe_trailing")
                        p["dividend_yield"] = cand_map[sym].get("dividend_yield")
                        p["return_20d_pct"] = cand_map[sym].get("return_20d_pct")
                        p["backtest"] = cand_map[sym].get("backtest")

                return {
                    "generated_at": now_str,
                    "market_regime": regime_info.get("regime_name"),
                    "weekly_theme": ai_res.get("weekly_theme", "厳選クオリティ・アルファ探索"),
                    "cio_outlook": ai_res.get("cio_outlook", "現在の相場レジームに応じ、堅固な堀と業績モメンタムを両立する銘柄への厳選配分を継続します。"),
                    "top_picks": top_picks,
                    "total_universe_scanned": len(cls.get_universe_tickers())
                }
            except Exception as e:
                print(f"[AlphaResearcher] AI briefing error: {e}")

        # Deterministic Fallback Top 5
        fallback_picks = []
        for rank, c in enumerate(candidates[:5], 1):
            fallback_picks.append({
                "rank": rank,
                "symbol": c["symbol"],
                "name": c["name"],
                "category": c["category"],
                "current_price": c["current_price"],
                "currency": c["currency"],
                "pb_ratio": c.get("pb_ratio"),
                "pe_trailing": c.get("pe_trailing"),
                "dividend_yield": c.get("dividend_yield"),
                "return_20d_pct": c.get("return_20d_pct"),
                "conviction_score": c["quant_score"],
                "sponsor_analysts": "CIOクオンツ総合審査",
                "catalyst": f"PBR {c.get('pb_ratio')}倍、ROE {c.get('roe')}%とマルチファクター定量評価がユニバース上位。",
                "suggested_action": "BUY" if c["quant_score"] >= 75 else "ACCUMULATE",
                "target_upside_pct": 15.0,
                "stop_loss_pct": -8.0
            })

        return {
            "generated_at": now_str,
            "market_regime": regime_info.get("regime_name"),
            "weekly_theme": "クオンツ・マルチファクター厳選アルファ",
            "cio_outlook": "市場休場中のデータ精査に基づき、財務健全性とモメンタムのバランスが最も優れた上位5銘柄を選定しました。",
            "top_picks": fallback_picks,
            "total_universe_scanned": len(cls.get_universe_tickers())
        }
