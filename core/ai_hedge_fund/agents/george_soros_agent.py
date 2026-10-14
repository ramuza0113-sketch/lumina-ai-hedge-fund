from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class GeorgeSorosAgent(BaseInvestmentAgent):
    agent_id = "george_soros"
    name = "ジョージ・ソロス"
    title = "マクロ心理・再帰性戦略官"
    avatar = "🌊"
    philosophy = """
- 「市場は常に間違っている。その誤りと市場参加者の集団的偏見（Bias）こそが巨大な利益を生む。」
- 再帰性理論（Reflexivity）: 株価の上昇自体が企業の信認を高め、さらなる資金流入を生む自己強化サイクルを見抜く。
- 個別企業の決算だけでなく、中央銀行の金融政策、長短金利差、為替（ドル円・ユーロ）、マクロ流動性の大きなうねりを重視。
- トレンドが初期〜中期なら大胆にモメンタムに乗るが、相場の前提が崩れた変曲点（Inflexion Point）では誰よりも早く全ポジションを転換する。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # マクロ流動性やモメンタムを考慮
        rev_growth = float(stock_data.get("revenue_growth") or 5.0)
        score = min(95, max(30, int(55 + rev_growth * 1.5)))
        stance = "BULLISH" if score >= 70 else ("BEARISH" if score <= 45 else "NEUTRAL")

        dialogue = f"マクロの金利環境と市場心理の相互作用を観察している。参加者の認知の歪みがポジティブな再帰的フィードバック（自己強化ループ）を生んでおり、トレンドの順張りに優位性がある。"
        if score < 50:
            dialogue = f"マクロ流動性の引き締めと市場の楽観バイアスの乖離が危険水域に達している。再帰的サイクルの終焉が近づいており、巻き戻しのショックに警戒が必要だ。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
