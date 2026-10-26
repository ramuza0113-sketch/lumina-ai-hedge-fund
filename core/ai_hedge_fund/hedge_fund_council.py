import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.news_feed import NewsFeed
from core.ai_hedge_fund.broker_client import PaperTradingEngine
from core.ai_hedge_fund.macro_liquidity_feed import MacroLiquidityFeed
from core.ai_hedge_fund.sec_insider_feed import SecInsiderFeed
from core.ai_hedge_fund.options_gex_feed import OptionsGexFeed
from core.openbb_provider import OpenBBProvider
from core.state_manager import load_app_settings
from google import genai
from google.genai import types

from core.ai_hedge_fund.agents import (
    ALL_ANALYST_AGENTS,
    RiskManagerAgent,
    PortfolioManagerAgent
)


class HedgeFundCouncil:
    """
    Lumina AI Autonomous Hedge Fund: True Multi-Agent Debate Council
    Upgraded from monolithic prompt to Independent Parallel Multi-Agent Architecture
    (Inspired by virattt/ai-hedge-fund).

    Orchestrates the "Seven Legends (神セブン)" + Risk Manager (Red Team) + CIO Lumina:
    1. Warren Buffett AI (Moat, Free Cash Flow, Long-term compounding)
    2. Benjamin Graham AI (Deep Value, Margin of Safety, PBR/PER defense)
    3. Cathie Wood AI (Disruptive Innovation, AI/TAM exponential growth)
    4. Michael Burry AI (Big Short contrarian, bubble crash warning, insider selling)
    5. George Soros AI (Macro liquidity, Reflexivity theory, market psychology)
    6. William O'Neil AI (CANSLIM, breakout momentum, relative strength)
    7. cis / BNF AI (Japanese/US swing momentum, volume spike, supply-demand)
    + Risk Manager AI (CRO & Devil's Advocate, Fibonacci stop-loss, Gamma Flip turbulence)
    + Lead Portfolio Manager / CIO Lumina AI (Synthesizes independent verdicts & executes order)
    """

    AVAILABLE_AGENTS = ALL_ANALYST_AGENTS
    _council_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_cached_council(cls, symbol: str, max_age_hours: float = 24.0) -> Optional[Dict[str, Any]]:
        norm = MarketDataFeed.normalize_symbol(symbol)
        if norm in cls._council_cache:
            return cls._council_cache[norm]
        
        try:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ai_hedge_fund")
            cache_file = os.path.join(cache_dir, f"council_{norm.replace('.', '_')}.json")
            if os.path.exists(cache_file):
                mtime = os.path.getmtime(cache_file)
                if (time.time() - mtime) < max_age_hours * 3600:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cls._council_cache[norm] = data
                        return data
        except Exception:
            pass
        return None

    @classmethod
    def convene_council(cls, symbol: str, selected_agent_ids: Optional[List[str]] = None, force_refresh: bool = True, broker_engine: Any = None, **kwargs) -> Dict[str, Any]:
        """Convenience alias for run_council."""
        return cls.run_council(symbol=symbol, selected_agent_ids=selected_agent_ids, force_refresh=force_refresh)

    @classmethod
    def run_council(cls, symbol: str, selected_agent_ids: Optional[List[str]] = None, force_refresh: bool = False, max_cache_age_hours: float = 0.5) -> Dict[str, Any]:
        """
        Execute the full autonomous investment council debate via independent parallel agents.
        
        1. Fetches real-time market metrics from MarketDataFeed.
        2. Fetches breaking news headlines & scandal check via NewsFeed.
        3. Fetches past fund memory via PaperTradingEngine.
        4. Fetches Macro Liquidity, SEC Insider Trading, and Options GEX.
        5. Executes ALL analyst agents in parallel (blind independent reasoning).
        6. Evaluates risk via RiskManagerAgent (devil's advocate & stop loss).
        7. Synthesizes radar scores and final verdict via PortfolioManagerAgent (CIO Lumina).
        8. Permanently archives council debate record into SQLite memory.
        """
        norm = MarketDataFeed.normalize_symbol(symbol)
        if not force_refresh:
            cached = cls.get_cached_council(norm, max_age_hours=max_cache_age_hours)
            if cached:
                return cached

        stock_data = MarketDataFeed.get_stock_data(symbol)
        company_name = stock_data.get("company_name", symbol)
        
        # 1. Fetch & Audit Latest News (Anti-Fake News Quarantine Layer)
        news_items = NewsFeed.fetch_ticker_news(symbol, company_name=company_name, limit=5)
        news_audit = NewsFeed.audit_and_quarantine_news(news_items, symbol=symbol, company_name=company_name)
        if news_audit.get("is_quarantined"):
            stock_data["news_sentiment_summary"] = f"⚠️【情報監査警告: 煽り・風説の疑い】{news_audit.get('sanitized_briefing')}"
        elif news_audit.get("sanitized_briefing"):
            stock_data["news_sentiment_summary"] = news_audit.get("sanitized_briefing")

        # 2. Fetch Historical Fund Memory & Trade Journeys
        memory_engine = PaperTradingEngine()
        symbol_memory = memory_engine.get_symbol_memory(symbol)

        # 3. Fetch Macro Liquidity Status (FRED Net Liquidity Weather Radar)
        macro_status = MacroLiquidityFeed.get_macro_status()

        # 4. Fetch SEC Form 4 Insider Trading Intel
        insider_metrics = SecInsiderFeed.get_insider_metrics(symbol)

        # 5. Fetch Options Gamma Exposure (GEX) Intel & Market Turbulence
        gex_profile = OptionsGexFeed.get_gex_profile(symbol)
        market_turbulence = OptionsGexFeed.get_market_turbulence_warning()

        # 6. Fetch OpenBB Institutional Data Bundle (SEC, FRED, Estimates, Insider)
        openbb_bundle = OpenBBProvider.get_full_institutional_bundle(symbol)

        # 6. Fetch Graphiti Temporal Knowledge Graph Lessons
        graph_lessons = []
        try:
            from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            if GraphitiMemoryManager.is_available():
                graph_lessons = GraphitiMemoryManager.query_temporal_lessons(
                    symbol=symbol,
                    sector=stock_data.get("sector"),
                    macro_liquidity=macro_status.get("macro_weather")
                )
        except Exception as ge:
            print(f"[HedgeFundCouncil] Graphiti query warning: {ge}")

        # 7. Compute Verified Deterministic Mathematical Metrics (FinRobot Inspired) & Microsoft Qlib Alpha158
        det_metrics = {}
        try:
            from core.ai_hedge_fund.deterministic_metrics import DeterministicMetrics
            det_metrics = DeterministicMetrics.compute_for_symbol(symbol)
        except Exception as dme:
            print(f"[HedgeFundCouncil] DeterministicMetrics warning: {dme}")

        alpha158_summary = {}
        try:
            from core.ai_hedge_fund.alpha158_engine import Alpha158Engine
            alpha158_summary = Alpha158Engine.compute_symbol_summary(symbol)
        except Exception as a158e:
            print(f"[HedgeFundCouncil] Alpha158Engine warning: {a158e}")

        # 8. Load Master Investment Charter & Mandates (mem0 Architecture)
        master_prompt = ""
        try:
            from core.ai_hedge_fund.master_policy_memory import MasterPolicyMemory
            master_prompt = MasterPolicyMemory.format_for_council_prompt()
        except Exception as mpe:
            print(f"[HedgeFundCouncil] MasterPolicyMemory warning: {mpe}")

        # 9. Compute Google TimesFM × Amazon Chronos Dual Quantum Forecast & Consensus
        timesfm_forecast = {}
        chronos_forecast = {}
        dual_quantum = {}
        try:
            from core.ai_hedge_fund.dual_quantum_forecaster import DualQuantumForecaster
            dual_quantum = DualQuantumForecaster.forecast(symbol, horizon_days=5)
            timesfm_forecast = dual_quantum.get("models", {}).get("google_timesfm", {})
            chronos_forecast = dual_quantum.get("models", {}).get("amazon_chronos", {})
        except Exception as tfe:
            print(f"[HedgeFundCouncil] Dual Quantum forecasting warning: {tfe}")
            try:
                from core.ai_hedge_fund.timesfm_forecaster import TimesFMForecaster
                timesfm_forecast = TimesFMForecaster.forecast_stock(symbol, horizon_days=5)
            except Exception:
                pass

        # 9.5 Compute Lead-Lag (with Hayashi-Yoshida) & Factor Ontology Schema (Zero-Hallucination Metadata)
        lead_lag_info = {}
        try:
            from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
            lead_lag_info = LeadLagAnalyzer.analyze_lead_lag(symbol)
        except Exception as lle:
            print(f"[HedgeFundCouncil] LeadLagAnalyzer warning: {lle}")

        factor_ontology = {}
        try:
            from core.ai_hedge_fund.factor_ontology import FactorOntology
            factor_ontology = FactorOntology.build_ontology_bundle(
                stock_data=stock_data,
                alpha158_summary=alpha158_summary,
                lead_lag_info=lead_lag_info,
            )
        except Exception as foe:
            print(f"[HedgeFundCouncil] FactorOntology warning: {foe}")

        # Context bundle for agents
        context_data = {
            "macro_liquidity": macro_status,
            "insider_trading": insider_metrics,
            "options_gex": {
                "market_turbulence": market_turbulence.get("summary_text"),
                "ticker_gex": gex_profile.get("summary_text")
            },
            "openbb_bundle": openbb_bundle,
            "qlib_alpha158": alpha158_summary,
            "lead_lag_causality": lead_lag_info,
            "factor_ontology": factor_ontology,
            "timesfm_forecast": timesfm_forecast,
            "chronos_forecast": chronos_forecast,
            "dual_quantum": dual_quantum,
            "news_intelligence": news_audit,
            "recent_news": [news_audit.get("sanitized_briefing")] if news_audit.get("sanitized_briefing") else [n.get("title") for n in news_items[:3]],
            "broker_engine": memory_engine,
            "temporal_graph_lessons": graph_lessons,
            "deterministic_metrics": det_metrics,
            "master_mandates_prompt": master_prompt
        }

        # Initialize Langfuse trace if configured
        langfuse_trace = None
        try:
            from core.ai_hedge_fund.langfuse_tracer import LuminaLangfuseTracer
            if LuminaLangfuseTracer.is_configured():
                langfuse_trace = LuminaLangfuseTracer.start_council_trace(
                    symbol=symbol,
                    company_name=company_name,
                    metadata={
                        "price": stock_data.get("current_price"),
                        "currency": stock_data.get("currency"),
                        "macro": macro_status.get("macro_weather"),
                        "graph_lessons_count": len(graph_lessons)
                    }
                )
        except Exception:
            pass

        # Filter active agents if specified
        active_agents = cls.AVAILABLE_AGENTS
        if selected_agent_ids:
            active_agents = [a for a in cls.AVAILABLE_AGENTS if a.agent_id in selected_agent_ids]
            if not active_agents:
                active_agents = cls.AVAILABLE_AGENTS

        # 7. Execute Parallel Independent Reasoning (Blind Evaluation)
        analyst_results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(active_agents))) as executor:
            future_to_agent = {
                executor.submit(agent_cls.evaluate, stock_data, context_data): agent_cls
                for agent_cls in active_agents
            }
            for future in as_completed(future_to_agent):
                agent_cls = future_to_agent[future]
                try:
                    res = future.result()
                    analyst_results.append(res)
                    if langfuse_trace:
                        LuminaLangfuseTracer.record_agent_span(
                            trace=langfuse_trace,
                            agent_id=agent_cls.agent_id,
                            agent_name=agent_cls.name,
                            input_data={"symbol": symbol},
                            output_data=res
                        )
                except Exception as e:
                    print(f"[HedgeFundCouncil] Agent {agent_cls.name} evaluation error: {e}")
                    fallback_res = agent_cls._rule_based_fallback(stock_data, context_data)
                    analyst_results.append(fallback_res)
                    if langfuse_trace:
                        LuminaLangfuseTracer.record_agent_span(
                            trace=langfuse_trace,
                            agent_id=agent_cls.agent_id,
                            agent_name=agent_cls.name,
                            input_data={"symbol": symbol},
                            output_data=fallback_res
                        )

        # Sort analyst results to maintain consistent order
        id_order = [a.agent_id for a in active_agents]
        analyst_results.sort(key=lambda x: id_order.index(x.get("agent_id")) if x.get("agent_id") in id_order else 99)

        # 8. Phase 2: Fact-Grounded Cross-Debate (Bear Leader vs Bull Leader)
        cross_debate = cls._run_cross_debate(stock_data, analyst_results, context_data)

        # 9. Risk Manager Evaluation (Devil's Advocate, Veto Power & Position Limiter)
        risk_result = RiskManagerAgent.evaluate_risk(stock_data, analyst_results, context_data)

        if langfuse_trace:
            LuminaLangfuseTracer.record_agent_span(
                trace=langfuse_trace,
                agent_id="risk_manager",
                agent_name="Risk Manager AI",
                input_data={"analysts_count": len(analyst_results)},
                output_data=risk_result
            )

        # Append Risk Manager into council dialogues for UI display
        council_dialogues = list(analyst_results)
        council_dialogues.append(risk_result)

        # 10. Lead Portfolio Manager (CIO Lumina) Verdict Synthesis via Dynamic MoE Gating
        synthesis = PortfolioManagerAgent.synthesize_verdict(
            stock_data, analyst_results, risk_result, context_data, cross_debate=cross_debate
        )

        if langfuse_trace:
            LuminaLangfuseTracer.record_final_verdict(
                trace=langfuse_trace,
                verdict=synthesis["verdict"]
            )

        ai_res = {
            "radar_scores": synthesis["radar_scores"],
            "council_dialogues": council_dialogues,
            "verdict": synthesis["verdict"],
            "cross_debate": cross_debate,
            "regime_info": synthesis.get("regime_info", {}),
            "symbol": stock_data.get("symbol"),
            "company_name": company_name,
            "currency": stock_data.get("currency"),
            "current_price": stock_data.get("current_price"),
            "stock_data": stock_data,
            "news_items": news_items,
            "symbol_memory": symbol_memory,
            "macro_status": macro_status,
            "insider_metrics": insider_metrics,
            "gex_profile": gex_profile,
            "market_turbulence": market_turbulence,
            "openbb_bundle": openbb_bundle,
            "timesfm_forecast": timesfm_forecast,
            "chronos_forecast": chronos_forecast,
            "dual_quantum": dual_quantum,
            "graph_lessons": graph_lessons,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # 10. Permanently archive council debate record into SQLite memory
        try:
            record_id = memory_engine.record_council(ai_res, news_items=news_items)
            ai_res["council_record_id"] = record_id
        except Exception as arc_err:
            print(f"[HedgeFundCouncil] Memory archive error: {arc_err}")

        # 11. Record strategic council decision to Neo4j Graphiti Knowledge Graph (VETO or BUY >= 70)
        try:
            verdict_dict = synthesis.get("verdict", {})
            v_action = str(verdict_dict.get("action", "")).upper()
            v_label = str(verdict_dict.get("action_label", ""))
            v_conf = int(verdict_dict.get("confidence_score", 50))
            is_veto = ("拒否権" in v_label) or (v_action == "VETO")
            is_high_buy = (v_action in ["BUY", "ACCUMULATE"]) and (v_conf >= 70)

            if is_veto or is_high_buy:
                from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
                if GraphitiMemoryManager.is_available():
                    GraphitiMemoryManager.record_council_decision(
                        symbol=stock_data.get("symbol", symbol),
                        company_name=company_name,
                        action=v_action,
                        action_label=v_label,
                        confidence_score=v_conf,
                        thesis_summary=verdict_dict.get("thesis_summary", ""),
                        sector=stock_data.get("sector") or stock_data.get("industry") or "Unknown",
                        key_agent="risk_manager" if is_veto else "cio",
                        cross_debate=cross_debate
                    )
        except Exception as neo_err:
            print(f"[HedgeFundCouncil] Neo4j council decision archive error: {neo_err}")

        # 11.5 Record TimesFM Foundation Forecast to Neo4j and ForecastTracker
        try:
            if timesfm_forecast and timesfm_forecast.get("status") == "SUCCESS":
                from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
                dec_id = ai_res.get("council_record_id")
                fc_id = GraphitiMemoryManager.record_timesfm_forecast(
                    timesfm_forecast,
                    decision_id=f"cd_{dec_id}" if dec_id else None
                )
                ai_res["timesfm_forecast_id"] = fc_id
        except Exception as tf_rec_err:
            print(f"[HedgeFundCouncil] TimesFM forecast record warning: {tf_rec_err}")

        # 12. Cache to disk and memory for instant UI retrieval
        try:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ai_hedge_fund")
            os.makedirs(cache_dir, exist_ok=True)
            norm_sym = MarketDataFeed.normalize_symbol(symbol)
            cache_file = os.path.join(cache_dir, f"council_{norm_sym.replace('.', '_')}.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(ai_res, f, ensure_ascii=False, indent=2, default=str)
            cls._council_cache[norm_sym] = ai_res
        except Exception as c_err:
            print(f"[HedgeFundCouncil] Cache save error: {c_err}")

        return ai_res

    @classmethod
    def _run_cross_debate(
        cls,
        stock_data: Dict[str, Any],
        analyst_results: List[Dict[str, Any]],
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phase 2: 1-Round Fact-Grounded Cross-Debate between the most polarized analysts.
        - Identifies the Bear Leader (lowest score) and Bull Leader (highest score).
        - If spread >= 25, orchestrates a 1-turn accusation (Turn 1) and 1-turn defense/re-scoring (Turn 2).
        - Fully grounded on objective metrics (Price, PER, PBR, GEX, Macro).
        - Uses Gemini 3.7 Flash with temperature=0.2 to completely prevent hallucinations.
        """
        if not analyst_results:
            return {"occurred": False, "reason": "アナリスト審査結果が存在しません。"}

        # Filter to actual analysts (excluding risk manager if present)
        analysts = [a for a in analyst_results if a.get("agent_id") != "risk_manager"]
        if len(analysts) < 2:
            return {"occurred": False, "reason": "討論に必要なアナリスト数が不足しています。"}

        # Find Bear Leader and Bull Leader
        sorted_by_score = sorted(analysts, key=lambda x: x.get("score", 50))
        bear_agent = sorted_by_score[0]
        bull_agent = sorted_by_score[-1]

        bear_score = bear_agent.get("score", 50)
        bull_score = bull_agent.get("score", 50)
        spread = bull_score - bear_score

        # Spread threshold: at least 25 points difference
        if spread < 25:
            return {
                "occurred": False,
                "spread_initial": spread,
                "reason": f"合意度高（最大スコア差 {spread}点。閾値25点未満のため直接討論省略）"
            }

        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")
        if not api_key:
            return {"occurred": False, "reason": "APIキー未設定のため直接討論をスキップ"}

        try:
            client = genai.Client(api_key=api_key)
            name = stock_data.get("name") or stock_data.get("company_name", "対象銘柄")
            symbol = stock_data.get("symbol", "")
            price = stock_data.get("current_price", 100.0)
            currency = stock_data.get("currency", "USD")
            pe = stock_data.get("pe_trailing", "N/A")
            pb = stock_data.get("pb_ratio", "N/A")
            roe = stock_data.get("roe", "N/A")
            gex_summary = context_data.get("options_gex", {}).get("ticker_gex", "中立")
            macro_summary = context_data.get("macro_liquidity", {}).get("summary_headline", "中立")

            # Deterministic Mathematical Metrics (FinRobot Inspired)
            det = context_data.get("deterministic_metrics", {})
            vol_20d = det.get("volatility_20d_annualized_pct", "N/A")
            max_dd = det.get("max_drawdown_pct", "N/A")
            sharpe = det.get("sharpe_ratio_1y", "N/A")
            rsi = det.get("rsi_14", "N/A")
            dist_high = det.get("dist_from_52w_high_pct", "N/A")
            trend_ma = det.get("trend_ma20_ma50", "N/A")

            # [Turn 1] Bear Leader Accusation
            prompt_turn1 = f"""あなたはヘッジファンドの伝説的投資家AI【{bear_agent['name']} ({bear_agent.get('title', '')})】です。
投資対象: {name} ({symbol})
市場客観指標・確定数理データ:
- 現在株価: {price:,.2f} {currency}
- 実績PER: {pe}倍, PBR: {pb}倍, ROE: {roe}%
- 確定リスク指標 (Python計算): 20日年率ボラティリティ {vol_20d}%, 過去1年最大下落率 {max_dd}%, シャープレシオ {sharpe}
- テクニカル・トレンド: RSI(14) {rsi}, 52週高値乖離 {dist_high}%, トレンド判定 {trend_ma}
- GEXオプション環境: {gex_summary}
- マクロ流動性環境: {macro_summary}

あなたの評価: スコア {bear_score}点（{bear_agent.get('stance', 'BEARISH')}）
あなたの主張要約: {bear_agent.get('dialogue', '')[:100]}

対戦相手: 【{bull_agent['name']}】はスコア【{bull_score}点（{bull_agent.get('stance', 'BULLISH')}）】と極めて強気に評価しています。

【任務】
上記の客観市場データ・数理指標（株価、PER、PBR、ボラティリティ、最大下落率、RSI等の確定数値）を最低1つ具体的に引用・論拠として突きつけ、
{bull_agent['name']}の過度に楽観的な評価の死角・過大評価・暴落リスクを痛烈に糾弾してください。
※絶対に架空の数値を捏造せず、提供された数字のみを論拠にすること。
※文字数は120〜160文字程度の自然な日本語で発言してください。"""

            res1 = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_turn1,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            turn1_attack = res1.text.strip() if res1 and res1.text else f"株価{price} {currency}（PER {pe}倍、PBR {pb}倍、最大DD {max_dd}%）の評価は過大であり安全域を欠いている。"

            # [Turn 2] Bull Leader Defense & Re-scoring
            prompt_turn2 = f"""あなたはヘッジファンドの伝説的投資家AI【{bull_agent['name']} ({bull_agent.get('title', '')})】です。
投資対象: {name} ({symbol})
市場客観指標・確定数理データ:
- 現在株価: {price:,.2f} {currency}
- 実績PER: {pe}倍, PBR: {pb}倍, ROE: {roe}%
- 確定リスク指標: 20日年率ボラティリティ {vol_20d}%, 過去1年最大下落率 {max_dd}%, シャープレシオ {sharpe}, RSI(14) {rsi}

あなたの当初評価: スコア {bull_score}点
弱気派筆頭【{bear_agent['name']} ({bear_score}点)】からの直接糾弾:
「{turn1_attack}」

【任務】
上記の{bear_agent['name']}の糾弾から逃げず、自身の投資哲学に基づいて堂々と反論した上で、
相手の指摘の妥当性を一部受け止めてスコアを現実的に修正（3〜10点程度の下方修正）するか、または完全に論破して当初スコアを断固維持するか判断してください。

【出力形式】
必ず以下のJSON形式のみを出力してください（Markdownのコードブロックは不要、純粋なJSON文字列のみ）:
{{
  "defense": "{bear_agent['name']}に対する反論発言（120〜160文字）",
  "adjusted_score": 整数（0〜100。当初スコア{bull_score}から批判を受け止めて3〜10点下方修正するか、または{bull_score}のまま維持）,
  "adjustment_rationale": "スコア修正または維持の理由（1文・50文字以内）"
}}"""

            res2 = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_turn2,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            
            raw_text = res2.text.strip() if res2 and res2.text else "{}"
            if raw_text.startswith("```"):
                import re
                raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()
            
            t2_data = json.loads(raw_text)
            turn2_defense = t2_data.get("defense", "イノベーションの将来価値は現在の指標では測れないが、短期のボラティリティは注視する。")
            adjusted_score = int(t2_data.get("adjusted_score", bull_score))
            adjusted_score = max(0, min(100, adjusted_score))
            rationale = t2_data.get("adjustment_rationale", "相手の指摘を踏まえスコアを再検討。")

            # Update the bull agent's score and dialogue in analyst_results
            for a in analyst_results:
                if a.get("agent_id") == bull_agent.get("agent_id"):
                    a["score"] = adjusted_score
                    a["dialogue"] += f"\n\n⚔️【直接討論による再評価】{bear_agent['name']}の糾弾を受け、当初{bull_score}点から【{adjusted_score}点】に調整（{rationale}）"
                    break

            return {
                "occurred": True,
                "spread_initial": spread,
                "bear_agent_id": bear_agent.get("agent_id"),
                "bear_name": bear_agent.get("name"),
                "bear_avatar": bear_agent.get("avatar", "🐻"),
                "bear_initial_score": bear_score,
                "turn1_attack": turn1_attack,
                "bull_agent_id": bull_agent.get("agent_id"),
                "bull_name": bull_agent.get("name"),
                "bull_avatar": bull_agent.get("avatar", "🐂"),
                "bull_initial_score": bull_score,
                "turn2_defense": turn2_defense,
                "adjusted_score": adjusted_score,
                "score_delta": adjusted_score - bull_score,
                "adjustment_rationale": rationale
            }
        except Exception as e:
            print(f"[HedgeFundCouncil] Cross-Debate execution error: {e}")
            return {"occurred": False, "reason": f"ディベート実行時例外: {e}"}

