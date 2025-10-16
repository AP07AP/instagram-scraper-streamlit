# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import pandas as pd
import time
from io import BytesIO
from zipfile import ZipFile

# -------------------------------
# GitHub Repo Details
# -------------------------------
REPO = "AP07AP/instagram-scraper-streamlit"
WORKFLOW_ID = "scraper.yml"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
ARTIFACT_NAME = "scraped_data"  # Must match uploaded artifact name

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
password = st.text_input("Instagram Password", type="password")

# -------------------------------
# Function to fetch latest artifact CSV
# -------------------------------
def fetch_artifact_csv(repo, token, artifact_name=ARTIFACT_NAME):
    headers = {"Authorization": f"Bearer {token}"}
    artifacts_url = f"https://api.github.com/repos/{repo}/actions/artifacts"
    r = requests.get(f"{artifacts_url}?per_page=100&timestamp={int(time.time())}", headers=headers)
    if r.status_code != 200:
        st.error("Failed to fetch artifacts.")
        return None

    artifacts = r.json().get("artifacts", [])
    artifact = next(
        (a for a in sorted(artifacts, key=lambda x: x["created_at"], reverse=True) if a["name"] == artifact_name),
        None
    )
    if not artifact:
        st.warning(f"No artifact named '{artifact_name}' found.")
        return None

    download_url = artifact["archive_download_url"]
    r = requests.get(download_url, headers=headers)
    if r.status_code != 200:
        st.error("Failed to download artifact.")
        return None

    zipfile = ZipFile(BytesIO(r.content))
    csv_filename = zipfile.namelist()[0]
    with zipfile.open(csv_filename) as f:
        df = pd.read_csv(f)
    return df

# -------------------------------
# Helper: Wait for workflow completion
# -------------------------------
def wait_for_workflow_completion(repo, workflow_id, token, timeout=600):
    """Waits for the most recent workflow run to complete (max wait = timeout seconds)."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    end_time = time.time() + timeout
    while time.time() < end_time:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/runs?per_page=1"
        r = requests.get(url, headers=headers)
        runs = r.json().get("workflow_runs", [])
        if runs:
            latest = runs[0]
            status = latest.get("status")
            conclusion = latest.get("conclusion")
            if status == "completed":
                if conclusion == "success":
                    st.success("✅ Scraping completed successfully!")
                    return True
                else:
                    st.error(f"❌ Workflow failed ({conclusion})")
                    return False
        st.info("⏳ Waiting for scraping to finish...")
        time.sleep(10)
    st.error("⏰ Timeout waiting for workflow completion.")
    return False

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
# Scrape & Store Data
# -------------------------------
if st.button("📑 Scrape & Get Report"):
    if not profile_url or not username or not password:
        st.warning("Please fill all the inputs.")
        st.stop()

    st.info("🚀 Triggering scraper workflow...")

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
            "password": password,
        },
    }

    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
        headers=headers,
        json=payload
    )
    if r.status_code != 204:
        st.error(f"Failed to trigger workflow: {r.text}")
        st.stop()

    # 🕒 Wait for workflow completion
    if not wait_for_workflow_completion(REPO, WORKFLOW_ID, GITHUB_TOKEN):
        st.stop()

    st.success("✅ Scraper finished! Fetching data...")

    # Fetch artifact
    df = fetch_artifact_csv(REPO, GITHUB_TOKEN)
    if df is None or df.empty:
        st.warning("No data found in artifact.")
        st.stop()

    st.session_state["scraped_df"] = df

# -------------------------------
# Post-explorer (persistent across reruns)
# -------------------------------
if "scraped_df" in st.session_state:
    df = st.session_state["scraped_df"]

    df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
    df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce").dt.time
    df["Comments"] = df["Comments"].replace("", pd.NA)

    if "username" in df.columns:
        st.markdown("## 👥 Profile Comparison Summary")
        summary_df = (
            df.groupby("username")
            .agg(
                Total_Posts=("URL", "nunique"),
                Total_Likes=("Likes", "sum"),
                Total_Comments=("Comments", lambda x: x.notna().sum())
            )
            .reset_index()
        )
        summary_df["Total_Likes"] = summary_df["Total_Likes"].apply(format_indian_number)
        summary_df["Total_Comments"] = summary_df["Total_Comments"].apply(format_indian_number)
        st.dataframe(summary_df, use_container_width=True)

        selected_users = st.multiselect(
            "Select one or more profiles to view details",
            options=summary_df["username"].tolist()
        )

        if selected_users:
            df = df[df["username"].isin(selected_users)]
        else:
            st.info("Select profiles above to explore their posts and stats.")
            st.stop()
    else:
        st.warning("Username column not found — cannot compare users.")
        st.stop()

    st.markdown("## User Overview")
    total_posts = df["URL"].nunique()
    total_likes = df["Likes"].sum()
    total_comments = df["Comments"].notna().sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
    with col2:
        st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
    with col3:
        st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")

    st.markdown("## 📌 Explore Posts")
    post_urls = df["URL"].unique().tolist()
    selected_posts = st.multiselect("🔗 Select one or more Posts (URLs)", post_urls)

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
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Scraped Data as CSV",
            data=csv_bytes,
            file_name="full_scraped_report.csv",
            mime="text/csv"
        )
