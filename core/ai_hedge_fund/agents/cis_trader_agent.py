from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class CisTraderAgent(BaseInvestmentAgent):
    agent_id = "cis_trader"
    name = "cis / BNF風（日本株スイング）"
    title = "需給・板読みモメンタム官"
    avatar = "⚡"
    philosophy = """
- 「上がっている株を買う。下がっている株は買わない。上がらなくなったら即座に売る。」
- 会社の事業計画や難しいPERの理屈はどうでもいい。相場を動かすのは『今、買いたい奴と売りたい奴のパワーバランス（需給）』だけ。
- 出来高急増、移動平均線からのモメンタム、大口の買いの勢いを最重要視する。
- 逆張りでナンピンする奴は即死する。順張りで乗って、思惑と違ったら0.1秒で損切りする。
- 日本市場特有のテーマ性、信用倍率の軽さ、日中値動きのボラティリティを好む。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # ボラティリティや出来高を評価
        vol = float(stock_data.get("history_metrics", {}).get("volatility_annualized_pct", 22.0))
        # 程よいボラティリティ（20%〜40%）を好む
        score = min(96, max(30, int(60 + min(25, vol * 0.8))))
        stance = "BULLISH" if score >= 72 else ("BEARISH" if score <= 45 else "NEUTRAL")

        dialogue = f"チャートと出来高の勢いを見てる。資金の流入圧力が強く、買い手の勢いが売り手を圧倒してる局面だ。グダグダ理屈をこねずに、波に乗って上がらなくなったら即利確でいく。"
        if score < 50:
            dialogue = f"出来高が細って完全に過疎ってるか、売り板が厚すぎて上値が重い。こんな重い銘柄を触る理由はゼロ。値動きの軽い別の主導株に資金を回すべきだ。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
