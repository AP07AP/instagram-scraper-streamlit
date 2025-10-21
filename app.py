# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import pandas as pd
import time
import uuid
import plotly.express as px
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
col_scrape, col_spacer, col_report = st.columns([1, 2.8, 1])

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
    for _ in range(600):
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

    df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
    df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce").dt.time
    df["Comments"] = df["Comments"].replace("", pd.NA)

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

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
    with col2:
        st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
    with col3:
        st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")

    df_sentiment_overall = pd.DataFrame({
        "Sentiment": ["🙂 Positive", "😡 Negative", "😐 Neutral"],
        "Percentage": [pos_pct, neg_pct, neu_pct]
    })

    hashtags_list_overall = df['Hashtags'].dropna().tolist()
    all_hashtags_overall = []
    for h in hashtags_list_overall:
        all_hashtags_overall.extend([tag.strip() for tag in h.split(",")])

    from collections import Counter
    top_hashtags_overall = Counter(all_hashtags_overall).most_common(10)
    if top_hashtags_overall:
        tags, counts = zip(*top_hashtags_overall)
        df_hashtags_overall = pd.DataFrame({"Hashtag": tags, "Frequency": counts})
    else:
        df_hashtags_overall = pd.DataFrame({"Hashtag": [], "Frequency": []})

    col_sent_overall, col_hash_overall = st.columns([1, 1.5])

    with col_sent_overall:
        y_max = df_sentiment_overall["Percentage"].max()
        y_limit = y_max + 5
        fig_sent_overall = px.bar(
            df_sentiment_overall,
            x="Sentiment",
            y="Percentage",
            text="Percentage",
            color="Sentiment",
            color_discrete_map={
                "🙂 Positive": "green",
                "😡 Negative": "red",
                "😐 Neutral": "gray"
            },
            title="Sentiment Distribution"
        )
        fig_sent_overall.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside',
            marker_line_width=0.5
        )
        fig_sent_overall.update_layout(
            title_x=0.2,
            yaxis_title="Percentage",
            xaxis_title="",
            showlegend=False,
            uniformtext_minsize=12,
            uniformtext_mode='hide',
            yaxis=dict(range=[0, y_limit])
        )
        st.plotly_chart(fig_sent_overall, use_container_width=True, key="sent_overall")

    with col_hash_overall:
        if not df_hashtags_overall.empty:
            fig_hash_overall = px.bar(
                df_hashtags_overall.sort_values("Frequency", ascending=False),
                x="Frequency",
                y="Hashtag",
                orientation='h',
                text="Frequency",
                labels={"Frequency": "Count", "Hashtag": "Hashtags"},
                title="Top 10 Hashtags"
            )
            fig_hash_overall.update_traces(
                texttemplate='%{text}',
                textposition='inside',
                textangle=0,
                insidetextanchor='middle',
                marker_color='lightblue',
                cliponaxis=False
            )
            fig_hash_overall.update_layout(
                title_x=0.5,
                yaxis=dict(autorange="reversed"),
                xaxis_title="Frequency",
                yaxis_title="Hashtags",
                uniformtext_minsize=12,
                uniformtext_mode='hide',
                bargap=0.3
            )
            st.plotly_chart(fig_hash_overall, use_container_width=True, key="hash_overall")
        else:
            st.info("No hashtags found overall.")

    # -------------------------------
    # USER-WISE VISUALIZATION
    # -------------------------------
    users = df['Profile'].unique().tolist()
    selected_user = st.selectbox("Select Profile for User-wise Analysis", users, key="user_select")

    df_user = df[df['Profile'] == selected_user]

    total_posts_user = df_user["URL"].nunique()
    total_likes_user = df_user["Likes"].sum()
    total_comments_user = df_user["Comments"].notna().sum()

    st.markdown(f"## 📊 {selected_user} Overview")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.write(f"📄 **Total Posts:** {format_indian_number(total_posts_user)}")
    with col2:
        st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes_user)}")
    with col3:
        st.write(f"💬 **Total Comments:** {format_indian_number(total_comments_user)}")

    df_sent_user = pd.DataFrame({
        "Sentiment": ["🙂 Positive", "😡 Negative", "😐 Neutral"],
        "Percentage": [
            df_user['Sentiment_label'].str.lower().eq('positive').mean()*100,
            df_user['Sentiment_label'].str.lower().eq('negative').mean()*100,
            df_user['Sentiment_label'].str.lower().eq('neutral').mean()*100
        ]
    })

    hashtags_list_user = df_user['Hashtags'].dropna().tolist()
    all_hashtags_user = []
    for h in hashtags_list_user:
        all_hashtags_user.extend([tag.strip() for tag in h.split(",")])
    top_hashtags_user = Counter(all_hashtags_user).most_common(10)
    if top_hashtags_user:
        tags, counts = zip(*top_hashtags_user)
        df_hashtags_user = pd.DataFrame({"Hashtag": tags, "Frequency": counts})
    else:
        df_hashtags_user = pd.DataFrame({"Hashtag": [], "Frequency": []})

    col_sent_user, col_hash_user = st.columns([1, 1.5])

    with col_sent_user:
        fig_sent_user = px.bar(
            df_sent_user,
            x="Sentiment",
            y="Percentage",
            text="Percentage",
            color="Sentiment",
            color_discrete_map={
                "🙂 Positive": "green",
                "😡 Negative": "red",
                "😐 Neutral": "gray"
            },
            title=f"Sentiment Distribution - {selected_user}"
        )
        fig_sent_user.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside',
            marker_line_width=0.5
        )
        fig_sent_user.update_layout(
            title_x=0.2,
            yaxis_title="Percentage",
            xaxis_title="",
            showlegend=False
        )
        st.plotly_chart(fig_sent_user, use_container_width=True, key=f"sent_user_{selected_user}")

    with col_hash_user:
        if not df_hashtags_user.empty:
            fig_hash_user = px.bar(
                df_hashtags_user.sort_values("Frequency", ascending=False),
                x="Frequency",
                y="Hashtag",
                orientation='h',
                text="Frequency",
                labels={"Frequency": "Count", "Hashtag": "Hashtags"},
                title=f"Top 10 Hashtags - {selected_user}"
            )
            fig_hash_user.update_traces(
                texttemplate='%{text}',
                textposition='inside',
                marker_color='lightblue'
            )
            fig_hash_user.update_layout(
                title_x=0.5,
                yaxis=dict(autorange="reversed")
            )
            st.plotly_chart(fig_hash_user, use_container_width=True, key=f"hash_user_{selected_user}")

    # -------------------------------
    # POST-WISE SENTIMENT
    # -------------------------------
    st.markdown(f"### Post-wise Sentiment - {selected_user}")
    for idx, row in df_user.iterrows():
        url = row["URL"]
        sentiment = row.get("Sentiment_label", "Neutral")
        st.markdown(f"**Post:** {url} | **Sentiment:** {sentiment}")
        # individual post chart (if any)
        fig_post = px.pie(
            names=[sentiment],
            values=[1],
            title=f"Sentiment for Post {url}",
        )
        st.plotly_chart(fig_post, use_container_width=True, key=f"sent_post_{selected_user}_{idx}")

# -------------------------------
# Download Full Dataset
# -------------------------------
output = BytesIO()
with pd.ExcelWriter(output) as writer:
    df.to_excel(writer, index=False, sheet_name='Sheet1')
output.seek(0)

st.download_button(
    label="📥 Download Full Scraped Data as Excel",
    data=output,
    file_name="full_scraped_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
