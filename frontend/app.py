import streamlit as st
import requests
import html

API_URL = "http://127.0.0.1:8000"
AI_API_URL = "http://127.0.0.1:8001"

st.set_page_config(
    page_title="Intelligent Email Retrieval System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
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
.stApp {
    background-color: #F4F6FB !important;
}

label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: #334155 !important;
    font-weight: 700 !important;
}

.stMarkdown,
p,
h1,
h2,
h3,
h4,
h5,
h6 {
    color: #111827 !important;
}
.app-title {
    font-size: 32px;
    font-weight: 850;
    color: #111827;
    margin-bottom: 4px;
}

.app-subtitle {
    font-size: 15px;
    color: #475569;
    margin-bottom: 30px;
}

.side-label {
    color: #334155;
    font-size: 12px;
    font-weight: 800;
    margin-top: 26px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.email-row {
    background-color: #111827;
    border: 1px solid #253041;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 12px;
}

.email-row:hover {
    border-color: #60A5FA;
    background-color: #172033;
}

.email-header {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 8px;
}

.email-sender {
    font-size: 14px;
    color: #F8FAFC;
    font-weight: 750;
}

.email-date {
    font-size: 12px;
    color: #94A3B8;
    white-space: nowrap;
}

.email-subject {
    font-size: 17px;
    color: #F9FAFB;
    font-weight: 800;
    margin-bottom: 6px;
}

.email-snippet {
    font-size: 14px;
    color: #CBD5E1;
    line-height: 1.55;
}

.attachment-card {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 14px 16px;
    margin-top: -4px;
    margin-bottom: 14px;
}

.attachment-title {
    color: #93C5FD;
    font-size: 14px;
    font-weight: 800;
    margin-bottom: 8px;
}

.attachment-text {
    color: #CBD5E1;
    font-size: 13px;
    line-height: 1.55;
    white-space: pre-wrap;
}

.stTextInput input,
.stNumberInput input {
    background-color: #0B0F19 !important;
    border: 1px solid #4B5563 !important;
    border-radius: 10px !important;
    color: #F8FAFC !important;
    height: 42px !important;
    box-shadow: none !important;
}

.stTextInput input:focus,
.stNumberInput input:focus {
    border: 1px solid #60A5FA !important;
    box-shadow: 0 0 0 1px #60A5FA !important;
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
    text-align: left;
    background: white !important;
    color: #111827 !important;
    border: 1px solid #CBD5E1 !important;
}

.status-card {
    padding: 14px 16px;
    border-radius: 14px;
    margin-bottom: 14px;
    background-color: #123524;
    color: #86EFAC;
    font-weight: 700;
}

.ai-answer-box {
    background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%);
    border: 1px solid #4338CA;
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 20px;
}

.ai-answer-label {
    font-size: 13px;
    font-weight: 800;
    color: #A78BFA;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 10px;
}

.ai-answer-text {
    font-size: 15px;
    color: #E2E8F0;
    line-height: 1.7;
    white-space: pre-wrap;
}

.ai-source-card {
    background-color: #111827;
    border: 1px solid #253041;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 10px;
}

.ai-source-card:hover {
    border-color: #818CF8;
    background-color: #172033;
}

.ai-source-idx {
    display: inline-block;
    background: #4338CA;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 6px;
    margin-right: 8px;
}

.ai-source-subject {
    font-size: 15px;
    color: #F9FAFB;
    font-weight: 700;
    margin-top: 6px;
    margin-bottom: 4px;
}

.ai-source-meta {
    font-size: 12px;
    color: #94A3B8;
}

.ai-source-preview {
    font-size: 13px;
    color: #CBD5E1;
    margin-top: 6px;
    line-height: 1.5;
}

.ai-status-pill {
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 8px;
}

.ai-status-ready { background: #064E3B; color: #6EE7B7; }
.ai-status-not-ready { background: #7F1D1D; color: #FCA5A5; }
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
                    <div class="attachment-card">
                        <div class="attachment-title">📎 PDF Attachment: {filename}</div>
                        <div class="attachment-text">{preview}</div>
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

    email_address = st.text_input("Email Address", placeholder="Enter email address")
    app_password = st.text_input("App Password", type="password", placeholder="Enter email app password")

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
                f"✅ Synchronization completed. Inserted: {result.get('inserted', 0)} | "
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

        st.caption("Search now checks email content and extracted PDF attachment text.")

        if search_query.strip():
            query = search_query.lower()

            filtered_emails = []

            for email_item in emails:
                email_text = (
                    str(email_item.get("subject", "")) + " " +
                    str(email_item.get("from", "")) + " " +
                    str(email_item.get("snippet", ""))
                ).lower()

                attachments = load_attachments_for_email(email_item.get("id"))
                attachment_text = " ".join(
                    str(att.get("extracted_text", "")) for att in attachments
                ).lower()

                if query in email_text or query in attachment_text:
                    filtered_emails.append(email_item)

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

        if not ai_ready:
            st.markdown("---")
            st.caption("Build the AI index from your synced emails before searching.")
            if st.button("⚡ Build AI Index", use_container_width=True):
                with st.spinner("Ingesting emails, generating embeddings, and building indexes... This may take a few minutes."):
                    try:
                        resp = requests.post(f"{AI_API_URL}/ingest", json={}, timeout=600)
                        if resp.status_code == 200:
                            data = resp.json()
                            st.success(
                                f"✅ Index built! {data.get('emails_embedded',0)} emails → "
                                f"{data.get('chunks_created',0)} chunks → "
                                f"{data.get('faiss_vectors',0)} FAISS vectors"
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
            placeholder="e.g. What is the Project Phoenix deadline?",
            label_visibility="collapsed",
            key="ai_query",
        )

        opts_col1, opts_col2 = st.columns(2)
        with opts_col1:
            use_rerank = st.checkbox("LLM Reranking", value=False)
        with opts_col2:
            expand_thread = st.checkbox("Expand Threads", value=False)

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

                        resp = requests.post(f"{AI_API_URL}/search", json=payload, timeout=120)

                        if resp.status_code == 200:
                            data = resp.json()
                            answer = data.get("answer", "")
                            sources = data.get("sources", [])
                            model = data.get("model_used", "")

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
            base_text = (
                str(email_item.get("subject", "")) + " " +
                str(email_item.get("from", "")) + " " +
                str(email_item.get("snippet", ""))
            ).lower()

            attachments = load_attachments_for_email(email_item.get("id"))
            attachment_text = " ".join(
                str(att.get("extracted_text", "")) for att in attachments
            ).lower()

            full_text = base_text + " " + attachment_text

            if (
                "important" in full_text
                or "urgent" in full_text
                or "deadline" in full_text
                or "meeting" in full_text
                or "invoice" in full_text
                or "payment" in full_text
            ):
                important_emails.append(email_item)

        st.caption("This section checks both email text and PDF attachment text.")
        st.markdown(f"### Important · {len(important_emails)} email(s)")
        render_email_list(important_emails)