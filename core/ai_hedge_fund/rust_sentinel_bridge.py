"""
Lumina Capital — Rust Sentinel & SoA Volume Clock Bridge (`rust_sentinel_bridge.py`)

Provides a persistent, sub-millisecond stdin/stdout IPC pipe to the compiled
`lumina-sentinel-rs` binary (`#![forbid(unsafe_code)]`, Cache-Resident SoA).
If the Rust binary is not yet compiled on the host environment, transparently
falls back to pure Python/NumPy SoA evaluation so production never halts.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RustSentinelBridge:
    """
    Manages a persistent background child process (`lumina-sentinel-rs --pipe`)
    for nanosecond/microsecond evaluation of:
      1. `SoAPositionBook` (5-Tier Exit & Monotonically Tightening Stop Rules A/B/B2/C/D/E + DAY_CIS)
      2. `SoAVolumeClock` (Easley-Lopez de Prado-O'Hara Volume Clock & Flow Velocity)
    """

    _instance: Optional["RustSentinelBridge"] = None
    _init_lock = threading.Lock()

    def __init__(self, binary_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self.binary_path = self._resolve_binary_path(binary_path)
        self.is_rust_active = False
        self.last_elapsed_ns: int = 0
        self._ensure_process()

    @classmethod
    def get_instance(cls) -> "RustSentinelBridge":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def _resolve_binary_path(custom_path: Optional[str] = None) -> Optional[str]:
        if custom_path and os.path.isfile(custom_path):
            return custom_path

        base_dir = Path(__file__).resolve().parent.parent.parent
        exe_name = (
            "lumina-sentinel-rs.exe"
            if platform.system().lower().startswith("win")
            else "lumina-sentinel-rs"
        )
        candidates = [
            base_dir / "rust_sentinel" / "target" / "release" / exe_name,
            base_dir / "rust_sentinel" / "target" / "debug" / exe_name,
            base_dir / "bin" / exe_name,
        ]
        for cand in candidates:
            if cand.is_file():
                return str(cand)
        return None

    def _ensure_process(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True

        if not self.binary_path or not os.path.isfile(self.binary_path):
            self.binary_path = self._resolve_binary_path()
            if not self.binary_path:
                self.is_rust_active = False
                return False

        try:
            self._proc = subprocess.Popen(
                [self.binary_path, "--pipe"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
            # Verify handshake
            assert self._proc.stdin is not None and self._proc.stdout is not None
            self._proc.stdin.write("PING\n")
            self._proc.stdin.flush()
            resp_line = self._proc.stdout.readline().strip()
            if resp_line and '"pong"' in resp_line:
                self.is_rust_active = True
                logger.info(
                    f"⚡ [Rust Sentinel Bridge] Connected to Cache-Resident SoA binary: {self.binary_path}"
                )
                return True
        except Exception as e:
            logger.warning(f"⚠️ [Rust Sentinel Bridge] Pipe startup fallback to Python: {e}")

        self.is_rust_active = False
        self._proc = None
        return False

    def evaluate_positions(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a batch of open positions using the Cache-Resident SoA Rust engine.

        Each item in `positions` accepts:
          - symbol (str)
          - entry_price (float)
          - current_price (float)
          - max_price_reached / peak_price (float, optional)
          - stop_loss_price (float, optional)
          - target_price (float, optional)
          - call_wall_price (float, optional)
          - is_half_profit_taken (bool/int, optional)
          - is_day_trade (bool/int, optional)

        Returns a dict containing `results` (list of per-symbol actions & updated stops/peaks),
        `elapsed_ns`, and `engine` ("lumina-sentinel-rs" or "python-soa-fallback").
        """
        if not positions:
            return {
                "status": "ok",
                "engine": "lumina-sentinel-rs" if self.is_rust_active else "python-soa-fallback",
                "elapsed_ns": 0,
                "results": [],
            }

        with self._lock:
            if self._ensure_process() and self._proc and self._proc.stdin and self._proc.stdout:
                try:
                    chunks: List[str] = []
                    for p in positions:
                        sym = str(p.get("symbol", "UNKNOWN")).replace(",", "").replace(";", "")
                        entry = float(p.get("entry_price") or 0.0)
                        cur = float(p.get("current_price") or entry)
                        peak = float(p.get("max_price_reached") or p.get("peak_price") or max(entry, cur))
                        stop = float(p.get("stop_loss_price") or 0.0)
                        target = float(p.get("target_price") or 0.0)
                        call_wall = float(p.get("call_wall_price") or 0.0)
                        is_half = 1 if p.get("is_half_profit_taken") else 0
                        is_day = 1 if p.get("is_day_trade") else 0
                        chunks.append(
                            f"{sym},{entry:.6f},{cur:.6f},{peak:.6f},{stop:.6f},{target:.6f},{call_wall:.6f},{is_half},{is_day}"
                        )

                    cmd = "EVAL_POS|" + ";".join(chunks) + "\n"
                    self._proc.stdin.write(cmd)
                    self._proc.stdin.flush()
                    line = self._proc.stdout.readline().strip()
                    if line:
                        data = json.loads(line)
                        self.last_elapsed_ns = int(data.get("elapsed_ns", 0))
                        return data
                except Exception as e:
                    logger.warning(f"⚠️ [Rust Sentinel Bridge] Pipe eval error, falling back: {e}")
                    self._proc = None
                    self.is_rust_active = False

        return self._fallback_evaluate_positions(positions)

    @staticmethod
    def _fallback_evaluate_positions(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        results = []
        for p in positions:
            sym = str(p.get("symbol", "UNKNOWN"))
            entry = float(p.get("entry_price") or 0.0)
            cur = float(p.get("current_price") or entry)
            prev_peak = max(entry, float(p.get("max_price_reached") or p.get("peak_price") or entry))
            prev_stop = float(p.get("stop_loss_price") or 0.0)
            target = float(p.get("target_price") or 0.0)
            call_wall = float(p.get("call_wall_price") or 0.0)
            is_half = bool(p.get("is_half_profit_taken"))
            is_day = bool(p.get("is_day_trade"))

            new_peak = max(prev_peak, cur)
            if entry <= 0.0 or cur <= 0.0:
                results.append(
                    {
                        "symbol": sym,
                        "action": "HOLD",
                        "new_peak": new_peak,
                        "new_stop": prev_stop,
                        "pnl_pct": 0.0,
                        "drawdown_pct": 0.0,
                    }
                )
                continue

            pnl_pct = ((cur - entry) / entry) * 100.0
            max_gain_pct = ((new_peak - entry) / entry) * 100.0
            drawdown_pct = ((cur - new_peak) / new_peak) * 100.0 if new_peak > 0 else 0.0

            if is_day:
                eff_stop = prev_stop if prev_stop > 0 else entry * 0.985
                if cur <= eff_stop:
                    act = "DAY_CIS_WALL_STOP"
                elif target > 0 and cur >= target:
                    act = "DAY_CIS_TARGET_PROFIT"
                else:
                    act = "HOLD"
                results.append(
                    {
                        "symbol": sym,
                        "action": act,
                        "new_peak": new_peak,
                        "new_stop": eff_stop,
                        "pnl_pct": round(pnl_pct, 4),
                        "drawdown_pct": round(drawdown_pct, 4),
                    }
                )
                continue

            fib_stop = entry * 0.87
            cand_stop = max(prev_stop, fib_stop) if prev_stop > 0 else fib_stop
            if is_half:
                cand_stop = max(cand_stop, entry)
            if max_gain_pct >= 5.0:
                cand_stop = max(cand_stop, new_peak * 0.96)

            if (target > 0 and cur >= target) or pnl_pct >= 25.0:
                act = "RULE_A_FULL_PROFIT"
            elif (not is_half) and call_wall > entry and cur >= call_wall * 0.997 and pnl_pct >= 3.0:
                act = "RULE_B2_CALL_WALL_HALF"
                cand_stop = max(cand_stop, entry)
            elif (not is_half) and pnl_pct >= 10.0:
                act = "RULE_B_HALF_PROFIT"
                cand_stop = max(cand_stop, entry)
            elif is_half and cur <= entry:
                act = "RULE_D_BREAKEVEN_STOP"
            elif max_gain_pct >= 5.0 and drawdown_pct <= -4.0:
                act = "RULE_C_TRAILING_STOP"
            elif pnl_pct <= -13.0 or (prev_stop > 0 and cur <= prev_stop):
                act = "RULE_E_FIB_STOP"
            else:
                act = "HOLD"

            results.append(
                {
                    "symbol": sym,
                    "action": act,
                    "new_peak": round(new_peak, 4),
                    "new_stop": round(cand_stop, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "drawdown_pct": round(drawdown_pct, 4),
                }
            )

        elapsed_ns = time.perf_counter_ns() - t0
        return {
            "status": "ok",
            "engine": "python-soa-fallback",
            "forbid_unsafe": True,
            "elapsed_ns": elapsed_ns,
            "results": results,
        }

    def close(self) -> None:
        with self._lock:
            if self._proc is not None:
                try:
                    if self._proc.stdin:
                        self._proc.stdin.write("QUIT\n")
                        self._proc.stdin.flush()
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None
                self.is_rust_active = False
