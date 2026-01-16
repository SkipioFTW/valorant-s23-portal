
import re
import cloudscraper
import json
import os
import sys
import time

class TrackerScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_match_data(self, match_url):
        """
        Scrapes match data from tracker.gg using the provided URL.
        """
        match_id_match = re.search(r'match/([a-zA-Z0-9\-]+)', match_url)
        if not match_id_match:
            return None, "Invalid Tracker.gg match URL"
        
        match_id = match_id_match.group(1)
        api_url = f"https://api.tracker.gg/api/v2/valorant/standard/matches/{match_id}"
        
        headers = self.headers.copy()
        headers['Referer'] = f'https://tracker.gg/valorant/match/{match_id}'
        
        try:
            print(f"🚀 Scraping Match: {match_id}")
            r = self.scraper.get(api_url, headers=headers)
            
            if r.status_code != 200:
                return None, f"Tracker.gg API error: {r.status_code}"
            
            data = r.json()
            return data, None
        except Exception as e:
            return None, f"Scraping error: {str(e)}"

    def get_profile_data(self, profile_url):
        """
        Scrapes profile data from tracker.gg using the provided URL.
        Example URL: https://tracker.gg/valorant/profile/riot/User%23TAG/overview
        """
        # Extract Riot ID from URL
        # Format: /profile/riot/User%23TAG
        profile_match = re.search(r'profile/riot/([^/?#]+)', profile_url)
        if not profile_match:
            return None, "Invalid Tracker.gg profile URL"
        
        user_url_part = profile_match.group(1)
        api_url = f"https://api.tracker.gg/api/v2/valorant/standard/profile/riot/{user_url_part}?forceCollect=true"
        
        headers = self.headers.copy()
        headers['Referer'] = profile_url
        
        try:
            print(f"👤 Scraping Profile: {user_url_part}")
            r = self.scraper.get(api_url, headers=headers)
            
            if r.status_code != 200:
                return None, f"Tracker.gg API error: {r.status_code}"
            
            data = r.json()
            return data, None
        except Exception as e:
            return None, f"Scraping error: {str(e)}"

    def save_match(self, data, folder="matches"):
        if not data or 'data' not in data:
            return None
        
        match_id = data['data']['attributes']['id']
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        filepath = os.path.join(folder, f"match_{match_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return filepath

    def save_profile(self, data, folder="profiles"):
        if not data or 'data' not in data:
            return None
        
        platform_info = data['data']['platformInfo']
        username = platform_info['platformUserHandle'].replace('#', '_')
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        filepath = os.path.join(folder, f"profile_{username}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return filepath

def main():
    if len(sys.argv) < 2:
        print("Usage: python tracker_scraper.py <url>")
        return

    url = sys.argv[1]
    scraper = TrackerScraper()
    
    if 'match' in url:
        data, error = scraper.get_match_data(url)
        if error:
            print(f"❌ Error: {error}")
        else:
            path = scraper.save_match(data)
            print(f"✅ Match saved to {path}")
    elif 'profile' in url:
        data, error = scraper.get_profile_data(url)
        if error:
            print(f"❌ Error: {error}")
        else:
            path = scraper.save_profile(data)
            print(f"✅ Profile saved to {path}")
    else:
        print("❌ Unknown URL type. Must contain 'match' or 'profile'.")

if __name__ == "__main__":
    main()
