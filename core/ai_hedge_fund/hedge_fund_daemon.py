# -*- coding: utf-8 -*-
import threading
import time
import datetime
import os
import json
from typing import Dict, Any, List, Optional
from core.ai_hedge_fund.auto_trader import AutoTrader
from core.ai_hedge_fund.market_screener import MarketScreener
from core.ai_hedge_fund.hedge_fund_notifier import HedgeFundNotifier
from core.ai_hedge_fund.market_session import MarketSession
from core.ai_hedge_fund.broker_client import PaperTradingEngine

class HedgeFundDaemon:
    """
    Lumina AI Autonomous Hedge Fund: Standing Background Daemon
    Runs continuous hands-free market patrols, debate synthesis, auto-buys,
    and automatic take-profit / stop-loss monitoring on a recurring interval.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HedgeFundDaemon, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.is_running = False
        self._was_previously_running = False
        self.interval_minutes = 15
        self.effective_interval_minutes = 15
        self.adaptive_desc = ""
        self.strategy = "ALL"
        self.max_new_orders = 2
        self.risk_budget_pct = 10.0
        self.enforce_market_hours = True
        self.capacity_mode = "AUTO"
        self.worker_thread: Optional[threading.Thread] = None
        self.watchdog_thread: Optional[threading.Thread] = None
        self.last_run_time: float = 0.0
        self.next_run_time: float = 0.0
        self.logs: List[str] = []
        self.total_cycles: int = 0
        self.total_buys: int = 0
        self.total_sells: int = 0
        self.engine = PaperTradingEngine()
        self._load_persisted_state()

    def _state_file_path(self) -> str:
        app_data_dir = os.path.join(os.getenv('APPDATA', ''), 'LuminaAI')
        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, 'hedge_fund_daemon_state.json')

    def _load_persisted_state(self):
        try:
            p = self._state_file_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._was_previously_running = bool(data.get("is_running", False))
                    self.interval_minutes = data.get("interval_minutes", 15)
                    self.strategy = data.get("strategy", "ALL")
                    self.max_new_orders = data.get("max_orders", 2)
                    self.enforce_market_hours = data.get("enforce_market_hours", True)
                    self.capacity_mode = data.get("capacity_mode", "AUTO")
                    self.total_cycles = data.get("total_cycles", 0)
                    self.total_buys = data.get("total_buys", 0)
                    self.total_sells = data.get("total_sells", 0)
                    self.logs = data.get("logs", [])[-500:]
        except Exception:
            pass

    def _persist_state(self):
        try:
            p = self._state_file_path()
            data = {
                "is_running": self.is_running,
                "interval_minutes": self.interval_minutes,
                "strategy": self.strategy,
                "max_orders": self.max_new_orders,
                "enforce_market_hours": self.enforce_market_hours,
                "capacity_mode": self.capacity_mode,
                "total_cycles": self.total_cycles,
                "total_buys": self.total_buys,
                "total_sells": self.total_sells,
                "last_run_time": self.last_run_time,
                "next_run_time": self.next_run_time,
                "logs": self.logs[-500:]
            }
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear_logs(self):
        """Clear activity log history"""
        self.logs = []
        self._persist_state()

    def reset_state(self):
        """Reset daemon statistics, cycles, and history back to 0"""
        self.total_cycles = 0
        self.total_buys = 0
        self.total_sells = 0
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs = [f"[{now_str}] 🔄 【シミュレーション初期化】口座・履歴・ログをリセットし、第1サイクルから再スタートしました。"]
        self._persist_state()

    def auto_resume_if_needed(self) -> bool:
        """Auto-resume daemon patrol if previously running before app restart/update"""
        for t in threading.enumerate():
            if t.name == "LuminaHedgeFundDaemonThread" and t.is_alive():
                self.is_running = True
                self.worker_thread = t
            elif t.name == "LuminaPositionWatchdogSentinelThread" and t.is_alive():
                self.watchdog_thread = t

        if self.worker_thread and self.worker_thread.is_alive():
            if not (self.watchdog_thread and self.watchdog_thread.is_alive()):
                self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="LuminaPositionWatchdogSentinelThread")
                self.watchdog_thread.start()
            return True

        if getattr(self, '_was_previously_running', False) and not self.is_running:
            self.start_patrol(
                interval_minutes=self.interval_minutes,
                strategy=self.strategy,
                max_orders=self.max_new_orders,
                enforce_market_hours=self.enforce_market_hours,
                capacity_mode=getattr(self, "capacity_mode", "AUTO")
            )
            self._add_log("🔄 【自動復帰】アプリ再起動・更新を検知し、前回の自動売買パトロールを自動再開しました。")
            try:
                print("[HedgeFundDaemon] 🔄 Auto-resumed previous patrol session.")
            except Exception:
                pass
            return True
        return False

    def start_patrol(self, interval_minutes: int = 15, strategy: str = "ALL", max_orders: int = 2, enforce_market_hours: bool = True, capacity_mode: str = "AUTO"):
        """Start the background autonomous trading daemon"""
        for t in threading.enumerate():
            if t.name == "LuminaHedgeFundDaemonThread" and t.is_alive():
                self.is_running = True
                self._was_previously_running = True
                self.interval_minutes = interval_minutes
                self.strategy = strategy
                self.max_new_orders = max_orders
                self.enforce_market_hours = enforce_market_hours
                self.capacity_mode = capacity_mode
                self.worker_thread = t
                if not (self.watchdog_thread and self.watchdog_thread.is_alive()):
                    self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="LuminaPositionWatchdogSentinelThread")
                    self.watchdog_thread.start()
                self._persist_state()
                return

        if self.is_running and self.worker_thread and self.worker_thread.is_alive():
            if not (self.watchdog_thread and self.watchdog_thread.is_alive()):
                self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="LuminaPositionWatchdogSentinelThread")
                self.watchdog_thread.start()
            return

        self.is_running = True
        self._was_previously_running = True
        self.interval_minutes = interval_minutes
        self.strategy = strategy
        self.max_new_orders = max_orders
        self.enforce_market_hours = enforce_market_hours
        self.capacity_mode = capacity_mode
        self.worker_thread = threading.Thread(target=self._daemon_loop, daemon=True, name="LuminaHedgeFundDaemonThread")
        self.worker_thread.start()
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="LuminaPositionWatchdogSentinelThread")
        self.watchdog_thread.start()
        mode_label = "実発注API準拠（開場中のみ発注）" if enforce_market_hours else "24h常時約定テスト"
        cap_label = "🤖 AI動的おまかせ(5〜6銘柄)" if capacity_mode == "AUTO" else f"{capacity_mode}銘柄枠"
        self._add_log(f"🟢 【常時自動売買スタート】巡回間隔: {interval_minutes}分毎 | 戦略: {strategy} | 保有枠: {cap_label} | 発注制限: {mode_label} | ⚡ 高頻度リアルタイム番犬センチネル(10秒巡回)起動")
        self._persist_state()

    def stop_patrol(self):
        """Stop the background autonomous trading daemon"""
        self.is_running = False
        self._was_previously_running = False
        self._add_log("🛑 【常時自動売買ストップ】自律パトロールを停止しました")
        self._persist_state()

    def _add_log(self, msg: str):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{now_str}] {msg}"
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    def _daemon_loop(self):
        """Continuous background execution loop"""
        while self.is_running:
            now = time.time()
            self.last_run_time = now

            # AIアダプティブ巡回インターバル判定 (市場閉場時は自動で60分ギアチェンジ)
            effective_interval, adaptive_desc = MarketSession.get_adaptive_interval(
                default_interval_minutes=self.interval_minutes,
                strategy=self.strategy
            )
            self.effective_interval_minutes = effective_interval
            self.adaptive_desc = adaptive_desc
            self.next_run_time = now + (effective_interval * 60)

            try:
                # Market Session Status Check
                sess_info = MarketSession.get_market_status()
                self._add_log(f"⏰ 【市場オープン状況】{sess_info.get('status_desc')}")
                self._add_log(f"⚙️ 【巡回インターバル】{adaptive_desc}")

                # Periodic News Catalyst Stock Discovery & Watchlist Cleanup (Every 4 cycles or on 1st cycle)
                if self.total_cycles % 4 == 0:
                    try:
                        # 1. 監視リストの自律クリーンアップ（30日賞味期限・上限15銘柄維持）
                        held_pos = self.engine.get_positions()
                        held_syms = {p["symbol"] for p in held_pos}
                        graduated = MarketScreener.cleanup_expired_custom_watchlist(held_symbols=held_syms, max_age_days=30, max_capacity=15)
                        if graduated:
                            for g in graduated:
                                self._add_log(f"🎓 【監視リスト自律卒業】{g.get('name')} ({g.get('symbol')}) を自動卒業（理由: {g.get('graduation_reason')}）")

                        # 2. 新規好材料・適時開示ニューススキャン
                        self._add_log("📰 【ニュース速報巡回】直近の好材料・適時開示・カタリスト速報をAIスキャン中...")
                        discovered = MarketScreener.auto_discover_catalyst_stocks()
                        if discovered:
                            for disc in discovered:
                                self._add_log(f"🌟 【注目株自動発掘】{disc.get('name')} ({disc.get('symbol')}) を好材料検知により巡回監視銘柄へ自動追加しました！")
                            # Send Discord Rich Alert
                            HedgeFundNotifier.notify_discovery(discovered)
                        else:
                            self._add_log("📰 【ニュース速報巡回】現在、市場ヘッドラインに即時追加基準を満たす新規材料株はありません。")
                    except Exception as disc_err:
                        self._add_log(f"⚠️ ニュース発掘・クリーンアップエラー: {disc_err}")

                # 3. Phase 3: 週末自律研究・ブラックスワン極限ストレステスト（休場中の自動バックグラウンド実行）
                import datetime
                weekday = datetime.datetime.now().weekday()  # 5: Saturday, 6: Sunday
                if weekday in (5, 6) and (self.total_cycles % 6 == 0):
                    try:
                        from core.ai_hedge_fund.alpha_researcher import AlphaResearcher
                        from core.ai_hedge_fund.adversarial_simulator import AdversarialSimulator
                        self._add_log("🔬 【Phase 3 週末自律研究】市場休場を活用し、アルファ探索とブラックスワン・ストレステストをバックグラウンド実行中...")
                        s_res = AdversarialSimulator.run_stress_test()
                        self._add_log(f"🌪️ 【ストレステスト完了】最悪シナリオ: {s_res.get('worst_scenario_name')} (想定最大下落: {s_res.get('estimated_max_drawdown_pct')}%)")
                        a_res = AlphaResearcher.run_research_scan()
                        self._add_log(f"🕵️ 【特選アルファ発掘完了】今週のテーマ: 『{a_res.get('weekly_theme')}』 (Top {len(a_res.get('top_picks', []))} 銘柄選定)")

                        # 4. 週末特選有料note（来週上がる株・厳選本命）の自動下書き保存パイプライン
                        try:
                            from core.ai_hedge_fund.weekly_paid_note_pipeline import WeeklyPaidNotePipeline
                            if WeeklyPaidNotePipeline.should_run_weekly_draft():
                                self._add_log("💎 【週刊AIアルファ】来週上がる株の有料note下書き保存パイプラインを自動起動中...")
                                wn_res = WeeklyPaidNotePipeline.generate_and_publish_weekly_draft(force=False)
                                if wn_res.get("success") and not wn_res.get("skipped"):
                                    self._add_log(f"💎 【週刊AIアルファ】有料note下書き保存完了！ ({wn_res.get('title')[:35]}...) -> {wn_res.get('edit_url')}")
                        except Exception as _wn_err:
                            self._add_log(f"⚠️ 週刊有料note自動パイプラインエラー: {_wn_err}")
                    except Exception as res_err:
                        self._add_log(f"⚠️ 週末自律研究エラー: {res_err}")

                # Dynamically load latest AutoTrader logic
                try:
                    import importlib
                    import core.ai_hedge_fund.auto_trader as at_mod
                    importlib.reload(at_mod)
                    active_auto_trader = at_mod.AutoTrader
                except Exception:
                    active_auto_trader = AutoTrader

                cycle_res = active_auto_trader.run_autonomous_cycle(
                    broker_engine=self.engine,
                    strategy=self.strategy,
                    max_new_orders=self.max_new_orders,
                    risk_budget_pct=self.risk_budget_pct,
                    enforce_market_hours=getattr(self, "enforce_market_hours", True),
                    capacity_mode=getattr(self, "capacity_mode", "AUTO")
                )
                self.total_cycles += 1
                new_buys = len(cycle_res.get("opened_orders", []))
                new_sells = len(cycle_res.get("closed_orders", []))
                self.total_buys += new_buys
                self.total_sells += new_sells

                for l in cycle_res.get("logs", []):
                    self._add_log(l)

                # 📢 株式自動売買・推移速報の定期Xポスト判定 (15:45 / 21:30)
                try:
                    now_dt = datetime.datetime.now()
                    from core.state_manager import get_stock_report_scheduler_settings
                    stock_sched = get_stock_report_scheduler_settings()
                    if stock_sched.get("enabled", True):
                        st_times = stock_sched.get("times", ["15:45", "21:30"])
                        for target_t in st_times:
                            t_h, t_m = map(int, target_t.split(":"))
                            diff_min = abs((now_dt.hour * 60 + now_dt.minute) - (t_h * 60 + t_m))
                            if diff_min <= 15:
                                from core.ai_hedge_fund.fund_content_generator import FundContentGenerator
                                x_res = FundContentGenerator.post_daily_stock_report_to_x(force=False)
                                if x_res.get("success") and not x_res.get("skipped"):
                                    self._add_log(f"📢 【X推移速報自動ポスト】本日の運用推移レポートを公式Xに射出しました！ (ID: {x_res.get('tweet_id')})")
                except Exception as _x_err:
                    self._add_log(f"⚠️ X推移速報自律ポスト判定エラー: {_x_err}")

                # 📝 株式自動売買・損益日報の定期note投稿判定 (市場営業日の20:00頃)
                try:
                    now_dt = datetime.datetime.now()
                    stock_sched = get_stock_report_scheduler_settings()
                    if stock_sched.get("note_enabled", True) and MarketSession.is_tse_trading_day(now_dt.date()):
                        target_t = stock_sched.get("note_time", "20:00")
                        t_h, t_m = map(int, target_t.split(":"))
                        diff_min = abs((now_dt.hour * 60 + now_dt.minute) - (t_h * 60 + t_m))
                        if diff_min <= 20:
                            from core.ai_hedge_fund.fund_content_generator import FundContentGenerator
                            note_res = FundContentGenerator.post_daily_stock_report_to_note(force=False)
                            if note_res.get("success") and not note_res.get("skipped"):
                                st_label = "下書き保存" if note_res.get("status") == "draft" else "自動公開"
                                self._add_log(f"📝 【note損益日報自動投稿】本日（{now_dt.strftime('%m/%d')}）の損益日報をnoteへ{st_label}しました！ ({note_res.get('url') or note_res.get('edit_url')})")
                except Exception as _note_err:
                    self._add_log(f"⚠️ note損益日報自律投稿判定エラー: {_note_err}")

                self._persist_state()
            except Exception as e:
                self._add_log(f"⚠️ 自律実行サイクルエラー: {e}")

            # Sleep in 1-second chunks for responsive cancellation
            while self.is_running and time.time() < self.next_run_time:
                time.sleep(1)

    def _watchdog_loop(self):
        """
        High-Frequency Realtime Position Watchdog Sentinel (Sub-minute / 5〜10s loop)
        Patrols held positions continuously during open market hours.
        Intercepts flash-crashes and sudden profit peaks to execute Exit Rules within seconds.
        """
        while self.is_running:
            try:
                positions = self.engine.get_positions()
                if positions:
                    has_open_market = False
                    for pos in positions:
                        sym = pos.get("symbol", "")
                        is_jp = sym.endswith(".T")
                        if is_jp and MarketSession.is_tse_open():
                            has_open_market = True
                            break
                        elif not is_jp and MarketSession.is_us_open():
                            has_open_market = True
                            break

                    if not self.enforce_market_hours or has_open_market:
                        try:
                            import importlib
                            import core.ai_hedge_fund.auto_trader as at_mod
                            importlib.reload(at_mod)
                            active_at = at_mod.AutoTrader
                        except Exception:
                            active_at = AutoTrader

                        patrol_res = active_at.patrol_positions(self.engine, enforce_market_hours=self.enforce_market_hours)
                        closed_orders = patrol_res.get("closed_orders", [])
                        if closed_orders:
                            self.total_sells += len(closed_orders)
                            for l in patrol_res.get("logs", []):
                                self._add_log(f"⚡ [番犬センチネル即時執行] {l}")
                            self._persist_state()
            except Exception:
                pass

            # Sleep 10 seconds in 1-second chunks for responsive cancellation
            for _ in range(10):
                if not self.is_running:
                    break
                time.sleep(1)

    def get_status(self) -> Dict[str, Any]:
        """Get live status and next run timer"""
        remaining_seconds = max(0, int(self.next_run_time - time.time())) if self.is_running else 0
        rem_min = remaining_seconds // 60
        rem_sec = remaining_seconds % 60
        countdown_str = f"{rem_min}分{rem_sec:02d}秒後" if self.is_running else "停止中"

        return {
            "is_running": self.is_running,
            "watchdog_active": bool(self.watchdog_thread and self.watchdog_thread.is_alive()),
            "interval_minutes": self.interval_minutes,
            "effective_interval_minutes": getattr(self, "effective_interval_minutes", self.interval_minutes),
            "adaptive_desc": getattr(self, "adaptive_desc", ""),
            "strategy": self.strategy,
            "capacity_mode": getattr(self, "capacity_mode", "AUTO"),
            "total_cycles": self.total_cycles,
            "total_buys": self.total_buys,
            "total_sells": self.total_sells,
            "countdown_str": countdown_str,
            "logs": self.logs[-30:]
        }
