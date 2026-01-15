import json
import re
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_tracker_json(url):
    """
    Opens a Chrome window to the Tracker.gg API URL, waits for the user to bypass Cloudflare,
    and then saves the JSON response to the matches folder.
    """
    # Extract match ID from URL
    match_id_match = re.search(r'match/([a-zA-Z0-9\-]+)', url)
    if not match_id_match:
        print("❌ Invalid Tracker.gg match URL")
        return
    
    match_id = match_id_match.group(1)
    api_url = f"https://api.tracker.gg/api/v2/valorant/standard/matches/{match_id}"
    
    print(f"🚀 Target Match ID: {match_id}")
    print(f"🔗 API URL: {api_url}")
    
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Don't use headless to allow manual Cloudflare bypass
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1200,800")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Use existing Chrome profile if possible to avoid bot detection
    # chrome_options.add_argument(f"--user-data-dir={os.path.expanduser('~')}\\AppData\\Local\\Google\\Chrome\\User Data")

    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("🌐 Opening browser... Please solve any Cloudflare challenges if they appear.")
        driver.get(api_url)
        
        # Wait for the JSON content to appear (it's usually inside a <pre> tag in the browser)
        print("⏳ Waiting for JSON data to load...")
        time.sleep(5) # Give it a few seconds for Cloudflare
        
        # Check if we are blocked
        if "Just a moment" in driver.title or "Cloudflare" in driver.page_source:
            print("🛡️ Cloudflare challenge detected. Please solve it in the browser window.")
            # Wait up to 60 seconds for the user to solve it
            WebDriverWait(driver, 60).until_not(EC.title_contains("Just a moment"))
        
        # Get the page source (which should be the raw JSON)
        content = driver.find_element(By.TAG_NAME, "body").text
        
        # Try to parse as JSON to verify
        try:
            data = json.loads(content)
            print("✅ JSON data successfully retrieved!")
            
            # Save to matches folder
            if not os.path.exists("matches"):
                os.makedirs("matches")
            
            filename = f"match_{match_id}.json"
            filepath = os.path.join("matches", filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
            print(f"💾 Saved to: {filepath}")
            print(f"👉 You can now enter '{match_id}' in the Portal to load this data.")
            
        except json.JSONDecodeError:
            print("❌ Failed to parse page content as JSON. Content preview:")
            print(content[:200])
            
    finally:
        print("🚪 Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = input("🔗 Enter Tracker.gg Match URL: ")
    
    get_tracker_json(target_url)
