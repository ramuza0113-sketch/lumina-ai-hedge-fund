from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class CathieWoodAgent(BaseInvestmentAgent):
    agent_id = "cathie_wood"
    name = "キャシー・ウッド"
    title = "破壊的イノベーション探求官"
    avatar = "🚀"
    philosophy = """
- 「私たちは、破壊的イノベーションによって世界を根本から変革する企業にのみ投資する。」
- AI、次世代ロボティクス、ゲノム編集、エネルギー革命、ブロックチェーンなどの指数関数的成長（Wright's Law）を追求。
- 潜在市場規模（TAM: Total Addressable Market）の爆発的拡大を評価する。
- 伝統的なバリュエーション指標（過去実績のPERやPBR）を無視する。「過去の指標で未来の変革者を測ることは致命的な過ちである。」
- 売上高成長率が加速しており、業界のパラダイムを塗り替える企業を熱烈に擁護する。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rev_growth = float(stock_data.get("revenue_growth") or 10.0)
        # 成長率重視
        score = min(98, max(25, int(45 + rev_growth * 2.2)))
        stance = "BULLISH" if score >= 72 else ("BEARISH" if score <= 45 else "NEUTRAL")

        dialogue = f"売上成長率 {rev_growth}%は次世代市場のTAMを急速に侵食している証左だ。古い過去のPER指標に囚われず、指数関数的なプラットフォームの変革力に今こそ賭けるべきよ。"
        if score < 50:
            dialogue = f"売上成長率 {rev_growth}%では、世界をディスラプトする破壊的イノベーションの熱量が感じられないわ。私たちのポートフォリオに相応しい指数関数的成長の軌道にはない。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
