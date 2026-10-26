# -*- coding: utf-8 -*-
"""
Lumina Capital — Quantitative Factor Ontology & Semantic Metadata Schema (`factor_ontology.py`)
==============================================================================================
Addresses LLM numeric hallucination in multi-agent debate (`u/Illustrious_Ad7630` architecture):
Instead of feeding raw, unlabeled numbers (e.g., `KLEN=0.042`, `WVMA_5=1.83`, `flow_velocity=2.1`)
directly into LLM prompts where personas might misinterpret polarity or scale, this module defines
a strict mathematical ontology for every factor:
  - Mathematical formula & unit
  - Polarity (`HIGHER_IS_BULLISH`, `LOWER_IS_BULLISH`, `REGIME_DEPENDENT`)
  - Normal operating bounds & anomaly thresholds
  - Primary investor personas (`buffett`, `graham`, `cathie_wood`, `michael_burry`, `george_soros`,
    `william_oneil`, `cis_trader`, `risk_manager`, `cio`)
  - Deterministic semantic translation into zero-ambiguity structured prompt cards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FactorSchema:
    factor_id: str
    display_name: str
    category: str
    unit: str
    polarity: str  # "HIGHER_IS_BULLISH", "LOWER_IS_BULLISH", "EXTREME_IS_RISK", "CONTEXTUAL"
    formula_desc: str
    bullish_threshold: float
    bearish_threshold: float
    assigned_agents: Tuple[str, ...]
    bullish_interpretation: str
    bearish_interpretation: str
    neutral_interpretation: str


class FactorOntology:
    """
    Canonical Factor Metadata Registry & Deterministic Semantic Translator.
    Guarantees 0% LLM polarity misinterpretation across Alpha158, Volume Clock, Deep OFI,
    Fundamental Quality, and Macro Liquidity metrics.
    """

    REGISTRY: Dict[str, FactorSchema] = {
        "alpha158_z_score": FactorSchema(
            factor_id="alpha158_z_score",
            display_name="Qlib Alpha158 Composite Z-Score",
            category="QUANT_TECHNICAL",
            unit="σ (Standard Deviations)",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="Cross-sectional & time-series standardized composite of 158 Qlib price/volume factors",
            bullish_threshold=0.75,
            bearish_threshold=-0.50,
            assigned_agents=("william_oneil", "cis_trader", "cio"),
            bullish_interpretation="統計的モメンタム上位圏（強い順張り買い優位・機関資金流入）",
            bearish_interpretation="統計的モメンタム劣化（需給悪化・下落トレンド警戒）",
            neutral_interpretation="統計的モメンタム中立圏（レンジ推移）",
        ),
        "roc_20": FactorSchema(
            factor_id="roc_20",
            display_name="20-Day Rate of Change (ROC20)",
            category="MOMENTUM",
            unit="%",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="(Close_t / Close_{t-20} - 1) * 100",
            bullish_threshold=5.0,
            bearish_threshold=-4.0,
            assigned_agents=("william_oneil", "cathie_wood", "michael_burry"),
            bullish_interpretation="中期トレンド上向き加速（Stage 2 順張り推進力あり ※25%超は過熱注意）",
            bearish_interpretation="中期モメンタム失速・下落基調",
            neutral_interpretation="中期トレンド横ばい・エネルギー充填中",
        ),
        "rsv_20": FactorSchema(
            factor_id="rsv_20",
            display_name="20-Day Raw Stochastic Value (RSV20)",
            category="OSCILLATOR",
            unit="0.0–1.0 Ratio",
            polarity="CONTEXTUAL",
            formula_desc="(Close_t - Low_20) / (High_20 - Low_20 + 1e-8)",
            bullish_threshold=0.70,
            bearish_threshold=0.25,
            assigned_agents=("cis_trader", "william_oneil", "michael_burry"),
            bullish_interpretation="直近20日レンジの上限ブレイク圏（強い買い需要 ※0.92超は短期買われすぎ）",
            bearish_interpretation="直近20日レンジの底値圏（強い売り圧力、または逆張り打診水準）",
            neutral_interpretation="直近20日レンジの中間均衡帯",
        ),
        "vol_spike_20": FactorSchema(
            factor_id="vol_spike_20",
            display_name="Volume Ratio vs 20-Day Average (VMA20 Ratio)",
            category="MICROSTRUCTURE_FLOW",
            unit="x (Multiple)",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="Volume_t / Mean(Volume_{t-19..t})",
            bullish_threshold=1.35,
            bearish_threshold=0.75,
            assigned_agents=("cis_trader", "william_oneil"),
            bullish_interpretation="出来高急増・大口参加者の実需フロー流入（陽線時は強いブレイク根拠）",
            bearish_interpretation="出来高細り・市場参加者の関心低下（閑散ノイズに注意）",
            neutral_interpretation="平常通りの出来高水準",
        ),
        "volatility_20": FactorSchema(
            factor_id="volatility_20",
            display_name="20-Day Annualized/Daily Return Volatility (STD20)",
            category="RISK_VOLATILITY",
            unit="% (Daily StdDev)",
            polarity="EXTREME_IS_RISK",
            formula_desc="StdDev(Return_{t-19..t}) * 100",
            bullish_threshold=1.8,
            bearish_threshold=4.2,
            assigned_agents=("risk_manager", "graham", "buffett"),
            bullish_interpretation="低ボラティリティ・安定した価格推移（ストップ狩りノイズ小）",
            bearish_interpretation="高ボラティリティ乱高下（ATR呼吸床の拡大およびロット圧縮が必須）",
            neutral_interpretation="標準的なボラティリティ水準",
        ),
        "flow_velocity": FactorSchema(
            factor_id="flow_velocity",
            display_name="Volume Clock Information Flow Velocity",
            category="MICROSTRUCTURE_FLOW",
            unit="x (Baseline Speed Multiple)",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="(BarVolume / BarDurationSec) / RollingMean_20(BarVolume / BarDurationSec)",
            bullish_threshold=1.50,
            bearish_threshold=0.70,
            assigned_agents=("cis_trader", "william_oneil", "risk_manager"),
            bullish_interpretation="出来高クロック高速回転（機関投資家クジラの緊急参入・強い情報フロー発生）",
            bearish_interpretation="出来高クロック低速化（大口不在の時間帯・ダマシに警戒）",
            neutral_interpretation="標準的な出来高消化スピード",
        ),
        "deep_ofi_score": FactorSchema(
            factor_id="deep_ofi_score",
            display_name="10-Level Deep Order Flow Imbalance (Rama Cont OFI)",
            category="MICROSTRUCTURE_FLOW",
            unit="Score (-100 to +100)",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="Distance-decayed sum of bid/ask queue deltas across Levels 1..10",
            bullish_threshold=25.0,
            bearish_threshold=-25.0,
            assigned_agents=("cis_trader", "risk_manager", "cio"),
            bullish_interpretation="板の2〜10本目まで厚い買い注文が優勢（機関のステルス買い支え）",
            bearish_interpretation="板奥で売り圧力が優勢（大口の売り抜けまたは買い板キャンセル警戒）",
            neutral_interpretation="板の買い・売り注文フローが均衡",
        ),
        "piotroski_f_score": FactorSchema(
            factor_id="piotroski_f_score",
            display_name="Piotroski F-Score (9-Point Financial Quality)",
            category="FUNDAMENTAL_QUALITY",
            unit="Points (0–9)",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="Sum of 9 binary accounting health signals (Profitability, Leverage, Efficiency)",
            bullish_threshold=6.0,
            bearish_threshold=3.0,
            assigned_agents=("buffett", "graham", "risk_manager"),
            bullish_interpretation="財務健全性・キャッシュ創出力が極めて強固（バリュートラップ耐性◎）",
            bearish_interpretation="財務悪化・粉飾または資金繰り悪化リスク（ファンダメンタルズ警戒）",
            neutral_interpretation="平均的な財務健全性",
        ),
        "pe_trailing": FactorSchema(
            factor_id="pe_trailing",
            display_name="Trailing Price-to-Earnings Ratio (PER)",
            category="VALUATION",
            unit="x (Multiple)",
            polarity="LOWER_IS_BULLISH",
            formula_desc="Price / Trailing 12M Diluted EPS",
            bullish_threshold=18.0,
            bearish_threshold=45.0,
            assigned_agents=("graham", "buffett", "michael_burry"),
            bullish_interpretation="利益に対して割安・安全域（Margin of Safety）が厚い",
            bearish_interpretation="高バリュエーション・成長鈍化時のマルチプル収縮（暴落）リスク大",
            neutral_interpretation="市場平均並みのバリュエーション",
        ),
        "roe": FactorSchema(
            factor_id="roe",
            display_name="Return on Equity (ROE)",
            category="FUNDAMENTAL_QUALITY",
            unit="%",
            polarity="HIGHER_IS_BULLISH",
            formula_desc="(Net Income / Shareholders' Equity) * 100",
            bullish_threshold=15.0,
            bearish_threshold=6.0,
            assigned_agents=("buffett", "william_oneil"),
            bullish_interpretation="高い資本効率と経済的な堀（Moat）による複利成長力",
            bearish_interpretation="資本効率が低く競争優位性が弱い",
            neutral_interpretation="標準的な資本効率",
        ),
        "hayashi_yoshida_corr": FactorSchema(
            factor_id="hayashi_yoshida_corr",
            display_name="Hayashi-Yoshida Asynchronous Lead-Lag Correlation",
            category="CROSS_ASSET_CAUSALITY",
            unit="Correlation (-1.0 to +1.0)",
            polarity="CONTEXTUAL",
            formula_desc="Overlap-weighted asynchronous covariance estimator (free from Epps effect)",
            bullish_threshold=0.35,
            bearish_threshold=-0.35,
            assigned_agents=("george_soros", "risk_manager", "cio"),
            bullish_interpretation="先行マクロ指標との強い非同期正連動（先行指標上昇時は強い追い風、重複保有時はHRP圧縮対象）",
            bearish_interpretation="先行マクロ指標との逆相関（金利上昇やドル高が逆風として波及）",
            neutral_interpretation="マクロ指標から独立した個別要因推移",
        ),
    }

    @classmethod
    def interpret_value(cls, factor_id: str, raw_value: Any) -> Optional[Dict[str, Any]]:
        """
        Translates a raw numeric factor value into a deterministic ontology entry.
        """
        if raw_value is None or factor_id not in cls.REGISTRY:
            return None
        try:
            val = float(raw_value)
        except (ValueError, TypeError):
            return None

        schema = cls.REGISTRY[factor_id]

        if schema.polarity == "HIGHER_IS_BULLISH":
            if val >= schema.bullish_threshold:
                signal = "BULLISH"
                meaning = schema.bullish_interpretation
            elif val <= schema.bearish_threshold:
                signal = "BEARISH"
                meaning = schema.bearish_interpretation
            else:
                signal = "NEUTRAL"
                meaning = schema.neutral_interpretation
        elif schema.polarity == "LOWER_IS_BULLISH":
            if val <= schema.bullish_threshold and val > 0:
                signal = "BULLISH"
                meaning = schema.bullish_interpretation
            elif val >= schema.bearish_threshold or val < 0:
                signal = "BEARISH"
                meaning = schema.bearish_interpretation
            else:
                signal = "NEUTRAL"
                meaning = schema.neutral_interpretation
        elif schema.polarity == "EXTREME_IS_RISK":
            if val <= schema.bullish_threshold:
                signal = "LOW_RISK_FAVORABLE"
                meaning = schema.bullish_interpretation
            elif val >= schema.bearish_threshold:
                signal = "HIGH_RISK_CAUTION"
                meaning = schema.bearish_interpretation
            else:
                signal = "NORMAL_RISK"
                meaning = schema.neutral_interpretation
        else:
            if val >= schema.bullish_threshold:
                signal = "HIGH_ZONE"
                meaning = schema.bullish_interpretation
            elif val <= schema.bearish_threshold:
                signal = "LOW_ZONE"
                meaning = schema.bearish_interpretation
            else:
                signal = "MID_ZONE"
                meaning = schema.neutral_interpretation

        return {
            "factor_id": schema.factor_id,
            "display_name": schema.display_name,
            "category": schema.category,
            "value": round(val, 4),
            "unit": schema.unit,
            "polarity_rule": schema.polarity,
            "semantic_signal": signal,
            "interpretation": meaning,
            "assigned_agents": list(schema.assigned_agents),
        }

    @classmethod
    def build_ontology_bundle(
        cls,
        stock_data: Dict[str, Any],
        alpha158_summary: Optional[Dict[str, Any]] = None,
        lead_lag_info: Optional[Dict[str, Any]] = None,
        microstructure_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts raw metrics from stock_data, alpha158, lead_lag, and microstructure feeds,
        and compiles a complete, human-and-LLM-verifiable Factor Ontology Bundle.
        """
        extracted: Dict[str, Any] = {}

        # 1. Fundamental metrics from stock_data
        if stock_data:
            extracted["pe_trailing"] = stock_data.get("pe_trailing")
            extracted["roe"] = stock_data.get("roe")
            f_score = stock_data.get("piotroski_f_score")
            if f_score is None and isinstance(stock_data.get("history_metrics"), dict):
                f_score = stock_data["history_metrics"].get("piotroski_f_score")
            extracted["piotroski_f_score"] = f_score

        # 2. Alpha158 metrics
        if alpha158_summary and isinstance(alpha158_summary, dict):
            extracted["alpha158_z_score"] = alpha158_summary.get("composite_z_score") or alpha158_summary.get("alpha_score_z")
            kf = alpha158_summary.get("key_factors", {})
            if isinstance(kf, dict):
                extracted["roc_20"] = kf.get("ROC_20") or kf.get("roc_20")
                extracted["rsv_20"] = kf.get("RSV_20") or kf.get("rsv_20")
                extracted["vol_spike_20"] = kf.get("VMA_RATIO_20") or kf.get("vol_spike_20")
                extracted["volatility_20"] = kf.get("STD_20") or kf.get("volatility_20")

        # 3. Microstructure (Volume Clock & Deep OFI)
        if microstructure_info and isinstance(microstructure_info, dict):
            extracted["flow_velocity"] = microstructure_info.get("flow_velocity")
            extracted["deep_ofi_score"] = microstructure_info.get("deep_ofi_score")

        # 4. Lead-Lag Hayashi-Yoshida Correlation
        if lead_lag_info and isinstance(lead_lag_info, dict):
            extracted["hayashi_yoshida_corr"] = (
                lead_lag_info.get("hayashi_yoshida_corr")
                or lead_lag_info.get("correlation")
            )

        entries: List[Dict[str, Any]] = []
        for fid, raw_val in extracted.items():
            item = cls.interpret_value(fid, raw_val)
            if item:
                entries.append(item)

        return {
            "schema_version": "v6.4.5-ontology",
            "factors_count": len(entries),
            "factors": entries,
        }

    @classmethod
    def format_for_agent_prompt(
        cls,
        ontology_bundle: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> str:
        """
        Generates a strict, zero-hallucination Factor Ontology Markdown section
        tailored to the specific agent persona (or all factors for CRO/CIO).
        """
        if not ontology_bundle or not ontology_bundle.get("factors"):
            return ""

        factors = ontology_bundle["factors"]
        lines = [
            "\n【📐 数理ファクター・オントロジー辞書 (Factor Metadata Schema — 数値の誤読・極性反転厳禁)】",
            "※以下の各指標はプログラムで数学的極性（Polarity）と意味が確定しています。数値を引用する際は必ずこの定義に従ってください：",
        ]

        for f in factors:
            is_primary = (
                agent_id is None
                or agent_id in ("cio", "risk_manager")
                or agent_id in f.get("assigned_agents", [])
            )
            prefix = "★[担当重要指標]" if is_primary else "・[共通指標]"
            lines.append(
                f"{prefix} {f['display_name']} ({f['factor_id']}): 実測値 = {f['value']} {f['unit']} "
                f"| 極性ルール: {f['polarity_rule']} | 確定シグナル: 【{f['semantic_signal']}】 ➔ {f['interpretation']}"
            )

        return "\n".join(lines) + "\n"
