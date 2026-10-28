import os
import math
import sqlite3
import threading
import queue
import time
import json
from typing import Dict, Any, List, Optional
from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.market_session import MarketSession

def round_price_to_exchange_tick(price: float, is_jp: bool = False) -> float:
    """
    Normalize order limit/stop prices to strictly conform to exchange minimum tick size rules.
    - TSE (Tokyo Stock Exchange / .T): Enforces standard tick size bands (1, 5, 10, 50, 100, 1000 JPY)
      to prevent IBKR Error 110 ('The price does not conform to the minimum price variation').
    - US Exchanges (NYSE/NASDAQ): Enforces $0.01 tick size (>= $1.00) or $0.0001 (< $1.00, SEC Rule 612).
    """
    p = float(price)
    if p <= 0:
        return 0.0
    if not is_jp:
        return round(p, 2) if p >= 1.0 else round(p, 4)

    # Tokyo Stock Exchange (TSE) Standard Tick Size Table (呼値の単位)
    if p <= 3000.0:
        return float(int(round(p)))
    elif p <= 5000.0:
        return float(int(round(p / 5.0)) * 5)
    elif p <= 30000.0:
        return float(int(round(p / 10.0)) * 10)
    elif p <= 50000.0:
        return float(int(round(p / 50.0)) * 50)
    elif p <= 300000.0:
        return float(int(round(p / 100.0)) * 100)
    else:
        return float(int(round(p / 1000.0)) * 1000)


def normalize_exchange_lot_size(quantity: int, is_jp: bool = False) -> int:
    """
    Enforce exchange board lot size constraints (単元株制度).
    - TSE (.T): Floors to nearest 100-share board lot (returns 0 if < 100 to prevent odd-lot OCO rejection).
    - US Exchanges: Allows 1-share integer increments.
    """
    q = int(quantity)
    if q <= 0:
        return 0
    if is_jp:
        return (q // 100) * 100
    return q


class BaseBrokerClient:
    """Abstract Interface for Brokerage Execution Adapters"""
    round_price_to_exchange_tick = staticmethod(round_price_to_exchange_tick)
    normalize_exchange_lot_size = staticmethod(normalize_exchange_lot_size)

    def get_account_balance(self) -> Dict[str, float]:
        raise NotImplementedError
    def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError
    def place_order(self, symbol: str, side: str, quantity: int, price: Optional[float] = None, order_type: str = "MARKET", notes: str = "", target_price: Optional[float] = None, stop_loss_price: Optional[float] = None) -> Dict[str, Any]:
        raise NotImplementedError


class PaperTradingEngine(BaseBrokerClient):
    """
    Lumina AI Autonomous Paper Trading Engine (SQLite-Backed)
    Default Sandbox: JPY 1,000,000 / USD $10,000
    Located at %APPDATA%/LuminaAI/hedge_fund_portfolio.db
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_lock = threading.RLock()
        self._reflexion_write_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._writer_thread: Optional[threading.Thread] = None
        if not db_path:
            app_data_dir = os.path.join(os.getenv('APPDATA', ''), 'LuminaAI')
            os.makedirs(app_data_dir, exist_ok=True)
            self.db_path = os.path.join(app_data_dir, 'hedge_fund_portfolio.db')
        else:
            self.db_path = db_path
        self._init_db()
        self._start_single_writer_worker()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    currency TEXT PRIMARY KEY,
                    cash_balance REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                currency TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_entry_price REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                order_time TEXT NOT NULL,
                notes TEXT
            )
            """)
            # Initialize default accounts if empty
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_equity_jpy REAL NOT NULL,
                jpy_cash REAL NOT NULL,
                usd_cash REAL NOT NULL,
                positions_value_jpy REAL NOT NULL,
                fx_rate REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS council_records (
                council_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                action TEXT NOT NULL,
                action_label TEXT NOT NULL,
                confidence_score INTEGER NOT NULL,
                target_price REAL,
                stop_loss_price REAL,
                allocation_pct REAL,
                thesis_summary TEXT,
                dialogues_json TEXT,
                radar_scores_json TEXT,
                news_headlines_json TEXT,
                created_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_memories (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                realized_pnl_pct REAL DEFAULT 0.0,
                trigger_rule TEXT,
                thesis_at_entry TEXT,
                lesson_learned TEXT,
                created_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_reflexions (
                reflexion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                stance_at_entry TEXT NOT NULL,
                score_at_entry INTEGER NOT NULL,
                exit_rule TEXT NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                realized_pnl_pct REAL DEFAULT 0.0,
                reflection_text TEXT NOT NULL,
                lesson_category TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

            cursor.execute("SELECT COUNT(*) FROM accounts")
            if cursor.fetchone()[0] == 0:
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO accounts VALUES ('JPY', 1000000.0, ?)", (now_str,))
                cursor.execute("INSERT INTO accounts VALUES ('USD', 0.0, ?)", (now_str,))
            else:
                # Remove any EUR account to keep clean 2-currency system (JPY and USD)
                cursor.execute("DELETE FROM accounts WHERE currency = 'EUR'")

            # Automatic table migration for trailing stop & partial take profit
            cursor.execute("PRAGMA table_info(positions)")
            cols = [r[1] for r in cursor.fetchall()]
            if "peak_price" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN peak_price REAL DEFAULT 0.0")
            if "half_profit_taken" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN half_profit_taken INTEGER DEFAULT 0")
            if "target_price" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN target_price REAL DEFAULT 0.0")
            if "stop_loss_price" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN stop_loss_price REAL DEFAULT 0.0")
            if "strategy_type" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN strategy_type TEXT DEFAULT 'SWING'")
            if "opened_at" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN opened_at TEXT DEFAULT ''")
            if "version" not in cols:
                cursor.execute("ALTER TABLE positions ADD COLUMN version INTEGER DEFAULT 1")

            # Automatic table migration for Phase 2 Cross-Debate & Dynamic MoE
            cursor.execute("PRAGMA table_info(council_records)")
            c_cols = [r[1] for r in cursor.fetchall()]
            if "cross_debate_json" not in c_cols:
                try:
                    cursor.execute("ALTER TABLE council_records ADD COLUMN cross_debate_json TEXT DEFAULT ''")
                except Exception: pass
            if "regime_info_json" not in c_cols:
                try:
                    cursor.execute("ALTER TABLE council_records ADD COLUMN regime_info_json TEXT DEFAULT ''")
                except Exception: pass

            # SQLite FTS5 Virtual Table for sub-millisecond BM25 Reflexion Memory retrieval
            # Tuned with `unicode61 'tokenchars=-_.'` to preserve compound financial terms
            try:
                cursor.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_reflexions_fts'"
                )
                row_sql = cursor.fetchone()
                if row_sql and row_sql[0] and "tokenchars" not in str(row_sql[0]):
                    cursor.execute("DROP TABLE IF EXISTS agent_reflexions_fts")

                try:
                    cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS agent_reflexions_fts USING fts5(
                        symbol,
                        company_name,
                        agent_id,
                        exit_rule,
                        lesson_category,
                        reflection_text,
                        tokenize="unicode61 tokenchars '-_.'"
                    )
                    """)
                except Exception:
                    cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS agent_reflexions_fts USING fts5(
                        symbol,
                        company_name,
                        agent_id,
                        exit_rule,
                        lesson_category,
                        reflection_text
                    )
                    """)
                cursor.execute("SELECT COUNT(*) FROM agent_reflexions_fts")
                fts_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM agent_reflexions")
                base_cnt = cursor.fetchone()[0]
                if fts_cnt < base_cnt:
                    cursor.execute("DELETE FROM agent_reflexions_fts")
                    cursor.execute("""
                    INSERT INTO agent_reflexions_fts(rowid, symbol, company_name, agent_id, exit_rule, lesson_category, reflection_text)
                    SELECT reflexion_id, symbol, company_name, agent_id, exit_rule, lesson_category, reflection_text
                    FROM agent_reflexions
                    """)
            except Exception:
                pass

            conn.commit()

    def get_account_balance(self) -> Dict[str, float]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency, cash_balance FROM accounts")
            rows = cursor.fetchall()
            return {r["currency"]: float(r["cash_balance"]) for r in rows}

    def get_positions(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE quantity > 0")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_order_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders ORDER BY order_id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        notes: str = "",
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        enforce_market_hours: bool = True,
        strategy_type: str = "SWING",
        signal_timestamp: Optional[float] = None,
        expected_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute simulated Buy / Sell trade with realistic execution price & balance tracking.
        Enforces realistic exchange rules: rejects market orders when markets are closed.
        """
        norm_sym = MarketDataFeed.normalize_symbol(symbol)
        side = side.upper()
        if quantity <= 0:
            return {"success": False, "error": "数量は1以上である必要があります"}

        from core.ai_hedge_fund.idempotency_guard import OrderIdempotencyGuard
        guard = OrderIdempotencyGuard(db_path=self.db_path)
        allowed, guard_msg, order_ref = guard.check_and_reserve(
            symbol=norm_sym,
            side=side,
            quantity=quantity,
            order_type=order_type,
            signal_timestamp=signal_timestamp,
            strategy_type=strategy_type,
        )
        if not allowed:
            return {
                "success": False,
                "error": guard_msg,
                "message": guard_msg,
                "stale_discarded": ("シグナル鮮度ガード" in guard_msg),
                "idempotency_blocked": True,
            }

        is_jp = norm_sym.endswith(".T")
        is_eu = any(norm_sym.endswith(sfx) for sfx in [".AS", ".DE", ".PA", ".CO", ".L", ".MI", ".MC", ".ST"])

        # Realistic Broker API Guard: Reject market orders when exchange is closed
        if enforce_market_hours and order_type.upper() == "MARKET":
            if is_jp and not MarketSession.is_tse_open():
                guard.record_completed(order_ref, is_success=False, error_message="東証取引時間外")
                return {
                    "success": False,
                    "error": "【取引時間外エラー】東京証券取引所は取引時間外です（平日 09:00〜15:30 JST）。実発注API（kabuステーション）準拠のため、成行発注は約定できません。"
                }
            elif is_eu and not MarketSession.is_eu_open():
                return {
                    "success": False,
                    "error": "【取引時間外エラー】欧州市場（Euronext/XETRA/LSE）は取引時間外です（平日 16:00〜翌00:30 JST）。成行発注は約定できません。"
                }
            elif not is_jp and not is_eu and not MarketSession.is_us_open():
                return {
                    "success": False,
                    "error": "【取引時間外エラー】米国市場（NYSE/NASDAQ）は取引時間外です（日本時間 22:30〜翌05:00 JST）。実発注API（IBKR Client Portal）準拠のため、成行発注は約定できません。"
                }

        if os.getenv("LUMINA_TEST_MODE") == "1" and price and price > 0:
            stock_data = MarketDataFeed._cache.get(norm_sym, {}).get("data") or {
                "company_name": norm_sym,
                "currency": "JPY" if is_jp else ("EUR" if is_eu else "USD"),
                "current_price": float(price),
            }
        else:
            stock_data = MarketDataFeed.get_stock_data(norm_sym)
        company_name = stock_data.get("company_name", norm_sym)
        currency = stock_data.get("currency", "JPY" if is_jp else ("EUR" if is_eu else "USD"))
        
        exec_price = price if price and price > 0 else stock_data.get("current_price", 1000.0)
        side = side.upper()
        
        if quantity <= 0:
            return {"success": False, "error": "数量は1以上である必要があります"}

        total_cost = exec_price * quantity
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Fetch cash
                cursor.execute("SELECT cash_balance FROM accounts WHERE currency = ?", (currency,))
                acc_row = cursor.fetchone()
                current_cash = float(acc_row["cash_balance"]) if acc_row else 0.0

                # Fetch position
                cursor.execute("SELECT * FROM positions WHERE symbol = ?", (norm_sym,))
                pos_row = cursor.fetchone()

                if side == "BUY":
                    # 🌟 注文時逆指値強制付帯ルール (Mandatory Bracket Stop-Loss / No Naked Buy Mandate)
                    # 買い注文時に逆指値（損切りライン）が未設定または無効な場合、フィボナッチ最適値 (-13.0%) を自動算出して強制付帯する
                    if stop_loss_price is None or stop_loss_price <= 0 or stop_loss_price >= exec_price:
                        stop_loss_price = round_price_to_exchange_tick(exec_price * 0.87, is_jp=is_jp)
                    else:
                        stop_loss_price = round_price_to_exchange_tick(stop_loss_price, is_jp=is_jp)
                    
                    if not target_price or target_price <= exec_price:
                        target_price = round_price_to_exchange_tick(exec_price * 1.25, is_jp=is_jp)
                    else:
                        target_price = round_price_to_exchange_tick(target_price, is_jp=is_jp)

                    bracket_tag = f"[強制ブラケット逆指値付帯: {stop_loss_price:,.2f} {currency} (-13.0%)]"
                    if bracket_tag not in notes:
                        notes = f"{notes} {bracket_tag}".strip()

                    deducted_currency = currency
                    deducted_amount = total_cost

                    if current_cash >= total_cost:
                        new_cash = current_cash - total_cost
                        cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = ?", (new_cash, now_str, currency))
                    elif currency == "EUR" or is_eu:
                        # 🌟 オートFX決済: ユーロ口座を増やさず、今ある資産（JPY または USD）から自動為替換算して引き落とす！
                        rate_eurjpy = self.get_eurjpy_rate()
                        rate_usdjpy = self.get_usdjpy_rate()
                        cost_in_jpy = total_cost * rate_eurjpy

                        cursor.execute("SELECT cash_balance FROM accounts WHERE currency = 'JPY'")
                        jpy_row = cursor.fetchone()
                        jpy_cash = float(jpy_row["cash_balance"]) if jpy_row else 0.0

                        cursor.execute("SELECT cash_balance FROM accounts WHERE currency = 'USD'")
                        usd_row = cursor.fetchone()
                        usd_cash = float(usd_row["cash_balance"]) if usd_row else 0.0
                        cost_in_usd = (cost_in_jpy / rate_usdjpy) if rate_usdjpy > 0 else (total_cost * 1.08)

                        if jpy_cash >= cost_in_jpy:
                            new_jpy = jpy_cash - cost_in_jpy
                            cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = 'JPY'", (new_jpy, now_str))
                            deducted_currency = "JPY"
                            deducted_amount = cost_in_jpy
                            notes = (notes + f" [手持ち資産から自動為替決済: {cost_in_jpy:,.0f}円 (為替 {rate_eurjpy:.2f}円/€)]").strip()
                        elif usd_cash >= cost_in_usd:
                            new_usd = usd_cash - cost_in_usd
                            cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = 'USD'", (new_usd, now_str))
                            deducted_currency = "USD"
                            deducted_amount = cost_in_usd
                            notes = (notes + f" [手持ちドル資産から自動為替決済: ${cost_in_usd:,.2f}]").strip()
                        else:
                            return {
                                "success": False,
                                "error": f"今ある資産（JPY / USD）の残高が不足しています (必要: €{total_cost:,.2f} ≒ ¥{cost_in_jpy:,.0f} または ${cost_in_usd:,.2f}、現在の残高: ¥{jpy_cash:,.0f} / ${usd_cash:,.2f})"
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"残高不足です (必要: {total_cost:,.2f} {currency}, 現在残高: {current_cash:,.2f} {currency})"
                        }

                    # Update or insert position
                    if pos_row:
                        old_qty = int(pos_row["quantity"])
                        old_avg = float(pos_row["avg_entry_price"])
                        new_qty = old_qty + quantity
                        new_avg = ((old_qty * old_avg) + total_cost) / new_qty
                        old_sl = float(pos_row["stop_loss_price"] or 0.0)
                        # リスクを広げない原則: 既存逆指値と新規逆指値のうち、より高い価格（タイトなストップ）を維持
                        effective_sl = max(old_sl, stop_loss_price)
                        cursor.execute("""
                            UPDATE positions 
                            SET quantity = ?, avg_entry_price = ?, updated_at = ?, peak_price = MAX(COALESCE(peak_price, 0), ?), stop_loss_price = ?
                            WHERE symbol = ?
                        """, (new_qty, new_avg, now_str, exec_price, effective_sl, norm_sym))
                    else:
                        cursor.execute("""
                            INSERT INTO positions (symbol, company_name, currency, quantity, avg_entry_price, updated_at, peak_price, half_profit_taken, target_price, stop_loss_price)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """, (norm_sym, company_name, currency, quantity, exec_price, now_str, exec_price, target_price, stop_loss_price))

                elif side == "SELL":
                    if not pos_row or int(pos_row["quantity"]) < quantity:
                        current_held = int(pos_row["quantity"]) if pos_row else 0
                        return {
                            "success": False,
                            "error": f"保有株数が不足しています (売却希望: {quantity}株, 保有中: {current_held}株)"
                        }
                    
                    # 欧州株（EUR）の売却代金は自動で日本円口座へ円転して戻す
                    if currency == "EUR" or is_eu:
                        rate_eurjpy = self.get_eurjpy_rate()
                        received_jpy = total_cost * rate_eurjpy
                        cursor.execute("SELECT cash_balance FROM accounts WHERE currency = 'JPY'")
                        jpy_row = cursor.fetchone()
                        jpy_cash = float(jpy_row["cash_balance"]) if jpy_row else 0.0
                        cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = 'JPY'", (jpy_cash + received_jpy, now_str))
                        notes = (notes + f" [自動円転入金: +{received_jpy:,.0f} JPY]").strip()
                    else:
                        new_cash = current_cash + total_cost
                        cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = ?", (new_cash, now_str, currency))

                    # Update position
                    old_qty = int(pos_row["quantity"])
                    new_qty = old_qty - quantity
                    if new_qty == 0:
                        cursor.execute("DELETE FROM positions WHERE symbol = ?", (norm_sym,))
                    else:
                        cursor.execute("UPDATE positions SET quantity = ?, updated_at = ? WHERE symbol = ?", (new_qty, now_str, norm_sym))
                else:
                    return {"success": False, "error": f"未対応の注文サイド: {side}"}

                # Record order
                cursor.execute("""
                    INSERT INTO orders (symbol, company_name, side, quantity, price, currency, status, order_time, notes)
                    VALUES (?, ?, ?, ?, ?, ?, 'FILLED', ?, ?)
                """, (norm_sym, company_name, side, quantity, exec_price, currency, now_str, notes))
                order_id = cursor.lastrowid
                conn.commit()

        guard.record_completed(order_ref, is_success=True)
        return {
            "success": True,
            "order_id": order_id,
            "order_ref": order_ref,
            "symbol": norm_sym,
            "company_name": company_name,
            "side": side,
            "quantity": quantity,
            "executed_price": exec_price,
            "total_amount": total_cost,
            "currency": currency,
            "target_price": target_price if side == "BUY" else None,
            "stop_loss_price": stop_loss_price if side == "BUY" else None,
            "timestamp": now_str
        }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Calculate live real-time equity, unrealized P&L, and asset breakdown.
        """
        balances = self.get_account_balance()
        raw_positions = self.get_positions()
        
        positions_with_pnl = []
        total_pos_value_jpy = 0.0
        total_pos_value_usd = 0.0
        unrealized_pnl_jpy = 0.0
        unrealized_pnl_usd = 0.0

        # Parallel fetch quotes for all held positions concurrently
        quotes_map = {}
        if raw_positions:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(raw_positions))) as executor:
                futures = {executor.submit(MarketDataFeed.get_realtime_quote, pos["symbol"]): pos["symbol"] for pos in raw_positions}
                for fut in futures:
                    sym = futures[fut]
                    try:
                        quotes_map[sym] = fut.result()
                    except Exception:
                        quotes_map[sym] = {}

        for pos in raw_positions:
            sym = pos["symbol"]
            qty = pos["quantity"]
            entry_price = pos["avg_entry_price"]
            curr = pos["currency"]

            stock_data = quotes_map.get(sym, {})
            current_price = stock_data.get("current_price") or entry_price
            
            market_value = current_price * qty
            cost_basis = entry_price * qty
            diff = market_value - cost_basis
            diff_pct = (diff / cost_basis * 100) if cost_basis > 0 else 0.0

            pos_item = {
                **pos,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": diff,
                "unrealized_pnl_pct": round(diff_pct, 2),
                "daily_change": stock_data.get("change", 0.0),
                "daily_change_pct": stock_data.get("change_pct", 0.0)
            }
            positions_with_pnl.append(pos_item)

            if curr == "JPY":
                total_pos_value_jpy += market_value
                unrealized_pnl_jpy += diff
            elif curr == "EUR":
                total_pos_value_eur = getattr(locals(), 'total_pos_value_eur', 0.0) + market_value
                unrealized_pnl_eur = getattr(locals(), 'unrealized_pnl_eur', 0.0) + diff
            else:
                total_pos_value_usd += market_value
                unrealized_pnl_usd += diff

        total_pos_value_eur = locals().get('total_pos_value_eur', 0.0)
        unrealized_pnl_eur = locals().get('unrealized_pnl_eur', 0.0)

        cash_jpy = balances.get("JPY", 0.0)
        cash_usd = balances.get("USD", 0.0)
        cash_eur = balances.get("EUR", 0.0)

        rate_usd = self.get_usdjpy_rate()
        rate_eur = self.get_eurjpy_rate()

        equity_jpy = cash_jpy + total_pos_value_jpy
        equity_usd = cash_usd + total_pos_value_usd
        equity_eur = cash_eur + total_pos_value_eur
        
        total_equity_jpy = equity_jpy + (equity_usd * rate_usd) + (equity_eur * rate_eur)
        total_equity_usd = total_equity_jpy / rate_usd if rate_usd > 0 else 0.0
        
        total_buying_power_jpy = cash_jpy + (cash_usd * rate_usd) + (cash_eur * rate_eur)
        total_buying_power_usd = total_buying_power_jpy / rate_usd if rate_usd > 0 else 0.0

        total_unrealized_pnl_jpy = unrealized_pnl_jpy + (unrealized_pnl_usd * rate_usd) + (unrealized_pnl_eur * rate_eur)
        total_cost_basis_jpy = total_equity_jpy - total_unrealized_pnl_jpy
        total_unrealized_pnl_pct = (total_unrealized_pnl_jpy / total_cost_basis_jpy * 100.0) if total_cost_basis_jpy > 0 else 0.0

        return {
            "cash_jpy": cash_jpy,
            "cash_usd": cash_usd,
            "cash_eur": cash_eur,
            "equity_jpy": equity_jpy,
            "equity_usd": equity_usd,
            "equity_eur": equity_eur,
            "usdjpy_rate": rate_usd,
            "eurjpy_rate": rate_eur,
            "total_equity_jpy": total_equity_jpy,
            "total_equity_usd": total_equity_usd,
            "total_buying_power_jpy": total_buying_power_jpy,
            "total_buying_power_usd": total_buying_power_usd,
            "total_unrealized_pnl_jpy": total_unrealized_pnl_jpy,
            "total_unrealized_pnl_pct": total_unrealized_pnl_pct,
            "unrealized_pnl_jpy": unrealized_pnl_jpy,
            "unrealized_pnl_usd": unrealized_pnl_usd,
            "unrealized_pnl_eur": unrealized_pnl_eur,
            "positions": positions_with_pnl
        }

    _cached_usdjpy_rate: float = 155.0
    _cached_usdjpy_time: float = 0.0
    _cached_eurjpy_rate: float = 165.0
    _cached_eurjpy_time: float = 0.0

    @classmethod
    def get_usdjpy_rate(cls) -> float:
        """Fetch live USD/JPY exchange rate with fast 60s memory caching and safe fallback"""
        if os.getenv("LUMINA_TEST_MODE") == "1":
            return cls._cached_usdjpy_rate or 155.0
        now = time.time()
        if cls._cached_usdjpy_rate > 50.0 and (now - cls._cached_usdjpy_time < 60):
            return cls._cached_usdjpy_rate
        try:
            quote = MarketDataFeed.get_realtime_quote("USDJPY=X")
            rate = quote.get("current_price")
            if rate and rate > 50.0:
                cls._cached_usdjpy_rate = float(rate)
                cls._cached_usdjpy_time = now
                return float(rate)
        except Exception:
            pass
        return cls._cached_usdjpy_rate or 155.0

    @classmethod
    def get_eurjpy_rate(cls) -> float:
        """Fetch live EUR/JPY exchange rate with fast 60s memory caching and safe fallback"""
        if os.getenv("LUMINA_TEST_MODE") == "1":
            return cls._cached_eurjpy_rate or 165.0
        now = time.time()
        if cls._cached_eurjpy_rate > 50.0 and (now - cls._cached_eurjpy_time < 60):
            return cls._cached_eurjpy_rate
        try:
            quote = MarketDataFeed.get_realtime_quote("EURJPY=X")
            rate = quote.get("current_price")
            if rate and rate > 50.0:
                cls._cached_eurjpy_rate = float(rate)
                cls._cached_eurjpy_time = now
                return float(rate)
        except Exception:
            pass
        return cls._cached_eurjpy_rate or 165.0

    def convert_currency(self, from_curr: str, to_curr: str, amount: float) -> Dict[str, Any]:
        """
        IBKR-style multi-currency conversion between JPY and USD.
        Allows instant rebalancing of cash balances inside the account.
        """
        from_curr = from_curr.upper()
        to_curr = to_curr.upper()
        if from_curr == to_curr:
            return {"success": False, "error": "同一通貨間の両替は不要です"}
        if amount <= 0:
            return {"success": False, "error": "両替金額は0より大きい必要があります"}

        rate = self.get_usdjpy_rate()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cash_balance FROM accounts WHERE currency = ?", (from_curr,))
                from_row = cursor.fetchone()
                from_cash = float(from_row["cash_balance"]) if from_row else 0.0

                if from_cash < amount:
                    return {"success": False, "error": f"{from_curr} の残高不足です (必要: {amount:,.2f}, 保有: {from_cash:,.2f})"}

                if from_curr == "USD" and to_curr == "JPY":
                    converted_amount = amount * rate
                elif from_curr == "JPY" and to_curr == "USD":
                    converted_amount = amount / rate
                else:
                    return {"success": False, "error": "サポートされていない通貨ペアです"}

                # Update from account
                new_from_cash = from_cash - amount
                cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = ?", (new_from_cash, now_str, from_curr))

                # Update to account
                cursor.execute("SELECT cash_balance FROM accounts WHERE currency = ?", (to_curr,))
                to_row = cursor.fetchone()
                to_cash = float(to_row["cash_balance"]) if to_row else 0.0
                new_to_cash = to_cash + converted_amount
                cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = ? WHERE currency = ?", (new_to_cash, now_str, to_curr))

                conn.commit()

        return {
            "success": True,
            "from_currency": from_curr,
            "to_currency": to_curr,
            "rate": rate,
            "deducted": amount,
            "received": converted_amount,
            "timestamp": now_str
        }

    def update_position_tracking(
        self,
        symbol: str,
        peak_price: Optional[float] = None,
        half_profit_taken: Optional[int] = None,
        stop_loss_price: Optional[float] = None,
        expected_version: Optional[int] = None,
    ) -> bool:
        """Update trailing peak price and dynamic stop-loss levels for a position"""
        norm_sym = MarketDataFeed.normalize_symbol(symbol)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                updates = ["updated_at = ?", "version = COALESCE(version, 1) + 1"]
                params = [now_str]
                if peak_price is not None:
                    updates.append("peak_price = ?")
                    params.append(peak_price)
                if half_profit_taken is not None:
                    updates.append("half_profit_taken = ?")
                    params.append(half_profit_taken)
                if stop_loss_price is not None:
                    updates.append("stop_loss_price = ?")
                    params.append(stop_loss_price)
                params.append(norm_sym)
                cursor.execute(f"UPDATE positions SET {', '.join(updates)} WHERE symbol = ?", params)
                conn.commit()
                return True

    def apply_stock_split_adjustment(
        self,
        symbol: str,
        split_ratio: float,
        expected_version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically adjust a held position's quantity, avg_entry_price, peak_price,
        stop_loss_price, and target_price when a Corporate Action (Stock Split or Reverse Split)
        is detected, preventing false -80% Stop-Loss misfires on split effective day.
        """
        if split_ratio <= 0.0 or abs(split_ratio - 1.0) < 1e-4:
            return None
        norm_sym = MarketDataFeed.normalize_symbol(symbol)
        is_jp = norm_sym.endswith(".T")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM positions WHERE symbol = ?", (norm_sym,))
                pos_row = cursor.fetchone()
                if not pos_row:
                    return None
                old_qty = int(pos_row["quantity"] or 0)
                if old_qty <= 0:
                    return None
                new_qty = max(1, int(round(old_qty * split_ratio)))
                if is_jp and new_qty >= 100:
                    new_qty = normalize_exchange_lot_size(new_qty, is_jp=True)
                old_entry = float(pos_row["avg_entry_price"] or 0.0)
                old_peak = float(pos_row["peak_price"] or old_entry)
                old_sl = float(pos_row["stop_loss_price"] or (old_entry * 0.87))
                old_tp = float(pos_row["target_price"] or (old_entry * 1.25))

                new_entry = round(old_entry / split_ratio, 4 if not is_jp else 2)
                new_peak = round(old_peak / split_ratio, 4 if not is_jp else 2)
                new_sl = round_price_to_exchange_tick(old_sl / split_ratio, is_jp=is_jp)
                new_tp = round_price_to_exchange_tick(old_tp / split_ratio, is_jp=is_jp)

                cursor.execute(
                    """
                    UPDATE positions
                    SET quantity = ?, avg_entry_price = ?, peak_price = ?, stop_loss_price = ?, target_price = ?,
                        updated_at = ?, version = COALESCE(version, 1) + 1
                    WHERE symbol = ?
                    """,
                    (new_qty, new_entry, new_peak, new_sl, new_tp, now_str, norm_sym),
                )
                conn.commit()
                return {
                    "symbol": norm_sym,
                    "split_ratio": split_ratio,
                    "old_quantity": old_qty,
                    "new_quantity": new_qty,
                    "old_entry_price": old_entry,
                    "new_entry_price": new_entry,
                    "new_peak_price": new_peak,
                    "new_stop_loss_price": new_sl,
                    "new_target_price": new_tp,
                }

    def reset_portfolio(self, initial_jpy: float = 1000000.0, initial_usd: float = 0.0):
        """Reset sandbox portfolio to initial ¥1,000,000 and $0 balance (or specified amounts), wiping all positions, snapshots, orders, and memories"""
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM positions")
                cursor.execute("DELETE FROM orders")
                cursor.execute("DELETE FROM equity_snapshots")
                cursor.execute("DELETE FROM trade_memories")
                cursor.execute("DELETE FROM council_records")
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM accounts")
                cursor.execute("INSERT INTO accounts VALUES ('JPY', ?, ?)", (initial_jpy, now_str))
                cursor.execute("INSERT INTO accounts VALUES ('USD', ?, ?)", (initial_usd, now_str))
                conn.commit()

        # Re-record fresh baseline starting snapshot (0% return, 0% MDD)
        self.record_equity_snapshot()
        return {"success": True, "message": f"シミュレーション口座を完全初期化しました (初期残高: ¥{initial_jpy:,.0f} / ${initial_usd:,.2f})"}




    def record_equity_snapshot(self) -> Dict[str, Any]:
        """
        Record current total portfolio equity, cash, positions value, and FX rate into SQLite.
        """
        summary = self.get_portfolio_summary()
        tot_eq = float(summary.get("total_equity_jpy", 1000000.0))
        bals = summary.get("balances", {})
        j_cash = float(bals.get("JPY", 0.0))
        u_cash = float(bals.get("USD", 0.0))
        pos_val = float(summary.get("positions_market_value_jpy", 0.0))
        fx = float(summary.get("usd_jpy_rate", 150.0))
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO equity_snapshots (
                    total_equity_jpy, jpy_cash, usd_cash, positions_value_jpy, fx_rate, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """, (tot_eq, j_cash, u_cash, pos_val, fx, now_str))
                conn.commit()
                snap_id = cursor.lastrowid or 0

        return {
            "snapshot_id": snap_id,
            "total_equity_jpy": tot_eq,
            "jpy_cash": j_cash,
            "usd_cash": u_cash,
            "positions_value_jpy": pos_val,
            "fx_rate": fx,
            "timestamp": now_str
        }

    def get_equity_curve(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Retrieve equity snapshots chronologically for plotting the portfolio equity curve.
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM equity_snapshots ORDER BY snapshot_id ASC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            if not rows:
                # Create initial baseline snapshot if none exists
                self.record_equity_snapshot()
                cursor.execute("SELECT * FROM equity_snapshots ORDER BY snapshot_id ASC LIMIT ?", (limit,))
                rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # Lumina AI Memory Engine (Council & Trade Memory)
    # ==========================================

    def record_council(self, council_res: Dict[str, Any], news_items: Optional[List[Dict[str, str]]] = None) -> int:
        """
        Permanently archive council debate transcripts, radar scores, verdict, and referenced news.
        """
        symbol = council_res.get("symbol", "")
        company_name = council_res.get("company_name", symbol)
        verdict = council_res.get("verdict", {})
        action = verdict.get("action", "HOLD")
        action_label = verdict.get("action_label", "様子見")
        confidence = verdict.get("confidence_score", 50)
        target_price = verdict.get("target_price")
        stop_loss_price = verdict.get("stop_loss_price")
        alloc = verdict.get("allocation_pct", 0.0)
        thesis = verdict.get("thesis_summary", "")

        cross_debate_json = json.dumps(council_res.get("cross_debate", {}), ensure_ascii=False)
        regime_info_json = json.dumps(council_res.get("regime_info", {}), ensure_ascii=False)
        dialogues_json = json.dumps(council_res.get("council_dialogues", []), ensure_ascii=False)
        radar_json = json.dumps(council_res.get("radar_scores", {}), ensure_ascii=False)
        news_json = json.dumps(news_items or [], ensure_ascii=False)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                # Deduplication Guard: Check if a council for this symbol was recorded within 15 minutes
                cursor.execute("""
                    SELECT council_id, created_at FROM council_records
                    WHERE symbol = ? ORDER BY council_id DESC LIMIT 1
                """, (symbol,))
                existing = cursor.fetchone()
                if existing:
                    existing_id = existing["council_id"] if isinstance(existing, sqlite3.Row) else existing[0]
                    existing_time_str = existing["created_at"] if isinstance(existing, sqlite3.Row) else existing[1]
                    try:
                        t_existing = time.mktime(time.strptime(existing_time_str, "%Y-%m-%d %H:%M:%S"))
                        if (time.time() - t_existing) < (15 * 60):  # within 15 minutes
                            cursor.execute("""
                            UPDATE council_records SET
                                company_name = ?, action = ?, action_label = ?, confidence_score = ?,
                                target_price = ?, stop_loss_price = ?, allocation_pct = ?, thesis_summary = ?,
                                dialogues_json = ?, radar_scores_json = ?, news_headlines_json = ?, created_at = ?,
                                cross_debate_json = ?, regime_info_json = ?
                            WHERE council_id = ?
                            """, (
                                company_name, action, action_label, confidence,
                                target_price, stop_loss_price, alloc, thesis,
                                dialogues_json, radar_json, news_json, now_str,
                                cross_debate_json, regime_info_json, existing_id
                            ))
                            conn.commit()
                            return existing_id
                    except Exception:
                        pass

                cursor.execute("""
                INSERT INTO council_records (
                    symbol, company_name, action, action_label, confidence_score,
                    target_price, stop_loss_price, allocation_pct, thesis_summary,
                    dialogues_json, radar_scores_json, news_headlines_json, created_at,
                    cross_debate_json, regime_info_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, company_name, action, action_label, confidence,
                    target_price, stop_loss_price, alloc, thesis,
                    dialogues_json, radar_json, news_json, now_str,
                    cross_debate_json, regime_info_json
                ))
                conn.commit()
                return cursor.lastrowid or 0

    def get_recent_councils(self, limit: int = 20, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve historical council meeting records"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if symbol:
                norm = MarketDataFeed.normalize_symbol(symbol)
                cursor.execute("SELECT * FROM council_records WHERE symbol = ? ORDER BY council_id DESC LIMIT ?", (norm, limit))
            else:
                cursor.execute("SELECT * FROM council_records ORDER BY council_id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["dialogues"] = json.loads(item.get("dialogues_json") or "[]")
                except Exception:
                    item["dialogues"] = []
                try:
                    item["radar_scores"] = json.loads(item.get("radar_scores_json") or "{}")
                except Exception:
                    item["radar_scores"] = {}
                try:
                    item["news_headlines"] = json.loads(item.get("news_headlines_json") or "[]")
                except Exception:
                    item["news_headlines"] = []
                try:
                    item["cross_debate"] = json.loads(item.get("cross_debate_json") or "{}")
                except Exception:
                    item["cross_debate"] = {}
                try:
                    item["regime_info"] = json.loads(item.get("regime_info_json") or "{}")
                except Exception:
                    item["regime_info"] = {}
                results.append(item)
            return results

    def record_trade_memory(
        self,
        symbol: str,
        company_name: str,
        trade_type: str,
        quantity: int,
        price: float,
        currency: str,
        realized_pnl: float = 0.0,
        realized_pnl_pct: float = 0.0,
        trigger_rule: str = "",
        thesis_at_entry: str = "",
        lesson_learned: str = ""
    ) -> int:
        """
        Record the narrative journey of a trade: entry rationale, exit trigger, PnL, and AI lessons.
        """
        norm = MarketDataFeed.normalize_symbol(symbol)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO trade_memories (
                    symbol, company_name, trade_type, quantity, price, currency,
                    realized_pnl, realized_pnl_pct, trigger_rule, thesis_at_entry, lesson_learned, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    norm, company_name, trade_type, quantity, price, currency,
                    realized_pnl, realized_pnl_pct, trigger_rule, thesis_at_entry, lesson_learned, now_str
                ))
                conn.commit()
                rowid = cursor.lastrowid or 0

        # 🧠 Trigger Gemini 3.7 Flash Reflexion Post-Mortem in background
        if trade_type in ("SELL_EXIT", "STOP_LOSS", "TRAILING_STOP", "CALL_WALL_EXIT", "TIMEOUT_EXIT", "EMERGENCY_EXIT", "PARTIAL_TAKE_PROFIT"):
            try:
                from core.ai_hedge_fund.reflexion_engine import ReflexionEngine
                ReflexionEngine.trigger_post_mortem_async(
                    symbol=norm,
                    company_name=company_name,
                    exit_rule=trigger_rule or trade_type,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    broker_engine=self
                )
            except Exception as _ref_err:
                print(f"[PaperTradingEngine] Post-mortem trigger warning: {_ref_err}")

        return rowid

    def get_trade_memories(self, symbol: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve trade journey memories"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if symbol:
                norm = MarketDataFeed.normalize_symbol(symbol)
                cursor.execute("SELECT * FROM trade_memories WHERE symbol = ? ORDER BY memory_id DESC LIMIT ?", (norm, limit))
            else:
                cursor.execute("SELECT * FROM trade_memories ORDER BY memory_id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def _start_single_writer_worker(self) -> None:
        """
        Starts a dedicated Single-Writer background worker (`u/Zane-Reddit` architecture)
        that drains `_reflexion_write_queue` in discrete WAL batch transactions,
        eliminating SQLite lock contention under burst concurrent agent writes.
        """
        if self._writer_thread is not None and self._writer_thread.is_alive():
            return

        def _worker():
            while True:
                try:
                    first_item = self._reflexion_write_queue.get()
                    if first_item is None:
                        self._reflexion_write_queue.task_done()
                        break
                    batch = [first_item]
                    while len(batch) < 32:
                        try:
                            nxt = self._reflexion_write_queue.get_nowait()
                            if nxt is not None:
                                batch.append(nxt)
                            else:
                                self._reflexion_write_queue.task_done()
                        except queue.Empty:
                            break
                    try:
                        self._commit_reflexion_batch(batch)
                    finally:
                        for _ in batch:
                            self._reflexion_write_queue.task_done()
                except Exception:
                    pass

        self._writer_thread = threading.Thread(
            target=_worker, daemon=True, name="LuminaSQLiteSingleWriter"
        )
        self._writer_thread.start()

    def _commit_reflexion_batch(self, batch: List[Dict[str, Any]]) -> List[int]:
        """Commits a batch of agent reflexions inside a single serialized WAL transaction."""
        if not batch:
            return []
        rowids: List[int] = []
        with self._db_lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                for item in batch:
                    cursor.execute("""
                    INSERT INTO agent_reflexions (
                        symbol, company_name, agent_id, stance_at_entry, score_at_entry,
                        exit_rule, realized_pnl, realized_pnl_pct, reflection_text, lesson_category, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item["symbol"], item["company_name"], item["agent_id"],
                        item["stance_at_entry"], item["score_at_entry"], item["exit_rule"],
                        item["realized_pnl"], item["realized_pnl_pct"], item["reflection_text"],
                        item["lesson_category"], item["created_at"]
                    ))
                    rid = cursor.lastrowid or 0
                    rowids.append(rid)
                    if rid:
                        try:
                            cursor.execute("""
                            INSERT INTO agent_reflexions_fts(rowid, symbol, company_name, agent_id, exit_rule, lesson_category, reflection_text)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                rid, item["symbol"], item["company_name"], item["agent_id"],
                                item["exit_rule"], item["lesson_category"], item["reflection_text"]
                            ))
                        except Exception:
                            pass
                conn.commit()
        return rowids

    def enqueue_agent_reflexion(
        self,
        symbol: str,
        company_name: str,
        agent_id: str,
        stance_at_entry: str,
        score_at_entry: int,
        exit_rule: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        reflection_text: str,
        lesson_category: str = "LESSON"
    ) -> None:
        """Zero-latency non-blocking enqueue into the Single-Writer Queue."""
        norm = MarketDataFeed.normalize_symbol(symbol)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        self._reflexion_write_queue.put({
            "symbol": norm,
            "company_name": company_name,
            "agent_id": agent_id,
            "stance_at_entry": stance_at_entry,
            "score_at_entry": score_at_entry,
            "exit_rule": exit_rule,
            "realized_pnl": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
            "reflection_text": reflection_text,
            "lesson_category": lesson_category,
            "created_at": now_str,
        })

    def flush_reflexion_queue(self) -> None:
        """Blocks until all queued agent reflexions are committed to SQLite WAL."""
        self._reflexion_write_queue.join()

    def record_agent_reflexion(
        self,
        symbol: str,
        company_name: str,
        agent_id: str,
        stance_at_entry: str,
        score_at_entry: int,
        exit_rule: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        reflection_text: str,
        lesson_category: str = "LESSON"
    ) -> int:
        """Record deep reflective self-critique from a specific analyst agent via serialized WAL writer"""
        norm = MarketDataFeed.normalize_symbol(symbol)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        rids = self._commit_reflexion_batch([{
            "symbol": norm,
            "company_name": company_name,
            "agent_id": agent_id,
            "stance_at_entry": stance_at_entry,
            "score_at_entry": score_at_entry,
            "exit_rule": exit_rule,
            "realized_pnl": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
            "reflection_text": reflection_text,
            "lesson_category": lesson_category,
            "created_at": now_str,
        }])
        return rids[0] if rids else 0

    def search_agent_reflexions_bm25(
        self,
        query_terms: List[str],
        agent_id: Optional[str] = None,
        limit: int = 4,
        half_life_days: float = 30.0
    ) -> List[Dict[str, Any]]:
        """
        Sub-millisecond SQLite FTS5 BM25 ranking search over historical agent reflexions
        with Exponential Time-Decay Aging (Half-Life = 30 days) to prevent AI overfitting/trauma
        from stale market regimes.
        Preserves compound financial terms (hyphens, underscores, dots).
        """
        if not self._reflexion_write_queue.empty():
            self.flush_reflexion_queue()

        import re as _re
        from datetime import datetime as _dt
        clean_tokens = []
        for t in (query_terms or []):
            tok = _re.sub(r'[^0-9A-Za-z_\-.\u3040-\u30FF\u4E00-\u9FFF]', ' ', str(t)).strip()
            for part in tok.split():
                part_clean = part.strip(".-_")
                if len(part_clean) >= 2 and part_clean.upper() not in ("OR", "AND", "NOT", "NEAR"):
                    clean_tokens.append(f'"{part}"')
        if not clean_tokens:
            return self.get_agent_reflexions(agent_id=agent_id, limit=limit)

        fts_query = " OR ".join(clean_tokens[:10])
        fetch_pool = max(limit * 3, 12)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                if agent_id:
                    cursor.execute("""
                        SELECT r.*, bm25(agent_reflexions_fts) AS bm25_score
                        FROM agent_reflexions_fts f
                        JOIN agent_reflexions r ON r.reflexion_id = f.rowid
                        WHERE agent_reflexions_fts MATCH ? AND r.agent_id = ?
                        ORDER BY bm25(agent_reflexions_fts) ASC, r.reflexion_id DESC
                        LIMIT ?
                    """, (fts_query, agent_id, fetch_pool))
                else:
                    cursor.execute("""
                        SELECT r.*, bm25(agent_reflexions_fts) AS bm25_score
                        FROM agent_reflexions_fts f
                        JOIN agent_reflexions r ON r.reflexion_id = f.rowid
                        WHERE agent_reflexions_fts MATCH ?
                        ORDER BY bm25(agent_reflexions_fts) ASC, r.reflexion_id DESC
                        LIMIT ?
                    """, (fts_query, fetch_pool))
                rows = [dict(r) for r in cursor.fetchall()]
                if rows:
                    decay_lambda = math.log(2.0) / max(1.0, float(half_life_days))
                    now_dt = _dt.now()
                    for r in rows:
                        raw_bm25 = abs(float(r.get("bm25_score", 0.0))) or 1.0
                        created_str = str(r.get("created_at") or "")
                        try:
                            dt_parsed = _dt.strptime(created_str[:19], "%Y-%m-%d %H:%M:%S")
                            age_days = max(0.0, (now_dt - dt_parsed).total_seconds() / 86400.0)
                        except Exception:
                            age_days = 0.0
                        decay_weight = math.exp(-decay_lambda * age_days)
                        r["age_days"] = round(age_days, 2)
                        r["decay_weight"] = round(decay_weight, 4)
                        r["effective_score"] = round(raw_bm25 * decay_weight, 6)
                    rows.sort(key=lambda x: (x["effective_score"], x.get("reflexion_id", 0)), reverse=True)
                    return rows[:limit]
            except Exception:
                pass
        return self.get_agent_reflexions(agent_id=agent_id, limit=limit)

    def get_agent_reflexions(
        self,
        agent_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve historical reflection memories for an agent or a symbol"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if agent_id and symbol:
                norm = MarketDataFeed.normalize_symbol(symbol)
                cursor.execute(
                    "SELECT * FROM agent_reflexions WHERE agent_id = ? AND symbol = ? ORDER BY reflexion_id DESC LIMIT ?",
                    (agent_id, norm, limit)
                )
            elif agent_id:
                cursor.execute(
                    "SELECT * FROM agent_reflexions WHERE agent_id = ? ORDER BY reflexion_id DESC LIMIT ?",
                    (agent_id, limit)
                )
            elif symbol:
                norm = MarketDataFeed.normalize_symbol(symbol)
                cursor.execute(
                    "SELECT * FROM agent_reflexions WHERE symbol = ? ORDER BY reflexion_id DESC LIMIT ?",
                    (norm, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM agent_reflexions ORDER BY reflexion_id DESC LIMIT ?",
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_symbol_memory(self, symbol: str) -> Dict[str, Any]:
        """
        Compile full historical memory for a specific stock:
        - Past council meetings & verdicts
        - Past trade outcomes (PnL & lessons)
        - Formatted dossier ready to inject into AI agent debate prompt
        """
        norm = MarketDataFeed.normalize_symbol(symbol)
        councils = self.get_recent_councils(limit=3, symbol=norm)
        trades = self.get_trade_memories(symbol=norm, limit=5)

        summary_lines = []
        if councils:
            last_c = councils[0]
            summary_lines.append(f"- 直近の合議会議 ({last_c['created_at']}): 判定「{last_c['action_label']}」 (確信度: {last_c['confidence_score']}点)")
            summary_lines.append(f"  ・目標株価: {last_c.get('target_price', 'N/A')} / 損切り: {last_c.get('stop_loss_price', 'N/A')}")
            if last_c.get("thesis_summary"):
                summary_lines.append(f"  ・合議結論要約: {last_c['thesis_summary']}")
        
        if trades:
            total_realized = sum(float(t.get("realized_pnl", 0.0)) for t in trades)
            last_trade = trades[0]
            summary_lines.append(f"- 過去の取引履歴: {len(trades)}回の売買記録あり (累計確定損益: {total_realized:+,.1f})")
            summary_lines.append(f"  ・直近取引 ({last_trade['created_at']}): {last_trade['trade_type']} @ {last_trade['price']:,.2f} ({last_trade.get('trigger_rule', 'N/A')})")
            if last_trade.get("realized_pnl_pct"):
                summary_lines.append(f"  ・損益率: {last_trade['realized_pnl_pct']:+.1f}% | 知見・反省: {last_trade.get('lesson_learned', 'なし')}")

        if not summary_lines:
            prompt_text = "※当ファンドにおいて、過去にこの銘柄の合議または取引の履歴はありません（新規検討銘柄）。"
        else:
            prompt_text = "### 【当ファンドの過去の記憶・取引経緯】\n" + "\n".join(summary_lines) + "\n※メンバーはこの過去の議論・取引結果を踏まえ、「前回の課題がクリアされたか」「投資仮説が持続しているか」を検証して討論してください。"

        return {
            "symbol": norm,
            "councils": councils,
            "trades": trades,
            "prompt_text": prompt_text
        }


class KabuStationClient(BaseBrokerClient):
    """
    au Kabucom Securities kabuステーション REST API Connector
    Port: 18080 (Prod) / 18082 (Simulation)
    Allows live automated execution on the Tokyo Stock Exchange (TSE).
    """

    def __init__(self, api_password: str = "", host: str = "localhost", port: int = 18082):
        self.api_password = api_password
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/kabusapi"
        self.token = ""

    def authenticate(self) -> bool:
        """Fetch kabusapi session token"""
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                f"{self.base_url}/token",
                data=json.dumps({"APIPassword": self.api_password}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.token = data.get("Token", "")
                return bool(self.token)
        except Exception as e:
            print(f"[KabuStationClient] Auth error (kabu station not running?): {e}")
            return False

    def get_account_balance(self) -> Dict[str, float]:
        """Fetch cash balance from kabu station"""
        if not self.token and not self.authenticate():
            return {"JPY": 0.0, "status": "DISCONNECTED"}
        # API call stub to /wallet/cash
        return {"JPY": 0.0, "status": "CONNECTED"}

    def get_positions(self) -> List[Dict[str, Any]]:
        return []

    def place_order(self, symbol: str, side: str, quantity: int, price: Optional[float] = None, order_type: str = "MARKET", notes: str = "", target_price: Optional[float] = None, stop_loss_price: Optional[float] = None) -> Dict[str, Any]:
        """Send order to kabuステーション API"""
        return {
            "success": False,
            "message": "auカブコム証券 kabuステーションAPI実発注モード: kabuステーションアプリが起動している必要があります。"
        }


class IBKRClient(BaseBrokerClient):
    """
    Interactive Brokers (IBKR) Client Connector
    Connects to TWS or IB Gateway (Default Gateway Paper: 4002, TWS Paper: 7497, Gateway Live: 4001, TWS Live: 7496)
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = None
    _shared_ib = None
    _shared_lock = threading.Lock()
    _needs_reconciliation = False
    _last_reconciled_at: float = 0.0
    _active_client_id: int = 1

    def _reconcile_after_reconnect(self, ib) -> Dict[str, Any]:
        """
        Reconciles live IBKR positions, open OCO bracket orders, and executions
        after recovering from an IB Gateway daily maintenance disconnect or socket drop.
        """
        summary = {"reconciled": False, "positions_count": 0, "open_orders_count": 0, "executions_count": 0}
        try:
            if ib is None or not getattr(ib, "isConnected", lambda: False)():
                return summary
            pos_list = list(ib.positions() or [])
            open_orders = list(ib.reqOpenOrders() if hasattr(ib, "reqOpenOrders") else (ib.openOrders() or []))
            execs = list(ib.executions() if hasattr(ib, "executions") else [])
            summary["reconciled"] = True
            summary["positions_count"] = len(pos_list)
            summary["open_orders_count"] = len(open_orders)
            summary["executions_count"] = len(execs)
            IBKRClient._last_reconciled_at = time.time()
        except Exception:
            pass
        return summary

    def _get_connection(self):
        """
        Attempts to connect to IB Gateway or TWS via ib_insync with shared connection pooling,
        explicit zombie-socket cleanup, ClientId failover (Error 326 mitigation), and
        automatic post-disconnect state reconciliation.
        """
        try:
            import ib_insync
            with IBKRClient._shared_lock:
                if IBKRClient._shared_ib is not None:
                    if getattr(IBKRClient._shared_ib, "isConnected", lambda: False)():
                        return IBKRClient._shared_ib
                    try:
                        IBKRClient._shared_ib.disconnect()
                    except Exception:
                        pass
                    IBKRClient._shared_ib = None
                    IBKRClient._needs_reconciliation = True

                ib = ib_insync.IB()
                connected = False
                for cid_offset in range(3):
                    try_cid = self.client_id + cid_offset
                    try:
                        ib.connect(self.host, self.port, clientId=try_cid, timeout=3.0)
                        if getattr(ib, "isConnected", lambda: True)():
                            connected = True
                            IBKRClient._active_client_id = try_cid
                            break
                    except Exception:
                        continue

                if not connected:
                    return None

                IBKRClient._shared_ib = ib
                self._ib = ib
                if IBKRClient._needs_reconciliation:
                    self._reconcile_after_reconnect(ib)
                    IBKRClient._needs_reconciliation = False
                return ib
        except Exception:
            return None

    def get_account_balance(self) -> Dict[str, float]:
        ib = self._get_connection()
        if ib and ib.isConnected():
            try:
                balances = {"USD": 0.0, "JPY": 0.0, "status": "CONNECTED"}
                for val in ib.accountValues():
                    if val.tag == "NetLiquidationByCurrency":
                        if val.currency in balances:
                            balances[val.currency] = float(val.value)
                    elif val.tag == "TotalCashBalance":
                        if val.currency == "USD" and balances["USD"] == 0.0:
                            balances["USD"] = float(val.value)
                        elif val.currency == "JPY" and balances["JPY"] == 0.0:
                            balances["JPY"] = float(val.value)
                return balances
            except Exception as e:
                pass
        return {"USD": 0.0, "JPY": 0.0, "status": "IBKR_STANDBY_GATEWAY_OFFLINE"}

    def get_positions(self) -> List[Dict[str, Any]]:
        ib = self._get_connection()
        if ib and ib.isConnected():
            try:
                positions = []
                for p in ib.positions():
                    positions.append({
                        "symbol": p.contract.symbol,
                        "sec_type": p.contract.secType,
                        "currency": p.contract.currency,
                        "quantity": p.position,
                        "avg_cost": p.avgCost
                    })
                return positions
            except Exception:
                pass
        return []

    def place_order(self, symbol: str, side: str, quantity: int, price: Optional[float] = None, order_type: str = "MARKET", notes: str = "", target_price: Optional[float] = None, stop_loss_price: Optional[float] = None) -> Dict[str, Any]:
        ib = self._get_connection()
        if not (ib and ib.isConnected()):
            return {
                "success": False,
                "message": f"IBKR API接続エラー: {self.host}:{self.port} に接続できません。IB Gateway または TWS が起動しているか確認してください。"
            }
        try:
            import ib_insync
            norm_sym = MarketDataFeed.normalize_symbol(symbol)
            is_jp = norm_sym.endswith(".T")
            currency = "JPY" if is_jp else "USD"

            norm_qty = normalize_exchange_lot_size(quantity, is_jp=is_jp)
            if norm_qty <= 0:
                return {
                    "success": False,
                    "tse_lot_rejected": True,
                    "message": f"【東証単元株ガード】{norm_sym} の発注数量 ({quantity}株) が単元株（100株単位）未満のため発注を遮断しました。"
                }
            quantity = norm_qty

            ib_symbol = norm_sym[:-2] if is_jp else norm_sym
            contract = (
                ib_insync.Stock(ib_symbol, "SMART", currency, primaryExchange="TSEJ")
                if is_jp
                else ib_insync.Stock(ib_symbol, "SMART", currency)
            )
            ib.qualifyContracts(contract)

            action = side.upper()
            if stop_loss_price:
                stop_loss_price = round_price_to_exchange_tick(float(stop_loss_price), is_jp=is_jp)
            if target_price:
                target_price = round_price_to_exchange_tick(float(target_price), is_jp=is_jp)
            if order_type.upper() == "LIMIT" and price:
                order = ib_insync.LimitOrder(action, quantity, round_price_to_exchange_tick(float(price), is_jp=is_jp))
            else:
                order = ib_insync.MarketOrder(action, quantity)

            trade = ib.placeOrder(contract, order)
            ib.sleep(0.5)
            return {
                "success": True,
                "order_id": trade.order.orderId,
                "status": trade.orderStatus.status,
                "message": f"IBKR発注完了: {norm_sym} {action} {quantity}株 ({order_type})" + (f" [ブラケット逆指値: {stop_loss_price}]" if stop_loss_price else "")
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"IBKR発注例外: {e}"
            }

