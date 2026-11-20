# -*- coding: utf-8 -*-
"""
dual_quantum_forecaster.py - Google TimesFM × Amazon Chronos 二刀流アンサンブル確率予測エンジン
世界最高峰の2大時系列基盤モデル（Google TimesFM ＆ Amazon Chronos）を同時に実行し、
両モデルの予測確率分布を重ね合わせることで「ダマシ（False Signals）」を排除するコンセンサス判定器。
"""

from typing import Dict, Any, List, Optional
from core.ai_hedge_fund.timesfm_forecaster import TimesFMForecaster
from core.ai_hedge_fund.chronos_forecaster import ChronosForecaster


class DualQuantumForecaster:
    """
    Google TimesFM × Amazon Chronos 統合数理アンサンブル
    """

    @classmethod
    def forecast(cls, ticker: str, horizon_days: int = 5) -> Dict[str, Any]:
        """
        Google TimesFM と Amazon Chronos の両方を実行し、合意シグナルを生成
        """
        # 1. 2大モデルの並行/順次推論
        timesfm_res = TimesFMForecaster.forecast_stock(ticker, horizon_days=horizon_days)
        chronos_res = ChronosForecaster.forecast_stock(ticker, horizon_days=horizon_days)

        tfm_ret = timesfm_res.get("expected_return_pct", 0.0)
        chr_ret = chronos_res.get("expected_return_pct", 0.0)

        tfm_down = timesfm_res.get("downside_risk_prob", 15.0)
        chr_down = chronos_res.get("downside_risk_prob", 15.0)

        tfm_up = timesfm_res.get("upside_breakout_prob", 15.0)
        chr_up = chronos_res.get("upside_breakout_prob", 15.0)

        tfm_backend = str(timesfm_res.get("backend") or "parametric_log_return_fallback")
        chr_backend = str(chronos_res.get("backend") or ("amazon/chronos-bolt-small" if chronos_res.get("status") == "SUCCESS_NEURAL" else "parametric_autoregressive_fallback"))
        tfm_is_native = tfm_backend not in ("unavailable", "parametric_log_return_fallback")
        chr_is_native = (chronos_res.get("status") == "SUCCESS_NEURAL") or ("chronos" in chr_backend and "fallback" not in chr_backend)
        is_foundation_ensemble = bool(tfm_is_native and chr_is_native)

        model_a_label = "Google TimesFM" if tfm_is_native else "モメンタム対数正規近似 (TimesFM未導入)"
        model_b_label = "Amazon Chronos" if chr_is_native else "自己回帰分位近似 (Chronos未導入)"
        pair_label = "Google TimesFM と Amazon Chronos の双方" if is_foundation_ensemble else f"2系統のパラメトリック時系列近似（{model_a_label} / {model_b_label}）"

        # 2. コンセンサス状態の数学的判定
        # 閾値: 上昇+1.5%以上, 下落-1.5%以下
        both_bull = (tfm_ret >= 1.5) and (chr_ret >= 1.5)
        both_bear = (tfm_ret <= -1.5) and (chr_ret <= -1.5)
        conflict = (tfm_ret * chr_ret < -1.0) # 符号が逆で乖離大

        if both_bull:
            consensus_status = "DOUBLE_BULLISH" # 🚀 両者揃って強気一致
            consensus_badge = (
                "🚀 DOUBLE BULLISH (Google×Amazon 確率合意)"
                if is_foundation_ensemble
                else "📈 DOUBLE BULLISH (パラメトリック近似合意 — 基盤モデル未導入)"
            )
            summary_desc = (
                "Google TimesFM と Amazon Chronos の双方が上昇予測で完全合意。最高ランクの確信シグナル。"
                if is_foundation_ensemble
                else f"{pair_label}が上昇方向で一致（※基盤モデル未導入のため統計近似推論）。"
            )
        elif both_bear:
            consensus_status = "DOUBLE_BEARISH" # ⚠️ 両者揃って急落警戒一致
            consensus_badge = (
                "⚠️ DOUBLE BEARISH (急落警戒合意)"
                if is_foundation_ensemble
                else "⚠️ DOUBLE BEARISH (パラメトリック近似・下落警戒)"
            )
            summary_desc = (
                "両時系列基盤モデルが下落リスクで一致。買いエントリーの厳格見送りを推奨。"
                if is_foundation_ensemble
                else f"{pair_label}が下落リスクで一致（※統計近似推論）。買いエントリー見送りを推奨。"
            )
        elif conflict:
            consensus_status = "DISAGREEMENT" # ⚔️ モデル間で予測乖離・対立
            consensus_badge = "⚔️ MODEL CONFLICT (数理予測の対立)"
            summary_desc = f"{model_a_label} ({tfm_ret:+.2f}%) と {model_b_label} ({chr_ret:+.2f}%) で方向性が乖離。ボラティリティ急変に警戒。"
        else:
            consensus_status = "NEUTRAL"
            consensus_badge = (
                "⚖️ QUANTUM NEUTRAL (レンジ推移)"
                if is_foundation_ensemble
                else "⚖️ APPROXIMATION NEUTRAL (パラメトリック近似・レンジ推移)"
            )
            summary_desc = f"{pair_label}ともに小幅レンジ内の推移を予測。トレンド発生待ち。"

        # 3. アンサンブル合成値（加重平均）
        ensemble_expected_ret = round((tfm_ret * 0.5 + chr_ret * 0.5), 2)
        curr_price = timesfm_res.get("current_price") or chronos_res.get("current_price", 0.0)
        ensemble_median_price = round(curr_price * (1.0 + ensemble_expected_ret / 100.0), 2)
        
        # 信頼区間の重ね合わせ（より安全な最外殻または平均帯）
        ensemble_lower_80 = round(min(timesfm_res.get("lower_bound_80", curr_price), chronos_res.get("lower_bound_80", curr_price)), 2)
        ensemble_upper_80 = round(max(timesfm_res.get("upper_bound_80", curr_price), chronos_res.get("upper_bound_80", curr_price)), 2)

        # 総合確信度スコア (不一致時はペナルティ)
        base_conf = (timesfm_res.get("confidence_score", 50) + chronos_res.get("confidence_score", 50)) / 2.0
        if consensus_status == "DOUBLE_BULLISH" or consensus_status == "DOUBLE_BEARISH":
            final_conf = min(98, int(base_conf + 12))
        elif consensus_status == "DISAGREEMENT":
            final_conf = max(35, int(base_conf - 20))
        else:
            final_conf = int(base_conf)

        return {
            "ticker": ticker,
            "horizon_days": horizon_days,
            "target_date": timesfm_res.get("target_date"),
            "current_price": curr_price,
            "consensus_status": consensus_status,
            "consensus_badge": consensus_badge,
            "is_foundation_ensemble": is_foundation_ensemble,
            "backends": {
                "google_timesfm": tfm_backend,
                "amazon_chronos": chr_backend,
            },
            "confidence_score": final_conf,
            "ensemble_expected_return_pct": ensemble_expected_ret,
            "ensemble_median_price": ensemble_median_price,
            "ensemble_lower_80": ensemble_lower_80,
            "ensemble_upper_80": ensemble_upper_80,
            "avg_downside_risk_prob": round((tfm_down + chr_down) / 2.0, 1),
            "avg_upside_breakout_prob": round((tfm_up + chr_up) / 2.0, 1),
            "summary_desc": summary_desc,
            "models": {
                "google_timesfm": timesfm_res,
                "amazon_chronos": chronos_res
            }
        }
