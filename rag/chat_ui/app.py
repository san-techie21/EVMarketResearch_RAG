"""
Streamlit chat UI — Home Energy & EV App Research assistant.
Features: login, per-user persistent chat history, new chat, source/app filters.

Run:  streamlit run rag/chat_ui/app.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)

import os
import yaml
import streamlit as st
import psycopg2
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader

from rag.retriever import (
    MODEL, generate_answer, retrieve, retrieve_by_source, retrieve_per_app,
    ALL_EV_APPS, ALL_PROSUMER_APPS,
)
from rag.chat_ui.session_db import (
    ensure_table, create_session, list_sessions,
    load_messages, save_messages, delete_session,
)
from rag.chat_ui.obs_db import ensure_obs_tables, log_query

# ---------------------------------------------------------------------------
# One-time DB setup
# ---------------------------------------------------------------------------
ensure_table()
ensure_obs_tables()

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Home Energy & EV App Research",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS  —  bright light theme, dark sidebar, mobile-first
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ════════════════════════════════════════════════════════════════════ */
:root {
    /* Sidebar — stays dark */
    --sb-bg:        #111827;
    --sb-bg-hover:  #1f2937;
    --sb-bg-active: #1e2a3a;
    --sb-border:    #1f2937;
    --sb-text:      #d1d5db;
    --sb-text-dim:  #6b7280;
    --sb-text-muted:#374151;

    /* Main area — bright */
    --bg:           #ffffff;
    --bg-surface:   #f8fafc;
    --bg-card:      #f1f5f9;
    --border:       #e2e8f0;
    --border-focus: #4f46e5;

    /* Text */
    --text:         #0f172a;
    --text-2:       #475569;
    --text-3:       #94a3b8;

    /* Accent */
    --accent:       #4f46e5;
    --accent-hover: #4338ca;
    --accent-soft:  #eef2ff;

    /* Chat */
    --user-bubble:  #eef2ff;
    --user-border:  #c7d2fe;
    --assistant-bg: #ffffff;
}

/* ════════════════════════════════════════════════════════════════════
   GLOBAL RESET / BASE
   ════════════════════════════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif !important;
}

/* Force light backgrounds everywhere in the main area */
html, body                               { background: var(--bg) !important; }
.stApp                                   { background: var(--bg) !important; }
[data-testid="stAppViewContainer"]       { background: var(--bg) !important; }
[data-testid="stMain"]                   { background: var(--bg) !important; }
section.main                             { background: var(--bg) !important; }
.block-container                         { background: var(--bg) !important; }

/* Remove default padding/max-width */
.block-container {
    padding-top:    0      !important;
    padding-bottom: 5rem   !important;
    max-width:      860px  !important;
    margin:         0 auto !important;
}

/* Hide Streamlit chrome */
[data-testid="stToolbar"],
[data-testid="stDeployButton"],
[data-testid="stDecoration"],
#MainMenu, footer, header { display: none !important; }

/* ════════════════════════════════════════════════════════════════════
   SIDEBAR
   ════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background-color: var(--sb-bg) !important;
    border-right: 1px solid #1f2937 !important;
    min-width: 255px !important;
    max-width: 255px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 0 1rem 0 !important;
}

/* All sidebar text */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] div {
    color: var(--sb-text) !important;
    font-size: 0.83rem !important;
}
[data-testid="stSidebar"] a { color: #818cf8 !important; }

/* Section labels */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p strong {
    color: var(--sb-text-dim) !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.09em;
}
[data-testid="stSidebar"] hr {
    border-color: #1f2937 !important;
    margin: 0.5rem 0 !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] button {
    border-radius: 7px !important;
    font-size: 0.83rem !important;
    transition: background 0.15s ease !important;
}
[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    color: #9ca3af !important;
    text-align: left !important;
    padding: 0.38rem 0.65rem !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: var(--sb-bg-hover) !important;
    color: #f3f4f6 !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    background: var(--sb-bg-active) !important;
    border: 1px solid #2d3748 !important;
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] button[kind="primary"]:hover {
    background: #243044 !important;
    border-color: #4f46e5 !important;
}

/* Sidebar labels */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stToggle label {
    color: #9ca3af !important;
    font-size: 0.79rem !important;
}

/* Sidebar selectbox */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #1f2937 !important;
    border-color: #374151 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div {
    color: #e2e8f0 !important;
}

/* Sidebar expander */
[data-testid="stSidebar"] .streamlit-expanderHeader {
    background: transparent !important;
    color: var(--sb-text-dim) !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    padding: 0.45rem 0 !important;
    border: none !important;
}
[data-testid="stSidebar"] .streamlit-expanderContent {
    background: transparent !important;
    border: none !important;
    padding: 0.25rem 0 !important;
}

/* Sidebar slider track */
[data-testid="stSidebar"] [data-testid="stSlider"] {
    color: #9ca3af !important;
}
[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #4f46e5 !important;
    border-color: #4f46e5 !important;
}

/* ════════════════════════════════════════════════════════════════════
   SIDEBAR COMPONENTS (HTML)
   ════════════════════════════════════════════════════════════════════ */
.sb-brand {
    padding: 1rem 1rem 0.8rem 1rem;
    border-bottom: 1px solid #1f2937;
    margin-bottom: 0.5rem;
}
.sb-brand-title {
    font-size: 1rem;
    font-weight: 700;
    color: #f1f5f9 !important;
    margin: 0;
}
.sb-brand-sub {
    font-size: 0.71rem;
    color: #6b7280 !important;
    margin: 0.15rem 0 0 0;
}
.sb-user {
    padding: 0.7rem 1rem;
    border-top: 1px solid #1f2937;
    margin-top: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
}
.sb-user-avatar {
    width: 30px; height: 30px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; color: #fff; font-weight: 700;
    flex-shrink: 0;
}
.sb-user-name {
    font-size: 0.83rem;
    font-weight: 500;
    color: #d1d5db !important;
}

/* ════════════════════════════════════════════════════════════════════
   TOPBAR
   ════════════════════════════════════════════════════════════════════ */
.ev-topbar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.85rem 0 0.7rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.2rem;
    background: var(--bg);
}
.ev-topbar-title {
    font-size: 0.97rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
    white-space: nowrap;
}
.ev-topbar-sub {
    font-size: 0.72rem;
    color: var(--text-3);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ════════════════════════════════════════════════════════════════════
   THREE-DOT POPOVER
   ════════════════════════════════════════════════════════════════════ */
[data-testid="stPopover"] button {
    background: var(--bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-2) !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    padding: 0.2rem 0.65rem !important;
    line-height: 1 !important;
    letter-spacing: 0.06em !important;
    min-height: unset !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.06) !important;
}
[data-testid="stPopover"] button:hover {
    background: var(--bg-surface) !important;
    border-color: #cbd5e1 !important;
    color: var(--text) !important;
}
[data-testid="stPopoverBody"] {
    background: var(--bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    min-width: 195px !important;
    padding: 0.55rem 0.8rem !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important;
}
[data-testid="stPopoverBody"] p,
[data-testid="stPopoverBody"] span,
[data-testid="stPopoverBody"] div {
    color: var(--text) !important;
}
[data-testid="stPopoverBody"] button {
    font-size: 0.84rem !important;
    color: var(--text-2) !important;
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    padding: 0.35rem 0.4rem !important;
    width: 100% !important;
    border-radius: 6px !important;
}
[data-testid="stPopoverBody"] button:hover {
    background: var(--bg-surface) !important;
    color: var(--text) !important;
}
[data-testid="stPopoverBody"] hr {
    border-color: var(--border) !important;
    margin: 0.5rem 0 !important;
}

/* ════════════════════════════════════════════════════════════════════
   CHAT MESSAGES
   ════════════════════════════════════════════════════════════════════ */

/* Container */
[data-testid="stChatMessage"] {
    background: var(--assistant-bg) !important;
    border: none !important;
}

/* All paragraph text */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessage"] p {
    font-size: 0.94rem !important;
    line-height: 1.75 !important;
    color: var(--text) !important;
}

/* Inline formatting */
[data-testid="stChatMessage"] strong {
    color: var(--text)   !important;
    font-weight: 600     !important;
}
[data-testid="stChatMessage"] em {
    color: var(--text-2) !important;
}

/* Headings — readable scale, dark color */
[data-testid="stChatMessage"] h1 {
    font-size: 1.15rem   !important;
    font-weight: 700     !important;
    color: var(--text)   !important;
    margin: 1.2rem 0 0.5rem 0 !important;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid var(--border);
}
[data-testid="stChatMessage"] h2 {
    font-size: 1.0rem    !important;
    font-weight: 600     !important;
    color: var(--text)   !important;
    margin: 1rem 0 0.35rem 0 !important;
}
[data-testid="stChatMessage"] h3 {
    font-size: 0.93rem   !important;
    font-weight: 600     !important;
    color: var(--text-2) !important;
    margin: 0.8rem 0 0.3rem 0 !important;
}

/* Lists */
[data-testid="stChatMessage"] ul,
[data-testid="stChatMessage"] ol {
    font-size: 0.94rem  !important;
    line-height: 1.8    !important;
    padding-left: 1.3rem !important;
    color: var(--text)  !important;
}
[data-testid="stChatMessage"] li {
    color: var(--text)  !important;
    margin-bottom: 0.15rem !important;
}

/* Tables — scrollable on mobile */
[data-testid="stChatMessage"] table {
    font-size: 0.85rem   !important;
    width: 100%;
    border-collapse: collapse;
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border: 1px solid var(--border);
    border-radius: 8px;
    margin: 0.75rem 0;
}
[data-testid="stChatMessage"] th {
    background: var(--bg-card) !important;
    font-weight: 600;
    padding: 0.5rem 0.85rem;
    text-align: left;
    color: var(--text)   !important;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
}
[data-testid="stChatMessage"] td {
    padding: 0.42rem 0.85rem;
    border-bottom: 1px solid var(--border);
    color: var(--text)   !important;
}
[data-testid="stChatMessage"] tr:last-child td {
    border-bottom: none;
}
[data-testid="stChatMessage"] tr:hover td {
    background: var(--bg-surface) !important;
}

/* Inline code */
[data-testid="stChatMessage"] code {
    background: var(--bg-card) !important;
    color: #7c3aed          !important;
    font-size: 0.83rem      !important;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    border: 1px solid var(--border);
}
/* Code blocks */
[data-testid="stChatMessage"] pre {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    overflow-x: auto;
}
[data-testid="stChatMessage"] pre code {
    background: transparent !important;
    border: none !important;
    color: var(--text) !important;
}

/* Blockquote */
[data-testid="stChatMessage"] blockquote {
    border-left: 3px solid #c7d2fe;
    padding-left: 0.9rem;
    margin: 0.5rem 0;
    color: var(--text-2) !important;
}

/* ════════════════════════════════════════════════════════════════════
   TOKEN INFO
   ════════════════════════════════════════════════════════════════════ */
.token-info {
    font-size: 0.71rem;
    color: var(--text-3);
    margin-top: 0.4rem;
    line-height: 1.5;
}

/* ════════════════════════════════════════════════════════════════════
   SOURCE EXPANDER (citations)
   ════════════════════════════════════════════════════════════════════ */
.streamlit-expanderHeader {
    background: var(--bg-surface) !important;
    color: var(--text-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}
.streamlit-expanderContent {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 0.25rem 0 !important;
}
.streamlit-expanderContent p,
.streamlit-expanderContent span {
    color: var(--text-2) !important;
    font-size: 0.81rem  !important;
}

/* ════════════════════════════════════════════════════════════════════
   EXAMPLE QUESTION PILLS
   ════════════════════════════════════════════════════════════════════ */
.stButton button[data-testid="baseButton-secondary"] {
    font-size: 0.83rem    !important;
    padding: 0.55rem 0.75rem !important;
    border-radius: 10px   !important;
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-2)  !important;
    white-space: normal   !important;
    text-align: left      !important;
    line-height: 1.45     !important;
    height: auto          !important;
    width: 100%           !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: all 0.15s !important;
}
.stButton button[data-testid="baseButton-secondary"]:hover {
    background: var(--accent-soft) !important;
    border-color: #c7d2fe !important;
    color: #3730a3        !important;
    box-shadow: 0 2px 6px rgba(79,70,229,0.12) !important;
}

/* ════════════════════════════════════════════════════════════════════
   CHAT INPUT
   ════════════════════════════════════════════════════════════════════ */
[data-testid="stChatInput"] {
    border-radius: 12px          !important;
    border: 1.5px solid var(--border) !important;
    background: var(--bg)        !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--accent)  !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.12) !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent      !important;
    color: var(--text)           !important;
    font-size: 0.94rem           !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--text-3)         !important;
}

/* Send button inside chat input */
[data-testid="stChatInput"] button {
    background: var(--accent)    !important;
    border-radius: 8px           !important;
    color: #fff                  !important;
}
[data-testid="stChatInput"] button:hover {
    background: var(--accent-hover) !important;
}

/* ════════════════════════════════════════════════════════════════════
   STATUS WIDGET
   ════════════════════════════════════════════════════════════════════ */
[data-testid="stStatusWidget"],
[data-testid="stStatusWidget"] > div {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
[data-testid="stStatusWidget"] p,
[data-testid="stStatusWidget"] span {
    color: var(--text-2) !important;
    font-size: 0.83rem   !important;
}

/* ════════════════════════════════════════════════════════════════════
   LOGIN PAGE
   ════════════════════════════════════════════════════════════════════ */
.login-outer {
    display: flex;
    justify-content: center;
    margin-top: 8vh;
}
.login-card {
    width: 100%;
    max-width: 380px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2.5rem 2rem 2rem 2rem;
    box-shadow: 0 4px 32px rgba(0,0,0,0.08);
    text-align: center;
}
.login-icon  { font-size: 2.6rem; margin-bottom: 0.6rem; }
.login-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 0.3rem 0;
}
.login-sub {
    font-size: 0.84rem;
    color: var(--text-3);
    margin: 0 0 1.8rem 0;
}

/* Login form fields */
[data-testid="stForm"] label {
    color: var(--text-2) !important;
    font-size: 0.84rem   !important;
    font-weight: 500     !important;
}
[data-testid="stForm"] input {
    background: var(--bg-surface) !important;
    border: 1.5px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-size: 0.93rem !important;
}
[data-testid="stForm"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.1) !important;
}
[data-testid="stForm"] input::placeholder {
    color: var(--text-3) !important;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"],
[data-testid="stForm"] button[kind="primary"] {
    background: var(--accent)      !important;
    border: none                   !important;
    border-radius: 8px             !important;
    color: #fff                    !important;
    font-weight: 600               !important;
    font-size: 0.93rem             !important;
    padding: 0.6rem 1rem           !important;
    width: 100%                    !important;
    transition: background 0.15s   !important;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
[data-testid="stForm"] button[kind="primary"]:hover {
    background: var(--accent-hover) !important;
}

/* ════════════════════════════════════════════════════════════════════
   EMPTY STATE
   ════════════════════════════════════════════════════════════════════ */
.empty-header {
    text-align: center;
    padding: 2.5rem 0 1.2rem 0;
}
.empty-icon  { font-size: 2.4rem; margin-bottom: 0.65rem; }
.empty-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 0.35rem 0;
}
.empty-sub {
    font-size: 0.84rem;
    color: var(--text-3);
    margin: 0 0 1.6rem 0;
}
.empty-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.5rem;
}

/* ════════════════════════════════════════════════════════════════════
   MOBILE  ( ≤ 640 px )
   ════════════════════════════════════════════════════════════════════ */
@media (max-width: 640px) {
    .block-container {
        padding-left:  0.85rem !important;
        padding-right: 0.85rem !important;
        max-width: 100%        !important;
    }
    /* Hide app list subtitle */
    .ev-topbar-sub { display: none !important; }
    /* Compact topbar */
    .ev-topbar { padding: 0.6rem 0 0.5rem 0 !important; margin-bottom: 0.9rem !important; }
    /* Larger readable text on mobile */
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li { font-size: 0.97rem !important; }
    /* Comfortable chat input tap target */
    [data-testid="stChatInput"] textarea {
        font-size: 1rem    !important;
        min-height: 46px   !important;
    }
    /* Token line wraps gracefully */
    .token-info { font-size: 0.67rem !important; }
    /* Full-width login card */
    .login-card {
        margin-top: 3vh;
        border-radius: 12px;
        padding: 2rem 1.25rem 1.5rem 1.25rem;
    }
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Auth setup
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parents[2] / "config" / "users.yaml"
with open(CONFIG_PATH) as f:
    auth_config = yaml.load(f, Loader=SafeLoader)

# SECURITY: the cookie signing key must NOT live in a committed file (anyone with
# the repo could forge auth cookies). Read it from the environment; fall back to
# the yaml value only for local/dev so existing setups keep working.
_cookie_key = os.environ.get("AUTH_COOKIE_KEY") or auth_config["cookie"]["key"]

authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    _cookie_key,
    auth_config["cookie"]["expiry_days"],
    auto_hash=False,
)

# ---------------------------------------------------------------------------
# Login gate
# ---------------------------------------------------------------------------
if not st.session_state.get("authentication_status"):
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="login-card">
            <div class="login-icon">⚡</div>
            <h2 class="login-title">Home Energy &amp; EV App Research</h2>
            <p class="login-sub">
                Competitive intelligence on<br>North American home energy &amp; EV apps
            </p>
        </div>
        """, unsafe_allow_html=True)
        authenticator.login(location="main", key="login_form")
        if st.session_state.get("authentication_status") is False:
            st.error("Incorrect username or password.")
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated
# ---------------------------------------------------------------------------
username: str     = st.session_state["username"]
display_name: str = st.session_state["name"]

# Resolve role from config and cache in session_state
if "role" not in st.session_state:
    _role = auth_config["credentials"]["usernames"].get(username, {}).get("role", "user")
    st.session_state["role"] = _role
role: str = st.session_state["role"]

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def switch_to_session(session_id: str):
    st.session_state.current_session_id = session_id
    st.session_state.messages = load_messages(session_id)


def start_new_chat():
    session_id = create_session(username)
    st.session_state.current_session_id = session_id
    st.session_state.messages = []


if "current_session_id" not in st.session_state:
    sessions = list_sessions(username)
    if sessions:
        switch_to_session(sessions[0]["session_id"])
    else:
        start_new_chat()

if "messages" not in st.session_state:
    st.session_state.messages = load_messages(st.session_state.current_session_id)

# ---------------------------------------------------------------------------
# KB count (cached 5 min)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def _get_kb_counts() -> int:
    # Fixed: previously conn.close() sat after `return` (unreachable) → leaked a
    # connection on every cache miss. Now closed in finally.
    conn = None
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks")
            return cur.fetchone()[0]
    except Exception:
        return 11_322
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CATEGORY_OPTIONS = ["All categories", "EV Charging", "Prosumer"]

CATEGORY_MAP = {
    "EV Charging": "ev_charging",
    "Prosumer":    "prosumer",
}

SOURCE_LABELS = {
    "google_play": "Google Play",
    "app_store":   "App Store",
    "news":        "News",
    "web_pages":   "Website",
    "youtube":     "YouTube",
}

EXAMPLE_QUESTIONS = [
    "What are the most common complaints about ChargePoint?",
    "How does EVgo compare to Electrify America on reliability?",
    "How does Enphase compare to SolarEdge on battery management UX?",
    "Which prosumer apps have the best solar monitoring experience?",
]

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:

    # ── Branding ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="sb-brand">
        <p class="sb-brand-title">⚡ Home Energy &amp; EV Research</p>
        <p class="sb-brand-sub">EV Charging &amp; Prosumer Apps</p>
    </div>
    """, unsafe_allow_html=True)

    # ── New Chat ───────────────────────────────────────────────────────────
    st.markdown("<div style='padding: 0.5rem 0 0.25rem 0;'>", unsafe_allow_html=True)
    if st.button("＋  New Chat", use_container_width=True, type="primary", key="new_chat_btn"):
        start_new_chat()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Recent Chats ───────────────────────────────────────────────────────
    sessions = list_sessions(username)
    if sessions:
        st.markdown(
            "<p style='padding: 0.5rem 0 0.2rem 0;'><strong>Recent chats</strong></p>",
            unsafe_allow_html=True,
        )
        for s in sessions:
            label     = s["title"][:40] + "…" if len(s["title"]) > 40 else s["title"]
            is_active = s["session_id"] == st.session_state.current_session_id
            col_btn, col_del = st.columns([11, 1])
            with col_btn:
                if st.button(
                    label,
                    key=f"sess_{s['session_id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    switch_to_session(s["session_id"])
                    st.rerun()
            with col_del:
                if st.button("×", key=f"del_{s['session_id']}", help="Delete chat"):
                    delete_session(s["session_id"])
                    if s["session_id"] == st.session_state.current_session_id:
                        start_new_chat()
                    st.rerun()

    st.divider()

    # ── Knowledge Base ────────────────────────────────────────────────────
    with st.expander("Knowledge Base", expanded=False):
        kb_counts = _get_kb_counts()
        st.markdown(
            f"Google Play &nbsp; **5,973**  \n"
            f"App Store &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **3,687**  \n"
            f"News articles &nbsp; **1,443**  \n"
            f"Web pages &nbsp;&nbsp;&nbsp;&nbsp; **112**  \n"
            f"YouTube &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **107**  \n"
            f"**Total** &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **{kb_counts:,}**"
        )

    # ── Search Settings ───────────────────────────────────────────────────
    with st.expander("Search Settings", expanded=True):
        comparison_mode = st.toggle(
            "Comparison mode",
            value=False,
            help="Fetches top chunks from every app — best for cross-app questions.",
        )

        category_choice = st.selectbox("Category", CATEGORY_OPTIONS, key="category_choice")
        category_filter = CATEGORY_MAP.get(category_choice)  # None = all

        if comparison_mode:
            app_filter    = None
            source_filter = None
            top_k         = None
            if category_filter == "ev_charging":
                _app_pool = ALL_EV_APPS
            elif category_filter == "prosumer":
                _app_pool = ALL_PROSUMER_APPS
            else:
                _app_pool = ALL_EV_APPS + ALL_PROSUMER_APPS
            n_per_app = st.slider("Chunks per app", min_value=2, max_value=5, value=3)
            st.caption(f"{n_per_app} chunks × {len(_app_pool)} apps = {n_per_app * len(_app_pool)} total")
        else:
            _app_pool = (
                ALL_EV_APPS if category_filter == "ev_charging"
                else ALL_PROSUMER_APPS if category_filter == "prosumer"
                else ALL_EV_APPS + ALL_PROSUMER_APPS
            )
            app_choice = st.selectbox("App", ["All apps"] + _app_pool, key="app_choice")
            app_filter = None if app_choice == "All apps" else app_choice

            source_choice = st.selectbox(
                "Source",
                ["All sources", "youtube", "google_play", "app_store", "news", "web_pages"],
                help="Use 'youtube' to query video content directly.",
            )
            source_filter = None if source_choice == "All sources" else source_choice
            top_k     = st.slider("Chunks to retrieve", min_value=4, max_value=25, value=12)
            n_per_app = None
            _app_pool = None

    # ── User block ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="sb-user">
        <div class="sb-user-avatar">{display_name[0].upper()}</div>
        <span class="sb-user-name">{display_name}</span>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# MAIN — topbar
# ---------------------------------------------------------------------------
topbar_left, topbar_right = st.columns([6, 1])

with topbar_left:
    st.markdown("""
    <div class="ev-topbar">
        <span class="ev-topbar-title">⚡ Home Energy &amp; EV App Research</span>
        <span class="ev-topbar-sub">
            EV Charging · Prosumer &amp; Home Energy Apps
        </span>
    </div>
    """, unsafe_allow_html=True)

with topbar_right:
    st.markdown(
        "<div style='padding-top:0.6rem; display:flex; justify-content:flex-end;'>",
        unsafe_allow_html=True,
    )
    with st.popover("···", use_container_width=False):
        role_colors = {
            "superadmin": ("Superadmin", "#eef2ff", "#4338ca"),
            "superuser":  ("Superuser",  "#f0fdf4", "#166534"),
            "user":       ("User",        "#f8fafc", "#475569"),
        }
        r_label, r_bg, r_color = role_colors.get(role, ("User", "#f8fafc", "#475569"))
        st.markdown(f"""
        <div style="padding:0.3rem 0 0.5rem 0;">
            <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{display_name}</div>
            <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.1rem;">@{username}</div>
            <div style="margin-top:0.4rem;">
                <span style="font-size:0.7rem; font-weight:700; text-transform:uppercase;
                    letter-spacing:0.05em; padding:0.15rem 0.5rem; border-radius:999px;
                    background:{r_bg}; color:{r_color};">{r_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        authenticator.logout(button_name="Sign out", location="main", key="logout_btn")
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# MAIN — chat area
# ---------------------------------------------------------------------------

# Empty state
if not st.session_state.messages:
    st.markdown("""
    <div class="empty-header">
        <div class="empty-icon">💬</div>
        <p class="empty-title">Ask anything about smart energy apps</p>
        <p class="empty-sub">Reviews · News · Videos · Website content across EV &amp; Prosumer apps</p>
        <p class="empty-label">Try one of these</p>
    </div>
    """, unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        col = c1 if i % 2 == 0 else c2
        if col.button(q, use_container_width=True, key=f"eq_{i}"):
            st.session_state.prefill = q
            st.rerun()

# Replay history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            u = msg.get("usage", {})
            if u:
                cache_read = u.get("cache_read_input_tokens", 0)
                cache_str  = f" · cache read {cache_read:,}" if cache_read else ""
                st.markdown(
                    f"<p class='token-info'>Tokens — "
                    f"in {u.get('input_tokens', 0):,} · "
                    f"out {u.get('output_tokens', 0):,} · "
                    f"total {u.get('total_tokens', 0):,}"
                    f"{cache_str} &nbsp;·&nbsp; {MODEL}</p>",
                    unsafe_allow_html=True,
                )
            if msg.get("sources"):
                with st.expander(f"View {len(msg['sources'])} source chunks"):
                    for s in msg["sources"]:
                        label = SOURCE_LABELS.get(s["source"], s["source"])
                        st.markdown(
                            f"**{s['app_name']}** &nbsp;·&nbsp; {label} "
                            f"&nbsp;·&nbsp; score `{s['score']:.3f}`"
                        )
                        st.caption(s["content"])
                        st.divider()

# Chat input
prefill = st.session_state.pop("prefill", None)
prompt  = st.chat_input("Ask a question about EV charging or prosumer apps...") or prefill

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        _q_error     = None
        _retrieve_ms = 0
        _generate_ms = 0

        status = st.status("Searching knowledge base...", expanded=False)
        with status:
            _t0 = time.perf_counter()
            try:
                if comparison_mode:
                    n_apps = len(_app_pool) if _app_pool else len(ALL_EV_APPS + ALL_PROSUMER_APPS)
                    st.write(f"Comparison mode — {n_per_app} chunks × {n_apps} apps...")
                    chunks = retrieve_per_app(prompt, n_per_app=n_per_app,
                                              category_filter=category_filter)
                elif source_filter:
                    st.write(f"Filtering to source: {source_filter}...")
                    chunks = retrieve_by_source(prompt, source=source_filter, top_k=top_k)
                else:
                    st.write("Running similarity search...")
                    chunks = retrieve(prompt, app_filter, top_k,
                                      category_filter=category_filter if not app_filter else None)
            except Exception as exc:
                _q_error = f"Retrieval error: {exc}"
                chunks   = []
            _retrieve_ms = int((time.perf_counter() - _t0) * 1000)
            st.write(f"Retrieved {len(chunks)} chunks. Generating answer...")

        if not chunks and not _q_error:
            answer = "No relevant documents found. Try rephrasing or adjusting the filters."
            sources, usage = [], {}
        elif _q_error:
            answer = "⚠️ An error occurred while searching the knowledge base. Please try again."
            sources, usage = [], {}
        else:
            _t1 = time.perf_counter()
            try:
                answer, usage = generate_answer(prompt, chunks)
            except Exception as exc:
                _q_error = (_q_error or "") + f"Generation error: {exc}"
                answer   = "⚠️ An error occurred while generating the answer. Please try again."
                usage    = {}
            _generate_ms = int((time.perf_counter() - _t1) * 1000)
            sources = [
                {
                    "app_name": c["app_name"],
                    "source":   c["source"],
                    "content":  c["content"][:400] + "…" if len(c["content"]) > 400 else c["content"],
                    "score":    float(c["score"]),
                }
                for c in chunks
            ]

        # ── Observability: log every query (with context for RAGAs eval) ──
        _scores   = [float(c["score"]) for c in chunks] if chunks else []
        _ctx_snap = [
            {"source": c["source"], "app_name": c["app_name"],
             "content": c["content"][:800], "score": float(c["score"])}
            for c in chunks
        ] if chunks else None
        log_query(
            username        = username,
            session_id      = st.session_state.get("current_session_id", ""),
            question        = prompt,
            answer_text     = answer if not _q_error else None,
            context_chunks  = _ctx_snap,
            app_filter      = app_filter if not comparison_mode else None,
            comparison_mode = comparison_mode,
            source_filter   = source_filter if not comparison_mode else None,
            chunks_returned = len(chunks),
            top_score       = max(_scores)              if _scores else None,
            avg_score       = sum(_scores)/len(_scores) if _scores else None,
            retrieve_ms     = _retrieve_ms,
            generate_ms     = _generate_ms,
            input_tokens    = usage.get("input_tokens",  0),
            output_tokens   = usage.get("output_tokens", 0),
            error           = _q_error,
        )

        status.update(label="Done", state="complete")
        st.markdown(answer)

        if usage:
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_str  = f" · cache read {cache_read:,}" if cache_read else ""
            st.markdown(
                f"<p class='token-info'>Tokens — "
                f"in {usage['input_tokens']:,} · "
                f"out {usage['output_tokens']:,} · "
                f"total {usage['total_tokens']:,}"
                f"{cache_str} &nbsp;·&nbsp; {MODEL}</p>",
                unsafe_allow_html=True,
            )

        if sources:
            with st.expander(f"View {len(sources)} source chunks"):
                for s in sources:
                    label = SOURCE_LABELS.get(s["source"], s["source"])
                    st.markdown(
                        f"**{s['app_name']}** &nbsp;·&nbsp; {label} "
                        f"&nbsp;·&nbsp; score `{s['score']:.3f}`"
                    )
                    st.caption(s["content"])
                    st.divider()

    assistant_msg = {
        "role": "assistant", "content": answer,
        "sources": sources, "usage": usage,
    }
    st.session_state.messages.append(assistant_msg)

    title = None
    if len(st.session_state.messages) == 2:
        title = prompt[:60] + ("…" if len(prompt) > 60 else "")

    save_messages(
        st.session_state.current_session_id,
        st.session_state.messages,
        title=title,
    )
