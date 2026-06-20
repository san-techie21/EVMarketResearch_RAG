"""
Observability Dashboard - RAG inference & pipeline metrics.

Access: superadmin (full) / superuser (read-only same view) / user (blocked)
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parents[3]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[3] / "config" / ".env", override=True)

import yaml
from yaml.loader import SafeLoader
import streamlit as st
import pandas as pd

from rag.chat_ui.obs_db import (
    ensure_obs_tables,
    get_kpi_stats,
    get_daily_volume,
    get_latency_trend,
    get_app_distribution,
    get_token_trend,
    get_recent_queries,
    get_recent_errors,
    get_ragas_kpis,
    get_ragas_trend,
    get_low_scoring_queries,
    get_unevaluated_queries,
)
from rag.chat_ui.ragas_eval import run_eval_batch, EVAL_MODEL
from rag.chat_ui.pipeline_db import (
    ensure_pipeline_tables,
    get_run_history,
    get_source_chunk_counts,
    SOURCES,
)

# -- Page config ----------------------------------------------------------------
st.set_page_config(
    page_title="Observability - EV Research",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONFIG_PATH = Path(__file__).parents[3] / "config" / "users.yaml"

SOURCE_META = {
    "google_play": {"icon": "📱", "label": "Google Play"},
    "app_store":   {"icon": "🍎", "label": "App Store"},
    "news":        {"icon": "📰", "label": "News"},
    "web_pages":   {"icon": "🌐", "label": "Web Pages"},
    "youtube":     {"icon": "🎬", "label": "YouTube"},
}

# -- Auth guard -----------------------------------------------------------------
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
    st.error("⛔ Access denied. Observability requires Superadmin or Superuser access.")
    st.page_link("app.py", label="← Back to Chat", icon="💬")
    st.stop()

# -- DB setup -------------------------------------------------------------------
ensure_obs_tables()
ensure_pipeline_tables()

# -- CSS ------------------------------------------------------------------------
st.markdown("""
<style>
.kpi-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 1rem 1.2rem; text-align: center;
}
.kpi-value { font-size: 1.9rem; font-weight: 700; color: #0f172a; line-height: 1.1; }
.kpi-label { font-size: 0.74rem; color: #64748b; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-sub   { font-size: 0.7rem; color: #94a3b8; margin-top: 0.1rem; }

.section-label {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.09em; color: #94a3b8; margin: 1.5rem 0 0.6rem 0;
}
.pill-ok    { display:inline-block; font-size:0.72rem; font-weight:600; padding:0.18rem 0.55rem; border-radius:999px; background:#dcfce7; color:#166534; }
.pill-err   { display:inline-block; font-size:0.72rem; font-weight:600; padding:0.18rem 0.55rem; border-radius:999px; background:#fee2e2; color:#991b1b; }
.pill-warn  { display:inline-block; font-size:0.72rem; font-weight:600; padding:0.18rem 0.55rem; border-radius:999px; background:#fef9c3; color:#92400e; }
.q-row      { font-size: 0.83rem; color: #0f172a; }
.q-meta     { font-size: 0.75rem; color: #64748b; }
.error-row  { background: #fff5f5; border-left: 3px solid #f87171; padding: 0.5rem 0.75rem; border-radius: 0 6px 6px 0; margin-bottom: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# -- Header ---------------------------------------------------------------------
st.markdown(
    "<h2 style='margin:0;font-size:1.35rem;color:#0f172a;'>📈 Observability</h2>"
    "<p style='font-size:0.82rem;color:#94a3b8;margin:0.1rem 0 1rem 0;'>"
    "RAG inference metrics · Pipeline health · Query log</p>",
    unsafe_allow_html=True,
)

# refresh
ref_col, _ = st.columns([1, 7])
with ref_col:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# -- Tabs -----------------------------------------------------------------------
tab_inference, tab_ragas, tab_pipeline, tab_queries, tab_errors = st.tabs([
    "🤖  Inference",
    "🧪  RAGAs Quality",
    "⚙️  Pipeline",
    "📋  Query Log",
    "🚨  Errors",
])


# ==============================================================================
# TAB 1 - INFERENCE
# ==============================================================================
with tab_inference:

    @st.cache_data(ttl=60)
    def _load_inference():
        return (
            get_kpi_stats(),
            get_daily_volume(14),
            get_latency_trend(7),
            get_app_distribution(),
            get_token_trend(7),
        )

    kpi, daily_vol, lat_trend, app_dist, tok_trend = _load_inference()

    # -- KPI row -----------------------------------------------------------
    st.markdown("<p class='section-label'>Last 7 days</p>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    def _kpi(col, value, label, sub=""):
        col.markdown(
            f"<div class='kpi-card'>"
            f"<div class='kpi-value'>{value}</div>"
            f"<div class='kpi-label'>{label}</div>"
            f"{'<div class=kpi-sub>' + sub + '</div>' if sub else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )

    _kpi(k1, f"{kpi.get('queries_today', 0):,}",    "Queries Today",     f"{kpi.get('queries_7d',0):,} this week")
    _kpi(k2, f"{kpi.get('total_queries', 0):,}",    "Total Queries",     "all time")
    _kpi(k3, f"{kpi.get('avg_latency_ms') or '-'} ms", "Avg Latency",    "end-to-end (7d)")
    _kpi(k4, f"{kpi.get('p95_latency_ms') or '-'} ms", "P95 Latency",    "95th percentile (7d)")
    _kpi(k5, f"{kpi.get('errors_7d', 0):,}",        "Errors",            "last 7 days")
    _kpi(k6, f"{(kpi.get('tokens_today') or 0):,}", "Tokens Today",      f"{(kpi.get('tokens_7d') or 0):,} this week")

    st.markdown("<div style='margin-top:1.2rem'></div>", unsafe_allow_html=True)

    # -- Query volume chart ------------------------------------------------
    chart_l, chart_r = st.columns(2)

    with chart_l:
        st.markdown("<p class='section-label'>Query volume - last 14 days</p>", unsafe_allow_html=True)
        if daily_vol:
            df_vol = pd.DataFrame(daily_vol)
            df_vol["day"] = pd.to_datetime(df_vol["day"]).dt.strftime("%b %d")
            df_vol = df_vol.set_index("day")
            st.bar_chart(df_vol[["queries", "errors"]], height=200,
                         color=["#4f46e5", "#f87171"])
        else:
            st.info("No queries logged yet.")

    with chart_r:
        st.markdown("<p class='section-label'>Latency breakdown - last 7 days (ms)</p>", unsafe_allow_html=True)
        if lat_trend:
            df_lat = pd.DataFrame(lat_trend)
            df_lat["day"] = pd.to_datetime(df_lat["day"]).dt.strftime("%b %d")
            df_lat = df_lat.set_index("day")
            st.bar_chart(
                df_lat[["avg_retrieve_ms", "avg_generate_ms"]],
                height=200,
                color=["#6366f1", "#f59e0b"],
            )
            st.caption("🟣 Retrieve (embed + vector search)  🟡 Generate (Claude API)")
        else:
            st.info("No latency data yet.")

    # -- App distribution + Token trend -----------------------------------
    dist_l, dist_r = st.columns(2)

    with dist_l:
        st.markdown("<p class='section-label'>Queries by app filter</p>", unsafe_allow_html=True)
        if app_dist:
            df_dist = pd.DataFrame(app_dist).set_index("app_label")
            st.bar_chart(df_dist["queries"], height=200, color="#10b981")
        else:
            st.info("No data yet.")

    with dist_r:
        st.markdown("<p class='section-label'>Token usage - last 7 days</p>", unsafe_allow_html=True)
        if tok_trend:
            df_tok = pd.DataFrame(tok_trend)
            df_tok["day"] = pd.to_datetime(df_tok["day"]).dt.strftime("%b %d")
            df_tok = df_tok.set_index("day")
            st.bar_chart(
                df_tok[["input_tokens", "output_tokens"]],
                height=200,
                color=["#4f46e5", "#a5b4fc"],
            )
            st.caption("🟣 Input tokens  🔵 Output tokens")
        else:
            st.info("No token data yet.")


# ==============================================================================
# TAB 2 - RAGAs QUALITY
# ==============================================================================
with tab_ragas:

    @st.cache_data(ttl=60)
    def _load_ragas():
        return get_ragas_kpis(), get_ragas_trend(14), get_low_scoring_queries(0.6)

    ragas_kpi, ragas_trend, low_scores = _load_ragas()
    pending_count = len(get_unevaluated_queries(limit=1))

    # -- Header explanation ------------------------------------------------
    st.markdown("""
    <div style='background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;
    padding:0.8rem 1.1rem;margin-bottom:1.2rem;font-size:0.84rem;color:#0c4a6e;'>
    <strong>🧪 RAGAs - Retrieval Augmented Generation Assessment</strong><br>
    Uses <em>Claude Haiku as an LLM judge</em> to score every query automatically
    in the background (batch of 10, every 30 min). No ground truth required.<br><br>
    <strong>Faithfulness</strong> - Does the answer only use info from the retrieved chunks?
    (Detects hallucinations) &nbsp;·&nbsp;
    <strong>Answer Relevancy</strong> - Does the answer address what was asked?
    &nbsp;·&nbsp;
    <strong>Context Precision</strong> - Were the retrieved chunks relevant to the question?
    </div>
    """, unsafe_allow_html=True)

    # -- Manual trigger ----------------------------------------------------
    is_superadmin_here = (role == "superadmin")
    trig_col, status_col = st.columns([2, 5])
    with trig_col:
        if is_superadmin_here:
            if st.button("▶  Run Evaluation Now", type="primary",
                         use_container_width=True, key="ragas_run_now"):
                with st.spinner("Running RAGAs evaluation batch…"):
                    import threading
                    result_holder = {}
                    def _run():
                        try:
                            result_holder["n"] = run_eval_batch()
                        except Exception as exc:
                            result_holder["err"] = str(exc)
                    t = threading.Thread(target=_run)
                    t.start()
                    t.join(timeout=120)
                if "err" in result_holder:
                    st.error(f"Evaluation failed: {result_holder['err']}")
                else:
                    n = result_holder.get("n", 0)
                    st.success(f"✅ Evaluated {n} queries." if n else
                               "ℹ️ No pending queries to evaluate.")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("Superadmin only to trigger manual evaluation.", icon="🔒")
    with status_col:
        total_eval = ragas_kpi.get("total_evaluated") or 0
        st.markdown(
            f"<p style='font-size:0.82rem;color:#64748b;margin:0.6rem 0;'>"
            f"<strong>{total_eval}</strong> queries evaluated (last 7d) &nbsp;·&nbsp; "
            f"<strong>{pending_count}+</strong> pending &nbsp;·&nbsp; "
            f"Judge model: <code>{EVAL_MODEL}</code></p>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)

    # -- KPI cards ---------------------------------------------------------
    st.markdown("<p class='section-label'>Average scores - last 7 days (0-1, higher is better)</p>",
                unsafe_allow_html=True)

    def _score_color(v):
        if v is None: return "#94a3b8", "#f8fafc"
        if v >= 0.8:  return "#166534", "#dcfce7"   # green
        if v >= 0.6:  return "#92400e", "#fef9c3"   # amber
        return "#991b1b", "#fee2e2"                   # red

    rk1, rk2, rk3, rk4 = st.columns(4)
    for col, label, key, hint in [
        (rk1, "Faithfulness",       "avg_faithfulness",      "Hallucination detector"),
        (rk2, "Answer Relevancy",   "avg_answer_relevancy",  "Response quality"),
        (rk3, "Context Precision",  "avg_context_precision", "Retrieval quality"),
        (rk4, "Queries Evaluated",  "total_evaluated",       "Last 7 days"),
    ]:
        val = ragas_kpi.get(key)
        if key == "total_evaluated":
            display = f"{val or 0}"
            tc, bg   = "#0f172a", "#f8fafc"
        else:
            display = f"{val:.2f}" if val is not None else "-"
            tc, bg   = _score_color(val)
        col.markdown(
            f"<div class='kpi-card' style='border-color:{bg};'>"
            f"<div class='kpi-value' style='color:{tc};font-size:2rem'>{display}</div>"
            f"<div class='kpi-label'>{label}</div>"
            f"<div class='kpi-sub'>{hint}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

    # -- Trend chart -------------------------------------------------------
    st.markdown("<p class='section-label'>Score trends - last 14 days</p>", unsafe_allow_html=True)
    if ragas_trend:
        df_ragas = pd.DataFrame(ragas_trend)
        df_ragas["day"] = pd.to_datetime(df_ragas["day"]).dt.strftime("%b %d")
        df_ragas = df_ragas.set_index("day")
        cols_to_plot = [c for c in
                        ["avg_faithfulness","avg_answer_relevancy","avg_context_precision"]
                        if c in df_ragas.columns and df_ragas[c].notna().any()]
        if cols_to_plot:
            st.line_chart(df_ragas[cols_to_plot], height=220,
                          color=["#4f46e5","#10b981","#f59e0b"][:len(cols_to_plot)])
            st.caption("🟣 Faithfulness &nbsp; 🟢 Answer Relevancy &nbsp; 🟡 Context Precision")
        else:
            st.info("Scores will appear here after the first evaluation batch runs.")
    else:
        st.info("No RAGAs data yet - trigger an evaluation above or wait for the scheduled run.")

    # -- Low-scoring queries -----------------------------------------------
    if low_scores:
        st.markdown("<p class='section-label'>⚠️ Low-scoring queries (any metric < 0.6)</p>",
                    unsafe_allow_html=True)
        for row in low_scores:
            diff = datetime.now(timezone.utc) - row["created_at"].replace(tzinfo=timezone.utc)
            hrs  = int(diff.total_seconds() // 3600)
            ago  = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"

            def _badge(v, label):
                if v is None: return f"<span style='color:#94a3b8'>{label}: -</span>"
                tc, bg = _score_color(v)
                return (f"<span style='background:{bg};color:{tc};font-size:0.7rem;"
                        f"font-weight:600;padding:0.15rem 0.45rem;border-radius:999px;"
                        f"margin-right:4px'>{label}: {v:.2f}</span>")

            badges = (
                _badge(row.get("faithfulness"),      "Faith") +
                _badge(row.get("answer_relevancy"),  "Relevancy") +
                _badge(row.get("context_precision"), "Precision")
            )
            st.markdown(
                f"<div style='background:#fffbeb;border:1px solid #fde68a;"
                f"border-radius:8px;padding:0.55rem 0.85rem;margin-bottom:0.4rem;'>"
                f"<p style='font-size:0.83rem;font-weight:600;color:#0f172a;margin:0 0 0.3rem 0;'>"
                f"{row['question']}</p>"
                f"<p style='margin:0;'>{badges}"
                f"<span style='font-size:0.7rem;color:#94a3b8;margin-left:0.5rem;'>"
                f"{row['username'] or '?'} · {ago}</span></p>"
                f"</div>",
                unsafe_allow_html=True,
            )
    elif total_eval > 0:
        st.success("✅ No low-scoring queries detected.")


# ==============================================================================
# TAB 3 - PIPELINE
# ==============================================================================
with tab_pipeline:

    @st.cache_data(ttl=60)
    def _load_pipeline():
        return get_source_chunk_counts(), get_run_history(limit=20)

    chunk_counts, run_history = _load_pipeline()

    st.markdown("<p class='section-label'>Knowledge base size</p>", unsafe_allow_html=True)
    pc1, pc2, pc3, pc4, pc5, pc6 = st.columns(6)
    cols = [pc1, pc2, pc3, pc4, pc5, pc6]
    source_order = ["google_play", "app_store", "news", "web_pages", "youtube"]
    total_chunks = sum(chunk_counts.values())
    _kpi(cols[0], f"{total_chunks:,}", "Total Chunks", "all sources")
    for i, src in enumerate(source_order):
        meta = SOURCE_META[src]
        _kpi(cols[i + 1], f"{chunk_counts.get(src, 0):,}", meta["label"], meta["icon"])

    st.markdown("<p class='section-label'>Recent pipeline runs</p>", unsafe_allow_html=True)

    if not run_history:
        st.info("No pipeline runs recorded. Trigger one from the Admin Portal → Data Sources.")
    else:
        now = datetime.now(timezone.utc)
        for run in run_history[:10]:
            status = run["status"]
            meta   = SOURCE_META.get(run["source"], {"icon": "📦", "label": run["source"]})
            diff   = now - run["started_at"].replace(tzinfo=timezone.utc)
            hrs    = int(diff.total_seconds() // 3600)
            ago    = f"{hrs}h ago" if hrs < 48 else f"{hrs // 24}d ago"
            dur_s  = run.get("duration_secs") or 0
            dur    = f"{dur_s // 60}m {dur_s % 60}s" if dur_s else "-"

            if status == "running":
                pill = "<span class='pill-warn'>⏳ Running</span>"
            elif status == "done":
                added = run.get("chunks_added", 0)
                pill  = f"<span class='pill-ok'>✓ Done +{added:,} chunks</span>"
            else:
                pill  = "<span class='pill-err'>✕ Error</span>"

            r1, r2, r3, r4 = st.columns([2, 2.5, 2.5, 1.5])
            r1.markdown(f"<p class='q-meta' style='margin:0.4rem 0'>{ago}</p>", unsafe_allow_html=True)
            r2.markdown(f"<p class='q-row' style='margin:0.35rem 0'>{meta['icon']} {meta['label']}</p>", unsafe_allow_html=True)
            r3.markdown(f"<p style='margin:0.35rem 0'>{pill}</p>", unsafe_allow_html=True)
            r4.markdown(f"<p class='q-meta' style='margin:0.4rem 0'>{dur}</p>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:0.25rem 0;border:none;border-top:1px solid #f1f5f9;'>", unsafe_allow_html=True)


# ==============================================================================
# TAB 3 - QUERY LOG
# ==============================================================================
with tab_queries:

    @st.cache_data(ttl=30)
    def _load_queries():
        return get_recent_queries(limit=100)

    queries = _load_queries()

    if not queries:
        st.info("No queries logged yet. Ask a question in the chat to see it appear here.")
    else:
        # Filter bar
        flt_user, flt_app, flt_status = st.columns(3)
        users_seen = sorted({q["username"] for q in queries if q["username"]})
        apps_seen  = sorted({q["app_filter"] for q in queries if q["app_filter"]})

        with flt_user:
            sel_user = st.selectbox("User", ["All"] + users_seen, key="ql_user",
                                    label_visibility="collapsed")
        with flt_app:
            sel_app  = st.selectbox("App", ["All"] + apps_seen, key="ql_app",
                                    label_visibility="collapsed")
        with flt_status:
            sel_status = st.selectbox("Status", ["All", "Success", "Error"], key="ql_status",
                                      label_visibility="collapsed")

        filtered = queries
        if sel_user   != "All":     filtered = [q for q in filtered if q["username"]   == sel_user]
        if sel_app    != "All":     filtered = [q for q in filtered if q["app_filter"] == sel_app]
        if sel_status == "Success": filtered = [q for q in filtered if not q["error"]]
        if sel_status == "Error":   filtered = [q for q in filtered if q["error"]]

        st.markdown(
            f"<p style='font-size:0.78rem;color:#64748b;margin:0.3rem 0 0.8rem 0;'>"
            f"Showing {len(filtered)} of {len(queries)} queries</p>",
            unsafe_allow_html=True,
        )

        # Column headers
        h1, h2, h3, h4, h5, h6, h7 = st.columns([3.5, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
        for col, lbl in zip([h1,h2,h3,h4,h5,h6,h7],
                            ["Question","User","App","Latency","Tokens","Top Score","Status"]):
            col.markdown(
                f"<p style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:0.08em;color:#94a3b8;margin:0'>{lbl}</p>",
                unsafe_allow_html=True,
            )
        st.markdown("<hr style='margin:0.3rem 0 0.4rem 0;border:none;border-top:2px solid #e2e8f0;'>",
                    unsafe_allow_html=True)

        now = datetime.now(timezone.utc)
        for q in filtered:
            diff = now - q["created_at"].replace(tzinfo=timezone.utc)
            mins = int(diff.total_seconds() // 60)
            ago  = (f"{mins}m ago" if mins < 60
                    else f"{mins//60}h ago" if mins < 1440
                    else f"{mins//1440}d ago")

            mode_tag = ""
            if q["comparison_mode"]:
                mode_tag = " 🔄"
            elif q["source_filter"]:
                mode_tag = f" [{q['source_filter'][:3]}]"

            app_label = (q["app_filter"] or "all") + mode_tag
            status_pill = ("<span class='pill-err'>✕</span>"
                           if q["error"] else
                           "<span class='pill-ok'>✓</span>")

            c1, c2, c3, c4, c5, c6, c7 = st.columns([3.5, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
            c1.markdown(f"<p class='q-row' style='margin:0.3rem 0'>{q['question']}</p>",
                        unsafe_allow_html=True)
            c2.markdown(f"<p class='q-meta' style='margin:0.35rem 0'>{q['username'] or '-'}<br>{ago}</p>",
                        unsafe_allow_html=True)
            c3.markdown(f"<p class='q-meta' style='margin:0.35rem 0'>{app_label}</p>",
                        unsafe_allow_html=True)
            c4.markdown(f"<p class='q-meta' style='margin:0.35rem 0'>{q['total_ms']:,} ms<br>"
                        f"<span style='font-size:0.68rem'>r:{q['retrieve_ms']} g:{q['generate_ms']}</span></p>",
                        unsafe_allow_html=True)
            tokens = (q["input_tokens"] or 0) + (q["output_tokens"] or 0)
            c5.markdown(f"<p class='q-meta' style='margin:0.35rem 0'>{tokens:,}<br>"
                        f"<span style='font-size:0.68rem'>in:{q['input_tokens']} out:{q['output_tokens']}</span></p>",
                        unsafe_allow_html=True)
            top_s = f"{float(q['top_score']):.3f}" if q["top_score"] else "-"
            c6.markdown(f"<p class='q-meta' style='margin:0.35rem 0'>{top_s}<br>"
                        f"{q['chunks_returned']} chunks</p>",
                        unsafe_allow_html=True)
            c7.markdown(f"<p style='margin:0.35rem 0'>{status_pill}</p>", unsafe_allow_html=True)

            if q["error"]:
                with st.expander("Error detail", expanded=False):
                    st.code(q["error"], language=None)

            st.markdown("<hr style='margin:0.2rem 0;border:none;border-top:1px solid #f1f5f9;'>",
                        unsafe_allow_html=True)


# ==============================================================================
# TAB 4 - ERRORS
# ==============================================================================
with tab_errors:

    @st.cache_data(ttl=60)
    def _load_errors():
        return get_recent_errors(limit=50)

    errors = _load_errors()
    kpi_e  = get_kpi_stats()
    err_7d = kpi_e.get("errors_7d", 0)

    if err_7d == 0:
        st.success("✅ No errors in the last 7 days.")
    else:
        st.warning(f"⚠️ {err_7d} errors in the last 7 days.")

    if not errors:
        st.info("No error records found.")
    else:
        now = datetime.now(timezone.utc)
        for e in errors:
            diff = now - e["created_at"].replace(tzinfo=timezone.utc)
            mins = int(diff.total_seconds() // 60)
            ago  = (f"{mins}m ago" if mins < 60
                    else f"{mins//60}h ago" if mins < 1440
                    else f"{mins//1440}d ago")
            st.markdown(
                f"<div class='error-row'>"
                f"<p style='font-size:0.82rem;font-weight:600;color:#991b1b;margin:0'>"
                f"❌ {e['question']}</p>"
                f"<p style='font-size:0.73rem;color:#94a3b8;margin:0.2rem 0 0.3rem 0'>"
                f"{e['username'] or 'unknown'} · {ago}</p>"
                f"<p style='font-size:0.77rem;color:#7f1d1d;font-family:monospace;"
                f"background:#fff5f5;padding:0.3rem 0.5rem;border-radius:4px;margin:0'>"
                f"{e['error']}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )
