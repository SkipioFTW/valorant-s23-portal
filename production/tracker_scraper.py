
import re
import cloudscraper
import json
import os
import sys
import time

# Path management for production/staging structure
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)

class TrackerScraper:
    def __init__(self):
        # Using a more specific browser profile to better mimic a real user
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10 # Cloudflare sometimes requires a delay before the challenge can be solved
        )
        # Standard headers that help mimic a browser request
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_match_data(self, match_input):
        """
        Scrapes match data from tracker.gg using either a URL or a Match ID.
        """
        match_id = match_input
        if "tracker.gg" in match_input:
            match_id_match = re.search(r'match/([a-zA-Z0-9\-]+)', match_input)
            if not match_id_match:
                return None, "Invalid Tracker.gg match URL"
            match_id = match_id_match.group(1)
        
        # Ensure match_id is clean
        match_id = re.sub(r'[^a-zA-Z0-9\-]', '', match_id)
        if not match_id:
            return None, "Invalid Match ID"

        api_url = f"https://api.tracker.gg/api/v2/valorant/standard/matches/{match_id}"
        
        headers = self.headers.copy()
        headers['Referer'] = f'https://tracker.gg/valorant/match/{match_id}'
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🚀 Scraping Match: {match_id} (Attempt {attempt + 1})")
                r = self.scraper.get(api_url, headers=headers, timeout=30)
                
                if r.status_code == 200:
                    data = r.json()
                    return data, None
                elif r.status_code == 403:
                    print(f"⚠️ 403 Forbidden on attempt {attempt + 1}. Cloudflare might be blocking the cloud IP.")
                    if attempt < max_retries - 1:
                        time.sleep(5) # Wait before retrying
                        continue
                    return None, f"Tracker.gg blocked the request (403). This often happens in cloud environments like Streamlit Cloud."
                else:
                    return None, f"Tracker.gg API error: {r.status_code}"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None, f"Scraping error: {str(e)}"
        return None, "Scraping failed after multiple attempts."

    def upload_match_to_github(self, match_id, jsdata, get_secret_func):
        """
        Uploads match JSON to GitHub matches/ folder.
        Requires a function to get secrets (GH_OWNER, GH_REPO, etc.)
        """
        import base64
        import requests
        
        owner = get_secret_func("GH_OWNER")
        repo = get_secret_func("GH_REPO")
        token = get_secret_func("GH_TOKEN")
        branch = get_secret_func("GH_BRANCH", "main")
        
        if not owner or not repo or not token:
            return False, "Missing GitHub configuration"
            
        path = f"assets/matches/match_{match_id}.json"
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        # 1. Check if file exists to get SHA
        sha = None
        try:
            r = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
            if r.status_code == 200:
                sha = r.json().get("sha")
        except Exception:
            pass
            
        # 2. Upload
        content = json.dumps(jsdata, indent=4)
        payload = {
            "message": f"Add match {match_id}",
            "content": base64.b64encode(content.encode('utf-8')).decode('ascii'),
            "branch": branch
        }
        if sha:
            payload["sha"] = sha
            payload["message"] = f"Update match {match_id}"
            
        try:
            r = requests.put(url, headers=headers, json=payload, timeout=15)
            if r.status_code in [200, 201]:
                return True, f"Successfully uploaded match_{match_id}.json to GitHub"
            else:
                return False, f"GitHub upload failed: {r.status_code}"
        except Exception as e:
            return False, f"GitHub upload error: {str(e)}"
    
    def push_match_to_github_via_git(self, match_id):
        """
        Pushes the locally saved match JSON to GitHub using git commands.
        This ensures the local repository stays in sync with GitHub.
        """
        import subprocess
        
        filepath = f"assets/matches/match_{match_id}.json"
        
        try:
            # Change to ROOT_DIR for git operations
            original_dir = os.getcwd()
            os.chdir(ROOT_DIR)
            
            # Check if file exists
            if not os.path.exists(filepath):
                os.chdir(original_dir)
                return False, f"File {filepath} not found locally"
            
            # Git add
            result = subprocess.run(
                ["git", "add", filepath],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                os.chdir(original_dir)
                error_msg = f"Git add failed: {result.stderr.strip() or result.stdout.strip() or 'Unknown error'}"
                return False, error_msg
            
            # Git commit
            commit_msg = f"Add match {match_id}"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Note: commit might return 1 if nothing to commit (file already committed)
            commit_output = result.stdout + result.stderr
            if result.returncode != 0 and "nothing to commit" not in commit_output.lower():
                os.chdir(original_dir)
                error_msg = f"Git commit failed: {result.stderr.strip() or result.stdout.strip() or 'Unknown error'}"
                return False, error_msg
            
            # If nothing to commit, file was already committed - that's OK
            if "nothing to commit" in commit_output.lower():
                os.chdir(original_dir)
                return True, f"Match {match_id} already committed, skipping push"
            
            # Git push
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                os.chdir(original_dir)
                error_msg = f"Git push failed: {result.stderr.strip() or result.stdout.strip() or 'Unknown error'}"
                return False, error_msg
            
            os.chdir(original_dir)
            return True, f"Successfully pushed match_{match_id}.json to GitHub via git"
            
        except subprocess.TimeoutExpired:
            os.chdir(original_dir)
            return False, "Git operation timed out"
        except Exception as e:
            os.chdir(original_dir)
            return False, f"Git push error: {str(e)}"

    def get_profile_data(self, profile_url):
        """
        Scrapes profile data from tracker.gg using the provided URL.
        Example URL: https://tracker.gg/valorant/profile/riot/User%23TAG/overview
        """
        # Extract Riot ID from URL
        profile_match = re.search(r'profile/riot/([^/?#]+)', profile_url)
        if not profile_match:
            return None, "Invalid Tracker.gg profile URL"
        
        user_url_part = profile_match.group(1)
        api_url = f"https://api.tracker.gg/api/v2/valorant/standard/profile/riot/{user_url_part}"
        
        headers = self.headers.copy()
        headers['Referer'] = profile_url
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"👤 Scraping Profile: {user_url_part} (Attempt {attempt + 1})")
                r = self.scraper.get(api_url, headers=headers, timeout=30)
                
                if r.status_code == 200:
                    data = r.json()
                    return data, None
                elif r.status_code == 403:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return None, "Tracker.gg blocked the profile request (403)."
                elif r.status_code == 451:
                    return None, "Profile data is restricted or requires manual collection (451)."
                else:
                    return None, f"Tracker.gg API error: {r.status_code}"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None, f"Scraping error: {str(e)}"
        return None, "Scraping failed after multiple attempts."

    def save_match(self, data, folder="assets/matches"):
        if not data or 'data' not in data:
            return None
        
        match_id = data['data']['attributes']['id']
        # Ensure path is relative to ROOT_DIR
        full_folder_path = os.path.join(ROOT_DIR, folder)
        if not os.path.exists(full_folder_path):
            os.makedirs(full_folder_path)
        
        filepath = os.path.join(full_folder_path, f"match_{match_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return filepath

    def save_profile(self, data, folder="assets/profiles"):
        if not data or 'data' not in data:
            return None
        
        platform_info = data['data']['platformInfo']
        username = platform_info['platformUserHandle'].replace('#', '_')
        # Ensure path is relative to ROOT_DIR
        full_folder_path = os.path.join(ROOT_DIR, folder)
        if not os.path.exists(full_folder_path):
            os.makedirs(full_folder_path)
        
        filepath = os.path.join(full_folder_path, f"profile_{username}.json")
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
