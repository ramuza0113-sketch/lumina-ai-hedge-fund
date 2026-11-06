# -*- coding: utf-8 -*-
"""
Lumina Quantitative Microstructure & Multi-Agent Research Library (`lumina-quant`)
==================================================================================
Provides standalone, deterministic mathematical modules for market microstructure,
factor ontology standardization, information-driven sampling, asynchronous covariance,
and institutional overfitting audits (WFE, Purged CPCV, Deflated Sharpe Ratio)
without requiring external LLM API keys or live brokerage connections.
"""

from core.ai_hedge_fund.deep_ofi_analyzer import (
    DeepOFIAnalyzer,
    OrderBookLevel,
    OrderBookSnapshot,
)
from core.ai_hedge_fund.factor_ontology import (
    FactorOntology,
    FactorSchema,
)
from core.ai_hedge_fund.volume_clock_sampler import VolumeClockSampler
from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
from core.ai_hedge_fund.deterministic_metrics import DeterministicMetrics

__version__ = "6.6.5"

__all__ = [
    "DeepOFIAnalyzer",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "FactorOntology",
    "FactorSchema",
    "VolumeClockSampler",
    "LeadLagAnalyzer",
    "DeterministicMetrics",
]
