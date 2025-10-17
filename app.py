# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import pandas as pd
import time
import uuid
from io import BytesIO
from zipfile import ZipFile

# -------------------------------
# GitHub Repo Details
# -------------------------------
REPO = "AP07AP/instagram-scraper-streamlit"
WORKFLOW_ID = "scraper.yml"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
ARTIFACT_NAME = "scraped_data"  # fallback name

# -------------------------------
# Dashboard Title
# -------------------------------
st.title("📸 Instagram Scraper Dashboard")

# -------------------------------
# Scraper Inputs
# -------------------------------
profile_url = st.text_area(
    "Enter one or more Instagram Profile URLs (comma-separated or one per line)",
    height=20,
    placeholder="https://www.instagram.com/user1/"
)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")
# password = st.text_input("Instagram Password", type="password")

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
# Function to fetch artifact CSV
# -------------------------------
def fetch_artifact_csv(repo, token, artifact_name=ARTIFACT_NAME):
    headers = {"Authorization": f"Bearer {token}"}

    # Wait for artifact to appear (max 2 mins)
    artifact_found = False
    for _ in range(600):
        artifacts = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts", headers=headers).json().get("artifacts", [])
        if any(a["name"] == artifact_name for a in artifacts):
            artifact_found = True
            break
        time.sleep(6)

    if not artifact_found:
        st.error(f"❌ Artifact {artifact_name} not found yet. Try again in a few seconds.")
        st.stop()

    # Download artifact
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts", headers=headers)
    artifacts = r.json().get("artifacts", [])
    artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
    if not artifact:
        st.error(f"❌ Artifact {artifact_name} not found.")
        return None

    download_url = artifact["archive_download_url"]
    r = requests.get(download_url, headers=headers)
    if r.status_code != 200:
        st.error("❌ Failed to download artifact.")
        return None

    zipfile = ZipFile(BytesIO(r.content))
    csv_filename = zipfile.namelist()[0]
    with zipfile.open(csv_filename) as f:
        df = pd.read_csv(f)
    return df


# -------------------------------
# SCRAPE BUTTON
# -------------------------------
if st.button("🕸️ Scrape Data"):
    # if not profile_url or not username or not password:
    if not profile_url or not username:
        st.warning("⚠️ Please fill all fields before scraping.")
        st.stop()

    # Unique artifact per user/session: username + short UUID
    unique_id = uuid.uuid4().hex[:6]
    st.session_state["artifact_name"] = f"scraped_data_{username}_{unique_id}"

    st.info(f"🚀 Triggering scraper workflow for artifact: `{st.session_state['artifact_name']}`")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }

    payload = {
        "ref": "main",
        "inputs": {
            "profile_url": ",".join([p.strip() for p in profile_url.replace("\n", ",").split(",") if p.strip()]),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "username": username,
            "artifact_name": st.session_state["artifact_name"],
        },
    }

    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
        headers=headers,
        json=payload,
    )

    if r.status_code != 204:
        st.error(f"❌ Failed to trigger workflow: {r.text}")
        st.stop()

    st.info("⏳ Waiting for workflow to complete (up to 5 mins)...")

    workflow_completed = False
    for _ in range(600):  # ~10 mins
        runs = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/runs", headers=headers).json()
        latest_run = runs.get("workflow_runs", [None])[0]
        if latest_run and latest_run.get("status") == "completed":
            workflow_completed = True
            break
        time.sleep(6)

    if workflow_completed:
        st.success("🔄 Scraping in progress...")
        st.session_state["scrape_done"] = True
    else:
        st.error("❌ Workflow timed out.")
        st.session_state["scrape_done"] = False


# -------------------------------
# REPORT BUTTON (enabled after scrape)
# -------------------------------
if st.session_state.get("scrape_done", False):
    if st.button("📊 Get Report"):
        artifact_name = st.session_state.get("artifact_name", ARTIFACT_NAME)
        st.info(f"📦 Fetching artifact `{artifact_name}` ...")

        df = fetch_artifact_csv(REPO, GITHUB_TOKEN, artifact_name)
        if df is None or df.empty:
            st.warning("⚠️ No data found in your artifact.")
            st.stop()

        st.session_state["scraped_df"] = df
        st.success("✅ Your report is ready!")


# -------------------------------
# DISPLAY REPORT
# -------------------------------
if "scraped_df" in st.session_state:
    df = st.session_state["scraped_df"]

    # Clean up data
    df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
    df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce").dt.time
    df["Comments"] = df["Comments"].replace("", pd.NA)

    # Username summary
    if "username" in df.columns:
        st.markdown("## 👥 Profile Summary")
        summary_df = (
            df.groupby("username")
            .agg(
                Total_Posts=("URL", "nunique"),
                Total_Likes=("Likes", "sum"),
                Total_Comments=("Comments", lambda x: x.notna().sum()),
            )
            .reset_index()
        )

        summary_df["Total_Likes"] = summary_df["Total_Likes"].apply(format_indian_number)
        summary_df["Total_Comments"] = summary_df["Total_Comments"].apply(format_indian_number)

        st.dataframe(summary_df, use_container_width=True)

        selected_users = st.multiselect(
            "Select profiles to explore",
            options=summary_df["username"].tolist(),
        )

        if selected_users:
            df = df[df["username"].isin(selected_users)]
    else:
        st.warning("Username column not found in data.")
        st.stop()

    # Overview
    st.markdown("## Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Posts", format_indian_number(df["URL"].nunique()))
    col2.metric("Total Likes", format_indian_number(df["Likes"].sum()))
    col3.metric("Total Comments", format_indian_number(df["Comments"].notna().sum()))

    # Post exploration
    st.markdown("## 📌 Explore Posts")
    post_urls = df["URL"].unique().tolist()
    selected_posts = st.multiselect(
        "🔗 Select one or more Posts (URLs)",
        post_urls
    )

    if selected_posts:
        multi_posts = df[df["URL"].isin(selected_posts)]
        st.subheader("📝 Selected Posts Details")
        for url in selected_posts:
            post_group = multi_posts[multi_posts["URL"] == url]
            caption_row = post_group[post_group["Caption"].notna()]
            if not caption_row.empty:
                row = caption_row.iloc[0]
                st.markdown(
                    f"**Caption:** {row['Caption']}  \n"
                    f"📅 {row['Date'].date()} 🕒 {row['Time']} ❤️ Likes: {format_indian_number(row['Likes'])}  \n"
                    f"🔗 [View Post]({url})"
                )

                comments_only = post_group[post_group["Comments"].notna()].copy()
                if not comments_only.empty:
                    st.dataframe(comments_only[["Comments"]].reset_index(drop=True), use_container_width=True)
                else:
                    st.info("No comments available for this post.")

            st.markdown("---")
            
        # -------------------------------
        # Download Button for Selected Posts
        # -------------------------------
        download_df = multi_posts.copy()
        download_df["Likes"] = download_df["Likes"].astype(int)
        csv_bytes = download_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Selected Posts as CSV",
            data=csv_bytes,
            file_name="selected_posts_report.csv",
            mime="text/csv"
        )

    else:
        # Download full scraped data if no post selected
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Scraped Data as CSV",
            data=csv_bytes,
            file_name="full_scraped_report.csv",
            mime="text/csv"
        )
