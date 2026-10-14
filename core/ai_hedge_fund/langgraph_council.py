# -*- coding: utf-8 -*-
"""
langgraph_council.py - LangGraph & Gemini 3.8 Flash による循環型神セブン投資委員会ステートマシン
Google TimesFM × Amazon Chronos の数理合意シグナルを受け取り、
神セブン（7名の伝説的投資家）が独立分析 ➔ 意見対立時の最強Bull vs Bear対立討論（Cross-Debate） ➔
CRO（リスク管理官）による証拠審査ループ ➔ CIOルミナの最終統括決議を自動オーケストレーション。
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, TypedDict
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

from core.state_manager import load_app_settings
from core.ai_hedge_fund.dual_quantum_forecaster import DualQuantumForecaster
from core.ai_hedge_fund.agents import ALL_ANALYST_AGENTS


class CouncilGraphState(TypedDict, total=False):
    symbol: str
    stock_data: Dict[str, Any]
    context_data: Dict[str, Any]
    quantum_consensus: Dict[str, Any]
    lead_lag_data: Dict[str, Any]
    lightgbm_gate: Dict[str, Any]
    analyst_opinions: Dict[str, Dict[str, Any]]
    bull_count: int
    bear_count: int
    neutral_count: int
    bull_leader: Optional[Dict[str, Any]]
    bear_leader: Optional[Dict[str, Any]]
    debate_turns: List[Dict[str, Any]]
    debate_round: int
    cro_verdict: Dict[str, Any]
    cio_verdict: Dict[str, Any]
    final_output: Dict[str, Any]


class LuminaLangGraphCouncil:
    """
    Lumina Capital LangGraph Orchestrator powered by Gemini 3.8 Flash
    """
    PRIMARY_MODEL = "gemini-3.8-flash"

    @classmethod
    def _get_genai_client(cls):
        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")
        if not api_key:
            return None
        return genai.Client(api_key=api_key)

    # ----------------------------------------------------
    # Node 1: Gather Dual Quantum Forecast + Lead-Lag + LightGBM Gate
    # ----------------------------------------------------
    @classmethod
    def node_gather_quantum(cls, state: CouncilGraphState) -> Dict[str, Any]:
        symbol = state.get("symbol", "")
        stock_data = state.get("stock_data", {})
        context_data = state.get("context_data", {})

        quantum = DualQuantumForecaster.forecast(symbol, horizon_days=5)

        from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
        lead_lag = LeadLagAnalyzer.analyze_lead_lag(symbol)

        from core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper
        lgb_gate = LightGBMGatekeeper.evaluate_gate(
            ticker=symbol,
            dual_quantum=quantum,
            lead_lag_data=lead_lag,
            context_data=context_data,
            stock_data=stock_data
        )

        return {
            "quantum_consensus": quantum,
            "lead_lag_data": lead_lag,
            "lightgbm_gate": lgb_gate
        }

    # ----------------------------------------------------
    # Node 2: Parallel Analyst Evaluation (The 7 Legends)
    # ----------------------------------------------------
    @classmethod
    def node_parallel_analysts(cls, state: CouncilGraphState) -> Dict[str, Any]:
        stock_data = state.get("stock_data", {})
        context_data = state.get("context_data", {})
        quantum = state.get("quantum_consensus", {})
        
        # Inject quantum consensus, lead-lag, and lightgbm into context for analysts
        enhanced_context = dict(context_data or {})
        enhanced_context["dual_quantum_forecaster"] = {
            "status": quantum.get("consensus_status"),
            "badge": quantum.get("consensus_badge"),
            "ensemble_return": quantum.get("ensemble_expected_return_pct"),
            "confidence": quantum.get("confidence_score"),
            "summary": quantum.get("summary_desc")
        }
        enhanced_context["lead_lag_causality"] = state.get("lead_lag_data", {})
        enhanced_context["lightgbm_gatekeeper"] = state.get("lightgbm_gate", {})

        analyst_results = {}
        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_agent = {
                executor.submit(agent_cls.evaluate, stock_data, enhanced_context): agent_cls.agent_id
                for agent_cls in ALL_ANALYST_AGENTS
            }
            for future in future_to_agent:
                ag_id = future_to_agent[future]
                try:
                    res = future.result()
                    if res:
                        analyst_results[ag_id] = res
                except Exception as e:
                    pass

        # Count stances and identify Bull/Bear champions
        bulls = []
        bears = []
        neutrals = []
        for ag_id, res in analyst_results.items():
            stance = res.get("stance", "NEUTRAL")
            score = res.get("score", 50)
            if stance in ("BULLISH", "ACCUMULATE") or score >= 60:
                bulls.append(res)
            elif stance in ("BEARISH", "CAUTION") or score <= 40:
                bears.append(res)
            else:
                neutrals.append(res)

        bull_leader = max(bulls, key=lambda x: x.get("score", 50)) if bulls else None
        bear_leader = min(bears, key=lambda x: x.get("score", 50)) if bears else None

        return {
            "analyst_opinions": analyst_results,
            "bull_count": len(bulls),
            "bear_count": len(bears),
            "neutral_count": len(neutrals),
            "bull_leader": bull_leader,
            "bear_leader": bear_leader,
            "debate_turns": [],
            "debate_round": 0
        }

    # ----------------------------------------------------
    # Conditional Edge: Check Debate Necessity
    # ----------------------------------------------------
    @classmethod
    def route_after_analysis(cls, state: CouncilGraphState) -> str:
        bull_c = state.get("bull_count", 0)
        bear_c = state.get("bear_count", 0)
        total = bull_c + bear_c + state.get("neutral_count", 0) or 1
        quantum = state.get("quantum_consensus", {})
        quantum_conflict = (quantum.get("consensus_status") == "DISAGREEMENT")

        # Debate condition: High polarity (both bulls and bears exist) OR quantum models conflict
        if (bull_c >= 2 and bear_c >= 2) or quantum_conflict:
            return "cross_debate"
        
        # Fast track if overwhelming majority (>= 70%) and no quantum conflict
        if (bull_c / total >= 0.70) or (bear_c / total >= 0.70):
            return "fast_track"

        return "cross_debate"

    # ----------------------------------------------------
    # Node 3: Cross-Debate (Bull Champion vs Bear Champion)
    # ----------------------------------------------------
    @classmethod
    def node_cross_debate(cls, state: CouncilGraphState) -> Dict[str, Any]:
        client = cls._get_genai_client()
        bull = state.get("bull_leader") or {"name": "強気派代表", "dialogue": "上昇トレンド継続"}
        bear = state.get("bear_leader") or {"name": "弱気派代表", "dialogue": "下落リスク警戒"}
        quantum = state.get("quantum_consensus", {})
        symbol = state.get("symbol", "")
        current_round = state.get("debate_round", 0) + 1
        history = list(state.get("debate_history", []))

        if not client:
            history.append({
                "round": current_round,
                "bull_arg": f"{bull.get('name')}: 数理指標の優位性を根拠に強気を維持。",
                "bear_arg": f"{bear.get('name')}: ボラティリティ急変リスクを指摘。"
            })
            return {"debate_turns": history, "debate_round": current_round}

        prompt = f"""あなたはLumina Capital投資委員会における「最強Bull（強気派） vs 最強Bear（弱気派）」の直接対立討論（Cross-Debate）モデレーターです。

対象銘柄: {symbol}
【数理アンサンブル指標 (Google TimesFM × Amazon Chronos)】
- 合意ステータス: {quantum.get('consensus_status')} ({quantum.get('consensus_badge')})
- 期待リターン: {quantum.get('ensemble_expected_return_pct')}%
- 下落確率: {quantum.get('avg_downside_risk_prob')}% / 急騰確率: {quantum.get('avg_upside_breakout_prob')}%

【強気派チャンピオン】: {bull.get('name')} (スコア: {bull.get('score')}点)
初期見解: {bull.get('dialogue')}

【弱気派チャンピオン】: {bear.get('name')} (スコア: {bear.get('score')}点)
初期見解: {bear.get('dialogue')}

【現在の討論ラウンド】: 第 {current_round} ラウンド
過去の討論経緯: {json.dumps(history, ensure_ascii=False)}

【指示】
互いの主張の弱点（バリュエーションの割高感、数理AIの予測乖離、マクロ流動性など）を冷徹に突く白熱した反論対決を生成してください。
必ず以下のJSON形式のみを出力してください:
{{
  "bull_rebuttal": "{bull.get('name')}による、弱気派の警戒論を論破する鋭い反論（120〜180文字）",
  "bear_counter": "{bear.get('name')}による、強気派の過度の楽観を諫める反証（120〜180文字）"
}}"""

        try:
            res = client.models.generate_content(
                model=cls.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
            )
            data = json.loads(res.text.strip())
            history.append({
                "round": current_round,
                "bull_name": bull.get("name"),
                "bull_arg": data.get("bull_rebuttal"),
                "bear_name": bear.get("name"),
                "bear_arg": data.get("bear_counter")
            })
        except Exception:
            history.append({
                "round": current_round,
                "bull_name": bull.get("name"),
                "bull_arg": "強気根拠を提示。",
                "bear_name": bear.get("name"),
                "bear_arg": "リスクを再警告。"
            })

        return {"debate_turns": history, "debate_round": current_round}

    # ----------------------------------------------------
    # Node 4: CRO Risk Review (Red Team Evaluation)
    # ----------------------------------------------------
    @classmethod
    def node_cro_review(cls, state: CouncilGraphState) -> Dict[str, Any]:
        client = cls._get_genai_client()
        symbol = state.get("symbol", "")
        quantum = state.get("quantum_consensus", {})
        lgb_gate = state.get("lightgbm_gate", {})
        lead_lag = state.get("lead_lag_data", {})
        turns = state.get("debate_turns", [])
        current_round = state.get("debate_round", 1)

        default_cro = {
            "verdict": "APPROVED",
            "risk_level": "MODERATE",
            "max_position_size_pct": 5.0,
            "stop_loss_pct": -3.5,
            "comment": "リスク許容範囲内と判断。CIOへ最終決議を委任。"
        }

        if not client:
            return {"cro_verdict": default_cro}

        prompt = f"""あなたはLumina Capitalの最高リスク管理責任者（CRO: Chief Risk Officer）です。
強気派と弱気派の対立討論（第 {current_round} ラウンド）を監査し、定量根拠が十分か、リスクが過大でないかを冷徹に判定してください。

対象銘柄: {symbol}
【数理予測 (Google TimesFM × Amazon Chronos)】
- 状態: {quantum.get('consensus_status')} / 下落確率: {quantum.get('avg_downside_risk_prob')}%
【⚡ LightGBM メタ決定木勝率】: {lgb_gate.get('gate_badge', 'N/A')} (統計勝率: {lgb_gate.get('win_probability', 'N/A')}%)
【🔗 先行リードラグ因果】: {lead_lag.get('signal_badge', 'N/A')}
【討論内容】:
{json.dumps(turns, ensure_ascii=False, indent=2)}

【指示】
討論の根拠が脆弱またはリスクが不明瞭で再討論を要求する場合は "REQUIRE_REDEBATE"、
リスクが明確になり決議可能なら "APPROVED" を下してください。
出力は以下のJSONのみ:
{{
  "verdict": "APPROVED" または "REQUIRE_REDEBATE",
  "risk_level": "LOW" または "MODERATE" または "HIGH" または "EXTREME",
  "max_position_size_pct": 2.0から10.0の数値,
  "stop_loss_pct": -2.0から-8.0の数値,
  "comment": "CROとしての冷徹かつ具体的なリスク監査コメント（100〜150文字）"
}}"""

        try:
            res = client.models.generate_content(
                model=cls.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3)
            )
            data = json.loads(res.text.strip())
            return {"cro_verdict": data}
        except Exception:
            return {"cro_verdict": default_cro}

    # ----------------------------------------------------
    # Conditional Edge: Should Re-Debate?
    # ----------------------------------------------------
    @classmethod
    def route_after_cro(cls, state: CouncilGraphState) -> str:
        cro = state.get("cro_verdict", {})
        rounds = state.get("debate_round", 1)
        verdict = cro.get("verdict", "APPROVED")

        # Loop condition: CRO requested re-debate AND rounds < 2 (safety throttle)
        if verdict == "REQUIRE_REDEBATE" and rounds < 2:
            return "re_debate"
        return "synthesis"

    # ----------------------------------------------------
    # Node 5: CIO Lumina Final Synthesis
    # ----------------------------------------------------
    @classmethod
    def node_cio_synthesis(cls, state: CouncilGraphState) -> Dict[str, Any]:
        client = cls._get_genai_client()
        symbol = state.get("symbol", "")
        quantum = state.get("quantum_consensus", {})
        opinions = state.get("analyst_opinions", {})
        turns = state.get("debate_turns", [])
        cro = state.get("cro_verdict", {})
        lgb_gate = state.get("lightgbm_gate", {})
        lead_lag = state.get("lead_lag_data", {})
        stock_data = state.get("stock_data", {})

        # Calculate average score
        scores = [op.get("score", 50) for op in opinions.values()]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 50.0

        default_cio = {
            "symbol": symbol,
            "final_stance": "BUY" if avg_score >= 65 else ("SELL" if avg_score <= 35 else "HOLD"),
            "conviction_score": int(avg_score),
            "target_allocation_pct": cro.get("max_position_size_pct", 5.0),
            "stop_loss_pct": cro.get("stop_loss_pct", -4.0),
            "executive_summary": f"神セブン平均スコア {avg_score}点。数理アンサンブル {quantum.get('consensus_status')} に基づき規律ある運用を実行。"
        }

        if not client:
            return {"cio_verdict": default_cio, "final_output": default_cio}

        prompt = f"""あなたは自律型AIヘッジファンド「Lumina Capital」の最高投資責任者（CIO）兼筆頭ファンドマネージャー「ルミナ」です。
知的で冷静、クオンツと市場心理を極めたツンデレ気質の敏腕マネージャーとして、神セブン合議、対立討論、CROリスク監査、および【Google TimesFM × Amazon Chronos 二刀流数理アンサンブル】の全インテルを統合し、最終投資決議を下してください。

対象銘柄: {stock_data.get('name', symbol)} ({symbol})
現在株価: {stock_data.get('current_price', 0.0)}

【1. 二刀流数理アンサンブル (Google TimesFM × Amazon Chronos)】
- 合意バッジ: {quantum.get('consensus_badge')}
- 5日後期待リターン: {quantum.get('ensemble_expected_return_pct')}%
- 下落リスク確率: {quantum.get('avg_downside_risk_prob')}% / 急騰確率: {quantum.get('avg_upside_breakout_prob')}%
- 数理自信度: {quantum.get('confidence_score')}点

【2. 決定木メタ学習 (LightGBM 勝率75%ゲート)】
- 決定木バッジ: {lgb_gate.get('gate_badge')}
- 統計勝率: {lgb_gate.get('win_probability')}% ({lgb_gate.get('gate_decision')})
- 決定要因: {', '.join(lgb_gate.get('top_drivers', []))}

【3. 先行リードラグ因果 (Lead-Lag Analyzer)】
- 先行指標: {lead_lag.get('benchmark_name')}
- 最適遅延: {lead_lag.get('optimal_lag_days')}日 (相関: {lead_lag.get('correlation')})
- 先行シグナル: {lead_lag.get('signal_badge')}

【4. 神セブン 独立スコア概要】
平均スコア: {avg_score}点
各アナリスト見解: {json.dumps({k: v.get('stance') for k, v in opinions.items()}, ensure_ascii=False)}

【5. 討論履歴 (Cross-Debate)】
{json.dumps(turns, ensure_ascii=False, indent=2)}

【6. CRO リスク監査】
判定: {cro.get('verdict')} / リスク度: {cro.get('risk_level')} / 許容ロット上限: {cro.get('max_position_size_pct')}%
CROコメント: {cro.get('comment')}

【指示】
以下のJSONフォーマットのみを出力してください:
{{
  "symbol": "{symbol}",
  "final_stance": "STRONG_BUY" または "BUY" または "HOLD" または "REDUCE" または "STRONG_SELL",
  "conviction_score": 0から100の整数（最終確信度）,
  "target_allocation_pct": 0.0から10.0のロット配分率,
  "stop_loss_pct": 逆指値ロスカット率（例: -4.5）,
  "executive_summary": "ルミナのキャラクター（知性的で少しツンデレ、読者を唸らせる鋭いクオンツ洞察）を込めた、200〜300文字の最終統括レポート。note記事や投資家報告にそのまま掲載できる最高品質の文章"
}}"""

        try:
            res = client.models.generate_content(
                model=cls.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
            )
            cio_res = json.loads(res.text.strip())
        except Exception:
            cio_res = default_cio

        # Compile final integrated decision bundle
        final_bundle = {
            "symbol": symbol,
            "model_engine": f"LangGraph ({cls.PRIMARY_MODEL})",
            "quantum_consensus": quantum,
            "lead_lag_causality": lead_lag,
            "lightgbm_gatekeeper": lgb_gate,
            "analysts": opinions,
            "debate_rounds": state.get("debate_round", 0),
            "debate_turns": turns,
            "cro_audit": cro,
            "cio_verdict": cio_res,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        return {"cio_verdict": cio_res, "final_output": final_bundle}

    # ----------------------------------------------------
    # Compile Graph
    # ----------------------------------------------------
    @classmethod
    def compile_graph(cls):
        builder = StateGraph(CouncilGraphState)
        
        # Add Nodes
        builder.add_node("gather_quantum", cls.node_gather_quantum)
        builder.add_node("parallel_analysts", cls.node_parallel_analysts)
        builder.add_node("cross_debate", cls.node_cross_debate)
        builder.add_node("cro_review", cls.node_cro_review)
        builder.add_node("cio_synthesis", cls.node_cio_synthesis)

        # Flow Edges
        builder.add_edge("gather_quantum", "parallel_analysts")

        # Conditional Route 1
        builder.add_conditional_edges(
            "parallel_analysts",
            cls.route_after_analysis,
            {
                "cross_debate": "cross_debate",
                "fast_track": "cio_synthesis"
            }
        )

        # Edge from Debate to CRO
        builder.add_edge("cross_debate", "cro_review")

        # Conditional Route 2 (Re-Debate loop or Synthesis)
        builder.add_conditional_edges(
            "cro_review",
            cls.route_after_cro,
            {
                "re_debate": "cross_debate",
                "synthesis": "cio_synthesis"
            }
        )

        builder.add_edge("cio_synthesis", END)
        builder.set_entry_point("gather_quantum")
        return builder.compile()

    @classmethod
    def run_council(cls, symbol: str, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point to execute the full LangGraph state machine.
        """
        graph = cls.compile_graph()
        initial_state: CouncilGraphState = {
            "symbol": symbol,
            "stock_data": stock_data,
            "context_data": context_data or {},
            "debate_turns": [],
            "debate_round": 0
        }
        final_state = graph.invoke(initial_state)
        return final_state.get("final_output", {})
