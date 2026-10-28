# -*- coding: utf-8 -*-
import time
import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf
from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.hedge_fund_council import HedgeFundCouncil
from core.ai_hedge_fund.market_screener import MarketScreener
from core.ai_hedge_fund.broker_client import PaperTradingEngine
from core.ai_hedge_fund.hedge_fund_notifier import HedgeFundNotifier
from core.ai_hedge_fund.market_session import MarketSession
from core.ai_hedge_fund.macro_liquidity_feed import MacroLiquidityFeed
from core.ai_hedge_fund.options_gex_feed import OptionsGexFeed
from core.ai_hedge_fund.concurrency_controller import ConcurrencyController
from core.ai_hedge_fund.volume_clock_sampler import VolumeClockSampler
from core.ai_hedge_fund.rust_sentinel_bridge import RustSentinelBridge

class AutoTrader:
    """
    Lumina AI Autonomous Trading Engine
    Executes end-to-end full-auto algorithmic trading:
    1. Scans market for top opportunities via MarketScreener.
    2. Convenes multi-agent debate (Buffett, Graham, Cathie Wood, Risk Manager) for top picks.
    3. Automatically executes BUY orders for high-confidence BUY verdicts.
    4. Patrols existing portfolio positions and automatically triggers Take-Profit / Stop-Loss.
    """

    _examined_cooldowns: Dict[str, float] = {}
    _time_barrier_cooldowns: Dict[str, float] = {}  # 14-day (1,209,600s) anti-churn lock after TIME_BARRIER_ROTATION / STOP_LOSS
    TIME_BARRIER_COOLDOWN_SEC: float = 14.0 * 86400.0
    _prices_cache: Dict[str, Tuple[float, pd.Series]] = {}
    PRICES_CACHE_TTL: float = 1800.0  # 30-min price history cache
    _swing_ofi_gate_retries: Dict[str, int] = {}

    @classmethod
    def hydrate_cooldowns_from_db(cls, broker_engine: PaperTradingEngine) -> int:
        """
        Rehydrate 14-day anti-churn cooldowns (`_time_barrier_cooldowns`) from SQLite `trade_memories`
        upon process startup or crash recovery (`kill -9` / `systemctl restart`), ensuring zero state loss.
        """
        restored = 0
        now_ts = time.time()
        try:
            memories = broker_engine.get_trade_memories(limit=100)
            for m in memories:
                rule = str(m.get("trigger_rule") or "")
                sym = str(m.get("symbol") or "")
                created_str = str(m.get("created_at") or "")
                if sym and rule in ("TIME_BARRIER_ROTATION", "FIBONACCI_STOP_LOSS", "DAY_CIS_STOP") and created_str:
                    try:
                        dt = datetime.datetime.strptime(created_str[:19], "%Y-%m-%d %H:%M:%S")
                        exit_ts = dt.timestamp()
                        if (now_ts - exit_ts) < cls.TIME_BARRIER_COOLDOWN_SEC:
                            if sym not in cls._time_barrier_cooldowns or exit_ts > cls._time_barrier_cooldowns[sym]:
                                cls._time_barrier_cooldowns[sym] = exit_ts
                                restored += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return restored

    @classmethod
    def evaluate_swing_ofi_execution_gate(
        cls,
        symbol: str,
        broker_engine: Any,
        symbol_name: str,
        now_str: str,
        logs: List[str]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        深層板情報 (Deep OFI: 1〜10本目) ＆ 出来高クロック (Volume Clock SoA) によるスイングスマート執行ゲートキーパー:
        1. 見せ板だまし（スプーフィング）急キャンセル、猛烈な売り抜け (OFI <= -45)、または出来高クロックでの大口売り浴びせ（陰線かつ流速 >= 1.8x）を検知した場合は発注を一時待機 (最大2回保留)。
        2. 大口アイスバーグ注文 (ステルス買い集め)、買い優勢 (OFI >= +30)、または出来高クロックでのクジラ買い加速（陽線かつ流速 >= 1.5x）を検知した場合は最安値スナイパー約定。
        3. 通常時はそのまま執行。
        """
        try:
            ob = broker_engine.get_order_book(symbol, depth=10)
        except Exception:
            ob = {}

        ofi = dict(ob.get("ofi_analysis", {}) if ob else {})
        is_spoof_trap = ofi.get("is_spoof_buy_wall", False)
        deep_ofi = ofi.get("deep_ofi_score", 0.0)
        is_iceberg = ofi.get("is_iceberg_accumulation", False)

        # ⚡ SoA 出来高クロック（Volume Clock）流速テレメトリの取得
        flow_vel = 1.0
        is_vc_bullish = True
        try:
            df_intraday = yf.download(symbol, period="5d", interval="5m", progress=False)
            if df_intraday is not None and len(df_intraday) >= 25:
                vol_bars = VolumeClockSampler.to_volume_bars(df_intraday, bars_per_day=32)
                if vol_bars is not None and not vol_bars.empty:
                    flow_vel = float(vol_bars["flow_velocity"].iloc[-1])
                    is_vc_bullish = float(vol_bars["close"].iloc[-1]) >= float(vol_bars["open"].iloc[-1])
        except Exception:
            pass

        ofi["flow_velocity"] = round(flow_vel, 2)
        ofi["is_vc_bullish"] = is_vc_bullish
        # 陰線高流速であっても、板奥でアイスバーグ買い吸収やプラスOFIがある場合は大口の底値吸収（好機）であるため除外
        is_whale_dump = (not is_vc_bullish) and (flow_vel >= 1.85) and (not is_iceberg) and (deep_ofi < 0.0)
        is_whale_surge = is_vc_bullish and (flow_vel >= 1.50)

        retries = cls._swing_ofi_gate_retries.get(symbol, 0)

        # 1. 見せ板トラップ または 出来高クロック大口売り浴びせ（高値掴み・ナイフ掴みリスク）
        if (is_spoof_trap or deep_ofi <= -45.0 or is_whale_dump) and retries < 2:
            cls._swing_ofi_gate_retries[symbol] = retries + 1
            if is_whale_dump:
                reason_detail = f"出来高クロック大口売り流速検知 (流速 {flow_vel:.2f}x 陰線)"
            else:
                reason_detail = ofi.get("spoof_buy_details", {}).get("reason", "強い潜在売り抜け圧力")
            logs.append(
                f"[{now_str}] ⏸️ 【深層OFI×出来高クロック防衛ゲート作動】{symbol_name} ({symbol}) は買い推奨ですが、"
                f"短期需給の悪化を検知（OFI: {deep_ofi:+.1f} / {reason_detail} / 保留 {retries+1}/2回）。"
                f"高値掴み回避のため発注を一時待機します！"
            )
            return False, "DELAY", ofi

        # 安全タイムアウト（2回保留後は強制執行）または通常通過
        if retries >= 2:
            cls._swing_ofi_gate_retries.pop(symbol, None)
            logs.append(
                f"[{now_str}] ⏱️ 【深層OFI安全タイムアウト】{symbol_name} ({symbol}) の2回保留が経過したため、"
                f"機会損失防止として強制執行へ移行します（OFI: {deep_ofi:+.1f} / 流速: {flow_vel:.2f}x）。"
            )
            return True, "TIMEOUT_EXEC", ofi

        cls._swing_ofi_gate_retries.pop(symbol, None)

        # 2. 大口ステルス買い支え または 出来高クロック・クジラ買い流入（最良仕込みタイミング）
        if is_iceberg or deep_ofi >= 30.0 or is_whale_surge:
            logs.append(
                f"[{now_str}] 💎 【深層OFI×出来高クロック好機検知】{symbol_name} ({symbol}) で"
                f"大口の買い流入を確認（OFI: {deep_ofi:+.1f} / 出来高流速: {flow_vel:.2f}x / アイスバーグ: {is_iceberg}）。最良タイミングで約定します！"
            )
            return True, "SNIPER_STEALTH", ofi

        # 3. 通常の安定板
        return True, "NORMAL", ofi

    @classmethod
    def determine_portfolio_capacity(
        cls,
        held_positions: List[Dict[str, Any]],
        total_equity_jpy: float,
        capacity_mode: str = "AUTO"
    ) -> tuple:
        """
        AI動的ポートフォリオ保有枠決定エンジン:
        - AUTO: 5〜6銘柄を市場・資金・日米バランスに合わせて動的に自動切替
        - 5_FIXED: 5銘柄固定 (リターン集中型)
        - 6_FIXED: 6銘柄固定 (リスク分散型)
        - 4_FIXED: 4銘柄固定 (従来基準)
        """
        if capacity_mode == "5_FIXED":
            return 5, "5銘柄固定（リターン集中型）"
        elif capacity_mode == "6_FIXED":
            return 6, "6銘柄固定（リスク分散型）"
        elif capacity_mode == "4_FIXED":
            return 4, "4銘柄固定（従来基準）"

        # AUTO（AI動的おまかせ 5〜6銘柄）判定
        cur_us = sum(1 for p in held_positions if p.get("currency") == "USD")
        cur_jp = sum(1 for p in held_positions if p.get("currency") == "JPY")

        # 1. 日米クロスマーケット共存枠拡張（すれ違い防止）:
        # すでに米国株が3銘柄以上あり、東証が開場した（またはその逆）場合、
        # 相手市場の買付スロットを確保するため上限を6枠へ拡張
        if cur_us >= 3 or cur_jp >= 3:
            return 6, "日米クロスマーケット共存枠拡張（相手国セッション買付スロット確保）"

        # 2. 口座資産の拡大期:
        # 口座総資産が140万円を超えて資金余裕が出た場合は、6枠で高回転・低DD運用
        if total_equity_jpy >= 1400000.0:
            return 6, "口座資産規模拡大による分散拡張（6銘柄・低ドローダウン運用）"

        # 3. 通常時（100万円規模）:
        # 単元株（100株＝20〜30万円）の購入予算を確実に厚く確保し、
        # トップ評価銘柄への集中投資で最高リターン（+125.7%）を狙う5枠モード
        return 5, "集中投資・資金効率最適化（5銘柄・リターン最大化運用）"

    ADAPTIVE_EUROPE_EQUITY_THRESHOLD = 2000000.0  # 200万円: 欧州ADR併用から日米集中特化への自動シフト境界線

    @classmethod
    def get_adaptive_market_mode(
        cls, 
        total_equity_jpy: float, 
        strategy: str = "ALL"
    ) -> tuple:
        """
        AIアダプティブ市場選択エンジン:
        - 口座資産 < 200万円: 日米欧グローバルモード (欧州ADR組入で単元制約を克服・少額高効率運用)
        - 口座資産 >= 200万円: 日米集中特化モード (単元株制約解除 ➔ 日米最強ツートップへ全集中)
        """
        if strategy == "JP_US":
            return "JP_US", False, "ユーザー指定: 日米特化モード（欧州除外）"
        elif strategy == "EUROPE_GLOBAL":
            return "EUROPE_GLOBAL", True, "ユーザー指定: 欧州ADRモード"
        elif strategy in ["AI_GROWTH", "DEFENSE_ENERGY", "VALUE_DIVIDEND", "DEEP_VALUE"]:
            if total_equity_jpy >= cls.ADAPTIVE_EUROPE_EQUITY_THRESHOLD:
                return strategy, False, f"テーマ「{strategy}」（資産 ¥{total_equity_jpy:,.0f} ≧ 200万: 日米集中）"
            else:
                return strategy, True, f"テーマ「{strategy}」（資産 ¥{total_equity_jpy:,.0f} < 200万: 欧州ADR併用）"

        # デフォルト ALL（自動アダプティブ判定）
        if total_equity_jpy >= cls.ADAPTIVE_EUROPE_EQUITY_THRESHOLD:
            return "JP_US", False, f"日米集中特化モード（資産 ¥{total_equity_jpy:,.0f} ≧ 200万円: 単元制約解除・日米最強ツートップ全集中）"
        else:
            return "GLOBAL", True, f"日米欧グローバルモード（資産 ¥{total_equity_jpy:,.0f} < 200万円: 欧州ADR組入・小資金効率化）"

    @classmethod
    def calculate_half_kelly_allocation(
        cls,
        confidence_score: float,
        target_price: Optional[float],
        current_price: Optional[float],
        stop_loss_price: Optional[float],
        effective_capacity: int = 5
    ) -> float:
        """
        Lumina AI Fractional Kelly (Half-Kelly) Position Sizing Engine (v4.0).
        Calculates optimal allocation percentage based on:
        - Estimated win probability W from CIO confidence score.
        - Payoff ratio R from Target Return vs ATR Stop Loss.
        - Fractional Kelly (Half-Kelly: f* / 2) to cut volatility by 75% and prevent ruin.
        - Clamped safely between 5.0% (cautious) and 25.0% (high conviction ceiling).
        """
        cur_p = current_price or 1000.0
        tgt_p = target_price or (cur_p * 1.25)
        stp_p = stop_loss_price or (cur_p * 0.87)

        # 1. Target Gain & Stop Loss percentages
        gain_pct = max(3.0, ((tgt_p - cur_p) / cur_p) * 100.0) if cur_p > 0 else 25.0
        loss_pct = max(2.5, ((cur_p - stp_p) / cur_p) * 100.0) if cur_p > 0 else 13.0

        # 2. Payoff Ratio R
        payoff_ratio = max(0.5, gain_pct / loss_pct)

        # 3. Estimated Win Probability W from CIO confidence score (50 to 100)
        clamped_score = max(50.0, min(100.0, float(confidence_score)))
        win_prob = 0.50 + ((clamped_score - 50.0) / 50.0) * 0.32  # 50 -> 0.50, 75 -> 0.66, 100 -> 0.82

        # 4. Full Kelly Criterion: K = W - (1 - W) / R
        full_kelly = win_prob - ((1.0 - win_prob) / payoff_ratio)

        # 5. Half-Kelly (Fractional Kelly)
        half_kelly_pct = (full_kelly * 0.5) * 100.0 if full_kelly > 0 else 5.0

        # 6. Blend with effective capacity baseline (e.g. 20% for 5-slot, 16.7% for 6-slot)
        base_alloc = 100.0 / effective_capacity
        blended_alloc = (base_alloc * 0.40) + (half_kelly_pct * 0.60)

        # 7. Clamp within professional risk bounds [5.0%, 25.0%]
        final_alloc = max(5.0, min(25.0, round(blended_alloc, 1)))
        return final_alloc

    @staticmethod
    def compute_hrp_weights(returns_df: pd.DataFrame) -> pd.Series:
        """
        Marcos López de Prado's Hierarchical Risk Parity (HRP) algorithm.
        Constructs a hierarchical tree from correlation distances and allocates
        risk budgets inversely to cluster variances via recursive bisection.
        """
        n_assets = returns_df.shape[1]
        if n_assets <= 1:
            return pd.Series([1.0], index=returns_df.columns)

        try:
            import scipy.cluster.hierarchy as sch
            from scipy.spatial.distance import squareform

            corr = returns_df.corr().fillna(0.0)
            cov = returns_df.cov().fillna(0.0)

            # 1. Distance matrix
            dist_mat = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
            dist_items = np.sqrt(((dist_mat.values[:, None, :] - dist_mat.values[None, :, :]) ** 2).sum(axis=-1))
            np.fill_diagonal(dist_items, 0.0)
            condensed_dist = squareform(dist_items, checks=False)

            # 2. Hierarchical Linkage
            link = sch.linkage(condensed_dist, method='single')

            # 3. Quasi-Diagonalization
            linkage_mat = link.astype(int)
            num_items = linkage_mat[-1, 3]
            cluster_list = [linkage_mat[-1, 0], linkage_mat[-1, 1]]
            while any(i >= num_items for i in cluster_list):
                new_list = []
                for item in cluster_list:
                    if item < num_items:
                        new_list.append(item)
                    else:
                        sub_idx = item - num_items
                        new_list.append(linkage_mat[sub_idx, 0])
                        new_list.append(linkage_mat[sub_idx, 1])
                cluster_list = new_list

            sorted_cols = returns_df.columns[cluster_list].tolist()

            # 4. Recursive Bisection
            def get_cluster_var(cov_sub, c_items):
                sub_cov = cov_sub.loc[c_items, c_items]
                diag_inv = 1.0 / np.clip(np.diag(sub_cov), 1e-8, None)
                w = diag_inv / diag_inv.sum()
                return float(np.dot(np.dot(w, sub_cov.values), w))

            weights = pd.Series(1.0, index=sorted_cols)
            clusters = [sorted_cols]
            while len(clusters) > 0:
                new_clusters = []
                for cluster in clusters:
                    if len(cluster) > 1:
                        mid = len(cluster) // 2
                        c1 = cluster[:mid]
                        c2 = cluster[mid:]
                        v1 = get_cluster_var(cov, c1)
                        v2 = get_cluster_var(cov, c2)
                        alpha1 = 1.0 - (v1 / (v1 + v2))
                        alpha2 = 1.0 - alpha1
                        weights[c1] *= alpha1
                        weights[c2] *= alpha2
                        if len(c1) > 1: new_clusters.append(c1)
                        if len(c2) > 1: new_clusters.append(c2)
                clusters = new_clusters

            return weights / weights.sum()
        except Exception as e:
            # Safe equal-weight fallback
            return pd.Series([1.0 / n_assets] * n_assets, index=returns_df.columns)

    @classmethod
    def evaluate_adaptive_hrp_scaling(
        cls,
        candidate_symbol: str,
        held_symbols: List[str],
        correlation_spike_threshold: float = 0.40
    ) -> tuple:
        """
        AI適応型HRP（相関スパイク検知）リスク予算エンジン:
        1. 既存保有銘柄と新規買付候補の過去60営業日リターンを取得
        2. 候補銘柄と既存ポートフォリオの相関行列を計算
        3. 平均相関 >= 0.40（相関スパイク検知）の場合のみ、HRP幾何学クラスタリングを起動
        4. 同一クラスタ重複リスクを検知し、ロットを自動圧縮（0.45〜1.00倍）
        5. 平常時（低相関時）は 1.00倍（フルケリー）でモメンタムを全開放
        
        Returns:
            (hrp_scale: float, avg_cand_corr: float, status_message: str)
        """
        clean_held = [s for s in held_symbols if s and s != candidate_symbol]
        if not clean_held:
            return 1.0, 0.0, "初回エントリー（既存保有なし・相関リスクゼロ・モメンタム全開 1.00倍）"

        try:
            basket = list(clean_held) + [candidate_symbol]
            now_ts = time.time()
            needed_symbols = [s for s in basket if (s not in cls._prices_cache or (now_ts - cls._prices_cache[s][0]) >= cls.PRICES_CACHE_TTL)]
            if needed_symbols:
                df_new = yf.download(needed_symbols, period="3mo", progress=False)['Close']
                if isinstance(df_new, pd.Series):
                    df_new = df_new.to_frame(name=needed_symbols[0])
                for col in df_new.columns:
                    cls._prices_cache[col] = (now_ts, df_new[col].dropna())

            series_dict = {}
            for s in basket:
                if s in cls._prices_cache:
                    series_dict[s] = cls._prices_cache[s][1]

            if len(series_dict) < len(basket):
                df_closes = yf.download(basket, period="3mo", progress=False)['Close']
                if isinstance(df_closes, pd.Series):
                    df_closes = df_closes.to_frame()
            else:
                df_closes = pd.DataFrame(series_dict)

            returns_df = df_closes.pct_change(fill_method=None).dropna()
            if len(returns_df) < 15:
                return 1.0, 0.0, "データ履歴不足（フェイルセーフ: 通常配分 1.00倍）"

            corr_matrix = returns_df.corr().fillna(0.0)
            if candidate_symbol not in corr_matrix.columns:
                return 1.0, 0.0, "銘柄相関データ取得不可（フェイルセーフ: 通常配分 1.00倍）"

            cand_corrs = []
            for s in clean_held:
                if s in corr_matrix.columns:
                    pearson_c = float(corr_matrix.loc[candidate_symbol, s])
                    hy_c = 0.0
                    try:
                        from core.ai_hedge_fund.lead_lag_analyzer import LeadLagAnalyzer
                        if candidate_symbol in series_dict and s in series_dict:
                            hy_c = LeadLagAnalyzer.compute_hayashi_yoshida_corr(series_dict[candidate_symbol], series_dict[s])
                    except Exception:
                        hy_c = 0.0
                    cand_corrs.append(max(pearson_c, hy_c))
            avg_cand_corr = float(np.mean(cand_corrs)) if cand_corrs else 0.0

            # Correlation Spike Trigger
            if avg_cand_corr < correlation_spike_threshold:
                return 1.0, avg_cand_corr, f"平常相関クリア（保有株との平均相関: {avg_cand_corr:.2f} < {correlation_spike_threshold:.2f}・モメンタム全開 1.00倍）"

            # Triggered: compute HRP weights
            hrp_weights = cls.compute_hrp_weights(returns_df)
            w_cand = hrp_weights.get(candidate_symbol, 1.0 / len(basket))
            w_eq = 1.0 / len(basket)
            raw_scale = w_cand / w_eq
            clamped_scale = float(np.clip(raw_scale, 0.45, 1.00))

            return clamped_scale, avg_cand_corr, f"🚨【相関スパイク検知】既存保有との平均相関 {avg_cand_corr:.2f} ≧ {correlation_spike_threshold:.2f}！同一クラスタ重複リスクを検知し、HRPによりロットを自動圧縮（{clamped_scale:.2f}倍）"
        except Exception as e:
            return 1.0, 0.0, f"HRP計算例外ガード: {e}（フェイルセーフ: 通常配分 1.00倍）"

    @classmethod
    def patrol_positions(
        cls,
        broker_engine: PaperTradingEngine,
        enforce_market_hours: bool = True
    ) -> Dict[str, Any]:
        """
        Sub-minute Realtime Position Watchdog Sentinel & Trailing Stop Engine
        Evaluates Rules A, B, B2, C, D, E for all currently held positions.
        Can be invoked both by the 15-minute deliberation cycle and the 5-10s Watchdog Sentinel thread.
        """
        logs = []
        closed_orders = []
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        patrol_sig_ts = time.time()

        summary = broker_engine.get_portfolio_summary()
        positions = summary.get("positions", [])

        # Pre-evaluate all positions in nanoseconds via `#![forbid(unsafe_code)]` Cache-Resident SoA Rust Sentinel
        rust_sentinel_ns = 0
        rust_engine_name = "python-soa-fallback"
        try:
            soa_payload = [
                {
                    "symbol": p.get("symbol", ""),
                    "entry_price": p.get("avg_entry_price", 0.0),
                    "current_price": p.get("current_price", 0.0),
                    "peak_price": p.get("peak_price", 0.0),
                    "stop_loss_price": p.get("stop_loss_price", 0.0),
                    "target_price": p.get("target_price", 0.0),
                    "call_wall_price": 0.0,
                    "is_half_profit_taken": p.get("half_profit_taken", 0),
                    "is_day_trade": 1 if p.get("strategy_type") == "DAY_CIS" else 0,
                }
                for p in positions
            ]
            rust_res = RustSentinelBridge.get_instance().evaluate_positions(soa_payload)
            rust_sentinel_ns = int(rust_res.get("elapsed_ns", 0))
            rust_engine_name = str(rust_res.get("engine", "lumina-sentinel-rs"))
        except Exception:
            pass

        for pos in positions:
            sym = pos["symbol"]
            qty = pos["quantity"]
            curr = pos["currency"]
            is_jp = sym.endswith(".T")

            # In real API mode: if this position's exchange is closed, market orders cannot be filled
            if enforce_market_hours:
                if is_jp and not MarketSession.is_tse_open():
                    continue
                if not is_jp and not MarketSession.is_us_open():
                    continue

            # Alpha & Beta Decoupling Protocol:
            # cur_price, entry_price, stop_loss_price, and pnl_pct are strictly denominated in
            # the stock's NATIVE CURRENCY (USD for US stocks, JPY for TSE stocks).
            # This completely insulates individual stop-losses from USD/JPY currency swings (no FX stop hunting).
            pnl_pct = pos["unrealized_pnl_pct"]
            cur_price = pos["current_price"]
            entry_price = pos["avg_entry_price"]
            name = pos["company_name"]
            pos_ver = int(pos.get("version", 1))
            
            # Trailing stop & target levels (Native Currency based)
            peak_price = max(float(pos.get("peak_price") or entry_price), cur_price)
            half_taken = int(pos.get("half_profit_taken") or 0)
            target_price = float(pos.get("target_price") or (entry_price * 1.25))
            stop_loss_price = float(pos.get("stop_loss_price") or (entry_price * 0.87))

            # 🛡️ Corporate Action (Stock Split / Reverse Split) Auto-Scaling Guard:
            # If price diverges sharply (>= -35% drop or >= +80% jump) and a recent split ratio exists
            # whose scaled entry price aligns within 25% of cur_price, atomically rescale position in SQLite!
            if entry_price > 0 and (pnl_pct <= -35.0 or pnl_pct >= 80.0):
                split_ratio = MarketDataFeed.get_recent_stock_split_ratio(sym, days_window=14)
                if split_ratio > 0.0 and abs(split_ratio - 1.0) > 1e-4:
                    theoretical_post_split_entry = entry_price / split_ratio
                    if abs(cur_price - theoretical_post_split_entry) / max(theoretical_post_split_entry, 1e-6) < 0.25:
                        adj = broker_engine.apply_stock_split_adjustment(sym, split_ratio, expected_version=pos_ver)
                        if adj:
                            qty = adj["new_quantity"]
                            entry_price = adj["new_entry_price"]
                            peak_price = max(adj["new_peak_price"], cur_price)
                            stop_loss_price = adj["new_stop_loss_price"]
                            target_price = adj["new_target_price"]
                            pnl_pct = ((cur_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
                            pos_ver += 1
                            logs.append(
                                f"[{now_str}] 🔄 【株式分割・併合 自動スケーリング補正】{name} ({sym}) のコーポレートアクション（分割比率 1:{split_ratio:g}）を検知！"
                                f"保有株数を {adj['old_quantity']}株 → {qty}株、取得単価を {adj['old_entry_price']:,.2f} → {entry_price:,.2f} {curr}、"
                                f"逆指値を {stop_loss_price:,.2f} {curr} に自動スケーリング補正し、誤損切りを完全防止しました。"
                            )

            # Update peak price in DB if new high is printed (with CAS)
            if cur_price > float(pos.get("peak_price") or 0.0):
                if broker_engine.update_position_tracking(sym, peak_price=cur_price, expected_version=pos_ver):
                    pos_ver += 1

            # Drawdown from peak (negative percentage)
            drawdown_from_peak_pct = ((cur_price - peak_price) / peak_price * 100.0) if peak_price > 0 else 0.0

            # --- ⚡ Day-Trading Book: cis Flow Sniper Intraday Wall Exit Engine ---
            strat_type = pos.get("strategy_type", "SWING")
            if strat_type == "DAY_CIS":
                # cis Rule 1: Target Wall Hit (Take Profit)
                if cur_price >= target_price:
                    res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"cisスナイパー売り壁目標達成 (+{pnl_pct:+.1f}%)", enforce_market_hours=enforce_market_hours, strategy_type="DAY_CIS", signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                    if res.get("cas_conflict"):
                        logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                        continue
                    if res.get("success"):
                        pnl_amount = (cur_price - entry_price) * qty
                        broker_engine.record_trade_memory(
                            symbol=sym, company_name=name, trade_type="SELL_EXIT",
                            quantity=qty, price=cur_price, currency=curr,
                            realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                            trigger_rule="DAY_CIS_TARGET",
                            lesson_learned=f"大口売り壁手前 ({target_price:,.2f} {curr}) 到達により利確完了。スカルピング/デイトレ成功。"
                        )
                        HedgeFundNotifier.notify_trade(
                            symbol=sym, company_name=name, side="SELL", quantity=qty, price=cur_price,
                            currency=curr, rule_type="DAY_CIS_TARGET", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                            notes=f"cisスナイパー売り壁目標 {target_price:,.2f} {curr} 到達により利確完了 (+{pnl_pct:+.1f}%)"
                        )
                        logs.append(f"[{now_str}] ⚡ 🎯 【cisスナイパー利確達成】{name} ({sym}) が大口売り壁目標 {target_price:,.2f} {curr} に到達！(+{pnl_pct:+.1f}%)")
                        closed_orders.append(res)
                        continue

                # cis Rule 2: Support Wall Broken + ATR Buffer Exhausted (Stop Loss)
                if cur_price <= stop_loss_price:
                    res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"cisスナイパー大口壁割れ損切り ({pnl_pct:+.1f}%)", enforce_market_hours=enforce_market_hours, strategy_type="DAY_CIS", signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                    if res.get("cas_conflict"):
                        logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                        continue
                    if res.get("success"):
                        pnl_amount = (cur_price - entry_price) * qty
                        broker_engine.record_trade_memory(
                            symbol=sym, company_name=name, trade_type="SELL_EXIT",
                            quantity=qty, price=cur_price, currency=curr,
                            realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                            trigger_rule="DAY_CIS_STOP",
                            lesson_learned=f"大口買い壁割れ＆ATRバッファ消化 ({stop_loss_price:,.2f} {curr}) により即時ロスカット。デイトレ規律遵守。"
                        )
                        HedgeFundNotifier.notify_trade(
                            symbol=sym, company_name=name, side="SELL", quantity=qty, price=cur_price,
                            currency=curr, rule_type="DAY_CIS_STOP", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                            notes=f"cisスナイパー大口壁割れ損切り ({pnl_pct:+.1f}% / 逆指値: {stop_loss_price:,.2f} {curr})"
                        )
                        logs.append(f"[{now_str}] ⚡ 🛡️ 【cisスナイパー損切り執行】{name} ({sym}) が支持壁割れライン {stop_loss_price:,.2f} {curr} に到達したため撤退 ({pnl_pct:+.1f}%)")
                        closed_orders.append(res)
                        continue

                # For DAY_CIS positions, do not run the swing rules A-E below
                continue

            # --- Rule A: Full Target Price Hit (+25%〜+40% CIO Target) ---
            if cur_price >= target_price:
                res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"CIO目標株価完全達成 (+{pnl_pct:.1f}%)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                if res.get("cas_conflict"):
                    logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                    continue
                if res.get("success"):
                    pnl_amount = (cur_price - entry_price) * qty
                    broker_engine.record_trade_memory(
                        symbol=sym, company_name=name, trade_type="SELL_EXIT",
                        quantity=qty, price=cur_price, currency=curr,
                        realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                        trigger_rule="CIO_TARGET",
                        lesson_learned=f"CIO目標株価 {target_price:,.2f} {curr} 完全到達により大勝利利確。投資テーゼが完全に的中。"
                    )
                    HedgeFundNotifier.notify_trade(
                        symbol=sym, company_name=name, side="SELL", quantity=qty, price=cur_price,
                        currency=curr, rule_type="CIO_TARGET", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                        notes=f"CIO目標株価 {target_price:,.2f} {curr} 完全到達！全株大勝利決済"
                    )
                    logs.append(f"[{now_str}] 🏆 【目標株価完全達成】{name} ({sym}) がCIOターゲット {target_price:,.2f} {curr} に到達！全株大勝利決済 (+{pnl_pct:.1f}%)")
                    if MarketScreener.remove_custom_ticker(sym):
                        logs.append(f"[{now_str}] 🎓 【監視リスト卒業】{name} ({sym}) は目標利確完了に伴いカスタム監視リストから自動卒業しました。")
                    closed_orders.append(res)
                    continue

            # --- Rule B: Partial Take-Profit (First +10% Gain) ---
            # Lock in 50% profit, then raise stop-loss to entry price (breakeven)!
            can_split = (qty >= 200 if curr == "JPY" else qty >= 2)
            if pnl_pct >= 10.0 and half_taken == 0 and can_split:
                sell_qty = (qty // 2 // 100) * 100 if curr == "JPY" else (qty // 2)
                if sell_qty > 0:
                    res = broker_engine.place_order(sym, "SELL", sell_qty, cur_price, notes=f"第1弾ハーフ利確 (+{pnl_pct:.1f}%)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                    if res.get("cas_conflict"):
                        logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                        continue
                    if res.get("success"):
                        broker_engine.update_position_tracking(sym, peak_price=cur_price, half_profit_taken=1, stop_loss_price=entry_price, expected_version=pos_ver + 1)
                        pnl_amount = (cur_price - entry_price) * sell_qty
                        broker_engine.record_trade_memory(
                            symbol=sym, company_name=name, trade_type="PARTIAL_TAKE_PROFIT",
                            quantity=sell_qty, price=cur_price, currency=curr,
                            realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                            trigger_rule="PARTIAL_TAKE_PROFIT",
                            lesson_learned=f"+10%達成で半分利確ロック。残りは建値ストップでノーリスク追従へ移行。"
                        )
                        HedgeFundNotifier.notify_trade(
                            symbol=sym, company_name=name, side="SELL", quantity=sell_qty, price=cur_price,
                            currency=curr, rule_type="PARTIAL_TAKE_PROFIT", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                            notes=f"+10%到達による第1弾ハーフ利確。残りポジションは買値ストップへ移行"
                        )
                        logs.append(f"[{now_str}] 🎯 【第1弾・ハーフ利確執行】{name} ({sym}) の半分 ({sell_qty}株) を利益確定ロック (+{pnl_pct:.1f}%)！残り {qty - sell_qty}株 は買値ストップでノーリスク大化け追従へ。")
                        closed_orders.append(res)
                        continue
            elif pnl_pct >= 10.0 and half_taken == 0 and not can_split:
                # 100-share TSE minimum board lot (or 1-share US lot) cannot be split into odd-lot 50 shares:
                # Activate synthetic Breakeven Stop & Trailing Stop protection immediately without odd-lot rejection!
                if broker_engine.update_position_tracking(sym, peak_price=cur_price, half_profit_taken=1, stop_loss_price=entry_price, expected_version=pos_ver):
                    pos_ver += 1
                    half_taken = 1
                    stop_loss_price = entry_price
                    logs.append(
                        f"[{now_str}] 🛡️ 【単元株+10%建値ロック発動】{name} ({sym}) は最小単元（{qty}株）のため端株分割を行わず、"
                        f"逆指値を建値（{entry_price:,.1f} {curr}）へ引き上げてノーリスク・トレイリング追従モードへ移行しました (+{pnl_pct:.1f}%)！"
                    )

            # --- Rule B2: Options Call Wall Half-Take-Profit & Squeeze Free-Ride (US Stocks) ---
            # If stock approaches Call Wall (-1.0% to +0.0%), lock in 50% profit early and ride Gamma Squeeze with free-ride stop!
            if not is_jp and half_taken == 0 and can_split and pnl_pct >= 3.0:
                gex_prof = OptionsGexFeed.get_gex_profile(sym)
                c_wall = gex_prof.get("call_wall")
                p_wall = gex_prof.get("put_wall")
                if c_wall and cur_price >= (c_wall * 0.99):
                    sell_qty = qty // 2
                    if sell_qty > 0:
                        res = broker_engine.place_order(sym, "SELL", sell_qty, cur_price, notes=f"Call Wall到達ハーフ利確 (天井壁 ${c_wall:,.2f})", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                        if res.get("cas_conflict"):
                            logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                            continue
                        if res.get("success"):
                            new_sl = max(entry_price, p_wall if p_wall else entry_price)
                            broker_engine.update_position_tracking(sym, peak_price=cur_price, half_profit_taken=1, stop_loss_price=new_sl, expected_version=pos_ver + 1)
                            pnl_amount = (cur_price - entry_price) * sell_qty
                            broker_engine.record_trade_memory(
                                symbol=sym, company_name=name, trade_type="PARTIAL_TAKE_PROFIT",
                                quantity=sell_qty, price=cur_price, currency=curr,
                                realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                                trigger_rule="CALL_WALL_HALF_PROFIT",
                                lesson_learned=f"機関の上値抵抗壁 Call Wall (${c_wall:,.2f}) 到達で半分利確ロック。残りは買値/Put Wallストップでガンマ・スクイーズ突破をノーリスク追随。"
                            )
                            HedgeFundNotifier.notify_trade(
                                symbol=sym, company_name=name, side="SELL", quantity=sell_qty, price=cur_price,
                                currency=curr, rule_type="PARTIAL_TAKE_PROFIT", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                                notes=f"Call Wall (${c_wall:,.2f}) 到達によるハーフ利確！残りポジションはガンマ・スクイーズ追随モードへ移行"
                            )
                            logs.append(f"[{now_str}] 🎯 【Call Wall ハーフ利確執行】{name} ({sym}) が機関の上値抵抗壁 ${c_wall:,.2f} 直下に到達！半分 ({sell_qty}株) を利益確定ロック (+{pnl_pct:.1f}%)！残り {qty - sell_qty}株 は買値ストップでガンマ・スクイーズ突破をノーリスク追随へ。")
                            closed_orders.append(res)
                            continue

            # --- Rule C: Trailing Stop Trigger (Peak-out after substantial gain) ---
            # If stock gained >= 10% (either currently or at peak) and drops -4% from peak -> sell remaining to lock peak profit!
            peak_pnl_pct = ((peak_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
            if (pnl_pct >= 10.0 or peak_pnl_pct >= 10.0) and drawdown_from_peak_pct <= -4.0:
                res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"トレイリングストップ発動 (高値 {peak_price:,.2f} から {drawdown_from_peak_pct:.1f}%)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                if res.get("cas_conflict"):
                    logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                    continue
                if res.get("success"):
                    pnl_amount = (cur_price - entry_price) * qty
                    broker_engine.record_trade_memory(
                        symbol=sym, company_name=name, trade_type="SELL_EXIT",
                        quantity=qty, price=cur_price, currency=curr,
                        realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                        trigger_rule="TRAILING_STOP",
                        lesson_learned=f"高値 {peak_price:,.2f} からの-4%反落を検知し天井付近で勝ち逃げ完了。利益を大幅確保。"
                    )
                    HedgeFundNotifier.notify_trade(
                        symbol=sym, company_name=name, side="SELL", quantity=qty, price=cur_price,
                        currency=curr, rule_type="TRAILING_STOP", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                        notes=f"最高値 {peak_price:,.2f} からの反落検知により天井付近で利益確保"
                    )
                    logs.append(f"[{now_str}] 🚀 【トレイリングストップ発動】{name} ({sym}) が最高値 {peak_price:,.2f} {curr} から反落 ({drawdown_from_peak_pct:.1f}%) したため、天井付近で全株売り抜け利益確保！(+{pnl_pct:.1f}%)")
                    if MarketScreener.remove_custom_ticker(sym):
                        logs.append(f"[{now_str}] 🎓 【監視リスト卒業】{name} ({sym}) はトレイリング利確完了に伴いカスタム監視リストから自動卒業しました。")
                    closed_orders.append(res)
                    continue

            # --- Rule D: Breakeven Stop (if half profit was already taken, never allow a loss) ---
            if half_taken == 1 and cur_price <= entry_price:
                res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes="建値撤退ストップ (損失ゼロ保護)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                if res.get("cas_conflict"):
                    logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                    continue
                if res.get("success"):
                    broker_engine.record_trade_memory(
                        symbol=sym, company_name=name, trade_type="SELL_EXIT",
                        quantity=qty, price=cur_price, currency=curr,
                        realized_pnl=0.0, realized_pnl_pct=0.0,
                        trigger_rule="BREAKEVEN_STOP",
                        lesson_learned="第1弾利確後の残り玉を買値撤退。第1弾の確定利益を守り切り損失ゼロで完了。"
                    )
                    logs.append(f"[{now_str}] 🛡️ 【建値撤退ストップ】{name} ({sym}) 残りポジションを買値撤退。第1弾の利確利益を100%死守しました。")
                    if MarketScreener.remove_custom_ticker(sym):
                        logs.append(f"[{now_str}] 🎓 【監視リスト卒業】{name} ({sym}) は決済完了に伴いカスタム監視リストから自動卒業しました。")
                    closed_orders.append(res)
                    continue

            # --- Rule E: Fibonacci Stop-Loss -13.0% (with -15.0% Safety Ceiling & Ex-Dividend Guard) ---
            if cur_price <= stop_loss_price or pnl_pct <= -15.0:
                # Ex-Dividend Adjustment Guard:
                # Check if recent theoretical ex-dividend drop artificially triggered the stop loss
                recent_div = MarketDataFeed.get_recent_ex_dividend_adjustment(sym, days_window=10)
                if recent_div > 0 and (cur_price + recent_div) > stop_loss_price and pnl_pct > -15.0:
                    new_sl = round(stop_loss_price - recent_div, 2 if curr == "USD" else 1)
                    broker_engine.update_position_tracking(sym, stop_loss_price=new_sl, expected_version=pos_ver)
                    adj_pnl = ((cur_price + recent_div - entry_price) / entry_price) * 100.0
                    logs.append(f"[{now_str}] 🛡️ 【配当落ち誤損切り防御ガード】{name} ({sym}) は配当権利落ち（1株あたり {recent_div:,.1f} {curr}）による一時的な窓開け下落を検知！配当還元後の実質損益率は {adj_pnl:+.1f}% のため強制損切りをブロックし、損切りラインを {new_sl:,.1f} {curr} に下方補正して保有を継続します。")
                    continue

                res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"フィボナッチ最適損切り執行 ({pnl_pct:.1f}%)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                if res.get("cas_conflict"):
                    logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                    continue
                if res.get("success"):
                    pnl_amount = (cur_price - entry_price) * qty
                    broker_engine.record_trade_memory(
                        symbol=sym, company_name=name, trade_type="SELL_EXIT",
                        quantity=qty, price=cur_price, currency=curr,
                        realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                        trigger_rule="FIBONACCI_STOP_LOSS",
                        lesson_learned=f"フィボナッチ最適損切りライン ({stop_loss_price:,.2f} {curr} / 損益: {pnl_pct:.1f}%) 到達による規律ある損切り。損失を最小限に抑え次回への教訓とする。"
                    )
                    HedgeFundNotifier.notify_trade(
                        symbol=sym, company_name=name, side="SELL", quantity=qty, price=cur_price,
                        currency=curr, rule_type="FIBONACCI_STOP_LOSS", pnl_amount=pnl_amount, pnl_pct=pnl_pct,
                        notes=f"フィボナッチ最適損切り執行 (損益: {pnl_pct:.1f}% / 逆指値: {stop_loss_price:,.2f} {curr})"
                    )
                    logs.append(f"[{now_str}] 🛡️ 【フィボナッチ最適損切り執行】{name} ({sym}) を {qty}株 @ {cur_price} {curr} でリスク管理損切り ({pnl_pct:.1f}% / 逆指値: {stop_loss_price:,.2f} {curr})")
                    if MarketScreener.remove_custom_ticker(sym):
                        logs.append(f"[{now_str}] 🎓 【監視リスト卒業】{name} ({sym}) は損切り決済完了に伴いカスタム監視リストから自動卒業しました。")
                    closed_orders.append(res)
                    continue

            # --- Rule F: Triple-Barrier Vertical Time-Stop (25-Trading-Day Dead-Money Rotation) ---
            # If held >= 35 calendar days (~25 trading days), never hit +10% partial TP, stagnant (+0.2% to +3.0%) and below 20-day SMA -> rotate capital!
            opened_at_str = pos.get("opened_at") or pos.get("updated_at")
            if not half_taken and opened_at_str and (0.2 <= pnl_pct <= 3.0):
                try:
                    opened_dt = datetime.datetime.strptime(opened_at_str[:19], "%Y-%m-%d %H:%M:%S")
                    days_held_cal = (datetime.datetime.now() - opened_dt).days
                    if days_held_cal >= 35:
                        sd_check = MarketDataFeed.get_stock_data(sym)
                        sma20_val = sd_check.get("history_metrics", {}).get("sma_20")
                        if sma20_val and cur_price < sma20_val:
                            res = broker_engine.place_order(sym, "SELL", qty, cur_price, notes=f"トリプルバリア時間制限ローテーション ({days_held_cal}日経過・微益撤退 +{pnl_pct:.1f}%)", enforce_market_hours=enforce_market_hours, signal_timestamp=patrol_sig_ts, expected_version=pos_ver)
                            if res.get("cas_conflict"):
                                logs.append(f"[{now_str}] 🛡️ {res.get('error')}")
                                continue
                            if res.get("success"):
                                pnl_amount = (cur_price - entry_price) * qty
                                broker_engine.record_trade_memory(
                                    symbol=sym, company_name=name, trade_type="SELL_EXIT",
                                    quantity=qty, price=cur_price, currency=curr,
                                    realized_pnl=pnl_amount, realized_pnl_pct=pnl_pct,
                                    trigger_rule="TIME_BARRIER_ROTATION",
                                    lesson_learned=f"保有{days_held_cal}日経過（約25営業日）でモメンタム鈍化（20日線割れ）。微益（+{pnl_pct:.1f}%）で資金を回収し、高RS主役株へローテーション。"
                                )
                                logs.append(f"[{now_str}] 🔄 【トリプルバリア時間ローテーション】{name} ({sym}) は保有{days_held_cal}日経過で20日線を割り込んだため、微益（+{pnl_pct:.1f}%）で資金回収し高モメンタム株へ枠を開放しました。")
                                closed_orders.append(res)
                                continue
                except Exception:
                    pass

        return {
            "closed_orders": closed_orders,
            "logs": logs,
            "inspected_count": len(positions),
            "rust_sentinel_ns": rust_sentinel_ns,
            "rust_engine": rust_engine_name,
        }

    @classmethod
    def run_autonomous_cycle(
        cls,
        broker_engine: PaperTradingEngine,
        strategy: str = "ALL",
        max_new_orders: int = 2,
        risk_budget_pct: float = 10.0,
        enforce_market_hours: bool = True,
        capacity_mode: str = "AUTO",
        swing_allocation_ratio: float = 1.00,
        day_allocation_ratio: float = 0.00,
        enable_day_sniper: bool = False
    ) -> Dict[str, Any]:
        """
        Execute one full autonomous cycle: Scan -> Analyze -> Buy -> Manage Positions (Sell).
        Supports Dual-Strategy: Swing Book (70%) + Day-Trading Book (30% cis flow sniper).
        Enforces realistic exchange rules: market orders execute only during open market hours.
        """
        logs = []
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cycle_sig_ts = time.time()
        logs.append(f"[{now_str}] 🚀 自律型AIヘッジファンド自動売買サイクルを開始しました（戦略: {strategy} ｜ 二刀流配分: スイング{int(swing_allocation_ratio*100)}% / デイトレ{int(day_allocation_ratio*100)}%）")

        # Market Session Status Check (Exchange trading hours inspection)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        is_dst = MarketSession._is_us_dst(now_utc)
        us_hours_desc = "22:30〜05:00 JST (夏時間 EDT)" if is_dst else "23:30〜06:00 JST (標準時 EST)"
        us_open_str = "22:30" if is_dst else "23:30"

        sess_info = MarketSession.get_market_status()
        active_market = sess_info.get("active_market", "CLOSED")
        status_desc = sess_info.get("status_desc", "")
        logs.append(f"[{now_str}] ⏰ 【市場稼働状況】{status_desc}（米国セッション: {us_hours_desc}）")

        # Macro Liquidity Weather Radar (FRED Net Liquidity)
        macro_status = MacroLiquidityFeed.get_macro_status()
        logs.append(f"[{now_str}] 🌊 【マクロ天候レーダー】{macro_status['summary_text']}")

        # Options Market Turbulence Radar (SPY/QQQ Gamma Flip)
        gex_turb = OptionsGexFeed.get_market_turbulence_warning()
        logs.append(f"[{now_str}] ⚡ 【オプション乱気流レーダー】{gex_turb['summary_text']}")

        # Realistic Broker API Guard: If both markets are closed, do not execute off-hours market orders
        if enforce_market_hours and active_market == "CLOSED":
            logs.append(f"[{now_str}] ⏸️ 【実発注API市場閉場ガード】現在、東京市場（09:00〜15:30 JST）および米国市場（{us_hours_desc}）ともに取引時間外です。実発注API規則（kabuステーション/IBKR）に準拠し、時間外成行発注を停止して開場（NY {us_open_str}〜 / 東証 翌09:00〜）を待機します。")
            try:
                broker_engine.record_equity_snapshot()
            except Exception:
                pass
            logs.append(f"[{now_str}] ✅ 自律売買サイクルが正常に完了しました（新規買い: 0件, 決済: 0件 - 市場開場待機中）")
            return {
                "timestamp": now_str,
                "opened_orders": [],
                "closed_orders": [],
                "logs": logs
            }

        # 1. Patrol Existing Positions with Trailing Stop & Partial Take Profit
        patrol_res = cls.patrol_positions(broker_engine=broker_engine, enforce_market_hours=enforce_market_hours)
        closed_orders = patrol_res.get("closed_orders", [])
        for pl in patrol_res.get("logs", []):
            logs.append(pl)

        # 2. Portfolio Balance & Unified Equity Inspection
        opened_orders = []
        balances = broker_engine.get_account_balance()
        held_positions = broker_engine.get_positions()
        held_symbols = {p["symbol"] for p in held_positions}

        # Calculate unified equity
        fx_rate = broker_engine.get_usdjpy_rate()
        pos_val_pre = 0.0
        for p in held_positions:
            s_close = p.get("current_price", p.get("avg_entry_price", 0.0))
            s_rate = fx_rate if p.get("currency") == "USD" else 1.0
            pos_val_pre += (p.get("quantity", 0) * s_close * s_rate)
        total_unified_equity_jpy = (balances.get("JPY", 0.0) + (balances.get("USD", 0.0) * fx_rate)) + pos_val_pre

        # Dynamic Position Capacity Determination
        effective_capacity, cap_reason = cls.determine_portfolio_capacity(
            held_positions=held_positions,
            total_equity_jpy=total_unified_equity_jpy,
            capacity_mode=capacity_mode
        )
        logs.append(f"[{now_str}] 🤖 【AI動的保有枠判定】上限枠: {effective_capacity}銘柄（{cap_reason}）| 現在保有: {len(held_symbols)}/{effective_capacity}銘柄")

        # Dynamic Adaptive Market Mode Determination (200万円スイッチング)
        adaptive_strat, include_europe, adaptive_desc = cls.get_adaptive_market_mode(
            total_equity_jpy=total_unified_equity_jpy,
            strategy=strategy
        )
        logs.append(f"[{now_str}] 🌐 【AIアダプティブ市場選択】{adaptive_desc}")

        # Check maximum portfolio capacity
        if len(held_symbols) >= effective_capacity:
            held_names = ", ".join([f"{p['company_name']} ({p['symbol']})" for p in held_positions[:effective_capacity]])
            logs.append(f"[{now_str}] 🛡️ 【ポートフォリオ満杯・エグジット監視中】現在、上限枠（{len(held_symbols)}/{effective_capacity}銘柄: {held_names}）を保有中です。新規買付を一時休止し、5重エグジットルールによる利確・損切り監視に専念します。")
            try:
                broker_engine.record_equity_snapshot()
            except Exception:
                pass
            logs.append(f"[{now_str}] ✅ 自律売買サイクルが正常に完了しました（新規買い: 0件, 決済: {len(closed_orders)}件）")
            return {
                "timestamp": now_str,
                "opened_orders": opened_orders,
                "closed_orders": closed_orders,
                "logs": logs
            }

        # Check unified buying power
        total_unified_cash = balances.get("JPY", 0.0) + (balances.get("USD", 0.0) * fx_rate)
        if total_unified_cash < 30000.0:
            logs.append(f"[{now_str}] ⏸️ 【買付余力待機】現在の総合余力（¥{total_unified_cash:,.0f}）が最低約定枠未満のため新規合議を待機し、保有株の利益確定による資金回収を待ちます。")
            try:
                broker_engine.record_equity_snapshot()
            except Exception:
                pass
            logs.append(f"[{now_str}] ✅ 自律売買サイクルが正常に完了しました（新規買い: 0件, 決済: {len(closed_orders)}件）")
            return {
                "timestamp": now_str,
                "opened_orders": opened_orders,
                "closed_orders": closed_orders,
                "logs": logs
            }

        # 3. Market Scan for Top Candidates (with Adaptive Europe Filter)
        logs.append(f"[{now_str}] 🔍 株式市場をスキャンし、投資妙味の高い銘柄を発掘中...（欧州ADR組入: {'ON (日米欧)' if include_europe else 'OFF (日米集中)'}）")
        candidates = MarketScreener.scan_opportunities(
            category=strategy, 
            max_results=12, 
            include_europe=include_europe
        )

        # Pillar 1: Market Breadth Regime Cash Shield (QuantConnect Lean / HMM Breadth Model)
        breadth_info = MarketScreener.get_market_breadth_regime()
        regime_max_slots = breadth_info.get("max_slots_cap", 6)
        min_rs_required = breadth_info.get("min_rs_required", 65)
        if regime_max_slots < effective_capacity:
            effective_capacity = regime_max_slots
            logs.append(f"[{now_str}] 🛡️ 【市場ブレッドス退避シールド】200日線維持率: {breadth_info['breadth_pct']}% ({breadth_info['regime_label']}) ➔ 最大保有枠を {effective_capacity}銘柄 に自動縮小してキャッシュを温存します。")
        else:
            logs.append(f"[{now_str}] 📊 【市場ブレッドス判定】200日線維持率: {breadth_info['breadth_pct']}% ({breadth_info['regime_label']} / 要求RS順位: {min_rs_required}以上)")

        # Real broker API filter: Prioritize only open market equities
        if enforce_market_hours:
            if active_market == "JP":
                candidates = [c for c in candidates if c["symbol"].endswith(".T")]
                logs.append(f"[{now_str}] 🇯🇵 【東証取引時間中】日本株のみを重点発掘・合議します（米国株は{us_open_str}のNY開場まで待機）")
            elif active_market == "US":
                candidates = [c for c in candidates if not c["symbol"].endswith(".T")]
                logs.append(f"[{now_str}] 🇺🇸 【米国市場取引時間中】米国株のみを重点発掘・合議します（日本株は翌09:00の東証開場まで待機）")

        # Filter candidates by 90-minute cooldown to ensure rich symbol rotation
        now_ts = time.time()
        available_candidates = []
        for cand in candidates:
            s_sym = cand["symbol"]
            if s_sym in held_symbols:
                continue
            last_ex = cls._examined_cooldowns.get(s_sym, 0.0)
            if (now_ts - last_ex) < (90 * 60):  # 90-min cooldown
                continue
            available_candidates.append(cand)

        # If all candidates are on cooldown, flush oldest to keep patrol flowing
        if not available_candidates:
            cls._examined_cooldowns.clear()
            available_candidates = [c for c in candidates if c["symbol"] not in held_symbols]

        council_calls_count = 0
        max_council_calls = max(3, max_new_orders + 1)

        for cand in available_candidates:
            if len(opened_orders) >= max_new_orders or len(held_symbols) >= effective_capacity or council_calls_count >= max_council_calls:
                break
            sym = cand["symbol"]
            name = cand["name"]
            if sym in held_symbols:
                continue

            # Record examination timestamp for cooldown rotation
            cls._examined_cooldowns[sym] = now_ts

            # Real broker API check: Skip if target exchange is currently closed
            if enforce_market_hours:
                is_jp = sym.endswith(".T")
                if is_jp and not MarketSession.is_tse_open():
                    logs.append(f"[{now_str}] ⏸️ 【東証休場スキップ】東証取引時間外（平日 09:00〜15:30 JST）のため {name} ({sym}) の買付を見送ります。")
                    continue
                if not is_jp and not MarketSession.is_us_open():
                    logs.append(f"[{now_str}] ⏸️ 【米国市場休場スキップ】米取引時間外（日本時間 22:30〜翌05:00 JST）のため {name} ({sym}) の買付を見送ります。")
                    continue

            # 1. Earnings Gamble Avoidance Filter (Avoid buying within 3 days of earnings)
            earn_cal = MarketDataFeed.get_earnings_calendar(sym)
            if earn_cal.get("is_near_earnings"):
                logs.append(f"[{now_str}] ⚠️ 【決算ギャンブル回避スキップ】{name} ({sym}) は次回決算発表（{earn_cal.get('earnings_date')}、あと{earn_cal.get('days_remaining')}日）が直前に迫っているため、決算跨ぎ暴落リスクを避けて新規買いを見送ります。")
                continue

            # 2. Stage 2 Uptrend Filter (Weinstein Stage 2: Never buy falling knives below 200-day SMA)
            stock_data_pre = MarketDataFeed.get_stock_data(sym)
            cur_price_pre = stock_data_pre.get("current_price") or 0.0
            sma_200 = stock_data_pre.get("history_metrics", {}).get("sma_200")
            curr_code = stock_data_pre.get("currency", "JPY" if sym.endswith(".T") else "USD")
            if sma_200 and cur_price_pre > 0 and cur_price_pre < (sma_200 * 0.98):
                logs.append(f"[{now_str}] 🛡️ 【ステージ2防御フィルター除外】{name} ({sym}) は株価（{cur_price_pre:,.1f} {curr_code}）が200日移動平均線（{sma_200:,.1f} {curr_code}）を下回る下降トレンド（Stage 4）のため、落ちてくるナイフ・ブルトラップを回避し新規買付を見送ります。")
                continue

            # 3. Buffett Financial Moat Filter (Strict ROE >= 12.0% Defense)
            roe_pre = stock_data_pre.get("roe")
            if roe_pre is not None and roe_pre < 12.0:
                logs.append(f"[{now_str}] 🛡️ 【バフェット財務堀フィルター除外】{name} ({sym}) は実績ROE（{roe_pre:.1f}%）が厳格基準（12.0%以上）未満のため、低収益・ダマシリスクを排除し新規買付を見送ります。")
                continue

            # 4. Pillar 2: Piotroski F-Score >= 6 Financial Quality Audit (FinanceToolkit Standard)
            f_score_pre = stock_data_pre.get("piotroski_f_score", cand.get("piotroski_f_score", 7))
            if f_score_pre is not None and f_score_pre < 6:
                logs.append(f"[{now_str}] 🛡️ 【ピオトロスキー財務監査除外】{name} ({sym}) はF-Score（{f_score_pre}/9点）が基準（6点以上）未満のため、過剰債務・営業CF悪化リスクを排除し見送ります。")
                continue

            # 5. Pillar 3: Cross-Sectional Relative Strength Rating Filter (vectorbt / O'Neil Standard)
            cand_rs = cand.get("rs_rating", 80)
            if cand_rs < min_rs_required:
                logs.append(f"[{now_str}] 🛡️ 【RS相対モメンタム除外】{name} ({sym}) は相対モメンタム順位（RS {cand_rs}）が現在レジーム基準（RS {min_rs_required}以上）未満のため、主役セクターへ資金を温存します。")
                continue

            logs.append(f"[{now_str}] 🏛️ 銘柄「{name} ({sym})」のAI投資合議委員会を招集 (ROE: {roe_pre}% / F-Score: {f_score_pre}点 / RS順位: {cand_rs})...")
            council_calls_count += 1
            with ConcurrencyController.council_debate_phase():
                council_res = HedgeFundCouncil.run_council(sym)
            verdict = council_res.get("verdict", {})
            action = verdict.get("action", "HOLD")
            score = verdict.get("confidence_score", 0)

            if action in ["BUY", "ACCUMULATE"] and score >= 70:
                curr = council_res.get("currency", "JPY")
                price = council_res.get("current_price", 1000.0)
                cash = balances.get(curr, 0.0)
                
                min_lot = 100 if curr == "JPY" else 1
                min_cost = min_lot * price

                # Unified buying power & target budget calculation
                fx_rate = broker_engine.get_usdjpy_rate()
                total_unified_cash_jpy = balances.get("JPY", 0.0) + (balances.get("USD", 0.0) * fx_rate)
                min_cost_jpy = min_cost if curr == "JPY" else (min_cost * fx_rate)

                if total_unified_cash_jpy < min_cost_jpy:
                    logs.append(f"[{now_str}] ⚠️ 【総合余力不足スキップ】{name} ({sym}) の購入には最低 {min_cost:,.0f} {curr}（{min_lot}株）必要ですが、口座全体の総合余力が ¥{total_unified_cash_jpy:,.0f} のためスキップし、他の候補を探索します。")
                    continue

                # Target allocation budget via Half-Kelly (Fractional Kelly)
                fib_sl_price = verdict.get("stop_loss_price") or round(price * 0.87, 2)
                half_kelly_alloc = cls.calculate_half_kelly_allocation(
                    confidence_score=score,
                    target_price=verdict.get("target_price"),
                    current_price=price,
                    stop_loss_price=fib_sl_price,
                    effective_capacity=effective_capacity
                )
                alloc_pct = verdict.get("allocation_pct") or half_kelly_alloc
                alloc_pct = min(25.0, max(5.0, alloc_pct))
                target_budget_jpy = min(total_unified_cash_jpy * 0.90, total_unified_cash_jpy * (alloc_pct / 100.0))

                # === ADAPTIVE HRP (CORRELATION SPIKE DETECTION) BRAKE ===
                hrp_scale, cand_corr, hrp_msg = cls.evaluate_adaptive_hrp_scaling(
                    candidate_symbol=sym,
                    held_symbols=list(held_symbols)
                )
                if hrp_scale < 1.0:
                    target_budget_jpy = max(min_cost_jpy, target_budget_jpy * hrp_scale)
                    logs.append(f"[{now_str}] 🛡️ {hrp_msg} (予算調整: ¥{target_budget_jpy:,.0f})")
                else:
                    logs.append(f"[{now_str}] 🛡️ 【適応型HRP判定】{hrp_msg}")

                # === OPTIONS GEX MARKET TURBULENCE BRAKE ===
                if gex_turb.get("is_turbulence"):
                    gex_scale = gex_turb.get("size_multiplier", 0.5)
                    target_budget_jpy = max(min_cost_jpy, target_budget_jpy * gex_scale)
                    logs.append(f"[{now_str}] 🛡️ 【乱気流防御発動】SPY/QQQ ネガティブ・ガンマ検知に伴い、新規配分予算を50%圧縮（¥{target_budget_jpy:,.0f}）")

                target_cost_curr = target_budget_jpy if curr == "JPY" else (target_budget_jpy / fx_rate)
                target_cost_curr = max(min_cost, target_cost_curr)
                logs.append(f"[{now_str}] ⚖️ 【ハーフ・ケリー×適応型HRP資金配分】{name} ({sym}) - 確信度: {score}点 / 最適ロット比率: {alloc_pct:.1f}% × {hrp_scale:.2f}倍 (配分予算: ¥{target_budget_jpy:,.0f})")

                # Auto-FX if direct currency cash is short but other currency has funds (IBKR Multi-Currency Auto-Allocation)
                if cash < target_cost_curr:
                    if curr == "JPY" and balances.get("USD", 0.0) > 0:
                        needed_jpy = target_cost_curr - cash
                        needed_usd = round((needed_jpy / fx_rate) * 1.01, 2)
                        needed_usd = min(needed_usd, balances["USD"])
                        if needed_usd > 0:
                            conv_res = broker_engine.convert_currency("USD", "JPY", needed_usd)
                            if conv_res.get("success"):
                                logs.append(f"[{now_str}] 💱 【IBKRマルチカレンシー自動充当】日本株「{name}」購入のため ${needed_usd:,.2f} を ¥{conv_res['received']:,.0f} に即時両替し、買付余力を確保しました！")
                                balances["USD"] -= needed_usd
                                balances["JPY"] += conv_res["received"]
                                cash = balances["JPY"]
                    elif curr == "USD" and balances.get("JPY", 0.0) > 0:
                        needed_usd = target_cost_curr - cash
                        needed_jpy = round(needed_usd * fx_rate * 1.01, 0)
                        needed_jpy = min(needed_jpy, balances["JPY"])
                        if needed_jpy > 0:
                            conv_res = broker_engine.convert_currency("JPY", "USD", needed_jpy)
                            if conv_res.get("success"):
                                logs.append(f"[{now_str}] 💱 【IBKRマルチカレンシー自動充当】海外株「{name}」購入のため ¥{needed_jpy:,.0f} を ${conv_res['received']:,.2f} に即時両替し、買付余力を確保しました！")
                                balances["JPY"] -= needed_jpy
                                balances["USD"] += conv_res["received"]
                                cash = balances["USD"]

                # Sizing based on Half-Kelly target budget and available cash in currency
                if curr == "JPY":
                    max_cash_lots = (int(cash // price) // 100) * 100
                    target_lots = (int(target_cost_curr // price) // 100) * 100
                    qty = min(max_cash_lots, max(100, target_lots))
                    if qty < 100 and cash >= min_cost:
                        qty = 100
                else:
                    target_qty = int(target_cost_curr // price)
                    qty = max(1, min(int(cash // price), target_qty))

                cost = qty * price
                if cost > cash:
                    qty = min_lot
                    cost = qty * price

                if qty > 0 and cash >= cost:
                    # ⚡ 【深層OFIスマート執行ゲートキーパー】発注直前の板奥需給チェック
                    allow_exec, gate_mode, ofi_res = cls.evaluate_swing_ofi_execution_gate(
                        symbol=sym,
                        broker_engine=broker_engine,
                        symbol_name=name,
                        now_str=now_str,
                        logs=logs
                    )
                    if not allow_exec:
                        continue  # 発注を一時保留し、大口の売り抜けをやり過ごす

                    ofi_score = ofi_res.get("deep_ofi_score", 0.0)
                    ofi_tag = (
                        f" 💎[深層OFIステルス買い: OFI {ofi_score:+.1f}]" if gate_mode == "SNIPER_STEALTH"
                        else (f" ⏱️[OFI待機タイムアウト執行]" if gate_mode == "TIMEOUT_EXEC" else f" ⚡[OFI正常: {ofi_score:+.1f}]")
                    )

                    res = broker_engine.place_order(
                        sym, "BUY", qty, price,
                        notes=f"自律買い執行 (CIO判定: {verdict.get('action_label')} / スコア: {score}点){ofi_tag}",
                        target_price=verdict.get("target_price"),
                        stop_loss_price=fib_sl_price,
                        enforce_market_hours=enforce_market_hours,
                        strategy_type="SWING",
                        signal_timestamp=cycle_sig_ts
                    )
                    if res.get("success"):
                        broker_engine.record_trade_memory(
                            symbol=sym, company_name=name, trade_type="BUY_ENTRY",
                            quantity=qty, price=price, currency=curr,
                            trigger_rule="COUNCIL_BUY",
                            thesis_at_entry=f"{verdict.get('thesis_summary', '合議委員会による買い推奨')}{ofi_tag}",
                            lesson_learned=f"目標株価: {verdict.get('target_price')} / 損切り: {fib_sl_price}"
                        )
                        HedgeFundNotifier.notify_trade(
                            symbol=sym, company_name=name, side="BUY", quantity=qty, price=price,
                            currency=curr, rule_type="COUNCIL_BUY",
                            notes=f"{verdict.get('thesis_summary', 'AI合議による積極買い約定')}{ofi_tag}",
                            target_price=verdict.get("target_price"),
                            stop_loss_price=fib_sl_price
                        )
                        logs.append(f"[{now_str}] 💰 【買い約定＆逆指値強制付帯{ofi_tag}】{name} ({sym}) {qty}株 @ {price} {curr} を新規約定！(目標: {verdict.get('target_price')} {curr} / ブラケット逆指値: {fib_sl_price:,.2f} {curr} [-13.0%])")
                        opened_orders.append(res)
                        # Deduct from tracking balance
                        balances[curr] -= cost
                        held_symbols.add(sym)
                    else:
                        err_msg = res.get('error', res.get('message', '不明なエラー'))
                        if res.get("idempotency_blocked") or res.get("stale_discarded"):
                            logs.append(f"[{now_str}] 🛡️ {err_msg}")
                        else:
                            logs.append(f"[{now_str}] ⚠️ 発注失敗: {err_msg}")
                else:
                    logs.append(f"[{now_str}] ⚠️ 【余力不足】{name} ({sym}) の必要額 {cost:,.0f} {curr} に対し、余力 {cash:,.0f} {curr} のため発注見送り")
            else:
                logs.append(f"[{now_str}] ⏸️ 判定保留: {name} ({sym}) は {verdict.get('action_label', action)} (スコア: {score}点) のため新規見送り")

        # 3. ⚡ Day-Trading Book: cis Flow Sniper Scan & Order Placement
        if enable_day_sniper:
            day_budget_jpy = total_unified_equity_jpy * day_allocation_ratio
            sniper_res = cls.run_cis_day_sniper_cycle(
                broker_engine=broker_engine,
                day_budget_jpy=day_budget_jpy,
                enforce_market_hours=enforce_market_hours
            )
            for sl in sniper_res.get("logs", []):
                logs.append(sl)
            for so in sniper_res.get("opened_orders", []):
                opened_orders.append(so)

        # Record Equity Curve Snapshot
        try:
            broker_engine.record_equity_snapshot()
        except Exception:
            pass
        logs.append(f"[{now_str}] ✅ 自律売買サイクルが正常に完了しました（新規買い: {len(opened_orders)}件, 決済: {len(closed_orders)}件）")

        return {
            "timestamp": now_str,
            "opened_orders": opened_orders,
            "closed_orders": closed_orders,
            "logs": logs
        }

    @classmethod
    def run_cis_day_sniper_cycle(
        cls,
        broker_engine: PaperTradingEngine,
        day_budget_jpy: float,
        enforce_market_hours: bool = True,
        sniper_symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Lumina AI Day-Trading Book: cis Flow Sniper Cycle
        Scans liquid targets, evaluates heavy buy/sell walls, VWAP trend,
        and executes bracket entries with ATR 0.8% false-breakout defense stop-losses.
        """
        import yfinance as yf
        from core.ai_hedge_fund.cis_flow_sniper import CisFlowSniper
        logs = []
        opened_orders = []
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        if not sniper_symbols:
            # Universe: Top liquid US growth/tech + custom watchlist
            custom_tickers = MarketScreener.get_custom_watchlist() or []
            custom_us = []
            for t in custom_tickers:
                sym_str = t.get("symbol", "") if isinstance(t, dict) else str(t)
                if sym_str and not sym_str.endswith(".T"):
                    custom_us.append(sym_str)
            sniper_symbols = ["NVDA", "TSLA", "QQQ", "AAPL", "MSFT"]
            for ct in custom_us:
                if ct not in sniper_symbols:
                    sniper_symbols.append(ct)

        # Enforce market hours check: if US market is closed, skip day sniper
        if enforce_market_hours and not MarketSession.is_us_open():
            logs.append(f"[{now_str}] ⏸️ 【cisデイトレ待機】米国市場（NY 22:30〜05:00 JST）閉場中のため、デイトレ・スナイパー発注を待機します。")
            return {"opened_orders": opened_orders, "logs": logs}

        # Check existing DAY_CIS holdings
        held_positions = broker_engine.get_positions()
        held_day_syms = {p["symbol"] for p in held_positions if p.get("strategy_type") == "DAY_CIS"}
        if len(held_day_syms) >= 2:
            logs.append(f"[{now_str}] ⚡ 【cisデイトレ枠満杯】現在 {len(held_day_syms)}銘柄保有中のため、新規デイトレ発注を見送りエグジット監視に専念します。")
            return {"opened_orders": opened_orders, "logs": logs}

        fx_rate = broker_engine.get_usdjpy_rate() or 155.0
        day_budget_usd = day_budget_jpy / fx_rate

        balances = broker_engine.get_account_balance()
        usd_cash = balances.get("USD", 0.0)

        for sym in sniper_symbols:
            if sym in held_day_syms:
                continue

            try:
                # Download 5m data for the last 5 days
                df_5m = yf.download(sym, period="5d", interval="5m", progress=False)
                if df_5m is None or len(df_5m) < 30:
                    continue

                order_book = broker_engine.get_order_book(sym, depth=10)
                setup = CisFlowSniper.evaluate_sniper_setup(sym, df_5m, order_book=order_book)
                if setup.get("is_spoof_trap"):
                    logs.append(f"[{now_str}] 🕵️ 【cis深層OFI防衛】{sym}: {setup.get('reason')}")
                    continue
                if setup.get("signal") == "BUY":
                    entry_p = setup["entry_price"]
                    tgt_p = setup["target_price"]
                    stp_p = setup["stop_loss_price"]
                    reason = setup["reason"]

                    # Sizing: Allocate up to 50% of remaining day budget per day trade
                    trade_usd = min(day_budget_usd * 0.50, 3000.0)
                    qty = max(1, int(trade_usd // entry_p))
                    req_cost = qty * entry_p

                    # Check cash; convert if JPY cash exists
                    if usd_cash < req_cost:
                        jpy_cash = balances.get("JPY", 0.0)
                        needed_jpy = (req_cost - usd_cash) * fx_rate * 1.02
                        if jpy_cash >= needed_jpy:
                            conv = broker_engine.convert_currency("JPY", "USD", round(req_cost - usd_cash + 50.0, 2))
                            if conv.get("success"):
                                usd_cash += conv["received"]

                    if usd_cash >= req_cost:
                        res = broker_engine.place_order(
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=entry_p,
                            target_price=tgt_p,
                            stop_loss_price=stp_p,
                            notes=f"[DAY cis需給スナイパー: {reason}]",
                            enforce_market_hours=enforce_market_hours,
                            strategy_type="DAY_CIS",
                            signal_timestamp=time.time()
                        )
                        if res.get("success"):
                            stock_info = MarketDataFeed.get_stock_data(sym)
                            c_name = stock_info.get("company_name", sym)
                            broker_engine.record_trade_memory(
                                symbol=sym,
                                company_name=c_name,
                                trade_type="BUY_ENTRY",
                                quantity=qty,
                                price=entry_p,
                                currency="USD",
                                trigger_rule="DAY_CIS_SNIPER",
                                thesis_at_entry=reason,
                                lesson_learned=f"支持壁反発・ダマシ防衛エントリー。目標: ${tgt_p:,.2f} / ストップ: ${stp_p:,.2f}"
                            )
                            HedgeFundNotifier.notify_trade(
                                symbol=sym,
                                company_name=c_name,
                                side="BUY",
                                quantity=qty,
                                price=entry_p,
                                currency="USD",
                                rule_type="DAY_CIS_SNIPER",
                                notes=f"⚡ cis需給スナイパー買い約定: {reason}",
                                target_price=tgt_p,
                                stop_loss_price=stp_p
                            )
                            logs.append(f"[{now_str}] ⚡ 🎯 【cis需給スナイパー買い約定】{c_name} ({sym}) {qty}株 @ ${entry_p:,.2f} (目標: ${tgt_p:,.2f} / 損切り: ${stp_p:,.2f} [ATRバッファ付]) - 理由: {reason}")
                            opened_orders.append(res)
                            held_day_syms.add(sym)
                            usd_cash -= req_cost
                            if len(held_day_syms) >= 2:
                                break
            except Exception as e_snip:
                logs.append(f"[{now_str}] ⚠️ cisスナイパー計算スキップ ({sym}): {e_snip}")

        return {"opened_orders": opened_orders, "logs": logs}
