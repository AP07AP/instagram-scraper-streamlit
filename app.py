import streamlit as st
from PIL import Image
from scraper import scrape_instagram  # Make sure scraper.py returns screenshot path on error

st.title("📸 Instagram Scraper Dashboard (Local Run)")

profile_url = st.text_input("Instagram Profile URL")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")
password = st.text_input("Instagram Password", type="password")

if st.button("🚀 Run Scraper"):
    st.info("Running scraper locally...")
    screenshot_path = scrape_instagram(
        profile_url,
        str(start_date),
        str(end_date),
        username,
        password
    )

    if screenshot_path:
        st.error("⚠️ Error clicking first post!")
        img = Image.open(screenshot_path)
        st.image(img, caption="Click Error Screenshot", use_column_width=True)
    else:
        st.success("Scraper ran successfully! No errors.")
