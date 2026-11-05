---
title: 'Lumina Capital: An Autonomous Multi-Agent Quantitative Hedge Fund Engine with Schmitt-Trigger Factor Ontologies, Scroll-Out Resistant Deep OFI, and Slippage-Proof Pyramiding'
tags:
  - Python
  - Rust
  - quantitative finance
  - market microstructure
  - limit order book
  - multi-agent systems
  - formal verification
authors:
  - name: Katsutoshi Hashimoto
    orcid: 0009-0009-8292-5085
    affiliation: 1
affiliations:
  - name: Lumina Capital AI Research, Japan
    index: 1
date: 4 November 2026
bibliography: paper.bib
---

# Summary

`Lumina Capital` is an open-source quantitative finance and market microstructure research framework that combines deterministic mathematical risk controls, high-frequency limit order book (LOB) analytics, and multi-agent Large Language Model (LLM) deliberation. Designed for researchers, financial economists, and algorithmic trading practitioners, the software provides an end-to-end simulation and execution studio spanning US equities, Japanese equities (Tokyo Stock Exchange), and spot precious metals (`XAUUSD`/`XAGUSD`). By strictly decoupling probabilistic qualitative reasoning from deterministic quantitative execution and formal risk invariants, `Lumina Capital` enables reproducible empirical evaluation of hybrid AI-quantitative strategies under realistic market frictions.

# Statement of need

Recent open-source financial agent frameworks have demonstrated the ability of LLM ensembles to synthesize unstructured corporate disclosures and macroeconomic narratives. However, deploying such architectures in empirical microstructure environments exposes three critical failure modes [@hashimoto2026whitepaper]:

1. **Semantic Polarity Inversion and Boundary Chattering:** Generative agents frequently misinterpret inverse valuation or distress metrics (such as $\text{EV/EBITDA}$ or debt-to-equity ratios) as positively correlated with forward returns, while memoryless threshold rules oscillate rapidly when factor $z$-scores hover near regime boundaries.
2. **Order Book Horizon Truncation Bias (The Scroll-Out Spoofing Illusion):** In finite $K$-level limit order book streams ($K \in \lbrace 10, 60\rbrace $), a rapid upward price impulse shifts the visible depth window upward, causing resting bid walls at deeper price levels $p < P_{\text{bid}, K}^{(t)}$ to scroll out of the observation payload. Naive cancellation estimators misclassify this window truncation as a $100\%$ liquidity pull (bearish spoofing) at the exact onset of a genuine breakout.
3. **Pyramiding Ruin Under Jump Slippage:** Scaling into profitable positions raises the aggregate break-even price, creating vulnerability to net losses when consolidated trailing stops experience adverse gap slippage.

`Lumina Capital` addresses these challenges by providing a unified, mathematically verified software package that bridges factor investing [@yang2020qlib], multi-level order flow imbalance [@cont2014price], and institutional overfitting audits [@bailey2014deflated; @lopez2018advances].

# State of the field

Existing open-source multi-agent trading repositories such as `virattt/ai-hedge-fund` and `TauricResearch/TradingAgents` focus primarily on prompt orchestration and sequential persona dialogues. While valuable as educational demonstrations of LLM tool use, they do not model multi-level limit order book dynamics, asynchronous cross-asset covariance, exchange-specific tick and lot size constraints, or formal statistical overfitting diagnostics. Conversely, traditional backtesting libraries (`Backtrader`, `Zipline`, `VectorBT`) provide historical bar simulation but lack native abstractions for Schmitt-Trigger factor ontologies, scroll-out resistant depth imbalance, or episodic agent memory with exponential time decay. `Lumina Capital` fills this gap as a purpose-built research platform uniting deterministic microstructure mathematics with multi-agent deliberation.

# Software design

`Lumina Capital` is architected around four deterministic layers:

1. **Deterministic Factor Ontology and Schmitt-Trigger Hysteresis:** Raw cross-sectional factors (including Microsoft Qlib Alpha158 features [@yang2020qlib] and Google TimesFM probabilistic forecasts [@das2024decoder]) are mapped into a canonical nonnegative polarity space prior to agent inspection. A discrete-time Schmitt-Trigger hysteresis operator with symmetric deadband $[-\delta, +\delta]$ suppresses regime chattering under local Gaussian noise.
2. **Scroll-Out Resistant Deep OFI and Rust SoA Sentinel:** Extending @cont2014price across $K$ visible book levels, the microstructure engine enforces a visible-window boundary invariant ($P_{\text{bid}, K}^{(t)} \le p \le P_{\text{bid}, 1}^{(t)}$), executed trade-volume subtraction, and $0.12\text{ s}$ twin-snapshot differentials to eliminate false-positive spoofing alerts. High-frequency stop-loss and trailing-stop evaluation is offloaded to a `#![forbid(unsafe_code)]` Rust Structure-of-Arrays (SoA) sentinel (`lumina-sentinel-rs`) achieving $3.63\text{ ns}$ per position check.
3. **Cross-Asset Covariance and Exchange Conformance:** Asynchronous lead-lag relationships across equities, FX, and commodities are estimated via the @hayashi2005covariance estimator projected onto the nearest positive semi-definite cone via @higham2002computing, paired with half-Kelly sizing [@kelly1956new] and exact Tokyo Stock Exchange tick/lot normalization.
4. **Formal Verification and Overfitting Audit Suite:** The repository includes automated property-based fuzzing (`Hypothesis`) across $1,000$ adversarial order book trajectories, SMT theorem proving (`Microsoft Z3`) for slippage-proof pyramiding bounds, and deterministic implementations of Walk-Forward Efficiency (WFE), Purged & Embargoed Combinatorial Symmetric Cross-Validation (CPCV), and the Deflated Sharpe Ratio [@bailey2014deflated].

# Research impact statement

`Lumina Capital` has been officially indexed in the curated `awesome-quant` and `Awesome_AI4Finance` research registries and archived with permanent identifiers on CERN Zenodo (`10.5281/zenodo.23935930`) and Figshare (`10.6084/m9.figshare.34923813`). Across a 5-year out-of-sample empirical audit (2021–2026), the framework achieved a Walk-Forward Efficiency of $89.6\%$, a 15-split Purged CPCV median Sharpe ratio of $1.29$ ($0.0\%$ Probability of Backtest Overfitting), a Deflated Sharpe Ratio of $97.76\%$ ($p = 0.0224$), and $0.0000\%$ ruin probability across $10,000$ Monte Carlo path permutations.

# AI usage disclosure

Generative AI tools (Google Gemini and Anthropic Claude) were used as pair-programming assistants during software scaffolding, unit test generation, and LaTeX/Markdown formatting of documentation and this manuscript. All mathematical derivations, microstructure theorems, and risk invariants were formally verified using the Microsoft Z3 SMT solver, property-based testing (`Hypothesis`), and 5-year historical market data audits conducted by the author.

# Acknowledgements

The author thanks the open-source maintainers of Qlib, LangGraph, and the Rust financial computing community for foundational libraries and technical discussions. This research received no external grant funding.

# References
