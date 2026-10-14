# -*- coding: utf-8 -*-
"""
Lumina Capital (AI Hedge Fund Engine v6.0.0)
Autonomous Multi-Agent Quantitative Hedge Fund Studio
Powered by LangGraph, Qlib Alpha158, Google TimesFM & 3D Knowledge Graph
"""

import os
import sys

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

import streamlit as st
from ui.mode_ai_hedge_fund import render_mode_ai_hedge_fund

st.set_page_config(
    page_title="Lumina Capital | AI Hedge Fund Engine",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Global Styling
st.markdown("""
<style>
    /* Dark Terminal Theme Polish */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    .stMetric {
        background: rgba(15, 23, 42, 0.65) !important;
        border: 1px solid rgba(56, 189, 248, 0.2) !important;
        border-radius: 10px !important;
        padding: 12px !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

def main():
    with st.sidebar:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
            <div style="font-size: 26px;">🏛️</div>
            <div>
                <div style="font-weight: 800; font-size: 1.15rem; color: #38bdf8;">Lumina Capital</div>
                <div style="font-size: 0.75rem; color: #94a3b8;">Autonomous AI Fund v6.0</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.caption("🤖 **LLM Engine Providers**")
        gemini_key = st.text_input(
            "Gemini API Key", 
            value=os.getenv("GEMINI_API_KEY", ""), 
            type="password",
            help="Required for LangGraph 7-agent debate & synthesis"
        )
        openai_key = st.text_input(
            "OpenAI API Key (Optional)", 
            value=os.getenv("OPENAI_API_KEY", ""), 
            type="password"
        )

        st.markdown("---")
        st.caption("⚙️ **Execution Architecture**")
        st.info("🛡️ **Mode**: High-Fidelity Paper Trading (SQLite, Real Commissions & Slippage)")
        
        st.markdown("---")
        st.markdown("""
        <div style="font-size: 0.78rem; color: #64748b; line-height: 1.5;">
            <strong>Lumina Capital OSS</strong><br>
            Research & Educational Platform.<br>
            License: CC BY-NC 4.0 (Non-Commercial)<br>
            <a href="https://github.com" target="_blank" style="color: #38bdf8; text-decoration: none;">GitHub Repository</a>
        </div>
        """, unsafe_allow_html=True)

    # Pass API key into main studio
    render_mode_ai_hedge_fund(api_key=gemini_key)

if __name__ == "__main__":
    main()
