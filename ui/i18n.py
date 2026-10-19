# -*- coding: utf-8 -*-
"""
Internationalization (i18n) module for Lumina Capital.
Provides bilingual support (English / 日本語) across the Studio UI.
Default: English (for global open-source developers & quants).
"""

import streamlit as st
from typing import Dict, Any

def get_current_lang() -> str:
    """Return 'en' or 'ja' based on session state. Default to 'en'."""
    return st.session_state.get("app_lang", "en")

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # --- Sidebar ---
    "sidebar_fund_sub": {
        "en": "Autonomous AI Fund v6.0",
        "ja": "Autonomous AI Fund v6.0"
    },
    "sidebar_llm_caption": {
        "en": "🤖 **LLM Engine Providers**",
        "ja": "🤖 **LLMエンジンプロバイダー**"
    },
    "sidebar_gemini_help": {
        "en": "Required for LangGraph 7-agent debate & synthesis",
        "ja": "LangGraphの7者合議・討議分析に必要です"
    },
    "sidebar_arch_caption": {
        "en": "⚙️ **Execution Architecture**",
        "ja": "⚙️ **執行アーキテクチャ**"
    },
    "sidebar_arch_info": {
        "en": "🛡️ **Mode**: High-Fidelity Paper Trading (SQLite, Real Commissions & Slippage)",
        "ja": "🛡️ **モード**: 高精度ペーパートレード (SQLite、手数料・スリッページ控除)"
    },
    "sidebar_lang_caption": {
        "en": "🌐 **Interface Language / 言語**",
        "ja": "🌐 **表示言語 / Language**"
    },
    "sidebar_star_box_title": {
        "en": "⭐ Support Lumina Open Source",
        "ja": "⭐ Luminaオープンソースを応援"
    },
    "sidebar_star_box_desc": {
        "en": "If you find this research platform valuable, please star us on GitHub!",
        "ja": "このプロジェクトが役立ちましたら、ぜひGitHubでStarをお願いします！"
    },
    "sidebar_star_btn": {
        "en": "⭐ Star on GitHub",
        "ja": "⭐ GitHubでStarする"
    },

    # --- Header Banner ---
    "header_badge": {
        "en": "● Autonomous Multi-Agent Investment Council",
        "ja": "● 自律型マルチエージェント投資合議"
    },
    "header_sub": {
        "en": "Legendary investor AI council (Buffett, Soros, Burry, Graham, Wood, O'Neil, CIS, Risk) debating via Alpha158 quant & LangGraph",
        "ja": "伝説の投資家AI（バフェット・ソロス・バーリ・グレアム・木・オニール・CIS・リスク管理）がAlpha158クオンツとLangGraphで合議"
    },
    "header_data": {
        "en": "📈 Data: yfinance (US, TSE, Global ADR)",
        "ja": "📈 データ: yfinance (東証/米国株/欧州ADR)"
    },
    "header_mode": {
        "en": "💼 Mode: Paper Trading ($10k / ¥1M initial)",
        "ja": "💼 運用モード: ペーパートレード (初期¥100万/$1万)"
    },

    # --- Main Tabs ---
    "tab_council": {
        "en": "🏛️ AI Investment Council",
        "ja": "🏛️ AI投資作戦会議 (Investment Council)"
    },
    "tab_portfolio": {
        "en": "💼 Portfolio & PnL Dashboard",
        "ja": "💼 ポートフォリオ＆損益ダッシュボード"
    },
    "tab_memory": {
        "en": "📜 Fund Memory & Archive",
        "ja": "📜 ファンド記憶・合議録アーカイブ (Memory)"
    },
    "tab_content": {
        "en": "🚀 Content Studio",
        "ja": "🚀 コンテンツ自動生成＆射出 (Content Studio)"
    },

    # --- Tab 1: Council ---
    "council_hint": {
        "en": "💡 **How it works**: Select a stock preset or enter a ticker symbol and click 'Convene Investment Council'. The CIO final verdict, 1v1 cross-debate, TradingView chart, and fast execution order box will appear below.",
        "ja": "💡 **合議・分析結果の閲覧場所**: 銘柄プリセットまたはティッカーを入力して『⚔️ 投資作戦会議を招集する』を押すと、この画面下部に**CIO最終判定・AI投資家討議・TradingViewチャート・即時発注**が表示されます。"
    },
    "quick_presets": {
        "en": "⚡ One-Click Stock Presets (US, Japan, Global ADR)",
        "ja": "⚡ ワンクリック銘柄プリセット（日本株 ＆ 米国株 ＆ 欧州グローバルADR）"
    },
    "manual_symbol_heading": {
        "en": "🎯 Target Ticker Symbol",
        "ja": "🎯 手動指定で招集する"
    },
    "symbol_input_label": {
        "en": "Ticker Symbol (e.g. NVDA, AAPL, MSFT, TSLA, 7203.T, ASML)",
        "ja": "銘柄コード / ティッカーシンボル (例: 7203.T, 8058.T, NVDA, AAPL, MSFT)"
    },
    "convene_btn": {
        "en": "⚔️ Convene Investment Council",
        "ja": "⚔️ 投資作戦会議を招集する"
    },
    "spinner_running": {
        "en": "🏛️ Gathering real-time metrics, SEC 10-K, Alpha158 quant factors, and convening legendary investor AI council...",
        "ja": "🏛️ 財務データ・SEC開示・Alpha158クオンツを取得し、伝説の投資家AIたちによる合議討議を開始しています..."
    },
    "council_done": {
        "en": "🎉 Deliberation completed for {symbol}! Scroll down for the CIO verdict and debate breakdown.",
        "ja": "🎉 「{symbol}」の合議討議が完了しました！下に分析結果と合議録を表示しています。"
    },
    "council_error": {
        "en": "Error during council execution: {error}",
        "ja": "合議実行中にエラーが発生しました: {error}"
    },

    # Metrics
    "current_price": {"en": "Current Price", "ja": "現在値"},
    "return_20d": {"en": "20D Return", "ja": "20日リターン"},
    "pe_trailing": {"en": "Trailing P/E", "ja": "実績PER"},
    "pb_ratio": {"en": "P/B Ratio", "ja": "PBR"},
    "dividend_yield": {"en": "Div Yield", "ja": "配当利回り"},
    "roe": {"en": "ROE", "ja": "ROE"},

    # CIO Verdict Card
    "cio_title": {"en": "Lumina Capital CIO Final Verdict", "ja": "Lumina Capital CIO 最終決定"},
    "target_price": {"en": "Target Price", "ja": "目標株価 (Target)"},
    "stop_loss": {"en": "Stop Loss Floor", "ja": "損切りライン (Stop Loss)"},
    "allocation": {"en": "Rec. Allocation", "ja": "推奨配分比率"},
    "confidence": {"en": "Confidence", "ja": "確信度スコア"},
    "thesis_title": {"en": "💡 CIO Investment Thesis:", "ja": "💡 CIO投資テーゼ（総括理由）:"},

    # Execution Box
    "fast_order_title": {"en": "⚡ Fast Paper Trading Order Execution", "ja": "⚡ ペーパートレード即時発注"},
    "order_side": {"en": "Side", "ja": "売買サイド"},
    "order_qty": {"en": "Quantity (Shares)", "ja": "株数 (Quantity)"},
    "order_est_val": {"en": "Est. Value", "ja": "概算約定代金"},
    "order_exec_btn": {"en": "🚀 Execute Simulation Order", "ja": "🚀 注文をシミュレーション執行"},
    "order_success": {"en": "Order Executed! Order #{order_id} | {side} {qty} shares @ {price} {curr}{sl_info}", "ja": "約定成功！注文ID #{order_id} | {side} {qty}株 @ {price} {curr}{sl_info}"},

    # Cross Debate Box
    "cross_debate_title": {"en": "⚔️ Philosophical Clash: Fact-Grounded Cross-Debate", "ja": "⚔️ 哲学衝突 ガチンコ・クロスディベート（事実拘束対決）"},
    "spread_label": {"en": "Max Stance Spread: {spread} pts", "ja": "最大見解乖離: {spread}点差"},
    "bear_attack_title": {"en": "🐻 [Bearish Lead Attack]", "ja": "🐻 [弱気派筆頭の痛烈糾弾]"},
    "bull_defense_title": {"en": "🐂 [Bullish Lead Defense & Re-evaluation]", "ja": "🐂 [強気派筆頭の回答 ＆ スコア再判定]"},
    "initial_score": {"en": "Initial {init} pts ➔ Verdict: {adj} pts {delta}", "ja": "当初 {init}点 ➔ 判定: {adj}点 {delta}"},
    "reconsider_label": {"en": "📌 Reconsideration Rationale:", "ja": "📌 再考理由:"},

    # TradingView Chart
    "chart_title": {"en": "📊 [TradingView Interactive Candlestick Chart] {name} ({sym})", "ja": "📊 【TradingView公式チャート】{name} ({sym}) インタラクティブ・ローソク足"},

    # --- Tab 2: Portfolio ---
    "broker_select_title": {"en": "🎛️ Broker & Execution Mode Selection", "ja": "🎛️ ブローカー・接続先モード選択"},
    "reset_portfolio_btn": {"en": "⚠️ Reset Portfolio ($10k / ¥1M initial balance)", "ja": "⚠️ ポートフォリオを初期化 (総資産100万円にリセット)"},
    "paper_broker_name": {"en": "🟢 Paper Trading (High-Fidelity Simulation - Initial $10,000 / ¥1,000,000)", "ja": "🟢 ペーパートレード (無料シミュレーション - 初期残高100万円 / $10,000)"},
    "kabu_broker_name": {"en": "🔵 au Kabucom Securities (kabu Station REST API - Tokyo Stock Exchange)", "ja": "🔵 auカブコム証券 (kabuステーション REST API - 東証現物自動発注)"},
    "ibkr_broker_name": {"en": "🟣 Interactive Brokers (IBKR TWS API - US & Global Equities)", "ja": "🟣 Interactive Brokers (IBKR TWS API - 米国株/日米株グローバル)"},
    "total_equity": {"en": "Total Equity", "ja": "総資産額"},
    "available_cash": {"en": "Available Cash", "ja": "買付余力 (現金)"},
    "unrealized_pnl": {"en": "Unrealized P&L", "ja": "評価損益"},
    "realized_pnl": {"en": "Realized P&L", "ja": "確定損益"},
    "win_rate": {"en": "Win Rate", "ja": "勝率"},
    "holdings_title": {"en": "📊 Active Portfolio Holdings", "ja": "📊 保有銘柄ポートフォリオ"},
    "history_title": {"en": "📜 Trade Execution History", "ja": "📜 取引履歴"},
    "daemon_title": {"en": "🤖 Autonomous Hedge Fund Daemon (15-min Cadence)", "ja": "🤖 完全自律運用デーモン（15分間隔巡回）"},
    "daemon_start": {"en": "▶️ Start Autonomous Daemon", "ja": "▶️ 自律運用を開始"},
    "daemon_stop": {"en": "⏹️ Stop Daemon", "ja": "⏹️ 停止する"},

    # --- Tab 3: Memory ---
    "memory_heading": {"en": "📜 Autonomous Fund Memory & Causal Knowledge Graph", "ja": "📜 ファンド記憶・合議録アーカイブ (Memory)"},
    "memory_search_label": {"en": "Search Symbol History (e.g. NVDA, AAPL, 7203.T)", "ja": "銘柄履歴を検索 (例: NVDA, AAPL, 7203.T)"},
    "graph_title": {"en": "🌐 3D Causal Knowledge Graph (SEC 10-K Supply Chain Risk Propagation)", "ja": "🌐 3Dナレッジグラフ (SEC 10-Kサプライチェーン波及)"},

    # --- Tab 4: Content Studio ---
    "content_heading": {"en": "🚀 Autonomous Research & Content Generation Studio", "ja": "🚀 コンテンツ自動生成＆射出 (Content Studio)"},
    "generate_report_btn": {"en": "📝 Generate Institutional Tear Sheet Report", "ja": "📝 機関投資家レポートを生成"}
}

def t(key: str, default: str = "", **kwargs) -> str:
    """
    Get localized string for the active language.
    Optionally formats the string with kwargs.
    """
    lang = get_current_lang()
    entry = TRANSLATIONS.get(key)
    if not entry:
        template = default or key
    else:
        template = entry.get(lang, entry.get("en", default or key))
        
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
