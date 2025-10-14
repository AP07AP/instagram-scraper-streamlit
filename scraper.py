import os
import time
import random
import pandas as pd
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
sys.stdout.reconfigure(encoding='utf-8')
def scrape_instagram(profile_url, start_date, end_date, username, password):
    # Generate output filename dynamically
    start_str = datetime.strptime(start_date, "%Y-%m-%d").strftime("%m-%d")
    end_str = datetime.strptime(end_date, "%Y-%m-%d").strftime("%m-%d")
    insta_user = profile_url.strip("/").split("/")[-1]
    output_file = f"{start_str}_{end_str}_{insta_user}.csv"

    # Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize Chrome driver
    service = Service()  # Add path if chromedriver not in PATH
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 15)

    # Login
    driver.get("https://www.instagram.com/")
    print("🔄 Opening Instagram...")
    try:
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        print("✅ Logged into Instagram")
        time.sleep(7)
    except Exception as e:
        print(f"⚠️ Login error: {e}")
        driver.quit()
        return

    # Navigate to profile
    driver.get(profile_url)
    print("✅ Profile page loaded")
    time.sleep(5)

    # Click first post
    first_post_xpath = '/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[2]/div[1]/section/main/div/div/div[2]/div/div/div/div/div[1]/div[1]/a'
    try:
        first_post = wait.until(EC.presence_of_element_located((By.XPATH, first_post_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", first_post)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", first_post)
        print("✅ Clicked first post")
        time.sleep(3)
    except Exception as e:
        print(f"⚠️ Error clicking first post: {e}")
        driver.save_screenshot("click_error.png")
        driver.quit()
        return

    # Scrape posts
    data = []
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    post_count = 0
    while True:
        post_count += 1
        print(f"\n📸 Scraping Post {post_count}")
        try:
            post_url = driver.current_url

            # Date
            try:
                date_element = driver.find_element(By.XPATH, '//time')
                datetime_str = date_element.get_attribute("datetime")
                datetime_obj = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                date_posted = datetime_obj.strftime("%Y-%m-%d")
                time_posted = datetime_obj.strftime("%H:%M:%S")
            except NoSuchElementException:
                datetime_obj = None
                date_posted, time_posted = "Unknown", "Unknown"

            if post_count > 3 and datetime_obj and datetime_obj.date() < start_dt.date():
                print(f"🛑 Post {post_count} is older than start date. Stopping scrape.")
                break

            # Likes
            try:
                likes = driver.find_element(By.XPATH, '//section[2]/div/div/span/a/span/span').text
            except NoSuchElementException:
                likes = "Hidden"

            # Caption & comments
            all_comments_data = []
            if datetime_obj and start_dt.date() <= datetime_obj.date() <= end_dt.date():
                try:
                    comments_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[3]/div/div'))
                    )
                    # Caption
                    try:
                        caption_elem = comments_container.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[1]/li/div/div/div[2]/div[1]/h1')
                        caption_text = caption_elem.text.strip()
                        all_comments_data.append(caption_text)
                        print(f"📝 Caption: {caption_text}")
                    except NoSuchElementException:
                        pass

                    # Load comments
                    prev_count = 0
                    while True:
                        comment_blocks = comments_container.find_elements(By.XPATH, './div[position()>=1]/ul/div/li/div/div/div[2]/div[1]/span')
                        current_count = len(comment_blocks)

                        for comment_elem in comment_blocks[prev_count:]:
                            try:
                                comment_text = comment_elem.text.strip()
                                all_comments_data.append(comment_text)
                                print(f"💬 Comment: {comment_text}")
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
            else:
                print(f"⏭ Post {post_count} skipped: date {date_posted} not in range.")

            # Save post data
            first_row = True
            for comment in all_comments_data:
                data.append({
                    "Post_Number": post_count if first_row else "",
                    "URL": post_url if first_row else "",
                    "Date": date_posted if first_row else "",
                    "Time": time_posted if first_row else "",
                    "Likes": likes if first_row else "",
                    "Comment": comment
                })
                first_row = False

            # Next post
            try:
                next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//div[contains(@class, "_aaqg") and contains(@class, "_aaqh")]//button[contains(@class, "_abl-")]')))
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(3, 5))
            except TimeoutException:
                print("⚠️ Next button not found, stopping.")
                break

        except Exception as e:
            print(f"⚠️ Error scraping post {post_count}: {e}")
            continue

    # Save to CSV
    if data:
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n✅ Data saved to {output_file} (Rows: {len(df)})")
    else:
        print("\n⚠️ No data scraped.")

    driver.quit()
    print("\n✅ Scraping completed successfully!")

# -------------------------
# CLI Run
# -------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print("Usage: python scraper.py <profile_url> <start_date> <end_date> <username> <password>")
        sys.exit(1)
    scrape_instagram(*sys.argv[1:])
