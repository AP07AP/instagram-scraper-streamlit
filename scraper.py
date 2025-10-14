import os
import time
import random
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException


def scrape_instagram_posts(profile_url, start_date, end_date, username, password, output_file="scraped_data.csv"):
    # --- Edge options ---
    edge_options = Options()
    edge_options.add_argument("--disable-blink-features=AutomationControlled")
    edge_options.add_argument("--disable-notifications")
    edge_options.add_argument("--start-maximized")
    edge_options.add_argument("--headless=new")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--window-size=1920,1080")

    # --- Initialize Edge ---
    service = Service()  # Add path if msedgedriver.exe not in PATH
    driver = webdriver.Edge(service=service, options=edge_options)
    wait = WebDriverWait(driver, 15)
    data = []

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    try:
        # --- LOGIN ---
        driver.get("https://www.instagram.com/")
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        print("✅ Logged in")
        time.sleep(7)

        # --- PROFILE PAGE ---
        driver.get(profile_url)
        print("✅ Profile loaded")
        time.sleep(5)

        # --- FIRST POST ---
        first_post_xpath = (
            '/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[2]/div[1]'
            '/section/main/div/div/div[2]/div/div/div/div/div[1]/div[1]/a'
        )
        first_post = wait.until(EC.presence_of_element_located((By.XPATH, first_post_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", first_post)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", first_post)
        print("✅ Clicked first post")
        time.sleep(3)

        post_count = 0
        while True:
            post_count += 1
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

            if post_count > 3 and datetime_obj and datetime_obj.date() < start_dt.date():
                break

            # --- Likes ---
            try:
                likes = driver.find_element(By.XPATH, '//section[2]/div/div/span/a/span/span').text
            except NoSuchElementException:
                likes = "Hidden"

            # --- Caption and Comments ---
            all_comments_data = []
            if datetime_obj and start_dt.date() <= datetime_obj.date() <= end_dt.date():
                try:
                    comments_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[3]/div/div')
                        )
                    )

                    # Caption
                    try:
                        caption_elem = comments_container.find_element(
                            By.XPATH, '/html/body/div[4]/div[1]/div/div[3]/div/div/div/div/div[2]/div/article/div/div[2]/div/div/div[2]/div[1]/ul/div[1]/li/div/div/div[2]/div[1]/h1'
                        )
                        caption_text = caption_elem.text.strip()
                        all_comments_data.append(caption_text)
                    except NoSuchElementException:
                        caption_text = "N/A"

                    # Load all comments
                    prev_count = 0
                    while True:
                        comment_blocks = comments_container.find_elements(By.XPATH, './div[position()>=1]/ul/div/li/div/div/div[2]/div[1]/span')
                        current_count = len(comment_blocks)

                        for comment_elem in comment_blocks[prev_count:]:
                            try:
                                comment_text = comment_elem.text.strip()
                                all_comments_data.append(comment_text)
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
                    pass

            # --- Save data ---
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
                break

    finally:
        driver.quit()

    # --- Save CSV ---
    if data:
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"✅ Data saved to {output_file} ({len(df)} rows)")
        return df
    else:
        print("⚠️ No data scraped.")
        return pd.DataFrame()


# --- Run via CLI ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print("Usage: python scraper.py <profile_url> <start_date> <end_date> <username> <password>")
        sys.exit(1)
    scrape_instagram_posts(*sys.argv[1:])
