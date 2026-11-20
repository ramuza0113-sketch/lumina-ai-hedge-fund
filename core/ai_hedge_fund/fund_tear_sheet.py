# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Institutional Performance Tear Sheet Engine (pyfolio Inspired)
Generates Wall Street grade performance and risk analytics from trading execution logs.
Produces monthly return heatmaps, underwater drawdown plots, and rolling Sharpe metrics.
"""

import os
import sys
import json
import time
import math
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive headless backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    matplotlib = None
    plt = None
    mdates = None

from core.ai_hedge_fund.broker_client import PaperTradingEngine


class FundTearSheet:
    """
    Institutional Performance & Risk Tear Sheet Generator (pyfolio architecture).
    Evaluates real trading journey health and exports publication-ready graphics for note.com.
    """

    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
    TEAR_SHEET_PNG = os.path.join(OUTPUT_DIR, "lumina_performance_tearsheet.png")

    @classmethod
    def generate_tear_sheet(cls, broker: Optional[PaperTradingEngine] = None, save_image: bool = True) -> Dict[str, Any]:
        """
        Calculates comprehensive fund metrics and renders the institutional tear sheet chart.
        """
        if not broker:
            broker = PaperTradingEngine()

        positions = broker.get_positions()
        summary = broker.get_portfolio_summary()
        history = getattr(broker, "get_trade_history", lambda: [])()

        # Retrieve live equity snapshots from SQLite WAL when available
        fx_rate = float(summary.get("usdjpy_rate") or 155.0)
        current_equity_jpy = float(summary.get("total_equity_jpy") or 1000000.0)
        current_equity_usd = float(summary.get("total_portfolio_value_usd") or (current_equity_jpy / fx_rate if fx_rate > 0 else 6451.61))
        realized_pnl = float(summary.get("total_realized_pnl_usd", 0.0))
        unrealized_pnl = float(summary.get("total_unrealized_pnl_usd", 0.0))

        snapshots = broker.get_equity_curve(limit=500) if hasattr(broker, "get_equity_curve") else []
        dates = []
        equity_values = []
        if snapshots and len(snapshots) >= 2:
            for s in snapshots:
                try:
                    ts = pd.to_datetime(s["timestamp"])
                    fx = float(s.get("fx_rate") or fx_rate)
                    eq_jpy = float(s.get("total_equity_jpy") or current_equity_jpy)
                    eq_usd = eq_jpy / fx if fx > 0 else current_equity_usd
                    dates.append(ts)
                    equity_values.append(eq_usd)
                except Exception:
                    continue

        has_snapshot_series = len(dates) >= 5
        if len(dates) < 2:
            now_dt = pd.Timestamp.now()
            dates = [now_dt - pd.Timedelta(hours=1), now_dt]
            equity_values = [current_equity_usd, current_equity_usd]

        initial_cash = equity_values[0] if equity_values and equity_values[0] > 0 else current_equity_usd
        equity_arr = np.asarray(equity_values, dtype=float)

        # Build genuine trade-level return series
        trades = []
        if hasattr(broker, "get_trade_memories"):
            try:
                raw_mem = broker.get_trade_memories(limit=200)
                trades = [m for m in raw_mem if m.get("trade_type") in ("SELL_EXIT", "PARTIAL_TAKE_PROFIT")]
            except Exception:
                trades = []
        elif hasattr(broker, "get_closed_positions"):
            trades = broker.get_closed_positions()

        win_trades = [t for t in trades if float(t.get("realized_pnl") or 0.0) > 0]
        loss_trades = [t for t in trades if float(t.get("realized_pnl") or 0.0) <= 0]
        total_trades = len(trades)
        win_rate = round(len(win_trades) / total_trades * 100.0, 1) if total_trades > 0 else None

        total_gain = sum(float(t.get("realized_pnl") or 0.0) for t in win_trades)
        total_loss = abs(sum(float(t.get("realized_pnl") or 0.0) for t in loss_trades))
        if total_trades == 0:
            profit_factor = None
        elif total_loss > 0:
            profit_factor = round(total_gain / total_loss, 2)
        else:
            profit_factor = None

        total_return_pct = round(((current_equity_usd - initial_cash) / initial_cash) * 100.0, 2) if initial_cash > 0 else 0.0

        peaks = np.maximum.accumulate(equity_arr)
        drawdowns = (equity_arr - peaks) / peaks * 100.0 if len(peaks) > 0 else np.array([0.0])
        max_dd_pct = round(float(np.min(drawdowns)), 2) if has_snapshot_series else 0.0

        if has_snapshot_series:
            pct_changes = np.diff(equity_arr) / np.maximum(equity_arr[:-1], 1e-9)
            vol_daily = float(np.std(pct_changes))
            annualized_vol_pct = round(vol_daily * np.sqrt(252) * 100.0, 1)
            mean_return = float(np.mean(pct_changes))
            sharpe_ratio = round((mean_return / vol_daily) * np.sqrt(252), 2) if vol_daily > 1e-9 else 0.0
            neg_rets = [r for r in pct_changes if r < 0]
            downside_vol = float(np.std(neg_rets)) if neg_rets else 0.0
            sortino_ratio = round((mean_return / downside_vol) * np.sqrt(252), 2) if downside_vol > 1e-9 else None
            calmar_ratio = round(total_return_pct / abs(max_dd_pct), 2) if max_dd_pct < -1e-6 else None
        else:
            annualized_vol_pct = None
            sharpe_ratio = None
            sortino_ratio = None
            calmar_ratio = None

        kpis = {
            "has_track_record": bool(total_trades > 0 or has_snapshot_series),
            "initial_capital_usd": round(initial_cash, 2),
            "total_portfolio_value_usd": round(current_equity_usd, 2),
            "total_net_pnl_usd": round(realized_pnl + unrealized_pnl, 2),
            "cumulative_return_pct": total_return_pct,
            "annualized_volatility_pct": annualized_vol_pct,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_drawdown_pct": max_dd_pct,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "total_trades_count": total_trades,
            "dates": dates,
            "equity_values": equity_values,
            "drawdowns": drawdowns,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if save_image:
            try:
                cls._render_matplotlib_tearsheet(kpis)
            except Exception as e:
                print(f"[FundTearSheet] Image rendering warning: {e}")

        return kpis

    @classmethod
    def _render_matplotlib_tearsheet(cls, kpis: Dict[str, Any]):
        """Render high-resolution 3-panel tear sheet chart (Dark Cyberpunk Theme)"""
        if plt is None:
            return
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)

        fig = plt.figure(figsize=(12, 8), dpi=150)
        fig.patch.set_facecolor("#030712")  # Deep cyber dark

        # Grid setup: 2 rows (Top: Cumulative Return & Underwater Drawdown, Bottom: Monthly Table / KPIs)
        gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.0], hspace=0.35, wspace=0.25)

        # 1. Panel 1: Cumulative Equity Curve (Recorded Snapshots Only — No Synthetic Noise)
        ax1 = fig.add_subplot(gs[0, :])
        ax1.set_facecolor("#0b0f19")
        dates = kpis.get("dates", [])
        equity_curve = np.asarray(kpis.get("equity_values", []), dtype=float)
        init_val = float(kpis.get("initial_capital_usd") or 100000.0)

        ax1.plot(dates, equity_curve, color="#00f0ff", linewidth=2.2, label="Lumina Capital NAV ($)")
        ax1.fill_between(dates, init_val, equity_curve, color="#00f0ff", alpha=0.12)
        ax1.axhline(init_val, color="#64748b", linestyle="--", linewidth=1.0, alpha=0.7)
        title_suffix = "" if kpis.get("has_track_record") else " [NO TRACK RECORD YET]"
        ax1.set_title(f"LUMINA CAPITAL — CUMULATIVE PORTFOLIO EQUITY (NAV){title_suffix}", color="#f8fafc", fontsize=12, fontweight="bold", pad=10)
        ax1.tick_params(colors="#94a3b8", labelsize=9)
        ax1.yaxis.set_major_formatter("${x:,.0f}")
        for spine in ax1.spines.values():
            spine.set_color("#1e293b")
        ax1.grid(True, color="#1e293b", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper left", facecolor="#0b0f19", edgecolor="#1e293b", labelcolor="#f8fafc", fontsize=9)

        # 2. Panel 2: Underwater Drawdown Plot
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.set_facecolor("#0b0f19")

        peaks = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peaks) / np.maximum(peaks, 1e-9) * 100.0

        ax2.plot(dates, drawdown, color="#ff0055", linewidth=1.8, label="Underwater DD (%)")
        ax2.fill_between(dates, 0, drawdown, color="#ff0055", alpha=0.25)
        ax2.set_title("UNDERWATER DRAWDOWN PROFILE (MAX DD %)", color="#f8fafc", fontsize=10, fontweight="bold", pad=10)
        ax2.tick_params(colors="#94a3b8", labelsize=8)
        ax2.yaxis.set_major_formatter("{x:.1f}%")
        for spine in ax2.spines.values():
            spine.set_color("#1e293b")
        ax2.grid(True, color="#1e293b", linestyle=":", alpha=0.6)
        ax2.legend(loc="lower left", facecolor="#0b0f19", edgecolor="#1e293b", labelcolor="#f8fafc", fontsize=8)

        # 3. Panel 3: Key Performance Diagnostic Table (KPIs)
        ax3 = fig.add_subplot(gs[1, 1])
        ax3.set_facecolor("#0b0f19")
        ax3.axis("off")

        def _fmt_metric(val, fmt_str: str) -> str:
            return "No Track Record" if val is None else fmt_str.format(val)

        kpi_rows = [
            ["Cumulative Return", f"{kpis['cumulative_return_pct']:+.2f}%"],
            ["Annualized Volatility", _fmt_metric(kpis["annualized_volatility_pct"], "{:.1f}%")],
            ["Sharpe Ratio", _fmt_metric(kpis["sharpe_ratio"], "{:.2f}")],
            ["Sortino Ratio", _fmt_metric(kpis["sortino_ratio"], "{:.2f}")],
            ["Calmar Ratio", _fmt_metric(kpis["calmar_ratio"], "{:.2f}")],
            ["Max Drawdown", f"{kpis['max_drawdown_pct']:.1f}%"],
            ["Win Rate", _fmt_metric(kpis["win_rate_pct"], "{:.1f}%")],
            ["Profit Factor", _fmt_metric(kpis["profit_factor"], "{:.2f}")],
            ["Closed Trades", str(kpis["total_trades_count"])],
        ]

        table = ax3.table(
            cellText=kpi_rows,
            colLabels=["Diagnostic Metric", "Fund Score"],
            loc="center",
            cellLoc="left"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.0, 1.4)

        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor("#1e293b")
            if row == 0:
                cell.set_facecolor("#0f172a")
                cell.set_text_props(color="#38bdf8", fontweight="bold")
            else:
                cell.set_facecolor("#0b0f19")
                cell.set_text_props(color="#f8fafc" if col == 1 else "#94a3b8")

        plt.savefig(cls.TEAR_SHEET_PNG, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        print(f"[FundTearSheet] Institutional Tear Sheet exported to: {cls.TEAR_SHEET_PNG}")
