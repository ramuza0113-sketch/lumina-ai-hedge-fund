from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class WilliamOneilAgent(BaseInvestmentAgent):
    agent_id = "william_oneil"
    name = "ウィリアム・オニール"
    title = "CANSLIM・成長株モメンタム官"
    avatar = "📈"
    philosophy = """
- 「安値で買って高値で売るのではない。高値で買って、さらに高値で売るのだ。」
- 伝説のCANSLIM投資法:
  - C (Current Earnings): 直近四半期EPSが前年同期比+25%〜+50%以上加速しているか。
  - A (Annual Earnings): 過去3〜5年の年間EPS成長率が25%以上か。
  - N (New): 新製品・新サービス・新高値ブレイクアウト（カップウィズハンドル等）。
  - S (Supply and Demand): 出来高急増を伴うブレイク。
  - L (Leader): 業界のNo.1主導株か（出遅れ株・負け犬株は買わない）。
  - I (Institutional Sponsorship): 優秀な機関投資家の資金流入があるか。
  - M (Market Direction): 相場全体が上昇トレンドにあるか。
- 割安株（ボロ株）の逆張りは絶対にしない。新高値をブレイクした最強の主導株に乗る。
- 買値から7%〜8%下落したら理由を問わず機械的に即損切り（Cut Losses Quickly）。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rev_growth = float(stock_data.get("revenue_growth") or 8.0)
        roe = float(stock_data.get("roe") or 10.0)
        score = min(96, max(30, int(50 + rev_growth * 1.6 + roe * 0.8)))
        stance = "BULLISH" if score >= 72 else ("BEARISH" if score <= 45 else "NEUTRAL")

        dialogue = f"直近の成長トレンドと業績モメンタムを精査した。CANSLIMの基準に照らし、売上高成長率 {rev_growth}%は主導株の資格を伺わせる。出来高急増を伴う新高値ブレイクの初動を狙う。"
        if score < 50:
            dialogue = f"成長率 {rev_growth}%ではモメンタムが弱すぎる。業界のトップリーダーとは呼べず、機関投資家の猛烈な買い集め（スポンサーシップ）も見られないため選外とする。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
