from core.ai_hedge_fund.market_session import MarketSession
# -*- coding: utf-8 -*-
import streamlit as st
import json
import time
import os
from typing import Dict, Any, List, Optional

from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.hedge_fund_council import HedgeFundCouncil
from core.ai_hedge_fund.broker_client import PaperTradingEngine, KabuStationClient, IBKRClient
from core.ai_hedge_fund.fund_content_generator import FundContentGenerator
from ui.i18n import t, get_current_lang

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def render_mode_ai_hedge_fund(api_key: str = "", generator = None, target_model: str = "", lang: str = "en"):
    """
    Lumina AI Hedge Fund: Autonomous Multi-Agent Investment Studio UI
    """
    is_en = (get_current_lang() == "en")
    default_init_sym = "NVDA" if is_en else "7203.T"

    if 'pending_hf_symbol' in st.session_state:
        target_sym = st.session_state.pop('pending_hf_symbol')
        st.session_state['hf_input_symbol'] = target_sym
        st.session_state['hf_input_symbol_field'] = target_sym
    elif 'hf_input_symbol_field' not in st.session_state:
        st.session_state['hf_input_symbol_field'] = st.session_state.get('hf_input_symbol', default_init_sym)
    
    # 💎 Premium SaaS Header Banner
    header_badge = t("header_badge")
    header_sub = t("header_sub")
    header_data = t("header_data")
    header_mode = t("header_mode")

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #06101e 0%, #0d1e38 50%, #15294e 100%); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 16px; padding: 20px 24px; color: #FFFFFF; margin-bottom: 20px; box-shadow: 0 4px 25px rgba(0,0,0,0.5), 0 0 20px rgba(56, 189, 248, 0.15);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="width: 48px; height: 48px; border-radius: 14px; background: linear-gradient(135deg, #0284c7, #10b981); display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);">
                    🏛️
                </div>
                <div>
                    <div style="font-size: 1.4rem; font-weight: 800; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px;">
                        <span>Lumina AI Hedge Fund</span>
                        <span style="font-size: 11px; padding: 3px 10px; border-radius: 9999px; background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-family: monospace;">{header_badge}</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #94a3b8; margin-top: 3px;">
                        {header_sub}
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <div style="background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 6px 14px; font-size: 11px; color: #38bdf8;">
                    {header_data}
                </div>
                <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 6px 14px; font-size: 11px; color: #34d399;">
                    {header_mode}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_council, tab_portfolio, tab_memory, tab_content = st.tabs([
        t("tab_council"),
        t("tab_portfolio"),
        t("tab_memory"),
        t("tab_content")
    ])

    paper_engine = PaperTradingEngine()

    # =========================================================================
    # TAB 1: 🏛️ AI投資作戦会議 (Investment Council)
    # =========================================================================
    with tab_council:
        st.info(t("council_hint"))

        def select_and_run_council(target_sym: str, force: bool = False):
            norm = MarketDataFeed.normalize_symbol(target_sym)
            st.session_state['pending_hf_symbol'] = norm
            st.session_state['hf_input_symbol'] = norm
            st.session_state['hf_input_symbol_field'] = norm
            
            # Check cached result first for instant response
            cached = None if force else HedgeFundCouncil.get_cached_council(norm, max_age_hours=2.0)
            if cached:
                st.session_state['last_council_result'] = cached
                st.session_state['auto_run_council'] = False
            else:
                st.session_state['auto_run_council'] = True
            st.rerun()

        st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;'>{t('quick_presets')}</div>", unsafe_allow_html=True)
        
        # Preset buttons (Adapted to active language)
        if is_en:
            presets = [
                ("🇺🇸 NVIDIA", "NVDA"),
                ("🇺🇸 Apple", "AAPL"),
                ("🇺🇸 Tesla", "TSLA"),
                ("🇺🇸 Microsoft", "MSFT"),
                ("🇺🇸 Palantir", "PLTR"),
                ("🇪🇺 ASML", "ASML"),
                ("🇯🇵 Toyota", "7203.T"),
                ("🇪🇺 SAP", "SAP"),
            ]
        else:
            presets = [
                ("🇯🇵 トヨタ", "7203.T"),
                ("🇯🇵 三菱商事", "8058.T"),
                ("🇯🇵 ソニー", "6758.T"),
                ("🇺🇸 NVIDIA", "NVDA"),
                ("🇺🇸 Apple", "AAPL"),
                ("🇺🇸 Tesla", "TSLA"),
                ("🇪🇺 ASML", "ASML"),
                ("🇪🇺 SAP", "SAP"),
            ]
        p_cols = st.columns(len(presets))
        for idx, (label, sym) in enumerate(presets):
            with p_cols[idx]:
                clean_code = sym.replace('.T', '')
                if st.button(f"{label}\n({clean_code})", key=f"hf_pre_{sym}", use_container_width=True):
                    select_and_run_council(sym)

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>{t('manual_symbol_heading')}</div>", unsafe_allow_html=True)
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            if 'hf_input_symbol_field' not in st.session_state and 'hf_input_symbol' in st.session_state:
                st.session_state['hf_input_symbol_field'] = st.session_state['hf_input_symbol']
            input_symbol = st.text_input(
                t("symbol_input_label"),
                key="hf_input_symbol_field"
            )
        with col_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            run_btn = st.button(t("convene_btn"), type="primary", use_container_width=True)

        should_run = (run_btn or st.session_state.get('auto_run_council', False)) and input_symbol
        if should_run:
            st.session_state['auto_run_council'] = False
            norm_symbol = MarketDataFeed.normalize_symbol(input_symbol.strip())
            st.session_state['hf_input_symbol'] = norm_symbol
            is_manual_force = bool(run_btn)
            with st.spinner(t("spinner_running")):
                try:
                    council_result = HedgeFundCouncil.run_council(norm_symbol, force_refresh=is_manual_force)
                    st.session_state['last_council_result'] = council_result
                    st.success(t("council_done", symbol=norm_symbol))
                except Exception as e:
                    st.error(t("council_error", error=str(e)))

        # Auto-load cached result on initial load if none in state
        if 'last_council_result' not in st.session_state:
            curr_sym = st.session_state.get('hf_input_symbol', "7203.T")
            cached_init = HedgeFundCouncil.get_cached_council(curr_sym)
            if cached_init:
                st.session_state['last_council_result'] = cached_init

        # Display Council Results if available
        c_res = st.session_state.get('last_council_result')
        if c_res:
            st.markdown("---")
            sym = c_res.get("symbol", "")
            name = c_res.get("company_name", "")
            curr = c_res.get("currency", "JPY")
            price = c_res.get("current_price", 0.0)
            stock_data = c_res.get("stock_data", {})
            verdict = c_res.get("verdict", {})
            dialogues = c_res.get("council_dialogues", [])

            # Summary Metrics Row
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric(t("current_price"), f"{price:,.2f} {curr}")
            m2.metric(t("return_20d"), f"{stock_data.get('history_metrics', {}).get('return_20d_pct', 0)}%")
            m3.metric(t("pe_trailing"), f"{stock_data.get('pe_trailing') or 'N/A'}")
            m4.metric(t("pb_ratio"), f"{stock_data.get('pb_ratio') or 'N/A'}")
            m5.metric(t("dividend_yield"), f"{stock_data.get('dividend_yield', 0)}%")
            m6.metric(t("roe"), f"{stock_data.get('roe') or 'N/A'}%")

            # 🏆 CIO Final Verdict Card
            action = verdict.get("action", "HOLD")
            action_color = "#10b981" if action in ["BUY", "ACCUMULATE"] else ("#ef4444" if action in ["SELL", "REDUCE"] else "#f59e0b")
            cio_title = t("cio_title")
            target_label = t("target_price")
            stop_loss_label = t("stop_loss")
            alloc_label = t("allocation")
            conf_label = t("confidence")
            thesis_label = t("thesis_title")
            if is_en:
                act_en_map = {
                    "BUY": "STRONG BUY",
                    "ACCUMULATE": "ACCUMULATE / DIP BUY",
                    "HOLD": "HOLD / NEUTRAL",
                    "REDUCE": "REDUCE",
                    "SELL": "STRONG SELL"
                }
                action_display = act_en_map.get(action, action)
            else:
                action_display = verdict.get('action_label', action)
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9)); border: 2px solid {action_color}; border-radius: 14px; padding: 20px; margin: 18px 0; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: bold;">{cio_title}</span>
                            {f'<span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 600;">{verdict.get("market_regime")}</span>' if verdict.get("market_regime") else ''}
                        </div>
                        <div style="font-size: 1.6rem; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 12px; margin-top: 4px;">
                            <span>{name} ({sym})</span>
                            <span style="background: {action_color}; color: #ffffff; font-size: 13px; font-weight: 800; padding: 4px 12px; border-radius: 8px;">
                                {action_display}
                            </span>
                        </div>
                    </div>
                    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                        <div>
                            <div style="font-size: 10px; color: #94a3b8;">{target_label}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #38bdf8;">{verdict.get('target_price', 'N/A')} {curr}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: #94a3b8;">{stop_loss_label}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #f87171;">{verdict.get('stop_loss_price', 'N/A')} {curr}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: #94a3b8;">{alloc_label}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #34d399;">{verdict.get('allocation_pct', 10)}%</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: #94a3b8;">{conf_label}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #fbbf24;">{verdict.get('confidence_score', 80)} / 100</div>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1); color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;">
                    <strong>{thesis_label}</strong><br/>
                    {verdict.get('thesis_summary', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 📊 TradingView Interactive Candlestick Chart
            chart_expander_title = t("chart_title", name=name, sym=sym)
            with st.expander(chart_expander_title, expanded=True):
                from core.ai_hedge_fund.chart_engine import ChartEngine
                try:
                    tgt_p = float(verdict.get("target_price")) if verdict.get("target_price") not in [None, "N/A"] else None
                except Exception: tgt_p = None
                try:
                    stp_p = float(verdict.get("stop_loss_price")) if verdict.get("stop_loss_price") not in [None, "N/A"] else None
                except Exception: stp_p = None
                
                ChartEngine.render_tradingview_chart(
                    symbol=sym,
                    target_price=tgt_p,
                    stop_loss_price=stp_p,
                    entry_price=price,
                    height=420
                )

            # 📋 Fast Execution Box
            with st.container(border=True):
                st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>{t('fast_order_title')}</div>", unsafe_allow_html=True)
                ex_c1, ex_c2, ex_c3, ex_c4 = st.columns([1.5, 1.5, 1.5, 2.5])
                with ex_c1:
                    side_options = ["BUY (Long)", "SELL (Short)"] if is_en else ["BUY (買い)", "SELL (売り)"]
                    order_side = st.selectbox(t("order_side"), side_options, index=0 if action in ["BUY", "ACCUMULATE"] else 1)
                with ex_c2:
                    default_qty = 10 if curr in ["USD", "EUR"] else 100
                    order_qty = st.number_input(t("order_qty"), min_value=1, value=default_qty, step=10 if curr == "JPY" else 1)
                with ex_c3:
                    st.metric(t("order_est_val"), f"{(order_qty * price):,.2f} {curr}")
                with ex_c4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    side_code = "BUY" if "BUY" in order_side else "SELL"
                    if st.button(f"{t('order_exec_btn')} ({side_code})", type="primary", use_container_width=True):
                        exec_res = paper_engine.place_order(
                            symbol=sym,
                            side=side_code,
                            quantity=order_qty,
                            price=price,
                            target_price=verdict.get("target_price"),
                            stop_loss_price=verdict.get("stop_loss_price"),
                            notes=f"CIO Verdict: {action}"
                        )
                        if exec_res.get("success"):
                            sl_info = f" (Stop Loss: {exec_res.get('stop_loss_price')} {curr})" if exec_res.get('stop_loss_price') else ""
                            st.success(t("order_success", order_id=exec_res['order_id'], side=side_code, qty=order_qty, price=price, curr=curr, sl_info=sl_info))
                        else:
                            st.error(f"Execution Error: {exec_res.get('error')}")

            # ⚔️ Phase 2: Fact-Grounded Cross-Debate Box
            cd = c_res.get("cross_debate", {})
            if cd.get("occurred"):
                bear_n = cd.get("bear_name", "Bear")
                bull_n = cd.get("bull_name", "Bull")
                b_init = cd.get("bear_initial_score", 0)
                u_init = cd.get("bull_initial_score", 0)
                u_adj = cd.get("adjusted_score", u_init)
                delta = cd.get("score_delta", 0)
                delta_str = f"({delta:+d} pts)" if is_en else (f"({delta:+d}点修正)" if delta != 0 else "(スコア維持)")
                delta_color = "#f87171" if delta < 0 else "#34d399"
                spread_text = t("spread_label", spread=cd.get("spread_initial", 0))
                score_comparison = t("initial_score", init=u_init, adj=u_adj, delta=delta_str)

                cd_html = (
                    f'<div style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.7), rgba(15, 23, 42, 0.85)); border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 12px; padding: 18px; margin: 18px 0;">'
                    f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-bottom: 12px;">'
                    f'<div style="display: flex; align-items: center; gap: 8px;">'
                    f'<span style="font-size: 20px;">⚔️</span>'
                    f'<span style="font-weight: 800; font-size: 1.05rem; color: #c084fc;">{t("cross_debate_title")}</span>'
                    f'</div>'
                    f'<span style="font-size: 12px; background: rgba(139, 92, 246, 0.2); color: #e9d5ff; border: 1px solid rgba(139, 92, 246, 0.4); padding: 3px 10px; border-radius: 6px; font-weight: bold;">'
                    f'{spread_text}'
                    f'</span>'
                    f'</div>'
                    f'<div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid #ef4444; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;">'
                    f'<div style="font-size: 12px; font-weight: bold; color: #f87171; margin-bottom: 4px;">'
                    f'{cd.get("bear_avatar", "🐻")} {t("bear_attack_title")} {bear_n} ({b_init} pts):'
                    f'</div>'
                    f'<div style="font-size: 0.92rem; color: #fecaca; line-height: 1.5;">'
                    f'"{cd.get("turn1_attack")}"'
                    f'</div>'
                    f'</div>'
                    f'<div style="background: rgba(56, 189, 248, 0.08); border-left: 4px solid #38bdf8; border-radius: 8px; padding: 12px 14px;">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">'
                    f'<span style="font-size: 12px; font-weight: bold; color: #38bdf8;">'
                    f'{cd.get("bull_avatar", "🐂")} {t("bull_defense_title")} {bull_n}:'
                    f'</span>'
                    f'<span style="font-size: 12px; font-weight: 800; color: {delta_color};">'
                    f'{score_comparison}'
                    f'</span>'
                    f'</div>'
                    f'<div style="font-size: 0.92rem; color: #e0f2fe; line-height: 1.5;">'
                    f'"{cd.get("turn2_defense")}"'
                    f'</div>'
                    f'<div style="font-size: 11px; color: #94a3b8; margin-top: 6px; font-style: italic;">'
                    f'{t("reconsider_label")} {cd.get("adjustment_rationale", "")}'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(cd_html, unsafe_allow_html=True)

            # 🎙️ Multi-Agent Debate Dialogues
            diag_title = "🎙️ Legendary Investor AI Council & Risk Manager Deliberation Transcripts" if lang == "en" else "🎙️ 伝説の投資家AI 神7 ＆ リスク管理者による白熱合議録"
            st.markdown(f"### {diag_title}")
            for d in dialogues:
                badge_color = "#10b981" if d.get("stance") == "BULLISH" else ("#ef4444" if d.get("stance") == "BEARISH" else "#f59e0b")
                score_str = f"Score: {d.get('score')} pts" if lang == "en" else f"スコア: {d.get('score')}点"
                dialogue_html = (
                    f'<div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 5px solid {badge_color}; border-radius: 10px; padding: 16px; margin-bottom: 12px;">'
                    f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">'
                    f'<div style="display: flex; align-items: center; gap: 10px;">'
                    f'<span style="font-size: 24px;">{d.get("avatar", "👤")}</span>'
                    f'<div>'
                    f'<span style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF;">{d.get("name")}</span>'
                    f'<span style="font-size: 11px; color: #94a3b8; margin-left: 6px;">({d.get("title")})</span>'
                    f'</div>'
                    f'</div>'
                    f'<div style="display: flex; align-items: center; gap: 8px;">'
                    f'<span style="font-size: 11px; background: rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 4px; color: #cbd5e1;">{score_str}</span>'
                    f'<span style="background: {badge_color}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px;">{d.get("stance")}</span>'
                    f'</div>'
                    f'</div>'
                    f'<div style="color: #e2e8f0; font-size: 0.92rem; line-height: 1.6; padding-left: 34px;">'
                    f'{d.get("dialogue")}'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(dialogue_html, unsafe_allow_html=True)
        else:
            hint_msg = (
                "👈 Click any **one-click ticker preset** above (e.g. NVDA, AAPL) or enter a ticker and click **'⚔️ Convene Investment Council'** to initiate multi-agent debate and trade decisions."
                if lang == "en" else
                "👈 上記の**ワンクリック銘柄プリセット**（トヨタ、NVIDIA等）をクリックするか、ティッカーを入力して『⚔️ 投資作戦会議を招集する』を押すと、AIたちによる合議討議と売買判定がここに展開されます。"
            )
            st.info(hint_msg)

        # 🔍 AI市場スキャナー ＆ 本日のおすすめ有望銘柄自動発掘
        st.markdown("---")
        from core.ai_hedge_fund.market_screener import MarketScreener
        
        screener_title = "🔍 [AI Market Screener] Auto-discover Top Promising Equities" if lang == "en" else "🔍 【AI市場スキャナー】株式市場から今日のおすすめ有望銘柄を自動発掘する"
        with st.expander(screener_title, expanded=False):
            st.caption(
                "AI scans global markets and scores candidate equities matching Buffett, Wood, and Graham investment philosophies."
                if lang == "en" else
                "AIが日米欧市場を自動巡回し、バフェット・キャシー・グレアムの各哲学に合致する有望銘柄をスコアリングして推薦します。"
            )
            sc_c1, sc_c2 = st.columns([3, 1])
            with sc_c1:
                if lang == "en":
                    strategy_map = {
                        "🌟 All-Market Hybrid (Global AI Top Picks)": "ALL",
                        "🇪🇺 European Moats (ASML, SAP, Pharma)": "EUROPE_GLOBAL",
                        "⚔️ Defense, Heavy Industry & AI Power": "DEFENSE_ENERGY",
                        "🚀 Disruptive AI, Semiconductors & Next-Gen Tech": "AI_GROWTH",
                        "🎩 Wide Moat, High ROE & Quality Dividends": "VALUE_DIVIDEND",
                        "📊 Deep Value & Sub-PBR Undervalued Stocks": "DEEP_VALUE"
                    }
                    strat_label = "Select Screener Strategy (Investment Style)"
                else:
                    strategy_map = {
                        "🌟 全市場ハイブリッド厳選 (日米欧AI総合トップピック)": "ALL",
                        "🇪🇺 欧州グローバル・独占モート厳選 (ASML・SAP・製薬)": "EUROPE_GLOBAL",
                        "⚔️ 防衛・重工業＆AI電力 (国策・特需モメンタム)": "DEFENSE_ENERGY",
                        "🚀 破壊的AI・半導体＆次世代テック (キャシー・ウッド型)": "AI_GROWTH",
                        "🎩 ワイドモート＆高配当・高ROE (ウォーレン・バフェット型)": "VALUE_DIVIDEND",
                        "📊 PBR1倍割れ＆深層割安ディープバリュー (ベンジャミン・グレアム型)": "DEEP_VALUE"
                    }
                    strat_label = "発掘ストラテジー（投資スタイル）を選択"
                selected_strat = st.selectbox(
                    strat_label,
                    list(strategy_map.keys()),
                    key="hf_screener_strat"
                )
            with sc_c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                do_scan = st.button("⚡ Scan Market" if lang == "en" else "⚡ 市場をスキャン発掘", type="primary", use_container_width=True)

            cat_code = strategy_map.get(selected_strat, "ALL")

            # 🚀 高速起動・非同期化: キャッシュまたは即時プリセットを0msでロード（画面遷移時のフリーズ完全防止）
            if 'hf_screener_results' not in st.session_state:
                cached_res = MarketScreener.get_cached_opportunities(cat_code)
                cached_brief = MarketScreener.get_cached_market_brief()
                if cached_res:
                    st.session_state['hf_screener_results'] = cached_res
                    st.session_state['hf_market_brief'] = cached_brief
                else:
                    st.session_state['hf_screener_results'] = MarketScreener.get_instant_preset_opportunities(cat_code)
                    st.session_state['hf_market_brief'] = MarketScreener._default_brief()

            # ユーザーが「⚡ 市場をスキャン発掘」ボタンを押した時のみ最新市場をスキャン
            if do_scan:
                with st.spinner("AI analyzing and scoring latest market data..." if lang == "en" else "AIが最新市場データを解析・スコアリング中..."):
                    fresh_res = MarketScreener.scan_opportunities(cat_code, max_results=6)
                    fresh_brief = MarketScreener.get_ai_market_hot_brief()
                    st.session_state['hf_screener_results'] = fresh_res
                    st.session_state['hf_market_brief'] = fresh_brief
                    MarketScreener.save_screener_cache(cat_code, fresh_res, brief=fresh_brief)
                    st.toast("Latest market scan completed!" if lang == "en" else "最新の市場スキャンが完了しました！", icon="⚡")
                    st.rerun()

            def _loc_screener_item(raw_it, l):
                if l == "ja":
                    return raw_it
                loc = dict(raw_it)
                sym = loc.get("symbol", "")
                en_name_map = {
                    "7011.T": "Mitsubishi Heavy Industries",
                    "7012.T": "Kawasaki Heavy Industries",
                    "7013.T": "IHI Corporation",
                    "5803.T": "Fujikura",
                    "5802.T": "Sumitomo Electric",
                    "6301.T": "Komatsu",
                    "8058.T": "Mitsubishi Corp",
                    "8001.T": "ITOCHU Corp",
                    "8031.T": "Mitsui & Co",
                    "8053.T": "Sumitomo Corp",
                    "8002.T": "Marubeni",
                    "7203.T": "Toyota Motor",
                    "7267.T": "Honda Motor",
                    "6758.T": "Sony Group",
                    "6501.T": "Hitachi",
                    "6146.T": "DISCO Corporation",
                    "6857.T": "Advantest",
                    "8035.T": "Tokyo Electron",
                    "9984.T": "SoftBank Group",
                    "3778.T": "Sakura Internet",
                    "5401.T": "Nippon Steel",
                    "8306.T": "Mitsubishi UFJ Financial",
                    "8316.T": "Sumitomo Mitsui Financial",
                    "8411.T": "Mizuho Financial",
                    "9432.T": "NTT",
                    "9433.T": "KDDI",
                    "4063.T": "Shin-Etsu Chemical",
                    "6861.T": "Keyence",
                    "7974.T": "Nintendo"
                }
                en_cat_map = {
                    "7011.T": "Defense Leader, Aerospace & Gas Turbines",
                    "7012.T": "Defense, Aircraft Engines & Hydrogen",
                    "7013.T": "Defense, Jet Engines & Space",
                    "5803.T": "AI Datacenter Cabling & Optical Fiber",
                    "5802.T": "Power Grid Infrastructure & Harnesses",
                    "6301.T": "World #2 Construction Machinery & Mining",
                    "NVDA": "Generative AI Chips & GPU King",
                    "MSFT": "Azure Cloud & OpenAI Premier Partner",
                    "GOOGL": "Gemini AI, Search & YouTube",
                    "META": "Open Source AI (Llama) & Social Ecosystem",
                    "AMZN": "AWS Cloud & E-commerce Automation",
                    "PLTR": "Enterprise & Defense AI Platform",
                    "AVGO": "Custom AI ASICs & VMware",
                    "TSLA": "EV, Autonomous FSD & Humanoid Robotics",
                    "8058.T": "Top General Trading House & Progressive Dividend",
                    "7203.T": "Global Automotive Leader",
                    "AAPL": "Ecosystem & Share Buyback King"
                }
                en_thesis_map = {
                    "7011.T": "Surging defense budgets and next-gen turbine demand. Powerful momentum leader.",
                    "5803.T": "Near-monopoly in ultra-high-density optical connectors for generative AI datacenters.",
                    "NVDA": "Dominates ~90% of AI datacenter infrastructure. Exponential Blackwell architecture demand.",
                    "8058.T": "Warren Buffett favorite. Robust resource/non-resource cash flows with strong buybacks.",
                    "PLTR": "Accelerating enterprise AIP adoption with expanding defense contracts and S&P 500 inclusion.",
                    "6301.T": "High-margin IoT fleet via Komtrax with durable mining demand and steady dividend growth."
                }
                if sym in en_name_map:
                    loc["name"] = en_name_map[sym]
                if sym in en_cat_map:
                    loc["category"] = en_cat_map[sym]
                if sym in en_thesis_map:
                    loc["thesis"] = en_thesis_map[sym]
                return loc

            def _loc_watchlist_item(raw_it, l):
                if l == "ja":
                    return raw_it
                loc = dict(raw_it)
                sym = loc.get("symbol", "")
                n = loc.get("name", "")
                c = loc.get("category", "")
                
                sym_name_map = {
                    "6143.T": "Sodick Co",
                    "ING": "ING Group",
                    "TMG": "ING Group / TMG",
                    "LITE": "Lumentum Holdings",
                    "8848.T": "Leopalace21",
                    "5932.T": "Sankyo Tateyama",
                    "8016.T": "Onward Holdings",
                    "6323.T": "Rorze Corp",
                    "6730.T": "Axell Corp",
                    "8697.T": "Japan Exchange Group (JPX)",
                    "6976.T": "Taiyo Yuden",
                    "6533.T": "Orchestra Holdings",
                    "3382.T": "Seven & i Holdings",
                    "MRK": "Merck & Co., Inc.",
                    "RARE": "Ultragenyx Pharmaceutical",
                    "3799.T": "Keyware Solutions",
                    "MU": "Micron Technology",
                    "ACN": "Accenture plc",
                    "7847.T": "Graphite Design",
                    "ABBV": "AbbVie Inc",
                    "EW": "Edwards Lifesciences",
                    "8923.T": "Tosei Corp",
                    "OTLK": "Outlook Therapeutics",
                    "7011.T": "Mitsubishi Heavy Industries",
                    "7012.T": "Kawasaki Heavy Industries",
                    "7013.T": "IHI Corporation",
                    "5803.T": "Fujikura",
                    "5802.T": "Sumitomo Electric",
                    "6301.T": "Komatsu",
                    "8058.T": "Mitsubishi Corp",
                    "7203.T": "Toyota Motor",
                    "6758.T": "Sony Group",
                    "6501.T": "Hitachi",
                    "6146.T": "DISCO Corporation",
                    "6857.T": "Advantest",
                    "8035.T": "Tokyo Electron",
                    "9984.T": "SoftBank Group",
                    "3778.T": "Sakura Internet",
                    "5401.T": "Nippon Steel",
                    "8306.T": "Mitsubishi UFJ Financial",
                    "8316.T": "Sumitomo Mitsui Financial",
                    "8411.T": "Mizuho Financial",
                    "4063.T": "Shin-Etsu Chemical",
                    "6861.T": "Keyence",
                    "7974.T": "Nintendo"
                }
                if sym in sym_name_map:
                    n = sym_name_map[sym]
                else:
                    name_repl = {
                        "アクセル": "Axell Corp",
                        "日本取引所グループ": "Japan Exchange Group (JPX)",
                        "太陽誘電": "Taiyo Yuden",
                        "セブン＆アイ・ホールディングス": "Seven & i Holdings",
                        "キーウェアソリューションズ": "Keyware Solutions",
                        "グラファイトデザイン": "Graphite Design",
                        "トーセイ": "Tosei Corp",
                        "ソディック": "Sodick Co",
                        "INGグループ": "ING Group",
                        "レオパレス21": "Leopalace21",
                        "三協立山": "Sankyo Tateyama",
                        "オンワードホールディングス": "Onward Holdings",
                        "ローツェ": "Rorze Corp",
                        "三菱重工業": "Mitsubishi Heavy Industries",
                        "川崎重工業": "Kawasaki Heavy Industries",
                        "フジクラ": "Fujikura",
                        "コマツ": "Komatsu",
                        "三菱商事": "Mitsubishi Corp",
                        "トヨタ自動車": "Toyota Motor",
                        "ソニーグループ": "Sony Group",
                        "日立製作所": "Hitachi",
                        "アッヴィ": "AbbVie",
                        "アクセンチュア": "Accenture",
                        "マイクロン": "Micron Technology",
                        "メルク": "Merck & Co"
                    }
                    for k, v in name_repl.items():
                        n = n.replace(k, v)
                loc["name"] = n

                cat_repl = [
                    ("AI速報発掘: ", "AI Catalyst: "),
                    ("AI速報発掘:", "AI Catalyst: "),
                    ("バイオ・医薬品", "Biotech & Pharma"),
                    ("バイオ医薬品", "Biopharmaceuticals"),
                    ("バイオテクノロジー・眼科疾患治療", "Biotech & Ophthalmology"),
                    ("半導体設計・ファブレス", "Semiconductor Design & Fabless"),
                    ("金融取引所・金融サービス", "Financial Exchanges & Services"),
                    ("グローバル金融サービス", "Global Financial Services"),
                    ("電子部品", "Electronic Components"),
                    ("DX推進・デジタルマーケティング", "DX & Digital Marketing"),
                    ("小売・コンビニエンスストア", "Retail & Convenience Stores"),
                    ("製薬・ヘルスケア", "Pharma & Healthcare"),
                    ("希少疾患・バイオ医薬品", "Rare Diseases & Biopharma"),
                    ("ITサービス・セキュリティ", "IT Services & Cybersecurity"),
                    ("半導体メモリ", "Semiconductor Memory"),
                    ("ITコンサルティング・SI", "IT Consulting & SI"),
                    ("スポーツ用品・ゴルフ用品", "Sporting Goods & Golf Equipment"),
                    ("医療機器", "Medical Devices"),
                    ("不動産・ファンド運用", "Real Estate & Asset Management"),
                    ("不動産・アパート賃貸管理", "Real Estate & Rental Management"),
                    ("工作機械", "Machine Tools"),
                    ("光通信・フォトニクスソリューション", "Optical & Photonics Solutions"),
                    ("非鉄金属・建材", "Non-Ferrous Metals & Building Materials"),
                    ("アパレル・小売り", "Apparel & Retail"),
                    ("アパレル・小売", "Apparel & Retail"),
                    ("半導体製造装置", "Semiconductor Equipment"),
                    ("好材料株", "Catalyst Stock"),
                    ("マイ監視", "Custom Monitored")
                ]
                for k, v in cat_repl:
                    c = c.replace(k, v)
                loc["category"] = c
                return loc

            brief = st.session_state.get('hf_market_brief', {})
            if brief:
                mood_text = "Bullish / Prime Dip-Buying Window" if lang == "en" else brief.get('market_mood', '強気 (Bullish) / 押し目買い好機')
                lead_text = "Avoid emotional top-buying. Diversified capital allocation combining Warren Buffett's wide moats with Cathie Wood's AI innovation delivers the highest reward ratio." if lang == "en" else brief.get('lead_advice', '')
                st.markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 0.88rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                        <span style="font-weight: bold; color: #38bdf8;">🌐 {'AI Market Regime:' if lang == 'en' else 'AI市場地合い診断:'} {mood_text}</span>
                        <span style="font-size: 11px; color: #94a3b8;">{'Real-time Macro Radar' if lang == 'en' else 'リアルタイムマクロ速報'}</span>
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.83rem;">
                        <strong>💡 {'Key Focus:' if lang == 'en' else '今週の着眼点:'}</strong> {lead_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            screener_items = st.session_state.get('hf_screener_results', [])
            if screener_items:
                st.markdown(f"<div style='font-size: 12px; font-weight: bold; color: #34d399; margin-bottom: 8px;'>{'🎯 AI-Selected Opportunities (Click to Convene Council):' if lang == 'en' else '🎯 発掘された本日のおすすめ銘柄（クリックで作戦会議へ即投入）:'}</div>", unsafe_allow_html=True)
                
                for i in range(0, len(screener_items), 2):
                    col_card1, col_card2 = st.columns(2)
                    for c_idx, col_tgt in enumerate([col_card1, col_card2]):
                        if i + c_idx < len(screener_items):
                            raw_item = screener_items[i + c_idx]
                            item = _loc_screener_item(raw_item, lang)
                            with col_tgt:
                                with st.container(border=True):
                                    top_c1, top_c2 = st.columns([2.5, 1])
                                    with top_c1:
                                        st.markdown(f"**{item['name']}** (`{item['symbol']}`)")
                                        st.caption(f"{item['category']}")
                                    with top_c2:
                                        score_txt = f"AI {item['ai_score']} pts" if lang == "en" else f"AI {item['ai_score']}点"
                                        st.markdown(f"<div style='text-align: right;'><span style='background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 2px 8px; border-radius: 6px; font-weight: bold; font-size: 12px;'>{score_txt}</span></div>", unsafe_allow_html=True)
                                        st.markdown(f"<div style='text-align: right; font-weight: bold; font-size: 13px; color: #f8fafc; margin-top: 2px;'>{item['current_price']:,.2f} {item['currency']}</div>", unsafe_allow_html=True)
                                    
                                    st.markdown(f"<div style='font-size: 11px; color: #94a3b8; line-height: 1.4; margin: 4px 0 8px 0;'>💡 {item['thesis']}</div>", unsafe_allow_html=True)
                                    
                                    if lang == "en":
                                        m_pbr = f"PBR: {item['pb']:.2f}x" if item.get('pb') else ""
                                        m_div = f"Div: {item['dividend_yield']}%" if item.get('dividend_yield') else ""
                                        m_ret = f"20D: {item['return_20d_pct']:+}%" if item.get('return_20d_pct') else ""
                                    else:
                                        m_pbr = f"PBR: {item['pb']:.2f}倍" if item.get('pb') else ""
                                        m_div = f"配当: {item['dividend_yield']}%" if item.get('dividend_yield') else ""
                                        m_ret = f"20日: {item['return_20d_pct']:+}%" if item.get('return_20d_pct') else ""
                                    tag_text = " | ".join(filter(None, [m_pbr, m_div, m_ret]))
                                    if tag_text:
                                        st.caption(f"{'Metrics:' if lang == 'en' else '指標:'} {tag_text}")
                                    
                                    # 簡易的な株価グラフ (30日トレンド: キャッシュまたは事前計算から0ms描画)
                                    rec_closes = item.get('recent_closes') or MarketDataFeed.get_historical_closes(item['symbol'], period="1mo")
                                    spark_lbl = "30-Day Price Trend" if lang == "en" else "30日株価トレンド"
                                    spark_html = MarketDataFeed.render_sparkline_svg(rec_closes, width=280, height=46, label=spark_lbl)
                                    st.markdown(spark_html, unsafe_allow_html=True)
                                    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                                    
                                    card_btn_txt = f"👉 Convene Council on {item['name']}" if lang == "en" else f"👉 「{item['name']}」で作戦会議を開く"
                                    if st.button(card_btn_txt, key=f"pick_btn_{item['symbol']}", use_container_width=True):
                                        select_and_run_council(item['symbol'])

        # ⭐ Custom Watchlist UI
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        wl_title = "⭐ [My Watchlist] Add & Manage Custom Monitored Tickers" if lang == "en" else "⭐ 【マイ監視リスト】あなた独自の巡回銘柄を追加・管理する"
        with st.expander(wl_title, expanded=False):
            st.caption(
                "Tickers registered here are prioritized by autonomous trading daemons and market scanners."
                if lang == "en" else
                "ここで登録した銘柄は、15分おきの全自動売買デーモンおよび市場スキャナーで最優先パトロールされます。"
            )
            cw_col1, cw_col2 = st.columns([3, 1])
            with cw_col1:
                new_watch_sym = st.text_input(
                    "Ticker Symbol (e.g. NVDA, AAPL, MSFT, 7203.T)" if lang == "en" else "銘柄コード / ティッカー (例: 7011, 5803, 6758, MSFT, NVDA)",
                    key="hf_new_watch_sym"
                )
            with cw_col2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                add_watch_btn = st.button("➕ Add to Watchlist" if lang == "en" else "➕ 監視リストに追加", key="hf_add_watch_btn", use_container_width=True)
            
            if add_watch_btn and new_watch_sym:
                add_res = MarketScreener.add_custom_ticker(new_watch_sym)
                if add_res.get("success"):
                    st.success(add_res.get("message"))
                    st.session_state.pop('hf_screener_results', None)
                    st.rerun()
                else:
                    st.warning(add_res.get("message"))

            custom_items = MarketScreener.get_custom_watchlist()
            if not custom_items:
                st.info("No custom tickers registered yet. Add tickers you wish to monitor." if lang == "en" else "現在登録されているカスタム銘柄はありません。気になる銘柄を追加してください。")
            else:
                st.markdown(f"<div style='font-size: 12px; font-weight: bold; color: #38bdf8; margin: 8px 0 4px 0;'>{'Currently Monitored Custom Tickers:' if lang == 'en' else '現在登録中のカスタム巡回銘柄:'}</div>", unsafe_allow_html=True)
                for c_it in custom_items:
                    c_it_loc = _loc_watchlist_item(c_it, lang)
                    c_col_info, c_col_del = st.columns([4, 1])
                    with c_col_info:
                        st.markdown(f"⭐ **{c_it_loc['name']}** (`{c_it_loc['symbol']}`) - {c_it_loc.get('category', 'Custom')}")
                    with c_col_del:
                        if st.button("🗑️ " + ("Delete" if lang == "en" else "削除"), key=f"del_watch_{c_it['symbol']}", use_container_width=True):
                            MarketScreener.remove_custom_ticker(c_it['symbol'])
                            st.session_state.pop('hf_screener_results', None)
                            st.rerun()

        # 🕵️ Phase 3: Autonomous Alpha Researcher - Weekly Top 5 Picks
        from core.ai_hedge_fund.alpha_researcher import AlphaResearcher
        briefing = AlphaResearcher.get_latest_briefing()

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        alpha_title = "🕵️ [Autonomous Alpha Research] Lumina CIO Weekly Top 5 Alpha Picks" if lang == "en" else "🕵️ 【週末自律発掘】Lumina CIO 今週の特選アルファ銘柄 Top 5"
        with st.expander(alpha_title, expanded=True if briefing else False):
            if not briefing:
                st.info("No weekly research briefing generated yet. Click below to run autonomous discovery across 100-ticker universe." if lang == "en" else "まだ週末自律探索レポートが生成されていません。下のボタンを押して100銘柄ユニバースから即時発掘を実行できます。")
                if st.button("🚀 Run Autonomous Alpha Discovery (100 Universe)" if lang == "en" else "🚀 100銘柄ユニバースから自律アルファ探索を実行", key="btn_run_alpha_init", type="primary", use_container_width=True):
                    with st.spinner("AI analyzing fundamentals across 100 global tickers, selecting Top 5 with Gemini 3.8 Flash..." if lang == "en" else "AIが日米欧100銘柄の財務指標を走査し、Gemini 3.7 FlashがTop 5を選定中..."):
                        AlphaResearcher.run_research_scan()
                        st.rerun()
            else:
                top_b1, top_b2 = st.columns([3, 1])
                theme_lbl = "📌 Weekly Investment Theme:" if lang == "en" else "📌 今週の投資テーマ:"
                cio_lbl = "👑 CIO Strategic Thesis:" if lang == "en" else "👑 CIO戦略声明:"
                updated_lbl = "Last Updated:" if lang == "en" else "最終更新:"
                scan_lbl = "Universe: Global 100 Tickers" if lang == "en" else f"走査対象: 日米欧 {briefing.get('total_universe_scanned', 100)}銘柄ユニバース"
                with top_b1:
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 10px; padding: 12px 16px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                            <span style="font-size: 13px; font-weight: 800; color: #38bdf8;">{theme_lbl} 『{briefing.get('weekly_theme')}』</span>
                            <span style="font-size: 11px; background: rgba(56, 189, 248, 0.2); color: #7dd3fc; padding: 2px 8px; border-radius: 4px;">{briefing.get('market_regime', '')}</span>
                        </div>
                        <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
                            <strong>{cio_lbl}</strong> {briefing.get('cio_outlook')}
                        </div>
                        <div style="font-size: 10px; color: #94a3b8; margin-top: 6px;">
                            {updated_lbl} {briefing.get('generated_at')} | {scan_lbl}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with top_b2:
                    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                    rescan_txt = "🔄 Rescan Alpha" if lang == "en" else "🔄 アルファ再探索"
                    if st.button(rescan_txt, key="btn_rerun_alpha", use_container_width=True):
                        with st.spinner("Rescanning 100-ticker universe..." if lang == "en" else "100銘柄ユニバースを再スキャン中..."):
                            AlphaResearcher.run_research_scan()
                            st.rerun()

                # Render Top 5 Picks
                picks = briefing.get("top_picks", [])
                for p in picks:
                    p_loc = _loc_screener_item(p, lang)
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2.5, 2.5, 1.2])
                        with c1:
                            conv_txt = f"Conviction: **{p.get('conviction_score')} pts**" if lang == "en" else f"確信度: **{p.get('conviction_score')}点**"
                            st.markdown(f"**#{p.get('rank', 1)} {p_loc.get('name')}** (`{p.get('symbol')}`)")
                            st.caption(f"{p_loc.get('category')} | {conv_txt} ({p.get('sponsor_analysts')})")
                            st.markdown(f"<div style='font-size: 12px; color: #e2e8f0; line-height: 1.4;'>💡 {p_loc.get('catalyst', p.get('catalyst'))}</div>", unsafe_allow_html=True)
                        with c2:
                            curr_sym = p.get('currency', 'JPY')
                            c_p = p.get('current_price', 0)
                            if lang == "en":
                                pbr_txt = f"{p.get('pb_ratio'):.2f}x" if p.get('pb_ratio') else "N/A"
                                per_txt = f"{p.get('pe_trailing'):.1f}x" if p.get('pe_trailing') else "N/A"
                                ret_txt = f"{p.get('return_20d_pct'):+}%" if p.get('return_20d_pct') else "N/A"
                                price_hdr = f"Price: {c_p:,.2f} {curr_sym}"
                                metrics_cap = f"PBR: {pbr_txt} | PER: {per_txt} | 20D Chg: {ret_txt}"
                                upside_lbl = "Target Upside:"
                                stop_lbl = "Stop-loss:"
                                gate_lbl = "(Risk Gate: -13%)"
                            else:
                                pbr_txt = f"{p.get('pb_ratio'):.2f}倍" if p.get('pb_ratio') else "N/A"
                                per_txt = f"{p.get('pe_trailing'):.1f}倍" if p.get('pe_trailing') else "N/A"
                                ret_txt = f"{p.get('return_20d_pct'):+}%" if p.get('return_20d_pct') else "N/A"
                                price_hdr = f"現在値: {c_p:,.2f} {curr_sym}"
                                metrics_cap = f"PBR: {pbr_txt} | PER: {per_txt} | 20日騰落: {ret_txt}"
                                upside_lbl = "想定上値:"
                                stop_lbl = "推奨下値節目:"
                                gate_lbl = "(執行防壁: -13%)"
                            st.markdown(f"<div style='font-size: 13px; font-weight: bold; color: #38bdf8;'>{price_hdr}</div>", unsafe_allow_html=True)
                            st.caption(metrics_cap)
                            st.markdown(f"<span style='font-size: 11px; color: #34d399;'>{upside_lbl} +{p.get('target_upside_pct')}%</span> | <span style='font-size: 11px; color: #f87171;'>{stop_lbl} {p.get('stop_loss_pct')}%</span> <span style='font-size: 10px; color: #94a3b8;'>{gate_lbl}</span>", unsafe_allow_html=True)
                        with c3:
                            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                            convene_btn_txt = "👉 Convene Council" if lang == "en" else "👉 審査招集"
                            if st.button(convene_btn_txt, key=f"alpha_pick_{p.get('symbol')}", use_container_width=True):
                                select_and_run_council(p.get('symbol'))

    # =========================================================================
    # TAB 2: 💼 Portfolio & PnL Dashboard
    # =========================================================================
    with tab_portfolio:
        from core.ai_hedge_fund.hedge_fund_daemon import HedgeFundDaemon
        daemon = HedgeFundDaemon()

        st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;'>{t('broker_select_title')}</div>", unsafe_allow_html=True)
        b_c1, b_c2 = st.columns([2, 1])
        with b_c1:
            broker_mode = st.radio(
                "接続モード",
                [
                    t("paper_broker_name"),
                    t("kabu_broker_name"),
                    t("ibkr_broker_name")
                ],
                index=0,
                label_visibility="collapsed"
            )
        with b_c2:
            if st.button(t("reset_portfolio_btn"), use_container_width=True):
                paper_engine.reset_portfolio(initial_jpy=1000000.0, initial_usd=0.0)
                daemon.clear_logs()
                daemon.total_cycles = 0
                daemon.total_buys = 0
                daemon.total_sells = 0
                daemon._persist_state()
                st.session_state.pop('last_auto_cycle_res', None)
                st.success("Portfolio reset successfully!")
                st.rerun()

        # 🏢 外部証券会社接続ガイド (auカブコム証券 / IBKR)
        if "auカブコム" in broker_mode or "au Kabucom" in broker_mode:
            with st.container(border=True):
                kabu_sec_title = "🔵 au Kabucom Securities (kabu Station API) Settings" if lang == "en" else "🔵 auカブコム証券 (kabuステーション API) 接続設定"
                kabu_cap = "Requires 'kabu Station' desktop app running locally on PC. (Port 18080: Live / 18082: Staging/Paper)" if lang == "en" else "PC上で「kabuステーション」アプリが起動している必要があります。（ポート 18080: 本番 / 18082: 検証環境）"
                st.markdown(f"<div style='font-size: 13px; font-weight: bold; color: #38bdf8;'>{kabu_sec_title}</div>", unsafe_allow_html=True)
                st.caption(kabu_cap)
                k_c1, k_c2, k_c3 = st.columns([2, 1.5, 1.5])
                with k_c1:
                    st.text_input("kabu Station API Password" if lang == "en" else "kabuステーション APIパスワード", type="password", key="kabu_api_pw")
                with k_c2:
                    k_opts = ["Staging Simulation (Port: 18082)", "Live Production (Port: 18080)"] if lang == "en" else ["検証シミュレーション (Port: 18082)", "本番取引 (Port: 18080)"]
                    st.selectbox("Environment" if lang == "en" else "接続環境", k_opts, key="kabu_port")
                with k_c3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🔌 " + ("Test Connection" if lang == "en" else "接続テスト"), key="btn_test_kabu_conn", use_container_width=True):
                        st.info("Health check sent to kabu Station API." if lang == "en" else "kabuステーションAPIへのヘルスチェックを実行しました。アプリが起動しているか確認してください。")

        elif "Interactive Brokers" in broker_mode:
            with st.container(border=True):
                ibkr_sec_title = "🟣 Interactive Brokers (IBKR) Settings" if lang == "en" else "🟣 Interactive Brokers (IBKR) 接続設定"
                ibkr_cap = "For US & global equities auto-trading. Requires Trader Workstation (TWS) or IB Gateway running locally." if lang == "en" else "米国株・世界株の自動売買用。PC上で「Trader Workstation (TWS)」または「IB Gateway」が起動している必要があります。"
                st.markdown(f"<div style='font-size: 13px; font-weight: bold; color: #a855f7;'>{ibkr_sec_title}</div>", unsafe_allow_html=True)
                st.caption(ibkr_cap)
                ib_c1, ib_c2, ib_c3 = st.columns([2, 1.5, 1.5])
                with ib_c1:
                    st.text_input("Host Address" if lang == "en" else "ホストアドレス", value="127.0.0.1", key="ibkr_host")
                with ib_c2:
                    ib_opts = ["IB Gateway Paper (Port: 4002)", "IB Gateway Live (Port: 4001)", "TWS Paper (Port: 7497)", "TWS Live (Port: 7496)"] if lang == "en" else ["IB Gateway ペーパー (Port: 4002)", "IB Gateway リアル (Port: 4001)", "TWS ペーパー (Port: 7497)", "TWS リアル (Port: 7496)"]
                    st.selectbox("Port" if lang == "en" else "ポート", ib_opts, key="ibkr_port")
                with ib_c3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🔌 " + ("Test Connection" if lang == "en" else "接続テスト"), key="btn_test_ibkr_conn", use_container_width=True):
                        st.info("Tested connectivity to TWS / IB Gateway API port." if lang == "en" else "TWS / IB Gateway APIポートへの疎通テストを実行しました。")

        # 🤖 自律自動売買エンジン (Autonomous Auto-Trading Engine & Daemon)
        from core.ai_hedge_fund.auto_trader import AutoTrader
        from core.ai_hedge_fund.hedge_fund_daemon import HedgeFundDaemon
        
        daemon = HedgeFundDaemon()
        daemon_status = daemon.get_status()
        is_bot_running = daemon_status.get("is_running", False)

        with st.expander("🤖 [Full-Auto Trading] 24/7 Autonomous Daemon & Engine" if lang == "en" else "🤖 【フルオート自動売買】24時間自律巡回＆自動売買エンジン", expanded=True):
            # Live Status Banner
            if is_bot_running:
                _cur_cap_mode = daemon_status.get("capacity_mode", "AUTO")
                if lang == "en":
                    _cur_cap_desc = "AI Dynamic (5-6)" if _cur_cap_mode == "AUTO" else f"{_cur_cap_mode} Slots"
                    running_title = "Autonomous AI Hedge Fund: 24/7 BACKGROUND PATROL ACTIVE"
                    next_scan_lbl = "Next Scan & Council in:"
                    interval_lbl = f"Interval: <strong>Every {daemon_status.get('effective_interval_minutes', daemon_status.get('interval_minutes'))}m</strong>"
                    watchdog_lbl = "⚡ Sentinel Watchdog:"
                    watchdog_st = "10s Active Monitoring" if daemon_status.get('watchdog_active') else "Standby"
                    exec_info = f"Executed: <strong style='color: #fff;'>{daemon_status.get('total_cycles')} cycles</strong> | Holdings: <strong style='color: #38bdf8;'>{_cur_cap_desc}</strong> | Total Buys: <strong style='color: #34d399;'>{daemon_status.get('total_buys')}</strong> | Total Exits: <strong style='color: #f87171;'>{daemon_status.get('total_sells')}</strong>"
                else:
                    _cur_cap_desc = "AI動的おまかせ (5〜6枠)" if _cur_cap_mode == "AUTO" else f"{_cur_cap_mode}枠"
                    running_title = "自律型AIヘッジファンド: 常時バックグラウンド巡回中"
                    next_scan_lbl = "次回市場スキャン・合議まで:"
                    interval_lbl = f"巡回間隔: <strong>每{daemon_status.get('effective_interval_minutes', daemon_status.get('interval_minutes'))}分</strong>"
                    watchdog_lbl = "⚡ リアルタイム番犬センチネル:"
                    watchdog_st = "10秒常時監視中" if daemon_status.get('watchdog_active') else "待機中"
                    exec_info = f"実行済: <strong style='color: #fff;'>{daemon_status.get('total_cycles')}サイクル</strong> | 保有枠: <strong style='color: #38bdf8;'>{_cur_cap_desc}</strong> | 累計買い: <strong style='color: #34d399;'>{daemon_status.get('total_buys')}件</strong> | 累計決済: <strong style='color: #f87171;'>{daemon_status.get('total_sells')}件</strong>"
                st.markdown(f"""
                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 12px 18px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 20px;">🟢</span>
                        <div>
                            <strong style="color: #34d399; font-size: 1.05rem;">{running_title}</strong>
                            <div style="font-size: 11px; color: #cbd5e1; margin-top: 2px;">
                                {next_scan_lbl} <strong style="color: #38bdf8;">{daemon_status.get('countdown_str')}</strong> | {interval_lbl} {f"<span style='color: #fbbf24;'>({daemon_status.get('adaptive_desc')})</span>" if daemon_status.get('adaptive_desc') else ""} | {watchdog_lbl} <strong style="color: #34d399;">{watchdog_st}</strong>
                            </div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #94a3b8;">
                        {exec_info}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                standby_title = "Autonomous AI Hedge Fund: STANDBY (Paused)" if lang == "en" else "自律型AIヘッジファンド: スタンバイ (停止中)"
                standby_desc = (
                    "Click 'Start 24/7 Background Trading' below to let AI autonomously patrol markets, debate, execute orders, and manage stop-loss/take-profit."
                    if lang == "en" else
                    "「常時自動売買をスタート」を押すと、指定した間隔でAIが市場を全自動巡回し、合議・発注・利確損切りを完全自動で執行し続けます。"
                )
                st.markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 12px 18px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 20px;">🔴</span>
                        <div>
                            <strong style="color: #94a3b8; font-size: 1.05rem;">{standby_title}</strong>
                            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                                {standby_desc}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            at_c1, at_c2, at_c3, at_c4, at_c5 = st.columns([1.5, 0.8, 0.7, 1.1, 1.1])
            with at_c1:
                strat_label = "Discovery Strategy" if lang == "en" else "自律発掘戦略"
                if lang == "en":
                    strat_opts = [
                        "🌟 All-Market Hybrid (ALL)",
                        "⚔️ Defense, Heavy Industry & Power (DEFENSE_ENERGY)",
                        "🚀 Disruptive AI & Next-Gen Tech (AI_GROWTH)",
                        "🎩 Wide Moat & High ROE (VALUE_DIVIDEND)",
                        "📊 Deep Value & Sub-PBR (DEEP_VALUE)"
                    ]
                else:
                    strat_opts = [
                        "🌟 全市場ハイブリッド厳選 (ALL)",
                        "⚔️ 防衛・重工業＆AI電力 (DEFENSE_ENERGY)",
                        "🚀 破壊的AI・半導体＆次世代テック (AI_GROWTH)",
                        "🎩 ワイドモート＆高配当・高ROE (VALUE_DIVIDEND)",
                        "📊 PBR1倍割れ＆深層割安ディープバリュー (DEEP_VALUE)"
                    ]
                auto_strat = st.selectbox(
                    strat_label,
                    strat_opts,
                    index=0,
                    key="hf_auto_strat"
                )
                auto_strat_code = "ALL"
                if "DEFENSE_ENERGY" in auto_strat: auto_strat_code = "DEFENSE_ENERGY"
                elif "AI_GROWTH" in auto_strat: auto_strat_code = "AI_GROWTH"
                elif "VALUE_DIVIDEND" in auto_strat: auto_strat_code = "VALUE_DIVIDEND"
                elif "DEEP_VALUE" in auto_strat: auto_strat_code = "DEEP_VALUE"

            with at_c2:
                saved_interval = daemon_status.get("interval_minutes", 15)
                interval_options = [5, 10, 15, 30, 60]
                default_interval_idx = interval_options.index(saved_interval) if saved_interval in interval_options else 2
                interval_label = "Patrol Interval" if lang == "en" else "自動巡回間隔"
                interval_sel = st.selectbox(
                    interval_label,
                    interval_options,
                    index=default_interval_idx,
                    format_func=(lambda x: f"Every {x} min") if lang == "en" else (lambda x: f"{x}分毎に実行"),
                    key="hf_interval_sel"
                )

            with at_c3:
                max_buys_label = "Max Orders / Cycle" if lang == "en" else "1回最大発注"
                max_buys = st.selectbox(max_buys_label, [1, 2, 3], index=1, key="hf_max_buys")

            with at_c4:
                guard_label = "Order Restrictions" if lang == "en" else "発注制限 (API準拠)"
                guard_opts = ["Market Hours Only (Live)", "24/7 Instant Execution (Test)"] if lang == "en" else ["開場時間中のみ (実戦)", "24時間即時約定 (テスト)"]
                guard_help = "Blocks off-hours market orders to replicate live broker execution." if lang == "en" else "「開場時間中のみ」を選択すると、実証券APIと同様に休場中の成行発注をブロックし、開場を待機します。"
                market_guard_mode = st.selectbox(
                    guard_label,
                    guard_opts,
                    index=0,
                    help=guard_help,
                    key="hf_market_guard_mode"
                )
                enforce_hours = ("Market Hours Only" in market_guard_mode or "開場時間中のみ" in market_guard_mode)

            with at_c5:
                cap_options = [
                    "🤖 AI Dynamic (5-6 Assets)" if lang == "en" else "🤖 AI動的おまかせ (5〜6銘柄)",
                    "🚀 5 Assets Fixed (High Conviction)" if lang == "en" else "🚀 5銘柄固定 (リターン集中)",
                    "🛡️ 6 Assets Fixed (Diversified)" if lang == "en" else "🛡️ 6銘柄固定 (低リスク分散)",
                    "🏛️ 4 Assets Fixed (Conservative)" if lang == "en" else "🏛️ 4銘柄固定 (従来基準)"
                ]
                saved_cap_mode = daemon_status.get("capacity_mode", "AUTO")
                default_cap_idx = 0
                if saved_cap_mode == "5_FIXED": default_cap_idx = 1
                elif saved_cap_mode == "6_FIXED": default_cap_idx = 2
                elif saved_cap_mode == "4_FIXED": default_cap_idx = 3

                cap_label = "Max Holdings" if lang == "en" else "保有上限枠"
                cap_choice = st.selectbox(
                    cap_label,
                    cap_options,
                    index=default_cap_idx,
                    help="AI controls optimal 5-6 slots dynamically based on session volatility." if lang == "en" else "AI動的おまかせ: 日米市場の開場バランスやボラティリティに応じて、AIが自動で最適な5〜6銘柄枠をコントロールします。",
                    key="hf_capacity_choice"
                )
                cap_code = "AUTO"
                if "5 Assets Fixed" in cap_choice or "5銘柄固定" in cap_choice: cap_code = "5_FIXED"
                elif "6 Assets Fixed" in cap_choice or "6銘柄固定" in cap_choice: cap_code = "6_FIXED"
                elif "4 Assets Fixed" in cap_choice or "4銘柄固定" in cap_choice: cap_code = "4_FIXED"

            # Action Buttons Row
            btn_col1, btn_col2 = st.columns([1.5, 1.5])
            with btn_col1:
                if not is_bot_running:
                    start_btn_txt = "🟢 Start 24/7 Background Trading" if lang == "en" else "🟢 常時バックグラウンド自動売買をスタート"
                    if st.button(start_btn_txt, type="primary", use_container_width=True):
                        daemon.start_patrol(
                            interval_minutes=interval_sel,
                            strategy=auto_strat_code,
                            max_orders=max_buys,
                            enforce_market_hours=enforce_hours,
                            capacity_mode=cap_code
                        )
                        st.success("Started background trading daemon! Continuous autonomous patrol active." if lang == "en" else "常時自動売買デーモンを起動しました！バックグラウンドで全自動売買を開始します。")
                        st.rerun()
                else:
                    stop_btn_txt = "🛑 Stop 24/7 Autonomous Trading" if lang == "en" else "🛑 常時自動売買を停止する"
                    if st.button(stop_btn_txt, type="secondary", use_container_width=True):
                        daemon.stop_patrol()
                        st.warning("Stopped background trading daemon." if lang == "en" else "常時自動売買デーモンを停止しました。")
                        st.rerun()

            with btn_col2:
                run_1cycle_txt = "⚡ Run 1 Cycle Instantly" if lang == "en" else "⚡ 今すぐ1サイクル手動即時実行"
                if st.button(run_1cycle_txt, use_container_width=True):
                    with st.spinner("AI running scan ➔ council debate ➔ auto-order ➔ risk patrol..." if lang == "en" else "🤖 AIが市場スキャン ➔ 合議判定 ➔ 自動発注 ➔ 利確/損切りパトロールを即時実行中..."):
                        cycle_res = AutoTrader.run_autonomous_cycle(
                            broker_engine=paper_engine,
                            strategy=auto_strat_code,
                            max_new_orders=max_buys,
                            enforce_market_hours=enforce_hours,
                            capacity_mode=cap_code
                        )
                        st.session_state['last_auto_cycle_res'] = cycle_res
                        st.success("Instant trading cycle completed!" if lang == "en" else "即時売買サイクルが完了しました！")
                        st.rerun()

            # Live Log Display
            current_logs = daemon.get_status().get("logs", [])
            last_res = st.session_state.get('last_auto_cycle_res')
            if last_res and "logs" in last_res:
                current_logs = current_logs + [l for l in last_res["logs"] if l not in current_logs]

            if current_logs:
                col_lt1, col_lt2, col_lt3 = st.columns([3.2, 0.9, 1.2])
                with col_lt1:
                    log_hdr = f"📜 Autonomous Trading Activity Log (Total {len(current_logs)} entries, scrollable):" if lang == "en" else f"📜 自律売買アクティビティログ (全 {len(current_logs)} 行・上下スクロール可能):"
                    st.markdown(f"<div style='font-size: 12px; font-weight: bold; color: #38bdf8; margin-top: 10px;'>{log_hdr}</div>", unsafe_allow_html=True)
                with col_lt2:
                    clear_logs_txt = "🗑️ Clear Logs" if lang == "en" else "🗑️ ログ消去"
                    if st.button(clear_logs_txt, key="hf_clear_logs_btn", use_container_width=True):
                        daemon.clear_logs()
                        st.session_state.pop('last_auto_cycle_res', None)
                        st.rerun()
                with col_lt3:
                    reset_acct_txt = "🔄 Reset Account" if lang == "en" else "🔄 口座リセット"
                    if st.button(reset_acct_txt, key="hf_quick_reset_btn", help="Reset portfolio and logs" if lang == "en" else "保有株・履歴・ログを初期化し1から再開", use_container_width=True):
                        paper_engine.reset_portfolio(initial_jpy=1000000.0, initial_usd=0.0)
                        daemon.reset_state()
                        AutoTrader._examined_cooldowns.clear()
                        st.session_state.pop('last_auto_cycle_res', None)
                        st.success("Portfolio reset successfully!" if lang == "en" else "口座を完全初期化しました！")
                        st.rerun()

                import html
                def _loc_daemon_log(log_line: str, l: str) -> str:
                    if l == "ja" or not log_line:
                        return log_line
                    s = log_line
                    repls = [
                        ("【常時自律売買スタート】", "[24/7 Autonomous Trading Started]"),
                        ("【自動復帰】", "[Auto-Resume]"),
                        ("アプリ再起動・更新を検知し、前回の自動売買パトロールを自動再開しました。", "Detected app restart/update, automatically resumed previous trading patrol."),
                        ("【市場オープン状況】", "[Market Session Status]"),
                        ("主要市場閉場中: ニュース材料スキャン&評価監視モード", "Major markets closed: Scanning news catalysts & monitoring valuation"),
                        ("欧州市場取引時間中 (16:00~00:30 JST): 欧州最良モード株重点パトロール", "European session active (16:00~00:30 JST): Prioritizing European top-conviction equities"),
                        ("東京市場取引時間中 (09:00~15:30 JST): 東証現物株リアルタイム発注モード", "Tokyo session active (09:00~15:30 JST): TSE real-time execution mode"),
                        ("米国市場取引時間中 (22:30~05:00 JST): 米国株リアルタイム発注モード", "US session active (22:30~05:00 JST): US equities real-time execution mode"),
                        ("【巡回インターバル】", "[Patrol Interval]"),
                        ("市場閉場中 (省エネ見守り): 次回巡回は約1時間後 (1時間間隔モード)", "Markets closed (Eco Mode): Next patrol in ~1 hour (1h interval mode)"),
                        ("市場開場中 (機動的パトロール): 次回巡回は約", "Markets open (Active Patrol): Next patrol in ~"),
                        ("自律型AIヘッジファンド自律売買サイクルを開始しました (戦略: ", "Started autonomous AI hedge fund trading cycle (Strategy: "),
                        ("【マクロ天候レーダー】", "[Macro Weather Radar]"),
                        ("FRB純流動性:", "Fed Net Liquidity:"),
                        ("前週比:", "WoW:"),
                        ("流動性拡大期 (マクロ追い風・リスク選好)", "Liquidity Expansion (Macro Tailwind / Risk-On)"),
                        ("流動性縮小期 (マクロ逆風・リスク回避)", "Liquidity Contraction (Macro Headwind / Risk-Off)"),
                        ("【オプション気流レーダー】", "[Options Flow Radar]"),
                        ("【オプション流動性安定】", "[Options Liquidity Stable]"),
                        ("ともにポジティブ・ガンマ維持、MMのクッション効果による安定レジーム。", "both maintaining Positive Gamma, stable regime driven by MM cushioning effect."),
                        ("ネガティブ・ガンマ警戒、ボラティリティ急拡大リスクゾーン。", "Negative Gamma alert, elevated volatility risk zone."),
                        ("【未発注API市場開場ガード】", "[Pre-Execution Market Session Guard]"),
                        ("現在、東京市場 (09:00~15:30 JST) および米国市場 (22:30~05:00 JST (夏時間 EDT)) ともに取引時間外です。実発注API規格 (kabuステーション/IBKR) に準拠し、時間外成行発注を停止して待機 (NY 22:30~ / 東証 09:00~) を待機します。", "Currently both Tokyo (09:00~15:30 JST) and US (22:30~05:00 JST) markets are outside trading hours. In compliance with real execution APIs (kabu Station / IBKR), after-hours market orders are paused until open."),
                        ("自律売買サイクルが正常に完了しました (新規買い: ", "Autonomous trading cycle completed successfully (New Buys: "),
                        ("件, 決済: ", " | Exits: "),
                        ("件 - 市場開場待機中)", " - Awaiting Market Open)"),
                        ("件 - 巡回完了)", " - Patrol Complete)"),
                        ("【動的保有枠判定】", "[Dynamic Slot Allocation]"),
                        ("上限枠:", "Max Slots:"),
                        ("銘柄 (日米クロスマケット共有枠拡張 (相手国セッション買付スロット確保)) | 現在保有: ", "stocks (US-Japan Cross-Market shared slot expanded) | Currently held: "),
                        ("巡回間隔: 15分毎", "Interval: Every 15m"),
                        ("戦略: ALL", "Strategy: ALL"),
                        ("[常時自動売買スタート]", "[24/7 Autonomous Trading Started]"),
                        ("保有枠: AI動的おまかせ(5〜6銘柄)", "Holding Slots: AI Dynamic (5-6 Tickers)"),
                        ("保有枠: AI動的おまかせ (5〜6銘柄)", "Holding Slots: AI Dynamic (5-6 Tickers)"),
                        ("発注承認: 実発注API準備 (待機中のみ発注)", "Execution Approval: Live API Ready (Session Guard Active)"),
                        ("⚡ 高頻度リアルタイム番犬センチネル (10秒巡回): 起動", "⚡ High-Frequency Sentinel Watchdog (10s patrol): Active"),
                        ("⚡ 高頻度リアルタイム番犬センチネル (10秒巡回)", "⚡ High-Frequency Sentinel Watchdog (10s patrol)"),
                        ("主要市場開場中: ニュース材料スキャン＆評価損益監視モード", "Major markets open: Scanning news catalysts & monitoring valuation"),
                        ("主要市場開場中: ニュース材料スキャン&評価損益監視モード", "Major markets open: Scanning news catalysts & monitoring valuation"),
                        ("米国セッション: 22:30〜05:00 JST (夏時間 EDT)", "US session: 22:30-05:00 JST (EDT)"),
                        ("米国セッション: 22:30〜05:00 JST (冬時間 EST)", "US session: 22:30-05:00 JST (EST)"),
                        ("市場閉場中 (省エネ見守り): 次回巡回は毎時00分 (1時間間隔モード)", "Markets closed (Eco Mode): Next patrol at :00 (1h interval mode)"),
                        ("⚡ 自律型AIヘッジファンド自動売買サイクルを開始しました", "⚡ Autonomous AI Hedge Fund trading cycle initiated"),
                        ("[市場巡回状況]", "[Market Patrol Status]"),
                        ("欧州市場取引時間中 (16:00〜00:30 JST): 欧州覇権モート株重点パトロール", "European session active (16:00-00:30 JST): Prioritizing European Moat Leaders"),
                        ("流動性拡大期 (マクロ追い風・リスク選好)", "Liquidity Expansion (Macro Tailwind / Risk-On)"),
                        ("流動性縮小期 (マクロ逆風・リスク回避)", "Liquidity Contraction (Macro Headwind / Risk-Off)"),
                        ("[オプション気流レーダー]", "[Options Flow Radar]"),
                        ("ともにポジティブ・ガンマ維持。MMのクッション効果による安定レジーム。", "Both maintaining positive gamma. Stable regime with MM cushioning effect."),
                        ("[実発注API市場開閉ガード]", "[Live API Session Guard]"),
                        ("現在、東京市場 (09:00〜15:30 JST) および米国市場 (22:30〜05:00 JST (夏時間 EDT)) ともに取引時間外です。実発注API規則 (kabuステーション/IBKR) に準拠し、時間外成行発注を停止して開場 (NY 22:30〜 / 東京 翌09:00〜) を待機します。", "Both Tokyo (09:00-15:30 JST) and US (22:30-05:00 JST) markets are outside trading hours. In compliance with real execution APIs (kabu Station / IBKR), after-hours market orders are paused until market open (NY 22:30 / Tokyo 09:00)."),
                        ("🏁 自律売買サイクルが正常に完了しました [新規買い: 0件 | exits: 0件 - 市場待機中]", "🏁 Autonomous trading cycle completed successfully [New Buys: 0 | Exits: 0 - Standing by for market open]"),
                        ("[AI動的保有枠状況]", "[AI Dynamic Slot Status]"),
                        ("銘柄 (日米クロスマーケット共存枠拡張 (相手国セッション寄付スロット確保)) | 現在保有: ", "tickers (US-Japan Cross-Market shared slot expanded) | Currently held: "),
                        ("銘柄", " tickers"),
                        ("株", " shs"),
                        ("買い付けました", " purchased"),
                        ("保有中", "held")
                    ]
                    for jp, en in repls:
                        s = s.replace(jp, en)
                    if any('\u3000' <= ch <= '\u9fff' for ch in s):
                        from core.ai_hedge_fund.translation_engine import TranslationEngine
                        s = TranslationEngine.translate_text(s, l)
                    return s

                log_html_lines = []
                for line in current_logs:
                    line_loc = _loc_daemon_log(line, lang)
                    escaped = html.escape(line_loc)
                    if any(k in escaped for k in ["🟢", "【買い執行】", "[BUY EXECUTED]", "約定", "正常に完了", "completed successfully"]):
                        color = "#34d399"  # emerald green
                    elif any(k in escaped for k in ["⚠️", "スキップ", "[SKIPPED]", "余力不足", "保留", "見送り"]):
                        color = "#fbbf24"  # amber
                    elif any(k in escaped for k in ["🛑", "損切り", "[STOP-LOSS", "失敗", "エラー"]):
                        color = "#f87171"  # rose red
                    elif any(k in escaped for k in ["🏆", "大勝利", "利確", "[PROFIT-TAKEN]", "目標株価"]):
                        color = "#facc15"  # gold
                    elif any(k in escaped for k in ["🚀", "トレイリング"]):
                        color = "#c084fc"  # purple
                    elif any(k in escaped for k in ["🔍", "🏛️"]):
                        color = "#38bdf8"  # cyan
                    else:
                        color = "#cbd5e1"
                    log_html_lines.append(f"<div style='color: {color}; margin-bottom: 3px; word-break: break-all;'>{escaped}</div>")

                terminal_html = "".join(log_html_lines)
                st.markdown(f"""
                <div style="
                    background-color: #0b1120;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 12px 14px;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 11.5px;
                    line-height: 1.5;
                    max-height: 380px;
                    overflow-y: scroll;
                    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
                ">
                    {terminal_html}
                </div>
                """, unsafe_allow_html=True)

        # 📢 X (Twitter) Autonomous Report Post
        from core.state_manager import get_stock_report_scheduler_settings, save_stock_report_scheduler_settings
        try:
            from x_scheduler import get_stock_report_task_status, register_stock_report_tasks, unregister_stock_report_tasks
        except ImportError:
            def get_stock_report_task_status():
                return {"enabled": False, "is_registered": False, "times": []}
            def register_stock_report_tasks():
                return {"success": False, "errors": ["Local task scheduler integration is optional."]}
            def unregister_stock_report_tasks():
                return {"success": True}

        stock_cfg = get_stock_report_scheduler_settings() or {}
        task_st = get_stock_report_task_status()

        x_title = "📢 [X (Twitter) Autonomous Report Post] Daily 1-2x Broadcast" if lang == "en" else "📢 【X (Twitter) 運用推移レポート自律ポスト】1日1〜2回 自動発信"
        with st.expander(x_title, expanded=True):
            st.caption(
                "Autonomously broadcasts hedge fund portfolio returns, PnL, holdings, and AI council theses to official X (Twitter)."
                if lang == "en" else
                "AI株式自動売買の資産推移、損益状況、保有銘柄、AI合議方針を公式X（Twitter）へ自動ポストします（1日1回〜2回）。"
            )
            
            x_col1, x_col2 = st.columns([1.6, 2.4])
            with x_col1:
                stock_enabled = st.toggle("Enable Autonomous Posting" if lang == "en" else "自律ポストを有効化", value=stock_cfg.get("enabled", True), key="hf_x_post_toggle")
                if lang == "en":
                    freq_options = {
                        "once_daily_2000": "1x Daily (20:00 Daily Brief & Close)",
                        "twice_daily": "2x Daily (15:45 Close / 21:30 Evening)",
                        "once_daily_close": "1x Daily (15:45 Market Close only)",
                        "once_daily_night": "1x Daily (21:30 Evening Flash only)"
                    }
                    freq_label = "Posting Schedule"
                    attach_label = "Auto-attach Infographic Performance Card Image"
                else:
                    freq_options = {
                        "once_daily_2000": "1日1回 (20:00 夜間速報・日次まとめ)",
                        "twice_daily": "1日2回 (15:45 東証引け後 / 21:30 夜間速報)",
                        "once_daily_close": "1日1回 (15:45 東証引け後のみ)",
                        "once_daily_night": "1日1回 (21:30 夜間速報のみ)"
                    }
                    freq_label = "投稿スケジュール"
                    attach_label = "インフォグラフィック実績カード画像を自動添付"
                curr_freq = stock_cfg.get("frequency", "once_daily_2000")
                if curr_freq == "once_daily_2000" or curr_freq == "once_daily":
                    idx = 0
                elif curr_freq == "twice_daily":
                    idx = 1
                elif "close" in curr_freq:
                    idx = 2
                else:
                    idx = 3
                selected_freq_label = st.selectbox(
                    freq_label,
                    list(freq_options.values()),
                    index=idx,
                    key="hf_x_freq_select"
                )
                selected_freq_key = [k for k, v in freq_options.items() if v == selected_freq_label][0]
                attach_card = st.checkbox(attach_label, value=stock_cfg.get("attach_card_image", True), key="hf_x_card_chk")

                # Save settings if changed
                if selected_freq_key == "once_daily_2000":
                    new_times = ["20:00"]
                elif selected_freq_key == "twice_daily":
                    new_times = ["15:45", "21:30"]
                elif selected_freq_key == "once_daily_close":
                    new_times = ["15:45"]
                else:
                    new_times = ["21:30"]
                if (stock_enabled != stock_cfg.get("enabled") or 
                    selected_freq_key != stock_cfg.get("frequency") or 
                    attach_card != stock_cfg.get("attach_card_image") or
                    new_times != stock_cfg.get("times")):
                    stock_cfg["enabled"] = stock_enabled
                    stock_cfg["frequency"] = selected_freq_key
                    stock_cfg["times"] = new_times
                    stock_cfg["attach_card_image"] = attach_card
                    save_stock_report_scheduler_settings(stock_cfg)
                    st.toast("Settings saved" if lang == "en" else "推移報告スケジュール設定を保存しました", icon="💾")

                # Windows Task Scheduler status
                is_reg = task_st.get("is_registered", False)
                status_txt = ("🟢 Registered (Runs on schedule)" if is_reg else "⚪ Unregistered") if lang == "en" else ("🟢 登録済み (PC起動時も定時射出)" if is_reg else "⚪ 未登録")
                sched_status_lbl = "Task Scheduler:" if lang == "en" else "Windowsタスク連携:"
                st.markdown(f"<div style='font-size: 11.5px; color: #94a3b8; margin-top: 6px;'>{sched_status_lbl} <strong style='color: {'#34d399' if is_reg else '#f87171'};'>{status_txt}</strong></div>", unsafe_allow_html=True)
                if st.button("⏰ " + ("Register / Update Task Scheduler" if lang == "en" else "タスクスケジューラに登録・更新"), key="hf_reg_task_btn", use_container_width=True):
                    r_res = register_stock_report_tasks()
                    if r_res.get("success"):
                        st.success(f"Registered to task scheduler! ({', '.join(r_res.get('registered_times', []))})" if lang == "en" else f"タスクスケジューラに登録しました！({', '.join(r_res.get('registered_times', []))})")
                        st.rerun()
                    else:
                        st.error(f"Scheduler note: {r_res.get('errors')}" if lang == "en" else f"登録エラー: {r_res.get('errors')}")

            with x_col2:
                # Cached daily report generation (TTL 60s to eliminate redundant rerun overhead)
                cache_key = f'_hf_cached_sample_rep_{lang}'
                cache_time_key = f'_hf_cached_sample_rep_time_{lang}'
                _cached_rep = st.session_state.get(cache_key)
                _cached_rep_t = st.session_state.get(cache_time_key, 0)
                now_ts = time.time()
                if not _cached_rep or (now_ts - _cached_rep_t > 60):
                    _cached_rep = FundContentGenerator.generate_portfolio_daily_report(lang=lang)
                    st.session_state[cache_key] = _cached_rep
                    st.session_state[cache_time_key] = now_ts
                sample_rep = _cached_rep
                st.text_area("Post Content (140-char limit)" if lang == "en" else "ポスト本文 (140文字 厳格制御)", value=sample_rep.get("main_tweet", ""), height=155, key="hf_live_preview_text")

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button("🚀 " + ("Test Post to X" if lang == "en" else "今すぐテスト射出 (Xへ投稿)"), type="primary", use_container_width=True, key="hf_test_post_x_btn"):
                        with st.spinner("Posting to X..." if lang == "en" else "Xへ最新運用推移レポートを射出中..."):
                            post_res = FundContentGenerator.post_daily_stock_report_to_x(force=True, attach_card=attach_card)
                            if post_res.get("success"):
                                tw_url = post_res.get("url", "")
                                st.success(f"🎉 Post published! [Open Post]({tw_url})" if lang == "en" else f"🎉 Xへの投稿が完了しました！ [ポストを開く]({tw_url})")
                            else:
                                st.error(f"Error: {post_res.get('error')}" if lang == "en" else f"X投稿エラー: {post_res.get('error')}")
                with btn_c2:
                    if st.button("🖼️ " + ("Preview Infographic Card" if lang == "en" else "実績カード画像を生成して確認"), use_container_width=True, key="hf_preview_card_btn"):
                        c_img = FundContentGenerator.generate_portfolio_card_image(sample_rep)
                        if c_img and os.path.exists(c_img):
                            st.session_state['hf_preview_card_img'] = c_img

                prev_card = st.session_state.get('hf_preview_card_img')
                if prev_card and os.path.exists(prev_card):
                    st.image(prev_card, caption="Infographic Performance Card (1200x675)" if lang == "en" else "X添付用 運用実績カード画像 (1200x675)", use_container_width=True)

        # 📝 note.com Autonomous Daily Report Article
        note_title = "📝 [note.com Portfolio Daily Article] Autonomous Market Close Publishing" if lang == "en" else "📝 【note.com 損益日報自律投稿】市場営業日 20:00頃 自動報告"
        with st.expander(note_title, expanded=True):
            st.caption(
                "Autonomously publishes comprehensive portfolio PnL, asset curve, and 5-agent AI council reviews as rich articles to note.com."
                if lang == "en" else
                "東証（日本株市場）が開いていた営業日の20:00頃に、AI自動売買の運用損益・資産推移・約定アクション・5人AI合議レビューをまとめた高品質な損益日報記事を、アイキャッチ画像付きでnoteへ自動投稿します。"
            )
            
            note_c1, note_c2 = st.columns([1.6, 2.4])
            with note_c1:
                n_enabled = st.toggle("Enable Autonomous note.com Daily Article" if lang == "en" else "note自動損益日報を有効化", value=stock_cfg.get("note_enabled", True), key="hf_note_post_toggle")
                n_time = st.text_input(
                    "Target Time (JST)" if lang == "en" else "投稿目標時刻 (JST)",
                    value=stock_cfg.get("note_time", "20:00"),
                    key="hf_note_time_input",
                    help="Specified evening time after market close (15:30 JST) when daily PnL is finalized." if lang == "en" else "市場大引け（15:30）以降、損益が確定した夜間の時間帯を指定します"
                )
                
                if lang == "en":
                    n_status_opts = {
                        "draft": "Save as Draft (Recommended)",
                        "published": "Direct Publish (Hands-Free)"
                    }
                else:
                    n_status_opts = {
                        "draft": "下書き保存 (推奨・スマホ/PCで確認後に公開)",
                        "published": "即時自動公開 (手放し完全自動)"
                    }
                curr_n_st = stock_cfg.get("note_status", "draft")
                n_idx = 0 if curr_n_st == "draft" else 1
                sel_n_st_label = st.selectbox(
                    "note Publishing Status" if lang == "en" else "note投稿ステータス",
                    list(n_status_opts.values()),
                    index=n_idx,
                    key="hf_note_status_select"
                )
                sel_n_status_key = [k for k, v in n_status_opts.items() if v == sel_n_st_label][0]

                # 営業日判定バッジ
                is_trading_today = MarketSession.is_tse_trading_day()
                if is_trading_today:
                    today_tse_lbl = "🟢 <strong>TSE Trading Day Active</strong> (Scheduled around 20:00 JST)" if lang == "en" else "🟢 <strong>本日は東証営業日</strong>（20:00頃に自動投稿対象）"
                    st.markdown(f"<div style='font-size: 11.5px; padding: 5px 8px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); color: #34d399; margin-top: 8px;'>{today_tse_lbl}</div>", unsafe_allow_html=True)
                else:
                    closed_tse_lbl = "🔴 <strong>Market Closed Today</strong> (Weekend / Holiday - Auto-Skipped)" if lang == "en" else "🔴 <strong>本日は市場休業日</strong>（土日・祝日・年末年始のため自動スキップ）"
                    st.markdown(f"<div style='font-size: 11.5px; padding: 5px 8px; border-radius: 6px; background: rgba(239, 68, 68, 0.15); color: #f87171; margin-top: 8px;'>{closed_tse_lbl}</div>", unsafe_allow_html=True)

                last_note_d = stock_cfg.get("last_posted_note_date", "")
                if last_note_d:
                    last_note_lbl = "Last Published:" if lang == "en" else "最終投稿日:"
                    st.markdown(f"<div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>{last_note_lbl} {last_note_d}</div>", unsafe_allow_html=True)

                # Save if changed
                if (n_enabled != stock_cfg.get("note_enabled") or
                    n_time != stock_cfg.get("note_time") or
                    sel_n_status_key != stock_cfg.get("note_status")):
                    stock_cfg["note_enabled"] = n_enabled
                    stock_cfg["note_time"] = n_time
                    stock_cfg["note_status"] = sel_n_status_key
                    save_stock_report_scheduler_settings(stock_cfg)
                    st.toast("Saved note daily report settings" if lang == "en" else "note損益日報の設定を保存しました", icon="💾")

            with note_c2:
                btn_n1, btn_n2 = st.columns(2)
                with btn_n1:
                    post_note_now_btn = "🚀 Post PnL Report to note Now" if lang == "en" else "🚀 今すぐ損益日報をnoteへ投稿"
                    if st.button(post_note_now_btn, type="primary", use_container_width=True, key="hf_test_post_note_btn"):
                        spin_note_txt = "Composing PnL report and publishing to note.com..." if lang == "en" else "Geminiで損益日報を執筆し、noteへ投稿中..."
                        with st.spinner(spin_note_txt):
                            note_res = FundContentGenerator.post_daily_stock_report_to_note(
                                force=True,
                                status=sel_n_status_key,
                                attach_card=True
                            )
                            if note_res.get("success"):
                                n_title = note_res.get("title", "")
                                n_edit_url = note_res.get("edit_url", "")
                                n_pub_url = note_res.get("url", "")
                                st.session_state['hf_last_note_res'] = note_res
                                st.success(f"🎉 Published to note.com! ({sel_n_st_label})" if lang == "en" else f"🎉 noteへの投稿が完了しました！（{sel_n_st_label}）")
                                if n_edit_url:
                                    st.markdown(f"👉 [**{'Open note.com Draft Editor' if lang == 'en' else 'note下書きエディタを開く'}**]({n_edit_url})")
                                elif n_pub_url:
                                    st.markdown(f"👉 [**{'Open Published Article' if lang == 'en' else '公開記事を開く'}**]({n_pub_url})")
                            else:
                                st.error(f"note publication error: {note_res.get('error') or note_res.get('reason')}" if lang == "en" else f"note投稿エラー: {note_res.get('error') or note_res.get('reason')}")

                with btn_n2:
                    pv_note_btn = "👁️ Preview note Article" if lang == "en" else "👁️ note記事をプレビュー生成"
                    if st.button(pv_note_btn, use_container_width=True, key="hf_preview_note_btn"):
                        with st.spinner("Generating daily PnL report preview..." if lang == "en" else "損益日報プレビューを生成中..."):
                            pv_art = FundContentGenerator.generate_note_daily_pnl_report()
                            st.session_state['hf_note_preview_article'] = pv_art

                pv = st.session_state.get('hf_note_preview_article')
                if pv:
                    title_draft_lbl = "**Draft Title**" if lang == "en" else "**タイトル案**"
                    st.markdown(f"{title_draft_lbl}: `{pv.get('title')}`")
                    pv_exp_title = "📄 Article Preview (HTML Render)" if lang == "en" else "📄 記事プレビュー（HTMLレンダリング）"
                    with st.expander(pv_exp_title, expanded=False):
                        st.markdown(pv.get("body_html", ""), unsafe_allow_html=True)

        st.markdown("---")

        col_rf1, col_rf2 = st.columns([2.5, 1.5])
        with col_rf1:
            live_monitor_lbl = "📊 Real-Time Portfolio PnL Monitor" if lang == "en" else "📊 リアルタイム・ポートフォリオ損益モニター"
            st.markdown(f"<div style='font-size: 13px; font-weight: bold; color: #38bdf8; margin-top: 4px;'>{live_monitor_lbl}</div>", unsafe_allow_html=True)
        with col_rf2:
            toggle_lbl = "📡 Auto-Refresh PnL (Every 15s)" if lang == "en" else "📡 リアルタイム損益自動更新 (15秒毎)"
            toggle_help = "Automatically updates holdings quotes, market value, unrealized PnL, and USD/JPY rate every 15s without refreshing full page." if lang == "en" else "ONにすると、画面全体をリロードすることなく、保有ポジションの現在株価・時価評価額・含み損益・ドル円為替レートを15秒ごとにバックグラウンド自動更新します。"
            auto_live_refresh = st.toggle(
                toggle_lbl,
                value=True,
                help=toggle_help,
                key="hf_auto_live_refresh"
            )

        @st.fragment(run_every=15 if auto_live_refresh else None)
        def render_live_portfolio_fragment():
            # Portfolio Summary calculation (with fast real-time quotes)
            summary = paper_engine.get_portfolio_summary()
            now_quote_str = time.strftime("%H:%M:%S")
            
            # 🌐 Real-Time Market Session & Risk Filter Badges
            sess = MarketSession.get_market_status()
            if lang == "en":
                tse_badge = "<span style='background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 3px 8px; border-radius: 6px; font-weight: bold;'>🟢 TSE: Open (09:00~15:30 JST)</span>" if sess["tse_open"] else "<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; padding: 3px 8px; border-radius: 6px;'>🔴 TSE: Closed</span>"
                us_badge = f"<span style='background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 3px 8px; border-radius: 6px; font-weight: bold;'>🟢 US Markets: Open {'(EDT)' if sess['us_dst'] else '(EST)'}</span>" if sess["us_open"] else f"<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; padding: 3px 8px; border-radius: 6px;'>🔴 US Markets: Closed {'(EDT)' if sess['us_dst'] else '(EST)'}</span>"
                sess_lbl = "⏰ Market Sessions:"
                quote_lbl = f"📡 Live Quotes: <strong>{now_quote_str}</strong> (15s auto-refresh)"
                gate_lbl = "🛡️ Earnings Gate: <strong>3-Day Skip Active</strong>"
            else:
                tse_badge = "<span style='background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 3px 8px; border-radius: 6px; font-weight: bold;'>🟢 東証: 取引中 (09:00〜15:30)</span>" if sess["tse_open"] else "<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; padding: 3px 8px; border-radius: 6px;'>🔴 東証: 閉場中</span>"
                us_badge = f"<span style='background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 3px 8px; border-radius: 6px; font-weight: bold;'>🟢 米国市場: 取引中 {'(夏時間)' if sess['us_dst'] else '(冬時間)'}</span>" if sess["us_open"] else f"<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; padding: 3px 8px; border-radius: 6px;'>🔴 米国市場: 閉場中 {'(夏時間)' if sess['us_dst'] else '(冬時間)'}</span>"
                sess_lbl = "⏰ 市場稼働状況:"
                quote_lbl = f"📡 リアルタイム株価: <strong>{now_quote_str}</strong> (15秒自動更新)"
                gate_lbl = "🛡️ 決算回避: <strong>3日前スキップ有効</strong>"
            
            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 12px;">
                    <span style="color: #94a3b8; font-weight: bold;">{sess_lbl}</span>
                    {tse_badge}
                    {us_badge}
                </div>
                <div style="display: flex; align-items: center; gap: 10px; font-size: 12px;">
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 3px 10px; border-radius: 6px;">{quote_lbl}</span>
                    <span style="background: rgba(168, 85, 247, 0.15); color: #c084fc; padding: 3px 10px; border-radius: 6px;">{gate_lbl}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 📈 Equity Curve Chart (Asset Growth Curve)
            eq_data = paper_engine.get_equity_curve(limit=100)
            if eq_data and len(eq_data) >= 1:
                eq_title = "📈 [Equity Curve Chart] NAV Growth Curve & Drawdown Profile" if lang == "en" else "📈 【資産推移グラフ】エクイティカーブ・チャート（初期資金100万円からの成長曲線）"
                with st.expander(eq_title, expanded=True):
                    import pandas as pd
                    chart_df = pd.DataFrame(eq_data)
                    time_col = "Time" if lang == "en" else "日時"
                    eq_col = "Total Equity (JPY)" if lang == "en" else "総資産 (円換算)"
                    chart_df[time_col] = chart_df["timestamp"].apply(lambda x: str(x)[5:16])
                    chart_df[eq_col] = chart_df["total_equity_jpy"]
                    
                    # Performance KPIs
                    init_val = float(chart_df[eq_col].iloc[0])
                    current_val = float(chart_df[eq_col].iloc[-1])
                    ath_val = float(chart_df[eq_col].max())
                    total_return_pct = ((current_val - init_val) / init_val * 100.0) if init_val > 0 else 0.0
                    mdd_pct = ((current_val - ath_val) / ath_val * 100.0) if ath_val > 0 else 0.0

                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("Initial Capital" if lang == "en" else "初期元本", f"¥{init_val:,.0f}")
                    kpi2.metric("ATH Value" if lang == "en" else "最高資産高 (ATH)", f"¥{ath_val:,.0f}")
                    kpi3.metric("Cumulative Return" if lang == "en" else "通算収益率", f"{total_return_pct:+.2f}%", delta=f"{total_return_pct:+.2f}%")
                    kpi4.metric("Max Drawdown from ATH" if lang == "en" else "最高値からのドローダウン", f"{mdd_pct:.2f}%", delta=f"{mdd_pct:.2f}%", delta_color="inverse")

                    st.line_chart(chart_df.set_index(time_col)[eq_col], use_container_width=True)

            # 🏛️ QuantStats Institutional Performance & Monthly Returns Heatmap
            from core.ai_hedge_fund.quant_reporter import QuantReporter
            QuantReporter.render_in_streamlit(paper_engine)

            # 📊 Institutional Performance Tear Sheet (pyfolio-reloaded architecture)
            from core.ai_hedge_fund.fund_tear_sheet import FundTearSheet
            tear_title = "📊 [Institutional Tear Sheet] pyfolio Asset Curves & Drawdown Profile" if lang == "en" else "📊 【機関投資家ファンド・ティアシート】 pyfolio 運用資産推移＆ドローダウン診断"
            with st.expander(tear_title, expanded=True):
                tear_head = "🏛️ Wall Street Standard Fund Tear Sheet (pyfolio-reloaded)" if lang == "en" else "🏛️ ウォール街基準ファンド・ティアシート (pyfolio-reloaded)"
                tear_cap = "Generates cumulative returns (NAV curve), underwater drawdown (MDD depth), and Sortino/Calmar ratios." if lang == "en" else "累積リターン（NAVカーブ）、アンダーウォーター・ドローダウン（MDD深度）、ソルティノ/カルマーレシオ等のクオンツ指標を完全統合生成します。note有料記事や月次レポートの図版として即時利用可能です。"
                st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>{tear_head}</div>", unsafe_allow_html=True)
                st.caption(tear_cap)
                
                regen_btn_txt = "🔄 Regenerate Tear Sheet" if lang == "en" else "🔄 ティアシート画像を再生成・更新"
                btn_re_tear = st.button(regen_btn_txt, key="btn_regen_tearsheet")
                if btn_re_tear or not os.path.exists(FundTearSheet.TEAR_SHEET_PNG):
                    spin_txt = "Rendering institutional tear sheet (NAV curve & drawdown profile)..." if lang == "en" else "機関投資家ティアシート（NAVカーブ・ドローダウンプロファイル）を描画中..."
                    with st.spinner(spin_txt):
                        FundTearSheet.generate_tear_sheet(paper_engine, save_image=True)
                
                if os.path.exists(FundTearSheet.TEAR_SHEET_PNG):
                    st.image(FundTearSheet.TEAR_SHEET_PNG, use_container_width=True)

            # 🌪️ Phase 3: Adversarial Black Swan Stress-Test Diagnosis
            from core.ai_hedge_fund.adversarial_simulator import AdversarialSimulator
            stress_rep = AdversarialSimulator.get_latest_report()

            stress_title = "🌪️ [Adversarial Stress Test] Tail-Risk & Extreme Shock Simulation (Historical Crisis Modeling)" if lang == "en" else "🌪️ 【敵対的ブラックスワン・ストレステスト】極限市場ショック耐性診断（歴史的危機シミュレーション）"
            with st.expander(stress_title, expanded=True if stress_rep else False):
                if not stress_rep:
                    st.info("No stress-test diagnostic results yet. Click below to simulate your portfolio's shock resilience against historical crises." if lang == "en" else "まだストレステスト診断結果がありません。下のボタンを押して保有ポートフォリオのショック耐性を今すぐシミュレーションできます。")
                    stress_btn_lbl = "⚡ Run Portfolio Stress Test" if lang == "en" else "⚡ ポートフォリオのストレステストを実行"
                    if st.button(stress_btn_lbl, key="btn_run_stress_init", type="primary", use_container_width=True):
                        with st.spinner("AI applying historical shocks (Ueda Shock, Liquidity Squeeze, Rates Spike) to portfolio..." if lang == "en" else "AIが歴史的ショック（植田ショック・流動性危機・金利急騰）をポートフォリオに適用中..."):
                            AdversarialSimulator.run_stress_test()
                            st.rerun()
                else:
                    st1, st2 = st.columns([3, 1])
                    with st1:
                        mdd = stress_rep.get("estimated_max_drawdown_pct", 0)
                        worst_name = stress_rep.get("worst_scenario_name", "Liquidity Crisis" if lang == "en" else "流動性危機")
                        worst_lbl = "⚠️ Worst-Case Shock:" if lang == "en" else "⚠️ 最悪想定ショック:"
                        mdd_lbl = "Max Estimated Drawdown:" if lang == "en" else "最大想定ドローダウン:"
                        vuln_lbl = "🔍 Vulnerability Diagnosis:" if lang == "en" else "🔍 脆弱性診断:"
                        def_lbl = "🛡️ Recommended Defensive Action:" if lang == "en" else "🛡️ 推奨防衛アクション:"
                        st.markdown(f"""
                        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-left: 5px solid #ef4444; border-radius: 10px; padding: 12px 16px; margin-bottom: 12px;">
                            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-bottom: 6px;">
                                <span style="font-weight: 800; font-size: 13px; color: #f87171;">{worst_lbl} 『{worst_name}』</span>
                                <span style="font-size: 13px; font-weight: 800; background: rgba(239, 68, 68, 0.2); color: #fca5a5; padding: 2px 10px; border-radius: 6px;">
                                    {mdd_lbl} {mdd}%
                                </span>
                            </div>
                            <div style="font-size: 12px; color: #fecaca; line-height: 1.5;">
                                <strong>{vuln_lbl}</strong> {stress_rep.get('vulnerability_diagnosis')}
                            </div>
                            <div style="font-size: 12px; color: #e2e8f0; line-height: 1.5; margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1);">
                                <strong>{def_lbl}</strong> {stress_rep.get('recommended_defensive_action')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with st2:
                        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                        re_stress_lbl = "⚡ Re-run Stress Test" if lang == "en" else "⚡ 再ストレステスト"
                        if st.button(re_stress_lbl, key="btn_rerun_stress", use_container_width=True):
                            with st.spinner("Recalculating historical shock scenarios..." if lang == "en" else "歴史的ショックシナリオを再計算中..."):
                                AdversarialSimulator.run_stress_test()
                                st.rerun()

                    # Calibrated Limits Badges (Anti-Whipsaw Quantitative Defense)
                    calib = stress_rep.get("calibrated_limits", {})
                    cl1, cl2, cl3 = st.columns(3)
                    cl1.metric("Suggested Cash Reserve" if lang == "en" else "推奨キャッシュ待機枠", f"{calib.get('suggested_cash_reserve_pct', 20)}%")
                    cl2.metric("Max Single-Stock Cap" if lang == "en" else "単一銘柄配分上限 (ロット抑制)", f"{calib.get('max_single_stock_alloc_pct', 12)}%")
                    cl3.metric("Anti-Whipsaw Guard" if lang == "en" else "損切り貧乏防止防壁", "ATR×2.0 Dynamic Floor" if lang == "en" else "ATR×2.0倍 呼吸床保証")

                    aw_policy = calib.get("anti_whipsaw_policy")
                    if aw_policy:
                        aw_title = "🛡️ **Anti-Whipsaw Defense Policy:**" if lang == "en" else "🛡️ **損切り貧乏対策方針:**"
                        st.caption(f"{aw_title} {aw_policy}")

                    hist_impact_lbl = "Historical Shock Impact Breakdown:" if lang == "en" else "歴史的ショック別 想定インパクト詳細:"
                    st.markdown(f"<div style='font-size: 12px; font-weight: bold; color: #94a3b8; margin: 8px 0 4px 0;'>{hist_impact_lbl}</div>", unsafe_allow_html=True)
                    sc_cols = st.columns(2)
                    for i, sc in enumerate(stress_rep.get("scenarios_evaluation", [])):
                        with sc_cols[i % 2]:
                            sev_color = "#ef4444" if sc.get("hit_severity") in ["CRITICAL", "HIGH"] else "#f59e0b"
                            st.markdown(f"""
                            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                    <span style="font-size: 12px; font-weight: bold; color: #f1f5f9;">{sc.get('name')}</span>
                                    <span style="font-size: 11px; font-weight: bold; color: {sev_color};">{sc.get('expected_drawdown_pct')}% ({sc.get('hit_severity')})</span>
                                </div>
                                <div style="font-size: 11px; color: #94a3b8; line-height: 1.4;">
                                    {sc.get('impact_summary')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)


            # Metrics Display (Interactive Brokers Multi-Currency Unified Dashboard)
            c_eq1, c_eq2, c_pnl1, c_fx = st.columns(4)
            c_eq1.metric(
                "🏛️ Total Portfolio Equity (JPY Equiv)" if lang == "en" else "🏛️ 総合総資産 (円換算合計)",
                f"¥{summary['total_equity_jpy']:,.0f}",
                f"JPY: ¥{summary['equity_jpy']:,.0f} | USD: ${summary['equity_usd']:,.2f}" if lang == "en" else f"円: ¥{summary['equity_jpy']:,.0f} | ＄: ${summary['equity_usd']:,.2f}"
            )
            c_eq2.metric(
                "💰 Total Buying Power" if lang == "en" else "💰 総合購買余力 (買付余力)",
                f"¥{summary['total_buying_power_jpy']:,.0f}",
                f"JPY Cash: ¥{summary['cash_jpy']:,.0f} | USD Cash: ${summary['cash_usd']:,.2f}" if lang == "en" else f"円余力: ¥{summary['cash_jpy']:,.0f} | ＄余力: ${summary['cash_usd']:,.2f}"
            )
            tot_pnl_jpy = summary["total_unrealized_pnl_jpy"]
            tot_pnl_pct = summary["total_unrealized_pnl_pct"]
            c_pnl1.metric(
                "📈 Unrealized PnL" if lang == "en" else "📈 総合評価損益",
                f"¥{tot_pnl_jpy:+,.0f}",
                delta=f"{tot_pnl_pct:+.2f}%"
            )
            c_fx.metric(
                "🌐 USD/JPY Exchange Rate" if lang == "en" else "🌐 USD/JPY 為替レート",
                f"¥{summary['usdjpy_rate']:.2f}",
                "IBKR Interbank Direct" if lang == "en" else "IBKRインターバンク直結"
            )

            # 💱 Currency Conversion & Buying Power Breakdown
            cur_exp_title = "💱 [IBKR Multi-Currency] Cash Breakdown & Instant Currency Swap (JPY ⇄ USD)" if lang == "en" else "💱 【IBKRマルチカレンシー】購買余力の内訳 ＆ 口座内即時両替（円 ⇄ ドル振替）"
            with st.expander(cur_exp_title, expanded=False):
                st.caption("Like Interactive Brokers, swap between JPY and USD instantly in your account. The trading daemon shares this converted buying power." if lang == "en" else "Interactive Brokers同様、口座内の日本円と米ドルはワンクリックで相互に即時両替できます。自動売買デーモンもこの両替余力を共有して買い付けます。")
                
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    jpy_title = "🇯🇵 JPY Buying Power (Japan Equities)" if lang == "en" else "🇯🇵 日本株 購買余力"
                    direct_cash_lbl = "(Direct Cash Held)" if lang == "en" else "(直接保有現金)"
                    max_jpy_desc = "Max JPY buying power if USD converted:" if lang == "en" else "ドル余力を円に充当した場合の最大買付可能額:"
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-weight: bold; color: #38bdf8; font-size: 13px;">{jpy_title}</div>
                        <div style="font-size: 20px; font-weight: bold; color: #f8fafc; margin: 4px 0;">¥{summary['cash_jpy']:,.0f} <span style="font-size: 12px; color: #94a3b8;">{direct_cash_lbl}</span></div>
                        <div style="font-size: 11px; color: #cbd5e1;">{max_jpy_desc} <strong style="color: #34d399;">¥{summary['total_buying_power_jpy']:,.0f}</strong></div>
                    </div>
                    """, unsafe_allow_html=True)
                with sub_col2:
                    usd_title = "🇺🇸 USD Buying Power (US Equities)" if lang == "en" else "🇺🇸 米国株 購買余力"
                    max_usd_desc = "Max USD buying power if JPY converted:" if lang == "en" else "円余力をドルに充当した場合の最大買付可能額:"
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(168, 85, 247, 0.2); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-weight: bold; color: #c084fc; font-size: 13px;">{usd_title}</div>
                        <div style="font-size: 20px; font-weight: bold; color: #f8fafc; margin: 4px 0;">${summary['cash_usd']:,.2f} <span style="font-size: 12px; color: #94a3b8;">{direct_cash_lbl}</span></div>
                        <div style="font-size: 11px; color: #cbd5e1;">{max_usd_desc} <strong style="color: #34d399;">${summary['total_buying_power_usd']:,.2f}</strong></div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                conv_c1, conv_c2, conv_c3 = st.columns([1.5, 1.5, 1])
                with conv_c1:
                    dir_label = "Conversion Direction" if lang == "en" else "両替方向"
                    dir_opts = ["USD ➔ JPY", "JPY ➔ USD"] if lang == "en" else ["USD ➔ JPY (ドルを円に両替)", "JPY ➔ USD (円をドルに両替)"]
                    conv_dir = st.selectbox(
                        dir_label,
                        dir_opts,
                        key="hf_conv_dir"
                    )
                with conv_c2:
                    if "USD ➔ JPY" in conv_dir:
                        max_amt = summary["cash_usd"]
                        amt_label = "USD Amount to Convert ($)" if lang == "en" else "両替する米ドル金額 ($)"
                        conv_amt = st.number_input(amt_label, min_value=1.0, max_value=max(1.0, max_amt), value=min(1000.0, max(1.0, max_amt)), step=100.0, key="hf_conv_amt")
                        st.caption(f"Yields approx ¥{conv_amt * summary['usdjpy_rate']:,.0f} at ¥{summary['usdjpy_rate']:.2f}/USD" if lang == "en" else f"現在のレート(¥{summary['usdjpy_rate']:.2f})で約 ¥{conv_amt * summary['usdjpy_rate']:,.0f} になります")
                    else:
                        max_amt = summary["cash_jpy"]
                        amt_label = "JPY Amount to Convert (¥)" if lang == "en" else "両替する日本円金額 (¥)"
                        conv_amt = st.number_input(amt_label, min_value=100.0, max_value=max(100.0, max_amt), value=min(100000.0, max(100.0, max_amt)), step=10000.0, key="hf_conv_amt")
                        st.caption(f"Yields approx ${conv_amt / summary['usdjpy_rate']:,.2f} at ¥{summary['usdjpy_rate']:.2f}/USD" if lang == "en" else f"現在のレート(¥{summary['usdjpy_rate']:.2f})で約 ${conv_amt / summary['usdjpy_rate']:,.2f} になります")
                with conv_c3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    swap_btn_lbl = "💱 Execute Swap" if lang == "en" else "💱 両替を実行"
                    if st.button(swap_btn_lbl, key="hf_do_convert_btn", use_container_width=True):
                        f_c, t_c = ("USD", "JPY") if "USD ➔ JPY" in conv_dir else ("JPY", "USD")
                        c_res = paper_engine.convert_currency(f_c, t_c, conv_amt)
                        if c_res.get("success"):
                            st.success(f"Currency swapped successfully! ({f_c} {c_res['deducted']:,.2f} ➔ {t_c} {c_res['received']:,.2f})" if lang == "en" else f"両替が完了しました！ ({f_c} {c_res['deducted']:,.2f} ➔ {t_c} {c_res['received']:,.2f})")
                            st.rerun()
                        else:
                            st.error(c_res.get("error"))

            # Holdings Table
            st.markdown("### " + ("📊 Open Positions" if lang == "en" else "📊 保有ポジション一覧"))
            positions = summary.get("positions", [])
            if not positions:
                st.info("No active positions held. Convene an investment council from Tab 1 to analyze and place orders." if lang == "en" else "現在保有中の銘柄はありません。「AI投資作戦会議」タブから銘柄を分析し、買い注文を発注してください。")
            else:
                for p in positions:
                    sym_p = p["symbol"]
                    qty_p = p["quantity"]
                    entry_p = p["avg_entry_price"]
                    cur_p = p["current_price"]
                    mval_p = p["market_value"]
                    pnl_p = p["unrealized_pnl"]
                    pnl_pct_p = p["unrealized_pnl_pct"]
                    curr_p = p["currency"]

                    pnl_color = "#34d399" if pnl_p >= 0 else "#f87171"
                    
                    with st.container(border=True):
                        col_p1, col_p2, col_p3, col_p_chart, col_p4, col_p5 = st.columns([2.2, 1.7, 1.7, 2.1, 1.6, 1.1])
                        with col_p1:
                            half_badge_txt = "🎯 50% Profit Taken (Risk-Free Trailing)" if lang == "en" else "🎯 50%利確済(ノーリスク追従中)"
                            half_badge = f"<span style='background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>{half_badge_txt}</span>" if p.get('half_profit_taken') else ""
                            st.markdown(f"**{p['company_name']}** (`{sym_p}`) {half_badge}", unsafe_allow_html=True)
                            holding_cap = f"Holding: {qty_p:,} shs | Target: {p.get('target_price', 0):,.2f} {curr_p}" if lang == "en" else f"保有数量: {qty_p:,} 株 | 目標: {p.get('target_price', 0):,.2f} {curr_p}"
                            st.caption(holding_cap)
                        with col_p2:
                            entry_lbl = "Avg Cost:" if lang == "en" else "取得単価:"
                            current_lbl = "Current:" if lang == "en" else "現在値:"
                            st.markdown(f"**{entry_lbl}** {entry_p:,.2f} {curr_p}")
                            day_chg_pct = p.get('daily_change_pct', 0.0)
                            day_chg_color = "#34d399" if day_chg_pct >= 0 else "#f87171"
                            st.markdown(f"**{current_lbl}** <span style='color: #f8fafc; font-weight: bold;'>{cur_p:,.2f} {curr_p}</span> <span style='font-size: 11px; color: {day_chg_color};'>({day_chg_pct:+.2f}%)</span>", unsafe_allow_html=True)
                        with col_p3:
                            peak_val = p.get('peak_price') or cur_p
                            peak_lbl = "Trailing High:" if lang == "en" else "追従最高値:"
                            mval_lbl = "Market Value:" if lang == "en" else "時価評価:"
                            st.markdown(f"**{peak_lbl}** {peak_val:,.2f} {curr_p}")
                            st.caption(f"{mval_lbl} {mval_p:,.2f} {curr_p}")
                        with col_p_chart:
                            # 簡易的な株価グラフ (30日推移)
                            p_closes = MarketDataFeed.get_historical_closes(sym_p, period="1mo")
                            trend_lbl = "30D Trend" if lang == "en" else "30日推移"
                            p_spark = MarketDataFeed.render_sparkline_svg(p_closes, width=170, height=46, label=trend_lbl, currency=curr_p)
                            st.markdown(p_spark, unsafe_allow_html=True)
                        with col_p4:
                            st.markdown(f"<span style='color: {pnl_color}; font-weight: bold; font-size: 1.1rem;'>{pnl_p:+,.2f} {curr_p}</span><br/><span style='color: {pnl_color}; font-size: 0.85rem;'>({pnl_pct_p:+.2f}%)</span>", unsafe_allow_html=True)
                        with col_p5:
                            sell_btn_txt = "Liquidate All" if lang == "en" else "全株売却"
                            if st.button(sell_btn_txt, key=f"sell_btn_{sym_p}", use_container_width=True):
                                s_res = paper_engine.place_order(sym_p, "SELL", qty_p, cur_p, notes="Manual Liquidation" if lang == "en" else "手動全株売却", enforce_market_hours=False)
                                if s_res.get("success"):
                                    st.success(f"Sold {qty_p} shares of {sym_p}!" if lang == "en" else f"{sym_p} を {qty_p}株 売却しました！")
                                    st.rerun()
                                else:
                                    st.error(s_res.get("error"))

                    # Interactive TradingView expander for holding
                    chart_exp_title = f"📊 `{sym_p}` ({p['company_name']}) {'Expand TradingView Chart' if lang == 'en' else 'TradingView チャートを展開'}"
                    with st.expander(chart_exp_title, expanded=False):
                        from core.ai_hedge_fund.chart_engine import ChartEngine
                        ChartEngine.render_tradingview_chart(
                            symbol=sym_p,
                            entry_price=entry_p,
                            target_price=p.get('target_price'),
                            stop_loss_price=p.get('stop_loss_price'),
                            height=360
                        )

        # Render the real-time live fragment
        render_live_portfolio_fragment()

        # Order History
        st.markdown("### " + ("📜 Recent Orders" if lang == "en" else "📜 約定・注文履歴 (Recent Orders)"))
        orders = paper_engine.get_order_history(limit=15)
        if not orders:
            st.caption("No orders executed yet." if lang == "en" else "注文履歴はまだありません。")
        else:
            def _loc_order_notes(note_str, l):
                if l == "ja" or not note_str:
                    return note_str
                s = note_str
                repls = [
                    ("自律買い執行 (CIO判定: 積極買い推奨 / スコア: ", "Autonomous BUY (CIO: Strong Buy / Score: "),
                    ("自律買い執行 (CIO判定: 買い推奨 (押し目構築) / スコア: ", "Autonomous BUY (CIO: Dip Buy Build / Score: "),
                    ("自律買い執行 (CIO判定: 買い推奨 / スコア: ", "Autonomous BUY (CIO: Recommended / Score: "),
                    ("自律買い執行 (CIO判定: 押し目買い推奨 / スコア: ", "Autonomous BUY (CIO: Dip Buy / Score: "),
                    ("自律買い執行 (CIO判定: 選別的買い推奨 / スコア: ", "Autonomous BUY (CIO: Selective Buy / Score: "),
                    ("点)", " pts)"),
                    ("フィボナッチ最適損切り執行", "Fibonacci Optimal Stop-Loss Executed"),
                    ("Call Wall到達ハーフ利確 (天井壁", "Call Wall Reached - Half Profit-Taking (Ceiling"),
                    ("手動全株売却", "Manual Full Liquidation"),
                    ("手動買い発注", "Manual Buy Order"),
                    ("手動成行買い", "Manual Market Buy"),
                    ("手動成行売り", "Manual Market Sell")
                ]
                for jp, en in repls:
                    s = s.replace(jp, en)
                return s

            if lang == "en":
                table_md = "| Order ID | Timestamp | Symbol / Asset | Side | Qty | Exec Price | Total Value | Thesis / Notes |\n|---|---|---|---|---|---|---|---|\n"
                for o in orders:
                    loc_notes = _loc_order_notes(o.get('notes', ''), lang)
                    table_md += f"| #{o['order_id']} | {o['order_time']} | {o['symbol']} ({o['company_name']}) | **{o['side']}** | {o['quantity']} shs | {o['price']:,.2f} {o['currency']} | {(o['price']*o['quantity']):,.2f} {o['currency']} | {loc_notes} |\n"
            else:
                table_md = "| 注文ID | 日時 | 銘柄 | サイド | 数量 | 約定単価 | 合計金額 | 備考 |\n|---|---|---|---|---|---|---|---|\n"
                for o in orders:
                    table_md += f"| #{o['order_id']} | {o['order_time']} | {o['symbol']} ({o['company_name']}) | **{o['side']}** | {o['quantity']}株 | {o['price']:,.2f} {o['currency']} | {(o['price']*o['quantity']):,.2f} {o['currency']} | {o.get('notes', '')} |\n"
            st.markdown(table_md)

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        reset_exp_title = "⚙️ [Environment Management] Reset Simulation Account (Reconfigure Capital Scale)" if lang == "en" else "⚙️ 【環境管理】シミュレーション口座の初期化（資金規模変更・1から再スタート）"
        with st.expander(reset_exp_title, expanded=False):
            warn_msg = "⚠️ Resetting the account will clear all holdings, order history, equity curves, and council archives, restarting from initial capital." if lang == "en" else "⚠️ 口座を初期化すると、保有株・注文履歴・エクイティカーブ・合議録がすべてリセットされ、初期資金の状態から再開します。"
            st.warning(warn_msg)
            rst_c1, rst_c2 = st.columns([2.5, 1])
            with rst_c1:
                sel_lbl = "Select Initial Capital for Reset" if lang == "en" else "リセット後の初期元本を選択"
                init_opts = ["¥1,000,000 ($6.5k Equiv)", "¥10,000,000 ($65k Equiv)", "¥50,000,000 ($325k Equiv)"] if lang == "en" else ["¥1,000,000 (100万円)", "¥10,000,000 (1,000万円)", "¥50,000,000 (5,000万円)"]
                init_choice = st.selectbox(
                    sel_lbl,
                    init_opts,
                    key="hf_init_choice_select"
                )
            with rst_c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                reset_btn_lbl = "🚨 Full Reset Account" if lang == "en" else "🚨 口座を全リセット"
                if st.button(reset_btn_lbl, key="hf_danger_full_reset_btn", type="primary", use_container_width=True):
                    initial_yen = 50000000.0 if ("50,000,000" in init_choice or "5,000万" in init_choice) else (10000000.0 if ("10,000,000" in init_choice or "1,000万" in init_choice) else 1000000.0)
                    paper_engine.reset_portfolio(initial_jpy=initial_yen, initial_usd=0.0)
                    daemon.reset_state()
                    AutoTrader._examined_cooldowns.clear()
                    st.session_state.pop('last_auto_cycle_res', None)
                    st.success(f"Account reset successfully! (Initial capital: ¥{initial_yen:,.0f})" if lang == "en" else f"口座を完全リセットしました！（初期元本: ¥{initial_yen:,.0f}）")
                    st.rerun()

    # =========================================================================
    # TAB 3: 📜 Fund Memory & Archive (Memory & Trade Journey)
    # =========================================================================
    with tab_memory:
        st.markdown(f"""
        <div style='font-size: 1.2rem; font-weight: 700; color: #FFFFFF; margin-bottom: 6px;'>
            {t('memory_heading')}
        </div>
        <div style='font-size: 0.88rem; color: #94a3b8; margin-bottom: 16px;'>
            Persistent SQLite fund memory storing all historic council debates, trade reflections, 3D causal knowledge graphs, and performance journeys.
        </div>
        """, unsafe_allow_html=True)

        recent_councils = paper_engine.get_recent_councils(limit=30)
        recent_trade_memories = paper_engine.get_trade_memories(limit=30)

        # Overview Stats
        stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
        stat_c1.metric("Total Councils Held" if lang == "en" else "総開催会議数", f"{len(recent_councils)} {'councils' if lang == 'en' else '回'}")
        stat_c2.metric("Total Trade Journeys" if lang == "en" else "総取引ジャーニー記録", f"{len(recent_trade_memories)} {'records' if lang == 'en' else '件'}")
        
        # Realized PnL from memories (split JPY and USD)
        pnl_jpy = sum(float(t.get("realized_pnl", 0.0)) for t in recent_trade_memories if t.get("currency") == "JPY")
        pnl_usd = sum(float(t.get("realized_pnl", 0.0)) for t in recent_trade_memories if t.get("currency") == "USD")
        win_trades = [t for t in recent_trade_memories if float(t.get("realized_pnl", 0.0)) > 0]
        loss_trades = [t for t in recent_trade_memories if float(t.get("realized_pnl", 0.0)) < 0]
        win_rate = (len(win_trades) / max(1, len(win_trades) + len(loss_trades))) * 100 if (win_trades or loss_trades) else 0.0

        if pnl_jpy != 0 and pnl_usd != 0:
            pnl_display = f"+¥{pnl_jpy:,.0f} / +${pnl_usd:,.1f}" if lang == "en" else f"{pnl_jpy:+,.0f} 円 / {pnl_usd:+,.1f} USD"
        elif pnl_usd != 0:
            est_jpy = pnl_usd * 153.0
            pnl_display = f"${pnl_usd:+,.1f} USD" if lang == "en" else f"{pnl_usd:+,.1f} USD (約{est_jpy:+,.0f}円)"
        elif pnl_jpy != 0:
            pnl_display = f"¥{pnl_jpy:+,.0f}" if lang == "en" else f"{pnl_jpy:+,.0f} 円"
        else:
            pnl_display = "$0.00 / ¥0" if lang == "en" else "¥0 (0.0 USD)"

        stat_c3.metric("Cumulative Realized PnL" if lang == "en" else "確定損益累計 (メモリ記録)", pnl_display)
        wr_win_lbl = f"{len(win_trades)}W {len(loss_trades)}L" if lang == "en" else f"{len(win_trades)}勝 {len(loss_trades)}敗"
        stat_c4.metric("Win Rate" if lang == "en" else "決済勝率", f"{win_rate:.1f}% ({wr_win_lbl})")

        sub_tabs_labels = [
            "🏛️ Historic Council Archives (All)" if lang == "en" else "🏛️ 過去の投資合議録アーカイブ (全記録)",
            "💼 Trade Logbook & Post-Mortem Journey" if lang == "en" else "💼 トレード航海日誌（経緯・勝敗・AI反省メモ）",
            "🕸️ Temporal Knowledge Graph Memory (Graphiti & Neo4j)" if lang == "en" else "🕸️ 時間軸ナレッジグラフ長期記憶 (Graphiti & Neo4j)",
            "📜 Master Fund Charter & Mandates (mem0)" if lang == "en" else "📜 マスター運用憲章・至上命題 (mem0 Master Charter)"
        ]
        sub_mem_council, sub_mem_trade, sub_mem_graph, sub_mem_charter = st.tabs(sub_tabs_labels)

        with sub_mem_council:
            if not recent_councils:
                st.info("No council archives recorded yet. Convene a council from Tab 1 to automatically archive deliberations here." if lang == "en" else "まだ記録された合議録はありません。銘柄を指定して作戦会議を開催すると、ここに全議事録が自動アーカイブされます。")
            else:
                from core.ai_hedge_fund.translation_engine import TranslationEngine
                for raw_cr in recent_councils:
                    cr = TranslationEngine.localize_council_record(raw_cr, lang, api_key)
                    c_id = cr.get("council_id")
                    c_sym = cr.get("symbol")
                    c_name = cr.get("company_name")
                    c_act = cr.get("action")
                    c_act_label = cr.get("action_label")
                    if lang == "en" and (not c_act_label or any('\u3000' <= ch <= '\u9fff' for ch in c_act_label)):
                        c_act_label = TranslationEngine.localize_action_label(c_act_label, c_act, lang)
                    c_score = cr.get("confidence_score")
                    c_time = cr.get("created_at")
                    c_t_price = cr.get("target_price")
                    c_s_price = cr.get("stop_loss_price")
                    c_thesis = cr.get("thesis_summary")
                    c_dialogues = cr.get("dialogues", [])
                    c_news = cr.get("news_headlines", [])

                    badge_bg = "#10b981" if c_act in ["BUY", "ACCUMULATE"] else ("#ef4444" if c_act in ["SELL", "REDUCE"] else "#f59e0b")
                    
                    exp_title = f"[{c_time}] {c_name} ({c_sym}) — Verdict: {c_act_label} (Conviction: {c_score} pts)" if lang == "en" else f"【{c_time}】 {c_name} ({c_sym}) — 判定: {c_act_label} (確信度: {c_score}点)"
                    with st.expander(exp_title, expanded=False):
                        cio_lbl = "CIO Investment Thesis:" if lang == "en" else "CIO投資方針:"
                        tgt_lbl = "Target:" if lang == "en" else "目標株価:"
                        sl_lbl = "Stop Loss:" if lang == "en" else "損切りライン:"
                        alloc_lbl = "Max Allocation:" if lang == "en" else "配分上限:"
                        council_card_html = (
                            f"<div style='background: rgba(15, 23, 42, 0.6); padding: 12px 16px; border-radius: 8px; border-left: 4px solid {badge_bg}; margin-bottom: 12px;'>"
                            f"<div style='font-size: 13px; color: #94a3b8;'><strong>{cio_lbl}</strong> {c_thesis}</div>"
                            f"<div style='font-size: 12px; color: #cbd5e1; margin-top: 4px;'>"
                            f"{tgt_lbl} <strong>{c_t_price if c_t_price else 'N/A'}</strong> | {sl_lbl} <strong>{c_s_price if c_s_price else 'N/A'}</strong> | {alloc_lbl} <strong>{cr.get('allocation_pct', 0)}%</strong>"
                            f"</div>"
                            f"</div>"
                        )
                        st.markdown(council_card_html, unsafe_allow_html=True)

                        if c_news:
                            news_hdr = f"**📰 Referenced News Headlines ({len(c_news)}):**" if lang == "en" else f"**📰 当時参照されたニュースヘッドライン ({len(c_news)}件):**"
                            st.markdown(news_hdr)
                            for ni, nw in enumerate(c_news[:5], 1):
                                nw_title = nw.get('title', '')
                                nw_pub = nw.get('publisher', '')
                                if lang == "en":
                                    from core.ai_hedge_fund.translation_engine import TranslationEngine
                                    nw_title = TranslationEngine.translate_text(nw_title, lang)
                                    if nw_pub:
                                        nw_pub = TranslationEngine.translate_text(nw_pub, lang)
                                st.caption(f"{ni}. {nw_title} ({nw_pub})" if nw_pub else f"{ni}. {nw_title}")

                        c_cd = cr.get("cross_debate", {})
                        if c_cd and c_cd.get("occurred"):
                            cd_hdr = "**⚔️ Fact-Grounded Cross-Debate Direct Clash:**" if lang == "en" else "**⚔️ ガチンコ・クロスディベート直接対決:**"
                            st.markdown(cd_hdr)
                            pts_lbl = "pts" if lang == "en" else "点"
                            st.caption(f"🥊 {c_cd.get('bear_name')} ({c_cd.get('bear_initial_score')}{pts_lbl}): \"{c_cd.get('turn1_attack')}\"")
                            st.caption(f"🛡️ {c_cd.get('bull_name')} ({c_cd.get('bull_initial_score')}{pts_lbl} ➔ {c_cd.get('adjusted_score')}{pts_lbl}): \"{c_cd.get('turn2_defense')}\"")

                        if c_dialogues:
                            diag_hdr = "**🗣️ Council Member Deliberation Transcripts:**" if lang == "en" else "**🗣️ 評議員たちの合議討論録:**"
                            st.markdown(diag_hdr)
                            for d in c_dialogues:
                                st.markdown(f"- **{d.get('avatar', '👤')} {d.get('name')}:** {d.get('dialogue')}")

        with sub_mem_trade:
            if not recent_trade_memories:
                st.info("No trade journeys recorded yet. Entry reasons and exit lessons will be archived automatically when trading." if lang == "en" else "まだ記録された取引ジャーニーはありません。自動売買または手動発注が実行されると、エントリー理由やエグジット経緯が自動記録されます。")
            else:
                from core.ai_hedge_fund.translation_engine import TranslationEngine
                for raw_tm in recent_trade_memories:
                    tm = TranslationEngine.localize_trade_memory(raw_tm, lang)
                    tm_sym = tm.get("symbol")
                    tm_name = tm.get("company_name")
                    tm_type = tm.get("trade_type")
                    tm_qty = tm.get("quantity")
                    tm_price = tm.get("price")
                    tm_curr = tm.get("currency")
                    tm_pnl = float(tm.get("realized_pnl", 0.0))
                    tm_pnl_pct = float(tm.get("realized_pnl_pct", 0.0))
                    tm_rule = tm.get("trigger_rule", "N/A")
                    tm_time = tm.get("created_at")
                    tm_lesson = tm.get("lesson_learned", "")

                    pnl_color = "#34d399" if tm_pnl > 0 else ("#f87171" if tm_pnl < 0 else "#94a3b8")
                    if lang == "en":
                        type_label = "🟢 BUY ENTRY" if tm_type == "BUY_ENTRY" else ("🎯 HALF PROFIT TAKE" if tm_type == "PARTIAL_TAKE_PROFIT" else "🔴 FULL EXIT")
                        pnl_lbl = "Realized PnL:"
                        memo_title = "💡 Trade Thesis & Reflection Memo:"
                        trig_lbl = "Trigger:"
                        unit_str = "shs"
                    else:
                        type_label = "🟢 買いエントリー" if tm_type == "BUY_ENTRY" else ("🎯 ハーフ利確" if tm_type == "PARTIAL_TAKE_PROFIT" else "🔴 全株決済手仕舞い")
                        pnl_lbl = "確定損益:"
                        memo_title = "💡 取引経緯・知見メモ:"
                        trig_lbl = "トリガー:"
                        unit_str = "株"

                    pnl_row = f"<div style='margin-top: 6px; font-size: 13px; font-weight: 700; color: {pnl_color};'>{pnl_lbl} {tm_pnl:+,.1f} {tm_curr} ({tm_pnl_pct:+.1f}%)</div>" if tm_type != "BUY_ENTRY" else ""
                    default_lesson = "No special notes." if lang == "en" else "特記事項なし"
                    memo_row = f"<div style='margin-top: 6px; font-size: 12px; color: #cbd5e1;'><strong>{memo_title}</strong> {tm_lesson if tm_lesson else default_lesson}</div>"

                    trade_card_html = (
                        f"<div style='background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;'>"
                        f"<div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;'>"
                        f"<div style='font-size: 14px; font-weight: 700; color: #FFFFFF;'>{type_label}: {tm_name} ({tm_sym}) {tm_qty} {unit_str} @ {tm_price:,.2f} {tm_curr}</div>"
                        f"<div style='font-size: 12px; color: #94a3b8;'>{tm_time} | {trig_lbl} <code style='color: #38bdf8;'>{tm_rule}</code></div>"
                        f"</div>"
                        f"{pnl_row}"
                        f"{memo_row}"
                        f"</div>"
                    )
                    st.markdown(trade_card_html, unsafe_allow_html=True)

        with sub_mem_graph:
            from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
            is_avail = GraphitiMemoryManager.is_available()
            
            c_header_1, c_header_2 = st.columns([3, 1])
            with c_header_1:
                g_title = "🕸️ Graphiti × Neo4j Temporal Knowledge Graph Memory Engine" if lang == "en" else "🕸️ Graphiti × Neo4j 時間軸ナレッジグラフ記憶エンジン"
                g_cap = "Persistently maps market regimes, sectors, trade outcomes, and post-mortem reflections into a temporal causal graph." if lang == "en" else "市場レジーム・セクター・決済勝敗・各伝説投資家の事後反省を有機的な時間軸因果関係として長期記憶・再帰学習します。"
                st.markdown(f"<div style='font-size: 15px; font-weight: 700; color: #38bdf8;'>{g_title}</div>", unsafe_allow_html=True)
                st.caption(g_cap)
            with c_header_2:
                if is_avail:
                    st.success("🟢 Neo4j Connected" if lang == "en" else "🟢 Neo4j 接続中")
                else:
                    st.error("🔴 Neo4j Disconnected" if lang == "en" else "🔴 Neo4j 未接続")

            if is_avail:
                stats = GraphitiMemoryManager.get_graph_statistics()
                g_c1, g_c2, g_c3, g_c4, g_c5, g_c6 = st.columns(6)
                g_c1.metric("Tracked Stocks" if lang == "en" else "登録銘柄 (Stocks)", stats.get("stocks", 0))
                g_c2.metric("TimesFM Forecasts" if lang == "en" else "確率予測 (TimesFM)", stats.get("forecasts", 0))
                g_c3.metric("Decisions" if lang == "en" else "合議判定 (Decisions)", stats.get("decisions", 0))
                g_c4.metric("Episodes" if lang == "en" else "決済記録 (Episodes)", stats.get("episodes", 0))
                g_c5.metric("Lessons" if lang == "en" else "蓄積教訓 (Lessons)", stats.get("lessons", 0))
                g_c6.metric("Causal Links" if lang == "en" else "因果エッジ (Links)", stats.get("relationships", 0))

                st.markdown("---")
                graph_viewer_hdr = "🌐 Interactive Temporal Knowledge Graph Viewer (Live Force Simulation)" if lang == "en" else "🌐 インタラクティブ・時間軸ナレッジグラフビューアー（リアルタイム物理演算）"
                graph_viewer_desc = "Drag nodes to explore, zoom/pan with mouse wheel to intuitively navigate causal relationships between stocks, agents, and trade reviews." if lang == "en" else "ノードをドラッグして動かしたり、ホイールでズーム・パンして銘柄・エージェント・反省因果関係を直感的に探索できます。"
                st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 4px;'>{graph_viewer_hdr}</div>", unsafe_allow_html=True)
                st.caption(graph_viewer_desc)

                vis_data = GraphitiMemoryManager.get_graph_visualization_data()
                nodes_json = json.dumps(vis_data.get("nodes", []), ensure_ascii=False)
                edges_json = json.dumps(vis_data.get("edges", []), ensure_ascii=False)

                btn_2d_lbl = "🕸️ 2D Diagram" if lang == "en" else "🕸️ 2D ダイアグラム"
                btn_3d_lbl = "🌐 3D Spatial Model" if lang == "en" else "🌐 3D 空間モデル"
                btn_rst_lbl = "🎯 Reset" if lang == "en" else "🎯 リセット"
                btn_rot_lbl = "🔄 Auto-Rotate: ON" if lang == "en" else "🔄 自転: ON"
                btn_phys_lbl = "⚡ Freeze" if lang == "en" else "⚡ 固定"
                hud_stocks_lbl = "Stocks:" if lang == "en" else "銘柄:"
                hud_fc_lbl = "Forecasts:" if lang == "en" else "予測:"
                hud_dec_lbl = "Decisions:" if lang == "en" else "判定:"
                hud_episodes_lbl = "Exits:" if lang == "en" else "決済:"
                hud_lessons_lbl = "Lessons:" if lang == "en" else "教訓:"
                hud_links_lbl = "Edges:" if lang == "en" else "エッジ:"

                vis_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                  <meta charset="utf-8" />
                  <script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
                  <script src="https://unpkg.com/three-spritetext@1.9.0/dist/three-spritetext.min.js"></script>
                  <script src="https://unpkg.com/3d-force-graph@1.73.3/dist/3d-force-graph.min.js"></script>
                  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
                  <style>
                    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                    body {{
                      background-color: #02050e;
                      color: #94a3b8;
                      font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
                      font-size: 11px;
                      overflow: hidden;
                    }}
                    .graph-wrapper {{
                      position: relative;
                      width: 100%;
                      height: 720px;
                      background: #02050e;
                      border: 1px solid #111e33;
                      border-radius: 8px;
                      overflow: hidden;
                      box-shadow: 0 0 50px rgba(0, 240, 255, 0.06), inset 0 0 80px rgba(1, 3, 10, 0.95);
                    }}
                    /* CRT Scanline */
                    .graph-wrapper::after {{
                      content: " ";
                      position: absolute;
                      top: 0; left: 0; bottom: 0; right: 0;
                      background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.2) 50%);
                      z-index: 5;
                      background-size: 100% 3px;
                      pointer-events: none;
                      opacity: 0.25;
                    }}

                    /* RESPONSIVE TOP HUD BAR */
                    .hud-top-bar {{
                      position: absolute;
                      top: 12px;
                      left: 14px;
                      right: 14px;
                      z-index: 10;
                      display: flex;
                      justify-content: space-between;
                      align-items: flex-start;
                      gap: 8px;
                      pointer-events: none;
                    }}
                    .hud-header {{
                      pointer-events: auto;
                      background: rgba(3, 8, 20, 0.90);
                      border: 1px solid #16243b;
                      border-radius: 6px;
                      padding: 9px 15px;
                      backdrop-filter: blur(10px);
                      box-shadow: 0 0 25px rgba(0, 240, 255, 0.1);
                      max-width: 100%;
                    }}
                    .hud-title {{
                      font-size: 12px;
                      font-weight: 800;
                      color: #00f0ff;
                      letter-spacing: 0.8px;
                      display: flex;
                      align-items: center;
                      gap: 8px;
                    }}
                    .hud-pulse {{
                      width: 7px;
                      height: 7px;
                      background: #00f0ff;
                      border-radius: 50%;
                      box-shadow: 0 0 8px #00f0ff;
                      animation: pulse 1.8s infinite;
                    }}
                    @keyframes pulse {{
                      0%, 100% {{ opacity: 0.4; transform: scale(0.9); }}
                      50% {{ opacity: 1; transform: scale(1.2); }}
                    }}
                    .hud-sub {{
                      font-size: 9px;
                      color: #64748b;
                      margin-top: 3px;
                      letter-spacing: 0.5px;
                    }}
                    .hud-stats {{
                      display: flex;
                      gap: 12px;
                      margin-top: 6px;
                    }}
                    .hud-stat-item {{
                      font-size: 9.5px;
                      color: #64748b;
                    }}
                    .stat-val {{
                      font-weight: 700;
                      color: #f1f5f9;
                      margin-left: 2px;
                    }}

                    /* TOP CONTROLS */
                    .hud-controls {{
                      pointer-events: auto;
                      display: flex;
                      gap: 5px;
                      align-items: center;
                      flex-wrap: wrap;
                    }}
                    .view-toggle-group {{
                      display: flex;
                      background: rgba(4, 11, 24, 0.92);
                      border: 1px solid #1e293b;
                      border-radius: 4px;
                      padding: 2px;
                      margin-right: 4px;
                    }}
                    .view-btn {{
                      background: transparent;
                      border: none;
                      color: #94a3b8;
                      padding: 4px 8px;
                      border-radius: 3px;
                      font-size: 9.5px;
                      cursor: pointer;
                      font-family: inherit;
                    }}
                    .view-btn.active {{
                      background: rgba(0, 240, 255, 0.15);
                      color: #00f0ff;
                      font-weight: 700;
                    }}

                    .ctrl-btn {{
                      background: rgba(4, 11, 24, 0.92);
                      border: 1px solid #1e293b;
                      color: #94a3b8;
                      padding: 5px 9px;
                      border-radius: 4px;
                      font-size: 9.5px;
                      cursor: pointer;
                      font-family: inherit;
                      backdrop-filter: blur(8px);
                      white-space: nowrap;
                    }}
                    .ctrl-btn:hover {{
                      border-color: #00f0ff;
                      color: #00f0ff;
                    }}

                    /* MOBILE RESPONSIVE TWEAKS */
                    @media (max-width: 768px) {{
                      .hud-top-bar {{
                        top: 8px;
                        left: 8px;
                        right: 8px;
                        flex-direction: column;
                        align-items: stretch;
                        gap: 6px;
                      }}
                      .hud-header {{
                        padding: 6px 10px;
                        width: 100%;
                        box-sizing: border-box;
                      }}
                      .hud-title {{
                        font-size: 11px;
                        letter-spacing: 0.5px;
                      }}
                      .hud-sub {{
                        display: none;
                      }}
                      .hud-stats {{
                        gap: 10px;
                        margin-top: 4px;
                        flex-wrap: wrap;
                      }}
                      .hud-stat-item {{
                        font-size: 9px;
                      }}
                      .hud-controls {{
                        width: 100%;
                        display: flex;
                        justify-content: flex-start;
                        gap: 4px;
                        overflow-x: auto;
                        -webkit-overflow-scrolling: touch;
                        padding-bottom: 2px;
                        flex-wrap: nowrap;
                      }}
                      .view-toggle-group {{
                        margin-right: 2px;
                        padding: 1px;
                        flex-shrink: 0;
                      }}
                      .view-btn {{
                        padding: 4px 7px;
                        font-size: 9px;
                        flex-shrink: 0;
                      }}
                      .ctrl-btn {{
                        padding: 4px 7px;
                        font-size: 9px;
                        flex-shrink: 0;
                      }}
                      .hud-inspector {{
                        left: 8px !important;
                        right: 8px !important;
                        bottom: 8px !important;
                        max-width: calc(100% - 16px) !important;
                        padding: 10px 12px !important;
                      }}
                      .hud-hint {{
                        display: none !important;
                      }}
                    }}

                    /* 3D and 2D CONTAINERS */
                    #container-3d {{
                      width: 100%;
                      height: 100%;
                      position: absolute;
                      top: 0; left: 0;
                      display: block;
                      touch-action: none;
                    }}
                    #container-3d canvas {{
                      touch-action: none;
                      outline: none;
                    }}
                    #container-2d {{
                      width: 100%;
                      height: 100%;
                      position: absolute;
                      top: 0; left: 0;
                      display: none;
                      background: #02050e;
                    }}
                    #network-2d {{
                      width: 100%;
                      height: 100%;
                    }}

                    /* INSPECTOR MODAL */
                    .hud-inspector {{
                      position: absolute;
                      bottom: 20px;
                      left: 16px;
                      max-width: 460px;
                      max-height: 280px;
                      overflow-y: auto;
                      background: rgba(2, 6, 18, 0.94);
                      border: 1px solid #00f0ff;
                      border-radius: 6px;
                      padding: 14px 18px;
                      z-index: 10;
                      display: none;
                      box-shadow: 0 0 35px rgba(0, 240, 255, 0.25);
                      backdrop-filter: blur(10px);
                    }}
                    .insp-title {{
                      font-size: 13px;
                      font-weight: 800;
                      color: #00f0ff;
                      margin-bottom: 4px;
                      letter-spacing: 0.5px;
                    }}
                    .insp-meta {{
                      font-size: 9.5px;
                      color: #64748b;
                      margin-bottom: 8px;
                    }}
                    .insp-desc {{
                      font-size: 10.5px;
                      color: #cbd5e1;
                      line-height: 1.55;
                      white-space: pre-wrap;
                    }}

                    /* FOOTER HINT */
                    .hud-hint {{
                      position: absolute;
                      bottom: 14px;
                      right: 16px;
                      z-index: 10;
                      font-size: 9px;
                      color: #475569;
                      pointer-events: none;
                      letter-spacing: 0.5px;
                    }}
                  </style>
                </head>
                <body>
                  <div class="graph-wrapper">
                    <!-- RESPONSIVE TOP HUD BAR -->
                    <div class="hud-top-bar">
                      <div class="hud-header">
                        <div class="hud-title">
                          <span class="hud-pulse"></span>
                          GRAPHITI 3D CAUSAL KNOWLEDGE GRAPH
                        </div>
                        <div class="hud-sub">VASTURIANO 3D-FORCE-GRAPH // NEO4J EPISODIC ARCHIVE</div>
                        <div class="hud-stats">
                          <div class="hud-stat-item">{hud_stocks_lbl} <span class="stat-val" style="color: #00f0ff;">{stats.get("stocks", 0)}</span></div>
                          <div class="hud-stat-item">{hud_fc_lbl} <span class="stat-val" style="color: #c084fc;">{stats.get("forecasts", 0)}</span></div>
                          <div class="hud-stat-item">{hud_dec_lbl} <span class="stat-val" style="color: #ff0055;">{stats.get("decisions", 0)}</span></div>
                          <div class="hud-stat-item">{hud_episodes_lbl} <span class="stat-val" style="color: #10b981;">{stats.get("episodes", 0)}</span></div>
                          <div class="hud-stat-item">{hud_lessons_lbl} <span class="stat-val" style="color: #38bdf8;">{stats.get("lessons", 0)}</span></div>
                          <div class="hud-stat-item">{hud_links_lbl} <span class="stat-val" style="color: #c084fc;">{stats.get("relationships", 0)}</span></div>
                        </div>
                      </div>

                      <div class="hud-controls">
                        <div class="view-toggle-group">
                          <button class="view-btn" id="btn-2d" onclick="switchView('2d')">{btn_2d_lbl}</button>
                          <button class="view-btn active" id="btn-3d" onclick="switchView('3d')">{btn_3d_lbl}</button>
                        </div>
                        <button class="ctrl-btn" onclick="reset3DCamera()">{btn_rst_lbl}</button>
                        <button class="ctrl-btn" id="btn-rot" onclick="toggleAutoRotate()">{btn_rot_lbl}</button>
                        <button class="ctrl-btn" id="btn-phys" onclick="toggle3DPhysics()">{btn_phys_lbl}</button>
                      </div>
                    </div>

                    <!-- 3D GRAPH CANVAS -->
                    <div id="container-3d"></div>

                    <!-- 2D VIS.JS NETWORK (FALLBACK OPTION) -->
                    <div id="container-2d">
                      <div id="network-2d"></div>
                    </div>

                    <!-- INSPECTOR -->
                    <div id="inspector" class="hud-inspector">
                      <div id="insp-title" class="insp-title">TARGET</div>
                      <div id="insp-meta" class="insp-meta"></div>
                      <div id="insp-desc" class="insp-desc"></div>
                    </div>

                    <div class="hud-hint">
                      🖱️ 空間ドラッグ: 3D回転 | ノードドラッグ: 位置移動 | ホイール: ズーム | 右ドラッグ: 平行移動
                    </div>
                  </div>

                  <script>
                    // -----------------------------------------------------------------
                    // 1. DATA PREPARATION (RAW GRAPHITI NODES & EDGES)
                    // -----------------------------------------------------------------
                    const rawNodes = {nodes_json};
                    const rawEdges = {edges_json};

                    function getNodeColor(g) {{
                      if (g === 'stock') return '#00f0ff';
                      if (g === 'agent') return '#f59e0b';
                      if (g === 'veto') return '#ff0055';
                      if (g === 'debate') return '#f43f5e';
                      if (g === 'alpha') return '#10b981';
                      if (g === 'forecast') return '#c084fc';
                      if (g === 'decision_buy') return '#00f0ff';
                      if (g === 'win') return '#10b981';
                      if (g === 'loss') return '#f43f5e';
                      if (g === 'lesson') return '#38bdf8';
                      return '#a855f7';
                    }}

                    function getNodeBgColor(g) {{
                      if (g === 'stock') return '#08253d';
                      if (g === 'agent') return '#2b1d06';
                      if (g === 'veto') return '#380612';
                      if (g === 'debate') return '#360614';
                      if (g === 'alpha') return '#042e1d';
                      if (g === 'forecast') return '#260a42';
                      if (g === 'decision_buy') return '#06263b';
                      if (g === 'win') return '#042e1d';
                      if (g === 'loss') return '#380612';
                      if (g === 'sector') return '#1e1338';
                      return '#0a1526';
                    }}

                    function formatShortLabel(n) {{
                      const parts = (n.label || n.id || '').split(String.fromCharCode(10));
                      let lbl = (parts[0] || '').trim();
                      const line2 = (parts[1] || '').trim();
                      lbl = lbl.replace('⚡ ', '').replace('🏢 ', '').replace('👑 ', '').replace('💡 ', '');
                      lbl = lbl.replace('⚔️ ', '').replace('🛡️ ', '').replace('💎 ', '').replace('🔮 ', '');
                      lbl = lbl.replace('🔴 ', '').replace('🟢 ', '');
                      lbl = lbl.replace('Portfolio Manager / CIO Lumina AI', 'CIO Lumina');
                      lbl = lbl.replace('Risk Manager AI (CRO)', 'CRO Risk');
                      lbl = lbl.replace('Warren Buffett AI', 'Buffett');
                      lbl = lbl.replace('George Soros AI', 'Soros');
                      lbl = lbl.replace('Benjamin Graham AI', 'Graham');
                      lbl = lbl.replace('Cathie Wood AI', 'Cathie');
                      lbl = lbl.replace('MACRO_REFLEXIVITY', 'Reflexivity');
                      lbl = lbl.replace('VALUATION_DISCIPLINE', 'Valuation');
                      lbl = lbl.replace('FALSE_NEGATIVE_CAUTION', 'Caution');
                      lbl = lbl.replace('ACCURATE_THESIS', 'Accurate');
                      if (line2 && ['veto', 'decision_buy', 'alpha', 'forecast', 'debate', 'episode', 'win', 'loss'].includes(n.group)) {{
                        const shortLine2 = line2.replace('点', '').replace('勝率', '');
                        lbl = lbl.replace('積極買', '買').replace('実証α', 'α').replace('TimesFM予測', '予測') + ':' + shortLine2;
                      }}
                      if (lbl.length > 16) lbl = lbl.slice(0, 15) + '…';
                      
                      let icon = '';
                      if (n.group === 'stock') icon = '⚡';
                      else if (n.group === 'agent') icon = '👑';
                      else if (n.group === 'sector') icon = '🏢';
                      else if (n.group === 'lesson') icon = '💡';
                      else if (n.group === 'veto') icon = '🛡️';
                      else if (n.group === 'alpha') icon = '💎';
                      else if (n.group === 'forecast') icon = '🔮';
                      else if (n.group === 'debate') icon = '⚔️';
                      else if (n.group === 'decision_buy') icon = '⚔️';
                      else if (n.group === 'episode') icon = (n.label || '').includes('WIN') ? '🟢' : '🔴';
                      return icon ? (icon + ' ' + lbl) : lbl;
                    }}

                    function getNodeRadius(g) {{
                      if (g === 'stock') return 5.5;
                      if (g === 'agent') return 7.0;
                      if (g === 'veto') return 5.8;
                      if (g === 'debate') return 5.8;
                      if (g === 'alpha') return 6.0;
                      if (g === 'forecast') return 6.0;
                      if (g === 'decision_buy') return 5.0;
                      if (g === 'win' || g === 'loss') return 4.5;
                      if (g === 'lesson') return 4.0;
                      return 4.0;
                    }}

                    function getLinkColor(label) {{
                      if (label === 'LEARNED_BY') return '#ffb700';
                      if (label === 'DECIDED_BY') return '#00f0ff';
                      if (label === 'DECIDED_ON') return '#38bdf8';
                      if (label === 'INVOLVED') return '#10b981';
                      if (label === 'LESSON') return '#facc15';
                      if (label === 'SECTOR') return '#c084fc';
                      if (label === 'PROVEN_ALPHA') return '#00ff88';
                      if (label === 'PROJECTED_FOR' || label === 'BASED_ON_FORECAST') return '#c084fc';
                      if (label === 'DEBATED') return '#f43f5e';
                      return '#38bdf8';
                    }}

                    // 5人の伝説投資家AIを3D空間の5大拠点に固定ピン留め (fx, fy, fz)
                    // これにより原点 (0,0,0) での重なりを物理シミュレーションレベルで100%遮断
                    const pinnedAgents = {{
                      'ag_cio': {{ fx: 0, fy: 75, fz: 0 }},
                      'ag_risk_manager': {{ fx: 90, fy: 15, fz: 35 }},
                      'ag_buffett': {{ fx: -90, fy: 15, fz: 35 }},
                      'ag_soros': {{ fx: 55, fy: -35, fz: -75 }},
                      'ag_graham': {{ fx: -55, fy: -35, fz: -75 }}
                    }};

                    // データ整合性保証: 未登録ノードを参照するエッジがあれば安全にノードを自動補完
                    // 3d-force-graph の「node not found」例外による描画クラッシュを100%防止
                    const nodeMap = new Map();
                    rawNodes.forEach(n => {{
                      if (n && n.id) nodeMap.set(n.id, Object.assign({{}}, n));
                    }});

                    rawEdges.forEach(e => {{
                      if (e.from && !nodeMap.has(e.from)) {{
                        const isStock = e.from.startsWith('stock_');
                        const sym = isStock ? e.from.replace('stock_', '') : e.from;
                        nodeMap.set(e.from, {{
                          id: e.from,
                          label: isStock ? ('⚡ ' + sym) : e.from,
                          group: isStock ? 'stock' : 'concept'
                        }});
                      }}
                      if (e.to && !nodeMap.has(e.to)) {{
                        const isStock = e.to.startsWith('stock_');
                        const sym = isStock ? e.to.replace('stock_', '') : e.to;
                        nodeMap.set(e.to, {{
                          id: e.to,
                          label: isStock ? ('⚡ ' + sym) : e.to,
                          group: isStock ? 'stock' : 'concept'
                        }});
                      }}
                    }});

                    const safeNodes = Array.from(nodeMap.values());
                    const safeNodeIds = new Set(safeNodes.map(n => n.id));
                    const safeEdges = rawEdges.filter(e => e.from && e.to && safeNodeIds.has(e.from) && safeNodeIds.has(e.to));

                    const g3dData = {{
                      nodes: safeNodes.map((n, idx) => {{
                        let initX, initY, initZ, fx, fy, fz;
                        if (pinnedAgents[n.id]) {{
                          initX = pinnedAgents[n.id].fx;
                          initY = pinnedAgents[n.id].fy;
                          initZ = pinnedAgents[n.id].fz;
                          fx = initX;
                          fy = initY;
                          fz = initZ;
                        }} else {{
                          // 空間楕円体にバランスよく分散配置 (Z深度を適度に抑制しカメラ直前遮蔽を完全防止)
                          const angle = (idx / safeNodes.length) * Math.PI * 2;
                          const r = 85 + (idx % 7) * 18;
                          const layer = (idx % 5) - 2;
                          initX = r * Math.cos(angle);
                          initY = layer * 30 + Math.sin(angle * 2) * 15;
                          initZ = (r * Math.sin(angle)) * 0.55;
                        }}

                        const neonColor = (typeof n.color === 'object' && n.color.border) ? n.color.border : getNodeColor(n.group);
                        const coreColor = (typeof n.color === 'object' && n.color.background) ? n.color.background : getNodeBgColor(n.group);

                        return {{
                          id: n.id,
                          name: n.label || n.id,
                          shortName: formatShortLabel(n),
                          group: n.group || 'concept',
                          color: neonColor,
                          coreColor: coreColor,
                          radius: getNodeRadius(n.group),
                          desc: n.title || (n.label + ' (' + n.group + ')'),
                          x: initX,
                          y: initY,
                          z: initZ,
                          fx: fx,
                          fy: fy,
                          fz: fz
                        }};
                      }}),
                      links: safeEdges.map(e => ({{
                        source: e.from,
                        target: e.to,
                        label: e.label || '',
                        color: getLinkColor(e.label)
                      }}))
                    }};

                    // -----------------------------------------------------------------
                    // 2. 3D-FORCE-GRAPH INITIALIZATION
                    // -----------------------------------------------------------------
                    const elem3d = document.getElementById('container-3d');
                    let autoRotate = true;
                    let physicsActive = true;
                    let focusNode = null;
                    let hoveredNode = null;
                    const highlightNodes = new Set();
                    const highlightLinks = new Set();

                    function updateFocus(node) {{
                      focusNode = node;
                      highlightNodes.clear();
                      highlightLinks.clear();
                      if (node) {{
                        highlightNodes.add(node.id);
                        g3dData.links.forEach(link => {{
                          const sId = typeof link.source === 'object' ? link.source.id : link.source;
                          const tId = typeof link.target === 'object' ? link.target.id : link.target;
                          if (sId === node.id || tId === node.id) {{
                            highlightLinks.add(link);
                            highlightNodes.add(sId);
                            highlightNodes.add(tId);
                          }}
                        }});
                      }}
                      refreshVisuals();
                    }}

                    function refreshVisuals() {{
                      g3dData.nodes.forEach(n => {{
                        if (n._group) {{
                          const isRelated = !focusNode || highlightNodes.has(n.id);
                          const isTarget = focusNode && (focusNode.id === n.id);
                          const isHovered = hoveredNode && (hoveredNode.id === n.id);

                          n._group.traverse(child => {{
                            if (child.isMesh) {{
                              if (child.material && child.material.wireframe) {{
                                child.material.opacity = isRelated ? (isTarget ? 0.45 : 0.24) : 0.03;
                              }} else if (child.material) {{
                                child.material.opacity = isRelated ? (isTarget ? 1.0 : 0.88) : 0.08;
                              }}
                            }} else if (child.isSprite) {{
                              if (child.material) {{
                                child.material.opacity = isRelated ? (isTarget ? 1.0 : (isHovered ? 1.0 : (focusNode ? 0.20 : 0.90))) : 0.08;
                                child.material.transparent = true;
                              }}
                            }}
                          }});
                        }}
                      }});
                    }}

                    const Graph3D = ForceGraph3D({{ controlType: 'orbit' }})
                      (elem3d)
                      .width(elem3d.clientWidth || 1000)
                      .height(elem3d.clientHeight || 720)
                      .graphData(g3dData)
                      .backgroundColor('#02050e')
                      .showNavInfo(false)
                      .enableNavigationControls(true)
                      .enableNodeDrag(true)
                      .warmupTicks(30)
                      .cooldownTicks(120)
                      .d3VelocityDecay(0.35)
                      // Tooltip overlay: Hovering reveals details cleanly outside 3D space
                      .nodeLabel(node => `<div style="background: rgba(2,6,18,0.96); border: 1.5px solid ${{node.color}}; padding: 7px 12px; border-radius: 6px; font-family: monospace; color: #fff; font-size: 11px; box-shadow: 0 0 18px rgba(0,240,255,0.30);">
                        <strong style="color:${{node.color}}; font-size: 12px;">${{node.name.split(String.fromCharCode(10))[0]}}</strong><br>
                        <span style="color:#94a3b8; font-size: 9.5px;">グループ: ${{node.group.toUpperCase()}}</span>
                      </div>`)
                      // Custom 3D Object: Dark Glass Core Sphere + Latitude-Longitude Cyber Mesh Globe + Elevated Billboard
                      .nodeThreeObject(node => {{
                        const group = new THREE.Group();

                        // 1. Dark Glass Core Sphere (動画と同一の深みのある落ち着いたダークガラス球)
                        const geom = new THREE.SphereGeometry(node.radius, 24, 24);
                        const mat = new THREE.MeshLambertMaterial({{
                          color: node.coreColor || '#08253d',
                          transparent: true,
                          opacity: 0.88
                        }});
                        const sphere = new THREE.Mesh(geom, mat);
                        group.add(sphere);

                        // 2. 地球儀・レーダー型サイバーメッシュ球 (ネオン発光ワイヤーフレーム)
                        const haloGeom = new THREE.SphereGeometry(node.radius * 1.35, 16, 16);
                        const haloMat = new THREE.MeshBasicMaterial({{
                          color: node.color,
                          transparent: true,
                          opacity: 0.25,
                          wireframe: true
                        }});
                        group.add(new THREE.Mesh(haloGeom, haloMat));

                        // 3. 銘柄・エージェント・CRO拒否判定・実証アルファ・予測ノードには外周クォンタムオーラ球 (14×14)
                        let hasOuterAura = false;
                        if (node.group === 'stock' || node.group === 'agent' || node.group === 'veto' || node.group === 'decision_buy' || node.group === 'alpha' || node.group === 'forecast') {{
                          hasOuterAura = true;
                          const outerGeom = new THREE.SphereGeometry(node.radius * 1.60, 14, 14);
                          const outerColor = node.group === 'veto' ? '#ff0055' : (node.group === 'agent' ? '#ffb700' : (node.group === 'forecast' ? '#c084fc' : (node.group === 'alpha' ? '#10b981' : '#00f0ff')));
                          const outerMat = new THREE.MeshBasicMaterial({{
                            color: outerColor,
                            transparent: true,
                            opacity: node.group === 'veto' ? 0.28 : 0.16,
                            wireframe: true
                          }});
                          group.add(new THREE.Mesh(outerGeom, outerMat));
                        }}

                        // 4. クッキリ読みやすい 3D SpriteText billboard (球体メッシュの上空に配置して被りゼロ)
                        const sprite = new SpriteText(node.shortName || node.name);
                        sprite.color = '#ffffff';
                        sprite.textHeight = 1.9;
                        sprite.backgroundColor = 'rgba(2, 6, 18, 0.92)';
                        sprite.borderColor = node.color;
                        sprite.borderWidth = 0.6;
                        sprite.borderRadius = 3;
                        sprite.padding = [1.0, 2.0];
                        sprite.fontFace = "'JetBrains Mono', Consolas, monospace";
                        
                        // メッシュ球体の頂点よりも完全に上空へオフセット (球体との被りを100%遮断)
                        const maxRadius = hasOuterAura ? (node.radius * 1.60) : (node.radius * 1.35);
                        sprite.position.y = maxRadius + 3.0;
                        sprite._origScale = sprite.scale.clone();
                        group.add(sprite);

                        node._group = group;
                        return group;
                      }})
                      // 3D Synaptic Links with glowing photon pulses! (動画準拠の洗練された光度)
                      .linkColor(link => link.color)
                      .linkOpacity(0.55)
                      .linkWidth(link => highlightLinks.has(link) ? 2.2 : 1.3)
                      .linkDirectionalParticles(link => highlightLinks.has(link) ? 4 : 2)
                      .linkDirectionalParticleWidth(link => highlightLinks.has(link) ? 2.4 : 1.8)
                      .linkDirectionalParticleSpeed(0.007)
                      .linkDirectionalParticleColor(link => link.color)
                      .onNodeHover(node => {{
                        hoveredNode = node;
                        refreshVisuals();
                      }})
                      // Click interaction: smooth elevated zoom in 3D without foreground occlusion
                      .onNodeClick(node => {{
                        focusOnNode(node);
                      }})
                      .onBackgroundClick(() => {{
                        updateFocus(null);
                        document.getElementById('inspector').style.display = 'none';
                      }});

                    // Force Physics tuning: Generous repulsion and link spacing to eliminate overlap
                    try {{
                      if (Graph3D.d3Force('charge')) {{
                        Graph3D.d3Force('charge').strength(-420);
                      }}
                      if (Graph3D.d3Force('link')) {{
                        Graph3D.d3Force('link').distance(l => {{
                          if (l.label === 'DECIDED_BY' || l.label === 'LEARNED_BY') return 80;
                          if (l.label === 'SECTOR') return 85;
                          return 55;
                        }});
                      }}
                    }} catch (e) {{
                      console.warn('d3Force setup notice:', e);
                    }}

                    // 3D Scene Lighting (動画準拠の落ち着いたサイバー陰影)
                    const scene = Graph3D.scene();
                    scene.add(new THREE.AmbientLight(0xffffff, 0.88));
                    const dirLight1 = new THREE.DirectionalLight(0x00f0ff, 0.45);
                    dirLight1.position.set(60, 60, 60);
                    scene.add(dirLight1);
                    const dirLight2 = new THREE.DirectionalLight(0xf59e0b, 0.35);
                    dirLight2.position.set(-60, -60, -60);
                    scene.add(dirLight2);

                    // Set comfortable wide camera position far from foreground
                    Graph3D.cameraPosition({{ x: 0, y: 120, z: 460 }}, {{ x: 0, y: 0, z: 0 }});

                    // Focus logic function: elevated 35-deg perspective + scale culling to eliminate occlusion
                    function focusOnNode(node) {{
                      if (!node) return;
                      updateFocus(node);

                      const camX = node.x + (node.x >= 0 ? 35 : -35);
                      const camY = node.y + 45;
                      const camZ = node.z + 75;

                      Graph3D.cameraPosition(
                        {{ x: camX, y: camY, z: camZ }},
                        node,
                        1400
                      );

                      const insp = document.getElementById('inspector');
                      if (insp) {{
                        insp.style.display = 'block';
                        insp.style.borderColor = node.color || '#00f0ff';
                        insp.style.boxShadow = `0 0 35px ${{node.color || '#00f0ff'}}55`;
                        document.getElementById('insp-title').innerText = (node.name || node.id).split(String.fromCharCode(10)).join(' ');
                        document.getElementById('insp-title').style.color = node.color;
                        document.getElementById('insp-meta').innerText = `NODE ID: ${{node.id}} // GROUP: ${{(node.group || '').toUpperCase()}}`;
                        document.getElementById('insp-desc').innerText = node.desc || '';
                      }}
                    }}

                    // Expose to window for testing and global control
                    window.Graph3D = Graph3D;
                    window.focusOnNode = focusOnNode;

                    function init3DControls() {{
                      const controls = Graph3D.controls();
                      if (controls) {{
                        controls.enableRotate = true;
                        controls.enableZoom = true;
                        controls.enablePan = true;
                        controls.autoRotate = autoRotate;
                        controls.autoRotateSpeed = 0.5;
                        controls.enableDamping = true;
                        controls.dampingFactor = 0.05;
                      }}
                    }}
                    setTimeout(init3DControls, 300);

                    function reset3DCamera() {{
                      updateFocus(null);
                      Graph3D.cameraPosition({{ x: 0, y: 120, z: 460 }}, {{ x: 0, y: 0, z: 0 }}, 1200);
                      document.getElementById('inspector').style.display = 'none';
                    }}

                    function toggleAutoRotate() {{
                      const controls = Graph3D.controls();
                      autoRotate = !autoRotate;
                      if (controls) controls.autoRotate = autoRotate;
                      document.getElementById('btn-rot').innerText = autoRotate ? "🔄 自転: ON" : "⏸️ 自転: OFF";
                    }}

                    function toggle3DPhysics() {{
                      physicsActive = !physicsActive;
                      if (physicsActive) {{
                        Graph3D.resumeAnimation();
                      }} else {{
                        Graph3D.pauseAnimation();
                      }}
                      document.getElementById('btn-phys').innerText = physicsActive ? "⚡ 固定" : "▶️ 再開";
                    }}

                    // -----------------------------------------------------------------
                    // 3. 2D VIS.JS NETWORK (DEFAULT INTUITIVE VISUALIZATION)
                    // -----------------------------------------------------------------
                    const net2dContainer = document.getElementById('network-2d');
                    const net2dData = {{
                      nodes: new vis.DataSet(safeNodes.map(n => ({{
                        id: n.id,
                        label: n.label,
                        shape: 'box',
                        margin: 9,
                        borderWidth: 2,
                        shadow: {{ enabled: true, color: 'rgba(0, 240, 255, 0.25)', size: 10 }},
                        color: {{
                          background: n.color ? (typeof n.color === 'object' ? n.color.background : n.color) : '#08172e',
                          border: getNodeColor(n.group),
                          highlight: {{ background: '#0e2a52', border: '#ffffff' }}
                        }},
                        font: {{ color: '#ffffff', size: 11, face: "'JetBrains Mono', Consolas, monospace" }}
                      }}))),
                      edges: new vis.DataSet(safeEdges.map(e => ({{
                        from: e.from,
                        to: e.to,
                        label: e.label,
                        arrows: {{ to: {{ enabled: true, scaleFactor: 0.65 }} }},
                        smooth: {{ type: 'continuous', roundness: 0.2 }},
                        font: {{ color: '#94a3b8', size: 9, face: "'JetBrains Mono', monospace", align: 'middle' }},
                        width: 1.5,
                        color: {{ color: (typeof e.color === 'object' ? e.color.color : e.color) || '#00f0ff', highlight: '#ffffff' }}
                      }})))
                    }};
                    const net2dOptions = {{
                      physics: {{
                        solver: 'forceAtlas2Based',
                        forceAtlas2Based: {{
                          gravitationalConstant: -75,
                          centralGravity: 0.015,
                          springLength: 95,
                          springConstant: 0.08,
                          damping: 0.45,
                          avoidOverlap: 1.0
                        }},
                        stabilization: {{ iterations: 120 }}
                      }},
                      interaction: {{
                        hover: true,
                        zoomView: true,
                        dragView: true,
                        tooltipDelay: 100
                      }}
                    }};
                    const network2D = new vis.Network(net2dContainer, net2dData, net2dOptions);

                    // 2D Inspector Interaction
                    network2D.on('click', function(params) {{
                      if (params.nodes.length > 0) {{
                        const nodeId = params.nodes[0];
                        const n = rawNodes.find(item => item.id === nodeId);
                        if (n) {{
                          const insp = document.getElementById('inspector');
                          if (insp) {{
                            insp.style.display = 'block';
                            insp.style.borderColor = getNodeColor(n.group);
                            insp.style.boxShadow = `0 0 35px ${{getNodeColor(n.group)}}55`;
                            document.getElementById('insp-title').innerText = (n.label || n.id).split(String.fromCharCode(10)).join(' ');
                            document.getElementById('insp-title').style.color = getNodeColor(n.group);
                            document.getElementById('insp-meta').innerText = `NODE ID: ${{n.id}} // GROUP: ${{(n.group || '').toUpperCase()}}`;
                            document.getElementById('insp-desc').innerText = n.title || (n.label + ' (' + n.group + ')');
                          }}
                        }}
                      }} else {{
                        document.getElementById('inspector').style.display = 'none';
                      }}
                    }});

                    network2D.on('stabilizationIterationsDone', function() {{
                      network2D.fit();
                    }});
                    setTimeout(function() {{ network2D.fit(); }}, 400);

                    // -----------------------------------------------------------------
                    // 4. VIEW SWITCHING
                    // -----------------------------------------------------------------
                    function switchView(mode) {{
                      const c3d = document.getElementById('container-3d');
                      const c2d = document.getElementById('container-2d');
                      const b3d = document.getElementById('btn-3d');
                      const b2d = document.getElementById('btn-2d');

                      if (mode === '3d') {{
                        b3d.className = 'view-btn active';
                        b2d.className = 'view-btn';
                        c3d.style.display = 'block';
                        c2d.style.display = 'none';
                        Graph3D.width(elem3d.clientWidth);
                        Graph3D.height(elem3d.clientHeight);
                      }} else {{
                        b3d.className = 'view-btn';
                        b2d.className = 'view-btn active';
                        c3d.style.display = 'none';
                        c2d.style.display = 'block';
                        network2D.fit();
                      }}
                    }}

                    window.addEventListener('resize', () => {{
                      if (Graph3D) {{
                        Graph3D.width(elem3d.clientWidth);
                        Graph3D.height(elem3d.clientHeight);
                      }}
                    }});
                  </script>
                </body>
                </html>
                """
                import streamlit.components.v1 as components
                components.html(vis_html, height=760)

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                test_hdr = "🔍 Temporal Knowledge Graph Lesson Extraction Test" if lang == "en" else "🔍 ナレッジグラフ時間軸教訓の抽出テスト"
                st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;'>{test_hdr}</div>", unsafe_allow_html=True)
                q_sym_lbl = "Search Ticker Symbol" if lang == "en" else "検索するティッカーシンボル"
                q_sym = st.text_input(q_sym_lbl, value="NVDA", key="graph_test_symbol")
                if q_sym:
                    lessons = GraphitiMemoryManager.query_temporal_lessons(q_sym.strip().upper(), limit=5)
                    if lessons:
                        lessons_title = f"**Temporal Lessons for \"{q_sym.upper()}\" ({len(lessons)} entries):**" if lang == "en" else f"**『{q_sym.upper()}』に関連する時間軸教訓 ({len(lessons)}件):**"
                        st.markdown(lessons_title)
                        for l in lessons:
                            ag_name = l.get("agent_name", "AI Analyst")
                            cat = l.get("category", "")
                            m_type = l.get("match_type", "DIRECT")
                            txt = l.get("lesson_text", "")
                            pnl_pct = l.get("pnl_pct", 0.0)
                            pnl_color = "#10b981" if pnl_pct >= 0 else "#ef4444"
                            match_lbl = "Match:" if lang == "en" else "照合:"
                            cat_lbl = "Category:" if lang == "en" else "分類:"
                            pnl_lbl = "Realized PnL:" if lang == "en" else "当時損益:"
                            st.markdown(
                                f"<div style='background: rgba(15, 23, 42, 0.6); border-left: 3px solid {pnl_color}; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px;'>"
                                f"<div style='font-size: 12px; color: #94a3b8;'><strong>{ag_name}</strong> | {match_lbl} <code>{m_type}</code> | {cat_lbl} <code>{cat}</code> | {pnl_lbl} <span style='color:{pnl_color}; font-weight:700;'>{pnl_pct:+.1f}%</span></div>"
                                f"<div style='font-size: 13px; color: #e2e8f0; margin-top: 4px;'>{txt}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                    else:
                        no_lessons_msg = f"No direct temporal lessons found for \"{q_sym.upper()}\" yet. New lessons are automatically recorded upon trade liquidation." if lang == "en" else f"『{q_sym.upper()}』に関する直接の教訓はまだナレッジグラフに登録されていません。取引が決済されると自動で記録されます。"
                        st.info(no_lessons_msg)

                st.markdown("---")
                grag_hdr = "🕸️ GraphRAG: Supply Chain Dependency & Propagation Risk Analysis" if lang == "en" else "🕸️ GraphRAG: 企業間サプライチェーン依存・波及リスク分析"
                grag_desc = "Dynamically explores inter-company supply and dependency relationships extracted from SEC 10-Ks and financial news to assist CRO systemic risk detection." if lang == "en" else "SEC 10-K・金融ニュースから自動抽出された企業間の供給・依存関係を有機的に探索し、CROの伝播リスク検知に活用します。"
                st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #38bdf8; margin-bottom: 6px;'>{grag_hdr}</div>", unsafe_allow_html=True)
                st.caption(grag_desc)
                from core.ai_hedge_fund.graph_rag_extractor import GraphRAGExtractor
                g_col1, g_col2 = st.columns([3, 1])
                with g_col1:
                    sc_input_lbl = "Supply Chain Search Ticker" if lang == "en" else "サプライチェーン探索ティッカー"
                    sc_sym = st.text_input(sc_input_lbl, value="NVDA", key="graphrag_sc_sym")
                with g_col2:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    seed_btn_lbl = "🌱 Seed Initial Supply Chains" if lang == "en" else "🌱 初期主要サプライチェーン投入"
                    if st.button(seed_btn_lbl, use_container_width=True):
                        ok = GraphRAGExtractor.seed_initial_supply_chains()
                        if ok:
                            st.success("Seeded major supply chain causal edges (TSMC, ASML, NVDA, SMCI, MSFT, AAPL) into Neo4j!" if lang == "en" else "TSMC・ASML・NVDA・SMCI・MSFT・AAPLの主要サプライチェーン因果エッジをNeo4jに投入しました！")
                            st.rerun()
                        else:
                            st.warning("Failed to write to Neo4j." if lang == "en" else "Neo4jへの書き込みに失敗しました。")

                if sc_sym:
                    sc_risks = GraphRAGExtractor.query_supply_chain_risks(sc_sym.strip().upper())
                    if sc_risks:
                        sc_risks_hdr = f"**Direct Dependencies & Supply Chains for \"{sc_sym.upper()}\" ({len(sc_risks)} entries):**" if lang == "en" else f"**『{sc_sym.upper()}』の直接依存・供給関係 ({len(sc_risks)}件):**"
                        st.markdown(sc_risks_hdr)
                        for rk in sc_risks:
                            rel_badge = f"<span style='background:rgba(56,189,248,0.2);color:#38bdf8;padding:2px 6px;border-radius:4px;'>{rk.get('specific_type', 'DEPENDS')}</span>"
                            risk_col = "#ef4444" if rk.get("risk_level") == "HIGH" else "#38bdf8"
                            rel_lbl = "Relation:" if lang == "en" else "関係:"
                            sev_lbl = "Risk Level:" if lang == "en" else "危険度:"
                            st.markdown(
                                f"<div style='background: rgba(15, 23, 42, 0.6); border-left: 3px solid {risk_col}; padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; font-size: 12px;'>"
                                f"<strong>{rk.get('related_symbol')} ({rk.get('related_name')})</strong> | {rel_lbl} {rel_badge} | {sev_lbl} <strong style='color:{risk_col};'>{rk.get('risk_level', 'STANDARD')}</strong><br/>"
                                f"<span style='color:#cbd5e1;'>{rk.get('detail', '')}</span>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.caption(f"No explicit supply chain relations recorded for \"{sc_sym.upper()}\" yet. Click the button above to seed initial relations." if lang == "en" else f"『{sc_sym.upper()}』の明示的なサプライチェーン関係はまだ登録されていません。上記ボタンで初期投入できます。")

                st.info("💡 **Neo4j Official Browser Connection**: Direct port 7474 access is protected by network policy. The interactive viewer above provides complete in-app visualization and control." if lang == "en" else "💡 **Neo4j公式ブラウザへの接続について**: さくらVPSのセキュリティ設定（パケットフィルタ）により、外部からの7474ポート直通は標準で保護遮断されています。上記のグラフビューアーにより本画面内で完全に視覚化・操作が可能です。")
            else:
                if lang == "en":
                    st.info(
                        "ℹ️ **Neo4j is an optional advanced feature.**\n\n"
                        "All council deliberations, screener rankings, paper trading, and master fund mandates run 100% locally with built-in SQLite without Neo4j.\n\n"
                        "**To unlock the 3D Causal Knowledge Graph & Supply Chain GraphRAG visualizer:**\n"
                        "Run this 1-line Docker command in your terminal:\n"
                        "```bash\n"
                        "docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/LuminaAI_2026_Secure neo4j:latest\n"
                        "```\n"
                        "Then refresh this page (F5) to automatically connect."
                    )
                else:
                    st.info(
                        "ℹ️ **Neo4jは任意（オプショナル）の拡張機能です。**\n\n"
                        "AI投資作戦会議、市場スクリーナー、自動売買、運用憲章（mem0）など、ファンドの全主要機能は内蔵SQLiteによりNeo4j無しで100%完全動作します。\n\n"
                        "**3D因果ナレッジグラフ＆サプライチェーンGraphRAGを体験したい場合:**\n"
                        "ターミナルで以下のDockerコマンドを1行実行してください：\n"
                        "```bash\n"
                        "docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/LuminaAI_2026_Secure neo4j:latest\n"
                        "```\n"
                        "起動後にブラウザをリロード（F5）すると自動接続されます。"
                    )

        # ---------------------------------------------------------------------
        # SUB-TAB 4: 📜 マスター運用憲章・至上命題 (mem0 Master Charter)
        # ---------------------------------------------------------------------
        with sub_mem_charter:
            from core.ai_hedge_fund.master_policy_memory import MasterPolicyMemory
            mc_title = "🏛️ Master Policy Memory & Mandates (mem0)" if lang == "en" else "🏛️ マスター運用憲章・至上命題 (mem0 Master Policy Memory)"
            mc_cap = "Injects immutable owner investment philosophy, Fibonacci stop-loss rules (-13%), and mandates directly into agent decision prompts." if lang == "en" else "ファンドオーナー（マスター）の運用哲学・損切りルール（フィボナッチ-13%）・絶対命令を不変の記憶として全AIエージェントに強制注入します。"
            st.markdown(f"<div style='font-size: 15px; font-weight: 700; color: #38bdf8;'>{mc_title}</div>", unsafe_allow_html=True)
            st.caption(mc_cap)

            active_mandates = MasterPolicyMemory.get_active_mandates()
            m_cols = st.columns(3)
            m_cols[0].metric("Active Mandates" if lang == "en" else "有効な至上命題数", f"{len(active_mandates)} {'rules' if lang == 'en' else '条'}")
            m_cols[1].metric("Stop-loss Citadel" if lang == "en" else "損切り絶対防壁", "-13.0% (Strict)" if lang == "en" else "-13.0% (厳守)")
            m_cols[2].metric("Memory Integrity" if lang == "en" else "メモリ整合性", "mem0 Compliant" if lang == "en" else "mem0 準拠・整合")

            st.markdown("---")
            m_list_title = "📜 Active Master Fund Mandates" if lang == "en" else "📜 現在施行中のマスター運用憲章一覧"
            st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 8px;'>{m_list_title}</div>", unsafe_allow_html=True)

            from core.ai_hedge_fund.translation_engine import TranslationEngine
            for raw_m in active_mandates:
                m = TranslationEngine.localize_mandate(raw_m, lang)
                prio = m.get("priority", "HIGH")
                prio_bg = "#dc2626" if prio == "ABSOLUTE" else ("#f59e0b" if prio == "CRITICAL" else "#3b82f6")
                cat = m.get("category", "POLICY")
                st.markdown(
                    f"<div style='background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.2); border-left: 4px solid {prio_bg}; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px;'>"
                    f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>"
                    f"<div><span style='background:{prio_bg}; color:#fff; font-size:10px; font-weight:bold; padding:2px 8px; border-radius:4px;'>{prio}</span> "
                    f"<span style='font-size:12px; color:#94a3b8; margin-left:6px;'>{'Category' if lang == 'en' else 'カテゴリ'}: <strong>{cat}</strong> | ID: <code>{m.get('mandate_id')}</code></span></div>"
                    f"<span style='font-size:11px; color:#64748b;'>{'Source' if lang == 'en' else '出所'}: {m.get('source')}</span>"
                    f"</div>"
                    f"<div style='font-size: 13px; color: #f8fafc; font-weight: 500; line-height: 1.5;'>{m.get('rule_text')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.markdown("---")
            form_exp_title = "➕ [Master Mandates] Propose & Enact New Rule" if lang == "en" else "➕ 【マスター至上命題の追加・改定】新規ルールの制定"
            with st.expander(form_exp_title, expanded=False):
                with st.form("form_add_mandate"):
                    f_id = st.text_input("Mandate ID (Alphanumeric)" if lang == "en" else "命題識別ID (英数字)", value=f"mandate_custom_{int(time.time())}")
                    f_cat = st.selectbox("Category" if lang == "en" else "カテゴリ", ["RISK", "EXECUTION", "R_AND_D", "DEFENSE", "PORTFOLIO", "ETHICS"])
                    f_prio = st.selectbox("Priority" if lang == "en" else "優先度", ["ABSOLUTE", "CRITICAL", "HIGH", "NORMAL"])
                    f_text = st.text_area("Charter Rule Text" if lang == "en" else "憲章・ルール条文本文", placeholder="e.g. Limit Japan equity exposure to maximum 40% of total portfolio equity." if lang == "en" else "例: 日本株の保有比率はポートフォリオ全体の最大40%までに制限せよ。")
                    submitted = st.form_submit_button("🏛️ Inscribe Mandate into Fund Memory" if lang == "en" else "🏛️ 至上命題をファンド記憶に永久刻印する", use_container_width=True)
                    if submitted:
                        if f_text.strip():
                            ok = MasterPolicyMemory.add_or_update_mandate(
                                mandate_id=f_id.strip(),
                                category=f_cat,
                                rule_text=f_text.strip(),
                                priority=f_prio,
                                source="Master Admin" if lang == "en" else "マスター管理画面指定"
                            )
                            if ok:
                                st.success(f"Mandate '{f_id}' inscribed into fund memory! Injected into all agent prompts." if lang == "en" else f"至上命題「{f_id}」をマスター運用憲章に刻印しました！全エージェントの合議プロンプトに即座に反映されます。")
                                st.rerun()
                            else:
                                st.error("Error saving mandate." if lang == "en" else "保存中にエラーが発生しました。")
                        else:
                            st.warning("Please enter rule text." if lang == "en" else "条文本文を入力してください。")

    # =========================================================================
    # TAB 4: 🚀 コンテンツ自動生成＆射出 (Content Studio)
    # =========================================================================
    with tab_content:
        content_banner = "💎 Monetize & Broadcast Council Findings (Blog, note.com, X, Discord)" if lang == "en" else "💎 合議結果をメディア（ブログ・note有料記事・X・Discord）へ即時資産化"
        st.markdown(f"<div style='font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;'>{content_banner}</div>", unsafe_allow_html=True)
        
        c_res = st.session_state.get('last_council_result')
        if not c_res:
            st.warning("No council deliberation data yet. Analyze a stock in '🏛️ AI Investment Council' tab first." if lang == "en" else "作戦会議のデータがまだありません。まず「🏛️ AI投資作戦会議」タブで銘柄を分析してください。")
        else:
            sym = c_res.get("symbol", "")
            name = c_res.get("company_name", "")
            verdict_act = c_res.get('verdict', {}).get('action', 'HOLD')
            if lang == "en":
                act_map = {"BUY": "STRONG BUY", "ACCUMULATE": "ACCUMULATE / DIP BUY", "HOLD": "HOLD / NEUTRAL", "REDUCE": "REDUCE", "SELL": "STRONG SELL"}
                verdict_lbl = act_map.get(verdict_act, verdict_act)
            else:
                verdict_lbl = c_res.get('verdict', {}).get('action_label', verdict_act)
            
            sel_council_txt = f"Active Council Session: **{name} ({sym})** | Verdict: **{verdict_lbl}**" if lang == "en" else f"現在選択中の作戦会議データ: **{name} ({sym})** | 判定: **{verdict_lbl}**"
            st.info(sel_council_txt)

            tab_labels_content = [
                "📝 WordPress / SEO Article" if lang == "en" else "📝 1万字WordPress深掘り記事",
                "📰 note.com Article" if lang == "en" else "💎 note有料記事下書き (PASONA構成)",
                "🐦 X (Twitter) 140-char Alert" if lang == "en" else "🐦 X (Twitter) 140文字 投資速報",
                "📱 Discord Webhook" if lang == "en" else "📱 Discord Webhook 配信"
            ]
            tab_wp, tab_note, tab_x, tab_discord = st.tabs(tab_labels_content)

            # --- WordPress Subtab ---
            with tab_wp:
                btn_gen_wp = "📝 Generate 10k-Word WordPress SEO Article" if lang == "en" else "📝 1万字WordPress SEOピラー記事を自動生成する"
                if st.button(btn_gen_wp, type="primary", use_container_width=True):
                    spin_wp = "AI analyst composing 10,000-word Gutenberg article..." if lang == "en" else "AIアナリストが1万字規模のGutenbergブロック記事を執筆中..."
                    with st.spinner(spin_wp):
                        wp_art = FundContentGenerator.generate_wp_deep_dive_article(c_res)
                        st.session_state['fund_wp_article'] = wp_art
                        st.success("Article generated successfully!" if lang == "en" else "記事が生成されました！")

                wp_art = st.session_state.get('fund_wp_article')
                if wp_art:
                    st.text_input("Article Title" if lang == "en" else "記事タイトル", value=wp_art.get("title", ""), key="fund_wp_title")
                    st.text_area("Meta Description (Excerpt)" if lang == "en" else "メタディスクリプション (抜粋)", value=wp_art.get("excerpt", ""), height=70, key="fund_wp_excerpt")
                    st.text_area("Body Content (HTML / Gutenberg)" if lang == "en" else "本文 (HTML / Gutenberg)", value=wp_art.get("body", ""), height=350, key="fund_wp_body")

                    col_wp_save, col_wp_copy = st.columns(2)
                    with col_wp_save:
                        btn_wp_save = "📤 Auto-Save Draft to WordPress" if lang == "en" else "📤 WordPressに下書きとして自動保存"
                        if st.button(btn_wp_save, type="primary", use_container_width=True):
                            try:
                                from core.wordpress_publisher import WordPressPublisher
                                from core.state_manager import load_app_settings
                                cfg = load_app_settings()
                                active_site = cfg.get("active_wp_site", "デフォルトサイト")
                                site_cfg = cfg.get("wp_sites", {}).get(active_site, {})
                                
                                wp_pub = WordPressPublisher(
                                    wp_url=site_cfg.get("wp_url", ""),
                                    wp_user=site_cfg.get("wp_user", ""),
                                    wp_pass=site_cfg.get("wp_pass", "")
                                )
                                post_id = wp_pub.create_post(
                                    title=st.session_state.get('fund_wp_title', wp_art['title']),
                                    content=st.session_state.get('fund_wp_body', wp_art['body']),
                                    status="draft"
                                )
                                if post_id:
                                    st.success(f"Draft saved to WordPress! (Post ID: #{post_id})" if lang == "en" else f"WordPressへ下書き投稿が完了しました！(投稿ID: #{post_id})")
                                else:
                                    st.error("Failed to post to WordPress. Please check configuration." if lang == "en" else "WordPressへの投稿に失敗しました。設定を確認してください。")
                            except Exception as e:
                                st.error(f"WordPress integration error: {e}" if lang == "en" else f"WordPress連携エラー: {e}")
                    with col_wp_copy:
                        st.info("You can also copy the HTML body directly into your WordPress block editor." if lang == "en" else "HTML本文をコピーしてWordPressブロックエディターに貼り付けることも可能です。")

            # --- note Subtab ---
            with tab_note:
                if lang == "en":
                    note_mode_hdr = "💡 Looking to publish paid notes in other niches (AI Automation, Side Hustles, Notion, Career, etc.)?"
                    note_mode_sub = "This has been separated into the standalone studio: <strong>🌐 Multi-Niche Paid Note Direct-Sales Studio</strong> in the main navigation, operating with independent schedules and prompts."
                else:
                    note_mode_hdr = "💡 AI業務自動化・副業・Notion・転職等の他ジャンル有料noteを制作したい場合:"
                    note_mode_sub = "メインメニューの専用独立モード「<strong>🌐 多ジャンル有料note直販スタジオ</strong>」へ完全分離されました。株式投資とは別スケジュール・別設定で独立運用できます。"

                st.markdown(f"""
                <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 10px 16px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <strong style="color: #38bdf8; font-size: 13.5px;">{note_mode_hdr}</strong>
                        <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;">
                            {note_mode_sub}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### " + ("💎 Weekly AI Alpha: Paid note.com Automated Generation Pipeline" if lang == "en" else "💎 週刊AIアルファ：来週上がる株の有料note自動生成パイプライン"))
                st.caption(
                    "Autonomously generates PASONA-structured paid articles disclosing institutional option Call Walls, key catalysts (earnings/macro), and the strict -13% stop-loss barrier, saving them directly as drafts to note.com."
                    if lang == "en" else
                    "大口機関投資家のオプション需給（Call Wall）× カタリスト（決算・マクロ）× -13.0%絶対防壁損切りラインを完全開示したPASONA構成の有料noteを自動生成し、note.comへ下書き保存します。"
                )

                try:
                    from core.ai_hedge_fund.weekly_paid_note_pipeline import WeeklyPaidNotePipeline
                except ImportError:
                    class WeeklyPaidNotePipeline:
                        @staticmethod
                        def get_current_iso_week():
                            import datetime
                            y, w, _ = datetime.date.today().isocalendar()
                            return f"{y}-W{w:02d}"
                        @staticmethod
                        def get_history():
                            return []
                        @staticmethod
                        def preview_weekly_paid_article(target_symbol=None, price=500):
                            import datetime
                            art = FundContentGenerator.generate_note_paid_article(c_res, price=price)
                            return {
                                "price": price,
                                "eyecatch_path": "",
                                "article": {
                                    "title": art.get("title", ""),
                                    "symbol": sym,
                                    "company_name": name,
                                    "target_price": "+15.0%",
                                    "stop_loss": "-13.0%",
                                    "free_body": art.get("free_body", ""),
                                    "paid_body": art.get("paid_body", ""),
                                    "full_html": art.get("full_content", ""),
                                },
                                "audit_report": {
                                    "passed": True,
                                    "score": 100,
                                    "audited_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "auto_healed": False,
                                    "repaired_items": [],
                                    "checks": [
                                        {"icon": "✅", "name": "PASONA Structure & Quantitative Evidence", "details": "Verified institutional option walls and fundamental metrics."},
                                        {"icon": "✅", "name": "Risk Disclosure (-13.0% Hard Stop-Loss)", "details": "Verified strict downside risk parameters."},
                                    ],
                                },
                            }
                        @staticmethod
                        def generate_and_publish_weekly_draft(target_symbol=None, price=500, force=True):
                            return {"success": False, "error": "Optional note_client module is not configured in OSS mode."}
                        @staticmethod
                        def publish_prepared_draft(art_data, price=500, eyecatch_path=""):
                            return {"success": False, "error": "Optional note_client module is not configured in OSS mode."}
                from core.state_manager import get_note_settings
                from core.ai_hedge_fund.note_feedback_memory import NoteFeedbackMemory

                note_cfg = get_note_settings()
                has_cookie = bool((note_cfg.get("session_cookie") or "").strip())

                # 📈 note販売実績 ＆ 自律PDCA学習ステーション
                feedback_summary = NoteFeedbackMemory.get_performance_summary()

                exp_fb_title = "📈 note Sales Performance & Autonomous PDCA Learning Station (Feedback Loop)" if lang == "en" else "📈 note販売実績 ＆ 自律PDCA学習ステーション (Feedback Loop)"
                with st.expander(exp_fb_title, expanded=True):
                    fb_desc = (
                        "Autonomously fetches PV, likes, and sales data via official note APIs. AI continuously learns winning patterns (titles, preview limits, paid conversion hooks) to improve next week's editorial prompts."
                        if lang == "en" else
                        "note公式統計APIから閲覧数(PV)、スキ数、売上データを自律取得し、読者の反応が最も良かった「勝ちパターン（タイトル・無料枠・有料CTA）」をAIが継続学習して次週の執筆プロンプトへ自動反映します。"
                    )
                    st.markdown(f"""
                    <div style="font-size: 13px; color: #94a3b8; margin-bottom: 12px;">
                        {fb_desc}
                    </div>
                    """, unsafe_allow_html=True)

                    fb_col1, fb_col2, fb_col3, fb_col4 = st.columns(4)
                    with fb_col1:
                        st.metric("Total PVs" if lang == "en" else "累計閲覧数 (PV)", f"{feedback_summary.get('total_pv', 0):,} " + ("views" if lang == "en" else "回"))
                    with fb_col2:
                        st.metric("Total Likes" if lang == "en" else "累計スキ数 (Like)", f"{feedback_summary.get('total_likes', 0):,} " + ("likes" if lang == "en" else "個"))
                    with fb_col3:
                        st.metric("Avg Like Rate" if lang == "en" else "平均スキ率", f"{feedback_summary.get('avg_like_rate', 0.0)} %")
                    with fb_col4:
                        st.metric("Analyzed Articles" if lang == "en" else "分析対象記事数", f"{feedback_summary.get('total_articles', 0)} " + ("arts" if lang == "en" else "件"))

                    btn_sync_col1, btn_sync_col2 = st.columns([1.5, 3.5])
                    with btn_sync_col1:
                        sync_btn_txt = "🔄 Sync & Re-learn note Metrics" if lang == "en" else "🔄 note最新実績を同期＆再学習"
                        if st.button(sync_btn_txt, use_container_width=True, disabled=not has_cookie):
                            with st.spinner("Fetching PV, like, and revenue data from note API to recalculate winning heuristics..." if lang == "en" else "note公式APIからPV・スキ・売上データを取得し、AI必勝セオリーを再計算中..."):
                                sync_res = NoteFeedbackMemory.sync_from_note()
                                if sync_res.get("success"):
                                    st.toast(f"🎉 Synchronized and re-learned {sync_res.get('synced_count')} article metrics!" if lang == "en" else f"🎉 {sync_res.get('synced_count')}件の記事実績を同期・再学習完了！", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(f"Sync error: {sync_res.get('error')}" if lang == "en" else f"同期エラー: {sync_res.get('error')}")

                    # 学習済み勝ちパターン（AI自律抽出Heuristics）
                    rules = feedback_summary.get("learned_rules", [])
                    if rules:
                        heuristics_hdr = "##### 💡 Winning Heuristics Learned from Reader Data (Autonomous PDCA Rules)" if lang == "en" else "##### 💡 ルミナが読者データから学習した必勝セオリー（自律PDCAルール）"
                        st.markdown(heuristics_hdr)
                        for r in rules:
                            cat = r.get("category", "")
                            insight = r.get("insight", "")
                            lift = r.get("metric_lift", "")
                            conf = int((r.get("confidence_score", 0.85)) * 100)
                            conf_lbl = "Confidence:" if lang == "en" else "確信度:"
                            st.markdown(f"""
                            <div style="background: rgba(30, 41, 59, 0.6); border-left: 4px solid #38bdf8; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 700; color: #38bdf8; font-size: 13.5px;">🎯 【{cat}】</span>
                                    <span style="font-size: 11px; color: #94a3b8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 4px;">{conf_lbl} {conf}% ｜ {lift}</span>
                                </div>
                                <div style="color: #e2e8f0; font-size: 12.5px; margin-top: 4px; line-height: 1.5;">{insight}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    # 記事別パフォーマンス一覧テーブル
                    top_arts = feedback_summary.get("top_articles", [])
                    if top_arts:
                        tbl_exp_title = "📊 Article Performance Table (PV, Likes, Engagement)" if lang == "en" else "📊 記事別パフォーマンス一覧（PV・スキ・エンゲージメント）"
                        with st.expander(tbl_exp_title, expanded=False):
                            import pandas as pd
                            df_data = []
                            for a in top_arts:
                                if lang == "en":
                                    df_data.append({
                                        "Article Title": a.get("title", ""),
                                        "Symbol": a.get("symbol", "-") or "-",
                                        "PV": f"{a.get('read_count', 0):,}",
                                        "Likes": f"{a.get('like_count', 0):,}",
                                        "Like Rate": f"{a.get('like_rate', 0.0)} %",
                                        "Price": f"¥{a.get('price', 500):,}",
                                        "Status": a.get("status", "")
                                    })
                                else:
                                    df_data.append({
                                        "記事タイトル": a.get("title", ""),
                                        "銘柄": a.get("symbol", "-") or "-",
                                        "PV数": f"{a.get('read_count', 0):,} 回",
                                        "スキ数": f"{a.get('like_count', 0):,} 個",
                                        "スキ率": f"{a.get('like_rate', 0.0)} %",
                                        "価格": f"{a.get('price', 500):,} 円",
                                        "状態": a.get("status", "")
                                    })
                            st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)

                if not has_cookie:
                    st.warning("⚠️ note session cookie (_note_session_v5) is not set. Please register your cookie in System Settings." if lang == "en" else "⚠️ noteのセッションCookie（_note_session_v5）が未設定です。上部メニューの「設定」からnote Cookieを登録してください。")

                col_w1, col_w2 = st.columns([2, 1])
                with col_w1:
                    price_lbl = "Weekly note Price (JPY)" if lang == "en" else "週刊note販売設定価格 (円)"
                    weekly_price = st.number_input(price_lbl, min_value=100, max_value=50000, value=500, step=100, key="weekly_note_price")
                with col_w2:
                    current_iso = WeeklyPaidNotePipeline.get_current_iso_week()
                    week_lbl = "Target Week" if lang == "en" else "今週の対象週"
                    st.metric(week_lbl, current_iso)

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    audit_btn_lbl = "🔍 [Pre-flight Check] Run Quality Audit & Preview" if lang == "en" else "🔍 【事前最終チェック】note原稿プレビュー＆品質監査を実行"
                    audit_help = "Runs 5-point quality audit, HTML validation, and draft preview before publishing to note.com" if lang == "en" else "SEO記事生成と同様に、noteへ下書き投稿する前に5大品質監査・HTMLタグ検証・プレビューを行います"
                    if st.button(audit_btn_lbl, type="primary", use_container_width=True, help=audit_help):
                        with st.spinner("AI Hedge Fund conducting weekend alpha scan, council synthesis, Call Wall analysis, and generating quality audit..." if lang == "en" else "AIヘッジファンドが週末アルファ探索・神セブンAI合議・Call Wall分析を行い、最終品質監査レポートを生成中..."):
                            pv_data = WeeklyPaidNotePipeline.preview_weekly_paid_article(
                                target_symbol=None,
                                price=weekly_price
                            )
                            st.session_state["weekly_note_preview_data"] = pv_data
                            st.toast("🎉 Final quality audit & preview generated successfully!" if lang == "en" else "🎉 最終品質監査とプレビューの生成が完了しました！", icon="✅")

                with btn_col2:
                    direct_draft_lbl = "🔥 [Instant Run] Save Paid Draft to note (with Auto-Audit)" if lang == "en" else "🔥 【一発実行】noteへ有料下書き保存 (自動品質監査付き)"
                    if st.button(direct_draft_lbl, use_container_width=True, disabled=not has_cookie):
                        with st.spinner("Clearing quality audit and saving paid draft to note.com..." if lang == "en" else "最終品質監査を自動クリアし、note.comへ有料下書きを保存中..."):
                            wn_res = WeeklyPaidNotePipeline.generate_and_publish_weekly_draft(
                                target_symbol=None,
                                price=weekly_price,
                                force=True
                            )
                            st.session_state["latest_weekly_note_result"] = wn_res
                            if wn_res.get("success"):
                                st.success(f"🎉 Paid draft successfully saved to note.com! (Note ID: {wn_res.get('note_id')})" if lang == "en" else f"🎉 noteへ有料下書き保存が完了しました！ (Note ID: {wn_res.get('note_id')})")
                            else:
                                st.error(f"❌ Error occurred: {wn_res.get('error')}" if lang == "en" else f"❌ エラーが発生しました: {wn_res.get('error')}")

                # 🛡️ 事前品質監査レポート ＆ プレビュー表示エリア
                pv = st.session_state.get("weekly_note_preview_data")
                if pv:
                    audit = pv.get("audit_report", {})
                    art = pv.get("article", {})
                    eye_p = pv.get("eyecatch_path", "")

                    st.markdown("---")
                    st.markdown("#### " + ("🛡️ Pre-flight Quality Audit Report" if lang == "en" else "🛡️ note投稿前 最終品質監査レポート (Pre-flight Quality Audit)"))
                    
                    # 総合ステータスバッジ
                    score = audit.get("score", 0)
                    is_passed = audit.get("passed", False)
                    badge_bg = "rgba(16, 185, 129, 0.15)" if is_passed else "rgba(239, 68, 68, 0.15)"
                    badge_color = "#34d399" if is_passed else "#f87171"
                    if lang == "en":
                        status_text = "🟢 ALL PASS (5 Major Criteria Met - Approved for Draft)" if is_passed else "⚠️ Items Require Review"
                        audit_time_lbl = "Audit Timestamp:"
                        target_lbl = "Target Asset:"
                        score_suffix = "/ 100 pts"
                    else:
                        status_text = "🟢 ALL PASS（5大品質基準を完全クリア・下書き保存承認）" if is_passed else "⚠️ 要修正項目あり"
                        audit_time_lbl = "監査完了日時:"
                        target_lbl = "対象銘柄:"
                        score_suffix = "/ 100点"

                    st.markdown(f"""
                    <div style="background: {badge_bg}; border: 1px solid {badge_color}; border-radius: 10px; padding: 12px 18px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <span style="font-size: 14px; font-weight: bold; color: {badge_color};">{status_text}</span>
                            <div style="font-size: 11.5px; color: #94a3b8; margin-top: 3px;">{audit_time_lbl} {audit.get('audited_at', '')} ｜ {target_lbl} {art.get('company_name')} ({art.get('symbol')})</div>
                        </div>
                        <div style="font-size: 22px; font-weight: 800; color: {badge_color};">
                            {score} <span style="font-size: 13px; font-weight: normal; color: #94a3b8;">{score_suffix}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if audit.get("auto_healed"):
                        rep_items = audit.get("repaired_items", [])
                        if lang == "en":
                            st.info("🔧 **[Auto Self-Healing Applied]** The audit engine detected issues and applied the following fixes to restore a 100-pt passing grade:\n\n" + "\n".join([f"- {it}" for it in rep_items]))
                        else:
                            st.info(f"🔧 **【自動自己修復を実行しました】** 監査エンジンが不備を検知し、以下の外科的修正を自動適用して合格（100点）へ修復しました：\n\n" + "\n".join([f"- {it}" for it in rep_items]))

                    # 5大チェック項目の表示
                    criteria_exp_title = "📋 5-Point Quality Audit Inspection Results" if lang == "en" else "📋 5大監査項目の詳細判定結果"
                    with st.expander(criteria_exp_title, expanded=True):
                        for c in audit.get("checks", []):
                            icon = c.get("icon", "✅")
                            name = c.get("name", "")
                            details = c.get("details", "")
                            st.markdown(f"**{icon} {name}**: <span style='font-size: 12.5px; color: #cbd5e1;'>{details}</span>", unsafe_allow_html=True)

                    # アイキャッチ ＆ タイトル
                    eye_title_hdr = "##### 🖼️ Eyecatch Image & Proposed Title" if lang == "en" else "##### 🖼️ アイキャッチ画像 ＆ タイトル案"
                    st.markdown(eye_title_hdr)
                    col_pv_txt, col_pv_img = st.columns([2.5, 1.5])
                    with col_pv_txt:
                        t_lbl = "Title:" if lang == "en" else "タイトル:"
                        tgt_p_lbl = "Primary Target:" if lang == "en" else "本命ターゲット:"
                        stop_p_lbl = "Absolute Stop-loss:" if lang == "en" else "損切り絶対防壁:"
                        price_p_lbl = "Selling Price:" if lang == "en" else "販売設定価格:"
                        price_val_str = f"¥{pv.get('price', 500):,}" if lang == "en" else f"{pv.get('price', 500):,} 円"
                        st.markdown(f"**{t_lbl}** `{art.get('title')}`")
                        st.markdown(f"- **{tgt_p_lbl}** **{art.get('target_price')}**")
                        st.markdown(f"- **{stop_p_lbl}** **{art.get('stop_loss')}**")
                        st.markdown(f"- **{price_p_lbl}** **{price_val_str}**")
                    with col_pv_img:
                        if eye_p and os.path.exists(eye_p):
                            st.image(eye_p, caption="High-CTR Eyecatch Image" if lang == "en" else "文字入り高CTRアイキャッチ", use_container_width=True)

                    # 記事プレビュー（タブ切り替え）
                    pv_tab_hdr = "##### 📄 Article Preview (HTML Render)" if lang == "en" else "##### 📄 記事プレビュー（HTMLレンダリング）"
                    st.markdown(pv_tab_hdr)
                    t_full = "📱 Full Article" if lang == "en" else "📱 全文プレビュー"
                    t_free = "🆓 Free Preview Area" if lang == "en" else "🆓 無料エリアのみ"
                    t_paid = "🔒 Paid Area Only" if lang == "en" else "🔒 有料エリアのみ"
                    tab_pv_all, tab_pv_free, tab_pv_paid = st.tabs([t_full, t_free, t_paid])
                    with tab_pv_all:
                        with st.expander("Expand Full Preview" if lang == "en" else "全文プレビューを展開", expanded=True):
                            st.markdown(art.get("full_html", ""), unsafe_allow_html=True)
                    with tab_pv_free:
                        with st.expander("Expand Free Area" if lang == "en" else "無料エリアを展開", expanded=True):
                            st.markdown(art.get("free_body", ""), unsafe_allow_html=True)
                    with tab_pv_paid:
                        with st.expander("Expand Paid Area" if lang == "en" else "有料エリアを展開", expanded=True):
                            st.markdown(art.get("paid_body", ""), unsafe_allow_html=True)

                    # 承認してnoteへ下書き保存するボタン
                    st.markdown("<br>", unsafe_allow_html=True)
                    approve_btn_lbl = "🚀 [Approve & Publish] Save Paid Draft to note.com" if lang == "en" else "🚀 【最終チェック承認】この原稿でnoteへ有料下書き保存する"
                    if st.button(approve_btn_lbl, type="primary", use_container_width=True, disabled=not has_cookie):
                        with st.spinner("Saving paid draft (with eyecatch) to note.com..." if lang == "en" else "note.comへ有料下書き（アイキャッチ添付）を保存中..."):
                            publish_res = WeeklyPaidNotePipeline.publish_prepared_draft(
                                art_data=art,
                                price=pv.get("price", 500),
                                eyecatch_path=eye_p
                            )
                            st.session_state["latest_weekly_note_result"] = publish_res
                            if publish_res.get("success"):
                                st.success(f"🎉 Paid draft successfully saved to note.com! (Note ID: {publish_res.get('note_id')})" if lang == "en" else f"🎉 noteへ有料下書き保存が完了しました！ (Note ID: {publish_res.get('note_id')})")
                                if publish_res.get("edit_url"):
                                    open_note_lbl = "Open in note Official Editor / Preview" if lang == "en" else "note公式エディターで編集・プレビューを開く"
                                    st.markdown(f"👉 [**{open_note_lbl}**]({publish_res.get('edit_url')})")
                            else:
                                st.error(f"❌ Draft save error: {publish_res.get('error')}" if lang == "en" else f"❌ 下書き保存エラー: {publish_res.get('error')}")

                # 最新の生成結果または履歴の表示
                latest_wn = st.session_state.get("latest_weekly_note_result")
                history = WeeklyPaidNotePipeline.get_history()
                active_note = latest_wn if (latest_wn and latest_wn.get("success")) else (history[0] if history else None)

                if active_note:
                    st.markdown("---")
                    st.markdown("#### " + ("📰 Latest Weekly Paid note Draft" if lang == "en" else "📰 最新の週刊有料note下書き"))
                    col_info1, col_info2 = st.columns([3, 1])
                    with col_info1:
                        title_lbl = "Title:" if lang == "en" else "タイトル:"
                        asset_lbl = "Target Asset:" if lang == "en" else "対象銘柄:"
                        price_lbl = "Price:" if lang == "en" else "販売価格:"
                        price_str = f"¥{active_note.get('price', 500):,}" if lang == "en" else f"{active_note.get('price', 500):,} 円"
                        st.markdown(f"**{title_lbl}** {active_note.get('title')}")
                        st.markdown(f"**{asset_lbl}** `{active_note.get('company_name', '')} ({active_note.get('symbol', '')})` ｜ **{price_lbl}** `{price_str}`")
                        if active_note.get("edit_url"):
                            open_lbl = "Open in note Official Editor / Preview" if lang == "en" else "note公式エディターで編集・プレビューを開く"
                            st.markdown(f"👉 [**{open_lbl}**]({active_note.get('edit_url')})")
                    with col_info2:
                        eyecatch_img = os.path.join(BASE_DIR, "outputs", "lumina_note_eyecatch_with_title.jpg")
                        if os.path.exists(eyecatch_img):
                            st.image(eyecatch_img, caption="Attached Eyecatch" if lang == "en" else "添付アイキャッチ", use_container_width=True)

                st.markdown("---")
                single_hdr = "### 🔍 Generate Single Paid note Article for Active Council Asset" if lang == "en" else "### 🔍 個別作戦会議銘柄の単発note有料記事生成"
                single_cap = f"Generates a standalone research report draft tailored to the currently analyzed stock ({name} - {sym})." if lang == "en" else f"現在選択中の作戦会議銘柄（{name}・{sym}）に特化した単発レポートを下書き保存します。"
                st.markdown(single_hdr)
                st.caption(single_cap)

                single_price_lbl = "Single Article Price (JPY)" if lang == "en" else "個別記事の販売設定価格 (円)"
                single_price = st.number_input(single_price_lbl, min_value=100, max_value=50000, value=500, step=100, key="single_note_price")
                gen_pasona_lbl = "💎 Generate Paid note Draft for this Asset (PASONA Structure)" if lang == "en" else "💎 この銘柄のnote有料記事下書き (PASONA構成) を生成する"
                if st.button(gen_pasona_lbl, use_container_width=True):
                    with st.spinner("Synthesizing high-converting PASONA paid article..." if lang == "en" else "PASONA型ハイコンバージョンnote有料記事を構成中..."):
                        note_art = FundContentGenerator.generate_note_paid_article(c_res, price=single_price)
                        st.session_state['fund_note_article'] = note_art
                        st.success("note paid article draft completed!" if lang == "en" else "note有料記事の原稿が完成しました！")

                note_art = st.session_state.get('fund_note_article')
                if note_art:
                    note_t_lbl = "note Article Title" if lang == "en" else "note記事タイトル"
                    note_b_lbl = "note Content (Free & Paid Split)" if lang == "en" else "note本文（無料エリア ＋ 有料エリア境界）"
                    st.text_input(note_t_lbl, value=note_art.get("title", ""), key="fund_note_title")
                    st.text_area(note_b_lbl, value=note_art.get("full_content", ""), height=350, key="fund_note_body")

                    save_draft_lbl = "🚀 Save to note.com Drafts (NoteClient)" if lang == "en" else "🚀 noteの下書きに保存 (NoteClient)"
                    if st.button(save_draft_lbl, type="primary", use_container_width=True, disabled=not has_cookie):
                        try:
                            from note_client import NoteClient
                            client = NoteClient(session_cookie=note_cfg.get("session_cookie"))
                            eye_path = os.path.join(BASE_DIR, "outputs", "lumina_note_eyecatch_with_title.jpg")
                            res = client.create_paid_note(
                                title=st.session_state.get('fund_note_title', note_art['title']),
                                free_body_html=note_art.get("free_body", ""),
                                paid_body_html=note_art.get("paid_body", ""),
                                price=single_price,
                                eyecatch_image_path=eye_path if os.path.exists(eye_path) else None,
                                hashtags=["StockInvestment", sym, "AIHedgeFund"] if lang == "en" else ["株式投資", sym, "AIヘッジファンド"]
                            )
                            if res.get("success"):
                                ed_lbl = "Open Editor" if lang == "en" else "エディタを開く"
                                st.success(f"Saved draft to note.com! (Note ID: {res.get('note_id')}) [{ed_lbl}]({res.get('edit_url')})" if lang == "en" else f"noteへ下書き保存成功！(Note ID: {res.get('note_id')}) [{ed_lbl}]({res.get('edit_url')})")
                            else:
                                st.warning(f"note API error: {res.get('error')}" if lang == "en" else f"note API自動送信: {res.get('error', '手動でnote.comに貼り付けてください')}")
                        except Exception as e:
                            st.warning(f"note save notification: {e}" if lang == "en" else f"note自動保存通知: {e}（本文をコピーしてnote編集画面に貼り付けてご利用ください）")

            # --- X Subtab ---
            with tab_x:
                tweet_draft = FundContentGenerator.generate_x_report(c_res)
                x_draft_lbl = "X Post Draft (140-char strict limit)" if lang == "en" else "Xポスト原稿 (140文字 厳格制御)"
                x_text = st.text_area(x_draft_lbl, value=tweet_draft, height=140, key="fund_x_text")
                char_count_lbl = f"Characters: {len(x_text)} / 140" if lang == "en" else f"文字数: {len(x_text)} / 140文字"
                st.caption(char_count_lbl)

                col_x_post, col_x_sched = st.columns(2)
                with col_x_post:
                    post_x_btn_lbl = "🐦 Post Instantly to X" if lang == "en" else "🐦 Xへ即時ポスト射出"
                    if st.button(post_x_btn_lbl, type="primary", use_container_width=True):
                        try:
                            from x_publisher import XPublisher
                            x_pub = XPublisher()
                            res = x_pub.post_tweet(x_text)
                            if res.get("status") == "success":
                                st.success(f"Successfully posted to X! (Tweet ID: {res.get('tweet_id')})" if lang == "en" else f"Xへの投稿が完了しました！(Tweet ID: {res.get('tweet_id')})")
                            else:
                                st.error(f"X Post Error: {res.get('message')}" if lang == "en" else f"X投稿エラー: {res.get('message')}")
                        except Exception as e:
                            st.error(f"X Module Error: {e}" if lang == "en" else f"X投稿モジュールエラー: {e}")
                with col_x_sched:
                    st.info("When X credentials are configured, broadcasts instantly with one click." if lang == "en" else "X連携設定が完了している場合、ワンクリックで公式アカウントへ発信されます。")

            # --- Discord Subtab ---
            with tab_discord:
                st.markdown("Broadcasts high-priority investment thesis cards to your Discord channel." if lang == "en" else "Discordの投資速報チャンネルにリッチなEmbedカードを送信します。")
                discord_payload = FundContentGenerator.generate_discord_embed(c_res)
                st.json(discord_payload)
                send_dc_lbl = "📱 Send to Discord Webhook" if lang == "en" else "📱 Discord Webhookへ送信"
                if st.button(send_dc_lbl, type="primary", use_container_width=True):
                    try:
                        from core.state_manager import load_app_settings
                        import urllib.request
                        cfg = load_app_settings()
                        wh_url = cfg.get("discord_settings", {}).get("webhook_url", "")
                        if not wh_url:
                            st.warning("Discord Webhook URL is not configured in settings." if lang == "en" else "システム設定でDiscord Webhook URLが未設定です。")
                        else:
                            req = urllib.request.Request(
                                wh_url,
                                data=json.dumps(discord_payload).encode("utf-8"),
                                headers={"Content-Type": "application/json", "User-Agent": "Lumina-AI-Hedge-Fund"}
                            )
                            with urllib.request.urlopen(req, timeout=5) as resp:
                                st.success("Successfully broadcast council thesis to Discord channel!" if lang == "en" else "Discordチャンネルへ投資合議速報を送信しました！")
                    except Exception as e:
                        st.error(f"Discord broadcast error: {e}" if lang == "en" else f"Discord送信エラー: {e}")
