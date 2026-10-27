"""
HDFC FundIQ: SEBI & AMFI Compliant Facts-Only Mutual Fund Assistant
Frontend styled directly from stitch_hdfc_fundiq_assistant (Obsidian Capital Design System):
- Top Sticky Amber Disclaimer Banner
- Primary App Header with Emerald Brand Emblem, "HDFC Mutual Fund FAQ", "RAG Chatbot", and Pulsing "API Online" Capsule
- Left Sidebar with "SELECT FUND CONTEXT" & High-Density Fund Cards (General, Top 100, Mid-Cap, Small Cap, Multi-Cap, Silver ETF)
- Center Hero Screen with Glowing Emerald AI Sparkle Star, "HDFC Mutual Fund Assistant", Scoped Scope Indicator, and Amber Guardrail Callout
- Bottom Horizontal Pill Suggestions Strip
- Bottom Floating Dark-Glass Chat Input Bar
- Dual-Mode Communication: FastAPI Microservice (Port 8000) with In-Process RAG Fallback
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.config import settings, TARGET_SCHEMES, STARTER_QUESTIONS, MANDATORY_DISCLAIMER, PROCESSED_DATA_DIR
from src.guardrails.pii_filter import sanitize_pii, is_otp_or_credential, get_otp_security_warning
from src.guardrails.intent_router import IntentType, classify_intent, generate_refusal_response
from src.rag.retriever import retrieve_context, get_canonical_citation_for_scheme
from src.rag.generator import generate_answer
from src.session.thread_manager import thread_manager

# ----------------------------------------------------------------------
# Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="HDFC Mutual Fund FAQ | RAG Chatbot",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_BASE_URL = os.getenv("API_URL", f"http://127.0.0.1:{settings.api_port}")

# Fund Context Definitions (Matching stitch_hdfc_fundiq_assistant screen.png)
FUND_CONTEXTS = [
    {
        "id": "all",
        "name": "General / All Schemes",
        "category": "General FAQ & Guide",
        "risk": "N/A RISK",
        "risk_type": "na",
        "desc": "Query general FAQs, statement instructions, and account guidelines across all funds.",
    },
    {
        "id": "hdfc-large-cap-fund-direct-growth",
        "name": "HDFC Top 100 Fund",
        "category": "Equity - Large Cap",
        "risk": "VERY HIGH RISK",
        "risk_type": "high",
        "desc": "Focuses on large-cap bluechip stocks with long-term growth potential.",
    },
    {
        "id": "hdfc-mid-cap-fund-direct-growth",
        "name": "HDFC Mid-Cap Opportunities Fund",
        "category": "Equity - Mid Cap",
        "risk": "VERY HIGH RISK",
        "risk_type": "high",
        "desc": "Predominantly invests in high-growth mid-sized companies.",
    },
    {
        "id": "hdfc-small-cap-fund-direct-growth",
        "name": "HDFC Small Cap Fund",
        "category": "Equity - Small Cap",
        "risk": "VERY HIGH RISK",
        "risk_type": "high",
        "desc": "Focuses on high-growth potential small-cap companies.",
    },
    {
        "id": "hdfc-multi-cap-fund-direct-growth",
        "name": "HDFC Multi-Cap Fund",
        "category": "Equity - Multi Cap",
        "risk": "VERY HIGH RISK",
        "risk_type": "high",
        "desc": "Invests across large-cap, mid-cap, and small-cap segments.",
    },
    {
        "id": "hdfc-silver-etf-fof-direct-growth",
        "name": "HDFC Silver ETF FoF",
        "category": "Commodity - Silver FoF",
        "risk": "HIGH RISK",
        "risk_type": "med_high",
        "desc": "Invests in units of HDFC Silver ETF tracking domestic physical silver prices.",
    },
]

# Suggestions tailored to selected scope
CONTEXT_SUGGESTIONS = {
    "all": [
        "How can I check my mutual fund statement?",
        "What is the exit load on HDFC funds?",
        "How to download capital gains statement on Groww?",
        "What is the lock-in period for ELSS funds?",
    ],
    "hdfc-large-cap-fund-direct-growth": [
        "What is the expense ratio of HDFC Top 100?",
        "What are top 5 stock holdings of HDFC Top 100?",
        "What is the 3-year return of HDFC Top 100?",
        "What is the minimum SIP for HDFC Top 100?",
    ],
    "hdfc-mid-cap-fund-direct-growth": [
        "What is the latest NAV and TER of HDFC Mid-Cap?",
        "What are top 5 stock holdings of HDFC Mid-Cap?",
        "What is the portfolio turnover of HDFC Mid-Cap?",
        "What is the exit load for HDFC Mid-Cap?",
    ],
    "hdfc-small-cap-fund-direct-growth": [
        "What is 3Y CAGR & 5Y SIP return for Small Cap?",
        "What is the exit load for HDFC Small Cap?",
        "What are top stock holdings of HDFC Small Cap?",
        "What is the latest NAV of HDFC Small Cap?",
    ],
    "hdfc-multi-cap-fund-direct-growth": [
        "What is the benchmark index for HDFC Multi-Cap?",
        "What is the current NAV of HDFC Multi-Cap?",
        "What is the minimum SIP for HDFC Multi-Cap?",
        "What are top stock holdings of HDFC Multi-Cap?",
    ],
    "hdfc-silver-etf-fof-direct-growth": [
        "What is the lock-in period for HDFC Silver ETF FoF?",
        "What is the 1-year return for HDFC Silver ETF FoF?",
        "What is the expense ratio of HDFC Silver ETF FoF?",
        "What is the benchmark index for Silver ETF?",
    ],
}


# ----------------------------------------------------------------------
# Safe HTML Renderer (Prevents CommonMark Indented Code Block Quirk)
# ----------------------------------------------------------------------
def render_html(html_str: str) -> None:
    """
    Render HTML safely in Streamlit without CommonMark indented code block escaping.
    Strips leading indentation from every line so lines never trigger the 4-space markdown rule.
    This permanently prevents literal <div> or XML leakage on the UI.
    """
    lines = [line.strip() for line in html_str.strip().splitlines() if line.strip()]
    st.markdown("\n".join(lines), unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Clean Response Parser (Zero XML / Zero Broken Tags)
# ----------------------------------------------------------------------
def parse_assistant_response(text: str, default_url: Optional[str] = None) -> Dict[str, Any]:
    """Extract clean narrative and official citation without XML leakage or metadata headers."""
    if not text:
        return {
            "narrative": "Information for this query is not available in the verified Groww sources.",
            "citation_url": default_url,
            "citation_anchor": "Groww Scheme Details",
        }

    # 1. Clean XML/HTML tags and entities
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"&lt;[^&>]+&gt;", "", clean)
    clean = re.sub(r"</?[a-zA-Z][^>]*>", "", clean)

    # 2. Strip footer date line
    clean = re.sub(r"\*?Last updated from sources:\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\*?", "", clean, flags=re.IGNORECASE).strip()

    # 3. Strip any residual AMC snapshot or latency text
    clean = re.sub(r"Audited AMC snapshot.*?Sub-100ms", "", clean, flags=re.DOTALL | re.IGNORECASE).strip()
    clean = re.sub(r"Groq LPU\s*•\s*Sub-100ms", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"Audited AMC snapshot\s*•\s*Freshness verified:\s*[0-9]{4}-[0-9]{2}-[0-9]{2}", "", clean, flags=re.IGNORECASE).strip()

    # 4. Extract citation link and anchor
    source_match = re.search(r"(?:Source|Reference):\s*\[([^\]]+)\]\((https?://[^\s)]+)\)", clean, re.IGNORECASE)
    if source_match:
        anchor = source_match.group(1).strip()
        url = source_match.group(2).strip()
        clean = re.sub(r"(?:Source|Reference):\s*\[([^\]]+)\]\((https?://[^\s)]+)\)", "", clean, flags=re.IGNORECASE).strip()
    else:
        inline_match = re.search(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", clean)
        if inline_match:
            anchor = inline_match.group(1).strip()
            url = inline_match.group(2).strip()
            clean = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1", clean).strip()
        else:
            anchor = "Official Groww Scheme Factsheet"
            url = default_url

    clean = re.sub(r"(?:\n|\r|\s)*(?:Source|Reference):?\s*\[?[^\]\n\r]*$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"(?:Source|Reference):?\s*\[[^\]\)]*$", "", clean, flags=re.IGNORECASE).strip()

    return {
        "narrative": clean,
        "citation_url": url or default_url,
        "citation_anchor": anchor,
    }


# ----------------------------------------------------------------------
# CSS Design System (Exact Match to stitch_hdfc_fundiq_assistant)
# ----------------------------------------------------------------------
render_html(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
    /* Dark Theme Base (stitch Obsidian palette) */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #0b0f19 !important;
        color: #f1f5f9 !important;
    }

    #MainMenu, header, footer {
        visibility: hidden !important;
        height: 0 !important;
    }

    /* Completely hide and eliminate left sidebar, collapse chevron tab, and scrollbars */
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"],
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"] {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        max-width: 0 !important;
        min-width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
        position: absolute !important;
        left: -9999px !important;
    }

    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 5.5rem !important;
        max-width: 920px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* Ensure chat input bottom container aligns with centered content */
    div[data-testid="stBottom"] > div {
        max-width: 920px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* Custom Sleek Scrollbar from code.html */
    ::-webkit-scrollbar {
        width: 5px;
        height: 5px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: #1e293b;
        border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #334155;
    }

    /* 1. TOP STICKY DISCLAIMER BANNER (Exact Match) */
    .top-disclaimer-bar {
        background: #0a0d14;
        border-bottom: 1px solid rgba(30, 41, 59, 0.8);
        padding: 8px 18px;
        margin: 0rem -1rem 14px -1rem;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 12px;
    }
    .disclaimer-tag {
        background: #facc15;
        color: #0f172a;
        font-weight: 900;
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 4px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        flex-shrink: 0;
    }
    .disclaimer-text {
        color: #cbd5e1;
        font-size: 12px;
        line-height: 1.35;
    }
    .disclaimer-text strong {
        color: #ffffff;
        font-weight: 600;
    }

    /* 2. PRIMARY NAVIGATION HEADER (Exact Match) */
    .app-header {
        background: #0d1322;
        border: 1px solid rgba(30, 41, 59, 0.9);
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .app-header-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .app-logo-box {
        height: 36px;
        width: 36px;
        border-radius: 12px;
        background: linear-gradient(to top right, #00b074, #00e5a3);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 10px 15px -3px rgba(2, 44, 34, 0.4);
        border: 1px solid rgba(52, 211, 153, 0.3);
        flex-shrink: 0;
    }
    .app-title-wrap {
        display: flex;
        flex-direction: column;
    }
    .app-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 16px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.025em;
        line-height: 1.2;
    }
    .app-subtitle {
        font-size: 11px;
        font-weight: 500;
        color: #94a3b8;
        letter-spacing: 0.025em;
        margin-top: 1px;
    }

    /* Live Pulsing Status Capsule (API Online) */
    .live-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 4px 12px;
        border-radius: 9999px;
        background: rgba(2, 44, 34, 0.7);
        border: 1px solid rgba(5, 150, 105, 0.4);
        color: #00d09c;
        font-size: 11px;
        font-weight: 600;
        box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.2);
    }
    .live-status-fallback {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 4px 12px;
        border-radius: 9999px;
        background: rgba(69, 26, 3, 0.7);
        border: 1px solid rgba(217, 119, 6, 0.4);
        color: #fbbf24;
        font-size: 11px;
        font-weight: 600;
        box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.2);
    }
    .pulse-dot-wrap {
        position: relative;
        display: flex;
        height: 8px;
        width: 8px;
    }
    .pulse-dot-ping {
        position: absolute;
        display: inline-flex;
        height: 100%;
        width: 100%;
        border-radius: 9999px;
        background: #00d09c;
        opacity: 0.75;
        animation: status-ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
    }
    .pulse-dot-core {
        position: relative;
        display: inline-flex;
        border-radius: 9999px;
        height: 8px;
        width: 8px;
        background: #00d09c;
    }
    @keyframes status-ping {
        75%, 100% {
            transform: scale(2.2);
            opacity: 0;
        }
    }

    /* 3. SIDEBAR: SELECT FUND CONTEXT (Obsidian Capital) */
    section[data-testid="stSidebar"] {
        background-color: #0d1320 !important;
        border-right: 1px solid rgba(30, 41, 59, 0.8) !important;
    }
    .sidebar-header-box {
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(30, 41, 59, 0.5);
        margin-bottom: 12px;
    }
    .sidebar-title {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #e2e8f0;
        margin-bottom: 2px;
    }
    .sidebar-subtitle {
        font-size: 12px;
        color: #94a3b8;
        line-height: 1.35;
    }

    /* Scheme Cards in Sidebar */
    .fund-card-box {
        width: 100%;
        text-align: left;
        padding: 13px 14px;
        border-radius: 12px;
        border: 1px solid rgba(30, 41, 59, 0.8);
        background: rgba(16, 23, 38, 0.6);
        margin-bottom: 8px;
        transition: all 200ms ease;
    }
    .fund-card-box:hover {
        background: #131d2e;
        border-color: #334155;
    }
    .fund-card-box-active {
        border-color: #00d09c !important;
        background: #111927 !important;
        box-shadow: 0 0 0 1px #00d09c, 0 4px 20px -2px rgba(0, 208, 156, 0.12) !important;
    }
    .card-top-flex {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    .cat-tag-emerald {
        font-size: 11px;
        font-weight: 500;
        color: #00d09c;
    }
    .cat-tag-slate {
        font-size: 11px;
        font-weight: 500;
        color: #cbd5e1;
    }
    .cat-tag-cyan {
        font-size: 11px;
        font-weight: 500;
        color: #67e8f9;
    }
    .risk-badge-na {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
        background: #1e293b;
        color: #94a3b8;
        border: 1px solid rgba(51, 65, 85, 0.6);
    }
    .risk-badge-vhigh {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(69, 10, 10, 0.6);
        color: #f87171;
        border: 1px solid rgba(153, 27, 27, 0.4);
    }
    .risk-badge-high {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(69, 26, 3, 0.6);
        color: #fbbf24;
        border: 1px solid rgba(180, 83, 9, 0.4);
    }
    .card-title-text {
        font-size: 14px;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.3;
        margin-top: 4px;
    }
    .card-desc-text {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 4px;
        line-height: 1.45;
    }

    /* 4. MAIN CHAT WORKSPACE (Empty State Hero) */
    .hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 35px 16px 20px 16px;
        max-width: 680px;
        margin: 0 auto;
    }
    .hero-sparkle-box {
        width: 56px;
        height: 56px;
        border-radius: 16px;
        background: #091a1d;
        border: 1px solid rgba(0, 208, 156, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #00d09c;
        margin-bottom: 24px;
        box-shadow: 0 0 40px -5px rgba(0, 208, 156, 0.15);
        outline: 1px solid rgba(0, 208, 156, 0.2);
    }
    .hero-main-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 30px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.025em;
        margin-bottom: 8px;
    }
    .hero-scope-text {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 12px;
    }
    .hero-scope-badge {
        font-weight: 600;
        color: #00d09c;
    }
    .hero-instruction {
        font-size: 12px;
        color: #94a3b8;
        max-width: 480px;
        line-height: 1.6;
        margin-bottom: 24px;
    }
    .facts-warning-box {
        width: 100%;
        background: rgba(24, 21, 18, 0.9);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        align-items: flex-start;
        text-align: left;
        gap: 14px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        margin-bottom: 24px;
    }
    .warning-icon {
        color: #fbbf24;
        flex-shrink: 0;
        margin-top: 2px;
    }
    .warning-text {
        font-size: 12px;
        color: rgba(254, 240, 138, 0.9);
        line-height: 1.5;
        font-weight: 400;
    }

    /* 5. SUGGESTIONS ROW (Pill Buttons Strip) */
    .suggestions-label {
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    div[data-testid="stHorizontalBlock"] button {
        background: #131b29 !important;
        border: 1px solid #1e293b !important;
        color: #cbd5e1 !important;
        border-radius: 9999px !important;
        padding: 6px 14px !important;
        font-size: 12px !important;
        font-weight: 400 !important;
        transition: all 150ms ease !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background: #1a2538 !important;
        color: #ffffff !important;
        border-color: #334155 !important;
    }

    /* 6. CHAT MESSAGE TURNS (Clean & Factual) */
    .user-turn-bubble {
        background: #141b2d;
        border: 1px solid #25324e;
        border-radius: 14px 14px 3px 14px;
        padding: 12px 18px;
        max-width: 78%;
        margin-left: auto;
        margin-bottom: 14px;
        font-size: 14px;
        line-height: 1.5;
        color: #f8fafc;
    }
    .assistant-turn-card {
        background: rgba(16, 23, 38, 0.8);
        border: 1px solid rgba(30, 41, 59, 0.8);
        border-left: 3px solid #00d09c;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .assistant-content-text {
        font-size: 14px;
        line-height: 1.6;
        color: #f1f5f9;
        margin-bottom: 10px;
    }
    .source-box {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        border-radius: 8px;
        background: rgba(2, 44, 34, 0.6);
        border: 1px solid rgba(0, 208, 156, 0.3);
        font-size: 12px;
        color: #00d09c;
        font-weight: 500;
        margin-top: 4px;
    }
    .source-box a {
        color: #00d09c !important;
        font-weight: 600;
        text-decoration: none;
    }
    .source-box a:hover {
        text-decoration: underline;
    }

    /* Refusal Alert Card */
    .refusal-alert-card {
        background: rgba(69, 10, 10, 0.25);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-left: 4px solid #ef4444;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .refusal-pill-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
        color: #f87171;
        margin-bottom: 8px;
    }
    .refusal-msg-text {
        font-size: 13px;
        color: rgba(254, 202, 202, 0.95);
        line-height: 1.55;
        margin-bottom: 12px;
    }
    .refusal-actions-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .refusal-btn {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #f1f5f9;
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 12px;
        text-decoration: none;
        transition: background 150ms ease;
    }
    .refusal-btn:hover {
        background: #334155;
    }

    /* 7. FLOATING CHAT INPUT BAR & BOTTOM CONTAINER (Dark Styled) */
    div[data-testid="stBottom"],
    div[data-testid="stBottomBlockContainer"],
    div[data-testid="stChatInputContainer"],
    footer {
        background-color: #0b0f19 !important;
        background: #0b0f19 !important;
        border: none !important;
    }

    div[data-testid="stChatInput"] {
        background-color: #121824 !important;
        background: #121824 !important;
        border: 1px solid #1e293b !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6) !important;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: rgba(0, 208, 156, 0.8) !important;
        box-shadow: 0 0 0 1px rgba(0, 208, 156, 0.4), 0 10px 25px -5px rgba(0, 0, 0, 0.6) !important;
    }
    div[data-testid="stChatInput"] > div {
        background-color: #121824 !important;
        background: #121824 !important;
        border: none !important;
    }
    div[data-testid="stChatInput"] textarea {
        background-color: #121824 !important;
        background: #121824 !important;
        color: #f1f5f9 !important;
        font-size: 14px !important;
        border: none !important;
        caret-color: #00d09c !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #94a3b8 !important;
        opacity: 0.85 !important;
    }
    div[data-testid="stChatInput"] button {
        background-color: #1f293d !important;
        color: #cbd5e1 !important;
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    div[data-testid="stChatInput"] button:hover {
        background-color: #28354f !important;
        color: #00d09c !important;
    }
    </style>
    """
)


# ----------------------------------------------------------------------
# Backend Integration Helpers (Dual-Mode: REST API / Standalone Pipeline)
# ----------------------------------------------------------------------
def is_api_online() -> bool:
    """Check if FastAPI server is responsive."""
    try:
        r = requests.get(f"{API_BASE_URL}/api/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def api_list_threads() -> List[Dict[str, Any]]:
    """Fetch threads via API or local thread_manager fallback."""
    if is_api_online():
        try:
            r = requests.get(f"{API_BASE_URL}/api/threads", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    import sqlite3
    with sqlite3.connect(str(thread_manager.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT t.thread_id, t.title, t.created_at, t.updated_at,
                   COUNT(m.message_id) AS message_count
            FROM threads t
            LEFT JOIN messages m ON t.thread_id = m.thread_id
            GROUP BY t.thread_id
            ORDER BY t.updated_at DESC;
            """
        )
        return [dict(r) for r in cur.fetchall()]


def api_create_thread(title: Optional[str] = None) -> str:
    """Create a new thread via API or fallback."""
    if is_api_online():
        try:
            payload = {"title": title} if title else {}
            r = requests.post(f"{API_BASE_URL}/api/threads", json=payload, timeout=3.0)
            if r.status_code == 201:
                return r.json()["thread_id"]
        except Exception:
            pass
    t = thread_manager.create_thread_sync(title=title)
    return t.thread_id


def api_delete_thread(thread_id: str) -> bool:
    """Delete a thread via API or fallback."""
    if is_api_online():
        try:
            r = requests.delete(f"{API_BASE_URL}/api/threads/{thread_id}", timeout=3.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
    return thread_manager.delete_thread_sync(thread_id)


def api_get_messages(thread_id: str) -> List[Dict[str, Any]]:
    """Retrieve thread messages via API or fallback."""
    if is_api_online():
        try:
            r = requests.get(f"{API_BASE_URL}/api/threads/{thread_id}/history", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    msgs = thread_manager.get_thread_history_sync(thread_id)
    return [
        {
            "message_id": m.message_id,
            "thread_id": m.thread_id,
            "role": m.role,
            "content": m.content,
            "source_url": m.source_url,
            "intent": m.intent,
            "created_at": m.created_at,
        }
        for m in msgs
    ]


def api_send_message(query: str, thread_id: str) -> Dict[str, Any]:
    """Send query to chat pipeline via API or in-process RAG pipeline."""
    if is_api_online():
        try:
            r = requests.post(
                f"{API_BASE_URL}/api/chat",
                json={"query": query, "thread_id": thread_id},
                timeout=25.0,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            st.error(f"API chat error ({exc}). Falling back to in-process pipeline.")

    # Fallback to in-process pipeline
    sanitized_query, pii_detected = sanitize_pii(query)

    if is_otp_or_credential(query):
        warning = get_otp_security_warning()
        thread_manager.add_message_sync(thread_id, "user", sanitized_query, intent="SECURITY_ALERT")
        thread_manager.add_message_sync(thread_id, "assistant", warning, intent="SECURITY_ALERT")
        return {
            "answer": warning,
            "thread_id": thread_id,
            "intent": "SECURITY_ALERT",
            "is_refusal": True,
            "source_url": None,
            "scheme_id": None,
            "detected_pii": pii_detected,
        }

    import asyncio
    resolved_query, antecedent_scheme_id = asyncio.run(
        thread_manager.resolve_antecedent_context(sanitized_query, thread_id)
    )

    intent = classify_intent(resolved_query)

    if intent != IntentType.FACTUAL:
        refusal = generate_refusal_response(intent, resolved_query)
        thread_manager.add_message_sync(thread_id, "user", sanitized_query, intent=intent.value)
        thread_manager.add_message_sync(thread_id, "assistant", refusal, intent=intent.value)
        return {
            "answer": refusal,
            "thread_id": thread_id,
            "intent": intent.value,
            "is_refusal": True,
            "source_url": None,
            "scheme_id": None,
            "detected_pii": pii_detected,
        }

    chunks, primary_scheme_id = retrieve_context(resolved_query, n_results=5)
    target_scheme_id = primary_scheme_id or antecedent_scheme_id
    answer = generate_answer(resolved_query, chunks, primary_scheme_id=target_scheme_id)
    canonical_name, canonical_url = get_canonical_citation_for_scheme(target_scheme_id)

    thread_manager.add_message_sync(thread_id, "user", sanitized_query, intent="FACTUAL")
    thread_manager.add_message_sync(thread_id, "assistant", answer, source_url=canonical_url, intent="FACTUAL")

    return {
        "answer": answer,
        "thread_id": thread_id,
        "intent": "FACTUAL",
        "is_refusal": False,
        "source_url": canonical_url,
        "scheme_id": target_scheme_id,
        "detected_pii": pii_detected,
    }


# ----------------------------------------------------------------------
# Session State Initialization
# ----------------------------------------------------------------------
if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id = None

if "preset_prompt" not in st.session_state:
    st.session_state.preset_prompt = None

if "selected_fund_context" not in st.session_state:
    st.session_state.selected_fund_context = "all"


# ----------------------------------------------------------------------
# MAIN WORKSPACE
# ----------------------------------------------------------------------

# Ensure active thread exists
if not st.session_state.active_thread_id:
    st.session_state.active_thread_id = api_create_thread()

# 1. TOP STICKY DISCLAIMER BANNER (Exact Match to screen.png)
render_html(
    """
    <header class="top-disclaimer-bar">
        <span class="disclaimer-tag">DISCLAIMER</span>
        <p class="disclaimer-text">
            This is a <strong>facts-only</strong> assistant for HDFC Mutual Funds. It cannot provide investment advice, personal portfolio details, or performance projections. All information is retrieved directly from official scheme factsheets.
        </p>
    </header>
    """
)

# 2. PRIMARY NAVIGATION HEADER (With Pulsing Status Capsule)
online = is_api_online()
if online:
    status_capsule_html = """
    <div class="live-status-pill">
        <span class="pulse-dot-wrap">
            <span class="pulse-dot-ping"></span>
            <span class="pulse-dot-core"></span>
        </span>
        <span>API Online</span>
    </div>
    """
else:
    status_capsule_html = """
    <div class="live-status-fallback">
        <span style="height: 8px; width: 8px; border-radius: 9999px; background: #fbbf24; display: inline-block;"></span>
        <span>In-Process RAG</span>
    </div>
    """

render_html(
    f"""
    <nav class="app-header">
        <div class="app-header-left">
            <div class="app-logo-box">
                <svg style="width: 20px; height: 20px; color: #0d1322;" fill="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" fill="none" r="9" stroke="currentColor" stroke-width="3"></circle>
                    <path d="M12 9v6" stroke="currentColor" stroke-linecap="round" stroke-width="3"></path>
                </svg>
            </div>
            <div class="app-title-wrap">
                <h1 class="app-title">HDFC Mutual Fund FAQ</h1>
                <p class="app-subtitle">RAG Chatbot</p>
            </div>
        </div>
        <div>
            {status_capsule_html}
        </div>
    </nav>
    """
)

# Active Fund Context Object
curr_ctx_id = st.session_state.get("selected_fund_context", "all")
curr_ctx = next((c for c in FUND_CONTEXTS if c["id"] == curr_ctx_id), FUND_CONTEXTS[0])

# Retrieve messages
messages = api_get_messages(st.session_state.active_thread_id)

# Quick New Chat Action Bar (Visible when active conversation exists)
if messages:
    bar_col1, bar_col2 = st.columns([5, 1])
    with bar_col1:
        render_html('<div style="font-size: 12px; color: #94a3b8; padding-top: 6px;">Active Chat Session • Facts retrieved from audited HDFC scheme factsheets</div>')
    with bar_col2:
        if st.button("➕ New Chat", key="btn_new_chat_top", use_container_width=True, help="Start a new chat session"):
            st.session_state.active_thread_id = api_create_thread()
            st.rerun()

# 3. ZERO-STATE SCREEN (Exact Match to screen.png & code.html)
if not messages:
    render_html(
        """
        <div class="hero-container">
            <div class="hero-sparkle-box">
                <svg style="width: 28px; height: 28px;" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2L13.8 8.8L20.6 10.6L13.8 12.4L12 19.2L10.2 12.4L3.4 10.6L10.2 8.8L12 2Z"></path>
                </svg>
            </div>
            <div class="hero-main-title">HDFC Mutual Fund Assistant</div>
            <div class="hero-scope-text">
                Factual Scope: <span class="hero-scope-badge">All 5 HDFC Mutual Fund Schemes</span>
            </div>
            <div class="hero-instruction">
                Ask specific factual questions about investment guidelines, exit loads, minimum investments, fund managers, and scheme rules across Top 100, Mid-Cap, Small Cap, Multi-Cap, and Silver ETF FoF.
            </div>
            <div class="facts-warning-box">
                <div class="warning-icon">
                    <svg style="width: 16px; height: 16px;" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                        <line x1="12" x2="12" y1="9" y2="13"></line>
                        <line x1="12" x2="12.01" y1="17" y2="17"></line>
                    </svg>
                </div>
                <div class="warning-text">
                    This assistant enforces facts-only guardrails. Queries asking for investment advice, returns performance, or containing personal identification numbers (PAN, Aadhaar) will be refused automatically.
                </div>
            </div>
        </div>
        """
    )


# 4. MESSAGE HISTORY RENDERER (Clean Factual Narrative + Verified Official Reference)
for msg_idx, msg in enumerate(messages):
    role = msg.get("role", "user")
    raw_content = msg.get("content", "")
    intent = msg.get("intent", "FACTUAL")
    source_url = msg.get("source_url")

    if role == "user":
        # Sanitize any HTML in user content to prevent code block or injection
        clean_user = re.sub(r"</?[a-zA-Z][^>]*>", "", raw_content)
        render_html(
            f"""
            <div class="user-turn-bubble">
                {clean_user}
            </div>
            """
        )
    else:
        is_refusal = intent in ("ADVISORY", "COMPARATIVE_OPINION", "SPECULATIVE_RETURNS", "JAILBREAK", "SECURITY_ALERT")

        if is_refusal:
            clean_refusal = re.sub(r"</?[a-zA-Z][^>]*>", "", raw_content)
            render_html(
                f"""
                <div class="refusal-alert-card">
                    <div class="refusal-pill-tag">
                        <svg style="width: 14px; height: 14px;" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
                        </svg>
                        <span>Regulatory Refusal: Non-Factual Query Intercepted</span>
                    </div>
                    <div class="refusal-msg-text">{clean_refusal}</div>
                    <div class="refusal-actions-row">
                        <a href="https://www.amfiindia.com" target="_blank" class="refusal-btn">AMFI Investor Corner ↗</a>
                        <a href="https://investor.sebi.gov.in" target="_blank" class="refusal-btn">SEBI Investor Education ↗</a>
                    </div>
                </div>
                """
            )
        else:
            parsed = parse_assistant_response(raw_content, default_url=source_url)

            # Official reference citation HTML
            citation_html = ""
            if parsed["citation_url"]:
                citation_html = (
                    f'<div class="source-box">'
                    f'<svg style="width: 14px; height: 14px; color: #00d09c; flex-shrink: 0;" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" viewBox="0 0 24 24">'
                    f'<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>'
                    f'</svg>'
                    f'<span><strong>Official Reference:</strong> <a href="{parsed["citation_url"]}" target="_blank">{parsed["citation_anchor"]}</a></span>'
                    f'</div>'
                )

            render_html(
                f"""
                <div class="assistant-turn-card">
                    <div class="assistant-content-text">{parsed["narrative"]}</div>
                    {citation_html}
                </div>
                """
            )


# ----------------------------------------------------------------------
# 5. SUGGESTIONS ROW (Exact Match to screen.png & code.html)
# ----------------------------------------------------------------------
suggestions_list = [
    "What is the minimum SIP for HDFC Top 100?",
    "What is the exit load on HDFC Mid-Cap?",
    "What is 3Y CAGR & 5Y SIP return for Small Cap?",
    "What is the expense ratio of HDFC Silver ETF FoF?",
]

render_html('<div class="suggestions-label">SUGGESTIONS:</div>')
sugg_cols = st.columns(len(suggestions_list))
for idx, sugg_text in enumerate(suggestions_list):
    with sugg_cols[idx]:
        if st.button(sugg_text, key=f"sugg_btn_{idx}", use_container_width=True):
            st.session_state.preset_prompt = sugg_text
            st.rerun()


# ----------------------------------------------------------------------
# 6. FLOATING INPUT BAR
# ----------------------------------------------------------------------
incoming_prompt = None
if st.session_state.preset_prompt:
    incoming_prompt = st.session_state.preset_prompt
    st.session_state.preset_prompt = None

user_query = st.chat_input("Ask anything about HDFC Mutual Funds...") or incoming_prompt

if user_query:
    active_tid = st.session_state.active_thread_id

    # If scoped to a specific scheme and not explicitly named in query, augment context
    effective_query = user_query
    if curr_ctx_id != "all":
        scheme_name = curr_ctx["name"]
        keywords = ["hdfc", "top 100", "large cap", "mid-cap", "mid cap", "small cap", "multi-cap", "multi cap", "silver"]
        if not any(k in user_query.lower() for k in keywords):
            effective_query = f"{user_query} for {scheme_name}"

    clean_q = re.sub(r"</?[a-zA-Z][^>]*>", "", user_query)
    render_html(
        f"""
        <div class="user-turn-bubble">
            {clean_q}
        </div>
        """
    )

    with st.spinner("Retrieving verified facts from ChromaDB..."):
        response_data = api_send_message(effective_query, active_tid)

    st.rerun()
