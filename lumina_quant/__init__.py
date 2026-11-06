# -*- coding: utf-8 -*-
"""
`lumina_quant` — Standalone Quantitative Market Microstructure & Factor Ontology Research Package
=================================================================================================
Exposes deterministic mathematical primitives for high-frequency limit order book analysis,
Schmitt-Trigger factor ontology standardization, information-driven volume-clock sampling,
asynchronous cross-asset covariance estimation (Hayashi-Yoshida + Higham Nearest-PSD projection),
and institutional overfitting diagnostics (Walk-Forward Efficiency, Purged CPCV, Deflated Sharpe Ratio)
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
from core.ai_hedge_fund.broker_client import (
    round_price_to_exchange_tick,
    normalize_exchange_lot_size,
)

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
    "round_price_to_exchange_tick",
    "normalize_exchange_lot_size",
]
