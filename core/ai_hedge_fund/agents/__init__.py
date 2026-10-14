from core.ai_hedge_fund.agents.base_agent import BaseInvestmentAgent
from core.ai_hedge_fund.agents.buffett_agent import BuffettAgent
from core.ai_hedge_fund.agents.graham_agent import GrahamAgent
from core.ai_hedge_fund.agents.cathie_wood_agent import CathieWoodAgent
from core.ai_hedge_fund.agents.michael_burry_agent import MichaelBurryAgent
from core.ai_hedge_fund.agents.george_soros_agent import GeorgeSorosAgent
from core.ai_hedge_fund.agents.william_oneil_agent import WilliamOneilAgent
from core.ai_hedge_fund.agents.cis_trader_agent import CisTraderAgent
from core.ai_hedge_fund.agents.risk_manager_agent import RiskManagerAgent
from core.ai_hedge_fund.agents.portfolio_manager_agent import PortfolioManagerAgent

ALL_ANALYST_AGENTS = [
    BuffettAgent,
    GrahamAgent,
    CathieWoodAgent,
    MichaelBurryAgent,
    GeorgeSorosAgent,
    WilliamOneilAgent,
    CisTraderAgent,
]

__all__ = [
    "BaseInvestmentAgent",
    "BuffettAgent",
    "GrahamAgent",
    "CathieWoodAgent",
    "MichaelBurryAgent",
    "GeorgeSorosAgent",
    "WilliamOneilAgent",
    "CisTraderAgent",
    "RiskManagerAgent",
    "PortfolioManagerAgent",
    "ALL_ANALYST_AGENTS",
]
