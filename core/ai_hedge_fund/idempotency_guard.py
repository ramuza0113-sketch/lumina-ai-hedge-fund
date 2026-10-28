# -*- coding: utf-8 -*-
"""
OrderIdempotencyGuard & Stale Signal Purge Engine
-------------------------------------------------
IBKRおよび自律AIヘッジファンドの通信切断・2FA再認証・ネットワーク瞬断時における
「二重発注の完全防止（冪等性・Client Order ID）」および
「古いシグナルキューの自動破棄（鮮度期限切れガード）」を司るエンタープライズ級防衛エンジン。
"""

import os
import time
import uuid
import sqlite3
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("idempotency_guard")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class OrderIdempotencyGuard:
    """
    発注冪等性・二重発注防止・シグナル鮮度管理ガード
    """
    # シグナル鮮度の最大許容時間（秒）。通信切断や再認証でこれ以上遅延したシグナルは破棄する
    MAX_SIGNAL_AGE_SECONDS: float = 90.0

    # 同一銘柄・同一売買方向の重複発注クールダウン時間（秒）
    COOLDOWN_WINDOW_SECONDS: float = 120.0

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # PaperTradingEngineと同じDBを使用
            app_data_dir = os.path.join(os.getenv('APPDATA', ''), 'LuminaAI')
            if not os.path.exists(app_data_dir):
                app_data_dir = os.path.expanduser('~/.lumina_ai')
            os.makedirs(app_data_dir, exist_ok=True)
            self.db_path = os.path.join(app_data_dir, 'hedge_fund_portfolio.db')
        else:
            self.db_path = db_path

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        # WALモードで高並行アクセスを保証
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        """DBテーブルの初期化"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_idempotency (
                idempotency_key TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                status TEXT NOT NULL,              -- 'PENDING', 'SUBMITTED', 'FILLED', 'REJECTED', 'STALE_DISCARDED'
                order_ref TEXT NOT NULL,           -- IBKR orderRef
                broker TEXT NOT NULL DEFAULT 'IBKR',
                broker_order_id TEXT,
                signal_timestamp REAL NOT NULL,    -- Unix timestamp when AI signal was generated
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT
            )
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_order_idempotency_sym_side 
            ON order_idempotency(symbol, side, status, signal_timestamp);
            """)
            conn.commit()

    @classmethod
    def generate_order_ref(
        cls,
        symbol: str,
        side: str,
        strategy_type: str = "SWING",
        prefix: str = "LUM"
    ) -> str:
        """
        IBKRの取引所・注文台帳（orderRef）に刻印する一意なClient Order IDを生成。
        形式: LUM_{SYM}_{SIDE}_{TS_MS}_{SHORT_UUID}
        例: LUM_NVDA_BUY_1730000000_a1b2
        """
        clean_sym = symbol.replace(".", "_").replace("^", "").upper()
        ts_ms = int(time.time() * 1000) % 100000000  # コンパクトなミリ秒タイムスタンプ
        uid = uuid.uuid4().hex[:4]
        strat_tag = "D" if strategy_type == "DAY_CIS" else "S"
        return f"{prefix}_{clean_sym}_{side[0]}_{strat_tag}_{ts_ms}_{uid}"

    def check_and_reserve(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        signal_timestamp: Optional[float] = None,
        strategy_type: str = "SWING",
        custom_key: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        発注前の事前検証および原子的（Atomic）予約。
        
        Returns:
            (is_allowed: bool, reason_or_message: str, order_ref: Optional[str])
        """
        now = time.time()
        sig_ts = signal_timestamp if signal_timestamp and signal_timestamp > 0 else now
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # -------------------------------------------------------------
        # 1. 🛡️ シグナル鮮度ガード (Stale Signal Expiration Guard)
        # -------------------------------------------------------------
        signal_age = now - sig_ts
        if signal_age > self.MAX_SIGNAL_AGE_SECONDS:
            ref_discard = self.generate_order_ref(symbol, side, strategy_type)
            msg = (
                f"⚠️ 【シグナル鮮度ガード】通信切断・再認証待機による遅延を検知！"
                f"シグナル生成から {signal_age:.1f}秒（許容上限 {self.MAX_SIGNAL_AGE_SECONDS:.0f}秒）が経過したため、"
                f"古いシグナルキューを自動破棄しました（現在値乖離・誤約定防止）。"
            )
            logger.warning(f"[{symbol}] {msg}")
            # 破棄履歴として記録
            try:
                with self._get_conn() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO order_idempotency (
                        idempotency_key, symbol, side, quantity, order_type, status,
                        order_ref, broker, signal_timestamp, created_at, updated_at, error_message
                    ) VALUES (?, ?, ?, ?, ?, 'STALE_DISCARDED', ?, 'IBKR', ?, ?, ?, ?)
                    """, (
                        ref_discard, symbol, side, quantity, order_type,
                        ref_discard, sig_ts, now_str, now_str, msg
                    ))
                    conn.commit()
            except Exception:
                pass
            return False, msg, None

        # -------------------------------------------------------------
        # 2. 🛡️ 進行中注文・重複発注チェック (In-Flight Cooldown Check)
        # -------------------------------------------------------------
        cutoff_ts = now - self.COOLDOWN_WINDOW_SECONDS
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT idempotency_key, order_ref, status, signal_timestamp, created_at
            FROM order_idempotency
            WHERE symbol = ? AND side = ? AND status IN ('PENDING', 'SUBMITTED', 'FILLED') AND signal_timestamp >= ?
            ORDER BY signal_timestamp DESC LIMIT 1
            """, (symbol, side, cutoff_ts))
            in_flight = cursor.fetchone()

            if in_flight:
                active_ref = in_flight["order_ref"]
                active_status = in_flight["status"]
                active_time = in_flight["created_at"]
                msg = (
                    f"⚠️ 【冪等性ガード】銘柄 {symbol} ({side}) に対し、直近の発注処理 "
                    f"（Ref: {active_ref} ｜ 状態: {active_status} ｜ 発生: {active_time}）が進行中のため、"
                    f"二重発注を完全抑止しました。"
                )
                logger.warning(f"[{symbol}] {msg}")
                return False, msg, None

        # -------------------------------------------------------------
        # 3. 🛡️ 発注予約の原子登録 (Atomic Reservation)
        # -------------------------------------------------------------
        order_ref = custom_key or self.generate_order_ref(symbol, side, strategy_type)
        idempotency_key = order_ref

        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO order_idempotency (
                    idempotency_key, symbol, side, quantity, order_type, status,
                    order_ref, broker, signal_timestamp, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, 'IBKR', ?, ?, ?)
                """, (
                    idempotency_key, symbol, side, quantity, order_type,
                    order_ref, sig_ts, now_str, now_str
                ))
                conn.commit()
            return True, "発注予約完了 (PENDING)", order_ref
        except sqlite3.IntegrityError:
            msg = f"⚠️ 【冪等性ガード】同一のClient Order ID ({order_ref}) が既に存在します。再発注を抑止しました。"
            logger.warning(f"[{symbol}] {msg}")
            return False, msg, None
        except Exception as e:
            msg = f"⚠️ 冪等性DB登録エラー: {e}"
            logger.error(msg)
            return False, msg, None

    def record_submitted(
        self,
        order_ref: str,
        broker_order_id: Optional[Any] = None,
        broker_type: str = "IBKR"
    ):
        """証券会社APIへの送信完了ステータス更新"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE order_idempotency 
                SET status = 'SUBMITTED', broker = ?, broker_order_id = ?, updated_at = ?
                WHERE order_ref = ?
                """, (broker_type, str(broker_order_id) if broker_order_id else None, now_str, order_ref))
                conn.commit()
        except Exception as e:
            logger.error(f"record_submitted 更新失敗: {e}")

    def record_completed(
        self,
        order_ref: str,
        is_success: bool,
        error_message: Optional[str] = None
    ):
        """約定完了または発注失敗の最終ステータス更新"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        new_status = "FILLED" if is_success else "REJECTED"
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE order_idempotency 
                SET status = ?, error_message = ?, updated_at = ?
                WHERE order_ref = ?
                """, (new_status, error_message, now_str, order_ref))
                conn.commit()
        except Exception as e:
            logger.error(f"record_completed 更新失敗: {e}")

    def get_in_flight_orders(self) -> list:
        """現在処理中の注文を取得"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM order_idempotency 
            WHERE status IN ('PENDING', 'SUBMITTED')
            ORDER BY signal_timestamp DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
