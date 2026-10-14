# -*- coding: utf-8 -*-
"""
Lumina Capital - TradingView Interactive Candlestick Chart Engine (v4.2.0)
Embeds high-performance TradingView Lightweight Charts in Streamlit.
"""

import sys
import os
import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
import streamlit as st

logger = logging.getLogger(__name__)

class ChartEngine:
    @staticmethod
    def prepare_ohlcv_data(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """
        Fetch and format OHLCV data from Yahoo Finance for TradingView Lightweight Charts.
        """
        try:
            import yfinance as yf
            ticker_str = f"{symbol}.T" if (symbol.isdigit() and len(symbol) == 4) else symbol
            tk = yf.Ticker(ticker_str)
            df = tk.history(period=period)
            if df is None or df.empty or len(df) < 5:
                return None
            
            df = df.reset_index()
            if "Date" in df.columns:
                date_col = "Date"
            elif "Datetime" in df.columns:
                date_col = "Datetime"
            else:
                date_col = df.columns[0]
            
            df["date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            
            df = df.sort_values("date").reset_index(drop=True)
            return df[["date", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.warning(f"Failed to fetch OHLCV for {symbol}: {e}")
            return None

    @classmethod
    def render_tradingview_chart(
        cls,
        symbol: str,
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        entry_price: Optional[float] = None,
        height: int = 420,
        period: str = "6mo",
        ohlcv_df: Optional[pd.DataFrame] = None
    ):
        """
        Render TradingView lightweight candlestick chart inside Streamlit.
        """
        df = ohlcv_df if ohlcv_df is not None else cls.prepare_ohlcv_data(symbol, period=period)
        if df is None or df.empty:
            st.warning(f"⚠️ `{symbol}` の株価チャートデータを取得できませんでした。")
            return

        try:
            from lightweight_charts.widgets import StreamlitChart
            
            chart = StreamlitChart(height=height, autosize=True)
            
            # Styling: Professional Dark Executive Theme
            chart.layout(
                background_color='#0f172a',
                text_color='#94a3b8',
                font_size=11,
                font_family='Segoe UI, Meiryo, sans-serif'
            )
            chart.candle_style(
                up_color='#22c55e',
                down_color='#ef4444',
                border_up_color='#22c55e',
                border_down_color='#ef4444',
                wick_up_color='#22c55e',
                wick_down_color='#ef4444'
            )
            chart.volume_config(
                up_color='rgba(34, 197, 94, 0.35)',
                down_color='rgba(239, 68, 68, 0.35)'
            )
            chart.grid(
                vert_enabled=True,
                horz_enabled=True,
                color='rgba(255, 255, 255, 0.05)'
            )
            
            chart.set(df)

            # Technical Indicators: Moving Averages
            if len(df) >= 20:
                sma20 = df["close"].rolling(20).mean()
                sma20_df = pd.DataFrame({"date": df["date"], "SMA 20": sma20}).dropna()
                line20 = chart.create_line(name="SMA 20", color="rgba(251, 191, 36, 0.8)", width=1, price_line=False)
                line20.set(sma20_df)

            if len(df) >= 50:
                sma50 = df["close"].rolling(50).mean()
                sma50_df = pd.DataFrame({"date": df["date"], "SMA 50": sma50}).dropna()
                line50 = chart.create_line(name="SMA 50", color="rgba(56, 189, 248, 0.8)", width=1, price_line=False)
                line50.set(sma50_df)

            if len(df) >= 150:
                sma200 = df["close"].rolling(min(200, len(df))).mean()
                sma200_df = pd.DataFrame({"date": df["date"], "SMA 200": sma200}).dropna()
                line200 = chart.create_line(name="SMA 200", color="rgba(168, 85, 247, 0.85)", width=2, price_line=False)
                line200.set(sma200_df)

            # Price Markers
            if entry_price and entry_price > 0:
                chart.horizontal_line(
                    price=float(entry_price),
                    color="rgba(56, 189, 248, 0.9)",
                    width=2,
                    style="dotted",
                    text=f"買付値 ({entry_price:,.1f})"
                )

            if target_price and target_price > 0:
                chart.horizontal_line(
                    price=float(target_price),
                    color="rgba(16, 185, 129, 0.95)",
                    width=2,
                    style="dashed",
                    text=f"目標利確 (+25%: {target_price:,.1f})"
                )

            if stop_loss_price and stop_loss_price > 0:
                chart.horizontal_line(
                    price=float(stop_loss_price),
                    color="rgba(239, 68, 68, 0.95)",
                    width=2,
                    style="dashed",
                    text=f"損切りライン (-13%: {stop_loss_price:,.1f})"
                )

            chart.load()

        except Exception as e:
            logger.warning(f"TradingView chart failed, rendering Plotly fallback: {e}")
            cls._render_plotly_fallback(df, symbol, target_price, stop_loss_price, entry_price)

    @classmethod
    def _render_plotly_fallback(
        cls,
        df: pd.DataFrame,
        symbol: str,
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        entry_price: Optional[float] = None
    ):
        """Fallback to Plotly Candlestick chart if lightweight_charts is unavailable."""
        try:
            import plotly.graph_objects as go
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df['date'],
                    open=df['open'], high=df['high'],
                    low=df['low'], close=df['close'],
                    increasing_line_color='#22c55e',
                    decreasing_line_color='#ef4444',
                    name=symbol
                )
            ])
            if target_price:
                fig.add_hline(y=target_price, line_dash="dash", line_color="#10b981", annotation_text="目標利確 (+25%)")
            if stop_loss_price:
                fig.add_hline(y=stop_loss_price, line_dash="dash", line_color="#ef4444", annotation_text="損切りライン (-13%)")
            if entry_price:
                fig.add_hline(y=entry_price, line_dash="dot", line_color="#38bdf8", annotation_text="買付単価")
            
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#0f172a",
                margin=dict(l=10, r=10, t=30, b=10),
                height=400,
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as ex:
            st.line_chart(df.set_index("date")["close"], use_container_width=True)
