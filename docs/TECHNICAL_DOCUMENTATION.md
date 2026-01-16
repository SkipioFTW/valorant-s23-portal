# Technical Documentation: VALORANT S23 Portal

## **1. System Architecture Overview**
The VALORANT S23 Portal is a modular Streamlit application designed for high-performance tournament tracking. It separates concerns between UI rendering, data scraping, and predictive analytics.

### **Core Components & File Linkages**
- **[visitor_dashboard.py](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/visitor_dashboard.py)**: The central hub. It manages the **Streamlit State Engine**, handles all UI routing via `st.session_state['page']`, and orchestrates the interaction between the scrapers and the databases.
- **[tracker_scraper.py](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/tracker_scraper.py)**: A standalone library class ([TrackerScraper](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/tracker_scraper.py)). It is initialized on-demand by the dashboard to perform authenticated/bypass requests to Tracker.gg.
- **[predictor_model.py](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/predictor_model.py)**: The machine learning inference engine. It is imported by the dashboard to provide real-time win probabilities using a serialized `scikit-learn` model.
- **[train_predictor.py](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/train_predictor.py)**: A utility script used to retrain the model when new match data is available in the SQLite databases.

---

## **2. Deep Dive: Key Backend Functions**

### **Data Processing & ETL**
- **`parse_tracker_json(jsdata, team1_id)`**: This is the heart of the data ingestion pipeline.
    - **Team Identification**: It performs a roster-matching algorithm to determine which team in the Tracker.gg JSON corresponds to our database's `team1_id`.
    - **Entity Linking**: It maps Tracker.gg's `platformUserIdentifier` to our internal `player_id` using a multi-step matching process:
        1. Direct Riot ID match (case-insensitive).
        2. "Name-only" match (splitting the #Tag).
        3. Fuzzy match against the player name.
    - **Normalization**: Converts raw stats (Score Per Round, Kills, etc.) into integer values compatible with the `match_stats_map` schema.

- **`get_standings()`**:
    - Aggregates data from `matches` and `teams` tables.
    - Calculates Wins, Losses, Round Differentials, and Points dynamically.
    - Uses SQL `CASE` statements to handle home/away team logic within a single query.

### **Session & Security Logic**
- **`get_visitor_ip()`**: Implements a **Fingerprinting Algorithm**. It combines `User-Agent`, `Accept-Language`, and `Accept` headers into an MD5 hash. This ensures that even if a user's IP rotates (common in mobile/cloud environments), their admin lock remains stable.
- **`get_active_admin_session()`**: Queries the `session_activity` table for any entry with `role='admin'` or `role='dev'` updated within the last 60 seconds, excluding the current user's fingerprint.

### **Predictive Analytics**
- **`extract_features(t1_id, t2_id)`**:
    - **Feature Engineering**: Computes four primary features:
        1. **Recent Form**: Win rate over the last 3 matches.
        2. **Skill Gap**: Average ACS (Average Combat Score) difference between rosters.
        3. **H2H**: Head-to-head win differential.
        4. **Temporal Context**: Current tournament week.
- **`predict_match()`**: Performs inference using `joblib.load()` on [match_predictor_model.pkl](file:///c:/Users/SBS/OneDrive/Bureau/FLV/valorant-s23-portal/match_predictor_model.pkl).

---

## **3. Database Schema Interplay**
The system utilizes a dual-database strategy for performance:
1.  **`valorant_s23.db`**: Stores "Relational Metadata" (Admins, Teams, Players, Rosters).
2.  **`matches.db`**: Stores "High-Volume Transactional Data" (Match Results, Map Scores, Player Match Stats).

These are linked via **Foreign Keys** (`team_id`, `player_id`) maintained manually through application logic to ensure cross-database compatibility.

---

## **4. Deployment & Integration**
- **GitHub Sync**: The `backup_db_to_github()` function uses the GitHub API to commit the latest `.db` files directly to the repository, acting as a primitive but effective distributed state management for Streamlit Cloud deployments.
- **Cloudflare Bypass**: `cloudscraper` is configured with a specific Chrome/Windows browser profile to mimic human behavior during match ingestion.
