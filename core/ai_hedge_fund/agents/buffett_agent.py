from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class BuffettAgent(BaseInvestmentAgent):
    agent_id = "buffett"
    name = "ウォーレン・バフェット"
    title = "価値創造・堀の番人"
    avatar = "🎩"
    philosophy = """
- 「喜んで10年間持ち続けられる株でなければ、10分間たりとも持つべきではない。」
- 企業の「堀（Economic Moat）」、持続可能な競争優位性、オーナー利益（フリーキャッシュフロー）を最重視する。
- 資本収益性（ROE > 12%〜15%）と誠実で有能な経営陣を求める。目先のハイテクブームや四半期ごとの市場ノイズには一切惑わされない。
- 一時的なスキャンダルや相場急落で優良企業の株価が投げ売られた時こそ、最高の買い場と見なす。
- 理解できない複雑なハイテクや赤字垂れ流しの企業には、いくら話題でも絶対に投資しない（Circle of Competence）。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        roe = float(stock_data.get("roe") or 8.0)
        pb = float(stock_data.get("pb_ratio") or 1.5)
        # ROE重視、PBRが低ければ加点
        score = min(96, max(25, int(roe * 3.8 + (2.5 / max(0.6, pb)) * 8)))
        stance = "BULLISH" if score >= 72 else ("BEARISH" if score <= 45 else "NEUTRAL")
        name = stock_data.get("name", "対象銘柄")
        
        dialogue = f"ROE {roe}%という資本効率と事業の安定性を精査した。我々が求めるのは予測可能な現金創出能力（オーナー利益）であり、この水準なら長期的な堀の維持に期待が持てる。"
        if score < 50:
            dialogue = f"資本収益率（ROE {roe}%）が物足りない。参入障壁としての『堀』が不十分であり、10年間の長期保有に値する確信が持てないため見送りを進言する。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
