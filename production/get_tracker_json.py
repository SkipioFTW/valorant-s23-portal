
import streamlit as st
import json
import re
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Path management for production/staging structure
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from tracker_scraper import TrackerScraper

# Configure Streamlit page
st.set_page_config(page_title="Tracker Scraper v0.8.0", page_icon="🎮")

def get_secret(key, default=None):
    """Retrieves secret from Streamlit secrets or environment variables."""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

def process_link(scraper, url, push_to_github):
    """Worker function for multi-threaded scraping."""
    try:
        if 'match' in url:
            data, error = scraper.get_match_data(url)
            if error:
                return url, False, f"Scrape Error: {error}"
            
            # Save locally
            match_id = data['data']['attributes']['id']
            filepath = scraper.save_match(data)
            
            # Push to GitHub if requested
            github_msg = ""
            if push_to_github:
                ok, gmsg = scraper.push_match_to_github_via_git(match_id)
                github_msg = f" | GitHub: {'✅' if ok else '❌'} {gmsg}"
            
            return url, True, f"✅ Match {match_id} saved{github_msg}"
            
        elif 'profile' in url:
            data, error = scraper.get_profile_data(url)
            if error:
                return url, False, f"Scrape Error: {error}"
            
            filepath = scraper.save_profile(data)
            return url, True, f"✅ Profile saved to {filepath}"
        else:
            return url, False, "❌ Invalid URL type"
    except Exception as e:
        return url, False, f"Unexpected Error: {str(e)}"

def main():
    st.title("🎮 Tracker Scraper v0.8.0")
    st.markdown("""
    This tool allows you to scrape match and profile data from Tracker.gg and optionally push it to GitHub.
    It saves match JSONs to `assets/matches/` for use in the main portal.
    """)

    # GitHub Configuration Section (Legacy - Not needed for git-based push)
    with st.expander("⚙️ GitHub API Configuration (Legacy/Optional)", expanded=False):
        st.info("This section is for the legacy GitHub API upload method. The tool now uses git commands by default, which doesn't require these settings.")
        col1, col2 = st.columns(2)
        with col1:
            gh_owner = st.text_input("GitHub Owner", value=get_secret("GH_OWNER", ""), placeholder="e.g. your-username")
            gh_repo = st.text_input("GitHub Repo", value=get_secret("GH_REPO", ""), placeholder="e.g. valorant-s23-portal")
        with col2:
            gh_token = st.text_input("GitHub Token (PAT)", value=get_secret("GH_TOKEN", ""), type="password")
            gh_branch = st.text_input("GitHub Branch", value=get_secret("GH_BRANCH", "main"))
        
        # Inject into environment if provided in UI (for this session)
        if gh_owner: os.environ["GH_OWNER"] = gh_owner
        if gh_repo: os.environ["GH_REPO"] = gh_repo
        if gh_token: os.environ["GH_TOKEN"] = gh_token
        if gh_branch: os.environ["GH_BRANCH"] = gh_branch

    # Input Section
    st.subheader("🔗 Input Tracker.gg Links")
    bulk_links = st.text_area("Enter links (one per line)", height=150, placeholder="https://tracker.gg/valorant/match/...\nhttps://tracker.gg/valorant/profile/riot/...")
    single_link = st.text_input("Or enter a single link", placeholder="https://tracker.gg/valorant/match/...")

    # Combine links
    links_to_process = [l.strip() for l in bulk_links.split('\n') if l.strip()]
    if single_link.strip() and single_link.strip() not in links_to_process:
        links_to_process.append(single_link.strip())

    # Options
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        push_to_github = st.checkbox("Push to GitHub assets/ folder", value=True)
    with col_opt2:
        max_workers = st.slider("Max simultaneous scrapes", 1, 5, 2)

    if st.button("🚀 Start Scraping", use_container_width=True, type="primary"):
        if not links_to_process:
            st.warning("Please enter at least one link.")
            return

        scraper = TrackerScraper()
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results_container = st.container()
        results_container.write("### 📝 Results")
        
        success_count = 0
        total = len(links_to_process)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_link, scraper, url, push_to_github): url for url in links_to_process}
            
            for i, future in enumerate(as_completed(futures)):
                url, success, msg = future.result()
                if success:
                    success_count += 1
                    results_container.success(f"**{url}**\n{msg}")
                else:
                    results_container.error(f"**{url}**\n{msg}")
                
                progress_bar.progress((i + 1) / total)
                status_text.text(f"Processing: {i+1}/{total}")
                
                # Small delay to avoid aggressive rate limiting
                if total > 1:
                    time.sleep(1)

        st.balloons()
        st.success(f"Finished! Successfully processed {success_count} out of {total} links.")

if __name__ == "__main__":
    main()
