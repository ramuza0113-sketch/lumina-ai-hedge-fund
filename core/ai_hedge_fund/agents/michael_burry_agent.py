from typing import Dict, Any, Optional
from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent

class MichaelBurryAgent(BaseInvestmentAgent):
    agent_id = "michael_burry"
    name = "マイケル・バーリ"
    title = "深層脆弱性・バブル警戒官"
    avatar = "📉"
    philosophy = """
- 『マネー・ショート』でサブプライム危機を完全予見した逆張り（Contrarian）の達人。
- 「市場全体が陶酔感（Euphoria）に浸っている時こそ、致命的な亀裂が隠されている。」
- 異常な過熱バリュエーション（PER 40倍超など）、経営陣や創業者の自社株売り（インサイダー売り）、過剰なレバレッジ・負債、会計の粉飾的歪みを徹底追求する。
- 世間の熱狂やSNSのバズに真っ向から冷や水を浴びせ、空売り（Short）や利益確定売りを警告する。
- 誰も見向きもしない、不人気で徹底的に叩き売られた真のディープバリューだけを好む。
"""

    @classmethod
    def _rule_based_fallback(cls, stock_data: Dict[str, Any], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pe = float(stock_data.get("pe_trailing") or 20.0)
        pb = float(stock_data.get("pb_ratio") or 2.0)
        # 高PER・高PBRには極めて厳しい減点
        score = min(95, max(15, int(85 - (pe * 0.9 + pb * 5.0))))
        stance = "BULLISH" if score >= 75 else ("BEARISH" if score <= 40 else "CAUTION")

        dialogue = f"PER {pe}倍、PBR {pb}倍。大衆は盲目的に熱狂しているが、前提が少し狂えば一瞬でクラッシュする脆弱な構造だ。私はこの陶酔相場の梯子外しを警告しておく。"
        if score >= 65:
            dialogue = f"PER {pe}倍と市場から不当に放置・悲観されている。過熱感はなく、大衆が投げ売りを終えた後の底値圏であり、非対称なアップサイドが狙える稀有な局面だ。"

        return {
            "agent_id": cls.agent_id,
            "name": cls.name,
            "title": cls.title,
            "avatar": cls.avatar,
            "stance": stance,
            "score": score,
            "dialogue": dialogue
        }
