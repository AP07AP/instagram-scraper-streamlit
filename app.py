# -------------------------------
# Scrape & Store Data
# -------------------------------
if st.button("📑 Scrape & Get Report"):
    if not profile_url or not username or not password:
        st.warning("Please fill all the inputs.")
        st.stop()

    st.info("Triggering scraper workflow...")
    
    # Trigger workflow (same as before)
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
        headers=headers,
        json=payload
    )
    if r.status_code != 204:
        st.error(f"Failed to trigger workflow: {r.text}")
        st.stop()

    st.info("Waiting for workflow to finish (~10 mins)...")

    # Poll workflow
    workflow_completed = False
    max_polls = 100
    for _ in range(max_polls):
        runs = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/runs",
            headers=headers
        ).json()
        latest_run = runs.get("workflow_runs", [None])[0]
        if latest_run and latest_run.get("status") == "completed":
            workflow_completed = True
            break
        time.sleep(6)

    if not workflow_completed:
        st.error("Workflow did not complete in time. Try again later.")
        st.stop()

    st.success("✅ Scraper finished! Fetching data...")

    # Fetch artifact
    df = fetch_artifact_csv(REPO, GITHUB_TOKEN)
    if df is None or df.empty:
        st.warning("No data found in artifact.")
        st.stop()

    # Store in session state
    st.session_state["scraped_df"] = df


# -------------------------------
# Post-explorer (persistent across reruns)
# -------------------------------
if "scraped_df" in st.session_state:
    df = st.session_state["scraped_df"]

    # Process CSV
    df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
    df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce').dt.time
    df["Comments"] = df["Comments"].replace("", pd.NA)

    # -------------------------------
    # User Overview
    # -------------------------------
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

    # -------------------------------
    # Explore Posts
    # -------------------------------
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
