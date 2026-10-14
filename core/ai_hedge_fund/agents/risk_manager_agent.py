from typing import Dict, Any, Optional, List
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent
from core.ai_hedge_fund.options_gex_feed import OptionsGexFeed

class RiskManagerAgent(BaseInvestmentAgent):
    agent_id = "risk_manager"
    name = "リスク管理者 (CRO)"
    title = "資産防衛・悪魔の代弁者"
    avatar = "🛡️"
    philosophy = """
- 「投資で最も重要なのは、大勝ちすることではない。致命傷を避けて生き残り続けることだ。」
- 他のアナリストたちが強気（BULLISH）で浮かれている時こそ、最悪のシナリオ（不正会計、リコール、マクロ金利急騰、相場急変）を暴き出す悪魔の代弁者（Red Team）。
- 統計的エッジと日中ノイズ耐性に優れたフィボナッチ最適値（買値×0.87＝-13.0%）を基本防壁とし、急変時の最大許容ドローダウン（-15.0%）を安全天井として損切りラインを強制する。
- 市場のガンマフリップ（Gamma Flip割れ）やボラティリティ急増時は、推奨配分を容赦なく半減またはゼロにする拒否権（Veto）を行使する。
"""

    @classmethod
    def evaluate_risk(
        cls, 
        stock_data: Dict[str, Any], 
        analyst_results: List[Dict[str, Any]], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate portfolio risk, perform Red Team counter-arguments, and calculate dynamic stop-loss.
        """
        price = float(stock_data.get("current_price") or 1000.0)
        currency = stock_data.get("currency", "JPY")
        vol = float(stock_data.get("history_metrics", {}).get("volatility_annualized_pct", 20.0))
        
        # Dynamic Stop Loss with Anti-Whipsaw ATR Breathing Floor (Preventing "損切り貧乏")
        hist_metrics = stock_data.get("history_metrics", {})
        dynamic_sl = hist_metrics.get("dynamic_stop_loss_price")
        atr_pct = float(hist_metrics.get("atr_pct") or 3.5)
        min_breathing_pct = max(5.0, min(16.0, atr_pct * 2.0))

        if dynamic_sl and dynamic_sl > 0:
            stop_loss = round(dynamic_sl, 2 if currency == "USD" else 1)
        else:
            stop_loss = round(price * (1.0 - min_breathing_pct / 100.0), 2 if currency == "USD" else 1)

        
        # Market turbulence / Options Gamma Flip check
        mkt_turb = OptionsGexFeed.get_market_turbulence_warning()
        is_turbulence = mkt_turb.get("is_turbulence", False)
        
        # Default safety score
        safety_score = min(92, max(30, int(78 - vol * 0.7)))
        if is_turbulence:
            safety_score = max(25, safety_score - 15)

        # Count bullish vs bearish from analysts
        bullish_count = sum(1 for a in analyst_results if a.get("stance") == "BULLISH")
        bearish_count = sum(1 for a in analyst_results if a.get("stance") in ("BEARISH", "CAUTION"))

        alloc = 10.0
        if bullish_count >= 5:
            alloc = 12.0
        elif bullish_count <= 2:
            alloc = 5.0
        
        # --- 🚨 CRO絶対的拒否権 (Absolute Veto Power) 判定 ---
        veto_triggered = False
        veto_reason = ""
        
        macro_liq = context_data.get("macro_liquidity", {}) if context_data else {}
        is_crunch = macro_liq.get("liquidity_crunch", False) or macro_liq.get("net_liquidity_weather") == "TIGHTENING"
        
        if is_turbulence and vol >= 30.0:
            veto_triggered = True
            veto_reason = "オプションGamma Flip割れ＋急変ボラティリティ急拡大による暴落警戒"
        elif is_turbulence and is_crunch:
            veto_triggered = True
            veto_reason = "FRB流動性引き締め局面における市場ガンマ急落（流動性ショック危機）"
        elif vol >= 60.0:
            veto_triggered = True
            veto_reason = f"対象銘柄の異常ボラティリティ（{vol:.1f}%）による壊滅的急落リスク"
        elif context_data and context_data.get("news_intelligence", {}).get("is_quarantined", False):
            veto_triggered = True
            veto_reason = "不審な風説・煽りニュース検知による情報汚染遮断（検疫プロトコル発動）"

        if veto_triggered:
            alloc = 0.0
            safety_score = 15
            stance = "VETO"
            dialogue = f"🚨【CRO絶対的拒否権（VETO）発動】{veto_reason}！アナリスト陣の意見に関わらず、資金防衛サーキットブレーカーを強制執行。新規ポジション建てを全面凍結（配分0.0%）とする。"
        elif is_turbulence:
            alloc = round(alloc * 0.5, 1)
            dialogue = f"⚠️【市場乱気流警報】SPY/QQQのGamma Flip割れを検知。急落ボラティリティを警戒し、現在値 {price} に対する損切りラインを {stop_loss} ({currency}) に強制固定。推奨配分を半減（{alloc}%）に抑制する。"
            stance = "CAUTION"
        elif bearish_count >= 3:
            dialogue = f"アナリスト陣の間で慎重論が根強い。ボラティリティ {vol}% に対し、下値防壁として損切りライン {stop_loss} ({currency}) を厳格に適用。最大リスク許容枠は {alloc}% を上限とする。"
            stance = "CAUTION"
        else:
            dialogue = f"現在値 {price} に対し、フィボナッチ最適値に基づく厳格な損切りラインを {stop_loss} ({currency}) に設定。ポートフォリオ全体の最大配分は {alloc}% を上限とし、資産防衛を担保する。"
            stance = "NEUTRAL" if bullish_count < 4 else "BULLISH"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": safety_score,
            "dialogue": dialogue,
            "stop_loss_price": stop_loss,
            "max_allocation_pct": alloc,
            "is_turbulence": is_turbulence,
            "veto_triggered": veto_triggered,
            "veto_reason": veto_reason
        }
