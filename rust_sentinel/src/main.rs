#![forbid(unsafe_code)]
//! Lumina Capital — Ultra-Low-Latency Sentinel & Volume Clock Engine (`lumina-sentinel-rs`)
//!
//! Architecture:
//! 1. **Zero `unsafe` End-to-End**: Enforced at compiler level via `#![forbid(unsafe_code)]`.
//! 2. **Cache-Resident SoA (Structure of Arrays)**:
//!    - Contiguous memory arrays (`Vec<f64>`, `Vec<u8>`) aligned for L1/L2 CPU cache residency
//!      and automatic LLVM SIMD vectorization (`opt-level = 3`, `lto = "fat"`).
//! 3. **Event / Volume Clocks over Wall-Clock Timers**:
//!    - Easley, Lopez de Prado, O'Hara (2012) Volume Clock construction & Continuous Information
//!      Flow Velocity (`flow_velocity`) in pure Rust.
//! 4. **Sub-Microsecond 5-Tier Risk & Exit Sentinel**:
//!    - Evaluates Rule A (Target), Rule B (+10% Half Profit & Breakeven Lock), Rule B2 (Call Wall Half),
//!      Rule C (Peak -4% Trailing), Rule D (Breakeven Stop), Rule E (-13% Fibonacci Stop / DAY_CIS Wall Stop),
//!      and Monotonically Tightening Stop updates in nanoseconds per position.

use std::env;
use std::io::{self, BufRead, Write};
use std::time::Instant;

/// Action codes emitted by `SoAPositionBook::evaluate_all`
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SentinelAction {
    Hold = 0,
    RuleAFullProfit = 1,
    RuleBHalfProfit = 2,
    RuleB2CallWallHalf = 3,
    RuleCTrailingStop = 4,
    RuleDBreakevenStop = 5,
    RuleEFibStop = 6,
    DayCisTargetProfit = 7,
    DayCisWallStop = 8,
}

impl SentinelAction {
    #[inline(always)]
    pub fn as_str(self) -> &'static str {
        match self {
            SentinelAction::Hold => "HOLD",
            SentinelAction::RuleAFullProfit => "RULE_A_FULL_PROFIT",
            SentinelAction::RuleBHalfProfit => "RULE_B_HALF_PROFIT",
            SentinelAction::RuleB2CallWallHalf => "RULE_B2_CALL_WALL_HALF",
            SentinelAction::RuleCTrailingStop => "RULE_C_TRAILING_STOP",
            SentinelAction::RuleDBreakevenStop => "RULE_D_BREAKEVEN_STOP",
            SentinelAction::RuleEFibStop => "RULE_E_FIB_STOP",
            SentinelAction::DayCisTargetProfit => "DAY_CIS_TARGET_PROFIT",
            SentinelAction::DayCisWallStop => "DAY_CIS_WALL_STOP",
        }
    }
}

/// Cache-Resident Structure of Arrays (SoA) Position Book.
/// Instead of AoS (`Vec<Position>`), every numerical field is stored in its own contiguous
/// vector so the CPU prefetcher and SIMD units stream purely sequential floats without cache pollution.
pub struct SoAPositionBook {
    pub symbols: Vec<String>,
    pub entries: Vec<f64>,
    pub currents: Vec<f64>,
    pub peaks: Vec<f64>,
    pub stops: Vec<f64>,
    pub targets: Vec<f64>,
    pub call_walls: Vec<f64>,
    pub is_half_profits: Vec<u8>,
    pub is_day_trades: Vec<u8>,
    // Output buffers pre-allocated to avoid heap allocation during hot loop
    pub out_actions: Vec<SentinelAction>,
    pub out_new_peaks: Vec<f64>,
    pub out_new_stops: Vec<f64>,
    pub out_pnl_pcts: Vec<f64>,
    pub out_drawdowns: Vec<f64>,
}

impl SoAPositionBook {
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            symbols: Vec::with_capacity(cap),
            entries: Vec::with_capacity(cap),
            currents: Vec::with_capacity(cap),
            peaks: Vec::with_capacity(cap),
            stops: Vec::with_capacity(cap),
            targets: Vec::with_capacity(cap),
            call_walls: Vec::with_capacity(cap),
            is_half_profits: Vec::with_capacity(cap),
            is_day_trades: Vec::with_capacity(cap),
            out_actions: Vec::with_capacity(cap),
            out_new_peaks: Vec::with_capacity(cap),
            out_new_stops: Vec::with_capacity(cap),
            out_pnl_pcts: Vec::with_capacity(cap),
            out_drawdowns: Vec::with_capacity(cap),
        }
    }

    pub fn clear(&mut self) {
        self.symbols.clear();
        self.entries.clear();
        self.currents.clear();
        self.peaks.clear();
        self.stops.clear();
        self.targets.clear();
        self.call_walls.clear();
        self.is_half_profits.clear();
        self.is_day_trades.clear();
        self.out_actions.clear();
        self.out_new_peaks.clear();
        self.out_new_stops.clear();
        self.out_pnl_pcts.clear();
        self.out_drawdowns.clear();
    }

    #[allow(clippy::too_many_arguments)]
    pub fn push(
        &mut self,
        symbol: String,
        entry: f64,
        current: f64,
        peak: f64,
        stop: f64,
        target: f64,
        call_wall: f64,
        is_half_profit: u8,
        is_day_trade: u8,
    ) {
        self.symbols.push(symbol);
        self.entries.push(entry);
        self.currents.push(current);
        self.peaks.push(peak);
        self.stops.push(stop);
        self.targets.push(target);
        self.call_walls.push(call_wall);
        self.is_half_profits.push(is_half_profit);
        self.is_day_trades.push(is_day_trade);
        self.out_actions.push(SentinelAction::Hold);
        self.out_new_peaks.push(peak);
        self.out_new_stops.push(stop);
        self.out_pnl_pcts.push(0.0);
        self.out_drawdowns.push(0.0);
    }

    #[inline(always)]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Hot-path SoA evaluation across all open positions.
    /// Zero heap allocations during execution.
    #[inline(never)]
    pub fn evaluate_all(&mut self) {
        let n = self.entries.len();
        for i in 0..n {
            let entry = self.entries[i];
            let cur = self.currents[i];
            let prev_peak = self.peaks[i].max(entry);
            let prev_stop = self.stops[i];
            let target = self.targets[i];
            let call_wall = self.call_walls[i];
            let is_half = self.is_half_profits[i] != 0;
            let is_day = self.is_day_trades[i] != 0;

            let new_peak = if cur > prev_peak { cur } else { prev_peak };
            self.out_new_peaks[i] = new_peak;

            if entry <= 0.0 || cur <= 0.0 {
                self.out_actions[i] = SentinelAction::Hold;
                self.out_new_stops[i] = prev_stop;
                self.out_pnl_pcts[i] = 0.0;
                self.out_drawdowns[i] = 0.0;
                continue;
            }

            let pnl_pct = ((cur - entry) / entry) * 100.0;
            let max_gain_pct = ((new_peak - entry) / entry) * 100.0;
            let drawdown_from_peak = if new_peak > 0.0 {
                ((cur - new_peak) / new_peak) * 100.0
            } else {
                0.0
            };

            self.out_pnl_pcts[i] = pnl_pct;
            self.out_drawdowns[i] = drawdown_from_peak;

            if is_day {
                // DAY_CIS Intraday Order-Book Wall Stop & Target Logic
                let effective_stop = if prev_stop > 0.0 {
                    prev_stop
                } else {
                    entry * 0.985
                };
                self.out_new_stops[i] = effective_stop;

                if cur <= effective_stop {
                    self.out_actions[i] = SentinelAction::DayCisWallStop;
                } else if target > 0.0 && cur >= target {
                    self.out_actions[i] = SentinelAction::DayCisTargetProfit;
                } else {
                    self.out_actions[i] = SentinelAction::Hold;
                }
                continue;
            }

            // Swing 5-Tier Quantitative Risk Rules (Rules A, B, B2, C, D, E)
            // Monotonically Tightening Dynamic Stop calculation:
            let fib_stop = entry * 0.87; // -13% Fibonacci Stop
            let mut candidate_stop = if prev_stop > 0.0 {
                prev_stop.max(fib_stop)
            } else {
                fib_stop
            };

            if is_half {
                // Once half profit is taken, stop can never fall below entry (Breakeven Lock)
                if entry > candidate_stop {
                    candidate_stop = entry;
                }
            }
            if max_gain_pct >= 5.0 {
                // Peak -4% trailing floor
                let trail_stop = new_peak * 0.96;
                if trail_stop > candidate_stop {
                    candidate_stop = trail_stop;
                }
            }
            self.out_new_stops[i] = candidate_stop;

            // Priority Evaluation:
            // Rule A: Full Target Reached (+25% or explicit target_price)
            if (target > 0.0 && cur >= target) || pnl_pct >= 25.0 {
                self.out_actions[i] = SentinelAction::RuleAFullProfit;
            }
            // Rule B2: Option Call Wall Front-Run Half Profit (within 0.3% of Call Wall & PnL >= +3%)
            else if !is_half && call_wall > entry && cur >= call_wall * 0.997 && pnl_pct >= 3.0 {
                self.out_actions[i] = SentinelAction::RuleB2CallWallHalf;
                self.out_new_stops[i] = candidate_stop.max(entry);
            }
            // Rule B: +10% Half Profit & Breakeven Lock
            else if !is_half && pnl_pct >= 10.0 {
                self.out_actions[i] = SentinelAction::RuleBHalfProfit;
                self.out_new_stops[i] = candidate_stop.max(entry);
            }
            // Rule D: Breakeven Stop (After Half Profit, price drops back to/below Entry)
            else if is_half && cur <= entry {
                self.out_actions[i] = SentinelAction::RuleDBreakevenStop;
            }
            // Rule C: Trailing Stop from Peak (Max Gain >= +5% and Drawdown <= -4%)
            else if max_gain_pct >= 5.0 && drawdown_from_peak <= -4.0 {
                self.out_actions[i] = SentinelAction::RuleCTrailingStop;
            }
            // Rule E: -13% Fibonacci Hard Stop (or custom tightened stop)
            else if pnl_pct <= -13.0 || (prev_stop > 0.0 && cur <= prev_stop) {
                self.out_actions[i] = SentinelAction::RuleEFibStop;
            } else {
                self.out_actions[i] = SentinelAction::Hold;
            }
        }
    }
}

/// Cache-Resident SoA Volume Clock & Information Flow Velocity Engine.
pub struct SoAVolumeClock {
    pub bar_opens: Vec<f64>,
    pub bar_highs: Vec<f64>,
    pub bar_lows: Vec<f64>,
    pub bar_closes: Vec<f64>,
    pub bar_vwaps: Vec<f64>,
    pub bar_volumes: Vec<f64>,
    pub bar_durations_sec: Vec<f64>,
}

#[derive(Debug, Clone, Copy)]
pub struct VolumeClockMetrics {
    pub num_bars: usize,
    pub timeout_bars: usize,
    pub volume_threshold: f64,
    pub latest_vwap: f64,
    pub latest_close: f64,
    pub is_bullish: bool,
    pub flow_velocity: f64,
    pub excess_kurtosis: f64,
}

impl SoAVolumeClock {
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            bar_opens: Vec::with_capacity(cap),
            bar_highs: Vec::with_capacity(cap),
            bar_lows: Vec::with_capacity(cap),
            bar_closes: Vec::with_capacity(cap),
            bar_vwaps: Vec::with_capacity(cap),
            bar_volumes: Vec::with_capacity(cap),
            bar_durations_sec: Vec::with_capacity(cap),
        }
    }

    pub fn clear(&mut self) {
        self.bar_opens.clear();
        self.bar_highs.clear();
        self.bar_lows.clear();
        self.bar_closes.clear();
        self.bar_vwaps.clear();
        self.bar_volumes.clear();
        self.bar_durations_sec.clear();
    }

    /// Transforms chronological OHLCV + timestamp (epoch seconds) arrays into Volume Clock bars
    /// with wall-clock timeout fallback (max 30m / 4x base interval) for illiquid lulls/halts,
    /// and computes continuous information flow velocity & return kurtosis in a single cache-resident pass.
    pub fn sample_and_analyze(
        &mut self,
        timestamps: &[f64],
        opens: &[f64],
        highs: &[f64],
        lows: &[f64],
        closes: &[f64],
        volumes: &[f64],
        target_bars_ratio: f64,
    ) -> VolumeClockMetrics {
        self.clear();
        let n = closes.len();
        if n < 5 {
            return VolumeClockMetrics {
                num_bars: 0,
                timeout_bars: 0,
                volume_threshold: 0.0,
                latest_vwap: closes.last().copied().unwrap_or(0.0),
                latest_close: closes.last().copied().unwrap_or(0.0),
                is_bullish: false,
                flow_velocity: 1.0,
                excess_kurtosis: 0.0,
            };
        }

        let mut total_vol = 0.0;
        for &v in volumes {
            if v > 0.0 {
                total_vol += v;
            }
        }

        let target_bars = ((n as f64) * target_bars_ratio).max(5.0);
        let threshold = (total_vol / target_bars).max(1.0);

        // Fallback default interval duration in seconds
        let default_dt = if n >= 2 {
            (timestamps[n - 1] - timestamps[0]).abs() / ((n - 1) as f64)
        } else {
            300.0
        }
        .max(1.0);
        let max_timeout_sec = (default_dt * 4.0).max(1800.0);

        let mut acc_vol = 0.0;
        let mut acc_pv = 0.0;
        let mut cur_open = opens[0];
        let mut cur_high = highs[0];
        let mut cur_low = lows[0];
        let mut start_ts = timestamps[0];
        let mut timeout_bars_count: usize = 0;

        for i in 0..n {
            let v = volumes[i].max(0.0);
            if acc_vol == 0.0 {
                cur_open = opens[i];
                cur_high = highs[i];
                cur_low = lows[i];
                start_ts = timestamps[i];
            } else {
                if highs[i] > cur_high {
                    cur_high = highs[i];
                }
                if lows[i] < cur_low {
                    cur_low = lows[i];
                }
            }

            let typical_price = (highs[i] + lows[i] + closes[i]) / 3.0;
            acc_vol += v;
            acc_pv += typical_price * v;

            let raw_dt = (timestamps[i] - start_ts).abs();
            let is_timeout = acc_vol > 0.0 && raw_dt >= max_timeout_sec;

            if acc_vol >= threshold || is_timeout || i == n - 1 {
                if is_timeout && acc_vol < threshold {
                    timeout_bars_count += 1;
                }
                let close_p = closes[i];
                let vwap = if acc_vol > 0.0 {
                    acc_pv / acc_vol
                } else {
                    close_p
                };
                let dt_sec = if raw_dt > 0.0 {
                    raw_dt + default_dt
                } else {
                    default_dt
                };

                self.bar_opens.push(cur_open);
                self.bar_highs.push(cur_high);
                self.bar_lows.push(cur_low);
                self.bar_closes.push(close_p);
                self.bar_vwaps.push(vwap);
                self.bar_volumes.push(acc_vol);
                self.bar_durations_sec.push(dt_sec);

                acc_vol = 0.0;
                acc_pv = 0.0;
            }
        }

        let m = self.bar_closes.len();
        if m == 0 {
            return VolumeClockMetrics {
                num_bars: 0,
                timeout_bars: 0,
                volume_threshold: threshold,
                latest_vwap: 0.0,
                latest_close: 0.0,
                is_bullish: false,
                flow_velocity: 1.0,
                excess_kurtosis: 0.0,
            };
        }

        // Compute Continuous Information Flow Velocity (volume digested per second vs rolling 20-bar baseline)
        let latest_rate = self.bar_volumes[m - 1] / self.bar_durations_sec[m - 1].max(1.0);
        let lookback_start = m.saturating_sub(20);
        let mut sum_rate = 0.0;
        let count_rate = (m - lookback_start) as f64;
        for j in lookback_start..m {
            sum_rate += self.bar_volumes[j] / self.bar_durations_sec[j].max(1.0);
        }
        let avg_rate = (sum_rate / count_rate).max(1e-9);
        let flow_velocity = latest_rate / avg_rate;

        let latest_close = self.bar_closes[m - 1];
        let latest_open = self.bar_opens[m - 1];
        let latest_vwap = self.bar_vwaps[m - 1];
        let is_bullish = latest_close >= latest_open && latest_close >= latest_vwap;

        let excess_kurtosis = compute_excess_kurtosis(&self.bar_closes);

        VolumeClockMetrics {
            num_bars: m,
            timeout_bars: timeout_bars_count,
            volume_threshold: threshold,
            latest_vwap,
            latest_close,
            is_bullish,
            flow_velocity,
            excess_kurtosis,
        }
    }
}

/// Computes sample excess kurtosis (Fisher's definition, Normal = 0.0) of percentage returns.
#[inline]
pub fn compute_excess_kurtosis(prices: &[f64]) -> f64 {
    if prices.len() < 5 {
        return 0.0;
    }
    let n = prices.len() - 1;
    let mut sum = 0.0;
    for i in 0..n {
        let p0 = prices[i];
        let r = if p0 > 0.0 {
            (prices[i + 1] - p0) / p0
        } else {
            0.0
        };
        sum += r;
    }
    let mean = sum / (n as f64);

    let mut m2 = 0.0;
    let mut m4 = 0.0;
    for i in 0..n {
        let p0 = prices[i];
        let r = if p0 > 0.0 {
            (prices[i + 1] - p0) / p0
        } else {
            0.0
        };
        let d = r - mean;
        let d2 = d * d;
        m2 += d2;
        m4 += d2 * d2;
    }
    let var = m2 / (n as f64);
    if var <= 1e-18 {
        return 0.0;
    }
    let kurt = (m4 / (n as f64)) / (var * var);
    kurt - 3.0
}

/// Processes a single TSV/pipe batch of positions and returns JSON lines.
/// Input protocol:
/// `EVAL_POS|symbol,entry,current,peak,stop,target,call_wall,is_half,is_day;symbol2,...`
fn handle_eval_positions(payload: &str, book: &mut SoAPositionBook) -> String {
    let t0 = Instant::now();
    book.clear();

    for item in payload.split(';') {
        let item = item.trim();
        if item.is_empty() {
            continue;
        }
        let parts: Vec<&str> = item.split(',').collect();
        if parts.len() < 9 {
            continue;
        }
        let sym = parts[0].trim().to_string();
        let entry = parts[1].parse::<f64>().unwrap_or(0.0);
        let current = parts[2].parse::<f64>().unwrap_or(0.0);
        let peak = parts[3].parse::<f64>().unwrap_or(entry);
        let stop = parts[4].parse::<f64>().unwrap_or(0.0);
        let target = parts[5].parse::<f64>().unwrap_or(0.0);
        let call_wall = parts[6].parse::<f64>().unwrap_or(0.0);
        let is_half = parts[7].parse::<u8>().unwrap_or(0);
        let is_day = parts[8].parse::<u8>().unwrap_or(0);

        book.push(
            sym, entry, current, peak, stop, target, call_wall, is_half, is_day,
        );
    }

    book.evaluate_all();
    let elapsed_ns = t0.elapsed().as_nanos();

    let mut out = String::with_capacity(256 + book.len() * 128);
    out.push_str("{\"status\":\"ok\",\"engine\":\"lumina-sentinel-rs\",\"forbid_unsafe\":true,\"elapsed_ns\":");
    out.push_str(&elapsed_ns.to_string());
    out.push_str(",\"results\":[");

    for i in 0..book.len() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&format!(
            "{{\"symbol\":\"{}\",\"action\":\"{}\",\"new_peak\":{:.4},\"new_stop\":{:.4},\"pnl_pct\":{:.4},\"drawdown_pct\":{:.4}}}",
            book.symbols[i],
            book.out_actions[i].as_str(),
            book.out_new_peaks[i],
            book.out_new_stops[i],
            book.out_pnl_pcts[i],
            book.out_drawdowns[i]
        ));
    }
    out.push_str("]}");
    out
}

/// Processes Volume Clock sampling over pipe:
/// `EVAL_VC|ratio|ts,open,high,low,close,vol;ts2,open2,...`
fn handle_eval_volume_clock(payload: &str, vc: &mut SoAVolumeClock) -> String {
    let t0 = Instant::now();
    let mut parts_iter = payload.splitn(2, '|');
    let ratio_str = parts_iter.next().unwrap_or("0.5");
    let rows_str = parts_iter.next().unwrap_or("");
    let ratio = ratio_str.parse::<f64>().unwrap_or(0.5).clamp(0.05, 1.0);

    let mut ts = Vec::with_capacity(512);
    let mut opens = Vec::with_capacity(512);
    let mut highs = Vec::with_capacity(512);
    let mut lows = Vec::with_capacity(512);
    let mut closes = Vec::with_capacity(512);
    let mut vols = Vec::with_capacity(512);

    for row in rows_str.split(';') {
        let row = row.trim();
        if row.is_empty() {
            continue;
        }
        let cols: Vec<&str> = row.split(',').collect();
        if cols.len() < 6 {
            continue;
        }
        ts.push(cols[0].parse::<f64>().unwrap_or(0.0));
        opens.push(cols[1].parse::<f64>().unwrap_or(0.0));
        highs.push(cols[2].parse::<f64>().unwrap_or(0.0));
        lows.push(cols[3].parse::<f64>().unwrap_or(0.0));
        closes.push(cols[4].parse::<f64>().unwrap_or(0.0));
        vols.push(cols[5].parse::<f64>().unwrap_or(0.0));
    }

    let metrics = vc.sample_and_analyze(&ts, &opens, &highs, &lows, &closes, &vols, ratio);
    let elapsed_ns = t0.elapsed().as_nanos();

    format!(
        "{{\"status\":\"ok\",\"engine\":\"lumina-sentinel-rs\",\"elapsed_ns\":{},\"num_bars\":{},\"timeout_bars\":{},\"volume_threshold\":{:.2},\"latest_vwap\":{:.4},\"latest_close\":{:.4},\"is_bullish\":{},\"flow_velocity\":{:.4},\"excess_kurtosis\":{:.4}}}",
        elapsed_ns,
        metrics.num_bars,
        metrics.timeout_bars,
        metrics.volume_threshold,
        metrics.latest_vwap,
        metrics.latest_close,
        if metrics.is_bullish { "true" } else { "false" },
        metrics.flow_velocity,
        metrics.excess_kurtosis
    )
}

fn run_benchmark() {
    let mut book = SoAPositionBook::with_capacity(1000);
    for i in 0..1000 {
        let entry = 100.0 + (i as f64) * 0.1;
        let current = match i % 6 {
            0 => entry * 1.26, // Rule A
            1 => entry * 1.11, // Rule B
            2 => entry * 1.04, // Rule B2 near call wall
            3 => entry * 1.02, // Rule C drawdown from 1.08 peak
            4 => entry * 0.86, // Rule E
            _ => entry * 1.01, // Hold
        };
        let peak = if i % 6 == 3 {
            entry * 1.08
        } else {
            current.max(entry)
        };
        let call_wall = if i % 6 == 2 { entry * 1.041 } else { 0.0 };
        book.push(
            format!("SYM{}", i),
            entry,
            current,
            peak,
            entry * 0.87,
            entry * 1.25,
            call_wall,
            0,
            0,
        );
    }

    // Warmup L1/L2 cache
    for _ in 0..100 {
        book.evaluate_all();
    }

    let iterations = 10_000;
    let t0 = Instant::now();
    for _ in 0..iterations {
        book.evaluate_all();
    }
    let total_ns = t0.elapsed().as_nanos();
    let per_batch_ns = total_ns / (iterations as u128);
    let per_pos_ns = (total_ns as f64) / ((iterations * 1000) as f64);

    // Benchmark SoAVolumeClock on 1,000 bars
    let mut ts = Vec::with_capacity(1000);
    let mut opens = Vec::with_capacity(1000);
    let mut highs = Vec::with_capacity(1000);
    let mut lows = Vec::with_capacity(1000);
    let mut closes = Vec::with_capacity(1000);
    let mut vols = Vec::with_capacity(1000);
    for i in 0..1000 {
        let p = 150.0 + ((i as f64) * 0.05).sin() * 3.0;
        ts.push(1_700_000_000.0 + (i as f64) * 300.0);
        opens.push(p - 0.1);
        highs.push(p + 0.5);
        lows.push(p - 0.5);
        closes.push(p + 0.2);
        vols.push(10_000.0 + ((i % 17) as f64) * 3_500.0);
    }

    let mut vc = SoAVolumeClock::with_capacity(1000);
    let t_vc = Instant::now();
    let mut metrics = vc.sample_and_analyze(&ts, &opens, &highs, &lows, &closes, &vols, 0.5);
    for _ in 0..999 {
        metrics = vc.sample_and_analyze(&ts, &opens, &highs, &lows, &closes, &vols, 0.5);
    }
    let vc_avg_ns = t_vc.elapsed().as_nanos() / 1000;

    println!(
        "{{\"status\":\"benchmark_complete\",\"forbid_unsafe\":true,\"soa_1000_positions_batch_ns\":{},\"soa_per_position_ns\":{:.2},\"volume_clock_1000_bars_ns\":{},\"vc_bars_generated\":{},\"vc_flow_velocity\":{:.4}}}",
        per_batch_ns,
        per_pos_ns,
        vc_avg_ns,
        metrics.num_bars,
        metrics.flow_velocity
    );
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut book = SoAPositionBook::with_capacity(128);
    let mut vc = SoAVolumeClock::with_capacity(1024);

    if args.len() > 1 {
        match args[1].as_str() {
            "--bench" => {
                run_benchmark();
                return;
            }
            "--eval-pos" => {
                let payload = args.get(2).map(|s| s.as_str()).unwrap_or("");
                println!("{}", handle_eval_positions(payload, &mut book));
                return;
            }
            "--eval-vc" => {
                let payload = args.get(2).map(|s| s.as_str()).unwrap_or("");
                println!("{}", handle_eval_volume_clock(payload, &mut vc));
                return;
            }
            "--pipe" => {
                let stdin = io::stdin();
                let mut stdout = io::stdout();
                for line in stdin.lock().lines() {
                    match line {
                        Ok(cmd) => {
                            let cmd = cmd.trim();
                            if cmd.is_empty() {
                                continue;
                            }
                            if cmd == "PING" {
                                let _ = writeln!(
                                    stdout,
                                    "{{\"status\":\"pong\",\"engine\":\"lumina-sentinel-rs\",\"forbid_unsafe\":true}}"
                                );
                                let _ = stdout.flush();
                            } else if cmd == "QUIT" || cmd == "EXIT" {
                                break;
                            } else if let Some(rest) = cmd.strip_prefix("EVAL_POS|") {
                                let resp = handle_eval_positions(rest, &mut book);
                                let _ = writeln!(stdout, "{}", resp);
                                let _ = stdout.flush();
                            } else if let Some(rest) = cmd.strip_prefix("EVAL_VC|") {
                                let resp = handle_eval_volume_clock(rest, &mut vc);
                                let _ = writeln!(stdout, "{}", resp);
                                let _ = stdout.flush();
                            } else {
                                let _ = writeln!(stdout, "{{\"status\":\"error\",\"msg\":\"unknown_command\"}}");
                                let _ = stdout.flush();
                            }
                        }
                        Err(_) => break,
                    }
                }
                return;
            }
            _ => {}
        }
    }

    run_benchmark();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_soa_position_rules_end_to_end() {
        let mut book = SoAPositionBook::with_capacity(16);
        // 0: Rule A (+26% full profit)
        book.push("NVDA".into(), 100.0, 126.0, 126.0, 87.0, 125.0, 0.0, 0, 0);
        // 1: Rule B (+11% half profit & breakeven lock)
        book.push("AAPL".into(), 100.0, 111.0, 111.0, 87.0, 125.0, 0.0, 0, 0);
        // 2: Rule B2 (Call Wall at 105.0, current at 104.8, PnL +4.8%)
        book.push("TSLA".into(), 100.0, 104.8, 104.8, 87.0, 125.0, 105.0, 0, 0);
        // 3: Rule C (Peak 108.0 (+8%), current 103.5 (-4.16% from peak))
        book.push("META".into(), 100.0, 103.5, 108.0, 87.0, 125.0, 0.0, 1, 0);
        // 4: Rule D (Half profit taken, price dropped back to entry 100.0)
        book.push("MSFT".into(), 100.0, 99.8, 110.5, 100.0, 125.0, 0.0, 1, 0);
        // 5: Rule E (-13.5% Fibonacci stop)
        book.push("AMZN".into(), 100.0, 86.5, 101.0, 87.0, 125.0, 0.0, 0, 0);
        // 6: DAY_CIS Wall Stop
        book.push("AMD".into(), 100.0, 98.9, 100.5, 99.0, 103.0, 0.0, 0, 1);

        book.evaluate_all();

        assert_eq!(book.out_actions[0], SentinelAction::RuleAFullProfit);
        assert_eq!(book.out_actions[1], SentinelAction::RuleBHalfProfit);
        assert!(book.out_new_stops[1] >= 100.0); // Breakeven locked
        assert_eq!(book.out_actions[2], SentinelAction::RuleB2CallWallHalf);
        assert_eq!(book.out_actions[3], SentinelAction::RuleCTrailingStop);
        assert_eq!(book.out_actions[4], SentinelAction::RuleDBreakevenStop);
        assert_eq!(book.out_actions[5], SentinelAction::RuleEFibStop);
        assert_eq!(book.out_actions[6], SentinelAction::DayCisWallStop);
    }

    #[test]
    fn test_soa_volume_clock_sampling() {
        let mut vc = SoAVolumeClock::with_capacity(64);
        let mut ts = Vec::new();
        let mut opens = Vec::new();
        let mut highs = Vec::new();
        let mut lows = Vec::new();
        let mut closes = Vec::new();
        let mut vols = Vec::new();

        for i in 0..50 {
            let p = 100.0 + (i as f64) * 0.2;
            ts.push(1_700_000_000.0 + (i as f64) * 60.0);
            opens.push(p - 0.05);
            highs.push(p + 0.15);
            lows.push(p - 0.15);
            closes.push(p + 0.10);
            // Burst of volume on the final bar to simulate institutional whale entry
            let v = if i == 49 { 50_000.0 } else { 5_000.0 };
            vols.push(v);
        }

        let m = vc.sample_and_analyze(&ts, &opens, &highs, &lows, &closes, &vols, 0.5);
        assert!(m.num_bars >= 5);
        assert!(m.is_bullish);
        assert!(m.flow_velocity > 1.5);
    }
}
