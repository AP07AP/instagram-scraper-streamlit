import os
import time
import random
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import sys

def scrape_instagram_posts(profile_url, start_date, end_date, username, password, output_file="scraped_data.csv"):
    # ------------------------------
    # Chrome options
    # ------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service()  # Add path to chromedriver.exe if not in PATH
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 15)

    data = []

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    try:
        # ------------------------------
        # LOGIN
        # ------------------------------
        driver.get("https://www.instagram.com/")
        print("🔄 Opening Instagram...")
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        login_button = driver.find_element(By.XPATH, '//button[@type="submit"]')
        login_button.click()
        print("✅ Logged in")
        time.sleep(7)

        # ------------------------------
        # Navigate to profile
        # ------------------------------
        driver.get(profile_url)
        print("✅ Profile loaded")
        time.sleep(5)

        # Click first post
        first_post_xpath = '/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[2]/div[1]/section/main/div/div/div[2]/div/div/div/div/div[1]/div[1]/a'
        first_post = wait.until(EC.presence_of_element_located((By.XPATH, first_post_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", first_post)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", first_post)
        print("✅ Clicked first post")
        time.sleep(3)

        # ------------------------------
        # Scrape posts
        # ------------------------------
        post_count = 0
        stop_scraping = False

        while not stop_scraping:
            post_count += 1
            print(f"\n📸 Scraping Post {post_count}")
            post_url = driver.current_url

            # --- Date ---
            try:
                date_element = driver.find_element(By.XPATH, '//time')
                datetime_str = date_element.get_attribute("datetime")
                datetime_obj = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                date_posted = datetime_obj.strftime("%Y-%m-%d")
                time_posted = datetime_obj.strftime("%H:%M:%S")
            except NoSuchElementException:
                datetime_obj = None
                date_posted, time_posted = "Unknown", "Unknown"

            # Stop if post older than start date
            if post_count > 3 and datetime_obj and datetime_obj.date() < start_dt.date():
                print(f"🛑 Post {post_count} older than start date. Stopping.")
                break

            # --- Likes ---
            try:
                likes = driver.find_element(By.XPATH, '//section[2]/div/div/span/a/span/span').text
            except NoSuchElementException:
                likes = "Hidden"

            # --- Caption and comments ---
            all_comments_data = []
            if datetime_obj and start_dt.date() <= datetime_obj.date() <= end_dt.date():
                try:
                    comments_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[3]/div/div'))
                    )

                    # Caption
                    try:
                        caption_elem = comments_container.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[1]/li/div/div/div[2]/div[1]/h1')
                        all_comments_data.append(caption_elem.text.strip())
                    except NoSuchElementException:
                        pass

                    prev_count = 0
                    while True:
                        comment_blocks = comments_container.find_elements(By.XPATH, './div[position()>=1]/ul/div/li/div/div/div[2]/div[1]/span')
                        current_count = len(comment_blocks)

                        for comment_elem in comment_blocks[prev_count:]:
                            try:
                                all_comments_data.append(comment_elem.text.strip())
                            except Exception:
                                continue

                        if current_count == prev_count:
                            break
                        prev_count = current_count

                        try:
                            load_more_btn = comments_container.find_element(By.XPATH, './li/div/button')
                            driver.execute_script("arguments[0].click();", load_more_btn)
                            time.sleep(2)
                        except NoSuchElementException:
                            break
                except Exception:
                    print("⚠️ Comments div not found")

            # --- Save post data ---
            first_row = True
            for comment in all_comments_data:
                if first_row:
                    data.append({
                        "Post_Number": post_count,
                        "URL": post_url,
                        "Date": date_posted,
                        "Time": time_posted,
                        "Likes": likes,
                        "Comment": comment
                    })
                    first_row = False
                else:
                    data.append({
                        "Post_Number": "",
                        "URL": "",
                        "Date": "",
                        "Time": "",
                        "Likes": "",
                        "Comment": comment
                    })

            # --- Next post ---
            try:
                next_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[contains(@class, "_aaqg") and contains(@class, "_aaqh")]//button[contains(@class, "_abl-")]')
                ))
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(3, 5))
            except TimeoutException:
                print("⚠️ Next button not found, stopping.")
                break

    finally:
        driver.quit()

    # Save CSV
    if data:
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n✅ Data saved to {output_file} (Rows: {len(df)})")
    else:
        print("\n⚠️ No data scraped.")


# ------------------------------
# CLI RUN
# ------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python scraper.py <profile_url> <start_date> <end_date> <username> <password>")
        sys.exit(1)

    scrape_instagram_posts(*sys.argv[1:])
