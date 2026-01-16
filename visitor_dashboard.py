import streamlit as st
import sqlite3
import os
import html
import json
import re
import pandas as pd
from tracker_scraper import TrackerScraper

# Set page config immediately as the first streamlit command
st.set_page_config(page_title="S23 Portal", layout="wide")

# App Mode Logic
if 'app_mode' not in st.session_state:
    st.session_state['app_mode'] = 'portal'

# Hide standard sidebar navigation and other streamlit elements
st.markdown("""<link href='https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@400;600&family=Inter:wght@400;700&display=swap' rel='stylesheet'><style>
/* Global Styles */
:root {
--primary-blue: #3FD1FF;
--primary-red: #FF4655;
--bg-dark: #0F1923;
--card-bg: #1F2933;
--text-main: #ECE8E1;
--text-dim: #8B97A5;
--nav-height: 80px;
}
.stApp {
background-color: var(--bg-dark);
background-image: radial-gradient(circle at 20% 30%, rgba(63, 209, 255, 0.05) 0%, transparent 40%), 
radial-gradient(circle at 80% 70%, rgba(255, 70, 85, 0.05) 0%, transparent 40%);
color: var(--text-main);
font-family: 'Inter', sans-serif;
transition: opacity 0.5s ease-in-out;
}
.stApp .main .block-container {
padding-top: var(--padding-top, 60px) !important;
}
.portal-header {
color: var(--primary-blue);
font-size: 3.5rem;
text-shadow: 0 0 30px rgba(63, 209, 255, 0.4);
margin-bottom: 0;
text-align: center;
font-family: 'Orbitron', sans-serif;
}
.portal-subtitle {
color: var(--text-dim);
font-size: 0.9rem;
letter-spacing: 5px;
margin-bottom: 3rem;
text-transform: uppercase;
text-align: center;
}
/* Navigation Button Styling */
.stButton > button {
background: transparent !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
color: var(--text-dim) !important;
font-family: 'Inter', sans-serif !important;
font-weight: 600 !important;
transition: all 0.3s ease !important;
border-radius: 4px !important;
text-transform: uppercase !important;
letter-spacing: 1px !important;
font-size: 0.8rem !important;
height: 40px !important;
}
.stButton > button:hover {
border-color: var(--primary-blue) !important;
color: var(--primary-blue) !important;
background: rgba(63, 209, 255, 0.05) !important;
}
.stButton > button[kind="primary"] {
background: var(--primary-red) !important;
border-color: var(--primary-red) !important;
color: white !important;
}
.stButton > button[kind="primary"]:hover {
background: #ff5c6a !important;
box-shadow: 0 0 20px rgba(255, 70, 85, 0.4) !important;
}
/* Active Tab Style */
.active-nav button {
border-bottom: 2px solid var(--primary-red) !important;
color: white !important;
background: rgba(255, 255, 255, 0.05) !important;
border-radius: 4px 4px 0 0 !important;
}
/* Exit Button Style */
.exit-btn button {
border-color: var(--primary-red) !important;
color: var(--primary-red) !important;
font-weight: bold !important;
}
.exit-btn button:hover {
background: rgba(255, 70, 85, 0.1) !important;
color: white !important;
}
.portal-container {
display: flex;
flex-direction: column;
align-items: center;
justify-content: center;
min-height: 85vh;
gap: 1.5rem;
animation: fadeIn 0.8s ease-out;
padding: 2rem;
}
.status-grid {
display: flex;
justify-content: center;
gap: 1.5rem;
width: 100%;
max-width: 1000px;
margin: 0 auto 2rem auto;
}
.status-indicator {
padding: 8px 16px;
background: rgba(255, 255, 255, 0.05);
border-radius: 20px;
font-size: 0.7rem;
letter-spacing: 2px;
font-family: 'Orbitron', sans-serif;
border: 1px solid rgba(255, 255, 255, 0.1);
}
.status-online { color: #00ff88; border-color: rgba(0, 255, 136, 0.2); }
.status-offline { color: #ff4655; border-color: rgba(255, 70, 85, 0.2); }

.portal-options {
display: grid;
grid-template-columns: repeat(3, 1fr);
gap: 2rem;
width: 100%;
max-width: 1200px;
}
.portal-card-wrapper {
background: var(--card-bg);
border: 1px solid rgba(255, 255, 255, 0.05);
border-radius: 8px;
padding: 2rem;
text-align: center;
transition: all 0.3s ease;
position: relative;
overflow: hidden;
height: 100%;
display: flex;
flex-direction: column;
justify-content: space-between;
}
.portal-card-wrapper:hover {
border-color: var(--primary-blue);
transform: translateY(-5px);
box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}
.portal-card-wrapper.disabled {
opacity: 0.6;
cursor: not-allowed;
filter: grayscale(1);
}
.portal-card-wrapper.disabled:hover {
transform: none;
border-color: rgba(255, 255, 255, 0.05);
}
.portal-card-content h3 {
font-family: 'Orbitron', sans-serif;
color: var(--text-main);
margin-bottom: 1rem;
}
.portal-card-footer {
margin-top: 2rem;
}

/* Navbar Styles */
.nav-wrapper {
position: fixed;
top: 0;
left: 0;
right: 0;
height: var(--nav-height);
background: rgba(15, 25, 35, 0.95);
backdrop-filter: blur(10px);
border-bottom: 1px solid rgba(255, 255, 255, 0.05);
display: flex;
align-items: center;
padding: 0 4rem;
z-index: 1000;
}
.nav-logo {
font-family: 'Orbitron', sans-serif;
font-size: 1.2rem;
color: var(--primary-blue);
letter-spacing: 4px;
font-weight: bold;
}
.sub-nav-wrapper {
position: fixed;
top: var(--nav-height);
left: 0;
right: 0;
background: rgba(31, 41, 51, 0.8);
border-bottom: 1px solid rgba(255, 255, 255, 0.05);
padding: 10px 4rem;
z-index: 999;
}

/* Custom Card for Dashboard */
.custom-card {
background: var(--card-bg);
border: 1px solid rgba(255, 255, 255, 0.05);
border-radius: 4px;
padding: 1.5rem;
height: 100%;
}

/* Dataframe Styling */
[data-testid="stDataFrame"] {
border: 1px solid rgba(255, 255, 255, 0.05) !important;
border-radius: 4px !important;
}

@keyframes fadeIn {
from { opacity: 0; transform: translateY(20px); }
to { opacity: 1; transform: translateY(0); }
}

/* Mobile Responsiveness */
@media (max-width: 1024px) {
.portal-header { font-size: 2.5rem; }
.portal-options { grid-template-columns: 1fr; gap: 1rem; }
.nav-wrapper { padding: 0 2rem; }
.sub-nav-wrapper { padding: 10px 2rem; }
}

@media (max-width: 768px) {
.portal-header { font-size: 2rem; }
.portal-subtitle { font-size: 0.7rem; letter-spacing: 2px; margin-bottom: 1.5rem; }
.status-grid { flex-direction: column; gap: 0.8rem; }
.status-indicator { min-width: 100%; }
.portal-options { grid-template-columns: 1fr; gap: 1.5rem; }
.nav-wrapper { height: 60px; padding: 0 1rem; align-items: center; }
.nav-logo { font-size: 0.9rem; letter-spacing: 2px; }
.sub-nav-wrapper { top: 60px; padding: 8px 0.5rem; overflow-x: auto; white-space: nowrap; display: block !important; -webkit-overflow-scrolling: touch; background: rgba(15, 25, 35, 0.95); }
.sub-nav-wrapper [data-testid="stHorizontalBlock"] { display: flex !important; flex-wrap: nowrap !important; width: max-content !important; gap: 12px !important; padding: 0 10px !important; }
.sub-nav-wrapper [data-testid="column"] { width: auto !important; min-width: 130px !important; flex: 0 0 auto !important; }
/* Hide the scrollbar for sub-nav */
.sub-nav-wrapper::-webkit-scrollbar { display: none; }
.sub-nav-wrapper { -ms-overflow-style: none; scrollbar-width: none; }
.main-header { font-size: 1.8rem !important; margin-bottom: 1.5rem !important; }
}
</style>""", unsafe_allow_html=True)

# Dynamic padding based on mode
if st.session_state.get('app_mode') == 'portal':
    st.markdown("<style>:root { --padding-top: 60px; }</style>", unsafe_allow_html=True)
    st.markdown("<style>@media (max-width: 768px) { :root { --padding-top: 30px; } }</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>:root { --padding-top: 180px; }</style>", unsafe_allow_html=True)
    st.markdown("<style>@media (max-width: 768px) { :root { --padding-top: 140px; } }</style>", unsafe_allow_html=True)

# Deferred imports moved inside functions to reduce initial white screen/load time:
# pandas, numpy, hashlib, hmac, secrets, tempfile, base64, requests, cloudscraper, re, io, json, html, time, plotly, PIL

def is_safe_path(path):
    if not path:
        return False
    # Prevent path traversal, absolute paths, and alternate data streams (Windows)
    if ".." in path or os.path.isabs(path) or ":" in path:
        return False
    return True

def ocr_extract(image_bytes, crop_box=None):
    """
    Returns (text, dataframe, error_message)
    """
    import io
    from PIL import Image
    try:
        import pytesseract
        # Try to find tesseract binary in common paths if not in PATH
        # (Windows specific check)
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\SBS\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        ]
        for p in possible_paths:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

        img = Image.open(io.BytesIO(image_bytes))
        if crop_box:
            img = img.crop(crop_box)
        
        # Preprocessing
        # 1. Convert to grayscale
        img_gray = img.convert('L')
        # 2. Thresholding (simple binary)
        # Adjust threshold as needed, 128 is standard
        img_thresh = img_gray.point(lambda x: 0 if x < 150 else 255, '1')
        
        # Try getting data
        try:
            df = pytesseract.image_to_data(img_thresh, output_type=pytesseract.Output.DATAFRAME)
        except Exception as e:
            # If data extraction fails, we might still get text? 
            # Usually if one fails, both fail, but let's try.
            # Also catch if tesseract is missing
            return "", None, f"Tesseract Error: {str(e)}"
            
        text = pytesseract.image_to_string(img_thresh)
        return text, df, None
    except ImportError:
        return "", None, "pytesseract not installed. Please install it to use OCR."
    except Exception as e:
        return "", None, f"Image Processing Error: {str(e)}"

def scrape_tracker_match(url):
    """
    Scrapes match data from tracker.gg using the TrackerScraper class.
    Returns (match_data_json, error_message)
    """
    try:
        scraper = TrackerScraper()
        data, error = scraper.get_match_data(url)
        return data, error
    except Exception as e:
        return None, f"Scraping error: {str(e)}"

def parse_tracker_json(jsdata, team1_id):
    """
    Parses Tracker.gg JSON data and matches it to team1_id.
    Returns (json_suggestions, map_name, t1_rounds, t2_rounds)
    """
    import re
    json_suggestions = {}
    segments = jsdata.get("data", {}).get("segments", [])
    
    # First pass: find team names/IDs to identify which Tracker team is which
    tracker_team_1_id = None
    team_segments = [s for s in segments if s.get("type") == "team-summary"]
    if len(team_segments) >= 2:
        # Use Riot IDs to match teams
        all_players_df = get_all_players()
        # Ensure team1_id is int for comparison
        t1_id_int = int(team1_id) if team1_id is not None else None
        t1_roster = all_players_df[all_players_df['default_team_id'] == t1_id_int]['riot_id'].dropna().tolist()
        t1_roster = [str(r).strip().lower() for r in t1_roster]
        
        potential_t1_id = team_segments[0].get("attributes", {}).get("teamId")
        t1_matches = 0
        for p_seg in [s for s in segments if s.get("type") == "player-summary"]:
            if p_seg.get("metadata", {}).get("teamId") == potential_t1_id:
                rid = p_seg.get("metadata", {}).get("platformInfo", {}).get("platformUserIdentifier")
                if rid and str(rid).strip().lower() in t1_roster:
                    t1_matches += 1
        
        if t1_matches >= 1:
            tracker_team_1_id = potential_t1_id
        else:
            tracker_team_1_id = team_segments[1].get("attributes", {}).get("teamId")

    for seg in segments:
        if seg.get("type") == "player-summary":
            rid = seg.get("metadata", {}).get("platformInfo", {}).get("platformUserIdentifier")
            if rid:
                rid = str(rid).strip()
            agent = seg.get("metadata", {}).get("agentName")
            st_map = seg.get("stats", {})
            acs = st_map.get("scorePerRound", {}).get("value", 0)
            k = st_map.get("kills", {}).get("value", 0)
            d = st_map.get("deaths", {}).get("value", 0)
            a = st_map.get("assists", {}).get("value", 0)
            t_id = seg.get("metadata", {}).get("teamId")
            
            our_team_num = 1 if t_id == tracker_team_1_id else 2
            
            if rid:
                rid_lower = rid.lower()
                json_suggestions[rid_lower] = {
                    'acs': int(acs) if acs is not None else 0, 
                    'k': int(k) if k is not None else 0, 
                    'd': int(d) if d is not None else 0, 
                    'a': int(a) if a is not None else 0, 
                    'agent': agent,
                    'team_num': our_team_num,
                    'conf': 100.0
                }
    
    # Extract map name and rounds
    map_name = jsdata.get("data", {}).get("metadata", {}).get("mapName")
    t1_r = 0
    t2_r = 0
    
    if len(team_segments) >= 2:
        if tracker_team_1_id == team_segments[0].get("attributes", {}).get("teamId"):
            t1_r = team_segments[0].get("stats", {}).get("roundsWon", {}).get("value", 0)
            t2_r = team_segments[1].get("stats", {}).get("roundsWon", {}).get("value", 0)
        else:
            t1_r = team_segments[1].get("stats", {}).get("roundsWon", {}).get("value", 0)
            t2_r = team_segments[0].get("stats", {}).get("roundsWon", {}).get("value", 0)
            
    return json_suggestions, map_name, int(t1_r), int(t2_r)

@st.cache_data(ttl=3600)
def get_base64_image(image_path):
    import base64
    if not image_path or not is_safe_path(image_path) or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

def get_secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

DB_PATH = get_secret("DB_PATH", "valorant_s23.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_admin_table(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    if should_close:
        conn.commit()
        conn.close()

def ensure_base_schema(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT,
        name TEXT UNIQUE,
        group_name TEXT,
        captain TEXT,
        co_captain TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        riot_id TEXT,
        rank TEXT,
        default_team_id INTEGER,
        FOREIGN KEY(default_team_id) REFERENCES teams(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week INTEGER,
        group_name TEXT,
        team1_id INTEGER,
        team2_id INTEGER,
        winner_id INTEGER,
        score_t1 INTEGER DEFAULT 0,
        score_t2 INTEGER DEFAULT 0,
        status TEXT DEFAULT 'scheduled',
        format TEXT,
        maps_played INTEGER DEFAULT 0,
        FOREIGN KEY(team1_id) REFERENCES teams(id),
        FOREIGN KEY(team2_id) REFERENCES teams(id),
        FOREIGN KEY(winner_id) REFERENCES teams(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS match_maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        map_index INTEGER NOT NULL,
        map_name TEXT,
        team1_rounds INTEGER,
        team2_rounds INTEGER,
        winner_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS match_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        team_id INTEGER,
        acs INTEGER,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')
    if should_close:
        conn.commit()
        conn.close()

def ensure_column(table, column_name, column_def_sql, conn=None):
    # Allowed tables for security validation
    ALLOWED_TABLES = {"teams", "players", "matches", "match_maps", "match_stats_map", "match_stats", "agents", "seasons", "team_history", "admins"}
    if table not in ALLOWED_TABLES:
        return # Skip if table is not allowed
    
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    c = conn.cursor()
    # Use string interpolation only for table names which are now validated against ALLOWED_TABLES
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if column_name not in cols:
        try:
            # Validate column_def_sql basic structure to prevent injection if it comes from untrusted source
            # In this app, it is hardcoded, but good practice to validate
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column_def_sql}")
        except sqlite3.OperationalError:
            pass
    
    if should_close:
        conn.commit()
        conn.close()

def ensure_upgrade_schema(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seasons (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        start_date TEXT,
        end_date TEXT,
        is_active BOOLEAN DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS team_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER,
        season_id INTEGER,
        final_rank INTEGER,
        group_name TEXT,
        FOREIGN KEY(team_id) REFERENCES teams(id),
        FOREIGN KEY(season_id) REFERENCES seasons(id)
    )''')
    
    ensure_column("teams", "logo_path", "logo_path TEXT", conn=conn)
    ensure_column("players", "rank", "rank TEXT", conn=conn)
    ensure_column("matches", "format", "format TEXT", conn=conn)
    ensure_column("matches", "maps_played", "maps_played INTEGER DEFAULT 0", conn=conn)
    ensure_column("seasons", "is_active", "is_active BOOLEAN DEFAULT 0", conn=conn)
    ensure_column("admins", "role", "role TEXT DEFAULT 'admin'", conn=conn)
    ensure_column("matches", "match_type", "match_type TEXT DEFAULT 'regular'", conn=conn)
    ensure_column("matches", "playoff_round", "playoff_round INTEGER", conn=conn)
    ensure_column("matches", "bracket_pos", "bracket_pos INTEGER", conn=conn)
    
    try:
        c.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (22, 'Season 22', 0)")
        c.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (23, 'Season 23', 1)")
    except Exception:
        pass
    try:
        c.execute("INSERT OR IGNORE INTO team_history (team_id, season_id, group_name) SELECT id, 23, group_name FROM teams")
    except Exception:
        pass
    
    if should_close:
        conn.commit()
        conn.close()

def import_sqlite_db(upload_bytes):
    import pandas as pd
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    try:
        tmp.write(upload_bytes)
        tmp.flush()
        src = sqlite3.connect(tmp.name)
        tgt = get_conn()
        tables = [
            "teams","players","matches","match_maps","match_stats_map","match_stats","agents","seasons","team_history"
        ]
        summary = {}
        for t in tables:
            try:
                df = pd.read_sql(f"SELECT * FROM {t}", src)
            except Exception:
                continue
            if df.empty:
                continue
            cols = [r[1] for r in tgt.execute(f"PRAGMA table_info({t})").fetchall()]
            use = [c for c in df.columns if c in cols]
            if not use:
                continue
            q = f"INSERT OR REPLACE INTO {t} (" + ",".join(use) + ") VALUES (" + ",".join(["?"]*len(use)) + ")"
            vals = df[use].values.tolist()
            tgt.executemany(q, vals)
            summary[t] = len(vals)
        tgt.commit()
        src.close()
        tgt.close()
        return summary
    finally:
        tmp.close()
        if os.path.exists(tmp.name):
            try:
                os.remove(tmp.name)
            except Exception:
                pass

def export_db_bytes():
    p = os.path.abspath(DB_PATH)
    try:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return f.read()
    except Exception:
        return None
    return None

def restore_db_from_github():
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    path = get_secret("GH_DB_PATH")
    branch = get_secret("GH_BRANCH", "main")
    if not owner or not repo or not path:
        return False
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.content:
            with open(DB_PATH, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        return False
    return False

def backup_db_to_github():
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    path = get_secret("GH_DB_PATH")
    branch = get_secret("GH_BRANCH", "main")
    token = get_secret("GH_TOKEN")
    if not owner or not repo or not path or not token:
        return False, "Missing secrets"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    sha = None
    try:
        gr = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        if gr.status_code == 200:
            data = gr.json()
            sha = data.get("sha")
    except Exception:
        pass
    data_bytes = export_db_bytes()
    if not data_bytes:
        return False, "No DB data"
    payload = {
        "message": "Portal DB backup",
        "content": base64.b64encode(data_bytes).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    try:
        pr = requests.put(url, headers=headers, json=payload, timeout=20)
        if pr.status_code in [200, 201]:
            return True, "Backed up"
        return False, f"Error {pr.status_code}"
    except Exception:
        return False, "Request failed"

@st.cache_data(ttl=300)
def get_substitutions_log():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql(
            """
            SELECT msm.match_id, msm.map_index, m.week, m.group_name,
                   t.name AS team, p.name AS player, sp.name AS subbed_for,
                   msm.agent, msm.acs, msm.kills, msm.deaths, msm.assists
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            LEFT JOIN teams t ON msm.team_id = t.id
            LEFT JOIN players p ON msm.player_id = p.id
            LEFT JOIN players sp ON msm.subbed_for_id = sp.id
            WHERE msm.is_sub = 1
            ORDER BY m.week, msm.match_id, msm.map_index
            """,
            conn,
        )
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_player_profile(player_id):
    import pandas as pd
    conn = get_conn()
    try:
        info = pd.read_sql(
            "SELECT p.id, p.name, p.rank, t.tag as team FROM players p LEFT JOIN teams t ON p.default_team_id=t.id WHERE p.id=?",
            conn,
            params=(int(player_id),),
        )
        if info.empty:
            conn.close()
            return {}
            
        rank_val = info.iloc[0]['rank']
        
        # Stats with match metadata in one go
        stats = pd.read_sql(
            """
            SELECT msm.match_id, msm.map_index, msm.agent, msm.acs, msm.kills, msm.deaths, msm.assists, msm.is_sub, m.week
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            WHERE msm.player_id=?
            """,
            conn,
            params=(int(player_id),),
        )
        
        # Combined Benchmarks
        bench = pd.read_sql(
            """
            SELECT 
                AVG(msm.acs) as lg_acs, AVG(msm.kills) as lg_k, AVG(msm.deaths) as lg_d, AVG(msm.assists) as lg_a,
                AVG(CASE WHEN p.rank = ? THEN msm.acs ELSE NULL END) as r_acs,
                AVG(CASE WHEN p.rank = ? THEN msm.kills ELSE NULL END) as r_k,
                AVG(CASE WHEN p.rank = ? THEN msm.deaths ELSE NULL END) as r_d,
                AVG(CASE WHEN p.rank = ? THEN msm.assists ELSE NULL END) as r_a
            FROM match_stats_map msm
            JOIN players p ON msm.player_id = p.id
            """,
            conn,
            params=(rank_val, rank_val, rank_val, rank_val)
        ).iloc[0]
        
        trend = pd.DataFrame()
        if not stats.empty:
            agg = stats.groupby('match_id').agg({'acs':'mean','kills':'sum','deaths':'sum','week':'first'}).reset_index()
            agg['kda'] = agg['kills'] / agg['deaths'].replace(0, 1)
            agg['label'] = 'W' + agg['week'].fillna(0).astype(int).astype(str) + '-M' + agg['match_id'].astype(int).astype(str)
            agg = agg.rename(columns={'acs':'avg_acs'})
            trend = agg[['label','avg_acs','kda']]
            
        conn.close()
    except Exception:
        if 'conn' in locals(): conn.close()
        return {}
        
    games = stats['match_id'].nunique() if not stats.empty else 0
    avg_acs = float(stats['acs'].mean()) if not stats.empty else 0.0
    total_k = int(stats['kills'].sum()) if not stats.empty else 0
    total_d = int(stats['deaths'].sum()) if not stats.empty else 0
    total_a = int(stats['assists'].sum()) if not stats.empty else 0
    kd = (total_k / (total_d if total_d != 0 else 1)) if not stats.empty else 0.0
    
    sub_impact = None
    if not stats.empty:
        s_sub = stats[stats['is_sub'] == 1]
        s_sta = stats[stats['is_sub'] == 0]
        sub_impact = {
            'sub_acs': float(s_sub['acs'].mean()) if not s_sub.empty else 0.0,
            'starter_acs': float(s_sta['acs'].mean()) if not s_sta.empty else 0.0,
            'sub_kda': float((s_sub['kills'].sum() / max(s_sub['deaths'].sum(), 1))) if not s_sub.empty else 0.0,
            'starter_kda': float((s_sta['kills'].sum() / max(s_sta['deaths'].sum(), 1))) if not s_sta.empty else 0.0,
        }

    return {
        'info': info.iloc[0].to_dict(),
        'games': int(games),
        'avg_acs': round(avg_acs, 1),
        'total_kills': total_k,
        'total_deaths': total_d,
        'total_assists': total_a,
        'kd_ratio': round(kd, 2),
        'sr_avg_acs': round(float(bench['r_acs'] or 0), 1),
        'sr_k': round(float(bench['r_k'] or 0), 1),
        'sr_d': round(float(bench['r_d'] or 0), 1),
        'sr_a': round(float(bench['r_a'] or 0), 1),
        'lg_avg_acs': round(float(bench['lg_acs'] or 0), 1),
        'lg_k': round(float(bench['lg_k'] or 0), 1),
        'lg_d': round(float(bench['lg_d'] or 0), 1),
        'lg_a': round(float(bench['lg_a'] or 0), 1),
        'maps': stats,
        'trend': trend,
        'sub_impact': sub_impact,
    }
def reset_db():
    conn = get_conn()
    c = conn.cursor()
    for t in [
        "admins","match_stats_map","match_stats","match_maps","matches","players","teams","agents","team_history","seasons"
    ]:
        try:
            c.execute(f"DROP TABLE IF EXISTS {t}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    ensure_base_schema()
    init_admin_table()
    init_match_stats_map_table()
    ensure_upgrade_schema()

def hash_password(password, salt=None):
    import secrets
    import hashlib
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
    return salt, hashed

def verify_password(password, salt, stored_hash):
    import hashlib
    import hmac
    calc = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
    return hmac.compare_digest(calc, stored_hash)

def admin_exists():
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) FROM admins WHERE is_active=1")
    count = cur.fetchone()[0]
    conn.close()
    return count > 0

def create_admin(username, password):
    salt, ph = hash_password(password)
    conn = get_conn()
    role = get_secret("ADMIN_SEED_ROLE", "admin") if not admin_exists() else "admin"
    conn.execute("INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (?, ?, ?, 1, ?)", (username, ph, salt, role))
    conn.commit()
    conn.close()

def create_admin_with_role(username, password, role):
    salt, ph = hash_password(password)
    conn = get_conn()
    conn.execute("INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (?, ?, ?, 1, ?)", (username, ph, salt, role))
    conn.commit()
    conn.close()

def ensure_seed_admins(conn=None):
    su = get_secret("ADMIN_SEED_USER")
    sp = get_secret("ADMIN_SEED_PWD")
    sr = get_secret("ADMIN_SEED_ROLE", "admin")
    
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    c = conn.cursor()
    if su and sp:
        row = c.execute("SELECT id, role FROM admins WHERE username=?", (su,)).fetchone()
        if not row:
            salt, ph = hash_password(sp)
            c.execute(
                "INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (?, ?, ?, 1, ?)",
                (su, ph, salt, sr)
            )
        else:
            if row[1] != sr:
                c.execute("UPDATE admins SET role=? WHERE id=?", (sr, int(row[0])))
    su2 = get_secret("ADMIN2_USER")
    sp2 = get_secret("ADMIN2_PWD")
    sr2 = get_secret("ADMIN2_ROLE", "admin")
    if su2 and sp2:
        row2 = c.execute("SELECT id FROM admins WHERE username=?", (su2,)).fetchone()
        if not row2:
            salt2, ph2 = hash_password(sp2)
            c.execute(
                "INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (?, ?, ?, 1, ?)",
                (su2, ph2, salt2, sr2)
            )
    
    if should_close:
        conn.commit()
        conn.close()

def authenticate(username, password):
    conn = get_conn()
    row = conn.execute("SELECT username, password_hash, salt, role FROM admins WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if not row:
        return None
    u, ph, salt, role = row
    if verify_password(password, salt, ph):
        return {"username": u, "role": role}
    return None

def init_match_stats_map_table(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS match_stats_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            map_index INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            player_id INTEGER,
            is_sub INTEGER DEFAULT 0,
            subbed_for_id INTEGER,
            agent TEXT,
            acs INTEGER,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER
        )
        """
    )
    if should_close:
        conn.commit()
        conn.close()

def upsert_match_maps(match_id, maps_data):
    conn = get_conn()
    c = conn.cursor()
    for m in maps_data:
        c.execute("SELECT id FROM match_maps WHERE match_id=? AND map_index=?", (match_id, m['map_index']))
        ex = c.fetchone()
        if ex:
            c.execute(
                "UPDATE match_maps SET map_name=?, team1_rounds=?, team2_rounds=?, winner_id=? WHERE id=?",
                (m['map_name'], m['team1_rounds'], m['team2_rounds'], m['winner_id'], ex[0])
            )
        else:
            c.execute(
                "INSERT INTO match_maps (match_id, map_index, map_name, team1_rounds, team2_rounds, winner_id) VALUES (?, ?, ?, ?, ?, ?)",
                (match_id, m['map_index'], m['map_name'], m['team1_rounds'], m['team2_rounds'], m['winner_id'])
            )
    conn.commit()
    conn.close()

@st.cache_data(ttl=300)
def get_standings():
    import pandas as pd
    import numpy as np
    conn = get_conn()
    try:
        teams_df = pd.read_sql_query("SELECT id, name, group_name, logo_path FROM teams", conn)
        matches_df = pd.read_sql_query("SELECT * FROM matches WHERE status='completed' AND match_type='regular' AND (UPPER(format)='BO1' OR format IS NULL)", conn)
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
    
    # Pre-calculate logo display safety to cache it
    # Vectorized check using list comprehension (faster than .apply for small/medium DFs)
    teams_df['logo_display'] = [
        p if p and not (".." in p or p.startswith("/") or p.startswith("\\")) and os.path.exists(p) 
        else None 
        for p in teams_df['logo_path']
    ]

    exclude_ids = set(teams_df[teams_df['name'].isin(['FAT1','FAT2'])]['id'].tolist())
    if exclude_ids:
        teams_df = teams_df[~teams_df['id'].isin(exclude_ids)]
        matches_df = matches_df[~(matches_df['team1_id'].isin(exclude_ids) | matches_df['team2_id'].isin(exclude_ids))]
    
    # Initialize stats using vectorization
    if matches_df.empty:
        for col in ['Wins', 'Losses', 'RD', 'Points', 'Points Against', 'Played']:
            teams_df[col] = 0
        return teams_df

    # Calculate match-level stats
    m = matches_df.copy()
    m['is_ot'] = (m['score_t1'] >= 12) & (m['score_t2'] >= 12)
    
    # Points for Team 1
    m['p1'] = 0
    m.loc[m['score_t1'] > m['score_t2'], 'p1'] = 15 + m['score_t1']
    m.loc[m['score_t1'] < m['score_t2'], 'p1'] = np.where(m['is_ot'], 12 + m['score_t1'], m['score_t1'])
    
    # Points for Team 2
    m['p2'] = 0
    m.loc[m['score_t2'] > m['score_t1'], 'p2'] = 15 + m['score_t2']
    m.loc[m['score_t2'] < m['score_t1'], 'p2'] = np.where(m['is_ot'], 12 + m['score_t2'], m['score_t2'])
    
    # Wins/Losses
    m['t1_win'] = (m['score_t1'] > m['score_t2']).astype(int)
    m['t2_win'] = (m['score_t2'] > m['score_t1']).astype(int)
    
    # Reshape to team-level
    t1_stats = m.groupby('team1_id').agg({
        't1_win': 'sum',
        't2_win': lambda x: (1-x).sum(), # t1 losses
        'score_t1': 'sum', # for RD calculation later or Points
        'score_t2': 'sum', # for RD calculation later or Points Against
        'p1': 'sum',
        'id': 'count' # Played
    }).rename(columns={'t1_win': 'Wins', 't2_win': 'Losses', 'score_t1': 'S_For', 'score_t2': 'S_Ag', 'p1': 'Points', 'id': 'Played'})
    
    t2_stats = m.groupby('team2_id').agg({
        't2_win': 'sum',
        't1_win': lambda x: (1-x).sum(), # t2 losses
        'score_t2': 'sum',
        'score_t1': 'sum',
        'p2': 'sum',
        'id': 'count'
    }).rename(columns={'t2_win': 'Wins', 't1_win': 'Losses', 'score_t2': 'S_For', 'score_t1': 'S_Ag', 'p2': 'Points', 'id': 'Played'})

    # Combine stats
    combined = pd.concat([t1_stats, t2_stats]).groupby(level=0).sum()
    combined['RD'] = combined['S_For'] - combined['S_Ag']
    combined = combined.rename(columns={'S_Ag': 'Points Against'})
    combined = combined.drop(columns=['S_For'])
    
    # Merge with teams_df
    df = teams_df.merge(combined, left_on='id', right_index=True, how='left').fillna(0)
    
    # Ensure correct types for numeric columns
    for col in ['Wins', 'Losses', 'RD', 'Points', 'Points Against', 'Played']:
        df[col] = df[col].astype(int)
        
    return df.sort_values(by=['Points', 'Points Against'], ascending=[False, True])

@st.cache_data(ttl=60)
def get_player_leaderboard():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """
            SELECT p.id as player_id,
                   p.name,
                   t.tag as team,
                   COUNT(DISTINCT msm.match_id) as games,
                   AVG(msm.acs) as avg_acs,
                   SUM(msm.kills) as total_kills,
                   SUM(msm.deaths) as total_deaths,
                   SUM(msm.assists) as total_assists
            FROM match_stats_map msm
            JOIN players p ON msm.player_id = p.id
            LEFT JOIN teams t ON p.default_team_id = t.id
            GROUP BY p.id, p.name
            HAVING games > 0
            """,
            conn,
        )
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
    if not df.empty:
        df['kd_ratio'] = df['total_kills'] / df['total_deaths'].replace(0, 1)
        df['avg_acs'] = df['avg_acs'].round(1)
        df['kd_ratio'] = df['kd_ratio'].round(2)
    return df.sort_values('avg_acs', ascending=False)

@st.cache_data(ttl=60)
def get_week_matches(week):
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT m.id, m.week, m.group_name, m.status, m.format, m.maps_played,
               t1.name as t1_name, t2.name as t2_name,
               m.score_t1, m.score_t2, t1.id as t1_id, t2.id as t2_id
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.week = ? AND m.match_type = 'regular'
        ORDER BY m.id
        """,
        conn,
        params=(week,),
    )
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_playoff_matches():
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT m.id, m.playoff_round, m.bracket_pos, m.status, m.format, m.maps_played,
               t1.name as t1_name, t2.name as t2_name,
               m.score_t1, m.score_t2, t1.id as t1_id, t2.id as t2_id,
               m.winner_id
        FROM matches m
        LEFT JOIN teams t1 ON m.team1_id = t1.id
        LEFT JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.match_type = 'playoff'
        ORDER BY m.playoff_round ASC, m.bracket_pos ASC
        """,
        conn
    )
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_match_maps(match_id):
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT map_index, map_name, team1_rounds, team2_rounds, winner_id FROM match_maps WHERE match_id=? ORDER BY map_index",
        conn,
        params=(match_id,),
    )
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_all_players_directory():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql(
            """
            SELECT p.id, p.name, p.riot_id, p.rank, t.name as team
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            ORDER BY p.name
            """,
            conn
        )
    except Exception:
        df = pd.DataFrame(columns=['id','name','riot_id','rank','team'])
    finally:
        conn.close()
    return df

@st.cache_data(ttl=300)
def get_map_stats(match_id, map_index, team_id):
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql(
            """
            SELECT p.name, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub 
            FROM match_stats_map ms 
            JOIN players p ON ms.player_id=p.id 
            WHERE ms.match_id=? AND ms.map_index=? AND ms.team_id=?
            """, 
            conn, 
            params=(int(match_id), int(map_index), int(team_id))
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_team_history_counts():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT team_id, COUNT(DISTINCT season_id) as season_count FROM team_history GROUP BY team_id",
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_all_players():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT id, name, riot_id, rank, default_team_id FROM players ORDER BY name", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_teams_list_full():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT id, name, tag, group_name, logo_path FROM teams ORDER BY name", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_teams_list():
    import pandas as pd
    df = get_teams_list_full()
    return df[['id', 'name']] if not df.empty else pd.DataFrame(columns=['id', 'name'])

@st.cache_data(ttl=3600)
def get_agents_list():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT name FROM agents ORDER BY name", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df['name'].tolist() if not df.empty else []

@st.cache_data(ttl=300)
def get_match_weeks():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT DISTINCT week FROM matches ORDER BY week", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df['week'].tolist() if not df.empty else []

@st.cache_data(ttl=300)
def get_match_maps_cached(match_id):
    return get_match_maps(match_id)

@st.cache_data(ttl=300)
def get_completed_matches():
    import pandas as pd
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT * FROM matches WHERE status='completed'", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def apply_plotly_theme(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#ECE8E1',
        font_family='Inter',
        title_font_family='Orbitron',
        title_font_color='#3FD1FF',
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.05)', 
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#8B97A5'),
            title_font=dict(color='#8B97A5')
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.05)', 
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#8B97A5'),
            title_font=dict(color='#8B97A5')
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(
            bgcolor='rgba(0,0,0,0)',
            bordercolor='rgba(255,255,255,0.1)',
            font=dict(color='#ECE8E1')
        )
    )
    return fig

# App Mode Logic
if 'login_attempts' not in st.session_state:
    st.session_state['login_attempts'] = 0
if 'last_login_attempt' not in st.session_state:
    st.session_state['last_login_attempt'] = 0

# Use a placeholder to clear the screen during transitions
main_container = st.empty()

if st.session_state['app_mode'] == 'portal':
    with main_container.container():
        st.markdown("""<div class="portal-container">
<h1 class="portal-header">VALORANT S23 PORTAL</h1>
<p class="portal-subtitle">System Status & Access Terminal</p>
<div class="status-grid">
<div class="status-indicator status-online">● VISITOR ACCESS: LIVE</div>
<div class="status-indicator status-offline">● TEAM PANEL: STAGING</div>
<div class="status-indicator status-online">● ADMIN CORE: SECURE</div>
</div>
<div class="portal-options">""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="portal-card-wrapper"><div class="portal-card-content"><h3>VISITOR</h3><p style="color: var(--text-dim); font-size: 0.9rem;">Browse tournament statistics, match history, and player standings.</p></div><div class="portal-card-footer">', unsafe_allow_html=True)
            if st.button("ENTER PORTAL", key="enter_visitor", use_container_width=True, type="primary"):
                st.session_state['app_mode'] = 'visitor'
                st.rerun()
            st.markdown('</div></div>', unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="portal-card-wrapper disabled"><div class="portal-card-content"><h3>TEAM LEADER</h3><p style="color: var(--text-dim); font-size: 0.9rem;">Manage your team roster, submit scores, and track performance.</p></div><div class="portal-card-footer">', unsafe_allow_html=True)
            st.button("LOCKED", key="enter_team", use_container_width=True, disabled=True)
            st.markdown('</div></div>', unsafe_allow_html=True)
            
        with col3:
            st.markdown('<div class="portal-card-wrapper"><div class="portal-card-content"><h3>ADMIN</h3><p style="color: var(--text-dim); font-size: 0.9rem;">Full system administration, data management, and tournament control.</p></div><div class="portal-card-footer">', unsafe_allow_html=True)
            if st.button("ADMIN LOGIN", key="enter_admin", use_container_width=True):
                st.session_state['app_mode'] = 'admin'
                st.rerun()
            st.markdown('</div></div>', unsafe_allow_html=True)
            
        st.markdown('</div></div>', unsafe_allow_html=True)
    st.stop()

# If in Visitor or Admin mode, show the dashboard
if st.session_state['app_mode'] == 'admin' and not st.session_state.get('is_admin'):
    # Show a simplified nav for login screen
    st.markdown('<div class="nav-wrapper"><div class="nav-logo" style="margin-left: auto; margin-right: auto;">VALORANT S23 • ADMIN PORTAL</div></div>', unsafe_allow_html=True)
    
    st.markdown('<div style="margin-top: 40px;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">ADMIN ACCESS</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("Please enter your administrator credentials to proceed.")
        
        # Simple rate limiting
        if st.session_state['login_attempts'] >= 5:
            time_since_last = time.time() - st.session_state['last_login_attempt']
            if time_since_last < 300: # 5 minute lockout
                st.error(f"Too many failed attempts. Please wait {int(300 - time_since_last)} seconds.")
                if st.button("← BACK TO SELECTION"):
                    st.session_state['app_mode'] = 'portal'
                    st.rerun()
                st.stop()
            else:
                st.session_state['login_attempts'] = 0

        with st.form("admin_login_main"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            tok = st.text_input("Admin Token", type="password")
            if st.form_submit_button("LOGIN TO ADMIN PANEL", use_container_width=True):
                env_tok = get_secret("ADMIN_LOGIN_TOKEN", None)
                
                if env_tok is None or env_tok == "":
                    st.error("Security Error: ADMIN_LOGIN_TOKEN not configured in environment.")
                    st.session_state['last_login_attempt'] = time.time()
                    st.session_state['login_attempts'] += 1
                else:
                    auth_res = authenticate(u, p)
                    if auth_res and hmac.compare_digest(tok or "", env_tok):
                        st.session_state['is_admin'] = True
                        st.session_state['username'] = auth_res['username']
                        st.session_state['role'] = auth_res['role']
                        st.session_state['page'] = "Admin Panel"
                        st.session_state['login_attempts'] = 0
                        st.success("Access Granted")
                        st.rerun()
                    else:
                        st.session_state['last_login_attempt'] = time.time()
                        st.session_state['login_attempts'] += 1
                        st.error(f"Invalid credentials (Attempt {st.session_state['login_attempts']}/5)")
        if st.button("← BACK TO SELECTION"):
            st.session_state['app_mode'] = 'portal'
            st.rerun()
    st.stop()

if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

# Admin status display in sidebar
if st.session_state['is_admin']:
    st.sidebar.success(f"Logged in as: {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['is_admin'] = False
        st.session_state['username'] = None
        st.session_state['app_mode'] = 'portal'
        st.rerun()

if 'page' not in st.session_state:
    st.session_state['page'] = "Overview & Standings"

pages = [
    "Overview & Standings",
    "Matches",
    "Match Predictor",
    "Match Summary",
    "Player Leaderboard",
    "Players Directory",
    "Teams",
    "Substitutions Log",
    "Player Profile",
]
if st.session_state['is_admin']:
    pages.insert(pages.index("Admin Panel") if "Admin Panel" in pages else len(pages), "Playoffs")
    if "Admin Panel" not in pages:
        pages.append("Admin Panel")

# Top Navigation Bar
st.markdown('<div class="nav-wrapper"><div class="nav-logo">VALORANT S23 • PORTAL</div></div>', unsafe_allow_html=True)

# Navigation Layout
st.markdown('<div class="sub-nav-wrapper">', unsafe_allow_html=True)
# Use a container to hold the columns, but we need to style the container itself to be part of the sub-nav
# Since we can't easily wrap st.columns in a div that stays fixed, we rely on sub-nav-wrapper
cols = st.columns([0.6] + [1] * len(pages))

with cols[0]:
    st.markdown('<div class="exit-btn">', unsafe_allow_html=True)
    if st.button("🏠 EXIT", key="exit_portal", use_container_width=True):
        st.session_state['app_mode'] = 'portal'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
for i, p in enumerate(pages):
    with cols[i+1]:
        is_active = st.session_state['page'] == p
        st.markdown(f'<div class="{"active-nav" if is_active else ""}">', unsafe_allow_html=True)
        if st.button(p, key=f"nav_{p}", use_container_width=True, 
                     type="primary" if is_active else "secondary"):
            st.session_state['page'] = p
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        if is_active:
            st.markdown('<div style="height: 3px; background: var(--primary-red); margin-top: -8px; box-shadow: 0 0 10px var(--primary-red); border-radius: 2px;"></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

page = st.session_state['page']

if page == "Overview & Standings":
    import pandas as pd
    st.markdown('<h1 class="main-header">OVERVIEW & STANDINGS</h1>', unsafe_allow_html=True)
    
    df = get_standings()
    if not df.empty:
        hist = get_team_history_counts()
        all_players_bench = get_all_players()
        # Pre-group rosters for efficiency
        rosters_by_team = {}
        if not all_players_bench.empty:
            for tid, group in all_players_bench.groupby('default_team_id'):
                rosters_by_team[int(tid)] = group[['name', 'rank']]

        df = df.merge(hist, left_on='id', right_on='team_id', how='left')
        df['season_count'] = df['season_count'].fillna(1).astype(int)
        
        groups = sorted(df['group_name'].unique())
        
        for grp in groups:
            st.markdown(f'<h2 style="color: var(--primary-blue); font-family: \'Orbitron\'; border-left: 4px solid var(--primary-blue); padding-left: 15px; margin: 2rem 0 1rem 0;">GROUP {html.escape(str(grp))}</h2>', unsafe_allow_html=True)
            
            grp_df = df[df['group_name'] == grp]
            
            # Team Cards Grid
            t_cols = st.columns(min(len(grp_df), 3))
            for idx, row in enumerate(grp_df.itertuples()):
                with t_cols[idx % 3]:
                    logo_html = ""
                    b64 = get_base64_image(row.logo_display)
                    if b64:
                        logo_html = f"<img src='data:image/png;base64,{b64}' width='40' style='border-radius: 4px;'/>"
                    else:
                        logo_html = "<div style='width:40px;height:40px;background:rgba(255,255,255,0.05);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);'>?</div>"
                    
                    st.markdown(f"""<div class="custom-card" style="height: 100%;">
<div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
{logo_html}
<div style="font-weight: bold; color: var(--primary-blue); font-size: 1rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{html.escape(str(row.name))}</div>
</div>
<div style="display: flex; justify-content: space-between; color: var(--text-dim); font-size: 0.8rem;">
<span>WINS: <span style="color: var(--text-main); font-family: 'Orbitron';">{row.Wins}</span></span>
<span>PTS: <span style="color: var(--primary-blue); font-family: 'Orbitron';">{row.Points}</span></span>
</div>
</div>""", unsafe_allow_html=True)
                    
                    with st.expander("Roster"):
                        roster = rosters_by_team.get(int(row.id), pd.DataFrame())
                        if roster.empty: st.caption("No players")
                        else: st.dataframe(roster, hide_index=True, use_container_width=True)
            
            # Standings Table for Group
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(
                grp_df[['name', 'Played', 'Wins', 'Losses', 'Points', 'RD']].sort_values('Points', ascending=False),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "name": "Team",
                    "RD": st.column_config.NumberColumn("Round Diff", help="Total Rounds Won - Total Rounds Lost")
                }
            )
            st.markdown("---")
    else:
        st.info("No standings data available yet.")

elif page == "Matches":
    import pandas as pd
    st.markdown('<h1 class="main-header">MATCH SCHEDULE</h1>', unsafe_allow_html=True)
    week = st.selectbox("Select Week", [1, 2, 3, 4, 5], index=0)
    df = get_week_matches(week)
    if df.empty:
        st.info("No matches for this week.")
    else:
        st.markdown("### Scheduled")
        sched = df[df['status'] != 'completed']
        if sched.empty:
            st.caption("None")
        else:
            for m in sched.itertuples():
                st.markdown(f"""<div class="custom-card">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div style="flex: 1; text-align: right; font-weight: bold; color: var(--primary-blue);">{html.escape(str(m.t1_name))}</div>
<div style="margin: 0 20px; color: var(--text-dim); font-family: 'Orbitron';">VS</div>
<div style="flex: 1; text-align: left; font-weight: bold; color: var(--primary-red);">{html.escape(str(m.t2_name))}</div>
</div>
<div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 10px;">{html.escape(str(m.format))} • {html.escape(str(m.group_name))}</div>
</div>""", unsafe_allow_html=True)
        
        st.markdown("### Completed")
        comp = df[df['status'] == 'completed']
        for m in comp.itertuples():
            with st.container():
                winner_color_1 = "var(--primary-blue)" if m.score_t1 > m.score_t2 else "var(--text-main)"
                winner_color_2 = "var(--primary-red)" if m.score_t2 > m.score_t1 else "var(--text-main)"
                
                st.markdown(f"""<div class="custom-card" style="border-left: 4px solid {'var(--primary-blue)' if m.score_t1 > m.score_t2 else 'var(--primary-red)'};">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div style="flex: 1; text-align: right;">
<span style="font-weight: bold; color: {winner_color_1};">{html.escape(str(m.t1_name))}</span>
<span style="font-size: 1.5rem; margin-left: 10px; font-family: 'Orbitron';">{m.score_t1}</span>
</div>
<div style="margin: 0 20px; color: var(--text-dim); font-family: 'Orbitron';">-</div>
<div style="flex: 1; text-align: left;">
<span style="font-size: 1.5rem; margin-right: 10px; font-family: 'Orbitron';">{m.score_t2}</span>
<span style="font-weight: bold; color: {winner_color_2};">{html.escape(str(m.t2_name))}</span>
</div>
</div>
<div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 10px;">{html.escape(str(m.format))} • {html.escape(str(m.group_name))}</div>
</div>""", unsafe_allow_html=True)
                
                with st.expander("Match Details"):
                    maps_df = get_match_maps(int(m.id))
                    if maps_df.empty:
                        st.caption("No map details")
                    else:
                        md = maps_df.copy()
                        t1_id_val = int(getattr(m, 't1_id', getattr(m, 'team1_id', 0)))
                        t2_id_val = int(getattr(m, 't2_id', getattr(m, 'team2_id', 0)))
                        # Vectorized Winner calculation
                        md['Winner'] = ''
                        md.loc[md['winner_id'] == t1_id_val, 'Winner'] = m.t1_name
                        md.loc[md['winner_id'] == t2_id_val, 'Winner'] = m.t2_name
                        
                        md = md.rename(columns={
                            'map_index': 'Map',
                            'map_name': 'Name',
                            'team1_rounds': m.t1_name,
                            'team2_rounds': m.t2_name,
                        })
                        md['Map'] = md['Map'] + 1
                        st.dataframe(md[['Map', 'Name', m.t1_name, m.t2_name, 'Winner']], hide_index=True, use_container_width=True)

elif page == "Match Summary":
    st.markdown('<h1 class="main-header">MATCH SUMMARY</h1>', unsafe_allow_html=True)
    
    wk_list = get_match_weeks()
    week = st.sidebar.selectbox("Week", wk_list if wk_list else [1], index=0, key="wk_sum")
    df = get_week_matches(week) if wk_list else pd.DataFrame()
    
    if df.empty:
        st.info("No matches for this week.")
    else:
        # Vectorized option generation
        opts = (df['t1_name'].fillna('') + " vs " + df['t2_name'].fillna('') + " (" + df['group_name'].fillna('') + ")").tolist()
        sel = st.selectbox("Select Match", list(range(len(opts))), format_func=lambda i: opts[i])
        m = df.iloc[sel]
        
        # Match Score Card
        st.markdown(f"""<div class="custom-card" style="margin-bottom: 2rem; border-bottom: 4px solid {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--primary-red)'};">
<div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
<div style="flex: 1; text-align: right;">
<h2 style="margin: 0; color: {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--text-main)'}; font-family: 'Orbitron';">{html.escape(str(m['t1_name']))}</h2>
</div>
<div style="margin: 0 30px; display: flex; align-items: center; gap: 15px;">
<span style="font-size: 3rem; font-family: 'Orbitron'; color: var(--text-main);">{m['score_t1']}</span>
<span style="font-size: 1.5rem; color: var(--text-dim); font-family: 'Orbitron';">:</span>
<span style="font-size: 3rem; font-family: 'Orbitron'; color: var(--text-main);">{m['score_t2']}</span>
</div>
<div style="flex: 1; text-align: left;">
<h2 style="margin: 0; color: {'var(--primary-red)' if m['score_t2'] > m['score_t1'] else 'var(--text-main)'}; font-family: 'Orbitron';">{html.escape(str(m['t2_name']))}</h2>
</div>
</div>
<div style="text-align: center; color: var(--text-dim); font-size: 0.9rem; margin-top: 10px; letter-spacing: 2px;">{html.escape(str(m['format'].upper()))} • {html.escape(str(m['group_name'].upper()))}</div>
</div>""", unsafe_allow_html=True)
        
        maps_df = get_match_maps(int(m['id']))
        if maps_df.empty:
            st.info("No detailed map data recorded for this match.")
        else:
            # Map Selection
            map_indices = sorted(maps_df['map_index'].unique().tolist())
            map_labels = [f"Map {i+1}: {maps_df[maps_df['map_index'] == i].iloc[0]['map_name']}" for i in map_indices]
            
            selected_map_idx = st.radio("Select Map", map_indices, format_func=lambda i: map_labels[i], horizontal=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Map Score Card
            curr_map = maps_df[maps_df['map_index'] == selected_map_idx].iloc[0]
            t1_id_val = int(m.get('t1_id', m.get('team1_id')))
            t2_id_val = int(m.get('t2_id', m.get('team2_id')))
            st.markdown(f"""<div class="custom-card" style="background: rgba(255,255,255,0.02); margin-bottom: 20px;">
<div style="display: flex; justify-content: center; align-items: center; gap: 40px;">
<div style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; margin-bottom: 5px;">{html.escape(str(m['t1_name']))}</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: {'var(--primary-blue)' if curr_map['team1_rounds'] > curr_map['team2_rounds'] else 'var(--text-main)'};">{curr_map['team1_rounds']}</div>
</div>
<div style="text-align: center;">
<div style="font-family: 'Orbitron'; color: var(--primary-blue); font-size: 1.2rem;">{html.escape(str(curr_map['map_name'].upper()))}</div>
<div style="color: var(--text-dim); font-size: 0.7rem;">WINNER: {html.escape(str(m['t1_name'] if curr_map['winner_id'] == t1_id_val else m['t2_name']))}</div>
</div>
<div style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; margin-bottom: 5px;">{html.escape(str(m['t2_name']))}</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: {'var(--primary-red)' if curr_map['team2_rounds'] > curr_map['team1_rounds'] else 'var(--text-main)'};">{curr_map['team2_rounds']}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            
            # Scoreboards
            t1_id_val = int(m.get('t1_id', m.get('team1_id')))
            t2_id_val = int(m.get('t2_id', m.get('team2_id')))
            s1 = get_map_stats(m['id'], selected_map_idx, t1_id_val)
            s2 = get_map_stats(m['id'], selected_map_idx, t2_id_val)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<h4 style="color: var(--primary-blue); font-family: \'Orbitron\';">{html.escape(str(m["t1_name"]))} Scoreboard</h4>', unsafe_allow_html=True)
                if s1.empty:
                    st.info("No scoreboard data")
                else:
                    st.dataframe(s1.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)
            
            with c2:
                st.markdown(f'<h4 style="color: var(--primary-red); font-family: \'Orbitron\';">{html.escape(str(m["t2_name"]))} Scoreboard</h4>', unsafe_allow_html=True)
                if s2.empty:
                    st.info("No scoreboard data")
                else:
                    st.dataframe(s2.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)

elif page == "Match Predictor":
    import pandas as pd
    st.markdown('<h1 class="main-header">MATCH PREDICTOR</h1>', unsafe_allow_html=True)
    st.write("Predict the outcome of a match based on team history and stats.")
    
    teams_df = get_teams_list()
    matches_df = get_completed_matches()
    
    tnames = teams_df['name'].tolist() if not teams_df.empty else []
    c1, c2 = st.columns(2)
    
    # Check if user is admin or dev
    is_privileged = st.session_state.get('is_admin', False) or st.session_state.get('role') in ['admin', 'dev']
    
    t1_name = c1.selectbox("Team 1", tnames, index=0, disabled=not is_privileged)
    t2_name = c2.selectbox("Team 2", tnames, index=(1 if len(tnames)>1 else 0), disabled=not is_privileged)
    
    if st.button("Predict Result", disabled=not is_privileged):
        if t1_name == t2_name:
            st.error("Select two different teams.")
        else:
            t1_id = teams_df[teams_df['name'] == t1_name].iloc[0]['id']
            t2_id = teams_df[teams_df['name'] == t2_name].iloc[0]['id']
            
            # Feature extraction helper
            def get_team_stats(tid):
                import pandas as pd
                played = matches_df[(matches_df['team1_id']==tid) | (matches_df['team2_id']==tid)]
                if played.empty:
                    return {'win_rate': 0.0, 'avg_score': 0.0, 'games': 0}
                wins = played[played['winner_id'] == tid].shape[0]
                total = played.shape[0]
                
                # Calculate avg score (rounds won) using vectorized operations
                scores_t1 = played.loc[played['team1_id'] == tid, 'score_t1']
                scores_t2 = played.loc[played['team2_id'] == tid, 'score_t2']
                all_scores = pd.concat([scores_t1, scores_t2])
                avg_score = all_scores.mean() if not all_scores.empty else 0
                
                return {'win_rate': wins/total, 'avg_score': avg_score, 'games': total}

            s1 = get_team_stats(t1_id)
            s2 = get_team_stats(t2_id)
            
            # Head to head
            h2h = matches_df[((matches_df['team1_id']==t1_id) & (matches_df['team2_id']==t2_id)) | 
                             ((matches_df['team1_id']==t2_id) & (matches_df['team2_id']==t1_id))]
            h2h_wins_t1 = h2h[h2h['winner_id'] == t1_id].shape[0]
            h2h_wins_t2 = h2h[h2h['winner_id'] == t2_id].shape[0]
            
            # Heuristic Score
            # Win Rate (40%), Avg Score (30%), H2H (30%)
            # Normalize scores? No, just compare raw weighted sums or probabilities
            
            # Heuristic Score (Fallback if ML fails or data too small)
            score1 = (s1['win_rate'] * 40) + (s1['avg_score'] * 2) + (h2h_wins_t1 * 5)
            score2 = (s2['win_rate'] * 40) + (s2['avg_score'] * 2) + (h2h_wins_t2 * 5)
            
            ml_prob = None
            try:
                import predictor_model
                ml_prob = predictor_model.predict_match(t1_id, t2_id)
            except Exception as e:
                pass
                
            if ml_prob is not None:
                prob1 = ml_prob * 100
                prob2 = (1 - ml_prob) * 100
                prediction_type = "ML MODEL"
            else:
                total = score1 + score2
                if total == 0:
                    prob1 = 50.0
                    prob2 = 50.0
                else:
                    prob1 = (score1 / total) * 100
                    prob2 = (score2 / total) * 100
                prediction_type = "HEURISTIC"
                
            winner = t1_name if prob1 > prob2 else t2_name
            conf = max(prob1, prob2)
            
            st.markdown(f"""<div class="custom-card" style="text-align: center; border-top: 4px solid { 'var(--primary-blue)' if winner == t1_name else 'var(--primary-red)' };">
<div style="color: var(--text-dim); font-size: 0.7rem; margin-bottom: 5px;">{prediction_type} PREDICTION</div>
<h2 style="margin: 0; color: { 'var(--primary-blue)' if winner == t1_name else 'var(--primary-red)' };">{html.escape(str(winner))}</h2>
<div style="font-size: 3rem; font-family: 'Orbitron'; margin: 10px 0;">{conf:.1f}%</div>
<div style="color: var(--text-dim);">CONFIDENCE LEVEL</div>
</div>""", unsafe_allow_html=True)

            # Probability Bar
            st.markdown(f"""<div style="width: 100%; background: rgba(255,255,255,0.05); height: 20px; border-radius: 10px; overflow: hidden; display: flex; margin: 20px 0;">
<div style="width: {prob1}%; background: var(--primary-blue); height: 100%; transition: width 1s ease-in-out;"></div>
<div style="width: {prob2}%; background: var(--primary-red); height: 100%; transition: width 1s ease-in-out;"></div>
</div>
<div style="display: flex; justify-content: space-between; font-family: 'Orbitron'; font-size: 0.8rem;">
<div style="color: var(--primary-blue);">{html.escape(str(t1_name))} ({prob1:.1f}%)</div>
<div style="color: var(--primary-red);">{html.escape(str(t2_name))} ({prob2:.1f}%)</div>
</div>""", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""<div class="custom-card">
<h3 style="color: var(--primary-blue); margin-top: 0;">{html.escape(str(t1_name))} Analysis</h3>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">Win Rate</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{s1['win_rate']:.0%}</div>
</div>
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">Avg Score</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{s1['avg_score']:.1f}</div>
</div>
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">H2H Wins</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{h2h_wins_t1}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="custom-card">
<h3 style="color: var(--primary-red); margin-top: 0;">{html.escape(str(t2_name))} Analysis</h3>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">Win Rate</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{s2['win_rate']:.0%}</div>
</div>
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">Avg Score</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{s2['avg_score']:.1f}</div>
</div>
<div>
<div style="color: var(--text-dim); font-size: 0.7rem; text-transform: uppercase;">H2H Wins</div>
<div style="font-size: 1.2rem; font-family: 'Orbitron';">{h2h_wins_t2}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

elif page == "Player Leaderboard":
    import pandas as pd
    df = get_player_leaderboard()
    if df.empty:
        st.info("No player stats yet.")
    else:
        st.markdown("### Top Performers")
        # Show top 3 in special cards
        top3 = df.head(3)
        cols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        colors = ["#FFD700", "#C0C0C0", "#CD7132"]
        
        for i, row in enumerate(top3.itertuples()):
            with cols[i]:
                st.markdown(f"""<div class="custom-card" style="text-align: center; border-bottom: 3px solid {colors[i]};">
<div style="font-size: 2rem;">{medals[i]}</div>
<div style="font-weight: bold; color: var(--primary-blue); font-size: 1.2rem; margin: 10px 0;">{html.escape(str(row.name))}</div>
<div style="color: var(--text-dim); font-size: 0.8rem;">{html.escape(str(row.team))}</div>
<div style="font-family: 'Orbitron'; font-size: 1.5rem; color: var(--text-main); margin-top: 10px;">{row.avg_acs}</div>
<div style="font-size: 0.6rem; color: var(--text-dim);">AVG ACS</div>
</div>""", unsafe_allow_html=True)
        
        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        names = df['name'].tolist()
        sel = st.selectbox("Detailed Profile", ["Select a player..."] + names)
        if sel != "Select a player...":
            pid = int(df[df['name'] == sel].iloc[0]['player_id'])
            prof = get_player_profile(pid)
            if prof:
                    st.markdown(f"""<div style="margin-top: 2rem; padding: 1rem; border-left: 5px solid var(--primary-blue); background: rgba(63, 209, 255, 0.05);">
<h2 style="margin: 0;">{html.escape(str(prof['info'].get('name')))}</h2>
<div style="color: var(--text-dim); font-family: 'Orbitron';">{html.escape(str(prof['info'].get('team') or 'No Team'))} • {html.escape(str(prof['info'].get('rank') or 'Unranked'))}</div>
</div>""", unsafe_allow_html=True)
                    
                    st.write("") # Spacer
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Games", prof['games'])
                    c2.metric("Avg ACS", prof['avg_acs'])
                    c3.metric("KD", prof['kd_ratio'])
                    c4.metric("Assists", prof['total_assists'])
                    cmp_df = pd.DataFrame({
                        'Metric': ['ACS','Kills','Deaths','Assists'],
                        'Player': [prof['avg_acs'], prof['total_kills']/max(prof['games'],1), prof['total_deaths']/max(prof['games'],1), prof['total_assists']/max(prof['games'],1)],
                        'Rank Avg': [prof['sr_avg_acs'], prof['sr_k'], prof['sr_d'], prof['sr_a']],
                        'League Avg': [prof['lg_avg_acs'], prof['lg_k'], prof['lg_d'], prof['lg_a']],
                    })
                    st.dataframe(cmp_df, hide_index=True, use_container_width=True)
                    
                    # Performance Benchmarks Chart (Dual Axis)
                    import plotly.graph_objects as go
                    import plotly.express as px
                    from plotly.subplots import make_subplots
                    fig_cmp_admin = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    fig_cmp_admin.add_trace(go.Bar(name='Player ACS', x=['ACS'], y=[prof['avg_acs']], marker_color='#3FD1FF'), secondary_y=False)
                    fig_cmp_admin.add_trace(go.Bar(name='Rank Avg ACS', x=['ACS'], y=[prof['sr_avg_acs']], marker_color='#FF4655', opacity=0.7), secondary_y=False)
                    fig_cmp_admin.add_trace(go.Bar(name='League Avg ACS', x=['ACS'], y=[prof['lg_avg_acs']], marker_color='#ECE8E1', opacity=0.5), secondary_y=False)
                    
                    other_metrics = ['Kills', 'Deaths', 'Assists']
                    player_others = [prof['total_kills']/max(prof['games'],1), prof['total_deaths']/max(prof['games'],1), prof['total_assists']/max(prof['games'],1)]
                    rank_others = [prof['sr_k'], prof['sr_d'], prof['sr_a']]
                    league_others = [prof['lg_k'], prof['lg_d'], prof['lg_a']]
                    
                    fig_cmp_admin.add_trace(go.Bar(name='Player Stats', x=other_metrics, y=player_others, marker_color='#3FD1FF', showlegend=False), secondary_y=True)
                    fig_cmp_admin.add_trace(go.Bar(name='Rank Avg Stats', x=other_metrics, y=rank_others, marker_color='#FF4655', opacity=0.7, showlegend=False), secondary_y=True)
                    fig_cmp_admin.add_trace(go.Bar(name='League Avg Stats', x=other_metrics, y=league_others, marker_color='#ECE8E1', opacity=0.5, showlegend=False), secondary_y=True)
                    
                    fig_cmp_admin.update_layout(
                        barmode='group', height=350,
                        title_text="Performance vs Benchmarks",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    fig_cmp_admin.update_yaxes(title_text="ACS", secondary_y=False)
                    fig_cmp_admin.update_yaxes(title_text="K/D/A", secondary_y=True)
                    st.plotly_chart(apply_plotly_theme(fig_cmp_admin), use_container_width=True)
                    if 'trend' in prof and not prof['trend'].empty:
                        st.caption("ACS trend")
                        fig_acs = px.line(prof['trend'], x='label', y='avg_acs', 
                                          title="ACS Trend", markers=True,
                                          color_discrete_sequence=['#3FD1FF'])
                        st.plotly_chart(apply_plotly_theme(fig_acs), use_container_width=True)
                        
                        st.caption("KDA trend")
                        fig_kda = px.line(prof['trend'], x='label', y='kda', 
                                          title="KDA Trend", markers=True,
                                          color_discrete_sequence=['#FF4655'])
                        st.plotly_chart(apply_plotly_theme(fig_kda), use_container_width=True)

                    if 'sub_impact' in prof:
                        sid = prof['sub_impact']
                        st.caption("Substitution impact")
                        c_sub1, c_sub2 = st.columns(2)
                        with c_sub1:
                            fig_sub_acs = px.bar(x=['Starter', 'Sub'], y=[sid['starter_acs'], sid['sub_acs']], 
                                               title="ACS: Starter vs Sub",
                                               labels={'x': 'Role', 'y': 'ACS'},
                                               color_discrete_sequence=['#3FD1FF'])
                            st.plotly_chart(apply_plotly_theme(fig_sub_acs), use_container_width=True)
                        with c_sub2:
                            fig_sub_kda = px.bar(x=['Starter', 'Sub'], y=[sid['starter_kda'], sid['sub_kda']], 
                                               title="KDA: Starter vs Sub",
                                               labels={'x': 'Role', 'y': 'KDA'},
                                               color_discrete_sequence=['#FF4655'])
                            st.plotly_chart(apply_plotly_theme(fig_sub_kda), use_container_width=True)
                    if not prof['maps'].empty:
                        st.caption("Maps played")
                        st.dataframe(prof['maps'][['match_id','map_index','agent','acs','kills','deaths','assists','is_sub']], hide_index=True, use_container_width=True)

elif page == "Players Directory":
    import pandas as pd
    st.markdown('<h1 class="main-header">PLAYERS DIRECTORY</h1>', unsafe_allow_html=True)
    
    players_df = get_all_players_directory()
    
    ranks_base = ["Unranked", "Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"]
    dynamic_ranks = sorted(list(set(players_df['rank'].dropna().unique().tolist() + ranks_base)))
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        with c1:
            rf = st.multiselect("Filter by Rank", dynamic_ranks, default=dynamic_ranks)
        with c2:
            q = st.text_input("Search Name or Riot ID", placeholder="Search...")
        st.markdown('</div>', unsafe_allow_html=True)
    
    out = players_df.copy()
    out['rank'] = out['rank'].fillna("Unranked")
    out = out[out['rank'].isin(rf)]
    if q:
        s = q.lower()
        out = out[
            out['name'].str.lower().fillna("").str.contains(s) | 
            out['riot_id'].str.lower().fillna("").str.contains(s)
        ]
    
    # Display as a clean table with the brand theme
    st.markdown("<br>", unsafe_allow_html=True)
    if out.empty:
        st.info("No players found matching your criteria.")
    else:
        st.dataframe(
            out[['name', 'riot_id', 'rank', 'team']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Name", width="medium"),
                "riot_id": st.column_config.TextColumn("Riot ID", width="medium"),
                "rank": st.column_config.TextColumn("Rank", width="small"),
                "team": st.column_config.TextColumn("Team", width="medium"),
            }
        )

elif page == "Teams":
    import pandas as pd
    st.markdown('<h1 class="main-header">TEAMS</h1>', unsafe_allow_html=True)
    
    teams = get_teams_list_full()
    all_players = get_all_players()
    
    # Pre-group rosters for efficiency
    rosters_by_team = {}
    if not all_players.empty:
        for tid, group in all_players.groupby('default_team_id'):
            rosters_by_team[int(tid)] = group[['name', 'rank']]
    
    groups = ["All"] + sorted(teams['group_name'].dropna().unique().tolist())
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        g = st.selectbox("Filter by Group", groups)
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    show = teams if g == "All" else teams[teams['group_name'] == g]
    for row in show.itertuples():
        with st.container():
            # Team Header Card
            b64 = get_base64_image(row.logo_path)
            logo_img_html = f"<img src='data:image/png;base64,{b64}' width='60'/>" if b64 else "<div style='width:60px;height:60px;background:rgba(255,255,255,0.05);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);'>?</div>"
            
            st.markdown(f"""<div class="custom-card" style="margin-bottom: 10px;">
<div style="display: flex; align-items: center; gap: 20px;">
<div style="flex-shrink: 0;">
{logo_img_html}
</div>
<div>
<h3 style="margin: 0; color: var(--primary-blue); font-family: 'Orbitron';">{html.escape(str(row.name))} <span style="color: var(--text-dim); font-size: 0.9rem;">[{html.escape(str(row.tag or ''))}]</span></h3>
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Group {html.escape(str(row.group_name))}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            
            with st.expander("Manage Roster & Details"):
                roster = rosters_by_team.get(int(row.id), pd.DataFrame())
                
                if roster.empty:
                    st.info("No players yet")
                else:
                    st.dataframe(roster, hide_index=True, use_container_width=True)
                
                if st.session_state.get('is_admin'):
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption("Edit Team Details")
                        with st.form(f"edit_team_{row.id}"):
                            new_name = st.text_input("Name", value=row.name)
                            new_tag = st.text_input("Tag", value=row.tag or "")
                            new_group = st.text_input("Group", value=row.group_name or "")
                            new_logo = st.text_input("Logo Path", value=row.logo_path or "")
                            if st.form_submit_button("Update Team"):
                                # Use is_safe_path for validation
                                if new_logo and not is_safe_path(new_logo):
                                    st.error("Invalid logo path. Path traversal or absolute paths are not allowed.")
                                else:
                                    conn_u = get_conn()
                                    conn_u.execute("UPDATE teams SET name=?, tag=?, group_name=?, logo_path=? WHERE id=?", (new_name, new_tag or None, new_group or None, new_logo or None, int(row.id)))
                                    conn_u.commit()
                                    conn_u.close()
                                    st.success("Team updated")
                                    st.rerun()
                    
                    with col2:
                        st.caption("Roster Management")
                        # Add player
                        unassigned = all_players[all_players['default_team_id'].isna()]
                        add_sel = st.selectbox(f"Add Player", [""] + unassigned['name'].tolist(), key=f"add_{row.id}")
                        if add_sel:
                            pid = int(all_players[all_players['name'] == add_sel].iloc[0]['id'])
                            conn_a = get_conn()
                            conn_a.execute("UPDATE players SET default_team_id=? WHERE id=?", (int(row.id), pid))
                            conn_a.commit()
                            conn_a.close()
                            st.success("Player added")
                            st.rerun()
                        
                        # Remove player
                        if not roster.empty:
                            rem_sel = st.selectbox(f"Remove Player", [""] + roster['name'].tolist(), key=f"rem_{row.id}")
                            if rem_sel:
                                pid = int(roster[roster['name'] == rem_sel].iloc[0]['id'])
                                conn_d = get_conn()
                                conn_d.execute("UPDATE players SET default_team_id=NULL WHERE id=?", (pid,))
                                conn_d.commit()
                                conn_d.close()
                                st.success("Player removed")
                                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

elif page == "Playoffs":
    import pandas as pd
    st.markdown('<h1 class="main-header">PLAYOFFS</h1>', unsafe_allow_html=True)
    
    if not st.session_state.get('is_admin'):
        st.warning("Playoffs are currently in staging. Only administrators can view this page.")
        st.stop()
        
    df = get_playoff_matches()
    
    # Playoffs Management (Admin Only)
    with st.expander("🛠️ Manage Playoff Matches"):
        # Show current standings for seeding reference
        st.caption("Current Standings Reference (for seeding)")
        standings_df = get_standings()
        if not standings_df.empty:
            ref_cols = st.columns(4)
            for i, row in enumerate(standings_df.head(24).itertuples()):
                with ref_cols[i % 4]:
                    st.markdown(f"<small>#{i+1}: {row.name}</small>", unsafe_allow_html=True)
        st.divider()

        teams_df = get_teams_list()
        tnames = [""] + (teams_df['name'].tolist() if not teams_df.empty else [])
        
        with st.form("add_playoff_match"):
            c1, c2, c3 = st.columns(3)
            round_idx = c1.selectbox("Round", [1, 2, 3, 4, 5], format_func=lambda x: {
                1: "Round 1 (Play-ins)", 
                2: "Round of 16", 
                3: "Quarter-finals", 
                4: "Semi-finals", 
                5: "Final"
            }[x])
            pos = c2.number_input("Bracket Position", min_value=1, max_value=8, value=1)
            fmt = c3.selectbox("Format", ["BO1", "BO3", "BO5"], index=1)
            
            c4, c5 = st.columns(2)
            t1 = c4.selectbox("Team 1", tnames)
            t2 = c5.selectbox("Team 2", tnames)
            
            if st.form_submit_button("Add/Update Playoff Match"):
                conn = get_conn()
                t1_id = int(teams_df[teams_df['name'] == t1].iloc[0]['id']) if t1 else None
                t2_id = int(teams_df[teams_df['name'] == t2].iloc[0]['id']) if t2 else None
                
                # Check if exists
                existing = conn.execute("SELECT id FROM matches WHERE match_type='playoff' AND playoff_round=? AND bracket_pos=?", (round_idx, pos)).fetchone()
                if existing:
                    conn.execute("UPDATE matches SET team1_id=?, team2_id=?, format=? WHERE id=?", (t1_id, t2_id, fmt, existing[0]))
                else:
                    conn.execute("INSERT INTO matches (match_type, playoff_round, bracket_pos, team1_id, team2_id, format, status, score_t1, score_t2) VALUES ('playoff', ?, ?, ?, ?, ?, 'scheduled', 0, 0)", (round_idx, pos, t1_id, t2_id, fmt))
                conn.commit()
                conn.close()
                st.success("Playoff match updated")
                st.rerun()

    # Match Map Editor for Playoffs (Admin Only)
    if not df.empty:
        with st.expander("📝 Edit Playoff Match Scores & Maps"):
            # Vectorized option generation
            match_opts = ("R" + df['playoff_round'].astype(str) + " P" + df['bracket_pos'].astype(str) + ": " + df['t1_name'].fillna('') + " vs " + df['t2_name'].fillna('')).tolist()
            idx = st.selectbox("Select Playoff Match to Edit", list(range(len(match_opts))), format_func=lambda i: match_opts[i], key="po_edit_idx")
            m = df.iloc[idx]
            
            c0, c1, c2 = st.columns([1,1,1])
            with c0:
                fmt = st.selectbox("Format", ["BO1","BO3","BO5"], index=["BO1","BO3","BO5"].index(str(m['format'] or "BO3").upper()), key="po_fmt")
            with c1:
                s1 = st.number_input(m['t1_name'], min_value=0, value=int(m['score_t1'] or 0), key="po_s1")
            with c2:
                s2 = st.number_input(m['t2_name'], min_value=0, value=int(m['score_t2'] or 0), key="po_s2")

            st.caption("Per-Map Scores")
            maps_catalog = ["Ascent","Bind","Breeze","Corrode","Fracture","Haven","Icebox","Lotus","Pearl","Split","Sunset"]
            fmt_constraints = {"BO1": (1,1), "BO3": (2,3), "BO5": (3,5)}
            min_maps, max_maps = fmt_constraints.get(fmt, (1,1))
            existing_maps_df = get_match_maps(int(m['id']))
            maps_data = []
            for i in range(max_maps):
                with st.expander(f"Map {i+1}"):
                    pre_name = ""
                    pre_t1 = 0
                    pre_t2 = 0
                    pre_win = None
                    if not existing_maps_df.empty:
                        rowx = existing_maps_df[existing_maps_df['map_index'] == i]
                        if not rowx.empty:
                            pre_name = rowx.iloc[0]['map_name']
                            pre_t1 = int(rowx.iloc[0]['team1_rounds'])
                            pre_t2 = int(rowx.iloc[0]['team2_rounds'])
                            pre_win = int(rowx.iloc[0]['winner_id']) if pd.notna(rowx.iloc[0]['winner_id']) else None
                    nsel = st.selectbox(f"Name {i+1}", maps_catalog, index=(maps_catalog.index(pre_name) if pre_name in maps_catalog else 0), key=f"po_mname_{i}")
                    t1r = st.number_input(f"{m['t1_name']} rounds", min_value=0, value=pre_t1, key=f"po_t1r_{i}")
                    t2r = st.number_input(f"{m['t2_name']} rounds", min_value=0, value=pre_t2, key=f"po_t2r_{i}")
                    t1_id_val = int(m.get('t1_id', m.get('team1_id')))
                    t2_id_val = int(m.get('t2_id', m.get('team2_id')))
                    wsel = st.selectbox("Winner", ["", m['t1_name'], m['t2_name']], index=(1 if pre_win==t1_id_val else (2 if pre_win==t2_id_val else 0)), key=f"po_win_{i}")
                    wid = None
                    if wsel == m['t1_name']:
                        wid = t1_id_val
                    elif wsel == m['t2_name']:
                        wid = t2_id_val
                    maps_data.append({"map_index": i, "map_name": nsel, "team1_rounds": int(t1r), "team2_rounds": int(t2r), "winner_id": wid})
            
            if st.button("Save Playoff Match & Maps"):
                played = 0
                for i, md in enumerate(maps_data):
                    if i < max_maps and (i < min_maps or (md['team1_rounds']+md['team2_rounds']>0)):
                        played += 1
                upsert_match_maps(int(m['id']), maps_data[:max_maps])
                conn_u = get_conn()
                t1_id_val = int(m.get('t1_id', m.get('team1_id')))
                t2_id_val = int(m.get('t2_id', m.get('team2_id')))
                winner_id = None
                if s1 > s2:
                    winner_id = t1_id_val
                elif s2 > s1:
                    winner_id = t2_id_val
                conn_u.execute("UPDATE matches SET score_t1=?, score_t2=?, winner_id=?, status=?, format=?, maps_played=? WHERE id=?", (int(s1), int(s2), winner_id, 'completed' if played > 0 else 'scheduled', fmt, int(played), int(m['id'])))
                conn_u.commit()
                conn_u.close()
                st.success("Saved playoff match data")
                st.rerun()

    # Bracket Visualization
    if df.empty:
        st.info("No playoff matches scheduled yet.")
    else:
        # Team to Rank Map for seeding display
        standings_df = get_standings()
        team_to_rank = {}
        if not standings_df.empty:
            team_to_rank = dict(zip(standings_df['name'], range(1, len(standings_df) + 1)))

        # Define Rounds
        rounds = {
            1: "Round 1",
            2: "Round of 16",
            3: "Quarter-finals",
            4: "Semi-finals",
            5: "Final"
        }
        
        # Add some CSS for better bracket look
        st.markdown("""
        <style>
        .bracket-container {
            display: flex;
            justify-content: space-between;
            overflow-x: auto;
            padding: 20px 0;
            min-width: 1000px;
        }
        .bracket-round {
            display: flex;
            flex-direction: column;
            justify-content: space-around;
            width: 180px;
            flex-shrink: 0;
        }
        .bracket-match {
            background: var(--card-bg);
            border: 1px solid rgba(63, 209, 255, 0.2);
            border-radius: 8px;
            padding: 8px;
            margin: 10px 0;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            font-size: 0.8rem;
            min-height: 80px;
        }
        .match-team {
            display: flex;
            justify-content: space-between;
            padding: 2px 0;
        }
        .team-winner {
            color: var(--primary-blue);
            font-weight: bold;
        }
        .match-info {
            font-size: 0.6rem;
            color: var(--text-dim);
            text-align: center;
            margin-top: 4px;
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 4px;
        }
        .tbd-match {
            background: rgba(255,255,255,0.02);
            border: 1px dashed rgba(255,255,255,0.1);
            color: var(--text-dim);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        </style>
        """, unsafe_allow_html=True)

        cols = st.columns(len(rounds))
        
        for r_idx, r_name in rounds.items():
            with cols[r_idx-1]:
                st.markdown(f'<h4 style="text-align: center; color: var(--primary-blue); font-family: \'Orbitron\'; font-size: 0.8rem; margin-bottom: 20px;">{r_name}</h4>', unsafe_allow_html=True)
                
                r_matches = df[df['playoff_round'] == r_idx].sort_values('bracket_pos')
                
                # Number of slots for this round
                slots = 8 if r_idx in [1, 2] else (4 if r_idx == 3 else (2 if r_idx == 4 else 1))
                
                # Calculate offsets for centering
                # We'll use spacer divs to achieve vertical alignment
                
                for p in range(1, slots + 1):
                    # Vertical Spacing Logic
                    if r_idx == 3: # QF
                        if p == 1: st.markdown('<div style="height: 50px;"></div>', unsafe_allow_html=True)
                        else: st.markdown('<div style="height: 100px;"></div>', unsafe_allow_html=True)
                    elif r_idx == 4: # SF
                        if p == 1: st.markdown('<div style="height: 150px;"></div>', unsafe_allow_html=True)
                        else: st.markdown('<div style="height: 300px;"></div>', unsafe_allow_html=True)
                    elif r_idx == 5: # Final
                        st.markdown('<div style="height: 350px;"></div>', unsafe_allow_html=True)

                    match = r_matches[r_matches['bracket_pos'] == p]
                    
                    if not match.empty:
                        m = match.iloc[0]
                        t1_name = m['t1_name'] or "TBD"
                        t2_name = m['t2_name'] or "TBD"
                        
                        t1_rank = team_to_rank.get(t1_name, "")
                        t2_rank = team_to_rank.get(t2_name, "")
                        t1_display = f'<span style="color: var(--text-dim); font-size: 0.6rem; margin-right: 5px;">{t1_rank}</span>{html.escape(t1_name)}' if t1_rank else html.escape(t1_name)
                        t2_display = f'<span style="color: var(--text-dim); font-size: 0.6rem; margin-right: 5px;">{t2_rank}</span>{html.escape(t2_name)}' if t2_rank else html.escape(t2_name)

                        s1 = m['score_t1']
                        s2 = m['score_t2']
                        status = m['status']
                        
                        t1_class = "team-winner" if status == 'completed' and s1 > s2 else ""
                        t2_class = "team-winner" if status == 'completed' and s2 > s1 else ""
                        
                        st.markdown(f"""
                        <div class="bracket-match">
                            <div class="match-team">
                                <span class="{t1_class}">{t1_display}</span>
                                <span style="font-family: 'Orbitron';">{s1}</span>
                            </div>
                            <div class="match-team">
                                <span class="{t2_class}">{t2_display}</span>
                                <span style="font-family: 'Orbitron';">{s2}</span>
                            </div>
                            <div class="match-info">
                                {m['format']} • {status.upper()}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="bracket-match tbd-match">
                            TBD vs TBD
                        </div>
                        """, unsafe_allow_html=True)

elif page == "Admin Panel":
    import pandas as pd
    import numpy as np
    st.markdown('<h1 class="main-header">ADMIN PANEL</h1>', unsafe_allow_html=True)
    if not st.session_state.get('is_admin'):
        st.warning("Admin only")
    else:
        if st.session_state.get('role', 'admin') == 'dev':
            st.subheader("Database Reset")
            do_reset = st.checkbox("Confirm reset all tables")
            if do_reset and st.button("Reset DB"):
                reset_db()
                st.success("Database reset")
                st.rerun()
            st.subheader("Data Import")
            up = st.file_uploader("Upload SQLite .db", type=["db","sqlite"])
            if up and st.button("Import DB"):
                res = import_sqlite_db(up.read())
                st.success("Imported")
                if res:
                    st.write(res)
                st.rerun()
            st.subheader("Data Export")
            dbb = export_db_bytes()
            if dbb:
                st.download_button("Download DB", data=dbb, file_name=os.path.basename(DB_PATH) or "valorant_s23.db", mime="application/octet-stream")
            else:
                st.info("Database file not found")
            st.subheader("Cloud Backup")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Backup DB to GitHub"):
                    ok, msg = backup_db_to_github()
                    if ok:
                        st.success("Backup complete")
                    else:
                        st.error(msg)
            with c2:
                if st.button("Restore DB from GitHub"):
                    ok = restore_db_from_github()
                    if ok:
                        st.success("Restore complete")
                        st.rerun()
                    else:
                        st.error("Restore failed")
            st.subheader("Admins Management")
            with st.form("create_admin_form"):
                na = st.text_input("Username")
                pa = st.text_input("Password", type="password")
                ra = st.selectbox("Role", ["admin","dev"], index=0)
                sa = st.form_submit_button("Create Admin")
                if sa and na and pa:
                    try:
                        create_admin_with_role(na, pa, ra)
                        st.success("Admin created")
                        st.rerun()
                    except Exception:
                        st.error("Failed to create admin")
        st.subheader("Match Editor")
        wk_list = get_match_weeks()
        wk = st.selectbox("Week", wk_list) if wk_list else None
        if wk is None:
            st.info("No matches yet")
        else:
            dfm = get_week_matches(wk)
            if dfm.empty:
                st.info("No matches for this week")
            else:
                # Vectorized option generation
                match_opts = ("ID " + dfm['id'].astype(str) + ": " + dfm['t1_name'].fillna('') + " vs " + dfm['t2_name'].fillna('') + " (" + dfm['group_name'].fillna('') + ")").tolist()
                idx = st.selectbox("Match", list(range(len(match_opts))), format_func=lambda i: match_opts[i])
                m = dfm.iloc[idx]

                c0, c1, c2 = st.columns([1,1,1])
                with c0:
                    fmt = st.selectbox("Format", ["BO1","BO3","BO5"], index=["BO1","BO3","BO5"].index(str(m['format'] or "BO3").upper()))
                with c1:
                    s1 = st.number_input(m['t1_name'], min_value=0, value=int(m['score_t1'] or 0))
                with c2:
                    s2 = st.number_input(m['t2_name'], min_value=0, value=int(m['score_t2'] or 0))

                st.caption("Per-Map Scores")
                maps_catalog = ["Ascent","Bind","Breeze","Corrode","Fracture","Haven","Icebox","Lotus","Pearl","Split","Sunset"]
                fmt_constraints = {"BO1": (1,1), "BO3": (2,3), "BO5": (3,5)}
                min_maps, max_maps = fmt_constraints.get(fmt, (1,1))
                existing_maps_df = get_match_maps(int(m['id']))
                maps_data = []
                for i in range(max_maps):
                    with st.expander(f"Map {i+1}"):
                        # Tracker.gg link for this map
                        turl = st.text_input(f"Tracker.gg Link for Map {i+1}", key=f"turl_map_{m['id']}_{i}", placeholder="https://tracker.gg/valorant/match/...")
                        
                        pre_name = ""
                        pre_t1 = 0
                        pre_t2 = 0
                        pre_win = None
                        
                        # Check if we just scraped this map
                        if turl:
                            if f"scraped_data_{m['id']}_{i}" not in st.session_state or st.session_state[f"scraped_url_{m['id']}_{i}"] != turl:
                                with st.spinner("Scraping Tracker.gg..."):
                                    jsdata, err = scrape_tracker_match(turl)
                                    if err:
                                        st.error(err)
                                    else:
                                        # Save to session state for scoreboard reuse
                                        cur_t1_id = int(m.get('t1_id', m.get('team1_id')))
                                        json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id)
                                        
                                        st.session_state[f"ocr_{m['id']}_{i}"] = json_suggestions
                                        st.session_state[f"scraped_data_{m['id']}_{i}"] = {
                                            'map_name': map_name,
                                            't1_rounds': int(t1_r),
                                            't2_rounds': int(t2_r)
                                        }
                                        st.session_state[f"scraped_url_{m['id']}_{i}"] = turl

                                        # Save to file for caching
                                        mid_match = re.search(r'match/([a-zA-Z0-9\-]+)', turl)
                                        if mid_match:
                                            mid = mid_match.group(1)
                                            if not os.path.exists("matches"): os.makedirs("matches")
                                            with open(os.path.join("matches", f"match_{mid}.json"), 'w', encoding='utf-8') as f:
                                                json.dump(jsdata, f, indent=4)
                                        
                                        st.success("Map data scraped and scoreboard pre-filled!")

                        scraped = st.session_state.get(f"scraped_data_{m['id']}_{i}")
                        
                        if not existing_maps_df.empty:
                            rowx = existing_maps_df[existing_maps_df['map_index'] == i]
                            if not rowx.empty:
                                pre_name = rowx.iloc[0]['map_name']
                                pre_t1 = int(rowx.iloc[0]['team1_rounds'])
                                pre_t2 = int(rowx.iloc[0]['team2_rounds'])
                                pre_win = int(rowx.iloc[0]['winner_id']) if pd.notna(rowx.iloc[0]['winner_id']) else None
                        
                        # Override with scraped data if available
                        t1_id_val = int(m.get('t1_id', m.get('team1_id')))
                        t2_id_val = int(m.get('t2_id', m.get('team2_id')))
                        if scraped:
                            pre_name = scraped['map_name']
                            pre_t1 = scraped['t1_rounds']
                            pre_t2 = scraped['t2_rounds']
                            if pre_t1 > pre_t2:
                                pre_win = t1_id_val
                            elif pre_t2 > pre_t1:
                                pre_win = t2_id_val

                        nsel = st.selectbox(f"Name {i+1}", maps_catalog, index=(maps_catalog.index(pre_name) if pre_name in maps_catalog else 0), key=f"mname_{i}")
                        t1r = st.number_input(f"{m['t1_name']} rounds", min_value=0, value=pre_t1, key=f"t1r_{i}")
                        t2r = st.number_input(f"{m['t2_name']} rounds", min_value=0, value=pre_t2, key=f"t2r_{i}")
                        wsel = st.selectbox("Winner", ["", m['t1_name'], m['t2_name']], index=(1 if pre_win==t1_id_val else (2 if pre_win==t2_id_val else 0)), key=f"win_{i}")
                        wid = None
                        if wsel == m['t1_name']:
                            wid = t1_id_val
                        elif wsel == m['t2_name']:
                            wid = t2_id_val
                        maps_data.append({"map_index": i, "map_name": nsel, "team1_rounds": int(t1r), "team2_rounds": int(t2r), "winner_id": wid})
                if st.button("Save Maps"):
                    played = 0
                    for i, md in enumerate(maps_data):
                        if i < max_maps and (i < min_maps or (md['team1_rounds']+md['team2_rounds']>0)):
                            played += 1
                    upsert_match_maps(int(m['id']), maps_data[:max_maps])
                    conn_u = get_conn()
                    winner_id = None
                    if s1 > s2:
                        winner_id = t1_id_val
                    elif s2 > s1:
                        winner_id = t2_id_val
                    conn_u.execute("UPDATE matches SET score_t1=?, score_t2=?, winner_id=?, status=?, format=?, maps_played=? WHERE id=?", (int(s1), int(s2), winner_id, 'completed', fmt, int(played), int(m['id'])))
                    conn_u.commit()
                    conn_u.close()
                    st.success("Saved match and maps")
                    st.rerun()

                st.divider()
                st.subheader("Per-Map Scoreboard")
                map_choice = st.selectbox("Select Map", list(range(1, max_maps+1)), index=0)
                map_idx = map_choice - 1
                
                all_df0 = get_all_players()
                name_to_riot = dict(zip(all_df0['name'].astype(str), all_df0['riot_id'].astype(str))) if not all_df0.empty else {}
                
                # Match ID or Link input for automatic pre-filling
                col_json1, col_json2, col_json3 = st.columns([2, 1, 1])
                with col_json1:
                    match_input = st.text_input("Enter Tracker.gg Link or Match ID", key=f"mid_{m['id']}_{map_idx}", placeholder="https://tracker.gg/valorant/match/...")
                with col_json2:
                    if st.button("Force Apply", key=f"force_json_{m['id']}_{map_idx}"):
                        st.session_state[f"force_apply_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0) + 1
                        st.rerun()
                with col_json3:
                    st.info("💡 **Tip:** Paste a Tracker.gg match link to automatically fetch rounds and stats!")

                if match_input:
                    jsdata = None
                    # 1. Try if it's a URL
                    if "tracker.gg" in match_input:
                        if f"scraped_data_{m['id']}_{map_idx}" not in st.session_state or st.session_state.get(f"scraped_url_{m['id']}_{map_idx}") != match_input:
                            with st.spinner("Scraping Tracker.gg..."):
                                jsdata, err = scrape_tracker_match(match_input)
                                if err:
                                    st.error(err)
                                else:
                                    st.session_state[f"scraped_url_{m['id']}_{map_idx}"] = match_input
                                    # Save to file for caching/offline use
                                    match_id_match = re.search(r'match/([a-zA-Z0-9\-]+)', match_input)
                                    if match_id_match:
                                        mid = match_id_match.group(1)
                                        if not os.path.exists("matches"): os.makedirs("matches")
                                        with open(os.path.join("matches", f"match_{mid}.json"), 'w', encoding='utf-8') as f:
                                            json.dump(jsdata, f, indent=4)
                    else:
                        # 2. Treat as Match ID and load from folder
                        match_id_clean = re.sub(r'[^a-zA-Z0-9\-]', '', match_input)
                        json_filename = f"match_{match_id_clean}.json"
                        json_path = os.path.join("matches", json_filename)
                        if os.path.exists(json_path):
                            try:
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    jsdata = json.load(f)
                            except Exception as e:
                                st.error(f"JSON Error: {str(e)}")
                        else:
                            st.warning(f"File '{json_filename}' not found in 'matches' folder.")

                    if jsdata:
                        try:
                            cur_t1_id = int(m.get('t1_id', m.get('team1_id')))
                            json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id)
                            
                            st.session_state[f"ocr_{m['id']}_{map_idx}"] = json_suggestions
                            st.session_state[f"scraped_data_{m['id']}_{map_idx}"] = {
                                'map_name': map_name,
                                't1_rounds': int(t1_r),
                                't2_rounds': int(t2_r)
                            }
                            # Trigger force apply
                            st.session_state[f"force_apply_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0) + 1
                            st.success("Data loaded! Rounds and scoreboard pre-filled.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Processing Error: {str(e)}")
                
                force_apply = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", False)

                # Pre-fetch shared data outside the loop
                agents_list = get_agents_list()
                all_df = get_all_players()
                
                # Vectorized global list and map creation
                if not all_df.empty:
                    has_riot = all_df['riot_id'].notna() & (all_df['riot_id'].str.strip() != "")
                    all_df['display_label'] = all_df['name']
                    all_df.loc[has_riot, 'display_label'] = all_df.loc[has_riot, 'riot_id'].astype(str) + " (" + all_df.loc[has_riot, 'name'] + ")"
                    global_list = all_df['display_label'].tolist()
                    global_map = dict(zip(global_list, all_df['id']))
                    label_to_riot = dict(zip(all_df.loc[has_riot, 'display_label'], all_df.loc[has_riot, 'riot_id'].str.strip().str.lower()))
                    riot_to_label = {v: k for k, v in label_to_riot.items()}
                else:
                    global_list = []
                    global_map = {}
                    label_to_riot = {}
                    riot_to_label = {}

                # Vectorized player lookup creation (common for both teams)
                player_lookup = {}
                if not all_df.empty:
                    player_lookup = {
                        row.id: {
                            'label': row.display_label,
                            'riot_id': str(row.riot_id).strip().lower() if pd.notna(row.riot_id) and str(row.riot_id).strip() else None
                        }
                        for row in all_df.itertuples()
                    }

                # Fetch all stats for this match and map index at once to reduce DB calls
                conn_p = get_conn()
                all_map_stats = pd.read_sql(
                    "SELECT * FROM match_stats_map WHERE match_id=? AND map_index=?", 
                    conn_p, 
                    params=(int(m['id']), map_idx)
                )
                conn_p.close()

                for team_key, team_id, team_name in [("t1", int(m.get('t1_id', m.get('team1_id'))), m['t1_name']), ("t2", int(m.get('t2_id', m.get('team2_id'))), m['t2_name'])]:
                    st.caption(f"{team_name} players")
                    
                    # Filter roster from all_df instead of querying DB
                    roster_df = all_df[all_df['default_team_id'] == team_id].sort_values('name')
                    
                    # Filter existing stats from the pre-fetched all_map_stats
                    existing = all_map_stats[all_map_stats['team_id'] == team_id]
                    
                    roster_list = roster_df['display_label'].tolist() if not roster_df.empty else []
                    roster_map = dict(zip(roster_list, roster_df['id']))
                    rows = []
                    
                    sug = st.session_state.get(f"ocr_{m['id']}_{map_idx}", {})
                    our_team_num = 1 if team_key == "t1" else 2
                    
                    if not existing.empty and not force_apply:
                        for r in existing.itertuples():
                            pname = ""
                            rid = None
                            if r.player_id in player_lookup:
                                pname = player_lookup[r.player_id]['label']
                                rid = player_lookup[r.player_id]['riot_id']
                            
                            sfname = ""
                            if r.subbed_for_id in player_lookup:
                                sfname = player_lookup[r.subbed_for_id]['label']
                            
                            # Merge with JSON if existing stats are 0
                            acs, k, d, a = int(r.acs or 0), int(r.kills or 0), int(r.deaths or 0), int(r.assists or 0)
                            agent = r.agent or (agents_list[0] if agents_list else "")
                            
                            if rid and rid in sug and acs == 0 and k == 0:
                                s = sug[rid]
                                acs, k, d, a = s['acs'], s['k'], s['d'], s['a']
                                agent = s.get('agent') or agent
                                
                            rows.append({
                                'player': pname,
                                'is_sub': bool(r.is_sub),
                                'subbed_for': sfname or (roster_list[0] if roster_list else ""),
                                'agent': agent,
                                'acs': acs,
                                'k': k,
                                'd': d,
                                'a': a,
                            })
                    else:
                        # New Logic for JSON pre-fill with substitution support
                        team_sug_rids = [rid for rid, s in sug.items() if s.get('team_num') == our_team_num]
                        roster_labels = roster_list
                        
                        json_roster_matches = [] # (rid, label, stats)
                        json_subs = [] # (rid, label_or_none, stats)
                        
                        for rid in team_sug_rids:
                            s = sug[rid]
                            l_rid = rid.lower()
                            db_label = riot_to_label.get(l_rid)
                            
                            if db_label in roster_labels:
                                json_roster_matches.append((rid, db_label, s))
                            else:
                                json_subs.append((rid, db_label, s))
                        
                        used_roster_labels = [m[1] for m in json_roster_matches]
                        missing_roster_labels = [l for l in roster_labels if l not in used_roster_labels]
                        
                        rows = []
                        # 1. Add roster matches
                        for rid, label, s in json_roster_matches:
                            rows.append({
                                'player': label,
                                'is_sub': False,
                                'subbed_for': label,
                                'agent': s.get('agent') or (agents_list[0] if agents_list else ""),
                                'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']
                            })
                            
                        # 2. Add subs (mapping to missing roster players)
                        for rid, db_label, s in json_subs:
                            if len(rows) >= 5: break
                            subbed_for = missing_roster_labels.pop(0) if missing_roster_labels else (roster_labels[0] if roster_labels else "")
                            rows.append({
                                'player': db_label or "",
                                'is_sub': True,
                                'subbed_for': subbed_for,
                                'agent': s.get('agent') or (agents_list[0] if agents_list else ""),
                                'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']
                            })
                            
                        # 3. Fill remaining slots with missing roster players
                        while len(rows) < 5 and missing_roster_labels:
                            l = missing_roster_labels.pop(0)
                            rows.append({
                                'player': l,
                                'is_sub': False,
                                'subbed_for': l,
                                'agent': agents_list[0] if agents_list else "",
                                'acs': 0, 'k': 0, 'd': 0, 'a': 0
                            })
                            
                        # 4. Final fallback to 5 rows
                        while len(rows) < 5:
                            rows.append({
                                'player': "",
                                'is_sub': False,
                                'subbed_for': roster_labels[0] if roster_labels else "",
                                'agent': agents_list[0] if agents_list else "",
                                'acs': 0, 'k': 0, 'd': 0, 'a': 0
                            })

                    with st.form(f"sb_{team_key}_{map_idx}"):
                        h1,h2,h3,h4,h5,h6,h7,h8,h9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                        h1.write("Player")
                        h2.write("Sub?")
                        h3.write("Subbing For")
                        h4.write("Agent")
                        h5.write("ACS")
                        h6.write("K")
                        h7.write("D")
                        h8.write("A")
                        h9.write("Conf")
                        entries = []
                        
                        for i, rowd in enumerate(rows):
                            c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                            # Find the best index for the player selectbox
                            if rowd['player'] in global_list:
                                p_idx = global_list.index(rowd['player'])
                            else:
                                p_idx = len(global_list) # Empty

                            # Use a unique key for the inputs to force refresh when JSON changes or Force Apply is clicked
                            # We include the hash of suggestions and the force apply counter to ensure inputs update
                            force_cnt = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0)
                            input_key_suffix = f"{m['id']}_{map_idx}_{team_key}_{i}_{force_cnt}"
                            if sug:
                                input_key_suffix += f"_{hash(str(sug))}"
                            
                            psel = c1.selectbox(f"P_{input_key_suffix}", global_list + [""], index=p_idx, label_visibility="collapsed")
                            rid_psel = label_to_riot.get(psel)
                            
                            # Update key suffix for stats inputs to include the selected player
                            # This ensures that changing a player updates their stats from suggestions
                            stats_key_suffix = input_key_suffix + f"_{rid_psel}"
                            
                            is_sub = c2.checkbox(f"S_{input_key_suffix}", value=rowd['is_sub'], label_visibility="collapsed")
                            sf_sel = c3.selectbox(f"SF_{input_key_suffix}", roster_list + [""], index=(roster_list.index(rowd['subbed_for']) if rowd['subbed_for'] in roster_list else (0 if roster_list else 0)), label_visibility="collapsed")
                            ag_sel = c4.selectbox(f"Ag_{input_key_suffix}", agents_list + [""], index=(agents_list.index(rowd['agent']) if rowd['agent'] in agents_list else (0 if agents_list else 0)), label_visibility="collapsed")
                            
                            # Final fallback: if selectbox changed, try to get suggestion again
                            current_sug = sug.get(rid_psel, {}) if rid_psel else {}
                            
                            val_acs = current_sug.get('acs', rowd['acs'])
                            val_k = current_sug.get('k', rowd['k'])
                            val_d = current_sug.get('d', rowd['d'])
                            val_a = current_sug.get('a', rowd['a'])
                            val_conf = current_sug.get('conf', '-')
                            
                            acs = c5.number_input(f"ACS_{stats_key_suffix}", min_value=0, value=int(val_acs), label_visibility="collapsed")
                            k = c6.number_input(f"K_{stats_key_suffix}", min_value=0, value=int(val_k), label_visibility="collapsed")
                            d = c7.number_input(f"D_{stats_key_suffix}", min_value=0, value=int(val_d), label_visibility="collapsed")
                            a = c8.number_input(f"A_{stats_key_suffix}", min_value=0, value=int(val_a), label_visibility="collapsed")
                            c9.write(val_conf)
                            
                            entries.append({
                                'player_id': global_map.get(psel),
                                'is_sub': int(is_sub),
                                'subbed_for_id': roster_map.get(sf_sel),
                                'agent': ag_sel or None,
                                'acs': int(acs),
                                'kills': int(k),
                                'deaths': int(d),
                                'assists': int(a),
                            })
                        submit = st.form_submit_button("Save Scoreboard")
                        if submit:
                            conn_s = get_conn()
                            conn_s.execute("DELETE FROM match_stats_map WHERE match_id=? AND map_index=? AND team_id=?", (int(m['id']), map_idx, team_id))
                            
                            # Pre-fetch all player Riot IDs for the entries to avoid queries in loop
                            entry_p_ids = [e['player_id'] for e in entries if e['player_id']]
                            p_riot_map = {}
                            if entry_p_ids:
                                placeholders = ",".join(["?"] * len(entry_p_ids))
                                p_riots = conn_s.execute(f"SELECT id, riot_id FROM players WHERE id IN ({placeholders})", entry_p_ids).fetchall()
                                p_riot_map = {r[0]: r[1] for r in p_riots}

                            for e in entries:
                                if e['player_id']:
                                    # Auto-complete stats from JSON if they are 0 and player has suggestion
                                    final_acs, final_k, final_d, final_a = e['acs'], e['kills'], e['deaths'], e['assists']
                                    final_agent = e['agent']
                                    
                                    # Get Riot ID for this player from pre-fetched map
                                    rid_raw = p_riot_map.get(e['player_id'])
                                    rid_key = str(rid_raw).strip().lower() if rid_raw else None
                                    if rid_key and rid_key in sug and final_acs == 0 and final_k == 0:
                                        s = sug[rid_key]
                                        final_acs, final_k, final_d, final_a = s['acs'], s['k'], s['d'], s['a']
                                        if not final_agent:
                                            final_agent = s.get('agent')

                                    conn_s.execute(
                                        "INSERT INTO match_stats_map (match_id, map_index, team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (int(m['id']), map_idx, team_id, e['player_id'], e['is_sub'], e['subbed_for_id'], final_agent, final_acs, final_k, final_d, final_a)
                                    )
                            conn_s.commit()
                            conn_s.close()
                            st.success("Scoreboard saved (stats auto-filled from JSON if they were 0)")
                            if f"force_apply_{m['id']}_{map_idx}" in st.session_state:
                                del st.session_state[f"force_apply_{m['id']}_{map_idx}"]
                            st.rerun()

        st.divider()
        st.subheader("Players Admin")
        players_df = get_all_players_directory()
        teams_list = get_teams_list()
        
        team_names = teams_list['name'].tolist() if not teams_list.empty else []
        team_map = dict(zip(teams_list['name'], teams_list['id']))
        rvals = ["Unranked","Iron","Bronze","Silver","Gold","Platinum","Diamond","Ascendant","Immortal","Radiant"]
        rvals_all = sorted(list(set(rvals + players_df['rank'].dropna().unique().tolist())))
        if st.session_state.get('role', 'admin') == 'dev':
            st.subheader("Add Player")
            with st.form("add_player_admin"):
                nm_new = st.text_input("Name")
                rid_new = st.text_input("Riot ID")
                rk_new = st.selectbox("Rank", rvals, index=0)
                tmn_new = st.selectbox("Team", [""] + team_names, index=0)
                add_ok = st.form_submit_button("Create Player")
                if add_ok and nm_new:
                    conn_add = get_conn()
                    # Check for duplicates
                    rid_clean = rid_new.strip() if rid_new else ""
                    nm_clean = nm_new.strip()
                    
                    if rid_clean:
                        existing_rid = pd.read_sql("SELECT name FROM players WHERE LOWER(riot_id) = ?", conn_add, params=(rid_clean.lower(),))
                        if not existing_rid.empty:
                            st.error(f"Error: A player ('{existing_rid.iloc[0]['name']}') already has Riot ID '{rid_clean}'.")
                            conn_add.close()
                            return
                    
                    existing_name = pd.read_sql("SELECT id FROM players WHERE LOWER(name) = ?", conn_add, params=(nm_clean.lower(),))
                    if not existing_name.empty:
                        st.error(f"Error: A player named '{nm_clean}' already exists.")
                        conn_add.close()
                        return

                    dtid_new = team_map.get(tmn_new) if tmn_new else None
                    conn_add.execute("INSERT INTO players (name, riot_id, rank, default_team_id) VALUES (?, ?, ?, ?)", (nm_clean, rid_clean, rk_new, dtid_new))
                    conn_add.commit()
                    conn_add.close()
                    st.success("Player added")
                    st.rerun()
            
            if st.button("🔍 Cleanup Duplicate Players", help="Merge players with exact same Riot ID or case-insensitive name"):
                conn_clean = get_conn()
                try:
                    players = pd.read_sql("SELECT id, name, riot_id FROM players", conn_clean)
                    players['name_lower'] = players['name'].str.lower().str.strip()
                    players['riot_lower'] = players['riot_id'].str.lower().str.strip().fillna("")
                    
                    merged_count = 0
                    # 1. Exact Riot ID duplicates
                    riot_dupes = players[players['riot_lower'] != ""][players.duplicated('riot_lower', keep=False)]
                    for rid, group in riot_dupes.groupby('riot_lower'):
                        group = group.sort_values('id')
                        keep_id = group.iloc[0]['id']
                        remove_ids = group.iloc[1:]['id'].tolist()
                        for rid_to_rem in remove_ids:
                            conn_clean.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (int(keep_id), int(rid_to_rem)))
                            conn_clean.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (int(keep_id), int(rid_to_rem)))
                            conn_clean.execute("DELETE FROM players WHERE id = ?", (int(rid_to_rem),))
                            merged_count += 1
                    
                    # 2. Case-insensitive Name duplicates (only if Riot ID matches or one is empty)
                    name_dupes = players[players.duplicated('name_lower', keep=False)]
                    for name, group in name_dupes.groupby('name_lower'):
                        group = group.sort_values('id')
                        keep_id = group.iloc[0]['id']
                        remove_ids = group.iloc[1:]['id'].tolist()
                        for rid_to_rem in remove_ids:
                            # Re-verify it still exists (might have been deleted by Riot ID check)
                            exists = conn_clean.execute("SELECT id FROM players WHERE id=?", (int(rid_to_rem),)).fetchone()
                            if exists:
                                conn_clean.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("DELETE FROM players WHERE id = ?", (int(rid_to_rem),))
                                merged_count += 1
                    
                    conn_clean.commit()
                    if merged_count > 0:
                        st.success(f"Successfully merged {merged_count} duplicate records.")
                        st.rerun()
                    else:
                        st.info("No duplicates found to merge.")
                except Exception as e:
                    st.error(f"Cleanup error: {e}")
                finally:
                    conn_clean.close()

            st.markdown("---")
            st.subheader("Delete Player")
            with st.form("delete_player_admin"):
                # Fetch all players for the dropdown
                p_list_df = get_all_players()
                
                if not p_list_df.empty:
                    # Vectorized player options creation
                    has_rid = p_list_df['riot_id'].notna() & (p_list_df['riot_id'].str.strip() != "")
                    p_list_df['display'] = p_list_df['name']
                    p_list_df.loc[has_rid, 'display'] = p_list_df.loc[has_rid, 'name'] + " (" + p_list_df.loc[has_rid, 'riot_id'].astype(str) + ")"
                    p_list_df.loc[~has_rid, 'display'] = p_list_df.loc[~has_rid, 'name'] + " (No Riot ID)"
                    
                    p_options = dict(zip(p_list_df['display'], p_list_df['id']))
                    p_to_del_name = st.selectbox("Select Player to Delete", options=list(p_options.keys()))
                    p_to_del_id = p_options[p_to_del_name]
                    
                    confirm_del = st.checkbox("I understand this will remove all stats associated with this player.")
                    del_submitted = st.form_submit_button("Delete Player", type="primary")
                    
                    if del_submitted:
                        if not confirm_del:
                            st.warning("Please confirm the deletion.")
                        else:
                            conn_exec = get_conn()
                            try:
                                 # Clean up references in match_stats_map and match_stats
                                 conn_exec.execute("DELETE FROM match_stats_map WHERE player_id = ?", (int(p_to_del_id),))
                                 conn_exec.execute("DELETE FROM match_stats_map WHERE subbed_for_id = ?", (int(p_to_del_id),))
                                 conn_exec.execute("DELETE FROM match_stats WHERE player_id = ?", (int(p_to_del_id),))
                                 conn_exec.execute("DELETE FROM match_stats WHERE subbed_for_id = ?", (int(p_to_del_id),))
                                 # Delete the player
                                 conn_exec.execute("DELETE FROM players WHERE id = ?", (int(p_to_del_id),))
                                 conn_exec.commit()
                                 st.success(f"Player '{p_to_del_name}' deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Deletion error: {e}")
                            finally:
                                conn_exec.close()
                else:
                    st.info("No players found to delete.")
        cfa, cfb, cfc = st.columns([2,2,2])
        with cfa:
            tf = st.multiselect("Team", [""] + team_names, default=[""] + team_names)
        with cfb:
            rf = st.multiselect("Rank", rvals_all, default=rvals_all)
        with cfc:
            q = st.text_input("Search")
        fdf = players_df.copy()
        fdf = fdf[fdf['team'].fillna("").isin(tf)]
        fdf = fdf[fdf['rank'].fillna("Unranked").isin(rf)]
        if q:
            s = q.lower()
            fdf = fdf[
                fdf['name'].str.lower().fillna("").str.contains(s) | 
                fdf['riot_id'].str.lower().fillna("").str.contains(s)
            ]
        edited = st.data_editor(
            fdf,
            num_rows=("dynamic" if st.session_state.get('role', 'admin') == 'dev' else "fixed"),
            use_container_width=True,
            column_config={
                "team": st.column_config.SelectboxColumn(options=[""] + team_names, required=False)
            }
        )
        if st.button("Save Players"):
            conn_up = get_conn()
            # Get current state to check for duplicates
            current_players = pd.read_sql("SELECT id, name, riot_id FROM players", conn_up)
            current_players['name_lower'] = current_players['name'].str.lower().str.strip()
            current_players['riot_lower'] = current_players['riot_id'].str.lower().str.strip().fillna("")
            
            # Vectorized duplicate check
            error_found = False
            if not edited.empty:
                nm_lower = edited['name'].str.lower().str.strip()
                rid_lower = edited['riot_id'].str.lower().str.strip().fillna("")
                
                # 1. Check internal duplicates in 'edited'
                if nm_lower.duplicated().any():
                    dup_name = edited.loc[nm_lower.duplicated(), 'name'].iloc[0]
                    st.error(f"Error: Player name '{dup_name}' is duplicated in your edits.")
                    error_found = True
                elif rid_lower[rid_lower != ""].duplicated().any():
                    dup_rid = edited.loc[rid_lower[rid_lower != ""].duplicated(), 'riot_id'].iloc[0]
                    st.error(f"Error: Riot ID '{dup_rid}' is duplicated in your edits.")
                    error_found = True
                
                if not error_found:
                    # 2. Check duplicates against 'current_players'
                    # We check each row in 'edited' against 'current_players' (excluding the same ID)
                    for row in edited.itertuples():
                        pid = getattr(row, 'id', None)
                        nm = str(row.name).strip()
                        rid = str(row.riot_id).strip() if pd.notna(row.riot_id) else ""
                        
                        nm_l = nm.lower()
                        rid_l = rid.lower()
                        
                        # Find potential conflicts
                        others = current_players[current_players['id'] != pid] if pd.notna(pid) else current_players
                        
                        if nm_l in others['name_lower'].values:
                            st.error(f"Error: Player name '{nm}' already exists in the database. Changes not saved.")
                            error_found = True
                            break
                        
                        if rid_l and rid_l in others['riot_lower'].values:
                            st.error(f"Error: Riot ID '{rid}' already exists in the database. Changes not saved.")
                            error_found = True
                            break
            
            if not error_found:
                # Identify deleted players
                original_ids = set(fdf['id'].dropna().astype(int).tolist())
                edited_ids = set(edited['id'].dropna().astype(int).tolist())
                deleted_ids = original_ids - edited_ids
                
                if deleted_ids:
                    for pid in deleted_ids:
                         conn_up.execute("DELETE FROM match_stats_map WHERE player_id = ?", (pid,))
                         conn_up.execute("DELETE FROM match_stats_map WHERE subbed_for_id = ?", (pid,))
                         conn_up.execute("DELETE FROM match_stats WHERE player_id = ?", (pid,))
                         conn_up.execute("DELETE FROM match_stats WHERE subbed_for_id = ?", (pid,))
                         conn_up.execute("DELETE FROM players WHERE id = ?", (pid,))

                for row in edited.itertuples():
                    pid = getattr(row, 'id', None)
                    nm = str(row.name).strip()
                    rid = str(row.riot_id).strip() if pd.notna(row.riot_id) else ""
                    rk = getattr(row, 'rank', "Unranked") or "Unranked"
                    tmn = getattr(row, 'team', None)
                    dtid = team_map.get(tmn) if pd.notna(tmn) else None
                    
                    if pd.isna(pid):
                        if st.session_state.get('role', 'admin') == 'dev':
                            conn_up.execute("INSERT INTO players (name, riot_id, rank, default_team_id) VALUES (?, ?, ?, ?)", (nm, rid, rk, dtid))
                    else:
                        conn_up.execute("UPDATE players SET name=?, riot_id=?, rank=?, default_team_id=? WHERE id=?", (nm, rid, rk, dtid, int(pid)))
                conn_up.commit()
                st.success("Players saved")
                st.rerun()
            conn_up.close()

        st.divider()
        st.subheader("Schedule Manager")
        teams_df = get_teams_list_full()
        weeks = list(range(1, 11))
        w = st.selectbox("Week", weeks, index=0)
        gnames = sorted([x for x in teams_df['group_name'].dropna().unique().tolist()])
        gsel = st.selectbox("Group", gnames + [""] , index=(0 if gnames else 0))
        tnames = teams_df['name'].tolist()
        t1 = st.selectbox("Team 1", tnames)
        t2 = st.selectbox("Team 2", tnames, index=(1 if len(tnames)>1 else 0))
        fmt = st.selectbox("Format", ["BO1","BO3","BO5"], index=1)
        if st.button("Add Match"):
            conn_ins = get_conn()
            id1 = int(teams_df[teams_df['name'] == t1].iloc[0]['id'])
            id2 = int(teams_df[teams_df['name'] == t2].iloc[0]['id'])
            conn_ins.execute("INSERT INTO matches (week, group_name, status, format, team1_id, team2_id, score_t1, score_t2, maps_played) VALUES (?, ?, 'scheduled', ?, ?, ?, 0, 0)", (int(w), gsel or None, fmt, id1, id2))
            conn_ins.commit()
            conn_ins.close()
            st.success("Match added")
            st.rerun()

elif page == "Substitutions Log":
    import pandas as pd
    import plotly.express as px
    st.markdown('<h1 class="main-header">SUBSTITUTIONS LOG</h1>', unsafe_allow_html=True)
    
    df = get_substitutions_log()
    if df.empty:
        st.info("No substitutions recorded.")
    else:
        # Summary Metrics
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Total Subs</div>
<div style="font-size: 2.5rem; font-family: 'Orbitron'; color: var(--primary-blue); margin: 10px 0;">{len(df)}</div>
</div>""", unsafe_allow_html=True)
        with m2:
            top_team = df.groupby('team').size().idxmax() if not df.empty else "N/A"
            st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Most Active Team</div>
<div style="font-size: 1.5rem; font-family: 'Orbitron'; color: var(--primary-red); margin: 10px 0;">{html.escape(str(top_team))}</div>
</div>""", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Charts Section
        c1, c2 = st.columns(2)
        with c1:
            tcount = df.groupby('team').size().reset_index(name='subs').sort_values('subs', ascending=False)
            fig_sub_team = px.bar(tcount, x='team', y='subs', title="Subs by Team",
                                  color_discrete_sequence=['#3FD1FF'], labels={'team': 'Team', 'subs': 'Substitutions'})
            st.plotly_chart(apply_plotly_theme(fig_sub_team), use_container_width=True)
        
        with c2:
            if 'week' in df.columns:
                wcount = df.groupby('week').size().reset_index(name='subs')
                fig_sub_week = px.line(wcount, x='week', y='subs', title="Subs per Week", markers=True,
                                       color_discrete_sequence=['#FF4655'], labels={'week': 'Week', 'subs': 'Substitutions'})
                st.plotly_chart(apply_plotly_theme(fig_sub_week), use_container_width=True)
        
        # Detailed Log
        st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">DETAILED LOG</h3>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

elif page == "Player Profile":
    import pandas as pd
    players_df = get_all_players()
    
    st.markdown('<h1 class="main-header">PLAYER PROFILE</h1>', unsafe_allow_html=True)
    
    opts = players_df['name'].tolist()
    sel = st.selectbox("Select a Player", opts) if opts else None
    
    if sel:
        pid = int(players_df[players_df['name'] == sel].iloc[0]['id'])
        prof = get_player_profile(pid)
        
        if prof:
            # Header Card
            st.markdown(f"""<div class="custom-card" style="margin-bottom: 2rem;">
<div style="display: flex; align-items: center; gap: 20px;">
<div style="background: var(--primary-blue); width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: var(--bg-dark);">
{html.escape(str(prof['info'].get('name')[0].upper() if prof['info'].get('name') else 'P'))}
</div>
<div>
<h2 style="margin: 0; color: var(--primary-blue); font-family: 'Orbitron';">{html.escape(str(prof['info'].get('name')))}</h2>
<div style="color: var(--text-dim); font-size: 1.1rem;">{html.escape(str(prof['info'].get('team') or 'Free Agent'))}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            
            # Metrics Grid
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Games</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{prof['games']}</div>
</div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Avg ACS</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-blue); margin: 10px 0;">{prof['avg_acs']}</div>
</div>""", unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">KD Ratio</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-red); margin: 10px 0;">{prof['kd_ratio']}</div>
</div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Assists</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{prof['total_assists']}</div>
</div>""", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Comparison Radar or Bar Chart
            st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">PERFORMANCE BENCHMARKS</h3>', unsafe_allow_html=True)
            
            cmp_df = pd.DataFrame({
                'Metric': ['ACS','Kills/Match','Deaths/Match','Assists/Match'],
                'Player': [prof['avg_acs'], prof['total_kills']/max(prof['games'],1), prof['total_deaths']/max(prof['games'],1), prof['total_assists']/max(prof['games'],1)],
                'Rank Avg': [prof['sr_avg_acs'], prof['sr_k'], prof['sr_d'], prof['sr_a']],
                'League Avg': [prof['lg_avg_acs'], prof['lg_k'], prof['lg_d'], prof['lg_a']],
            })
            
            # Plotly Bar Chart for comparison with dual axis
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            fig_cmp = make_subplots(specs=[[{"secondary_y": True}]])
            
            # ACS (Primary Y-Axis)
            fig_cmp.add_trace(go.Bar(name='Player ACS', x=['ACS'], y=[prof['avg_acs']], marker_color='#3FD1FF'), secondary_y=False)
            fig_cmp.add_trace(go.Bar(name='Rank Avg ACS', x=['ACS'], y=[prof['sr_avg_acs']], marker_color='#FF4655', opacity=0.7), secondary_y=False)
            fig_cmp.add_trace(go.Bar(name='League Avg ACS', x=['ACS'], y=[prof['lg_avg_acs']], marker_color='#ECE8E1', opacity=0.5), secondary_y=False)
            
            # Per-Match Stats (Secondary Y-Axis)
            other_metrics = ['Kills/Match', 'Deaths/Match', 'Assists/Match']
            player_others = [prof['total_kills']/max(prof['games'],1), prof['total_deaths']/max(prof['games'],1), prof['total_assists']/max(prof['games'],1)]
            rank_others = [prof['sr_k'], prof['sr_d'], prof['sr_a']]
            league_others = [prof['lg_k'], prof['lg_d'], prof['lg_a']]
            
            fig_cmp.add_trace(go.Bar(name='Player Stats', x=other_metrics, y=player_others, marker_color='#3FD1FF', showlegend=False), secondary_y=True)
            fig_cmp.add_trace(go.Bar(name='Rank Avg Stats', x=other_metrics, y=rank_others, marker_color='#FF4655', opacity=0.7, showlegend=False), secondary_y=True)
            fig_cmp.add_trace(go.Bar(name='League Avg Stats', x=other_metrics, y=league_others, marker_color='#ECE8E1', opacity=0.5, showlegend=False), secondary_y=True)
            
            fig_cmp.update_layout(
                barmode='group', 
                height=400,
                title_text="Performance vs Benchmarks (ACS on Left, Others on Right)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_cmp.update_yaxes(title_text="Average Combat Score (ACS)", secondary_y=False)
            fig_cmp.update_yaxes(title_text="K/D/A Per Match", secondary_y=True)
            
            st.plotly_chart(apply_plotly_theme(fig_cmp), use_container_width=True)
            
            if not prof['maps'].empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">RECENT MATCHES</h3>', unsafe_allow_html=True)
                maps_display = prof['maps'][['match_id','map_index','agent','acs','kills','deaths','assists','is_sub']].copy()
                maps_display.columns = ['Match ID', 'Map', 'Agent', 'ACS', 'K', 'D', 'A', 'Sub']
                st.dataframe(maps_display, hide_index=True, use_container_width=True)
