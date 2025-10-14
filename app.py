# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import os
from PIL import Image

# Your GitHub repo details
REPO = "AP07AP/instagram-scraper-streamlit"
WORKFLOW_ID = "scraper.yml"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

st.title("📸 Instagram Scraper Dashboard")

profile_url = st.text_input("Instagram Profile URL")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")
password = st.text_input("Instagram Password", type="password")

if st.button("🚀 Run Scraper"):
    st.info("Triggering GitHub Action...")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    payload = {
        "ref": "main",
        "inputs": {
            "profile_url": profile_url,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "username": username,
            "password": password,
        },
    }

    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
        headers=headers, json=payload
    )

    if r.status_code == 204:
        st.success("✅ Workflow triggered successfully! Wait ~1–2 mins.")

        # --- Check if screenshot exists after run ---
        screenshot_path = "click_error.png"
        if os.path.exists(screenshot_path):
            st.error("⚠️ Error occurred while clicking the first post.")
            img = Image.open(screenshot_path)
            st.image(img, caption="Error Screenshot", use_column_width=True)
        else:
            st.success("🎉 No errors — everything worked fine!")

    else:
        st.error(f"❌ Error triggering workflow: {r.text}")
