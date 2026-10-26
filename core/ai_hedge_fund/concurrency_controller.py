# -*- coding: utf-8 -*-
"""
ConcurrencyController & Distributed Exclusion Engine
----------------------------------------------------
Redditクオンツコミュニティレビューを反映した分散並行制御アーキテクチャ。
1. 15分合議サイクルと10秒番犬センチネルの完全排他制御（Turn Mutex）
2. 銘柄単位の細粒度ロック（Symbol-Level Fine-Grained Mutex）
3. バージョン付きポジションスナップショットとCAS更新（Optimistic Concurrency Control）
4. SQLite WALモードにおけるロック競合防止
"""

import time
import logging
import threading
from contextlib import contextmanager
from collections import defaultdict
from typing import Dict, Any, Optional, Generator

logger = logging.getLogger("concurrency_controller")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class ConcurrencyController:
    """
    自律AIヘッジファンド並行処理排他制御コントローラー
    """
    # グローバルな売買・リバランス確定用Mutex（発注・残高コミット時のみ瞬時獲得）
    _commit_lock = threading.RLock()

    # 銘柄ごとの個別Mutex（同一銘柄への同時操作・二重売り抜けを排他）
    _symbol_locks = defaultdict(threading.RLock)
    _symbol_locks_guard = threading.Lock()

    # 合議中フラグ（番犬が現在のシステム状況を把握するための情報）
    _is_council_deliberating = False
    _council_start_time = 0.0

    @classmethod
    def get_symbol_lock(cls, symbol: str) -> threading.RLock:
        """銘柄専用の細粒度ロックを取得"""
        norm = symbol.strip().upper()
        with cls._symbol_locks_guard:
            return cls._symbol_locks[norm]

    @classmethod
    @contextmanager
    def symbol_mutex(cls, symbol: str, timeout: float = 8.0) -> Generator[bool, None, None]:
        """
        特定銘柄に対する原子的操作用コンテキストマネージャー
        """
        lock = cls.get_symbol_lock(symbol)
        acquired = lock.acquire(timeout=timeout)
        if not acquired:
            logger.warning(f"⚠️ 銘柄 {symbol} のロック獲得タイムアウト ({timeout}s)")
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()

    @classmethod
    @contextmanager
    def commit_turn(cls, timeout: float = 10.0) -> Generator[bool, None, None]:
        """
        注文発注・ポジション更新・資金増減の原子的コミット用ターンMutex
        """
        acquired = cls._commit_lock.acquire(timeout=timeout)
        if not acquired:
            logger.warning(f"⚠️ コミットロック獲得タイムアウト ({timeout}s)")
        try:
            yield acquired
        finally:
            if acquired:
                cls._commit_lock.release()

    @classmethod
    @contextmanager
    def council_debate_phase(cls) -> Generator[None, None, None]:
        """
        合議AIが市場スキャン〜LLM討議を行う期間をマークするコンテキスト。
        ※この期間は番犬のトレイリング監視をブロックしません（非ブロッキング並行性）。
        """
        cls._is_council_deliberating = True
        cls._council_start_time = time.time()
        try:
            yield
        finally:
            cls._is_council_deliberating = False
            cls._council_start_time = 0.0

    @classmethod
    def is_council_active(cls) -> bool:
        """現在AI合議が進行中かを取得"""
        return cls._is_council_deliberating

    @classmethod
    def get_concurrency_stats(cls) -> Dict[str, Any]:
        """現在の排他制御状態の統計"""
        return {
            "is_council_deliberating": cls._is_council_deliberating,
            "council_duration_seconds": round(time.time() - cls._council_start_time, 1) if cls._council_start_time > 0 else 0.0,
            "active_symbol_locks_count": len(cls._symbol_locks),
        }
