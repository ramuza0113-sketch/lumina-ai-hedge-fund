---
title: 'Lumina Capital (`lumina-quant`): A Quantitative Market Microstructure and Anti-Sycophancy Multi-Agent Research Framework with Schmitt-Trigger Factor Ontologies, Scroll-Out Resistant Deep OFI, and Slippage-Proof Pyramiding'
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
date: 6 November 2026
bibliography: paper.bib
---

# Summary

`Lumina Capital` (installable as the standalone Python research library `lumina-quant`) is an open-source quantitative finance and market microstructure research framework that combines deterministic mathematical risk invariants, high-frequency limit order book (LOB) econometrics, and anti-sycophancy multi-agent Large Language Model (LLM) deliberation. Designed for financial economists, market microstructure researchers, and quantitative systems engineers, the software provides modular Python primitives (`import lumina_quant`) alongside an experimental simulation environment spanning US equities, Japanese equities (Tokyo Stock Exchange), and spot precious metals (`XAUUSD`/`XAGUSD`). By strictly decoupling probabilistic qualitative reasoning from deterministic quantitative execution and formal risk invariants, `Lumina Capital` enables reproducible empirical investigation of hybrid AI-quantitative models under realistic market frictions.

# Statement of need

Recent open-source financial machine learning and agent frameworks have catalyzed empirical research into automated market decision-making, yet researchers investigating hybrid LLM-microstructure systems encounter three fundamental theoretical and methodological gaps [@hashimoto2026whitepaper]:

1. **Semantic Polarity Inversion and Boundary Chattering:** Generative agents frequently misinterpret inverse valuation or distress metrics (such as $\text{EV/EBITDA}$ or debt-to-equity ratios) as positively correlated with forward returns, while memoryless threshold rules oscillate rapidly when factor $z$-scores hover near regime boundaries.
2. **Order Book Horizon Truncation Bias (The Scroll-Out Spoofing Illusion):** In finite $K$-level limit order book streams ($K \in \lbrace 10, 60\rbrace$), a rapid upward price impulse shifts the visible depth window upward, causing resting bid walls at deeper price levels $p < P_{\text{bid}, K}^{(t)}$ to scroll out of the observation payload. Naive cancellation estimators misclassify this window truncation as a $100\%$ liquidity pull (bearish spoofing) at the exact onset of a genuine breakout.
3. **Pyramiding Ruin Under Jump Slippage:** Scaling into profitable positions raises the aggregate break-even price, creating vulnerability to net losses when consolidated trailing stops experience adverse gap slippage.

`Lumina Capital` (`lumina-quant`) addresses these challenges by providing a unified, mathematically verified Python and Rust research library that bridges cross-sectional factor investing [@yang2020qlib], subordinated volume-clock sampling [@clark1973subordinated; @lopez2018advances], multi-level order flow imbalance [@cont2014price], asynchronous cross-asset covariance [@hayashi2005covariance], and institutional overfitting diagnostics [@bailey2014deflated].

# State of the field

Existing academic financial machine learning platforms address subsets of the quantitative modeling pipeline but leave a structural gap between microstructure econometrics and multi-agent reasoning:

- **Reinforcement Learning Frameworks (`FinRL`):** @liu2020finrl provide a foundational deep reinforcement learning library (`FinRL`) for automated trading across continuous and discrete action spaces. However, `FinRL` optimizes black-box policies over bar-level state vectors without modeling heterogeneous adversarial agent deliberation (anti-sycophancy), explicit semantic factor polarity contracts, or finite-window limit order book horizon truncation.
- **Factor Investment Platforms (`Microsoft Qlib`):** @yang2020qlib introduce `Qlib` for daily and intraday alpha factor engineering (`Alpha158`). While `Lumina Capital` incorporates `Alpha158` factor formulations, `Qlib` focuses primarily on supervised cross-sectional return prediction over chronological wall-clock bars rather than subordinated volume-clock normality restoration [@clark1973subordinated], @hayashi2005covariance asynchronous lead-lag covariance with @higham2002computing positive semi-definite (PSD) projection, or sub-microsecond Rust stop-loss enforcement.
- **Conversational Agent Repositories (`TradingAgents` / `ai-hedge-fund`):** Community multi-agent repositories (`virattt/ai-hedge-fund`, `TauricResearch/TradingAgents`) demonstrate sequential LLM persona prompting but lack deterministic microstructure math, exchange tick/lot conformance, and formal statistical overfitting audits.

`Lumina Capital` fills this gap as a modular research library (`import lumina_quant`) uniting deterministic microstructure mathematics with verifiable multi-agent deliberation.

# Software design

`Lumina Capital` is architected around four deterministic layers that can be imported independently in Python research scripts or Jupyter notebooks without external API keys:

1. **Deterministic Factor Ontology and Schmitt-Trigger Hysteresis:** Raw cross-sectional factors (including Qlib Alpha158 features [@yang2020qlib] and TimesFM probabilistic forecasts [@das2024decoder]) are mapped into a canonical nonnegative polarity space (`FactorOntology`) prior to agent inspection. A discrete-time Schmitt-Trigger hysteresis operator with symmetric deadband $[-\delta, +\delta]$ suppresses regime chattering under local Gaussian noise.
2. **Scroll-Out Resistant Deep OFI and Rust SoA Sentinel:** Extending @cont2014price across $K$ visible book levels, `DeepOFIAnalyzer` enforces a visible-window boundary invariant $(P_{\text{bid}, K}^{(t)} \le p \le P_{\text{bid}, 1}^{(t)})$, executed trade-volume subtraction, and $0.12\text{ s}$ twin-snapshot differentials to eliminate false-positive spoofing alerts. High-frequency stop-loss evaluation is offloaded to a `#![forbid(unsafe_code)]` Rust Structure-of-Arrays (SoA) sentinel (`lumina-sentinel-rs`) achieving $3.63\text{ ns}$ per position check.
3. **Volume Clocks, Cross-Asset Covariance, and Exchange Conformance:** `VolumeClockSampler` transforms fat-tailed wall-clock returns into subordinated volume bars [@clark1973subordinated; @lopez2018advances] with a $1,800\text{ s}$ illiquidity timeout fallback. Asynchronous lead-lag relationships across US/Japanese equities, FX, and commodities are estimated via `LeadLagAnalyzer` using the @hayashi2005covariance estimator projected onto the nearest PSD cone via @higham2002computing, paired with half-Kelly sizing [@kelly1956new] and exact Tokyo Stock Exchange tick/lot normalization.
4. **Formal Verification and Overfitting Audit Suite:** The repository includes automated property-based fuzzing (`Hypothesis`) across $1,000$ adversarial order book trajectories, SMT theorem proving (`Microsoft Z3`) for slippage-proof pyramiding bounds, and deterministic implementations (`DeterministicMetrics`) of Walk-Forward Efficiency (WFE), Purged & Embargoed Combinatorial Symmetric Cross-Validation (CPCV), and the Deflated Sharpe Ratio [@bailey2014deflated].

# Research impact statement

`Lumina Capital` has been officially indexed in the curated `awesome-quant` and `Awesome_AI4Finance` research registries and archived with permanent identifiers on CERN Zenodo (`10.5281/zenodo.23935930`), OSF Preprints (`10.17605/OSF.IO/76PF3`), and Figshare (`10.6084/m9.figshare.34923813`). The core mathematical library (`lumina-quant`, published on the Python Package Index (`pip install lumina-quant`, https://pypi.org/project/lumina-quant/) and installable from source via `pip install .` with zero external API keys) exposes standalone Python classes (`DeepOFIAnalyzer`, `FactorOntology`, `VolumeClockSampler`, `LeadLagAnalyzer`, `DeterministicMetrics`) backed by an offline `pytest` verification suite covering 20 institutional hardening tests and $1,000$ `Hypothesis` property-based trajectories. Across a 5-year out-of-sample empirical audit (2021–2026), the framework achieved a Walk-Forward Efficiency of $73.3\%$ ($89.6\%$ multi-window reference), a 15-split Purged CPCV median Sharpe ratio of $1.09$ (mean $1.15$, $0/15$ negative splits, $20.0\%$ baseline PBO), a Deflated Sharpe Ratio of $99.14\%$ ($p = 0.0086 < 0.01$), and $0.0000\%$ ruin probability across $10,000$ Monte Carlo path permutations.

# AI usage disclosure

Generative AI tools (Google Gemini and Anthropic Claude) were used as pair-programming assistants during software scaffolding, unit test generation, and LaTeX/Markdown formatting of documentation and this manuscript. All mathematical derivations, microstructure theorems, econometric estimators, and risk invariants were conceived, audited, and formally verified by the human author using the Microsoft Z3 SMT solver, property-based testing (`Hypothesis`), and 5-year historical market data evaluations.

# Acknowledgements

The author thanks the open-source maintainers of Qlib, FinRL, LangGraph, and the Rust financial computing community for foundational libraries and technical discussions. This research received no external grant funding.

# References
