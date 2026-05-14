import streamlit as st
import requests
import html

API_URL = "http://127.0.0.1:8000"

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
div[data-testid="stDecoration"] {
    display: none !important;
}

[data-testid="stSidebar"] {
    display: none !important;
}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.app-title {
    font-size: 32px;
    font-weight: 850;
    color: #F8FAFC;
    margin-bottom: 4px;
}

.app-subtitle {
    font-size: 15px;
    color: #CBD5E1;
    margin-bottom: 30px;
}

.side-label {
    color: #94A3B8;
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
}

.status-card {
    padding: 14px 16px;
    border-radius: 14px;
    margin-bottom: 14px;
    background-color: #123524;
    color: #86EFAC;
    font-weight: 700;
}
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
                f"✅ Synchronization completed. Inserted: {result.get('inserted', 0)} | Skipped: {result.get('skipped', 0)}"
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
            placeholder="Search by subject, sender, or email content",
            label_visibility="collapsed"
        )

        st.caption("Current version uses local filtering. Later, this can connect to AI semantic retrieval.")

        if search_query.strip():
            query = search_query.lower()

            filtered_emails = [
                email_item for email_item in emails
                if query in str(email_item.get("subject", "")).lower()
                or query in str(email_item.get("from", "")).lower()
                or query in str(email_item.get("snippet", "")).lower()
            ]

            st.markdown(f"### Results · {len(filtered_emails)} email(s)")
            render_email_list(filtered_emails)
        else:
            st.info("Type a search query to find emails.")

    elif st.session_state.page == "Important":
        st.markdown("### ⭐ Important Emails")

        important_emails = [
            email_item for email_item in emails
            if "important" in str(email_item.get("subject", "")).lower()
            or "urgent" in str(email_item.get("subject", "")).lower()
            or "deadline" in str(email_item.get("subject", "")).lower()
            or "meeting" in str(email_item.get("subject", "")).lower()
        ]

        st.caption("This section currently uses keyword filtering. Later, priority detection can be improved with AI.")
        st.markdown(f"### Important · {len(important_emails)} email(s)")
        render_email_list(important_emails)