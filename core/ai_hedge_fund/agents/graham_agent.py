from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class GrahamAgent(BaseInvestmentAgent):
    agent_id = "graham"
    name = "ベンジャミン・グレアム"
    title = "安全域・深層バリュー分析官"
    avatar = "📊"
    philosophy = """
- 「投資とは、徹底的な分析に基づいて、元本の安全と満足すべきリターンを約束するものである。」
- バリュー投資の父。他者の将来成長に対するバラ色の熱弁には一切同調しない。
- 徹底した「安全域（Margin of Safety）」を要求する。PBR 1.0倍割れ、ネットネット株（純流動資産以下）、低PERを好む。
- グレアム数（√(22.5 × EPS × BPS)）より現在の株価が著しく高い場合、たとえどんな成長企業であっても容赦なくNO（BEARISH）を突きつける。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pb = float(stock_data.get("pb_ratio") or 1.5)
        pe = float(stock_data.get("pe_trailing") or 18.0)
        # 低PBR・低PER重視
        score = min(96, max(20, int(65 + (1.2 - min(3.0, pb)) * 22 + (15.0 - min(35.0, pe)) * 0.8)))
        stance = "BULLISH" if score >= 70 else ("BEARISH" if score <= 45 else "NEUTRAL")
        
        dialogue = f"実績PBR {pb}倍、実績PER {pe}倍を精査した。市場の過熱感はなく、下値支持線としての安全域（Margin of Safety）は一定程度確保されていると判定する。"
        if score < 50:
            dialogue = f"PBR {pb}倍、PER {pe}倍は明白な過大評価だ。投機的な将来期待が価格に織り込まれすぎており、暴落時に下値を守る安全域が完全に欠落している。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
