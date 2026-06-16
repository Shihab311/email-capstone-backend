import streamlit as st
import requests
import html
import time

API_URL = "http://127.0.0.1:8000"
AI_API_URL = "http://127.0.0.1:8001"

st.set_page_config(
    page_title="Intelligent Email Retrieval System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
html, body, .stApp {
    background-color: #FFFFFF !important;
    color: #111827 !important;
}

.block-container {
    padding-top: 1rem !important;
    max-width: 1350px !important;
}

header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
[data-testid="stSidebar"] {
    display: none !important;
}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.app-title {
    font-size: 32px;
    font-weight: 850;
    color: #111827;
    margin-bottom: 4px;
}

.app-subtitle {
    font-size: 15px;
    color: #4B5563;
    margin-bottom: 30px;
}

.side-label {
    color: #475569;
    font-size: 12px;
    font-weight: 800;
    margin-top: 26px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: #374151 !important;
    font-weight: 700 !important;
}

.email-row {
    background-color: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 14px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
}

.email-row:hover {
    border-color: #60A5FA;
    background-color: #F8FAFC;
}

.email-header {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 8px;
}

.email-sender {
    font-size: 14px;
    color: #111827;
    font-weight: 750;
}

.email-date {
    font-size: 12px;
    color: #6B7280;
    white-space: nowrap;
}

.email-subject {
    font-size: 17px;
    color: #111827;
    font-weight: 800;
    margin-bottom: 6px;
}

.email-snippet {
    font-size: 14px;
    color: #4B5563;
    line-height: 1.55;
}

.pdf-card {
    background-color: #F8FAFC;
    border: 1px solid #BFDBFE;
    border-left: 4px solid #2563EB;
    border-radius: 14px;
    padding: 14px 16px;
    margin-top: -4px;
    margin-bottom: 14px;
}

.pdf-title {
    color: #1D4ED8;
    font-size: 14px;
    font-weight: 800;
    margin-bottom: 8px;
}

.pdf-text {
    color: #111827;
    font-size: 13px;
    line-height: 1.55;
    white-space: pre-wrap;
}

.stTextInput input,
.stNumberInput input {
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 10px !important;
    color: #111827 !important;
    height: 42px !important;
    box-shadow: none !important;
}

.stTextInput input::placeholder {
    color: #374151 !important;
    opacity: 1 !important;
}

.stTextInput input:focus,
.stNumberInput input:focus {
    border: 1px solid #2563EB !important;
    box-shadow: 0 0 0 1px #2563EB !important;
}

[data-testid="InputInstructions"] {
    display: none !important;
}

button {
    border-radius: 999px !important;
    font-weight: 700 !important;
    min-height: 42px !important;
}

div[data-testid="stButton"] > button {
    width: 100%;
    text-align: center;
    background-color: #FFFFFF !important;
    color: #111827 !important;
    border: 1px solid #CBD5E1 !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: #F3F4F6 !important;
    border-color: #2563EB !important;
    color: #111827 !important;
}

.ai-answer-box {
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 20px;
}

.ai-answer-label {
    font-size: 13px;
    font-weight: 800;
    color: #4F46E5;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 10px;
}

.ai-answer-text {
    font-size: 15px;
    color: #111827;
    line-height: 1.7;
    white-space: pre-wrap;
}

.ai-source-card {
    background-color: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 10px;
}

.ai-source-subject {
    font-size: 15px;
    color: #111827;
    font-weight: 700;
    margin-top: 6px;
    margin-bottom: 4px;
}

.ai-source-meta {
    font-size: 12px;
    color: #6B7280;
}

.ai-source-preview {
    font-size: 13px;
    color: #4B5563;
    margin-top: 6px;
    line-height: 1.5;
}

.ai-source-idx {
    display: inline-block;
    background: #4F46E5;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 6px;
    margin-right: 8px;
}

.ai-status-pill {
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 8px;
}
            .stTextInput input,
.stNumberInput input {
    caret-color: #111827 !important;
}

.ai-status-ready { background: #DCFCE7; color: #166534; }
.ai-status-not-ready { background: #FEE2E2; color: #991B1B; }
</style>
""", unsafe_allow_html=True)


def load_emails():
    try:
        response = requests.get(f"{API_URL}/emails")
        if response.status_code == 200:
            return response.json()
        st.error("Unable to load emails from backend.")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Backend server is not running. Start FastAPI first.")
        return []


def load_attachments_for_email(email_id):
    try:
        response = requests.get(f"{API_URL}/emails/{email_id}/attachments")
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.ConnectionError:
        return []


def clear_emails():
    try:
        response = requests.delete(f"{API_URL}/emails")
        if response.status_code == 200:
            return response.json()
        return {"status": "failed", "error": "Failed to clear stored emails."}
    except requests.exceptions.ConnectionError:
        return {"status": "failed", "error": "Backend server is not running."}


def sync_emails(email_address, app_password, limit):
    payload = {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "email": email_address.strip(),
        "password": app_password.strip().replace(" ", ""),
        "limit": int(limit)
    }

    try:
        response = requests.post(f"{API_URL}/sync", json=payload)
        if response.status_code == 200:
            return response.json()
        return {"status": "failed", "error": f"Backend returned status code {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"status": "failed", "error": "Backend server is not running."}


def get_email_search_text(email_item):
    text = (
        str(email_item.get("subject", "")) + " " +
        str(email_item.get("from", "")) + " " +
        str(email_item.get("snippet", "")) + " " +
        str(email_item.get("body", ""))
    )

    attachments = load_attachments_for_email(email_item.get("id"))
    attachment_text = " ".join(
        str(att.get("extracted_text", "")) for att in attachments
    )

    return (text + " " + attachment_text).lower()


def render_email_list(emails):
    if not emails:
        st.info("No emails found.")
        return

    for email_item in emails:
        email_id = email_item.get("id")
        subject = html.escape(str(email_item.get("subject", "No Subject")))
        sender = html.escape(str(email_item.get("from", "Unknown Sender")))
        date = html.escape(str(email_item.get("date", "Unknown Date")))
        snippet = html.escape(str(email_item.get("snippet", "")))

        st.markdown(
            f"""
            <div class="email-row">
                <div class="email-header">
                    <div class="email-sender">{sender}</div>
                    <div class="email-date">{date}</div>
                </div>
                <div class="email-subject">{subject}</div>
                <div class="email-snippet">{snippet}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        attachments = load_attachments_for_email(email_id)

        if attachments:
            for att in attachments:
                filename = html.escape(str(att.get("filename", "Attachment.pdf")))
                extracted_text = html.escape(str(att.get("extracted_text", "")))

                preview = extracted_text[:800]
                if len(extracted_text) > 800:
                    preview += "..."

                st.markdown(
                    f"""
                    <div class="pdf-card">
                        <div class="pdf-title">📎 PDF Attachment: {filename}</div>
                        <div class="pdf-text">{preview}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


if "page" not in st.session_state:
    st.session_state.page = "Inbox"

emails = load_emails()

st.markdown('<div class="app-title">📧 Intelligent Email Retrieval</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Connect and synchronize your email inbox to enable intelligent search, contextual retrieval, and AI-assisted insights.</div>',
    unsafe_allow_html=True
)

left_col, main_col = st.columns([1.1, 4.2], gap="large")

with left_col:
    if st.button("📥 Inbox", use_container_width=True):
        st.session_state.page = "Inbox"

    if st.button("🔎 Search", use_container_width=True):
        st.session_state.page = "Search"

    if st.button("🤖 AI Search", use_container_width=True):
        st.session_state.page = "AI Search"

    if st.button("⭐ Important", use_container_width=True):
        st.session_state.page = "Important"

    st.markdown('<div class="side-label">Connect Email</div>', unsafe_allow_html=True)

    email_address = st.text_input("Email Address", placeholder="Enter Gmail address")
    app_password = st.text_input("App Password", type="password", placeholder="Enter Gmail app password")

    limit = st.number_input(
        "Emails to Sync",
        min_value=1,
        max_value=500,
        value=10,
        step=5
    )

    sync_clicked = st.button("🔄 Sync Emails", use_container_width=True)
    load_clicked = st.button("📥 Refresh Inbox", use_container_width=True)
    clear_clicked = st.button("🧹 Clear Emails", use_container_width=True)

if sync_clicked:
    if not email_address.strip() or not app_password.strip():
        st.error("Please enter both email address and app password.")
    else:
        with st.spinner("Synchronizing emails..."):
            result = sync_emails(email_address, app_password, limit)

        if result.get("status") == "ok":
            st.success(
                f"✅ Synchronization completed. "
                f"Inserted: {result.get('inserted', 0)} | "
                f"Skipped: {result.get('skipped', 0)} | "
                f"PDFs saved: {result.get('pdf_attachments_saved', 0)}"
            )
        else:
            st.error(f"Synchronization failed: {result.get('error', 'Unknown error')}")

        emails = load_emails()

if load_clicked:
    emails = load_emails()

if clear_clicked:
    result = clear_emails()

    if result.get("status") == "ok":
        st.success(f"Stored emails cleared. Deleted: {result.get('deleted', 0)}")
        emails = []
    else:
        st.error(result.get("error", "Failed to clear emails."))

with main_col:
    if st.session_state.page == "Inbox":
        st.markdown(f"### 📬 Inbox · {len(emails)} email(s)")
        render_email_list(emails)

    elif st.session_state.page == "Search":
        st.markdown("### 🔎 Search Emails")

        search_query = st.text_input(
            "Search emails",
            placeholder="Search by subject, sender, email content, or PDF attachment text",
            label_visibility="collapsed"
        )

        st.caption("Search checks email text and extracted PDF attachment text.")

        if search_query.strip():
            query = search_query.lower()

            filtered_emails = [
                email_item for email_item in emails
                if query in get_email_search_text(email_item)
            ]

            st.markdown(f"### Results · {len(filtered_emails)} email(s)")
            render_email_list(filtered_emails)
        else:
            st.info("Type a search query to find emails or PDF attachment content.")

    elif st.session_state.page == "AI Search":
        st.markdown("### 🤖 AI-Powered Email Search")

        ai_ready = False
        try:
            ai_status = requests.get(f"{AI_API_URL}/status", timeout=3).json()
            ai_ready = ai_status.get("ready", False)
            pill_cls = "ai-status-ready" if ai_ready else "ai-status-not-ready"
            pill_txt = "AI Ready" if ai_ready else "Not Indexed"
            st.markdown(
                f'<span class="ai-status-pill {pill_cls}">{pill_txt}</span>'
                f'<span style="color:#94A3B8;font-size:12px;">'
                f'{ai_status.get("chunk_count",0)} chunks · '
                f'{ai_status.get("faiss_vectors",0)} vectors</span>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.warning("AI backend is not running. Start it with: `uvicorn ai_backend.main:app --port 8001`")

        st.markdown("---")

        if not ai_ready:
            st.caption("Build the AI index from your synced emails before searching.")
            ingest_label = "⚡ Build AI Index"
        else:
            st.caption("Synced new emails? Click to add them to AI Search.")
            ingest_label = "🔄 Process synced emails → AI Search"

        if st.button(ingest_label, use_container_width=True):
            with st.spinner("Embedding new emails and updating the AI index..."):
                try:
                    resp = requests.post(f"{AI_API_URL}/ingest", json={}, timeout=600)
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(
                            f"✅ AI index updated. "
                            f"{data.get('emails_in_db',0)} emails in database · "
                            f"{data.get('chunks_created',0)} chunks · "
                            f"{data.get('faiss_vectors',0)} vectors"
                        )
                        st.rerun()
                    else:
                        st.error(f"Ingest failed: {resp.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to AI backend.")
                except Exception as e:
                    st.error(f"Ingest error: {e}")

        st.markdown("---")

        ai_query = st.text_input(
            "Ask anything about your emails",
            placeholder="e.g. What did John say about the project deadline?",
            label_visibility="collapsed",
            key="ai_query",
        )

        opts_col1, opts_col2 = st.columns(2)
        with opts_col1:
            use_rerank = st.checkbox("LLM Reranking", value=False, help="Use Gemini to rerank results for higher accuracy")
        with opts_col2:
            expand_thread = st.checkbox("Expand Threads", value=False, help="Include sibling chunks from the same email thread")

        with st.expander("Advanced Filters"):
            fc1, fc2 = st.columns(2)
            with fc1:
                from_filter = st.text_input("From contains", key="ai_from")
                subject_filter = st.text_input("Subject contains", key="ai_subj")
            with fc2:
                to_filter = st.text_input("To contains", key="ai_to")
            fd1, fd2 = st.columns(2)
            with fd1:
                date_from = st.text_input("Date from (YYYY-MM-DD)", key="ai_df")
            with fd2:
                date_to = st.text_input("Date to (YYYY-MM-DD)", key="ai_dt")

        search_clicked = st.button("🔍 Search with AI", use_container_width=True, type="primary")

        if search_clicked and ai_query.strip():
            if not ai_ready:
                st.error("AI index is not built yet. Click 'Build AI Index' first.")
            else:
                with st.spinner("Searching and generating answer..."):
                    try:
                        payload = {
                            "query": ai_query.strip(),
                            "top_k": 10,
                            "use_rerank": use_rerank,
                            "expand_thread": expand_thread,
                        }

                        if from_filter.strip():
                            payload["from_contains"] = from_filter.strip()
                        if to_filter.strip():
                            payload["to_contains"] = to_filter.strip()
                        if subject_filter.strip():
                            payload["subject_contains"] = subject_filter.strip()
                        if date_from.strip():
                            payload["date_from"] = date_from.strip()
                        if date_to.strip():
                            payload["date_to"] = date_to.strip()

                        start_time = time.perf_counter()
                        resp = requests.post(f"{AI_API_URL}/search", json=payload, timeout=120)
                        elapsed = time.perf_counter() - start_time

                        if resp.status_code == 200:
                            data = resp.json()
                            answer = data.get("answer", "")
                            sources = data.get("sources", [])
                            model = data.get("model_used", "")

                            st.markdown(
                                f'<div class="ai-status-pill ai-status-ready">'
                                f'⏱️ Answered in {elapsed:.2f} s</div>',
                                unsafe_allow_html=True,
                            )

                            st.markdown(
                                f'<div class="ai-answer-box">'
                                f'<div class="ai-answer-label">🤖 AI Answer · {html.escape(model or "")}</div>'
                                f'<div class="ai-answer-text">{html.escape(answer)}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                            if sources:
                                st.markdown(f"#### 📎 Sources · {len(sources)} chunk(s)")
                                for src in sources:
                                    idx = src.get("chunk_index", "")
                                    subj = html.escape(str(src.get("subject", "(no subject)")))
                                    sender = html.escape(str(src.get("sender", "")))
                                    date_val = html.escape(str(src.get("date", "")))
                                    preview = html.escape(str(src.get("preview", "")))
                                    faiss_s = src.get("faiss_score")
                                    bm25_s = src.get("bm25_score")

                                    score_parts = []
                                    if faiss_s is not None:
                                        score_parts.append(f"FAISS: {faiss_s:.4f}")
                                    if bm25_s is not None:
                                        score_parts.append(f"BM25: {bm25_s:.4f}")

                                    score_str = " · ".join(score_parts)

                                    st.markdown(
                                        f'<div class="ai-source-card">'
                                        f'<span class="ai-source-idx">CHUNK {idx}</span>'
                                        f'<span class="ai-source-meta">{score_str}</span>'
                                        f'<div class="ai-source-subject">{subj}</div>'
                                        f'<div class="ai-source-meta">From: {sender} · {date_val}</div>'
                                        f'<div class="ai-source-preview">{preview}</div>'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )

                        elif resp.status_code == 503:
                            st.error("AI engine not ready. Build the index first.")
                        else:
                            st.error(f"Search failed: {resp.text}")

                    except requests.exceptions.ConnectionError:
                        st.error("Cannot connect to AI backend.")
                    except Exception as e:
                        st.error(f"Search error: {e}")

        elif search_clicked:
            st.warning("Please enter a query.")

    elif st.session_state.page == "Important":
        st.markdown("### ⭐ Important Emails")

        important_emails = []
        for email_item in emails:
            text = get_email_search_text(email_item)
            if (
                "important" in text
                or "urgent" in text
                or "deadline" in text
                or "meeting" in text
                or "invoice" in text
                or "payment" in text
            ):
                important_emails.append(email_item)

        st.caption("This section checks email text and extracted PDF attachment text.")
        st.markdown(f"### Important · {len(important_emails)} email(s)")
        render_email_list(important_emails)