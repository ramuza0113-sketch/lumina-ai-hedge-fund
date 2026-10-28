import datetime
import time
import os
import json
from typing import Dict, Any, Optional
import pandas as pd
import yfinance as yf

class MarketDataFeed:
    """
    Lumina AI Hedge Fund: Real-Time & Historical Market Data Provider
    Integrates yfinance for Zero-Cost Japanese (TSE) and US (NASDAQ/NYSE) market data.
    Provides in-memory caching and fundamental analysis normalization.
    """
    
    _cache: Dict[str, Dict[str, Any]] = {}
    CACHE_TTL_SECONDS = 300  # 5 minutes
    _quote_cache: Dict[str, Dict[str, Any]] = {}
    QUOTE_CACHE_TTL = 15  # 15 seconds fast quote cache
    _history_cache: Dict[str, Dict[str, Any]] = {}
    HISTORY_CACHE_TTL = 900  # 15 minutes cache for sparklines
    _dividend_cache: Dict[str, Any] = {}
    DIVIDEND_CACHE_TTL = 21600.0  # 6 hours cache for ex-dividend checks
    _split_cache: Dict[str, Any] = {}
    SPLIT_CACHE_TTL = 21600.0  # 6 hours cache for stock split / reverse split checks

    @classmethod
    def get_historical_closes(cls, symbol: str, period: str = "1mo") -> list:
        """
        Fetch clean daily close prices for sparklines and mini price charts.
        Returns a list of float prices (oldest to newest).
        """
        norm_sym = cls.normalize_symbol(symbol)
        cache_key = f"{norm_sym}_{period}"
        now = time.time()
        
        if cache_key in cls._history_cache:
            entry = cls._history_cache[cache_key]
            if now - entry["cached_at"] < cls.HISTORY_CACHE_TTL:
                return entry["data"]
        
        try:
            ticker = yf.Ticker(norm_sym)
            hist = ticker.history(period=period)
            if hist is not None and not hist.empty:
                closes = [float(x) for x in hist["Close"].dropna().tolist()]
                cls._history_cache[cache_key] = {"cached_at": now, "data": closes}
                return closes
        except Exception as e:
            print(f"[MarketDataFeed] get_historical_closes error for {norm_sym}: {e}")
            
        return []

    @staticmethod
    def render_sparkline_svg(
        prices: list, 
        width: int = 160, 
        height: int = 42, 
        label: str = "30日推移",
        currency: str = ""
    ) -> str:
        """
        Generate an ultra-lightweight, high-fidelity SVG sparkline for stock price trends.
        Zero external dependencies, renders in 0ms with hardware-accelerated SVG.
        """
        if not prices or len(prices) < 2:
            return f"""
            <div style="background: rgba(15, 23, 42, 0.4); border: 1px dashed rgba(100, 116, 139, 0.3); border-radius: 8px; height: {height}px; display: flex; align-items: center; justify-content: center; width: 100%;">
                <span style="font-size: 10px; color: #64748b; font-family: sans-serif;">チャート取得中...</span>
            </div>
            """
        
        min_p = min(prices)
        max_p = max(prices)
        p_range = max_p - min_p if max_p != min_p else 1.0
        
        padding_top = 13
        padding_bottom = 4
        plot_h = height - padding_top - padding_bottom
        step_x = (width - 12) / (len(prices) - 1)
        
        points = []
        for i, p in enumerate(prices):
            x = 6 + i * step_x
            y = padding_top + plot_h - ((p - min_p) / p_range * plot_h)
            points.append((x, y))
        
        path_d = f"M {points[0][0]:.1f} {points[0][1]:.1f} "
        for x, y in points[1:]:
            path_d += f"L {x:.1f} {y:.1f} "
            
        area_d = path_d + f"L {points[-1][0]:.1f} {height} L {points[0][0]:.1f} {height} Z"
        
        is_up = prices[-1] >= prices[0]
        stroke_color = "#34d399" if is_up else "#f87171"
        fill_color_start = "rgba(52, 211, 153, 0.28)" if is_up else "rgba(248, 113, 113, 0.28)"
        fill_color_end = "rgba(52, 211, 153, 0.0)" if is_up else "rgba(248, 113, 113, 0.0)"
        
        grad_id = f"spark_{abs(hash(tuple(round(p, 1) for p in prices[:4])))}"
        
        pct_chg = ((prices[-1] - prices[0]) / prices[0]) * 100.0 if prices[0] > 0 else 0.0
        pct_str = f"{pct_chg:+.1f}%"
        
        last_x, last_y = points[-1]
        
        svg = f"""
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.18); border-radius: 8px; padding: 4px 6px; width: 100%; box-sizing: border-box;">
            <svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="overflow: visible; display: block;">
                <defs>
                    <linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="{fill_color_start}" />
                        <stop offset="100%" stop-color="{fill_color_end}" />
                    </linearGradient>
                </defs>
                <path d="{area_d}" fill="url(#{grad_id})" />
                <path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.2" fill="{stroke_color}" />
                <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5.5" fill="none" stroke="{stroke_color}" stroke-width="0.8" opacity="0.5" />
                <text x="4" y="10" fill="#94a3b8" font-size="8.5" font-weight="600" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto">{label}</text>
                <text x="{width - 4}" y="10" fill="{stroke_color}" font-size="9" font-weight="700" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto">{pct_str}</text>
            </svg>
        </div>
        """
        return svg

    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """
        Normalize user input ticker symbols.
        - Japanese 4-digit code (e.g. 7203) -> 7203.T
        - US tickers (e.g. nvda, aapl) -> NVDA, AAPL
        """
        s = symbol.strip().upper()
        if s.isdigit() and len(s) == 4:
            return f"{s}.T"
        if s.endswith(".T") or s.endswith(".TO"):
            return s
        return s

    @classmethod
    def get_earnings_calendar(cls, symbol: str) -> Dict[str, Any]:
        """
        Fetch next earnings announcement date from yfinance and calculate days remaining.
        Flags 'is_near_earnings' if scheduled within 3 days (earnings gamble avoidance).
        """
        norm_sym = cls.normalize_symbol(symbol)
        try:
            ticker = yf.Ticker(norm_sym)
            cal = ticker.calendar
            if cal and isinstance(cal, dict) and "Earnings Date" in cal:
                raw_dates = cal["Earnings Date"]
                if isinstance(raw_dates, list) and raw_dates:
                    target_d = raw_dates[0]
                    if isinstance(target_d, (datetime.date, datetime.datetime)):
                        target_date = target_d if isinstance(target_d, datetime.date) else target_d.date()
                        today = datetime.date.today()
                        days_rem = (target_date - today).days
                        is_near = (0 <= days_rem <= 3)
                        return {
                            "earnings_date": target_date.strftime("%Y-%m-%d"),
                            "days_remaining": days_rem,
                            "is_near_earnings": is_near,
                            "status": "NEAR_EARNINGS_RISK" if is_near else "OK"
                        }
        except Exception as e:
            pass

        return {
            "earnings_date": None,
            "days_remaining": None,
            "is_near_earnings": False,
            "status": "UNKNOWN"
        }

    @classmethod
    def get_recent_ex_dividend_adjustment(cls, symbol: str, days_window: int = 14) -> float:
        """
        Check if the stock has gone ex-dividend within the last `days_window` days.
        Returns the dividend amount per share to adjust stop-loss calculation and prevent
        artificial stop-loss triggers caused by theoretical price drop on ex-dividend day.
        """
        norm_sym = cls.normalize_symbol(symbol)
        now = time.time()
        if norm_sym in cls._dividend_cache:
            c_time, c_val = cls._dividend_cache[norm_sym]
            if now - c_time < cls.DIVIDEND_CACHE_TTL:
                return c_val

        try:
            ticker = yf.Ticker(norm_sym)
            divs = ticker.dividends
            if divs is not None and not divs.empty:
                cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=days_window)
                recent_divs = divs[divs.index >= cutoff]
                if not recent_divs.empty:
                    div_amt = float(recent_divs.iloc[-1])
                    cls._dividend_cache[norm_sym] = (now, div_amt)
                    return div_amt
        except Exception:
            pass

        cls._dividend_cache[norm_sym] = (now, 0.0)
        return 0.0

    @classmethod
    def get_recent_stock_split_ratio(cls, symbol: str, days_window: int = 14) -> float:
        """
        Check if the stock has undergone a stock split or reverse split within `days_window` days.
        Returns the split ratio (e.g. 5.0 for a 5-for-1 split, 0.1 for a 1-for-10 reverse split, or 1.0 if none).
        """
        norm_sym = cls.normalize_symbol(symbol)
        now = time.time()
        if norm_sym in cls._split_cache:
            c_time, c_val = cls._split_cache[norm_sym]
            if now - c_time < cls.SPLIT_CACHE_TTL:
                return float(c_val)

        try:
            ticker = yf.Ticker(norm_sym)
            splits = ticker.splits
            if splits is not None and not splits.empty:
                cutoff = pd.Timestamp.now(tz=splits.index.tz) - pd.Timedelta(days=days_window)
                recent_splits = splits[splits.index >= cutoff]
                if not recent_splits.empty:
                    ratio = float(recent_splits.iloc[-1])
                    if ratio > 0.0 and abs(ratio - 1.0) > 1e-4:
                        cls._split_cache[norm_sym] = (now, ratio)
                        return ratio
        except Exception:
            pass

        cls._split_cache[norm_sym] = (now, 1.0)
        return 1.0

    @classmethod
    def get_realtime_quote(cls, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Ultra-fast real-time price & PnL quote lookup using yfinance fast_info.
        Optimized with 15s in-memory cache to ensure instant (0ms) response on re-renders.
        """
        norm_sym = cls.normalize_symbol(symbol)
        now = time.time()
        
        # Check in-memory fast quote cache
        if not force_refresh and norm_sym in cls._quote_cache:
            entry = cls._quote_cache[norm_sym]
            if now - entry["cached_at"] < cls.QUOTE_CACHE_TTL:
                return entry["data"]

        res = None
        try:
            ticker = yf.Ticker(norm_sym)
            fi = ticker.fast_info
            last_price = float(getattr(fi, "last_price", None) or fi.get("lastPrice") or 0.0)
            prev_close = float(getattr(fi, "previous_close", None) or fi.get("previousClose") or last_price)
            curr = getattr(fi, "currency", None) or fi.get("currency") or ("JPY" if norm_sym.endswith(".T") else "USD")
            change = last_price - prev_close
            change_pct = (change / prev_close * 100.0) if prev_close > 0 else 0.0
            res = {
                "symbol": norm_sym,
                "current_price": round(last_price, 2) if curr == "USD" else round(last_price, 1),
                "previous_close": prev_close,
                "change": round(change, 2) if curr == "USD" else round(change, 1),
                "change_pct": round(change_pct, 2),
                "currency": curr,
                "timestamp": now
            }
        except Exception:
            sd = cls.get_stock_data(norm_sym)
            cp = sd.get("current_price", 0.0)
            res = {
                "symbol": norm_sym,
                "current_price": cp,
                "previous_close": cp,
                "change": 0.0,
                "change_pct": 0.0,
                "currency": sd.get("currency", "JPY" if norm_sym.endswith(".T") else "USD"),
                "timestamp": now
            }
        
        cls._quote_cache[norm_sym] = {"cached_at": now, "data": res}
        return res

    @classmethod
    def get_stock_data(cls, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch comprehensive real-time quotes, technical stats, and fundamentals.
        """
        norm_sym = cls.normalize_symbol(symbol)
        now = time.time()
        
        # Check cache
        if not force_refresh and norm_sym in cls._cache:
            entry = cls._cache[norm_sym]
            if now - entry["cached_at"] < cls.CACHE_TTL_SECONDS:
                return entry["data"]

        ticker = yf.Ticker(norm_sym)
        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        # Historical data for technical indicators
        try:
            hist = ticker.history(period="1y")
        except Exception:
            hist = None

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current_price and hist is not None and not hist.empty:
            current_price = float(hist["Close"].iloc[-1])

        currency = info.get("currency", "JPY" if norm_sym.endswith(".T") else "USD")
        company_name = info.get("longName") or info.get("shortName") or norm_sym

        # Technical calculations
        hist_metrics = {}
        if hist is not None and not hist.empty and len(hist) > 20:
            closes = hist["Close"]
            current = float(closes.iloc[-1])
            prev_20 = float(closes.iloc[-20])
            hist_metrics["return_20d_pct"] = round(((current - prev_20) / prev_20) * 100, 2)
            hist_metrics["sma_20"] = round(float(closes.tail(20).mean()), 2)
            if len(closes) >= 50:
                hist_metrics["sma_50"] = round(float(closes.tail(50).mean()), 2)
            if len(closes) >= 200:
                hist_metrics["sma_200"] = round(float(closes.tail(200).mean()), 2)
            # Volatility (Annualized)
            daily_returns = closes.pct_change().dropna()
            if not daily_returns.empty:
                hist_metrics["volatility_annualized_pct"] = round(float(daily_returns.std() * (252 ** 0.5) * 100), 2)
        else:
            hist_metrics["return_20d_pct"] = 0.0

        # 14-day ATR (Average True Range) Volatility Calculation
        atr_14 = None
        atr_pct = None
        dynamic_stop_pct = 13.0
        dynamic_stop_loss_price = round(current_price * 0.87, 2 if currency == "USD" else 1) if current_price else None

        if hist is not None and not hist.empty and len(hist) >= 15:
            try:
                highs = hist["High"]
                lows = hist["Low"]
                closes = hist["Close"]
                prev_closes = closes.shift(1)
                tr1 = highs - lows
                tr2 = (highs - prev_closes).abs()
                tr3 = (lows - prev_closes).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr_series = tr.rolling(window=14).mean()
                latest_atr = float(atr_series.iloc[-1])
                if current_price and current_price > 0 and latest_atr > 0:
                    atr_14 = round(latest_atr, 2 if currency == "USD" else 1)
                    atr_pct = round((latest_atr / current_price) * 100.0, 2)
                    # Clamped between 4.0% (defensive low-vol cut) and 15.0% (high-vol max ceiling)
                    dynamic_stop_pct = round(max(4.0, min(15.0, atr_pct * 2.5)), 1)
                    dynamic_stop_loss_price = round(current_price * (1.0 - dynamic_stop_pct / 100.0), 2 if currency == "USD" else 1)
            except Exception:
                pass

        hist_metrics["atr_14"] = atr_14
        hist_metrics["atr_pct"] = atr_pct
        hist_metrics["dynamic_stop_pct"] = dynamic_stop_pct
        hist_metrics["dynamic_stop_loss_price"] = dynamic_stop_loss_price

        # Graham Number calculation: sqrt(22.5 * EPS * BPS)
        eps = info.get("trailingEps") or info.get("forwardEps")
        bps = info.get("bookValue")
        graham_number = None
        if eps and bps and eps > 0 and bps > 0:
            graham_number = round((22.5 * eps * bps) ** 0.5, 2)

        data = {
            "symbol": norm_sym,
            "company_name": company_name,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "currency": currency,
            "current_price": current_price,
            "previous_close": info.get("previousClose"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "market_cap": info.get("marketCap"),
            
            # Valuation Metrics (Graham & Buffett Focus)
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "peg_ratio": info.get("pegRatio"),
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else 0.0,
            "graham_number": graham_number,
            "eps": eps,
            "bps": bps,
            
            # Profitability & Moat Metrics (Buffett Focus)
            "roe": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
            "roa": round(info.get("returnOnAssets", 0) * 100, 2) if info.get("returnOnAssets") else None,
            "operating_margin": round(info.get("operatingMargins", 0) * 100, 2) if info.get("operatingMargins") else None,
            "profit_margin": round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None,
            
            # Financial Health & Debt
            "total_debt": info.get("totalDebt"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            "current_ratio": info.get("currentRatio"),
            
            # Growth & Innovation (Cathie Wood Focus)
            "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None,
            "earnings_growth": round(info.get("earningsGrowth", 0) * 100, 2) if info.get("earningsGrowth") else None,
            
            # Technical & Volatility Metrics
            "atr_14": atr_14,
            "atr_pct": atr_pct,
            "dynamic_stop_pct": dynamic_stop_pct,
            "dynamic_stop_loss_price": dynamic_stop_loss_price,
            "history_metrics": hist_metrics,
            "business_summary": info.get("longBusinessSummary", ""),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        }

        # Cache result
        cls._cache[norm_sym] = {
            "cached_at": now,
            "data": data
        }
        return data

    @classmethod
    def format_for_council_prompt(cls, data: Dict[str, Any]) -> str:
        """
        Format fundamental and technical metrics into a structured dossier for AI debate agents.
        """
        sym = data.get("symbol", "")
        name = data.get("company_name", "")
        curr = data.get("currency", "")
        price = data.get("current_price", "N/A")
        
        def _f(val, suffix=""):
            if val is None or val == "N/A":
                return "N/A"
            if isinstance(val, (int, float)):
                return f"{val:,.2f}{suffix}"
            return f"{val}{suffix}"

        def _fmt_big(num):
            if not num or not isinstance(num, (int, float)):
                return "N/A"
            if num >= 1e12:
                return f"{num/1e12:.2f} 兆"
            if num >= 1e8:
                return f"{num/1e8:.2f} 億"
            return f"{num:,.0f}"

        hist_m = data.get("history_metrics", {})
        summary = data.get("business_summary", "")[:500]

        dossier = f"""### 【企業基本情報・最新株価データ】
- 銘柄コード: {sym} ({name})
- セクター / 業種: {data.get('sector')} / {data.get('industry')}
- 現在値: {_f(price)} {curr} (直近20日リターン: {hist_m.get('return_20d_pct', 'N/A')}%)
- 52週高値/安値: {_f(data.get('fifty_two_week_high'))} / {_f(data.get('fifty_two_week_low'))} {curr}
- 時価総額: {_fmt_big(data.get('market_cap'))} {curr}
- 次回決算発表予定: {data.get('earnings_calendar', {}).get('earnings_date') or '未公表'} ({'⚠️ 直近3日以内・決算跨ぎ暴落リスクあり！' if data.get('earnings_calendar', {}).get('is_near_earnings') else f"残り{data.get('earnings_calendar', {}).get('days_remaining')}日" if data.get('earnings_calendar', {}).get('days_remaining') is not None else '安全'})

### 【財務・バリュエーション指標 (グレアム＆バフェット判定用)】
- 実績PER / 予想PER: {_f(data.get('pe_trailing'))}倍 / {_f(data.get('pe_forward'))}倍
- PBR (純資産倍率): {_f(data.get('pb_ratio'))}倍
- グレアム数 (理論安全域株価): {_f(data.get('graham_number'))} {curr}
- 配当利回り: {_f(data.get('dividend_yield'), '%')}
- ROE (自己資本利益率): {_f(data.get('roe'), '%')}
- 営業利益率 / 純利益率: {_f(data.get('operating_margin'), '%')} / {_f(data.get('profit_margin'), '%')}
- 有利子負債比率 (D/E比率): {_f(data.get('debt_to_equity'))}%
- 流動比率: {_f(data.get('current_ratio'))}
- フリーキャッシュフロー (FCF): {_fmt_big(data.get('free_cashflow'))} {curr}

### 【成長性・イノベーション指標 (キャシー・ウッド判定用)】
- 売上高成長率 (YoY): {_f(data.get('revenue_growth'), '%')}
- 利益成長率 (YoY): {_f(data.get('earnings_growth'), '%')}
- 年率ボラティリティ: {hist_m.get('volatility_annualized_pct', 'N/A')}%

### 【テクニカル＆ボラティリティ指標 (リスク管理判定用)】
- 200日移動平均線 (SMA200): {_f(hist_m.get('sma_200'))} {curr} ({'🟢 ステージ2強気トレンド (株価 >= 200SMA)' if price and hist_m.get('sma_200') and price >= (hist_m.get('sma_200') * 0.98) else '🔴 下降トレンド (株価 < 200SMA / 買付非推奨)'})
- 14日ATR (真の価格変動幅): {_f(data.get('atr_14'))} {curr} ({_f(data.get('atr_pct'), '%')})
- 推奨ATR動的損切りライン: -{_f(data.get('dynamic_stop_pct'), '%')} ({_f(data.get('dynamic_stop_loss_price'))} {curr}) [低ボラ株は-4〜-5%で早期撤退、高ボラ株はノイズ回避-10〜-13%]

### 【事業概要 (抜粋)】
{summary}...
"""
        return dossier
