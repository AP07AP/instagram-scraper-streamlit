import streamlit as st
from scraper import scrape_instagram_posts

st.title("📸 Instagram Scraper Dashboard")

# Inputs
profile_url = st.text_input("Instagram Profile URL", "https://www.instagram.com/vangalapudianitha/")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")
password = st.text_input("Instagram Password", type="password")
output_file = st.text_input("Output CSV File Name", "instagram_data.csv")

if st.button("🚀 Run Scraper"):
    with st.spinner("Scraping Instagram posts..."):
        try:
            df = scrape_instagram_posts(
                profile_url=str(profile_url),
                start_date=str(start_date),
                end_date=str(end_date),
                username=username,
                password=password,
                output_file=output_file
            )
            if not df.empty:
                st.success(f"✅ Scraping completed! {len(df)} rows saved to {output_file}")
                st.dataframe(df.head(10))
                st.download_button("📥 Download CSV", df.to_csv(index=False), file_name=output_file)
            else:
                st.warning("⚠️ No data scraped for the given date range.")
        except Exception as e:
            st.error(f"❌ Error during scraping: {e}")
