# ----------------------------------
# scraper.py
# ----------------------------------
import time
import random
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

def scrape_instagram_posts(profile_url, start_date, end_date, username, password, output_file="scraped_data.csv"):
    # -------------------------------
    # Chrome options (headless for CI)
    # -------------------------------
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--window-size=1920,1080")

    # Chromium binary location on GitHub Actions
    chrome_options.binary_location = "/usr/bin/chromium-browser"

    # -------------------------------
    # Launch Chrome with version compatibility
    # -------------------------------
    driver = uc.Chrome(options=chrome_options, version_main=141)
    wait = WebDriverWait(driver, 15)
    data = []

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    try:
        # Login
        driver.get("https://www.instagram.com/")
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        time.sleep(7)

        # Navigate to profile
        driver.get(profile_url)
        time.sleep(5)

        # Click first post
        first_post_xpath = (
            '/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[2]/div[1]'
            '/section/main/div/div/div[2]/div/div/div/div/div[1]/div[1]/a'
        )
        first_post = wait.until(EC.presence_of_element_located((By.XPATH, first_post_xpath)))
        driver.execute_script("arguments[0].click();", first_post)
        time.sleep(3)

        post_count = 0
        while True:
            post_count += 1
            post_url = driver.current_url

            # --- Date & Time ---
            try:
                date_element = driver.find_element(By.XPATH, '//time')
                datetime_str = date_element.get_attribute("datetime")
                datetime_obj = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                date_posted = datetime_obj.strftime("%Y-%m-%d")
                time_posted = datetime_obj.strftime("%H:%M:%S")
            except NoSuchElementException:
                datetime_obj = None
                date_posted, time_posted = "Unknown", "Unknown"

            # Stop scraping if older than start date
            if post_count > 3 and datetime_obj and datetime_obj.date() < start_dt.date():
                break

            # --- Likes ---
            try:
                likes = driver.find_element(By.XPATH, '//section[2]/div/div/span/a/span/span').text
            except NoSuchElementException:
                likes = "Hidden"

            # --- Comments & Caption ---
            comments = []
            if datetime_obj and start_dt.date() <= datetime_obj.date() <= end_dt.date():
                try:
                    comments_elems = driver.find_elements(By.XPATH, '//ul/div/li/div/div/div[2]/div[1]/span')
                    comments = [elem.text.strip() for elem in comments_elems]
                except Exception:
                    pass

            for i, comment in enumerate(comments):
                data.append({
                    "Post": post_count if i == 0 else "",
                    "URL": post_url if i == 0 else "",
                    "Date": date_posted if i == 0 else "",
                    "Time": time_posted if i == 0 else "",
                    "Likes": likes if i == 0 else "",
                    "Comment": comment
                })

            # --- Next post ---
            try:
                next_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//button[contains(@class, "_abl-")]')
                ))
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(3, 5))
            except TimeoutException:
                break

    finally:
        driver.quit()

    # --- Save CSV ---
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ Saved {len(df)} rows to {output_file}")
    return df

# Run via CLI (GitHub Action)
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print("Usage: python scraper.py <profile_url> <start_date> <end_date> <username> <password>")
        sys.exit(1)
    scrape_instagram_posts(*sys.argv[1:])
