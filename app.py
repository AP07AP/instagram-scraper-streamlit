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
st.title("📸 Instagram Insights Dashboard")

# -------------------------------
# Scraper Inputs
# -------------------------------
profile_url = st.text_area(
    "Enter one or more Instagram Profile URLs or Usernames (comma separated or one per line)",
    height=20,
    placeholder="https://www.instagram.com/user1/"
)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input(
    "Name",
    placeholder="Enter your Name"
)

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
        # st.error(f"❌ Artifact {artifact_name} not found yet. Try again in a few seconds.")
        st.error(f"❌ Dataset not found yet. Try again in a few seconds.")
        st.stop()

    # Download artifact
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts", headers=headers)
    artifacts = r.json().get("artifacts", [])
    artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
    if not artifact:
        # st.error(f"❌ Artifact {artifact_name} not found.")
        st.error(f"❌ Dataset not found.")
        return None

    download_url = artifact["archive_download_url"]
    r = requests.get(download_url, headers=headers)
    if r.status_code != 200:
        # st.error("❌ Failed to download artifact.")
        st.error("❌ Failed to download Dataset.")
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

    # Unique artifact per user/session: username + short UUID
    unique_id = uuid.uuid4().hex[:6]
    st.session_state["artifact_name"] = f"scraped_data_{username}_{unique_id}"

    # st.info(f"🚀 Triggering scraper workflow for artifact: `{st.session_state['artifact_name']}`")
    st.info(f"🚀 Scraping Started")

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

    # st.info("⏳ Waiting for workflow to complete (up to 5 mins)...")
    st.info("⏳ Waiting for scraping to complete (up to 5 mins)...")

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
    # st.info(f"📦 Fetching artifact `{artifact_name}` ...")
    st.info(f"📦 Fetching Dataset `{artifact_name}` ...")

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

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
    with col2:
        st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
    with col3:
        st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")

        # -------------------------------
    # -------------------------------
    # Sentiment Visualization + Top Hashtags (Overall)
    # -------------------------------
    # st.markdown("### 📈 Sentiment Distribution & Top Hashtags (Overall)")
    
    # Prepare sentiment dataframe
    df_sentiment_overall = pd.DataFrame({
        "Sentiment": ["🙂 Positive", "😡 Negative", "😐 Neutral"],
        "Percentage": [pos_pct, neg_pct, neu_pct]
    })
    
    # Prepare top hashtags (overall)
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
        y_limit = y_max + 5  # add margin so text labels aren’t cut
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
            title_x=0.2,  # Center the title
            yaxis_title="Percentage",
            xaxis_title="",
            showlegend=False,
            uniformtext_minsize=12,
            uniformtext_mode='hide',
            yaxis=dict(range=[0, y_limit]) 
        )
        st.plotly_chart(fig_sent_overall, use_container_width=True)
    
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
                title_x=0.5,  # Center the title
                yaxis=dict(autorange="reversed"),
                xaxis_title="Frequency",
                yaxis_title="Hashtags",
                uniformtext_minsize=12,
                uniformtext_mode='hide',
                bargap=0.3
            )
            st.plotly_chart(fig_hash_overall, use_container_width=True)
        else:
            st.info("No hashtags found overall.")



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

            col2, col3, col4 = st.columns([1,1,1])
            # with col1:
            #     img_path = f"{selected_user}.jpg"
            #     try:
            #         st.image(img_path, width=150, caption=selected_user)
            #     except Exception:
            #         st.markdown(f"**Name:** {selected_user}")

            with col2:
                st.write(f"📄 **Total Posts:** {format_indian_number(total_posts)}")
            with col3:
                st.write(f"❤️ **Total Likes:** {format_indian_number(total_likes)}")
            with col4:
                st.write(f"💬 **Total Comments:** {format_indian_number(total_comments)}")
    
            # -------------------------------
            # st.markdown(f"### 📊 Sentiment Distribution & Top Hashtags for {selected_user}")

            # Sentiment DataFrame
            df_sentiment_user = pd.DataFrame({
                "Sentiment": ["🙂 Positive", "😡 Negative", "😐 Neutral"],
                "Percentage": [pos_pct, neg_pct, neu_pct]
            })
        
            # Hashtags DataFrame
            hashtags_list_user = filtered['Hashtags'].dropna().tolist()
            all_hashtags_user = []
            for h in hashtags_list_user:
                all_hashtags_user.extend([tag.strip() for tag in h.split(",")])
        
            from collections import Counter
            top_hashtags_user = Counter(all_hashtags_user).most_common(10)
        
            if top_hashtags_user:
                tags, counts = zip(*top_hashtags_user)
                df_hashtags_user = pd.DataFrame({"Hashtag": tags, "Frequency": counts})
            else:
                df_hashtags_user = pd.DataFrame({"Hashtag": [], "Frequency": []})
        
            # Layout (side-by-side)
            col_sent_user, col_hash_user = st.columns([1, 1.5])
        
            with col_sent_user:
                y_max_user = df_sentiment_user["Percentage"].max()
                y_limit_user = y_max_user + 5  # Add margin so text isn’t cut
                fig_sent_user = px.bar(
                    df_sentiment_user,
                    x="Sentiment",
                    y="Percentage",
                    text="Percentage",
                    color="Sentiment",
                    color_discrete_map={
                        "🙂 Positive": "green",
                        "😡 Negative": "red",
                        "😐 Neutral": "gray"
                    },
                    title=f"Sentiment Distribution"
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
                    showlegend=False,
                    uniformtext_minsize=12,
                    uniformtext_mode='hide',
                    yaxis=dict(range=[0, y_limit_user])
                )
                st.plotly_chart(fig_sent_user, use_container_width=True, key=f"sent_chart_{selected_user}")
        
            with col_hash_user:
                if not df_hashtags_user.empty:
                    fig_hash_user = px.bar(
                        df_hashtags_user.sort_values("Frequency", ascending=False),
                        x="Frequency",
                        y="Hashtag",
                        orientation='h',
                        text="Frequency",
                        labels={"Frequency": "Count", "Hashtag": "Hashtags"},
                        title=f"Top 10 Hashtags for {selected_user}"
                    )
                    fig_hash_user.update_traces(
                        texttemplate='%{text}',
                        textposition='inside',
                        textangle=0,
                        insidetextanchor='middle',
                        marker_color='lightblue',
                        cliponaxis=False
                    )
                    fig_hash_user.update_layout(
                        title_x=0.2,
                        yaxis=dict(autorange="reversed"),
                        xaxis_title="Frequency",
                        yaxis_title="Hashtags",
                        uniformtext_minsize=12,
                        uniformtext_mode='hide',
                        bargap=0.3
                    )
                    st.plotly_chart(fig_hash_user, use_container_width=True)
                else:
                    st.info(f"No hashtags found for {selected_user}.")



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

                    # Total comments for this post
                    total_comments_post = post_group["Comments"].notna().sum()

                    if not caption_row.empty:
                        row = caption_row.iloc[0]

                        # Format likes and comments
                        likes_formatted = format_indian_number(row["Likes"])
                        comments_formatted = format_indian_number(total_comments_post)

                        st.markdown(
                            f"**Caption:** {row['Caption']} 🔗 [View Post]({url})  \n\n"
                            f"📅 {row['Date'].date()}  🕒 {row['Time']}  ❤️ Likes: {likes_formatted}  💬 Comments: {comments_formatted}  \n"
                        )

                        # Calculate post sentiment (if comments exist)
                        comments_with_sentiment = post_group[post_group["Comments"].notna()]
                        if not comments_with_sentiment.empty and "Sentiment_label" in comments_with_sentiment.columns:
                            sentiment_counts_post = (
                                comments_with_sentiment["Sentiment_label"].astype(str).str.title().value_counts(normalize=True) * 100
                            )

                            # -------------------------
                            # --- Plot Sentiment Only ---
                            # -------------------------
                            df_sentiment = pd.DataFrame({
                                "Sentiment": ["🙂 Positive", "😡 Negative", "😐 Neutral"],
                                "Percentage": [
                                    sentiment_counts_post.get("Positive", 0),
                                    sentiment_counts_post.get("Negative", 0),
                                    sentiment_counts_post.get("Neutral", 0)
                                ]
                            })
                            
                            # Create a column just for sentiment
                            col_sent = st.container()
                            
                            with col_sent:
                                y_max = df_sentiment["Percentage"].max()
                                y_limit = y_max + 5  # Add small margin so labels don’t get cut
                                fig_sent = px.bar(
                                    df_sentiment,
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
                                fig_sent.update_traces(
                                    texttemplate='%{text:.1f}%',
                                    textposition='outside',
                                    marker_line_width=0.5
                                )
                                fig_sent.update_layout(
                                    yaxis_title="Percentage",
                                    xaxis_title="",
                                    showlegend=False,
                                    uniformtext_minsize=12,
                                    uniformtext_mode='hide',
                                    yaxis=dict(range=[0, y_limit]),
                                    title_x=0.4
                                )
                                st.plotly_chart(fig_sent, use_container_width=True, key=f"sent_chart_{selected_user}_{url}")
                                # st.markdown("---")
                
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
            st.markdown("---")

    # Full dataset download as Excel
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
