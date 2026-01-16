
import json
import re
import os
import sys
from tracker_scraper import TrackerScraper

def get_tracker_json(url):
    """
    Uses TrackerScraper to fetch match data and save it to the matches folder.
    """
    scraper = TrackerScraper()
    
    if 'match' in url:
        data, error = scraper.get_match_data(url)
        if error:
            print(f"❌ Error: {error}")
            return
        
        filepath = scraper.save_match(data)
        if filepath:
            match_id = data['data']['attributes']['id']
            print(f"✅ JSON data successfully retrieved!")
            print(f"💾 Saved to: {filepath}")
            print(f"👉 You can now enter '{match_id}' in the Portal to load this data.")
    elif 'profile' in url:
        data, error = scraper.get_profile_data(url)
        if error:
            print(f"❌ Error: {error}")
            return
        
        filepath = scraper.save_profile(data)
        if filepath:
            print(f"✅ Profile data successfully retrieved!")
            print(f"💾 Saved to: {filepath}")
    else:
        print("❌ Invalid Tracker.gg URL. Must be a match or profile link.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = input("🔗 Enter Tracker.gg URL (Match or Profile): ")
    
    get_tracker_json(target_url)
