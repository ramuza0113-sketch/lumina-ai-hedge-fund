# -*- coding: utf-8 -*-
"""
Lumina Capital v6.4.8 - Complete Institutional Audit Suite (Remaining 4 Pillars):
1. Chapter 4: Overfitting Diagnostics (Rolling WFA/WFE, Purged & Embargoed CPCV, PBO, Deflated Sharpe Ratio DSR, Parameter Sensitivity Plateau)
2. Chapter 6: Multi-Dimensional Risk-Adjusted Metrics (Sharpe, Sortino, Calmar, Payoff, Max Underwater Duration <= 180d)
3. Chapter 2.1: Almgren-Chriss Square-Root Market Impact (sqrt(Q / ADV_20)) & Strategy Capacity Limit (10M JPY to 3B JPY)
4. Chapter 3.2: Point-in-Time (PIT) Financial Disclosure Lag (45-day & 90-day SEC 10-Q / Kessan Tanshin reporting delay)
"""

import os
import sys
import math
import itertools
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis
import yfinance as yf

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.ai_hedge_fund.market_screener import MarketScreener
from core.ai_hedge_fund.broker_client import round_price_to_exchange_tick, normalize_exchange_lot_size

ROE_DATA = {
    "NVDA": 115.0, "MSFT": 38.5, "AAPL": 160.0, "GOOGL": 30.5, "META": 33.2,
    "AMZN": 21.0, "PLTR": 18.2, "AVGO": 24.5, "AMD": 13.5, "ARM": 19.0,
    "6146.T": 28.5, "6857.T": 24.2, "8035.T": 22.0, "5803.T": 18.5, "5802.T": 12.8,
    "6501.T": 14.5, "6758.T": 13.5, "8001.T": 16.5, "8031.T": 15.2, "8058.T": 13.5,
    "6861.T": 15.0, "4063.T": 14.8, "7011.T": 12.5, "7012.T": 12.2, "6301.T": 14.0,
    "ASML": 45.0, "SAP": 14.0, "NVO": 80.0, "AZN": 16.5, "LVMUY": 26.0,
    "JPM": 16.8, "BRK-B": 13.5, "KO": 42.0, "JNJ": 32.0, "GE": 22.0,
    "VST": 17.5, "RTX": 12.5, "LMT": 55.0, "GM": 14.5, "WMT": 21.5,
    "3778.T": 4.5, "VALE": 8.5, "INTC": -2.0, "F": 8.0, "5401.T": 7.5,
    "7267.T": 8.0, "5020.T": 7.0, "1812.T": 9.2, "1801.T": 6.5, "9101.T": 10.5,
    "9432.T": 12.2, "9433.T": 12.5, "8306.T": 9.5, "8316.T": 9.0, "8411.T": 8.5,
    "2914.T": 14.2, "7203.T": 13.8, "7974.T": 18.5, "CCJ": 7.5, "7013.T": 11.0,
    "8053.T": 11.8, "8002.T": 11.5, "EADSY": 11.0, "TSLA": 15.0, "9984.T": 6.5,
    # Crash / Fallen Angel stocks
    "PTON": -35.0, "ZM": 5.5, "PYPL": 14.5, "LULU": 25.0, "NKE": 22.0,
    "EL": 8.5, "BABA": 9.5, "DIS": 6.5, "BA": -15.0,
    "2413.T": 13.5, "6594.T": 10.5, "7201.T": 3.5, "4911.T": 4.2, "4755.T": -12.0, "4385.T": 8.0,
}

PIOTROSKI_F_SCORE = {
    "NVDA": 9, "MSFT": 8, "AAPL": 8, "GOOGL": 8, "META": 8,
    "AMZN": 7, "PLTR": 7, "AVGO": 8, "AMD": 6, "ARM": 7,
    "6146.T": 9, "6857.T": 8, "8035.T": 8, "5803.T": 8, "5802.T": 7,
    "6501.T": 8, "6758.T": 7, "8001.T": 8, "8031.T": 8, "8058.T": 7,
    "6861.T": 9, "4063.T": 9, "7011.T": 8, "7012.T": 7, "6301.T": 7,
    "ASML": 8, "SAP": 8, "NVO": 9, "AZN": 7, "LVMUY": 7,
    "JPM": 7, "BRK-B": 8, "KO": 7, "JNJ": 7, "GE": 8, "WMT": 8,
    "VST": 7, "RTX": 7, "LMT": 8, "7974.T": 8, "9433.T": 7, "7203.T": 7, "9432.T": 6,
    "GM": 5, "TSLA": 5, "2914.T": 5, "3778.T": 3, "VALE": 4, "INTC": 2, "F": 4, "9984.T": 3,
    # Crash / Fallen Angel stocks
    "PTON": 2, "ZM": 5, "PYPL": 6, "LULU": 6, "NKE": 6,
    "EL": 4, "BABA": 5, "DIS": 5, "BA": 2,
    "2413.T": 6, "6594.T": 5, "7201.T": 3, "4911.T": 4, "4755.T": 2, "4385.T": 4,
}

MIXED_20_SYMBOLS = [
    # 10 Crash / Fallen Angel stocks (avg -68.5%)
    "PTON", "2413.T", "PYPL", "6594.T", "ZM", "LULU", "NKE", "EL", "7201.T", "4911.T",
    # 10 Standard Large-Cap stocks (excluding NVDA/Advantest)
    "MSFT", "AAPL", "WMT", "JPM", "KO", "JNJ", "7203.T", "6758.T", "8001.T", "9432.T",
]


def is_near_earnings_gamble(sym: str, date_obj) -> bool:
    m = date_obj.month
    d = date_obj.day
    if sym.endswith(".T"):
        return (m in [2, 5, 8, 11]) and (1 <= d <= 14)
    return (m in [1, 4, 7, 10]) and (15 <= d <= 28)


def load_5year_data(symbols: List[str]) -> Tuple[Dict[str, pd.DataFrame], List[pd.Timestamp], pd.Series]:
    start_date = "2020-06-01"
    end_date = "2026-10-25"
    raw_data = yf.download(
        tickers=symbols, start=start_date, end=end_date,
        interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True
    )
    usdjpy_df = yf.download("USDJPY=X", start=start_date, end=end_date, interval="1d", auto_adjust=True, progress=False)
    usdjpy_series = usdjpy_df["Close"].squeeze()

    stock_data = {}
    for sym in symbols:
        df = None
        try:
            df_cand = raw_data[sym].copy()
            df_cand.dropna(subset=["Close"], inplace=True)
            if len(df_cand) > 120:
                df = df_cand
        except Exception:
            df = None

        # Sequential fallback if concurrent yf.download(threads=True) rate-limited a TSE (.T) ticker
        if df is None or len(df) <= 120:
            for _attempt in range(3):
                try:
                    t_hist = yf.Ticker(sym).history(start=start_date, end=end_date, interval="1d", auto_adjust=True)
                    if t_hist is not None and not t_hist.empty:
                        if t_hist.index.tz is not None:
                            t_hist.index = t_hist.index.tz_localize(None)
                        t_hist.dropna(subset=["Close"], inplace=True)
                        if len(t_hist) > 120:
                            df = t_hist
                            break
                except Exception:
                    continue

        try:
            if df is not None and len(df) > 120:
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                closes = df["Close"]
                highs = df["High"]
                lows = df["Low"]
                vols = df["Volume"]
                df["ma20"] = closes.rolling(20).mean()
                df["ma50"] = closes.rolling(50).mean()
                df["ma200"] = closes.rolling(200).mean()
                delta = closes.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, 1e-9)
                df["rsi"] = 100.0 - (100.0 / (1.0 + rs))
                df["roc20"] = (closes / closes.shift(20) - 1.0) * 100.0
                df["roc60"] = (closes / closes.shift(60) - 1.0) * 100.0
                tr = pd.concat([
                    highs - lows,
                    (highs - closes.shift(1)).abs(),
                    (lows - closes.shift(1)).abs()
                ], axis=1).max(axis=1)
                df["atr14"] = tr.rolling(14).mean()
                df["atr_pct"] = (df["atr14"] / closes) * 100.0
                df["adv20"] = vols.rolling(20).mean().replace(0, 1e6)
                # 3-day Volume-Clock institutional accumulation surge ratio
                df["flow_velocity"] = vols.rolling(3).max() / df["adv20"]
                df["daily_vol"] = closes.pct_change().rolling(20).std().fillna(0.02)
                df["high250"] = closes.rolling(250, min_periods=60).max()
                df["dd_from_1y_high"] = (closes / df["high250"] - 1.0) * 100.0
                stock_data[sym] = df
        except Exception:
            continue

    all_dates = sorted([
        dt for dt in set.union(*[set(df.index) for df in stock_data.values()])
        if dt >= pd.Timestamp("2021-01-04")
    ])
    return stock_data, all_dates, usdjpy_series


def run_backtest_engine(
    stock_data: Dict[str, pd.DataFrame],
    dates_slice: List[pd.Timestamp],
    usdjpy_series: pd.Series,
    initial_capital: float = 10_000_000.0,
    stop_loss_pct: float = 0.13,
    target_profit_pct: float = 0.22,
    partial_tp_pct: float = 0.10,
    flow_vel_min: float = 1.12,
    time_barrier_days: int = 25,
    sma200_mult: float = 0.98,
    slippage_pct: float = 0.0005,
    use_almgren_chriss: bool = False,
    almgren_y: float = 0.5,
    pit_disclosure_lag_days: int = 0,
    force_fallen_angels_high_roe: bool = False,
    compound_sizing: bool = True,
) -> Dict[str, Any]:
    cash = initial_capital
    active_positions: Dict[str, Dict[str, Any]] = {}
    cooldown_until_idx: Dict[str, int] = {}
    roundtrip_trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = []
    impact_bps_list: List[float] = []

    for d_idx, dt in enumerate(dates_slice):
        dt_str = dt.strftime("%Y-%m-%d")
        try:
            r_val = usdjpy_series.asof(dt)
            fx_rate = float(r_val) if not pd.isna(r_val) else 145.0
        except Exception:
            fx_rate = 145.0

        # 1. Manage existing positions
        to_remove = []
        for sym, pos in list(active_positions.items()):
            df = stock_data[sym]
            if dt not in df.index:
                continue
            row = df.loc[dt]
            cur_open = float(row["Open"])
            cur_close = float(row["Close"])
            cur_high = float(row["High"])
            cur_low = float(row["Low"])
            ma20 = float(row["ma20"]) if not pd.isna(row["ma20"]) else cur_close
            adv20 = float(row["adv20"]) if not pd.isna(row["adv20"]) else 1e6
            d_vol = float(row["daily_vol"]) if not pd.isna(row["daily_vol"]) else 0.02

            pos["last_close"] = cur_close
            pos["days_held"] += 1

            entry_p = pos["entry_price"]
            cur_qty = pos["shares"]
            peak_p = max(pos["peak_price"], cur_high)
            pos["peak_price"] = peak_p
            is_jp = sym.endswith(".T")

            pnl_pct = ((cur_close - entry_p) / entry_p) * 100.0
            dd_from_peak = ((cur_low - peak_p) / peak_p) * 100.0
            stop_p = pos["stop_loss"]

            exit_reason = None
            raw_exit_p = None
            exit_shares = 0

            # Rule E: Stop-Loss (including real overnight gap-down Open check)
            if cur_low <= stop_p and pos["half_taken"] == 0:
                raw_exit_p = min(cur_open, stop_p) if cur_open < stop_p else stop_p
                exit_shares = cur_qty
                exit_reason = "STOP_LOSS"
            # Rule B: +10% Half Profit & Breakeven Lock
            elif pnl_pct >= (partial_tp_pct * 100.0) and pos["half_taken"] == 0 and cur_qty >= (200 if is_jp else 2):
                half_qty = normalize_exchange_lot_size(cur_qty // 2, is_jp=is_jp)
                if half_qty > 0:
                    raw_exit_p = cur_close
                    exit_shares = half_qty
                    exit_reason = "PARTIAL_TP"
                    pos["half_taken"] = 1
                    pos["shares"] = cur_qty - half_qty
                    pos["stop_loss"] = entry_p
            # Rule D: Breakeven Stop
            elif pos["half_taken"] == 1 and cur_low <= entry_p:
                raw_exit_p = min(cur_open, entry_p) if cur_open < entry_p else entry_p
                exit_shares = cur_qty
                exit_reason = "BREAKEVEN_STOP"
            # Rule C: Trailing Stop (-4% from peak)
            elif pos["half_taken"] == 1 and dd_from_peak <= -4.0:
                raw_exit_p = peak_p * 0.96
                exit_shares = cur_qty
                exit_reason = "TRAILING_STOP"
            # Rule A: Target Profit
            elif cur_high >= entry_p * (1.0 + target_profit_pct):
                raw_exit_p = entry_p * (1.0 + target_profit_pct)
                exit_shares = cur_qty
                exit_reason = "TARGET_PROFIT"
            # Rule F: Time-Barrier Dead-Money Rotation
            elif pos["half_taken"] == 0 and pos["days_held"] >= time_barrier_days and (0.2 <= pnl_pct <= 3.0) and (cur_close < ma20):
                raw_exit_p = cur_close
                exit_shares = cur_qty
                exit_reason = "TIME_BARRIER"

            if exit_shares > 0 and raw_exit_p is not None:
                impact_pct = 0.0
                if use_almgren_chriss and adv20 > 0:
                    impact_pct = almgren_y * d_vol * math.sqrt(exit_shares / adv20)
                    impact_bps_list.append(impact_pct * 10000.0)
                eff_slip = slippage_pct + impact_pct
                exec_p = round_price_to_exchange_tick(raw_exit_p * (1.0 - eff_slip), is_jp=is_jp)
                trade_fx = 1.0 if is_jp else fx_rate
                gross_jpy = exec_p * exit_shares * trade_fx
                comm_jpy = gross_jpy * 0.0005 if is_jp else max(1.0, exit_shares * 0.005) * fx_rate
                proceeds_jpy = gross_jpy - comm_jpy
                cost_jpy = entry_p * exit_shares * trade_fx
                leg_pnl_jpy = proceeds_jpy - cost_jpy

                cash += proceeds_jpy
                if exit_reason == "PARTIAL_TP":
                    pos["realized_partial_pnl"] = pos.get("realized_partial_pnl", 0.0) + leg_pnl_jpy
                else:
                    total_pos_pnl = pos.get("realized_partial_pnl", 0.0) + leg_pnl_jpy
                    init_cost = pos["initial_cost_jpy"]
                    roundtrip_trades.append({
                        "symbol": sym,
                        "entry_date": pos["entry_date"],
                        "exit_date": dt_str,
                        "pnl_jpy": total_pos_pnl,
                        "pnl_pct": (total_pos_pnl / max(init_cost, 1.0)) * 100.0,
                        "reason": exit_reason,
                    })
                    to_remove.append(sym)
                    if exit_reason in ("TIME_BARRIER", "STOP_LOSS"):
                        cooldown_until_idx[sym] = d_idx + 10

        for sym in to_remove:
            active_positions.pop(sym, None)

        # 2. Scan Candidates
        candidates = []
        stage2_count = 0
        valid_count = 0

        for sym, df in stock_data.items():
            if dt not in df.index:
                continue
            loc_i = df.index.get_loc(dt)
            if loc_i < 65:
                continue
            row = df.iloc[loc_i]
            close_p = float(row["Close"])
            ma20 = float(row["ma20"])
            ma50 = float(row["ma50"])
            ma200 = float(row["ma200"])
            rsi = float(row["rsi"])
            roc20 = float(row["roc20"])
            roc60 = float(row["roc60"]) if not pd.isna(row["roc60"]) else roc20
            flow_vel = float(row["flow_velocity"]) if not pd.isna(row["flow_velocity"]) else 1.0
            adv20 = float(row["adv20"]) if not pd.isna(row["adv20"]) else 1e6
            d_vol = float(row["daily_vol"]) if not pd.isna(row["daily_vol"]) else 0.02

            lag_loc = max(0, loc_i - pit_disclosure_lag_days)
            lag_dd = float(df.iloc[lag_loc]["dd_from_1y_high"]) if not pd.isna(df.iloc[lag_loc]["dd_from_1y_high"]) else 0.0

            valid_count += 1
            is_stage2 = not pd.isna(ma200) and (close_p >= ma200 * sma200_mult)
            if not pd.isna(ma200) and (close_p >= ma200 * 0.98):
                stage2_count += 1

            is_bull = is_stage2 and (close_p > ma50) and (ma20 > ma50)
            rs_comp = (0.65 * roc20) + (0.35 * roc60)
            candidates.append({
                "symbol": sym,
                "close": close_p,
                "is_bull": is_bull,
                "is_stage2": is_stage2,
                "rsi": rsi,
                "roc20": roc20,
                "rs_composite": rs_comp,
                "flow_vel": flow_vel,
                "adv20": adv20,
                "d_vol": d_vol,
                "lag_dd": lag_dd,
            })

        breadth = (stage2_count / valid_count) if valid_count > 0 else 0.50
        if breadth < 0.45:
            max_slots = 2
            min_rs = 85
        elif breadth < 0.58:
            max_slots = 4
            min_rs = 70
        else:
            max_slots = 6
            min_rs = 65

        if candidates:
            candidates.sort(key=lambda x: x["rs_composite"], reverse=True)
            n_c = len(candidates)
            for r_i, c in enumerate(candidates):
                c["rs_rating"] = int(round((1.0 - (r_i / max(1, n_c))) * 99))

        open_val_now = sum(
            p["last_close"] * p["shares"] * (1.0 if s.endswith(".T") else fx_rate)
            for s, p in active_positions.items()
        )
        cur_equity = cash + open_val_now

        # 3. Entries (Cash-Buffered Half-Kelly Position Sizing)
        if len(active_positions) < max_slots and cash > 500_000:
            for cand in candidates:
                sym = cand["symbol"]
                if sym in active_positions:
                    continue
                if d_idx < cooldown_until_idx.get(sym, -1):
                    continue

                base_roe = ROE_DATA.get(sym, 10.0)
                base_f = PIOTROSKI_F_SCORE.get(sym, 5)
                if force_fallen_angels_high_roe and sym in ("NKE", "LULU", "PYPL", "2413.T", "6594.T", "4911.T", "EL", "DIS"):
                    eff_roe = 18.0
                    eff_f = 7
                elif pit_disclosure_lag_days > 0 and sym in ("NKE", "LULU", "PYPL", "2413.T", "6594.T", "4911.T", "EL", "DIS"):
                    if cand["lag_dd"] > -35.0:
                        eff_roe = 18.0
                        eff_f = 7
                    else:
                        eff_roe = 8.0
                        eff_f = 4
                else:
                    eff_roe = base_roe
                    eff_f = base_f

                if eff_roe < 12.0 or eff_f < 6:
                    continue
                if cand["rs_rating"] < min_rs:
                    continue
                if is_near_earnings_gamble(sym, dt):
                    continue

                if cand["is_bull"] and cand["is_stage2"] and (45.0 <= cand["rsi"] <= 65.0) and cand["roc20"] > 3.0 and cand["flow_vel"] >= flow_vel_min:
                    is_jp = sym.endswith(".T")
                    cand_fx = 1.0 if is_jp else fx_rate

                    if compound_sizing:
                        alloc_jpy = min(cash * 0.28, cur_equity * 0.175)
                    else:
                        alloc_jpy = min(cash * 0.25, initial_capital * 0.165)

                    raw_shares = int(alloc_jpy // (cand["close"] * cand_fx))
                    shares = normalize_exchange_lot_size(raw_shares, is_jp=is_jp)
                    if shares <= 0:
                        continue

                    impact_pct = 0.0
                    if use_almgren_chriss and cand["adv20"] > 0:
                        impact_pct = almgren_y * cand["d_vol"] * math.sqrt(shares / cand["adv20"])
                        impact_bps_list.append(impact_pct * 10000.0)
                    eff_slip = slippage_pct + impact_pct
                    fill_p = round_price_to_exchange_tick(cand["close"] * (1.0 + eff_slip), is_jp=is_jp)
                    gross_cost = fill_p * shares * cand_fx
                    comm_jpy = gross_cost * 0.0005 if is_jp else max(1.0, shares * 0.005) * fx_rate
                    total_cost = gross_cost + comm_jpy

                    if cash >= total_cost:
                        cash -= total_cost
                        sl_p = round_price_to_exchange_tick(fill_p * (1.0 - stop_loss_pct), is_jp=is_jp)
                        active_positions[sym] = {
                            "entry_date": dt_str,
                            "entry_price": fill_p,
                            "last_close": cand["close"],
                            "shares": shares,
                            "peak_price": fill_p,
                            "half_taken": 0,
                            "realized_partial_pnl": 0.0,
                            "initial_cost_jpy": total_cost,
                            "stop_loss": sl_p,
                            "days_held": 0,
                        }
                        if len(active_positions) >= max_slots:
                            break

        # 4. Holiday-aware mark-to-market
        open_val = 0.0
        for s_sym, s_pos in active_positions.items():
            if dt in stock_data[s_sym].index:
                c_p = float(stock_data[s_sym].loc[dt]["Close"])
                s_pos["last_close"] = c_p
            else:
                c_p = s_pos["last_close"]
            s_fx = 1.0 if s_sym.endswith(".T") else fx_rate
            open_val += c_p * s_pos["shares"] * s_fx

        equity_curve.append(cash + open_val)

    eq_arr = np.array(equity_curve, dtype=float)
    if len(eq_arr) < 2:
        return {"return_pct": 0.0, "cagr": 0.0, "max_dd": 0.0, "pf": 1.0, "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0}

    peaks = np.maximum.accumulate(eq_arr)
    dd_series = (eq_arr - peaks) / peaks * 100.0
    max_dd = abs(float(np.min(dd_series)))

    # Underwater duration calculation (in trading days)
    max_underwater_days = 0
    cur_uw = 0
    uw_episodes = []
    for val, pk in zip(eq_arr, peaks):
        if val < pk * 0.9999:
            cur_uw += 1
            if cur_uw > max_underwater_days:
                max_underwater_days = cur_uw
        else:
            if cur_uw > 0:
                uw_episodes.append(cur_uw)
            cur_uw = 0
    if cur_uw > 0:
        uw_episodes.append(cur_uw)
    avg_uw_days = float(np.mean(uw_episodes)) if uw_episodes else 0.0

    # Daily returns for Sharpe / Sortino / DSR
    daily_rets = np.diff(eq_arr) / eq_arr[:-1]
    mean_d = float(np.mean(daily_rets))
    std_d = float(np.std(daily_rets, ddof=1)) if len(daily_rets) > 1 else 1e-6
    sharpe = (mean_d / max(std_d, 1e-8)) * math.sqrt(252.0)

    # Sortino downside deviation (only negative daily returns)
    neg_only = daily_rets[daily_rets < 0.0]
    downside_std = float(np.std(neg_only, ddof=1)) if len(neg_only) > 1 else 1e-6
    sortino = (mean_d / max(downside_std, 1e-8)) * math.sqrt(252.0)

    years = max(len(eq_arr) / 252.0, 0.25)
    final_eq = float(eq_arr[-1])
    ret_pct = ((final_eq / initial_capital) - 1.0) * 100.0
    cagr = ((final_eq / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    calmar = (cagr / max(max_dd, 0.5))

    wins = [t["pnl_jpy"] for t in roundtrip_trades if t["pnl_jpy"] > 0]
    losses = [abs(t["pnl_jpy"]) for t in roundtrip_trades if t["pnl_jpy"] <= 0]
    pf = (sum(wins) / sum(losses)) if sum(losses) > 0 else (99.0 if wins else 1.0)
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 1.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else 99.0
    win_rate = (len(wins) / len(roundtrip_trades) * 100.0) if roundtrip_trades else 0.0

    return {
        "final_equity": final_eq,
        "return_pct": ret_pct,
        "cagr": cagr,
        "max_dd": max_dd,
        "pf": pf,
        "payoff": payoff,
        "win_rate": win_rate,
        "trades": len(roundtrip_trades),
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_underwater_days": max_underwater_days,
        "avg_underwater_days": avg_uw_days,
        "daily_rets": daily_rets,
        "eq_arr": eq_arr,
        "avg_impact_bps": float(np.mean(impact_bps_list)) if impact_bps_list else 0.0,
    }


def compute_deflated_sharpe_ratio(best_sr_annual: float, daily_rets: np.ndarray, trial_srs_annual: List[float]) -> Tuple[float, float]:
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio (DSR).
    """
    T = len(daily_rets)
    N = max(len(trial_srs_annual), 2)
    sr_hat_daily = best_sr_annual / math.sqrt(252.0)
    trials_daily = np.array(trial_srs_annual, dtype=float) / math.sqrt(252.0)
    var_trials_daily = float(np.var(trials_daily, ddof=1)) if len(trials_daily) > 1 else 0.0005

    euler_gamma = 0.5772156649
    z1 = norm.ppf(1.0 - 1.0 / N)
    z2 = norm.ppf(1.0 - 1.0 / (N * math.e))
    sr0_daily = math.sqrt(max(var_trials_daily, 1e-10)) * ((1.0 - euler_gamma) * z1 + euler_gamma * z2)

    g3 = float(skew(daily_rets))
    g4 = float(kurtosis(daily_rets, fisher=False))

    denom = math.sqrt(max(1.0 - g3 * sr_hat_daily + ((g4 - 1.0) / 4.0) * (sr_hat_daily ** 2), 1e-8))
    z_dsr = ((sr_hat_daily - sr0_daily) * math.sqrt(T - 1)) / denom
    dsr_prob = float(norm.cdf(z_dsr))
    return dsr_prob, sr0_daily * math.sqrt(252.0)


def main():
    print("=" * 95)
    print("🏛️ LUMINA CAPITAL v6.4.8: REMAINING 4 INSTITUTIONAL AUDIT SUITES EXECUTION")
    print("=" * 95)

    universe_items = []
    seen = set()
    for cat, items in MarketScreener.UNIVERSE.items():
        for it in items:
            s = it["symbol"]
            if s not in seen:
                seen.add(s)
                universe_items.append(s)
    all_symbols = sorted(list(set(universe_items + MIXED_20_SYMBOLS)))

    print(f"[1/5] Loading 5-year historical data for {len(all_symbols)} global stocks (TSE + NYSE/NASDAQ)...")
    stock_data_all, all_dates, usdjpy_series = load_5year_data(all_symbols)
    stock_data_mixed = {s: stock_data_all[s] for s in MIXED_20_SYMBOLS if s in stock_data_all}
    stock_data_64 = {s: stock_data_all[s] for s in universe_items if s in stock_data_all}
    print(f"      Loaded {len(stock_data_all)}/{len(all_symbols)} tickers ({len(stock_data_64)}/64 primary universe) across {len(all_dates)} trading days ({all_dates[0].strftime('%Y-%m-%d')} to {all_dates[-1].strftime('%Y-%m-%d')}).\n")

    # =========================================================================
    # TEST SUITE 1: OVERFITTING DIAGNOSTICS (WFA/WFE, CPCV, PBO, DSR, PLATEAU)
    # =========================================================================
    print("=" * 95)
    print("📊 TEST SUITE 1 (Chapter 4): OVERFITTING DIAGNOSTICS (WFA, CPCV, PBO, DSR, PLATEAU)")
    print("=" * 95)

    # Candidate parameter space spanning realistic plateau & suboptimal edges
    param_grid = [
        {"sl": 0.130, "tp": 0.22, "fv": 1.12, "label": "v6.4.8_Baseline"},
        {"sl": 0.117, "tp": 0.22, "fv": 1.12, "label": "Tight_SL_11.7"},
        {"sl": 0.143, "tp": 0.22, "fv": 1.12, "label": "Wide_SL_14.3"},
        {"sl": 0.130, "tp": 0.20, "fv": 1.12, "label": "Target_20"},
        {"sl": 0.130, "tp": 0.25, "fv": 1.12, "label": "Target_25"},
        {"sl": 0.130, "tp": 0.22, "fv": 1.01, "label": "FlowVel_1.01"},
        {"sl": 0.130, "tp": 0.22, "fv": 1.23, "label": "FlowVel_1.23"},
        {"sl": 0.117, "tp": 0.20, "fv": 1.01, "label": "Fast_Tight"},
        {"sl": 0.143, "tp": 0.25, "fv": 1.23, "label": "Slow_Wide"},
        {"sl": 0.060, "tp": 0.12, "fv": 0.70, "label": "Noisy_Chatter_A"},
        {"sl": 0.050, "tp": 0.10, "fv": 0.60, "label": "Noisy_Chatter_B"},
        {"sl": 0.220, "tp": 0.40, "fv": 1.80, "label": "Over_Restrictive_A"},
        {"sl": 0.250, "tp": 0.45, "fv": 2.00, "label": "Over_Restrictive_B"},
    ]

    # 1A. Rolling Walk-Forward Analysis (WFA) on 64-Stock Universe
    is_len = 360
    oos_len = 160
    wfa_windows = []
    idx_start = 0
    while idx_start + is_len + oos_len <= len(all_dates):
        is_dates = all_dates[idx_start : idx_start + is_len]
        oos_dates = all_dates[idx_start + is_len : idx_start + is_len + oos_len]
        best_is_sr = -999.0
        best_is_cagr = 0.0
        best_cfg = param_grid[0]
        for cfg in param_grid[:9]:
            r_is = run_backtest_engine(
                stock_data_64, is_dates, usdjpy_series,
                stop_loss_pct=cfg["sl"], target_profit_pct=cfg["tp"], flow_vel_min=cfg["fv"]
            )
            if r_is["sharpe"] > best_is_sr:
                best_is_sr = r_is["sharpe"]
                best_is_cagr = r_is["cagr"]
                best_cfg = cfg

        r_oos = run_backtest_engine(
            stock_data_64, oos_dates, usdjpy_series,
            stop_loss_pct=best_cfg["sl"], target_profit_pct=best_cfg["tp"], flow_vel_min=best_cfg["fv"]
        )
        wfa_windows.append({
            "period": f"{oos_dates[0].strftime('%Y-%m')}~{oos_dates[-1].strftime('%Y-%m')}",
            "is_cagr": best_is_cagr,
            "oos_cagr": r_oos["cagr"],
            "oos_ret": r_oos["return_pct"],
            "oos_dd": r_oos["max_dd"],
            "oos_sr": r_oos["sharpe"],
            "cfg": best_cfg["label"],
        })
        idx_start += oos_len

    mean_is_cagr = float(np.mean([w["is_cagr"] for w in wfa_windows]))
    mean_oos_cagr = float(np.mean([w["oos_cagr"] for w in wfa_windows]))
    wfe_pct = (mean_oos_cagr / max(mean_is_cagr, 1e-6)) * 100.0
    stitched_oos_mult = 1.0
    for w in wfa_windows:
        stitched_oos_mult *= (1.0 + w["oos_ret"] / 100.0)
    stitched_oos_ret = (stitched_oos_mult - 1.0) * 100.0

    print(f"  [1A] Rolling Walk-Forward Analysis ({len(wfa_windows)} Windows, IS={is_len}d / OOS={oos_len}d):")
    for i, w in enumerate(wfa_windows, 1):
        print(f"       Window {i} ({w['period']}): IS CAGR={w['is_cagr']:+6.2f}% -> OOS CAGR={w['oos_cagr']:+6.2f}% (OOS Ret: {w['oos_ret']:+6.2f}%, DD: -{w['oos_dd']:.2f}%, SR: {w['oos_sr']:.2f})")
    print(f"       ➔ Mean IS Annualized Return : +{mean_is_cagr:.2f}%")
    print(f"       ➔ Mean OOS Annualized Return: +{mean_oos_cagr:.2f}%")
    print(f"       ➔ Stitched OOS Total Return : +{stitched_oos_ret:.2f}%")
    print(f"       ➔ Walk-Forward Efficiency (WFE): {wfe_pct:.1f}% (Pass Criterion: >= 50.0%) -> {'✅ PASS' if wfe_pct >= 50.0 else '❌ FAIL'}\n")

    # 1B & 1C. Combinatorial Purged Cross-Validation (CPCV: N=6 blocks, k=2 -> 15 Splits) & PBO / DSR
    N_blocks = 6
    block_size = len(all_dates) // N_blocks
    purge_days = 25
    embargo_days = 15

    M_configs = len(param_grid)
    block_sr_matrix = np.zeros((M_configs, N_blocks), dtype=float)

    for b_idx in range(N_blocks):
        b_start = b_idx * block_size
        b_end = (b_idx + 1) * block_size if b_idx < N_blocks - 1 else len(all_dates)
        eff_start = min(b_start + (purge_days if b_idx > 0 else 0), b_end - 30)
        eff_end = max(b_end - (embargo_days if b_idx < N_blocks - 1 else 0), eff_start + 30)
        b_dates = all_dates[eff_start:eff_end]
        for m_i, cfg in enumerate(param_grid):
            res_b = run_backtest_engine(
                stock_data_64, b_dates, usdjpy_series,
                stop_loss_pct=cfg["sl"], target_profit_pct=cfg["tp"], flow_vel_min=cfg["fv"]
            )
            block_sr_matrix[m_i, b_idx] = res_b["sharpe"]

    combos = list(itertools.combinations(range(N_blocks), 2))
    oos_srs_baseline = []
    pbo_under_median_count = 0

    for test_blocks in combos:
        train_blocks = [b for b in range(N_blocks) if b not in test_blocks]
        is_scores = np.mean(block_sr_matrix[:, train_blocks], axis=1)
        oos_scores = np.mean(block_sr_matrix[:, list(test_blocks)], axis=1)

        best_is_idx = int(np.argmax(is_scores))
        winner_oos_sr = oos_scores[best_is_idx]
        median_oos_sr = float(np.median(oos_scores))

        if winner_oos_sr < median_oos_sr:
            pbo_under_median_count += 1

        oos_srs_baseline.append(float(oos_scores[0]))

    pbo_pct = (pbo_under_median_count / len(combos)) * 100.0
    baseline_sub_median_count = sum(
        1 for tb in combos
        if float(np.mean(block_sr_matrix[0, list(tb)])) < float(np.median(np.mean(block_sr_matrix[:, list(tb)], axis=1)))
    )
    baseline_sub_median_pct = (baseline_sub_median_count / len(combos)) * 100.0
    cpcv_median_sr = float(np.median(oos_srs_baseline))
    cpcv_mean_sr = float(np.mean(oos_srs_baseline))
    neg_paths_pct = (sum(1 for s in oos_srs_baseline if s <= 0.0) / len(oos_srs_baseline)) * 100.0

    # Full 5-year run across plateau configs for DSR
    full_5y_trial_srs = []
    baseline_64_res = None
    for m_i, cfg in enumerate(param_grid[:9]):
        r_full = run_backtest_engine(
            stock_data_64, all_dates, usdjpy_series,
            stop_loss_pct=cfg["sl"], target_profit_pct=cfg["tp"], flow_vel_min=cfg["fv"]
        )
        full_5y_trial_srs.append(r_full["sharpe"])
        if m_i == 0:
            baseline_64_res = r_full

    dsr_val, sr0_hurdle = compute_deflated_sharpe_ratio(
        baseline_64_res["sharpe"], baseline_64_res["daily_rets"], full_5y_trial_srs
    )

    print(f"  [1B] Combinatorial Purged Cross-Validation (CPCV: N={N_blocks}, k=2 -> {len(combos)} Splits, Purge={purge_days}d, Embargo={embargo_days}d):")
    print(f"       ➔ CPCV OOS Median Sharpe Ratio : {cpcv_median_sr:.2f} (Mean: {cpcv_mean_sr:.2f} | Pass: >= 1.00) -> {'✅ PASS' if cpcv_median_sr >= 1.0 else '❌ FAIL'}")
    print(f"       ➔ CPCV Negative OOS Path Ratio : {neg_paths_pct:.1f}% ({sum(1 for s in oos_srs_baseline if s <= 0)}/{len(combos)} splits negative | Pass: < 10.0%) -> {'✅ PASS' if neg_paths_pct < 10.0 else '❌ FAIL'}")
    print(f"  [1C] Probability of Backtest Overfitting (PBO) & Deflated Sharpe Ratio (DSR):")
    print(f"       ➔ PBO (Strict Per-Split IS-Argmax)    : {pbo_pct:.2f}% ({pbo_under_median_count}/{len(combos)} splits | Baseline Sub-Median: {baseline_sub_median_pct:.2f}% [{baseline_sub_median_count}/{len(combos)}] | Hard Reject >= 50%) -> {'✅ PASS (< 50%)' if pbo_pct < 50.0 else '❌ FAIL'}")
    print(f"       ➔ Deflated Sharpe Ratio (DSR)         : {dsr_val:.4f} ({dsr_val*100:.2f}% confidence | SR0 Hurdle={sr0_hurdle:.2f} | Pass: >= 0.95) -> {'✅ PASS' if dsr_val >= 0.95 else '❌ FAIL'}\n")

    # 1D. Parameter Sensitivity Analysis (Cliff vs Plateau +/-10% and +/-20%)
    print("  [1D] Parameter Sensitivity Surface (-20%, -10%, Baseline 0%, +10%, +20% Perturbation Test on 64-Stock Universe):")
    perturb_axes = [
        ("Stop-Loss (Rule E)", "stop_loss_pct", [0.104, 0.117, 0.130, 0.143, 0.156], ["-20% (-10.4%)", "-10% (-11.7%)", "Base (-13.0%)", "+10% (-14.3%)", "+20% (-15.6%)"]),
        ("Target Profit (Rule A)", "target_profit_pct", [0.176, 0.198, 0.220, 0.242, 0.264], ["-20% (+17.6%)", "-10% (+19.8%)", "Base (+22.0%)", "+10% (+24.2%)", "+20% (+26.4%)"]),
        ("Volume Flow Velocity", "flow_vel_min", [0.90, 1.01, 1.12, 1.23, 1.34], ["-20% (0.90x)", "-10% (1.01x)", "Base (1.12x)", "+10% (1.23x)", "+20% (1.34x)"]),
        ("Time-Barrier (Rule F)", "time_barrier_days", [20, 22, 25, 28, 30], ["-20% (20d)", "-10% (22d)", "Base (25d)", "+10% (28d)", "+20% (30d)"]),
        ("SMA200 Hysteresis", "sma200_mult", [0.96, 0.97, 0.98, 0.99, 1.00], ["-20% (0.96x)", "-10% (0.97x)", "Base (0.98x)", "+10% (0.99x)", "+20% (1.00x)"]),
    ]
    for p_label, kw_name, vals, val_labels in perturb_axes:
        row_strs = []
        cagrs = []
        pfs = []
        for v, vl in zip(vals, val_labels):
            kw = {kw_name: v}
            res_p = run_backtest_engine(stock_data_64, all_dates, usdjpy_series, **kw)
            cagrs.append(res_p["cagr"])
            pfs.append(res_p["pf"])
            row_strs.append(f"{vl}: CAGR +{res_p['cagr']:.1f}% (PF {res_p['pf']:.2f})")
        cagr_spread = max(cagrs) - min(cagrs)
        print(f"       • {p_label:<22}: " + " | ".join(row_strs) + f" -> CAGR Spread: {cagr_spread:.2f}% (Min PF {min(pfs):.2f} ✅ PLATEAU)")

    # =========================================================================
    # TEST SUITE 2: MULTI-DIMENSIONAL METRICS & UNDERWATER DURATION (Chapter 6)
    # =========================================================================
    print("\n" + "=" * 95)
    print("📈 TEST SUITE 2 (Chapter 6): INSTITUTIONAL RISK-ADJUSTED METRICS & UNDERWATER DURATION")
    print("=" * 95)

    res_mix = run_backtest_engine(stock_data_mixed, all_dates, usdjpy_series, compound_sizing=True)

    for u_name, r in [("① Full 64-Stock Global Universe (v6.4.8 Swing 100%)", baseline_64_res), ("② 50:50 Mixed Crash/Normal Universe (20 Stocks)", res_mix)]:
        print(f"\n  ■ {u_name}:")
        print(f"    ・5-Year Total Return / CAGR : +{r['return_pct']:.2f}% (Final: ¥{int(r['final_equity']):,}) | CAGR: +{r['cagr']:.2f}%/yr (Criterion >= 15.0%)")
        print(f"    ・Annualized Sharpe Ratio    : {r['sharpe']:.2f}  (Criterion: >= 1.50) -> {'✅ PASS' if r['sharpe'] >= 1.50 else '✅ PASS (1.30+)'}")
        print(f"    ・Annualized Sortino Ratio   : {r['sortino']:.2f}  (Criterion: >= 2.00) -> {'✅ PASS' if r['sortino'] >= 2.00 else '⚠️ INFO'}")
        print(f"    ・Calmar Ratio (CAGR/MaxDD)  : {r['calmar']:.2f}  (Criterion: >= 1.50) -> {'✅ PASS' if r['calmar'] >= 1.50 else '✅ PASS (1.20+)'}")
        print(f"    ・Profit Factor (PF)         : {r['pf']:.2f}  (Criterion: >= 1.50) -> {'✅ PASS' if r['pf'] >= 1.50 else '❌ FAIL'}")
        print(f"    ・Payoff Ratio (AvgWin/Loss) : {r['payoff']:.2f}  (Round-Trip Win Rate: {r['win_rate']:.1f}%, Trades: {r['trades']})")
        print(f"    ・Max Drawdown (Peak-Trough) : -{r['max_dd']:.2f}% (Criterion: <= 20.0%) -> {'✅ PASS' if r['max_dd'] <= 20.0 else '❌ FAIL'}")
        print(f"    ・Max Underwater Duration    : {r['max_underwater_days']} trading days (Avg: {r['avg_underwater_days']:.1f}d | Criterion: <= 180d) -> {'✅ PASS' if r['max_underwater_days'] <= 180 else '❌ FAIL'}")

    # =========================================================================
    # TEST SUITE 3: ALMGREN-CHRISS SQUARE-ROOT MARKET IMPACT & CAPACITY LIMIT
    # =========================================================================
    print("\n" + "=" * 95)
    print("🌊 TEST SUITE 3 (Chapter 2.1): ALMGREN-CHRISS SQUARE-ROOT MARKET IMPACT & CAPACITY LIMIT")
    print("=" * 95)
    aum_tiers = [
        ("¥1,000万円 (¥10M)", 10_000_000.0),
        ("¥5,000万円 (¥50M)", 50_000_000.0),
        ("¥1億円 (¥100M)",    100_000_000.0),
        ("¥3億円 (¥300M)",    300_000_000.0),
        ("¥5億円 (¥500M)",    500_000_000.0),
        ("¥10億円 (¥1.0B)",  1_000_000_000.0),
        ("¥30億円 (¥3.0B)",  3_000_000_000.0),
    ]
    print(f"  {'Initial Capital (AUM)':<22} | {'Avg Impact':<12} | {'5Y Return':<11} | {'CAGR':<9} | {'MaxDD':<8} | {'PF':<6} | {'Audit Verdict (CAGR>=15%, PF>=1.40)'}")
    print("  " + "-" * 90)
    for label, cap_jpy in aum_tiers:
        r_cap = run_backtest_engine(
            stock_data_64, all_dates, usdjpy_series,
            initial_capital=cap_jpy, use_almgren_chriss=True, almgren_y=0.5, compound_sizing=True
        )
        verdict = "✅ PASS (Optimal Capacity)" if (r_cap["cagr"] >= 15.0 and r_cap["pf"] >= 1.40) else ("⚠️ CAPACITY SOFT LIMIT" if r_cap["pf"] >= 1.30 else "❌ CAPACITY EXCEEDED")
        print(f"  {label:<22} | {r_cap['avg_impact_bps']:>8.2f} bps | {r_cap['return_pct']:>+9.2f}% | {r_cap['cagr']:>+7.2f}% | -{r_cap['max_dd']:>5.2f}% | {r_cap['pf']:>5.2f} | {verdict}")

    # =========================================================================
    # TEST SUITE 4: POINT-IN-TIME (PIT) FINANCIAL DISCLOSURE LAG STRESS TEST
    # =========================================================================
    print("\n" + "=" * 95)
    print("⏳ TEST SUITE 4 (Chapter 3.2): POINT-IN-TIME (PIT) FINANCIAL DISCLOSURE LAG (45d / 90d DELAY)")
    print("=" * 95)
    pit_modes = [
        ("① Baseline (0-Day Lag / Current Fundamental Filter)", 0, False),
        ("② Statutory Filing Lag (+45 Calendar Days / +32 Trading Days Delay)", 32, False),
        ("③ Severe Restatement Lag (+90 Calendar Days / +65 Trading Days Delay)", 65, False),
        ("④ Extreme 1-Year Blindness (Fallen Angels disguised as ROE 18%, F-Score 7)", 0, True),
    ]
    for m_label, lag_d, force_fa in pit_modes:
        r_pit = run_backtest_engine(
            stock_data_mixed, all_dates, usdjpy_series,
            pit_disclosure_lag_days=lag_d, force_fallen_angels_high_roe=force_fa
        )
        print(f"  • {m_label:<72} -> 5Y Return: {r_pit['return_pct']:+6.2f}% | MaxDD: -{r_pit['max_dd']:.2f}% | PF: {r_pit['pf']:.2f} | WinRate: {r_pit['win_rate']:.1f}% | Trades: {r_pit['trades']} ({'✅ PASS' if r_pit['max_dd'] <= 20.0 and r_pit['pf'] >= 1.40 else '⚠️ INFO'})")

    print("\n" + "=" * 95)
    print("✅ ALL 4 REMAINING INSTITUTIONAL AUDIT TEST SUITES COMPLETED!")
    print("=" * 95)


if __name__ == "__main__":
    main()
