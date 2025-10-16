# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import os
import pandas as pd
from PIL import Image
from io import BytesIO
from zipfile import ZipFile

# -------------------------------
# GitHub Repo Details
# -------------------------------
REPO = "AP07AP/instagram-scraper-streamlit"
WORKFLOW_ID = "scraper.yml"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
ARTIFACT_NAME = "scraped_data"  # Make sure it matches your artifact name

# -------------------------------
# Dashboard Title
# -------------------------------
st.title("📸 Instagram Scraper Dashboard")

# -------------------------------
# Scraper Inputs
# -------------------------------
profile_url = st.text_input("Instagram Profile URL")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")
password = st.text_input("Instagram Password", type="password")

# -------------------------------
# Trigger Scraper Workflow
# -------------------------------
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
    else:
        st.error(f"❌ Error triggering workflow: {r.text}")

# -------------------------------
# Function to fetch latest artifact CSV
# -------------------------------
def fetch_artifact_csv(repo, token, artifact_name=ARTIFACT_NAME):
    headers = {"Authorization": f"Bearer {token}"}
    # Get list of artifacts
    artifacts_url = f"https://api.github.com/repos/{repo}/actions/artifacts"
    r = requests.get(artifacts_url, headers=headers)
    if r.status_code != 200:
        st.error("Failed to fetch artifacts.")
        return None

    artifacts = r.json().get("artifacts", [])
    artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
    if not artifact:
        st.warning(f"No artifact named '{artifact_name}' found.")
        return None

    download_url = artifact["archive_download_url"]
    r = requests.get(download_url, headers=headers)
    if r.status_code != 200:
        st.error("Failed to download artifact.")
        return None

    zipfile = ZipFile(BytesIO(r.content))
    csv_filename = zipfile.namelist()[0]  # assume first file is CSV
    with zipfile.open(csv_filename) as f:
        df = pd.read_csv(f)
    return df

# -------------------------------
# Get Report Inputs
# -------------------------------
st.markdown("### 📑 Get Report")
selected_user = st.text_input("Enter Instagram Username for Report").strip()
from_date = st.date_input("From")
to_date = st.date_input("To")

if st.button("Generate Report"):
    if not selected_user:
        st.warning("Please enter a username.")
    else:
        df = fetch_artifact_csv(REPO, GITHUB_TOKEN)
        if df is None or df.empty:
            st.warning("No scraped data available. Run the scraper first.")
            st.stop()

        # -------------------------------
        # Clean Likes column
        # -------------------------------
        df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
        df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)

        # Convert Date & Time
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce").dt.time

        # Filter by username & dates
        filtered = df[
            (df["username"] == selected_user) &
            (df["Date"] >= pd.to_datetime(from_date)) &
            (df["Date"] <= pd.to_datetime(to_date))
        ]

        if filtered.empty:
            st.warning(f"No data found for user '{selected_user}' in selected date range.")
            st.stop()

        # -------------------------------
        # Helper: Indian number format
        # -------------------------------
        def format_indian_number(number):
            try:
                s = str(int(number))
            except:
                return "0"
            if len(s) <= 3:
                return s
            last3 = s[-3:]
            remaining = s[:-3]
            parts = []
            while len(remaining) > 2:
                parts.append(remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                parts.append(remaining)
            return ','.join(reversed(parts)) + ',' + last3

        # -------------------------------
        # User Overview
        # -------------------------------
        total_posts = filtered["URL"].nunique()
        total_likes = filtered["Likes"].sum()
        total_comments = filtered["Comments"].notna().sum()

        st.markdown("## User Overview")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
        with col2:
            st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
        with col3:
            st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")

        # -------------------------------
        # Display Posts Drill-down
        # -------------------------------
        st.markdown("## 📌 Explore Posts")
        post_urls = filtered["URL"].unique().tolist()
        selected_posts = st.multiselect("Select one or more posts", post_urls)

        if selected_posts:
            for url in selected_posts:
                post_data = filtered[filtered["URL"] == url]
                first_row = post_data.iloc[0]

                st.markdown(
                    f"**Caption:** {first_row['Caption']}  \n"
                    f"📅 {first_row['Date'].date()} 🕒 {first_row['Time']} ❤️ Likes: {format_indian_number(first_row['Likes'])}  \n"
                    f"🔗 [View Post]({url})"
                )

                comments_only = post_data[post_data["Comments"].notna()]
                if not comments_only.empty:
                    st.dataframe(comments_only[["Comments"]].reset_index(drop=True))
                else:
                    st.info("No comments available for this post.")

        st.markdown("---")
        st.success("✅ Report generated successfully!")
