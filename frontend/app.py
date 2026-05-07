import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.title("Intelligent Email Management and Retrieval System")

st.write("Frontend connected to FastAPI backend")

if st.button("Load Emails"):
    response = requests.get(f"{API_URL}/emails")

    if response.status_code == 200:
        emails = response.json()

        if not emails:
            st.info("No emails found.")
        else:
            for email in emails:
                st.subheader(email["subject"])
                st.write(f"From: {email['from']}")
                st.write(f"Date: {email['date']}")
                st.write(email["snippet"])
                st.divider()
    else:
        st.error("Failed to load emails")