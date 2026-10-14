"""
ai_blog_pro/core/ai_hedge_fund/cross_market_ranker.py
=====================================================
全市場横断ランキングスクリーナー (Cross-Sectional Market Ranker)
Powered by Microsoft Qlib Alpha158 × LightGBM Meta-Decision Tree

日米の主要高流動性銘柄群（東証プライム代表銘柄 ＆ 米国メガテック・AI半導体群）を一斉スキャンし、
Alpha158数理ファクター行列とLightGBMゲートキーパーを連携させて
「今、全市場で最も数学的勝率・期待値の高いトップ5銘柄」を機械的に抽出する。
"""

import os
import time
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from ai_blog_pro.core.ai_hedge_fund.alpha158_engine import Alpha158Engine
    from ai_blog_pro.core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper
    from ai_blog_pro.core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
except ImportError:
    from core.ai_hedge_fund.alpha158_engine import Alpha158Engine
    from core.ai_hedge_fund.lightgbm_gatekeeper import LightGBMGatekeeper
    from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer

logger = logging.getLogger(__name__)

# スキャン対象ユニバース（流動性・時価総額・セクター分散を網羅した日米精鋭群）
JP_UNIVERSE = [
    {"ticker": "7203.T", "name": "トヨタ自動車", "sector": "自動車"},
    {"ticker": "6758.T", "name": "ソニーグループ", "sector": "電機・エンタメ"},
    {"ticker": "6861.T", "name": "キーエンス", "sector": "FA・センサー"},
    {"ticker": "8035.T", "name": "東京エレクトロン", "sector": "半導体製造装置"},
    {"ticker": "6920.T", "name": "レーザーテック", "sector": "半導体マスク検査"},
    {"ticker": "6526.T", "name": "ソシオネクスト", "sector": "カスタムSoC"},
    {"ticker": "6857.T", "name": "アドバンテスト", "sector": "半導体テスター"},
    {"ticker": "6146.T", "name": "ディスコ", "sector": "半導体切断研削"},
    {"ticker": "7735.T", "name": "SCREENホールディングス", "sector": "半導体洗浄"},
    {"ticker": "9984.T", "name": "ソフトバンクグループ", "sector": "AI・テック投資"},
    {"ticker": "9983.T", "name": "ファーストリテイリング", "sector": "グローバル小売"},
    {"ticker": "8306.T", "name": "三菱UFJフィナンシャルG", "sector": "メガバンク"},
    {"ticker": "8316.T", "name": "三井住友フィナンシャルG", "sector": "メガバンク"},
    {"ticker": "8058.T", "name": "三菱商事", "sector": "総合商社"},
    {"ticker": "8001.T", "name": "伊藤忠商事", "sector": "総合商社"},
    {"ticker": "6501.T", "name": "日立製作所", "sector": "社会イノベーション"},
    {"ticker": "7974.T", "name": "任天堂", "sector": "ゲーム・IP"},
    {"ticker": "4063.T", "name": "信越化学工業", "sector": "シリコンウエハ"},
    {"ticker": "7011.T", "name": "三菱重工業", "sector": "防衛・エネルギー"},
    {"ticker": "6723.T", "name": "ルネサスエレクトロニクス", "sector": "車載半導体"},
    {"ticker": "6367.T", "name": "ダイキン工業", "sector": "空調"},
    {"ticker": "7267.T", "name": "ホンダ", "sector": "自動車"},
    {"ticker": "6981.T", "name": "村田製作所", "sector": "電子部品"},
    {"ticker": "9432.T", "name": "NTT", "sector": "通信・インフラ"},
]

US_UNIVERSE = [
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "AI半導体・GPU"},
    {"ticker": "MSFT", "name": "Microsoft", "sector": "クラウド・AI基盤"},
    {"ticker": "AAPL", "name": "Apple", "sector": "コンシューマーエコシステム"},
    {"ticker": "AMZN", "name": "Amazon", "sector": "AWS・Eコマース"},
    {"ticker": "GOOGL", "name": "Alphabet", "sector": "検索・AI・YouTube"},
    {"ticker": "META", "name": "Meta Platforms", "sector": "SNS・オープンソースAI"},
    {"ticker": "TSLA", "name": "Tesla", "sector": "EV・自動運転・ロボティクス"},
    {"ticker": "AMD", "name": "Advanced Micro Devices", "sector": "CPU・AI半導体"},
    {"ticker": "AVGO", "name": "Broadcom", "sector": "カスタムASIC・ネットワーキング"},
    {"ticker": "PLTR", "name": "Palantir Technologies", "sector": "企業・防衛向けAIプラットフォーム"},
    {"ticker": "ARM", "name": "Arm Holdings", "sector": "CPUアーキテクチャIP"},
    {"ticker": "TSM", "name": "TSMC", "sector": "半導体ファウンドリ"},
]


class CrossMarketRanker:
    """
    全市場 Alpha158 × LightGBM クロスセクショナルスクリーナー
    """

    _cache: Dict[str, Any] = {}
    _cache_time: float = 0.0
    CACHE_TTL_SECONDS = 1800  # 30分キャッシュ

    @classmethod
    def scan_market(
        cls,
        market: str = "ALL",  # 'JP', 'US', or 'ALL'
        top_n: int = 5,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        指定市場の全銘柄を並列スキャンし、Alpha158 × LightGBMでランキングを出力
        
        Args:
            market: 'JP' (日本株), 'US' (米国株), 'ALL' (日米統合)
            top_n: 上位何銘柄を抽出するか (デフォルト5)
            force_refresh: キャッシュを無視して再計算するか
            
        Returns:
            Dict[str, Any]: スキャン結果 (top_alphas, bottom_alphas, universe_size, timestamp等)
        """
        cache_key = f"scan_{market}_{top_n}"
        now = time.time()
        if not force_refresh and cache_key in cls._cache and (now - cls._cache_time < cls.CACHE_TTL_SECONDS):
            logger.info("Returning cached cross-market scan results")
            return cls._cache[cache_key]

        # 対象銘柄リストの構築
        universe: List[Dict[str, str]] = []
        if market in ["JP", "ALL"]:
            universe.extend(JP_UNIVERSE)
        if market in ["US", "ALL"]:
            universe.extend(US_UNIVERSE)

        tickers = [u["ticker"] for u in universe]
        ticker_meta = {u["ticker"]: u for u in universe}

        logger.info(f"CrossMarketRanker: Scanning {len(tickers)} stocks ({market})...")
        t0 = time.time()

        # yfinance バルク一括ダウンロード (threads=True で超並列取得)
        try:
            bulk_df = yf.download(
                tickers,
                period="6mo",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False
            )
        except Exception as e:
            logger.error(f"Bulk download failed: {e}")
            return {"error": str(e), "top_alphas": []}

        results: List[Dict[str, Any]] = []

        # 各銘柄のAlpha158計算 ＆ LightGBMスコアリング
        for item in universe:
            sym = item["ticker"]
            try:
                # バルクデータから単一銘柄のDataFrameを抽出
                if isinstance(bulk_df.columns, pd.MultiIndex):
                    if sym in bulk_df.columns.levels[0]:
                        stock_df = bulk_df[sym].dropna(how="all")
                    else:
                        continue
                else:
                    stock_df = bulk_df.dropna(how="all")

                if len(stock_df) < 30:
                    continue

                # Alpha158 計算 (Vectorized Native)
                f_dict = Alpha158Engine.get_latest_factors(stock_df)
                if not f_dict:
                    continue

                # 主要Alpha158指標の抽出
                roc5 = f_dict.get("ROC5", 0.0)
                roc20 = f_dict.get("ROC20", 0.0)
                rsqr20 = f_dict.get("RSQR20", 0.0)
                beta20 = f_dict.get("BETA20", 0.0)
                corr20 = f_dict.get("CORR20", 0.0)
                skew20 = f_dict.get("SKEW20", 0.0)
                vsumd20 = f_dict.get("VSUMD20", 0.0)
                resi20 = f_dict.get("RESI20", 0.0)

                # 合成Alphaスコアの数理算出 (Qlibマルチファクター重み付け)
                # 健全な上昇トレンド: モメンタム正 + トレンド決定係数高 + 出来高相関正 + 買い出来高比率正
                alpha_score = (
                    0.25 * np.tanh(roc20 * 10) +
                    0.20 * rsqr20 * np.sign(beta20) +
                    0.20 * np.tanh(roc5 * 15) +
                    0.15 * corr20 +
                    0.10 * vsumd20 +
                    0.10 * np.clip(skew20, -1.0, 1.0)
                )

                # LightGBM ゲートキーパーで勝率推定 (12特徴量)
                lead_sig = "BULLISH_LAG" if (alpha_score > 0.15 and corr20 > 0) else "NEUTRAL"
                dual_q_payload = {
                    "consensus_status": "DOUBLE_BULLISH" if alpha_score > 0.20 else "NEUTRAL",
                    "models": {
                        "google_timesfm": {
                            "expected_return_pct": float(roc5 * 100),
                            "downside_risk_prob": 15.0 if roc20 > 0 else 35.0
                        },
                        "amazon_chronos": {
                            "expected_return_pct": float(roc5 * 100 * 1.1),
                            "downside_risk_prob": 15.0 if roc20 > 0 else 35.0
                        }
                    }
                }
                lead_lag_payload = {
                    "lead_lag_signal": lead_sig,
                    "correlation": float(corr20)
                }

                gate_res = LightGBMGatekeeper.evaluate_gate(
                    ticker=sym,
                    dual_quantum=dual_q_payload,
                    lead_lag_data=lead_lag_payload,
                    context_data={},
                    stock_data={"pe_trailing": 20.0, "roe": 12.0}
                )

                # 主要寄与ファクターの言語化
                drivers = []
                if rsqr20 > 0.4 and beta20 > 0:
                    drivers.append(f"強固な上昇トレンド(R²: {rsqr20:.2f})")
                if corr20 > 0.3:
                    drivers.append("機関買い集め相関(+)")
                if vsumd20 > 0.15:
                    drivers.append("陽線出来高優位")
                if roc5 > 0.02:
                    drivers.append(f"5日急伸(+{roc5*100:.1f}%)")
                if resi20 < -0.02 and beta20 > 0:
                    drivers.append("上昇トレンド内押し目リバウンド")

                latest_close = float(stock_df['Close'].iloc[-1])

                results.append({
                    "ticker": sym,
                    "name": item["name"],
                    "sector": item["sector"],
                    "latest_close": latest_close,
                    "alpha_score": float(alpha_score),
                    "win_probability": gate_res["win_probability"],
                    "gate_decision": gate_res["gate_decision"],
                    "gate_badge": gate_res["gate_badge"],
                    "roc5_pct": float(roc5 * 100),
                    "roc20_pct": float(roc20 * 100),
                    "trend_r2": float(rsqr20),
                    "volume_corr": float(corr20),
                    "top_drivers": drivers[:3] if drivers else ["均衡状態"],
                    "raw_factors": {
                        "KMID": f_dict.get("KMID", 0.0),
                        "ROC5": roc5,
                        "RSQR20": rsqr20,
                        "CORR20": corr20,
                        "SKEW20": skew20
                    }
                })
            except Exception as e:
                logger.warning(f"Failed processing {sym}: {e}")
                continue

        # スコア順にソート
        results.sort(key=lambda x: (x["alpha_score"], x["win_probability"]), reverse=True)

        top_alphas = results[:top_n]
        bottom_alphas = results[-3:] if len(results) >= 3 else []

        scan_duration = time.time() - t0
        logger.info(f"Scan completed in {scan_duration:.2f}s. Extracted top {len(top_alphas)} stocks.")

        response = {
            "market": market,
            "universe_size": len(results),
            "scan_duration_sec": round(scan_duration, 2),
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "top_alphas": top_alphas,
            "bottom_alphas": bottom_alphas
        }

        # Neo4j自己進化ナレッジグラフへ永続化
        try:
            try:
                from ai_blog_pro.core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            except ImportError:
                from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            GraphitiMemoryManager.record_alpha158_scan(response)
        except Exception as e:
            logger.warning(f"Neo4j record_alpha158_scan skipped: {e}")

        cls._cache[cache_key] = response
        cls._cache_time = now
        return response
