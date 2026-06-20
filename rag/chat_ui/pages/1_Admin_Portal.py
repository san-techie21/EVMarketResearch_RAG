"""
Admin Portal - pipeline monitoring, source management, automation, user management.

Role access:
  superadmin → full access (run pipelines, upload YouTube, manage users, toggle schedules)
  superuser  → read-only  (view all stats, logs, and user list - no actions)
  user       → blocked    (redirected back to chat)
"""
import sys
import subprocess
import threading
import time
import secrets
import string
import bcrypt
from pathlib import Path
from datetime import datetime, timezone

import yaml
from yaml.loader import SafeLoader

sys.path.insert(0, str(Path(__file__).parents[3]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[3] / "config" / ".env", override=True)

import streamlit as st

from rag.chat_ui.ragas_eval import start_ragas_scheduler
from rag.chat_ui.pipeline_db import (
    ensure_pipeline_tables,
    get_source_chunk_counts,
    get_source_chunk_count,
    get_total_chunk_count,
    get_chunks_by_app_source,
    get_run_history,
    get_last_run,
    get_running_sources,
    get_schedules,
    update_schedule,
    mark_schedule_ran,
    get_overdue_sources,
    log_run_start,
    log_run_finish,
    SOURCES,
)

# -- Page config ---------------------------------------------------------------
st.set_page_config(
    page_title="Admin Portal - Home Energy & EV Research",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT          = Path(__file__).parents[3]
YOUTUBE_SUMMARIES_DIR = PROJECT_ROOT / "data" / "raw" / "text" / "youtube_summaries"
CONFIG_PATH           = PROJECT_ROOT / "config" / "users.yaml"

APPS = [
    # EV Charging
    "chargepoint", "evgo", "blink", "plugshare", "electrify_america",
    "flo", "evcs", "shell_recharge", "tesla",
    # Prosumer / Home Energy
    "tesla_powerwall", "enphase", "solaredge", "emporia",
    "sense", "sunpower", "generac", "span",
    # General
    "general",
]

SOURCE_META = {
    "google_play": {"icon": "📱", "label": "Google Play Reviews"},
    "app_store":   {"icon": "🍎", "label": "App Store Reviews"},
    "news":        {"icon": "📰", "label": "News (RSS)"},
    "web_pages":   {"icon": "🌐", "label": "Web Pages"},
    "youtube":     {"icon": "🎬", "label": "YouTube Summaries"},
}

ROLE_OPTS = ["superadmin", "superuser", "user"]
ROLE_LABELS = {"superadmin": "Superadmin", "superuser": "Superuser", "user": "User"}
ROLE_COLORS = {
    "superadmin": ("linear-gradient(135deg,#4f46e5,#7c3aed)", "#eef2ff", "#4338ca"),
    "superuser":  ("linear-gradient(135deg,#059669,#10b981)", "#f0fdf4", "#166534"),
    "user":       ("linear-gradient(135deg,#64748b,#94a3b8)", "#f8fafc", "#475569"),
}


# -- Auth guard ----------------------------------------------------------------
if not st.session_state.get("authentication_status"):
    st.warning("Please log in from the main chat page first.")
    st.page_link("app.py", label="← Go to Login", icon="💬")
    st.stop()

username     = st.session_state["username"]
display_name = st.session_state["name"]

with open(CONFIG_PATH) as f:
    _auth_cfg = yaml.load(f, Loader=SafeLoader)

role = _auth_cfg["credentials"]["usernames"].get(username, {}).get("role", "user")

if role == "user":
    st.error("⛔ Access denied. Admin Portal requires Superadmin or Superuser access.")
    st.page_link("app.py", label="← Back to Chat", icon="💬")
    st.stop()

is_superadmin = (role == "superadmin")

# -- DB setup ------------------------------------------------------------------
ensure_pipeline_tables()


# -- Background pipeline runner ------------------------------------------------
def _run_pipeline_bg(source: str):
    def _execute():
        chunks_before = get_source_chunk_count(source)
        run_id        = log_run_start(source, chunks_before)
        try:
            proc = subprocess.run(
                [sys.executable, "pipeline/run_pipeline.py", "--source", source],
                capture_output=True, text=True,
                cwd=str(PROJECT_ROOT), timeout=600,
            )
            chunks_after = get_source_chunk_count(source)
            status       = "done" if proc.returncode == 0 else "error"
            log_output   = (proc.stdout + "\n" + proc.stderr).strip()
            log_run_finish(run_id, status, chunks_after, log_output)
            if status == "done":
                mark_schedule_ran(source)
        except subprocess.TimeoutExpired:
            log_run_finish(run_id, "error",
                           get_source_chunk_count(source), "Timed out after 10 minutes.")
        except Exception as e:
            log_run_finish(run_id, "error", get_source_chunk_count(source), str(e))

    threading.Thread(target=_execute, daemon=True).start()


# -- Weekly background scheduler (module-level singleton) ---------------------
_SCHED_STARTED = False
_SCHED_LOCK    = threading.Lock()

def _scheduler_loop():
    while True:
        time.sleep(1800)
        try:
            running = set(get_running_sources())
            for src in get_overdue_sources():
                if src not in running:
                    _run_pipeline_bg(src)
        except Exception:
            pass

def _start_scheduler():
    global _SCHED_STARTED
    with _SCHED_LOCK:
        if not _SCHED_STARTED:
            _SCHED_STARTED = True
            threading.Thread(target=_scheduler_loop, daemon=True,
                             name="ev-pipeline-scheduler").start()

_start_scheduler()
start_ragas_scheduler()   # RAGAs async quality evaluator


# -- User management helpers ---------------------------------------------------
def _load_cfg() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.load(f, Loader=SafeLoader)

def _save_cfg(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()

def _gen_pw(length: int = 12) -> str:
    """Generate a secure random password (uppercase + lowercase + digits + symbols)."""
    pool = string.ascii_letters + string.digits + "!#$%"
    # Guarantee at least one of each character class
    pw = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!#$%"),
    ]
    pw += [secrets.choice(pool) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)

def _count_superadmins(cfg: dict) -> int:
    return sum(
        1 for u in cfg["credentials"]["usernames"].values()
        if u.get("role") == "superadmin"
    )


# -- Global CSS ----------------------------------------------------------------
st.markdown("""
<style>
/* Source / stat cards */
.src-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 1.1rem 1.3rem 0.9rem 1.3rem;
    margin-bottom: 0.85rem;
}
.src-card-title { font-size: 0.97rem; font-weight: 600; color: #0f172a; margin: 0; }
.src-card-meta  { font-size: 0.79rem; color: #64748b; margin: 0; }
.src-card-count { font-size: 1.6rem; font-weight: 700; color: #4f46e5; line-height: 1; }

.stat-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.2rem; text-align:center; }
.stat-value { font-size:2rem; font-weight:700; color:#0f172a; line-height:1.1; }
.stat-label { font-size:0.78rem; color:#64748b; margin-top:0.25rem; }

/* Status pills */
.pill           { display:inline-block; font-size:0.72rem; font-weight:600; padding:0.2rem 0.6rem; border-radius:999px; letter-spacing:0.03em; }
.pill-idle      { background:#f1f5f9; color:#475569; }
.pill-running   { background:#fef9c3; color:#92400e; }
.pill-done      { background:#dcfce7; color:#166534; }
.pill-error     { background:#fee2e2; color:#991b1b; }

/* Role badge */
.role-badge     { display:inline-block; font-size:0.72rem; font-weight:700; padding:0.2rem 0.65rem; border-radius:999px; letter-spacing:0.04em; text-transform:uppercase; }
.role-superadmin{ background:#eef2ff; color:#4338ca; border:1px solid #c7d2fe; }
.role-superuser { background:#f0fdf4; color:#166534; border:1px solid #bbf7d0; }

/* View-only banner */
.view-only-banner { background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:0.55rem 1rem; font-size:0.83rem; color:#92400e; margin-bottom:1.2rem; }

/* Log output */
.log-row { font-size:0.82rem; font-family:"SF Mono","Fira Code",monospace; color:#475569; background:#f8fafc; padding:0.6rem 0.85rem; border-radius:6px; white-space:pre-wrap; word-break:break-word; max-height:280px; overflow-y:auto; border:1px solid #e2e8f0; }

/* Section label */
.section-label { font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; color:#94a3b8; margin:1.2rem 0 0.5rem 0; }

/* Upload hint */
.upload-hint { font-size:0.78rem; color:#64748b; background:#f1f5f9; border:1px dashed #cbd5e1; border-radius:8px; padding:0.6rem 0.85rem; margin-bottom:0.5rem; }

/* User row */
.user-row-name  { font-weight:600; color:#0f172a; margin:0.35rem 0 0 0; font-size:0.9rem; }
.user-row-email { color:#475569; margin:0.35rem 0 0 0; font-size:0.83rem; font-family:monospace; }

/* Add-user / reset-pw panel */
.action-panel { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:1rem 1.1rem 0.9rem 1.1rem; margin:0.25rem 0 0.75rem 0; }
</style>
""", unsafe_allow_html=True)


# -- Page header ---------------------------------------------------------------
role_class = "role-superadmin" if is_superadmin else "role-superuser"
role_label = "Superadmin" if is_superadmin else "Superuser · View Only"

hdr_l, hdr_r = st.columns([5, 1])
with hdr_l:
    st.markdown(
        "<h2 style='margin:0;font-size:1.35rem;color:#0f172a;'>⚙️ Admin Portal</h2>"
        "<p style='font-size:0.82rem;color:#94a3b8;margin:0.1rem 0 1rem 0;'>"
        "Pipeline management · Data sources · Automation · Users</p>",
        unsafe_allow_html=True,
    )
with hdr_r:
    st.markdown(
        f"<div style='text-align:right;padding-top:0.4rem;'>"
        f"<span class='role-badge {role_class}'>{role_label}</span>"
        f"<br><span style='font-size:0.75rem;color:#94a3b8;margin-top:0.3rem;display:block;'>"
        f"{display_name}</span></div>",
        unsafe_allow_html=True,
    )

if not is_superadmin:
    st.markdown(
        "<div class='view-only-banner'>👁️ <strong>View-only mode.</strong> "
        "You can monitor pipelines, logs, and users, but cannot trigger runs, "
        "upload files, manage users, or change settings.</div>",
        unsafe_allow_html=True,
    )

# -- Tabs ----------------------------------------------------------------------
tab_overview, tab_sources, tab_auto, tab_logs, tab_users = st.tabs([
    "📊  Overview",
    "🗄️  Data Sources",
    "⏰  Automation",
    "📋  Run Logs",
    "👥  Users",
])


# ==============================================================================
# TAB 1 - OVERVIEW
# ==============================================================================
with tab_overview:

    @st.cache_data(ttl=60)
    def _overview_data():
        counts    = get_source_chunk_counts()
        total     = sum(counts.values())
        schedules = get_schedules()
        enabled   = sum(1 for s in schedules if s["enabled"])
        history   = get_run_history(limit=1)
        last_run  = history[0]["started_at"] if history else None
        by_app    = get_chunks_by_app_source()
        return counts, total, enabled, last_run, by_app

    counts, total, enabled_count, last_run_ts, by_app = _overview_data()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div class='stat-card'><div class='stat-value'>{total:,}</div>"
            f"<div class='stat-label'>Total chunks in KB</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='stat-card'><div class='stat-value'>{enabled_count}/{len(SOURCES)}</div>"
            f"<div class='stat-label'>Sources on weekly schedule</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        if last_run_ts:
            now  = datetime.now(timezone.utc)
            diff = now - last_run_ts.replace(tzinfo=timezone.utc)
            hrs  = int(diff.total_seconds() // 3600)
            ago  = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
        else:
            ago = "Never"
        st.markdown(
            f"<div class='stat-card'><div class='stat-value'>{ago}</div>"
            f"<div class='stat-label'>Last pipeline run</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<p class='section-label'>Chunks by source</p>", unsafe_allow_html=True)
    source_order = ["google_play", "app_store", "news", "web_pages", "youtube"]
    chart_data   = {SOURCE_META[s]["label"]: counts.get(s, 0) for s in source_order}
    st.bar_chart(chart_data, height=220, color="#4f46e5")

    with st.expander("Chunks by app × source", expanded=False):
        from collections import defaultdict
        import pandas as pd
        pivot: dict = defaultdict(lambda: defaultdict(int))
        for row in by_app:
            pivot[row["app_name"]][row["source"]] += row["count"]
        rows = []
        for app in sorted(pivot.keys()):
            r = {"App": app}
            total_app = 0
            for src in source_order:
                v = pivot[app].get(src, 0)
                r[SOURCE_META[src]["label"]] = v
                total_app += v
            r["Total"] = total_app
            rows.append(r)
        df = pd.DataFrame(rows).set_index("App")
        st.dataframe(df, use_container_width=True)


# ==============================================================================
# TAB 2 - DATA SOURCES
# ==============================================================================
with tab_sources:

    counts  = get_source_chunk_counts()
    running = set(get_running_sources())

    for source in SOURCES:
        meta       = SOURCE_META[source]
        count      = counts.get(source, 0)
        last_run   = get_last_run(source)
        is_running = source in running

        if is_running:
            pill = "<span class='pill pill-running'>⏳ Running</span>"
        elif last_run is None:
            pill = "<span class='pill pill-idle'>○ Never run</span>"
        elif last_run["status"] == "done":
            pill = "<span class='pill pill-done'>✓ Last run OK</span>"
        else:
            pill = "<span class='pill pill-error'>✕ Last run failed</span>"

        if last_run:
            now  = datetime.now(timezone.utc)
            diff = now - last_run["started_at"].replace(tzinfo=timezone.utc)
            hrs  = int(diff.total_seconds() // 3600)
            ago  = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
            meta_txt = f"{count:,} chunks &nbsp;·&nbsp; last run {ago}"
        else:
            meta_txt = f"{count:,} chunks &nbsp;·&nbsp; never ingested"

        st.markdown(
            f"<div class='src-card'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.35rem;'>"
            f"<p class='src-card-title'>{meta['icon']} &nbsp;{meta['label']}</p>"
            f"<span class='src-card-count'>{count:,}</span></div>"
            f"<p class='src-card-meta'>{meta_txt} &nbsp;·&nbsp; {pill}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

        btn_col, _ = st.columns([1, 5 if source != "youtube" else 3])
        with btn_col:
            if is_superadmin:
                if st.button(
                    "⏳ Running…" if is_running else "▶  Run Now",
                    key=f"run_{source}", disabled=is_running, use_container_width=True,
                ):
                    _run_pipeline_bg(source)
                    st.toast(f"✅ {meta['label']} pipeline started!", icon="🚀")
                    time.sleep(0.4)
                    st.rerun()
            else:
                st.button("▶  Run Now", key=f"run_{source}_ro",
                          disabled=True, use_container_width=True,
                          help="Superadmin only")

        if source == "youtube" and is_superadmin:
            st.markdown(
                "<div class='upload-hint'>📄 <strong>Upload a new summary .txt file.</strong> "
                "Header format: Title:, Video ID:, URL:, then blank line, then body.</div>",
                unsafe_allow_html=True,
            )
            u1, u2 = st.columns([1, 2])
            with u1:
                app_choice = st.selectbox("App folder", APPS, key="yt_app_select")
            with u2:
                uploaded = st.file_uploader("Choose .txt file", type=["txt"],
                                            key="yt_uploader",
                                            label_visibility="collapsed")
            if uploaded is not None:
                content = uploaded.read().decode("utf-8")
                with st.expander(f"📄 Preview - {uploaded.name}", expanded=False):
                    st.text(content[:1500] + ("…" if len(content) > 1500 else ""))
                if st.button("✅  Save & Ingest", key="yt_upload_btn", type="primary"):
                    dest = YOUTUBE_SUMMARIES_DIR / app_choice
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / uploaded.name).write_text(content, encoding="utf-8")
                    st.success(f"Saved to `youtube_summaries/{app_choice}/{uploaded.name}`")
                    _run_pipeline_bg("youtube")
                    st.toast("🎬 YouTube pipeline started.", icon="✅")
                    time.sleep(0.4)
                    st.rerun()
        elif source == "youtube" and not is_superadmin:
            st.info("📄 YouTube file uploads are restricted to Superadmin.", icon="🔒")

        st.markdown("<div style='margin-bottom:0.3rem'></div>", unsafe_allow_html=True)


# ==============================================================================
# TAB 3 - AUTOMATION
# ==============================================================================
with tab_auto:

    st.markdown(
        "<p style='font-size:0.9rem;color:#475569;margin-bottom:1.2rem;'>"
        "When enabled, each source runs automatically <strong>every 7 days</strong>. "
        "A background thread checks every 30 minutes and fires any overdue jobs.</p>",
        unsafe_allow_html=True,
    )

    schedules = get_schedules()
    sched_map = {s["source"]: s for s in schedules}

    if is_superadmin:
        changes: dict[str, bool] = {}
        for source in SOURCES:
            meta    = SOURCE_META[source]
            s       = sched_map.get(source, {})
            enabled = s.get("enabled", False)
            last_r  = s.get("last_run_at")
            next_r  = s.get("next_run_at")

            c_ic, c_nm, c_tog, c_last, c_next = st.columns([0.5, 3, 1.5, 2, 2])
            with c_ic:
                st.markdown(f"<p style='font-size:1.4rem;margin:0.5rem 0'>{meta['icon']}</p>",
                            unsafe_allow_html=True)
            with c_nm:
                st.markdown(f"<p style='font-weight:600;color:#0f172a;margin:0.55rem 0 0 0;'>"
                            f"{meta['label']}</p>", unsafe_allow_html=True)
            with c_tog:
                changes[source] = st.toggle("Enable", value=enabled,
                                             key=f"sched_{source}",
                                             label_visibility="collapsed")
            with c_last:
                if last_r:
                    diff = datetime.now(timezone.utc) - last_r.replace(tzinfo=timezone.utc)
                    hrs  = int(diff.total_seconds() // 3600)
                    txt  = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
                else:
                    txt = "-"
                st.markdown(f"<p style='font-size:0.82rem;color:#64748b;margin:0.55rem 0 0 0;'>"
                            f"Last: {txt}</p>", unsafe_allow_html=True)
            with c_next:
                if next_r and changes[source]:
                    diff = next_r.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
                    hrs  = int(diff.total_seconds() // 3600)
                    nxt  = f"in {hrs}h" if hrs >= 0 else "overdue"
                elif changes[source]:
                    nxt = "in ~7 days"
                else:
                    nxt = "-"
                st.markdown(f"<p style='font-size:0.82rem;color:#64748b;margin:0.55rem 0 0 0;'>"
                            f"Next: {nxt}</p>", unsafe_allow_html=True)
            st.divider()

        if st.button("💾  Save Schedule", type="primary", key="save_sched"):
            for src, val in changes.items():
                update_schedule(src, val)
            st.success("✅ Schedule saved.")
            st.rerun()
    else:
        import pandas as pd
        rows = []
        now = datetime.now(timezone.utc)
        for source in SOURCES:
            meta = SOURCE_META[source]
            s    = sched_map.get(source, {})
            lr   = s.get("last_run_at")
            nr   = s.get("next_run_at")
            en   = s.get("enabled", False)
            if lr:
                diff = now - lr.replace(tzinfo=timezone.utc)
                hrs  = int(diff.total_seconds() // 3600)
                last_txt = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
            else:
                last_txt = "Never"
            if nr and en:
                diff = nr.replace(tzinfo=timezone.utc) - now
                hrs  = int(diff.total_seconds() // 3600)
                next_txt = f"in {hrs}h" if hrs >= 0 else "Overdue"
            else:
                next_txt = "-"
            rows.append({
                "Source":   f"{meta['icon']} {meta['label']}",
                "Schedule": "Every 7 days",
                "Enabled":  "✅ Yes" if en else "○ No",
                "Last Run": last_txt,
                "Next Run": next_txt,
            })
        st.dataframe(pd.DataFrame(rows).set_index("Source"), use_container_width=True)


# ==============================================================================
# TAB 4 - RUN LOGS
# ==============================================================================
with tab_logs:

    lf_col, ref_col = st.columns([5, 1])
    with lf_col:
        src_filter = st.selectbox("Filter by source",
                                  ["All sources"] + SOURCES, key="log_filter",
                                  label_visibility="collapsed")
    with ref_col:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    history = get_run_history(limit=50)
    if src_filter != "All sources":
        history = [h for h in history if h["source"] == src_filter]

    if not history:
        st.info("No pipeline runs recorded yet. Use Data Sources → Run Now to start one.")
    else:
        now = datetime.now(timezone.utc)
        for run in history:
            status = run["status"]
            meta   = SOURCE_META.get(run["source"], {"icon": "📦", "label": run["source"]})
            diff   = now - run["started_at"].replace(tzinfo=timezone.utc)
            hrs    = int(diff.total_seconds() // 3600)
            ago    = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
            dur_s  = run.get("duration_secs") or 0
            dur    = f"{dur_s // 60}m {dur_s % 60}s" if dur_s else "-"

            if status == "running":
                status_html = "<span class='pill pill-running'>⏳ Running</span>"
            elif status == "done":
                added = run.get("chunks_added", 0)
                status_html = (f"<span class='pill pill-done'>✓ Done</span>"
                               f"<span style='font-size:0.78rem;color:#166534;margin-left:0.5rem;'>"
                               f"+{added:,} chunks</span>")
            else:
                status_html = "<span class='pill pill-error'>✕ Error</span>"

            c1, c2, c3, c4 = st.columns([2, 2.5, 2.5, 1.2])
            with c1:
                st.markdown(f"<p style='font-size:0.82rem;color:#64748b;margin:0.4rem 0;'>{ago}</p>",
                            unsafe_allow_html=True)
            with c2:
                st.markdown(f"<p style='font-size:0.85rem;font-weight:500;color:#0f172a;margin:0.35rem 0;'>"
                            f"{meta['icon']} {meta['label']}</p>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<p style='margin:0.35rem 0;'>{status_html}</p>",
                            unsafe_allow_html=True)
            with c4:
                st.markdown(f"<p style='font-size:0.8rem;color:#94a3b8;margin:0.4rem 0;'>{dur}</p>",
                            unsafe_allow_html=True)

            if run.get("log_output"):
                with st.expander("View log output", expanded=False):
                    st.markdown(f"<div class='log-row'>{run['log_output']}</div>",
                                unsafe_allow_html=True)
            st.divider()


# ==============================================================================
# TAB 5 - USERS
# ==============================================================================
with tab_users:

    # -- Description + Add button ------------------------------------------
    desc_col, add_col = st.columns([5, 1])
    cfg        = _load_cfg()
    users_dict = cfg["credentials"]["usernames"]

    with desc_col:
        n_sa = sum(1 for u in users_dict.values() if u.get("role") == "superadmin")
        n_su = sum(1 for u in users_dict.values() if u.get("role") == "superuser")
        n_u  = sum(1 for u in users_dict.values() if u.get("role") == "user")
        st.markdown(
            f"<p style='font-size:0.88rem;color:#475569;margin-bottom:0.75rem;'>"
            f"{len(users_dict)} total &nbsp;·&nbsp; "
            f"<span style='color:#4338ca;font-weight:600;'>{n_sa} Superadmin</span> &nbsp;·&nbsp; "
            f"<span style='color:#166534;font-weight:600;'>{n_su} Superuser</span> &nbsp;·&nbsp; "
            f"{n_u} User</p>",
            unsafe_allow_html=True,
        )
    with add_col:
        if is_superadmin:
            if st.button("＋  Add User", type="primary",
                         use_container_width=True, key="open_add_user"):
                st.session_state["show_add_user"] = (
                    not st.session_state.get("show_add_user", False)
                )
                st.session_state.pop("nu_pw", None)

    # -- Add New User panel -------------------------------------------------
    if is_superadmin and st.session_state.get("show_add_user"):
        st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
        st.markdown(
            "<p style='font-weight:700;font-size:1rem;color:#0f172a;margin:0 0 0.75rem 0;'>"
            "➕ New User</p>",
            unsafe_allow_html=True,
        )
        f1, f2 = st.columns(2)
        with f1:
            nu_name  = st.text_input("Display Name *", key="nu_name",
                                     placeholder="e.g. Jane Smith")
            nu_uname = st.text_input("Email / Username *", key="nu_uname",
                                     placeholder="jane.smith@company.com")
        with f2:
            nu_role = st.selectbox("Role", ROLE_OPTS, index=2, key="nu_role",
                                   format_func=lambda r: ROLE_LABELS[r])
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            if st.button("🔀  Generate Password", key="nu_gen"):
                st.session_state["nu_pw"] = _gen_pw()

        nu_pw = st.session_state.get("nu_pw", "")
        if nu_pw:
            st.markdown(
                "<p style='font-size:0.8rem;color:#64748b;margin:0.4rem 0 0.15rem 0;'>"
                "🔑 Generated password - copy before saving:</p>",
                unsafe_allow_html=True,
            )
            st.code(nu_pw, language=None)

            # Shareable credentials block
            with st.expander("📋 Copy shareable credentials", expanded=False):
                share_text = (
                    f"Home Energy & EV App Research - Login Credentials\n"
                    f"{'-'*45}\n"
                    f"URL:      https://168.144.26.72\n"
                    f"Username: {st.session_state.get('nu_uname', '').strip() or '<email>'}\n"
                    f"Password: {nu_pw}\n"
                    f"Role:     {ROLE_LABELS.get(st.session_state.get('nu_role', 'user'), 'User')}\n"
                    f"{'-'*45}\n"
                    f"Please log in and confirm access."
                )
                st.code(share_text, language=None)

            st.caption("⚠️ Password is shown once. After saving, only the hash is stored.")

        c_save, c_cancel = st.columns(2)
        with c_save:
            if st.button("✅  Create User", type="primary", key="nu_save",
                         disabled=not nu_pw, use_container_width=True):
                name_val  = st.session_state.get("nu_name", "").strip()
                uname_val = st.session_state.get("nu_uname", "").strip()
                role_val  = st.session_state.get("nu_role", "user")
                if not name_val:
                    st.error("Display name is required.")
                elif not uname_val:
                    st.error("Email / username is required.")
                elif uname_val in users_dict:
                    st.error(f"Username '{uname_val}' already exists.")
                else:
                    cfg["credentials"]["usernames"][uname_val] = {
                        "name":     name_val,
                        "password": _hash_pw(nu_pw),
                        "role":     role_val,
                    }
                    _save_cfg(cfg)
                    for k in ["show_add_user", "nu_name", "nu_uname", "nu_pw", "nu_role"]:
                        st.session_state.pop(k, None)
                    st.toast(f"✅ User '{uname_val}' created.", icon="🎉")
                    st.rerun()
        with c_cancel:
            if st.button("Cancel", key="nu_cancel", use_container_width=True):
                for k in ["show_add_user", "nu_name", "nu_uname", "nu_pw", "nu_role"]:
                    st.session_state.pop(k, None)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # -- Column headers -----------------------------------------------------
    h_av, h_nm, h_em, h_rl, h_ac = st.columns([0.4, 2.2, 3.2, 2, 1.8])
    for col, lbl in zip(
        [h_av, h_nm, h_em, h_rl, h_ac],
        ["", "Name", "Email / Username", "Role", "Actions"],
    ):
        col.markdown(
            f"<p style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.09em;color:#94a3b8;margin:0;'>{lbl}</p>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='margin:0.3rem 0 0.5rem 0;border:none;border-top:2px solid #e2e8f0;'>",
        unsafe_allow_html=True,
    )

    # -- User rows ----------------------------------------------------------
    for uname, udata in list(users_dict.items()):
        uname_display = udata.get("name", uname)
        u_role        = udata.get("role", "user")
        is_self       = (uname == username)
        av_grad, _, _ = ROLE_COLORS.get(u_role, ROLE_COLORS["user"])

        av_col, nm_col, em_col, rl_col, ac_col = st.columns([0.4, 2.2, 3.2, 2, 1.8])

        with av_col:
            st.markdown(
                f"<div style='width:30px;height:30px;border-radius:50%;"
                f"background:{av_grad};display:flex;align-items:center;"
                f"justify-content:center;font-size:0.8rem;color:#fff;"
                f"font-weight:700;margin-top:0.25rem;'>"
                f"{uname_display[0].upper()}</div>",
                unsafe_allow_html=True,
            )

        with nm_col:
            self_tag = (" <span style='font-size:0.68rem;color:#94a3b8;"
                        "font-weight:400;'>(you)</span>") if is_self else ""
            st.markdown(
                f"<p class='user-row-name'>{uname_display}{self_tag}</p>",
                unsafe_allow_html=True,
            )

        with em_col:
            st.markdown(
                f"<p class='user-row-email'>{uname}</p>",
                unsafe_allow_html=True,
            )

        with rl_col:
            if is_superadmin:
                new_role = st.selectbox(
                    "role", ROLE_OPTS,
                    index=ROLE_OPTS.index(u_role) if u_role in ROLE_OPTS else 2,
                    key=f"role_sel_{uname}",
                    label_visibility="collapsed",
                    disabled=is_self,           # cannot change own role
                    format_func=lambda r: ROLE_LABELS[r],
                )
                if new_role != u_role and not is_self:
                    # Prevent removing the last superadmin
                    if u_role == "superadmin" and _count_superadmins(cfg) <= 1:
                        st.error("Cannot remove the last Superadmin.")
                        st.rerun()
                    else:
                        cfg["credentials"]["usernames"][uname]["role"] = new_role
                        _save_cfg(cfg)
                        st.toast(f"Role updated for {uname_display}.", icon="✅")
                        st.rerun()
            else:
                _, rbg, rc = ROLE_COLORS.get(u_role, ROLE_COLORS["user"])
                st.markdown(
                    f"<p style='margin:0.35rem 0 0 0;'>"
                    f"<span style='font-size:0.75rem;font-weight:600;padding:0.2rem 0.55rem;"
                    f"border-radius:999px;background:{rbg};color:{rc};'>"
                    f"{ROLE_LABELS.get(u_role, u_role)}</span></p>",
                    unsafe_allow_html=True,
                )

        with ac_col:
            if is_superadmin:
                pw_col, del_col = st.columns(2)
                with pw_col:
                    if st.button("🔑", key=f"pwbtn_{uname}",
                                 help="Reset password", use_container_width=True):
                        k = f"show_reset_{uname}"
                        st.session_state[k] = not st.session_state.get(k, False)
                        st.session_state.pop(f"reset_pw_gen_{uname}", None)
                with del_col:
                    if st.button(
                        "🗑️", key=f"delbtn_{uname}",
                        help="Cannot delete yourself" if is_self else "Delete user",
                        disabled=is_self, use_container_width=True,
                    ):
                        k = f"confirm_del_{uname}"
                        st.session_state[k] = not st.session_state.get(k, False)

        # -- Reset password panel -------------------------------------------
        if is_superadmin and st.session_state.get(f"show_reset_{uname}"):
            st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
            st.markdown(
                f"<p style='font-weight:700;color:#0f172a;margin:0 0 0.6rem 0;'>"
                f"🔑 Reset password for <em>{uname_display}</em></p>",
                unsafe_allow_html=True,
            )
            rg1, rg2 = st.columns([4, 1])
            with rg2:
                if st.button("🔀 Generate", key=f"reset_gen_{uname}",
                             use_container_width=True):
                    st.session_state[f"reset_pw_gen_{uname}"] = _gen_pw()

            reset_pw = st.session_state.get(f"reset_pw_gen_{uname}", "")
            if reset_pw:
                st.markdown(
                    "<p style='font-size:0.8rem;color:#64748b;margin:0.2rem 0 0.1rem 0;'>"
                    "New password - copy before saving:</p>",
                    unsafe_allow_html=True,
                )
                st.code(reset_pw, language=None)
                with st.expander("📋 Copy shareable credentials", expanded=False):
                    share_text = (
                        f"Home Energy & EV App Research - Updated Credentials\n"
                        f"{'-'*45}\n"
                        f"URL:      https://168.144.26.72\n"
                        f"Username: {uname}\n"
                        f"Password: {reset_pw}\n"
                        f"{'-'*45}"
                    )
                    st.code(share_text, language=None)
                rs1, rs2 = st.columns(2)
                with rs1:
                    if st.button("✅ Save Password", key=f"reset_save_{uname}",
                                 type="primary", use_container_width=True):
                        cfg["credentials"]["usernames"][uname]["password"] = _hash_pw(reset_pw)
                        _save_cfg(cfg)
                        for k in [f"show_reset_{uname}", f"reset_pw_gen_{uname}"]:
                            st.session_state.pop(k, None)
                        st.toast(f"Password reset for {uname_display}.", icon="🔑")
                        st.rerun()
                with rs2:
                    if st.button("Cancel", key=f"reset_cancel_{uname}",
                                 use_container_width=True):
                        for k in [f"show_reset_{uname}", f"reset_pw_gen_{uname}"]:
                            st.session_state.pop(k, None)
                        st.rerun()
            else:
                with rg1:
                    st.info("Click Generate to create a new random password.", icon="ℹ️")
                if st.button("Close", key=f"reset_close_{uname}"):
                    st.session_state.pop(f"show_reset_{uname}", None)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # -- Delete confirmation panel --------------------------------------
        if is_superadmin and st.session_state.get(f"confirm_del_{uname}"):
            is_last_sa = (u_role == "superadmin" and _count_superadmins(cfg) <= 1)
            if is_last_sa:
                st.error("⛔ Cannot delete the last Superadmin account.")
                st.session_state.pop(f"confirm_del_{uname}", None)
            else:
                st.warning(
                    f"⚠️ Delete **{uname_display}** (`{uname}`)? "
                    f"Their chat history will remain in the database."
                )
                dc1, dc2, _ = st.columns([1, 1, 2])
                with dc1:
                    if st.button(f"🗑️ Yes, Delete", key=f"del_yes_{uname}",
                                 type="primary", use_container_width=True):
                        del cfg["credentials"]["usernames"][uname]
                        _save_cfg(cfg)
                        st.session_state.pop(f"confirm_del_{uname}", None)
                        st.toast(f"'{uname_display}' deleted.", icon="🗑️")
                        st.rerun()
                with dc2:
                    if st.button("Cancel", key=f"del_cancel_{uname}",
                                 use_container_width=True):
                        st.session_state.pop(f"confirm_del_{uname}", None)
                        st.rerun()

        st.markdown(
            "<hr style='margin:0.35rem 0;border:none;border-top:1px solid #f1f5f9;'>",
            unsafe_allow_html=True,
        )
