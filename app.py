"""
Contract Review Agent - Main Streamlit Application
A hackathon-ready AI-powered contract analysis tool.
"""
import streamlit as st
import os
import uuid
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Local imports
import database as db
import pdf_parser
import clause_extractor
import risk_analysis as ra
from groq_client import GroqClient
from memory import HindsightMemory

# ─── Config ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Contract Review Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global */
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"] { background: #1a1d27; border-right: 1px solid #2d3148; }

/* Chat bubbles */
.user-bubble {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white; border-radius: 18px 18px 4px 18px;
    padding: 12px 18px; margin: 8px 0; max-width: 80%;
    margin-left: auto; box-shadow: 0 2px 12px rgba(79,70,229,0.3);
}
.assistant-bubble {
    background: #1e2235; color: #e2e8f0;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 18px; margin: 8px 0; max-width: 85%;
    border: 1px solid #2d3148; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.bubble-time { font-size: 0.7rem; opacity: 0.5; margin-top: 4px; }

/* Risk badges */
.risk-high { background:#3d1515; border:1px solid #ff4b4b; border-radius:8px; padding:12px; margin:6px 0; }
.risk-medium { background:#3d2a0a; border:1px solid #ffa500; border-radius:8px; padding:12px; margin:6px 0; }
.risk-low { background:#0a2d1a; border:1px solid #00c853; border-radius:8px; padding:12px; margin:6px 0; }

/* Metric cards */
.metric-card {
    background: #1e2235; border: 1px solid #2d3148;
    border-radius: 12px; padding: 16px; text-align: center;
}
.metric-value { font-size: 2rem; font-weight: 700; }
.metric-label { font-size: 0.8rem; color: #8892b0; margin-top: 4px; }

/* Memory alert */
.memory-alert {
    background: #1a2744; border-left: 4px solid #4f46e5;
    border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 8px 0;
    font-size: 0.9rem; color: #a5b4fc;
}

/* Audit log */
.audit-entry {
    background: #12151f; border: 1px solid #2d3148;
    border-radius: 6px; padding: 8px 12px; margin: 4px 0;
    font-family: monospace; font-size: 0.78rem;
}

/* Status indicator */
.status-dot-green { display:inline-block; width:8px; height:8px; border-radius:50%; background:#00c853; margin-right:6px; }
.status-dot-red { display:inline-block; width:8px; height:8px; border-radius:50%; background:#ff4b4b; margin-right:6px; }

/* Section header */
.section-header {
    font-size: 1.1rem; font-weight: 600; color: #a5b4fc;
    border-bottom: 1px solid #2d3148; padding-bottom: 8px; margin-bottom: 12px;
}

/* Welcome card */
.welcome-card {
    background: linear-gradient(135deg, #1e2235, #252a3d);
    border: 1px solid #2d3148; border-radius: 16px;
    padding: 40px; text-align: center; margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "messages": [],
        "current_contract_id": None,
        "current_contract_text": "",
        "current_analysis": {},
        "audit_log": [],
        "groq_client": None,
        "memory": None,
        "analysis_done": False,
        "processing": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if st.session_state.groq_client is None:
        st.session_state.groq_client = GroqClient()
    if st.session_state.memory is None:
        st.session_state.memory = HindsightMemory()


init_session()
db.init_db()

groq: GroqClient = st.session_state.groq_client
memory: HindsightMemory = st.session_state.memory


# ─── Helper Functions ──────────────────────────────────────────────────────────
def add_message(role: str, content: str):
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M")
    })


def add_audit(entry: Dict):
    st.session_state.audit_log.append(entry)
    if st.session_state.current_contract_id:
        db.save_audit_entry(st.session_state.current_contract_id, entry)


def save_contract_to_db(contract_id: str, filename: str, analysis: Dict, full_text: str):
    risk_data = analysis.get("risks", {})
    missing_data = analysis.get("missing", {})
    clauses_data = analysis.get("clauses", {})
    summary_data = analysis.get("summary", {})

    composite_score = ra.calculate_composite_score(risk_data, missing_data.get("missing_clauses", []), clauses_data)

    db.save_contract({
        "id": contract_id,
        "filename": filename,
        "upload_date": datetime.now().isoformat(),
        "contract_type": summary_data.get("contract_type", "Unknown"),
        "parties": json.dumps(summary_data.get("parties", [])),
        "duration": summary_data.get("duration", ""),
        "key_dates": json.dumps(summary_data.get("key_dates", [])),
        "contract_value": summary_data.get("contract_value", ""),
        "governing_law": summary_data.get("governing_law", ""),
        "risk_score": composite_score,
        "full_text": full_text[:50000],
        "summary_json": json.dumps(summary_data),
        "clauses_json": json.dumps(clauses_data),
        "risks_json": json.dumps(risk_data),
        "missing_clauses_json": json.dumps(missing_data),
        "plain_english": analysis.get("plain_english", ""),
    })
    return composite_score


# ─── Analysis Pipeline ─────────────────────────────────────────────────────────
def run_full_analysis(contract_text: str, contract_id: str, filename: str):
    """Run complete contract analysis pipeline."""
    chunked = pdf_parser.chunk_text(contract_text)
    analysis = {}

    progress = st.progress(0, text="🔍 Starting analysis...")

    # 1. Summary
    progress.progress(10, "📋 Extracting contract summary...")
    resp, audit = groq.analyze_summary(chunked)
    add_audit(audit)
    analysis["summary"] = clause_extractor.parse_summary_response(resp)

    # 2. Clause Extraction
    progress.progress(30, "📑 Extracting clauses...")
    resp, audit = groq.extract_clauses(chunked)
    add_audit(audit)
    analysis["clauses"] = clause_extractor.parse_clauses_response(resp)

    # 3. Risk Analysis (with memory context)
    progress.progress(50, "⚠️ Analyzing risks...")
    memory_ctx = memory.get_memory_context(list(analysis["clauses"].keys()))
    resp, audit = groq.analyze_risks(chunked, memory_ctx)
    add_audit(audit)
    analysis["risks"] = clause_extractor.parse_risk_response(resp)

    # 4. Missing Clauses
    progress.progress(65, "🔎 Checking for missing clauses...")
    resp, audit = groq.detect_missing_clauses(chunked)
    add_audit(audit)
    analysis["missing"] = clause_extractor.parse_missing_clauses_response(resp)

    # 5. Plain English
    progress.progress(80, "💬 Translating to plain English...")
    plain_eng, audit = groq.translate_to_plain_english(chunked)
    add_audit(audit)
    analysis["plain_english"] = plain_eng

    # 6. Save to DB
    progress.progress(90, "💾 Saving results...")
    composite_score = save_contract_to_db(contract_id, filename, analysis, contract_text)
    analysis["composite_score"] = composite_score

    # 7. Save memory
    high_risk_clauses = [r["clause"] for r in analysis["risks"].get("high_risks", [])]
    memory.record_contract_pattern(analysis["summary"].get("contract_type", "Unknown"), high_risk_clauses)
    memory.save_session(contract_id, f"Reviewed {filename}")

    progress.progress(100, "✅ Analysis complete!")
    time.sleep(0.5)
    progress.empty()

    return analysis


def build_analysis_message(analysis: Dict, filename: str) -> str:
    """Build the initial analysis chat message."""
    summary = analysis.get("summary", {})
    risks = analysis.get("risks", {})
    missing = analysis.get("missing", {})
    score = analysis.get("composite_score", 0)
    badge = ra.generate_risk_badge(score)

    # Memory alerts
    memory_alerts = []
    for clause in [r["clause"] for r in risks.get("high_risks", [])]:
        alert = memory.check_for_previously_flagged(clause)
        if alert:
            memory_alerts.append(alert)

    pattern_insight = memory.get_pattern_insight(summary.get("contract_type", ""))

    lines = [
        f"## ⚖️ Contract Analysis Complete: `{filename}`",
        "",
        f"### {badge['icon']} Risk Score: **{score:.0f}/100** — {badge['label']}",
        "",
        "---",
        "### 📋 Contract Summary",
        f"- **Type:** {summary.get('contract_type', 'Unknown')}",
        f"- **Parties:** {', '.join(summary.get('parties', ['Not identified']))}",
        f"- **Duration:** {summary.get('duration', 'Not specified')}",
        f"- **Value:** {summary.get('contract_value', 'Not specified')}",
        f"- **Governing Law:** {summary.get('governing_law', 'Not specified')}",
    ]

    key_dates = summary.get("key_dates", [])
    if key_dates:
        lines.append(f"- **Key Dates:** {', '.join(key_dates[:3])}")

    # Memory alerts
    if memory_alerts or pattern_insight:
        lines.append("\n---\n### 🧠 Memory Insights")
        for alert in memory_alerts:
            lines.append(f"\n{alert}")
        if pattern_insight:
            lines.append(f"\n{pattern_insight}")

    # Risk Summary
    lines.append("\n---\n### ⚠️ Risk Overview")
    lines.append(risks.get("summary", "See detailed risk analysis below."))

    high_risks = risks.get("high_risks", [])
    if high_risks:
        lines.append("\n**🔴 High Risk Items:**")
        for r in high_risks[:3]:
            lines.append(f"- **{r['clause']}**: {r['explanation'][:100]}...")

    # Missing clauses warning
    missing_list = missing.get("missing_clauses", [])
    critical = [c for c in missing_list if c.get("importance", "").lower() == "critical"]
    if critical:
        lines.append(f"\n---\n### 🚨 Missing Critical Clauses")
        for c in critical[:3]:
            lines.append(f"- ⚠️ **{c['name']}** — {c['recommendation'][:100]}")

    lines.append("\n---")
    lines.append("💬 **You can now ask me questions about this contract!**")
    lines.append("Try: *'What are the main risks?'* | *'Explain the payment terms'* | *'What should I negotiate?'*")

    return "\n".join(lines)


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 16px 0 8px'>
        <span style='font-size:2rem'>⚖️</span>
        <h2 style='color:#a5b4fc; margin:4px 0 0; font-size:1.2rem'>Contract Review Agent</h2>
        <p style='color:#4a5568; font-size:0.75rem; margin:0'>Powered by Groq AI</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # API Status
    api_ok = groq.is_available()
    status_dot = "status-dot-green" if api_ok else "status-dot-red"
    status_text = "Groq API Connected" if api_ok else "API Not Connected"
    st.markdown(f'<div><span class="{status_dot}"></span><span style="color:#8892b0;font-size:0.85rem">{status_text}</span></div>', unsafe_allow_html=True)

    if not api_ok:
        st.warning("⚙️ Set GROQ_API_KEY in your .env file")

    st.divider()

    # Upload Section
    st.markdown('<div class="section-header">📤 Upload Contract</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Choose PDF file",
        type=["pdf"],
        help="Upload a legal contract PDF to analyze",
        label_visibility="collapsed"
    )

    if uploaded_file and not st.session_state.processing:
        if st.button("🚀 Analyze Contract", type="primary", use_container_width=True):
            st.session_state.processing = True
            st.rerun()

    st.divider()

    # Contract History
    st.markdown('<div class="section-header">📚 Contract History</div>', unsafe_allow_html=True)
    contracts = db.get_all_contracts()

    if not contracts:
        st.markdown('<p style="color:#4a5568;font-size:0.8rem">No contracts reviewed yet.</p>', unsafe_allow_html=True)
    else:
        for contract in contracts[:8]:
            score = contract.get("risk_score", 0)
            badge = ra.generate_risk_badge(score)
            ctype = contract.get("contract_type", "Unknown")[:20]
            fname = contract.get("filename", "Unknown")[:22]
            date = contract.get("upload_date", "")[:10]

            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button(f"📄 {fname}", key=f"hist_{contract['id']}", use_container_width=True):
                    # Load historical contract
                    hist = db.get_contract(contract["id"])
                    if hist:
                        st.session_state.current_contract_id = contract["id"]
                        st.session_state.current_contract_text = hist.get("full_text", "")
                        st.session_state.current_analysis = {
                            "summary": json.loads(hist.get("summary_json", "{}")),
                            "clauses": json.loads(hist.get("clauses_json", "{}")),
                            "risks": json.loads(hist.get("risks_json", "{}")),
                            "missing": json.loads(hist.get("missing_clauses_json", "{}")),
                            "plain_english": hist.get("plain_english", ""),
                            "composite_score": hist.get("risk_score", 0),
                        }
                        # Load chat history
                        chat_hist = db.get_chat_history(contract["id"])
                        st.session_state.messages = [
                            {"role": m["role"], "content": m["content"],
                             "timestamp": m["timestamp"][:5]}
                            for m in chat_hist
                        ]
                        st.session_state.analysis_done = True
                        st.rerun()
            with col2:
                st.markdown(f'<div style="color:{badge["color"]};font-size:0.7rem;text-align:right;padding-top:6px">{score:.0f}</div>', unsafe_allow_html=True)

    st.divider()

    # Memory Settings
    st.markdown('<div class="section-header">🧠 Memory Settings</div>', unsafe_allow_html=True)
    mem_summary = memory.get_memory_summary()

    st.markdown(f'<p style="color:#8892b0;font-size:0.8rem">📊 {mem_summary["total_reviews"]} contracts reviewed</p>', unsafe_allow_html=True)

    historical = mem_summary.get("historical_flags", [])
    if historical:
        st.markdown('<p style="color:#8892b0;font-size:0.75rem">Previously flagged:</p>', unsafe_allow_html=True)
        for flag in historical[:5]:
            st.markdown(f'<span style="background:#2d1f5e;color:#a5b4fc;border-radius:4px;padding:2px 6px;font-size:0.7rem;margin:2px;display:inline-block">⚑ {flag}</span>', unsafe_allow_html=True)

    if st.button("🗑️ Clear Memory", use_container_width=True):
        memory.clear_session()
        st.success("Session memory cleared!")


# ─── Processing Logic ──────────────────────────────────────────────────────────
if st.session_state.processing and uploaded_file:
    with st.spinner(""):
        try:
            # Extract text
            file_bytes = uploaded_file.read()
            raw_text, method = pdf_parser.extract_text_from_pdf(file_bytes)
            cleaned_text = pdf_parser.clean_text(raw_text)

            if not cleaned_text or len(cleaned_text) < 50:
                st.error("❌ Could not extract text from PDF. Please ensure it's a text-based PDF.")
                st.session_state.processing = False
                st.stop()

            # Setup contract
            contract_id = str(uuid.uuid4())
            st.session_state.current_contract_id = contract_id
            st.session_state.current_contract_text = cleaned_text
            st.session_state.messages = []
            st.session_state.audit_log = []

            # Save file
            save_path = os.path.join(UPLOADS_DIR, f"{contract_id}_{uploaded_file.name}")
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            # Add system message
            page_count = pdf_parser.get_page_count(file_bytes)
            add_message("assistant",
                f"📄 **Uploaded:** `{uploaded_file.name}` ({page_count} pages, {len(cleaned_text):,} characters)\n"
                f"🔍 **Extraction method:** {method}\n\n"
                "⏳ Running full analysis... this may take 30-60 seconds."
            )

            # Run analysis
            if not groq.is_available():
                st.error("❌ Groq API not configured. Please add your GROQ_API_KEY to .env file.")
                st.session_state.processing = False
                st.stop()

            analysis = run_full_analysis(cleaned_text, contract_id, uploaded_file.name)
            st.session_state.current_analysis = analysis
            st.session_state.analysis_done = True

            # Build and save analysis message
            analysis_msg = build_analysis_message(analysis, uploaded_file.name)
            add_message("assistant", analysis_msg)

            # Save all messages to DB
            for msg in st.session_state.messages:
                db.save_chat_message(contract_id, msg["role"], msg["content"])

        except Exception as e:
            logger.error("Analysis failed: %s", e, exc_info=True)
            st.error(f"❌ Analysis failed: {str(e)}")
        finally:
            st.session_state.processing = False

    st.rerun()


# ─── Main Area ─────────────────────────────────────────────────────────────────
if not st.session_state.analysis_done:
    # Welcome screen
    st.markdown("""
    <div class="welcome-card">
        <div style="font-size:4rem">⚖️</div>
        <h1 style="color:#a5b4fc;margin:16px 0 8px">Contract Review Agent</h1>
        <p style="color:#8892b0;font-size:1.1rem;max-width:500px;margin:0 auto">
            Upload a legal contract PDF and get instant AI-powered analysis —
            risks, clauses, plain English translation, and actionable insights.
        </p>
        <div style="display:flex;gap:24px;justify-content:center;margin-top:32px;flex-wrap:wrap">
            <div style="text-align:center">
                <div style="font-size:1.5rem">📋</div>
                <div style="color:#8892b0;font-size:0.85rem;margin-top:4px">Contract Summary</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:1.5rem">⚠️</div>
                <div style="color:#8892b0;font-size:0.85rem;margin-top:4px">Risk Analysis</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:1.5rem">🔍</div>
                <div style="color:#8892b0;font-size:0.85rem;margin-top:4px">Clause Extraction</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:1.5rem">💬</div>
                <div style="color:#8892b0;font-size:0.85rem;margin-top:4px">Ask Questions</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:1.5rem">🧠</div>
                <div style="color:#8892b0;font-size:0.85rem;margin-top:4px">Memory Insights</div>
            </div>
        </div>
        <p style="color:#4a5568;font-size:0.85rem;margin-top:32px">
            ← Upload a contract PDF from the sidebar to get started
        </p>
    </div>
    """, unsafe_allow_html=True)

else:
    # Main analysis view
    analysis = st.session_state.current_analysis
    score = analysis.get("composite_score", 0)
    badge = ra.generate_risk_badge(score)

    # Top tabs
    tab_chat, tab_clauses, tab_risks, tab_missing, tab_plain, tab_audit = st.tabs([
        "💬 Chat", "📑 Clauses", "⚠️ Risks", "🔎 Missing", "📖 Plain English", "🔧 Audit Log"
    ])

    # ── Chat Tab ──
    with tab_chat:
        # Quick stats row
        risks_data = analysis.get("risks", {})
        missing_data = analysis.get("missing", {})
        stats = ra.get_quick_stats(risks_data, missing_data)
        summary = analysis.get("summary", {})

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:{badge['color']}">{score:.0f}</div>
                <div class="metric-label">Risk Score</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#ff4b4b">{stats['high_risks']}</div>
                <div class="metric-label">High Risks</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#ffa500">{stats['medium_risks']}</div>
                <div class="metric-label">Medium Risks</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#ff4b4b">{stats['missing_critical']}</div>
                <div class="metric-label">Missing Critical</div>
            </div>""", unsafe_allow_html=True)
        with c5:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#a5b4fc">{summary.get('contract_type', 'N/A')[:10]}</div>
                <div class="metric-label">Contract Type</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Chat messages
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(f"""<div class="user-bubble">
                        {msg['content']}
                        <div class="bubble-time">{msg.get('timestamp','')}</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="assistant-bubble">""", unsafe_allow_html=True)
                    st.markdown(msg["content"])
                    st.markdown(f"""<div class="bubble-time">{msg.get('timestamp','')}</div>
                    </div>""", unsafe_allow_html=True)

        # Quick action buttons
        st.markdown("**Quick Actions:**")
        qcol1, qcol2, qcol3, qcol4 = st.columns(4)
        quick_prompts = {
            "🚨 Main Risks": "What are the main risks in this contract?",
            "💰 Payment Terms": "Explain the payment terms in detail.",
            "🤝 What to Negotiate": "What clauses should I negotiate?",
            "📝 Quick Summary": "Give me a brief summary of this contract.",
        }
        for i, (label, prompt) in enumerate(quick_prompts.items()):
            col = [qcol1, qcol2, qcol3, qcol4][i]
            with col:
                if st.button(label, use_container_width=True, key=f"quick_{i}"):
                    st.session_state._pending_message = prompt
                    st.rerun()

        # Chat input
        user_input = st.chat_input("Ask anything about this contract...")

        # Handle quick action or typed input
        pending = st.session_state.pop("_pending_message", None)
        if pending:
            user_input = pending

        if user_input:
            add_message("user", user_input)
            db.save_chat_message(st.session_state.current_contract_id, "user", user_input)

            with st.spinner("Thinking..."):
                chat_history = [{"role": m["role"], "content": m["content"]}
                                for m in st.session_state.messages[:-1]]
                response, audit = groq.chat(
                    user_input,
                    st.session_state.current_contract_text,
                    chat_history
                )
                add_audit(audit)

            add_message("assistant", response)
            db.save_chat_message(st.session_state.current_contract_id, "assistant", response)
            st.rerun()

    # ── Clauses Tab ──
    with tab_clauses:
        st.markdown("### 📑 Extracted Clauses")
        clauses = analysis.get("clauses", {})

        if not clauses:
            st.info("No clause data available. Please upload and analyze a contract.")
        else:
            for key, clause_data in clauses.items():
                display_name = clause_extractor.get_clause_display_name(key)
                present = clause_data.get("present", False)
                risk = clause_extractor.assess_clause_risk(key, clause_data)

                risk_color = {"HIGH": "#ff4b4b", "MEDIUM": "#ffa500", "OK": "#00c853"}.get(risk, "#8892b0")
                present_label = "✅ Found" if present else "❌ Missing"

                # Memory check
                mem_alert = memory.check_for_previously_flagged(key.replace("_", " "))

                with st.expander(f"{display_name} — {present_label}", expanded=not present):
                    if mem_alert:
                        st.markdown(f'<div class="memory-alert">{mem_alert}</div>', unsafe_allow_html=True)

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Summary:** {clause_data.get('summary', 'N/A')}")
                    with col2:
                        st.markdown(f'<span style="color:{risk_color};font-weight:600">{risk} RISK</span>', unsafe_allow_html=True)

                    if present and clause_data.get("content"):
                        st.markdown("**Extracted Content:**")
                        st.code(clause_data["content"][:800], language=None)

                    # Flag button
                    flag_key = f"flag_{key}"
                    if st.button(f"⚑ Flag as Risky", key=flag_key):
                        memory.flag_clause(key.replace("_", " ").title())
                        memory.save_session(st.session_state.current_contract_id)
                        st.success(f"Flagged '{display_name}' for future reference!")

    # ── Risks Tab ──
    with tab_risks:
        st.markdown("### ⚠️ Risk Analysis")
        risks = analysis.get("risks", {})

        if not risks:
            st.info("No risk data available.")
        else:
            # Score gauge
            score_col, summary_col = st.columns([1, 2])
            with score_col:
                st.markdown(f"""<div class="metric-card" style="padding:24px">
                    <div class="metric-value" style="color:{badge['color']};font-size:3rem">{score:.0f}</div>
                    <div style="color:{badge['color']};font-size:1rem;margin-top:8px">{badge['icon']} {badge['label']}</div>
                    <div class="metric-label">out of 100</div>
                </div>""", unsafe_allow_html=True)
            with summary_col:
                st.markdown(f"**Assessment:** {risks.get('summary', '')}")

            st.markdown("---")

            # High risks
            high = risks.get("high_risks", [])
            if high:
                st.markdown("#### 🔴 High Risk")
                for r in high:
                    mem_insight = memory.get_risk_insight(r.get("clause", ""))
                    with st.container():
                        st.markdown(f'<div class="risk-high">', unsafe_allow_html=True)
                        st.markdown(f"**{r.get('clause', 'Unknown')}**")
                        if mem_insight:
                            st.markdown(f'<div class="memory-alert">{mem_insight}</div>', unsafe_allow_html=True)
                        st.markdown(f"📌 {r.get('explanation', '')}")
                        st.markdown(f"💡 **Recommendation:** {r.get('recommendation', '')}")
                        st.markdown('</div>', unsafe_allow_html=True)

            # Medium risks
            med = risks.get("medium_risks", [])
            if med:
                st.markdown("#### 🟡 Medium Risk")
                for r in med:
                    st.markdown(f'<div class="risk-medium">', unsafe_allow_html=True)
                    st.markdown(f"**{r.get('clause', 'Unknown')}**")
                    st.markdown(f"📌 {r.get('explanation', '')}")
                    st.markdown(f"💡 **Recommendation:** {r.get('recommendation', '')}")
                    st.markdown('</div>', unsafe_allow_html=True)

            # Low risks
            low = risks.get("low_risks", [])
            if low:
                st.markdown("#### 🟢 Low Risk")
                for r in low:
                    st.markdown(f'<div class="risk-low">', unsafe_allow_html=True)
                    st.markdown(f"**{r.get('clause', 'Unknown')}** — {r.get('explanation', '')}")
                    st.markdown('</div>', unsafe_allow_html=True)

            # Negotiation tips
            st.markdown("---")
            if st.button("📝 Get Negotiation Tips", type="primary"):
                with st.spinner("Generating negotiation strategy..."):
                    risk_summary = ra.format_risk_summary_for_chat(risks, score)
                    tips, audit = groq.get_negotiation_tips(
                        st.session_state.current_contract_text, risk_summary
                    )
                    add_audit(audit)
                st.markdown("### 🤝 Negotiation Strategy")
                st.markdown(tips)

    # ── Missing Clauses Tab ──
    with tab_missing:
        st.markdown("### 🔎 Missing Clause Detection")
        missing = analysis.get("missing", {})
        missing_list = missing.get("missing_clauses", [])
        present_list = missing.get("present_clauses", [])

        if missing_list:
            critical = [c for c in missing_list if c.get("importance", "").lower() == "critical"]
            important = [c for c in missing_list if c.get("importance", "").lower() == "important"]
            recommended = [c for c in missing_list if c.get("importance", "").lower() == "recommended"]

            if critical:
                st.markdown("#### 🚨 Critical — Must Add")
                for c in critical:
                    st.error(f"**{c['name']}**\n\n{c['recommendation']}")

            if important:
                st.markdown("#### ⚠️ Important — Should Add")
                for c in important:
                    st.warning(f"**{c['name']}**\n\n{c['recommendation']}")

            if recommended:
                st.markdown("#### 💡 Recommended — Consider Adding")
                for c in recommended:
                    st.info(f"**{c['name']}**\n\n{c['recommendation']}")
        else:
            st.success("✅ All key clauses appear to be present!")

        if present_list:
            st.markdown("---\n#### ✅ Important Clauses Present")
            cols = st.columns(3)
            for i, clause in enumerate(present_list):
                cols[i % 3].markdown(f"✅ {clause}")

    # ── Plain English Tab ──
    with tab_plain:
        st.markdown("### 📖 Plain English Translation")
        st.markdown("*Legal language translated into simple, everyday English.*")
        st.markdown("---")
        plain = analysis.get("plain_english", "")
        if plain:
            st.markdown(plain)
        else:
            st.info("Plain English translation not available.")

    # ── Audit Log Tab ──
    with tab_audit:
        st.markdown("### 🔧 CascadeFlow Audit Log")
        st.markdown("*Shows how tasks were routed between AI models.*")
        st.markdown("---")

        audit_entries = db.get_audit_log(st.session_state.current_contract_id or "")
        session_audit = st.session_state.audit_log

        # Merge and deduplicate
        all_audit = session_audit if session_audit else audit_entries

        if not all_audit:
            st.info("No audit entries yet. Analyze a contract to see routing decisions.")
        else:
            # Summary stats
            simple_count = sum(1 for a in all_audit if a.get("task_type") == "Simple")
            advanced_count = sum(1 for a in all_audit if a.get("task_type") == "Advanced")
            total_ms = sum(a.get("duration_ms", 0) for a in all_audit)

            col1, col2, col3 = st.columns(3)
            col1.metric("Simple Tasks", simple_count, help="Used fast LLaMA-8B model")
            col2.metric("Advanced Tasks", advanced_count, help="Used powerful LLaMA-70B model")
            col3.metric("Total Time", f"{total_ms/1000:.1f}s")

            st.markdown("---\n**Routing Decisions:**")
            for entry in all_audit:
                task_type = entry.get("task_type", "?")
                color = "#a5b4fc" if task_type == "Simple" else "#f59e0b"
                icon = "⚡" if task_type == "Simple" else "🧠"
                success_icon = "✅" if entry.get("success", True) else "❌"

                st.markdown(f"""<div class="audit-entry">
                    {success_icon} {icon} <span style="color:{color};font-weight:600">[{task_type}]</span>
                    <span style="color:#e2e8f0"> {entry.get('task_name', 'unknown')}</span>
                    <span style="color:#4a5568"> → {entry.get('model', 'N/A')}</span>
                    <span style="color:#2d3748"> | {entry.get('duration_ms', 0)}ms</span>
                    <br/><span style="color:#4a5568;font-size:0.75rem">📎 {entry.get('reason', '')}</span>
                </div>""", unsafe_allow_html=True)
