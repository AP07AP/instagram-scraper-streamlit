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
st.title("📸 Instagram Analyser Dashboard")

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
# SCRAPE & REPORT BUTTONS (same line)
# -------------------------------
# col_scrape, col_report = st.columns([1,1])
col_scrape, col_spacer, col_report = st.columns([1, 2, 1])

with col_scrape:
    scrape_clicked = st.button("🕸️ Scrape Data")

with col_report:
    report_clicked = st.button("📊 Get Report")

# -------------------------------
# SCRAPE LOGIC
# -------------------------------
if scrape_clicked:
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
# REPORT LOGIC
# -------------------------------
if report_clicked and st.session_state.get("scrape_done", False):
    artifact_name = st.session_state.get("artifact_name", ARTIFACT_NAME)
    st.info(f"📦 Fetching artifact `{artifact_name}` ...")

    df = fetch_artifact_csv(REPO, GITHUB_TOKEN, artifact_name)
    if df is None or df.empty:
        st.warning("⚠️ No data found in your artifact.")
        st.stop()

    # -------------------------------
    # Sentiment Analysis Integration
    # -------------------------------
    import sentiment_model

    if "Comments" in df.columns and not df["Comments"].isna().all():
        st.info("🧠 Running Sentiment Analysis on Comments...")
        df = sentiment_model.analyze_comments(df, column="Comments")
        st.success("✅ Sentiment Analysis Completed!")

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

    # -------------------------------
    # Overall Overview (All Users)
    # -------------------------------
    st.markdown("## 📊 Overall Overview")

    total_posts = df["URL"].nunique()
    total_likes = df["Likes"].sum()
    total_comments = df["Comments"].notna().sum()

    all_comments = df[df["Comments"].notna()]
    sentiment_counts = (
        all_comments["Sentiment_label"].astype(str).str.strip().str.title().value_counts(normalize=True) * 100
    )
    pos_pct = sentiment_counts.get("Positive", 0.0)
    neg_pct = sentiment_counts.get("Negative", 0.0)
    neu_pct = sentiment_counts.get("Neutral", 0.0)

    col1, col2, col3, col4 = st.columns([1,1.5,1.5,2])
    with col1:
        st.write(f"📄 **Posts:** {format_indian_number(total_posts)}")
    with col2:
        st.write(f"❤️ **Likes:** {format_indian_number(total_likes)}")
    with col3:
        st.write(f"💬 **Comments:** {format_indian_number(total_comments)}")
    with col4:
        st.markdown(
            f"**Overall Sentiment:**  \n"
            f"🙂 Positive: {pos_pct:.1f}%  \n"
            f"😡 Negative: {neg_pct:.1f}%  \n"
            f"😐 Neutral: {neu_pct:.1f}%"
        )

    # -------------------------------
    # Profile Summary Table with Sentiment
    # -------------------------------
    if "username" in df.columns:
        st.markdown("## 👥 Profile Summary")
        summary_df = df.groupby("username").agg(
            Total_Posts=("URL", "nunique"),
            Total_Likes=("Likes", "sum"),
            Total_Comments=("Comments", lambda x: x.notna().sum()),
        ).reset_index()

        sentiments_list = []
        for user in summary_df["username"]:
            user_comments = df[(df["username"]==user) & (df["Comments"].notna())]
            scounts = (user_comments["Sentiment_label"].astype(str).str.strip().str.title().value_counts(normalize=True)*100)
            sentiments_list.append(f"🙂 {scounts.get('Positive',0):.1f}% | 😡 {scounts.get('Negative',0):.1f}% | 😐 {scounts.get('Neutral',0):.1f}%")
        summary_df["Sentiment"] = sentiments_list

        summary_df["Total_Likes"] = summary_df["Total_Likes"].apply(format_indian_number)
        summary_df["Total_Comments"] = summary_df["Total_Comments"].apply(format_indian_number)

        st.dataframe(summary_df, use_container_width=True)

        selected_users = st.multiselect(
            "Select profiles to explore",
            options=summary_df["username"].tolist(),
        )

        # -------------------------------
        # User Overview for Selected Users + User-wise Post Exploration + Download
        # -------------------------------
        for selected_user in selected_users:
            st.markdown(f"## 👤 User Overview: {selected_user}")
            filtered = df[df["username"] == selected_user]

            total_posts = filtered["URL"].nunique()
            total_likes = filtered["Likes"].sum()
            total_comments = filtered["Comments"].notna().sum()

            all_comments_user = filtered[filtered["Comments"].notna()]
            sentiment_counts_user = (all_comments_user["Sentiment_label"].astype(str).str.strip().str.title().value_counts(normalize=True)*100)
            pos_pct = sentiment_counts_user.get("Positive", 0.0)
            neg_pct = sentiment_counts_user.get("Negative", 0.0)
            neu_pct = sentiment_counts_user.get("Neutral", 0.0)

            col1, col2, col3, col4, col5 = st.columns([2,1,1,1,2])
            with col1:
                img_path = f"{selected_user}.jpg"
                try:
                    st.image(img_path, width=150, caption=selected_user)
                except Exception:
                    st.markdown(f"**Name:** {selected_user}")

            with col2:
                st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
            with col3:
                st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
            with col4:
                st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")
            with col5:
                st.markdown(
                    f"**Overall Sentiment:**  \n"
                    f"🙂 Positive: {pos_pct:.1f}%  \n"
                    f"😡 Negative: {neg_pct:.1f}%  \n"
                    f"😐 Neutral: {neu_pct:.1f}%"
                )

            # User-wise Post Exploration
            st.markdown(f"### 📌 Explore Posts: {selected_user}")
            post_urls_user = filtered["URL"].unique().tolist()
            selected_posts_user = st.multiselect(
                f"🔗 Select Posts for {selected_user}",
                post_urls_user,
                key=f"posts_{selected_user}"
            )

            if selected_posts_user:
                multi_posts_user = filtered[filtered["URL"].isin(selected_posts_user)]
                st.subheader(f"📝 Selected Posts Details: {selected_user}")
                for url in selected_posts_user:
                    post_group = multi_posts_user[multi_posts_user["URL"] == url]
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
                            if "Sentiment_label" in comments_only.columns:
                                comments_only["Sentiment_label"] = comments_only["Sentiment_label"].astype(str).str.title()
                                sentiment_filter = st.selectbox(
                                    f"Filter comments by Sentiment ({url})", 
                                    ["All", "Positive", "Negative", "Neutral"],
                                    key=f"filter_{url}_{selected_user}"
                                )
                                if sentiment_filter != "All":
                                    comments_only = comments_only[comments_only["Sentiment_label"] == sentiment_filter]

                                st.dataframe(
                                    comments_only[["Comments", "Sentiment_label", "Sentiment_score"]].reset_index(drop=True),
                                    use_container_width=True
                                )

                                sentiment_counts_post = post_group[post_group["Comments"].notna()]["Sentiment_label"].astype(str).str.title().value_counts(normalize=True) * 100
                                st.markdown(
                                    f"**Post Sentiment:**  \n"
                                    f"🙂 Positive: {sentiment_counts_post.get('Positive', 0):.1f}% | "
                                    f"😡 Negative: {sentiment_counts_post.get('Negative', 0):.1f}% | "
                                    f"😐 Neutral: {sentiment_counts_post.get('Neutral', 0):.1f}%"
                                )
                            else:
                                st.dataframe(comments_only[["Comments"]].reset_index(drop=True), use_container_width=True)
                        else:
                            st.info("No comments available for this post.")
                    st.markdown("---")

                # Download Button for Selected Posts (User-wise)
                download_df_user = multi_posts_user.copy()
                download_df_user["Likes"] = download_df_user["Likes"].astype(int)
                csv_bytes_user = download_df_user.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Download Selected Posts for {selected_user}",
                    data=csv_bytes_user,
                    file_name=f"{selected_user}_selected_posts.csv",
                    mime="text/csv"
                )

            # Download Overall User Data
            # Download Overall User Data as Excel
            excel_buffer_user = BytesIO()
            filtered_copy = filtered.copy()
            filtered_copy["Likes"] = filtered_copy["Likes"].astype(int)
            with pd.ExcelWriter(excel_buffer_user) as writer:
                filtered_copy.to_excel(writer, index=False, sheet_name='User Data')
            excel_buffer_user.seek(0)
            
            st.download_button(
                label=f"📥 Download Full Data for {selected_user}",
                data=excel_buffer_user,
                file_name=f"{selected_user}_full_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


    # Full dataset download
    
    # Full dataset download as Excel
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        writer.save()
    output.seek(0)
    
    st.download_button(
        label="📥 Download Full Scraped Data as Excel",
        data=output,
        file_name="full_scraped_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
