import json
from typing import Dict, Any, List, Optional
from core.state_manager import load_app_settings

class PortfolioManagerAgent:
    """
    Lead Portfolio Manager & CIO: Lumina AI
    Acts as an impartial judge, synthesizing independent analyst verdicts
    and enforcing risk manager constraints to generate the final execution verdict.
    """

    agent_id = "cio"
    name = "CIO Lumina"
    title = "最高投資責任者・最高審判官"
    avatar = "👑"

    @classmethod
    def detect_market_regime(cls, context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Dynamic MoE Gating Network:
        Classifies market regime based on FRED Net Liquidity & Options GEX,
        and computes dynamic weights across all 7 legends + CRO.
        """
        macro = (context_data or {}).get("macro_liquidity", {})
        gex = (context_data or {}).get("options_gex", {})
        mkt_turb = str(gex.get("market_turbulence", ""))
        ticker_gex = str(gex.get("ticker_gex", ""))
        summary_hl = str(macro.get("summary_headline", ""))
        status = str(macro.get("status", "NORMAL"))
        trend = str(macro.get("net_liquidity_trend", "FLAT"))

        is_turbulent = (
            "警戒" in mkt_turb or "乱流" in mkt_turb or "ネガティブガンマ" in mkt_turb or
            "急変" in mkt_turb or "CRITICAL" in status.upper() or 
            ("SHRINKING" in trend.upper() and "ALERT" in mkt_turb.upper())
        )
        is_bull_liquidity = (
            ("EXPANDING" in trend.upper() or "増加" in trend or "良好" in summary_hl or "金余り" in summary_hl or "NORMAL" in status.upper())
            and not is_turbulent
        )
        is_tightening = (
            ("引き締め" in summary_hl or "収縮" in summary_hl or "縮小" in trend or "CONTRACTION" in trend.upper() or "SHRINKING" in trend.upper())
            and not is_turbulent
        )

        if is_turbulent:
            regime_name = "⚠️ ボラティリティ急変・ガンマ乱流相場"
            rationale = "GEXガンマフリップ乱流または市場ボラティリティ急増を検知。リスク管理者および防衛的バリュー投資家の比重を最大化。"
            weights = {
                "buffett": 0.12,
                "graham": 0.18,
                "cathie_wood": 0.03,
                "michael_burry": 0.22,
                "george_soros": 0.05,
                "william_oneil": 0.05,
                "cis_trader": 0.03,
                "cro": 0.32
            }
        elif is_bull_liquidity:
            regime_name = "🚀 強気・流動性膨張相場"
            rationale = "FRB純流動性の拡大および安定した正のガンマ環境。モメンタムと破壊的グロースの比重を引き上げ、積極的なアルファ獲得を志向。"
            weights = {
                "buffett": 0.10,
                "graham": 0.06,
                "cathie_wood": 0.22,
                "michael_burry": 0.04,
                "george_soros": 0.14,
                "william_oneil": 0.22,
                "cis_trader": 0.14,
                "cro": 0.08
            }
        elif is_tightening:
            regime_name = "🛡️ 景気後退・流動性収縮相場"
            rationale = "金融引き締め・流動性収縮環境。高い価格支配力と強固な堀、現金を創出するクオリティ・バリュー投資家を最重要視。"
            weights = {
                "buffett": 0.26,
                "graham": 0.24,
                "cathie_wood": 0.03,
                "michael_burry": 0.12,
                "george_soros": 0.10,
                "william_oneil": 0.05,
                "cis_trader": 0.04,
                "cro": 0.16
            }
        else:
            regime_name = "⚖️ 平常・中立レンジ相場"
            rationale = "特筆すべき極端な歪みのない中立環境。全7大哲学とリスク管理をバランスよく配分。"
            weights = {
                "buffett": 0.15,
                "graham": 0.14,
                "cathie_wood": 0.14,
                "michael_burry": 0.07,
                "george_soros": 0.13,
                "william_oneil": 0.14,
                "cis_trader": 0.11,
                "cro": 0.12
            }

        return {
            "regime_name": regime_name,
            "rationale": rationale,
            "weights": weights
        }

    @classmethod
    def synthesize_verdict(
        cls,
        stock_data: Dict[str, Any],
        analyst_results: List[Dict[str, Any]],
        risk_result: Dict[str, Any],
        context_data: Optional[Dict[str, Any]] = None,
        cross_debate: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize radar scores and final verdict using Dynamic MoE Gating & Cross-Debate outcomes.
        """
        price = float(stock_data.get("current_price") or 1000.0)
        currency = stock_data.get("currency", "JPY")
        stop_loss = risk_result.get("stop_loss_price", round(price * 0.87, 2))
        max_alloc = risk_result.get("max_allocation_pct", 10.0)

        # 1. Calculate Radar Scores based on specific agents
        scores_by_id = {a.get("agent_id"): a.get("score", 50) for a in analyst_results}
        moat_score = scores_by_id.get("buffett", 70)
        value_score = int((scores_by_id.get("graham", 60) + scores_by_id.get("michael_burry", 60)) / 2)
        growth_score = int((scores_by_id.get("cathie_wood", 70) + scores_by_id.get("william_oneil", 70)) / 2)
        safety_score = risk_result.get("score", 70)
        timing_score = int((scores_by_id.get("cis_trader", 65) + scores_by_id.get("george_soros", 65)) / 2)

        radar_scores = {
            "moat": moat_score,
            "value": value_score,
            "growth": growth_score,
            "safety": safety_score,
            "timing": timing_score
        }

        # 2. Dynamic MoE Gating Network Weighting
        regime_info = cls.detect_market_regime(context_data)
        weights = regime_info["weights"]

        weighted_sum = 0.0
        weight_total = 0.0
        for a in analyst_results:
            aid = a.get("agent_id")
            w = weights.get(aid, 0.10)
            weighted_sum += a.get("score", 50) * w
            weight_total += w

        cro_w = weights.get("cro", 0.12)
        weighted_sum += risk_result.get("score", 50) * cro_w
        weight_total += cro_w

        overall_score = int(round(weighted_sum / weight_total)) if weight_total > 0 else 50

        # 3. Determine action & target price (Enforcing CRO Absolute Veto Power)
        veto_triggered = risk_result.get("veto_triggered", False)
        veto_reason = risk_result.get("veto_reason", "リスク管理者による危機警戒")

        if veto_triggered:
            action = "HOLD"
            action_label = f"🚨 CRO拒否権発動（新規建て完全凍結）"
            target_price = round(price * 1.0, 2)
            alloc = 0.0
            overall_score = min(overall_score, 30)
        elif overall_score >= 75:
            action = "BUY"
            action_label = "積極買い推奨"
            target_price = round(price * 1.25, 2)
            alloc = max_alloc
        elif overall_score >= 60:
            action = "ACCUMULATE"
            action_label = "打診買い（分散積立）"
            target_price = round(price * 1.15, 2)
            alloc = min(max_alloc, 7.0)
        elif overall_score >= 45:
            action = "HOLD"
            action_label = "様子見・保有継続"
            target_price = round(price * 1.05, 2)
            alloc = 0.0
        else:
            action = "SELL"
            action_label = "利益確定 / 撤退売り"
            target_price = round(price * 0.95, 2)
            alloc = 0.0

        # 4. Generate thesis summary via Gemini 3.7 Flash or fallback
        thesis_summary = cls._generate_thesis_summary(
            stock_data, analyst_results, risk_result, action_label, overall_score, regime_info, cross_debate
        )

        return {
            "radar_scores": radar_scores,
            "regime_info": regime_info,
            "verdict": {
                "action": action,
                "action_label": action_label,
                "target_price": target_price,
                "stop_loss_price": stop_loss,
                "allocation_pct": alloc,
                "confidence_score": overall_score,
                "horizon": "中期（6〜12ヶ月）" if action in ("BUY", "ACCUMULATE") else "短期（見送り）",
                "thesis_summary": thesis_summary,
                "market_regime": regime_info.get("regime_name")
            }
        }

    @classmethod
    def _generate_thesis_summary(
        cls,
        stock_data: Dict[str, Any],
        analyst_results: List[Dict[str, Any]],
        risk_result: Dict[str, Any],
        action_label: str,
        overall_score: int,
        regime_info: Optional[Dict[str, Any]] = None,
        cross_debate: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate high-conviction editorial synthesis"""
        try:
            cfg = load_app_settings()
            api_key = cfg.get("google_api_key", "")
            if api_key:
                from google import genai
                
                name = stock_data.get("name", "対象銘柄")
                opinions = "\n".join([f"- {a['name']} ({a['stance']}, スコア{a['score']}): {a['dialogue']}" for a in analyst_results])
                opinions += f"\n- {risk_result['name']} (安全スコア{risk_result['score']}): {risk_result['dialogue']}"
                
                debate_section = ""
                if cross_debate and cross_debate.get("occurred"):
                    b_name = cross_debate.get("bear_name")
                    u_name = cross_debate.get("bull_name")
                    b_atk = cross_debate.get("turn1_attack")
                    u_adj = cross_debate.get("adjusted_score")
                    b_orig = cross_debate.get("bull_initial_score")
                    debate_section = f"\n\n【クロスディベート直接対決】\n- {b_name}の糾弾: 「{b_atk}」\n- {u_name}の対応: 当初{b_orig}点 ➔ 修正後{u_adj}点（{cross_debate.get('adjustment_rationale', '')}）"

                regime_section = ""
                if regime_info:
                    regime_section = f"\n市場レジーム: {regime_info.get('regime_name')} ({regime_info.get('rationale')})"

                client = genai.Client(api_key=api_key)
                prompt = f"""銘柄: {name}
総合判定: {action_label} (総合確信度スコア: {overall_score}点){regime_section}

各エージェントの独立意見:{debate_section}
{opinions}

上記7大投資家とリスク管理者、およびクロスディベートの激突結果を裁判官（CIO）として公正に総括し、投資判断の核心となる投資根拠（Thesis Summary）を200文字程度の格調高い文章で1段落で出力してください。"""

                res = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )
                if res and res.text:
                    return res.text.strip()
        except Exception:
            pass

        # Deterministic fallback
        name = stock_data.get("name", "対象銘柄")
        bulls = [a['name'] for a in analyst_results if a.get('stance') == 'BULLISH']
        bears = [a['name'] for a in analyst_results if a.get('stance') in ('BEARISH', 'CAUTION')]
        
        bull_str = "、".join(bulls[:2]) if bulls else "一部アナリスト"
        bear_str = "、".join(bears[:2]) if bears else "慎重派"
        
        return f"{bull_str}による成長・モメンタム評価に対し、{bear_str}によるバリュエーションおよび下値リスクの指摘を総合審理。リスクリワード比および厳格な損切りラインを担保した上で、{action_label}の判断を下す。"
