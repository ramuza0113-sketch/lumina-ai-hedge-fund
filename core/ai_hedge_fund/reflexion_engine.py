# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Reflexion & Deep Post-Mortem Self-Critique Engine
Powered by Gemini 3.7 Flash.
Enables independent worker agents (The Seven Legends + CRO) to learn from their
own investment outcomes without collapsing their role diversity (No Groupthink).
"""

import os
import sys
import json
import threading
from typing import Dict, Any, List, Optional
from core.state_manager import load_app_settings

MODEL_NAME = "gemini-3.8-flash"

class ReflexionEngine:
    """Post-Mortem Self-Reflection Engine for Multi-Agent Fund"""

    @classmethod
    def trigger_post_mortem_async(
        cls,
        symbol: str,
        company_name: str,
        exit_rule: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        broker_engine: Any
    ):
        """Spawns non-blocking background thread to perform LLM post-mortem self-reflection"""
        def _worker():
            try:
                cls.analyze_trade_outcome_and_record(
                    symbol=symbol,
                    company_name=company_name,
                    exit_rule=exit_rule,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    broker_engine=broker_engine
                )
            except Exception as e:
                print(f"[ReflexionEngine] Background post-mortem error: {e}")

        t = threading.Thread(target=_worker, daemon=True, name=f"ReflexionPostMortem_{symbol}")
        t.start()

    @classmethod
    def analyze_trade_outcome_and_record(
        cls,
        symbol: str,
        company_name: str,
        exit_rule: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        broker_engine: Any
    ) -> List[Dict[str, Any]]:
        """
        Deep LLM post-mortem:
        1. Retrieves the entry council debate record from SQLite.
        2. Identifies key agents whose convictions were most challenged or proven.
        3. Calls Gemini 3.7 Flash embodying each agent's philosophy to generate a targeted Reflexion.
        4. Permanently archives into agent_reflexions table.
        """
        from core.ai_hedge_fund.market_data_feed import MarketDataFeed
        norm = MarketDataFeed.normalize_symbol(symbol)
        
        # 1. Fetch past council records for this symbol
        councils = broker_engine.get_recent_councils(limit=1, symbol=norm)
        if not councils:
            return []

        last_council = councils[0]
        dialogues_raw = last_council.get("dialogues_json", "[]")
        try:
            dialogues = json.loads(dialogues_raw) if isinstance(dialogues_raw, str) else dialogues_raw
        except Exception:
            dialogues = []

        if not dialogues:
            return []

        # 2. Select 2 key agents to reflect:
        # If trade lost (PnL < 0): The highest-scoring Bullish agent (oversight) + one Caution/Bearish agent (correct warning)
        # If trade won (PnL > 0): The highest-scoring Bullish agent (thesis confirmed) + the most skeptical agent
        dialogues_sorted = sorted(dialogues, key=lambda d: d.get("score", 50), reverse=True)
        bullish_agents = [d for d in dialogues_sorted if d.get("agent_id") not in ("cio", "risk_manager") and d.get("stance") == "BULLISH"]
        bearish_agents = [d for d in dialogues_sorted if d.get("agent_id") not in ("cio", "risk_manager") and d.get("stance") in ("BEARISH", "CAUTION")]

        selected_dialogues = []
        if bullish_agents:
            selected_dialogues.append(bullish_agents[0])
        if bearish_agents:
            selected_dialogues.append(bearish_agents[-1])

        # If not enough, take top 2 analysts
        if len(selected_dialogues) < 2:
            analysts = [d for d in dialogues if d.get("agent_id") not in ("cio", "risk_manager")]
            selected_dialogues = analysts[:2]

        recorded = []
        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")

        for a_dialogue in selected_dialogues:
            agent_id = a_dialogue.get("agent_id", "")
            agent_name = a_dialogue.get("name", agent_id)
            stance = a_dialogue.get("stance", "NEUTRAL")
            score = a_dialogue.get("score", 50)
            orig_speech = a_dialogue.get("dialogue", "")

            # Determine category
            if realized_pnl_pct > 0:
                cat = "ACCURATE_THESIS" if stance == "BULLISH" else "FALSE_NEGATIVE_CAUTION"
            else:
                cat = "FALSE_POSITIVE_OVERCONFIDENCE" if stance == "BULLISH" else "ACCURATE_RISK_WARNING"

            reflection_text = ""
            if api_key:
                reflection_text = cls._generate_llm_reflexion(
                    api_key=api_key,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    symbol=norm,
                    company_name=company_name,
                    stance=stance,
                    score=score,
                    orig_speech=orig_speech,
                    exit_rule=exit_rule,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    category=cat
                )

            if not reflection_text:
                # Deterministic fallback
                if realized_pnl_pct >= 0:
                    reflection_text = f"【{agent_name}の事後反省】決済ルール「{exit_rule}」にて利益確定（{realized_pnl_pct:+.1f}%）。自身の分析観点と一次データの整合性が実証された。この判断プロセスを今後の類似局面での成功パターンとして記憶する。"
                else:
                    reflection_text = f"【{agent_name}の事後反省】損切りルール「{exit_rule}」が発動（{realized_pnl_pct:+.1f}%）。初期評価時のスコア（{score}点）に過信があった。次回は下値支持線と需給の歪みに対するチェック基準をさらに厳格化する。"

            # Save to SQLite
            broker_engine.record_agent_reflexion(
                symbol=norm,
                company_name=company_name,
                agent_id=agent_id,
                stance_at_entry=stance,
                score_at_entry=score,
                exit_rule=exit_rule,
                realized_pnl=realized_pnl,
                realized_pnl_pct=realized_pnl_pct,
                reflection_text=reflection_text,
                lesson_category=cat
            )
            recorded.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "reflection_text": reflection_text,
                "category": cat
            })
            print(f"[ReflexionEngine] 🧠 Saved reflection for {agent_name} on {norm}: {reflection_text[:60]}...")

        # Also persist to Neo4j Temporal Knowledge Graph via GraphitiMemoryManager
        try:
            from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            from core.ai_hedge_fund.macro_liquidity_feed import MacroLiquidityFeed
            stock_info = MarketDataFeed.get_stock_data(norm)
            macro_stat = MacroLiquidityFeed.get_macro_status().get("macro_weather", "NEUTRAL")
            sector_name = stock_info.get("sector", "Equities")

            GraphitiMemoryManager.record_trade_episode(
                symbol=norm,
                company_name=company_name,
                sector=sector_name,
                outcome="WIN" if realized_pnl >= 0 else "LOSS",
                realized_pnl=realized_pnl,
                realized_pnl_pct=realized_pnl_pct,
                exit_rule=exit_rule,
                macro_liquidity=macro_stat,
                reflections=recorded,
                council_dialogues=dialogues
            )
        except Exception as ge:
            print(f"[ReflexionEngine] Neo4j graph recording warning: {ge}")

        return recorded

    @classmethod
    def _generate_llm_reflexion(
        cls,
        api_key: str,
        agent_id: str,
        agent_name: str,
        symbol: str,
        company_name: str,
        stance: str,
        score: int,
        orig_speech: str,
        exit_rule: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        category: str
    ) -> str:
        """Call Gemini 3.7 Flash to generate role-invariant self-reflection"""
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            from core.ai_hedge_fund.agents import ALL_ANALYST_AGENTS
            agent_cls = next((a for a in ALL_ANALYST_AGENTS if a.agent_id == agent_id), None)
            philosophy = getattr(agent_cls, "philosophy", "客観的数値と投資規律の徹底") if agent_cls else "投資規律"

            prompt = f"""あなたは世界的投資家AI「{agent_name}」です。
あなたの投資哲学:
{philosophy}

【直近の投資結果の検証】
銘柄: {company_name} ({symbol})
あなたがエントリー時に下した判断: 【{stance} / 確信スコア {score}点】
あなたの当時の発言:
「{orig_speech}」

【決済結果】
決済ルール: {exit_rule}
実現損益: {realized_pnl:+,.0f} 円 ({realized_pnl_pct:+.1f}%)
検証カテゴリー: {category}

【依頼】
あなたの投資哲学を絶対に崩さず、自身のモノサシ（視点）に照らして「今回の結果に対する痛烈かつ客観的な自己省察（Reflexion）」を140〜200文字程度の日本語で出力してください。
※「ハイテクが上がったからハイテクを買おう」のようなキャラクターのブレ（同調）は厳禁です。「自身の分析基準の何が正しかったか、あるいは何を見落としていたか」を、次回同じ轍を踏まない（または成功を再現する）ための教訓として具体的に述べてください。"""

            res = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            if res and res.text:
                return res.text.strip().replace("\n", " ")
        except Exception as e:
            print(f"[ReflexionEngine] LLM reflexion call error: {e}")
        return ""

    @classmethod
    def get_agent_reflection_prompt(
        cls,
        agent_id: str,
        symbol: str,
        broker_engine: Any,
        query_keywords: Optional[List[str]] = None
    ) -> str:
        """
        Retrieves historical reflection memories for this agent using sub-millisecond
        SQLite FTS5 BM25 ranking (plus direct ticker match) and formats a prompt section
        to inject into the agent's evaluation prompt.
        """
        if not broker_engine:
            return ""

        from core.ai_hedge_fund.market_data_feed import MarketDataFeed
        norm = MarketDataFeed.normalize_symbol(symbol)

        # 1. Direct ticker reflections
        ticker_refs = broker_engine.get_agent_reflexions(agent_id=agent_id, symbol=norm, limit=2)

        # 2. Sub-millisecond FTS5 BM25 contextual search across all past reflections
        bm25_terms = [norm, "損切り", "利確", "ストップ", "需給", "過信"]
        if query_keywords:
            bm25_terms = list(query_keywords) + bm25_terms
        bm25_refs = []
        if hasattr(broker_engine, "search_agent_reflexions_bm25"):
            try:
                bm25_refs = broker_engine.search_agent_reflexions_bm25(
                    query_terms=bm25_terms,
                    agent_id=agent_id if agent_id not in ("risk_manager", "cio") else None,
                    limit=3
                )
            except Exception:
                bm25_refs = []

        # 3. Fallback general recent reflections
        general_refs = broker_engine.get_agent_reflexions(agent_id=agent_id, limit=2)

        all_refs = []
        seen_ids = set()
        for r in (ticker_refs + bm25_refs + general_refs):
            rid = r.get("reflexion_id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_refs.append(r)

        if not all_refs:
            return ""

        lines = [
            "\n【🧠 SQLite FTS5 (BM25 × 指数時間減衰 Half-Life 30d) 高速記憶検索による自己省察メモ】",
            "過去の類似局面・銘柄におけるあなたの投資判断と事後検証の結果（BM25×時間減衰ウェイト上位）です。同じ失敗パターンを絶対に繰り返さず、教訓を活かして厳格に評価してください:"
        ]
        for r in all_refs[:3]:
            sym = r.get("symbol", "")
            pnl_pct = r.get("realized_pnl_pct", 0.0)
            txt = r.get("reflection_text", "")
            cat = r.get("lesson_category", "")
            decay_w = r.get("decay_weight", 1.0)
            age_d = r.get("age_days", 0.0)
            aging_tag = f" | 減衰Weight: {decay_w:.2f} ({age_d:.0f}日前)" if "decay_weight" in r else ""
            lines.append(f"- 【過去トレード記憶: {sym} (損益: {pnl_pct:+.1f}% | 分類: {cat}{aging_tag})】{txt}")

        # Check Graphiti Temporal Knowledge Graph for Sector and Macro lessons
        try:
            from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            if GraphitiMemoryManager.is_available():
                graph_lessons = GraphitiMemoryManager.query_temporal_lessons(symbol=norm, limit=2)
                for gl in graph_lessons:
                    m_type = gl.get("match_type", "GRAPH")
                    g_sym = gl.get("symbol", "")
                    g_outcome = gl.get("outcome", "")
                    g_pnl = gl.get("pnl_pct", 0.0)
                    g_txt = gl.get("lesson_text", "")
                    g_ag = gl.get("agent_name", "")
                    lines.append(f"- 【🕸️ 時間軸ナレッジグラフ教訓 ({m_type}: {g_sym} {g_outcome} {g_pnl:+.1f}% / 観察: {g_ag})】{g_txt}")
        except Exception:
            pass

        lines.append("※上記の教訓を踏まえつつ、古い記憶（低Weight）や異なる相場レジームの損切りトラウマに過剰適合（Over-fitting）して現在の特A級シグナルを不当に萎縮・棄却しないよう客観的に検証してください。\n")
        return "\n".join(lines)

