import streamlit as st
import sqlite3
import pandas as pd
import os
import hashlib
import hmac
import secrets
import tempfile
import base64
import requests
import re
import io
import json
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image, ImageOps

def ocr_extract(image_bytes, crop_box=None):
    """
    Returns (text, dataframe, error_message)
    """
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

def get_secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

DB_PATH = get_secret("DB_PATH", "valorant_s23.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_admin_table():
    conn = get_conn()
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
    conn.commit()
    conn.close()

def ensure_base_schema():
    conn = get_conn()
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
    conn.commit()
    conn.close()

def ensure_column(table, column_name, column_def_sql):
    conn = get_conn()
    c = conn.cursor()
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if column_name not in cols:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column_def_sql}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def ensure_upgrade_schema():
    conn = get_conn()
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
    conn.commit()
    conn.close()
    ensure_column("teams", "logo_path", "logo_path TEXT")
    ensure_column("players", "rank", "rank TEXT")
    ensure_column("matches", "format", "format TEXT")
    ensure_column("matches", "maps_played", "maps_played INTEGER DEFAULT 0")
    ensure_column("seasons", "is_active", "is_active BOOLEAN DEFAULT 0")
    ensure_column("admins", "role", "role TEXT DEFAULT 'admin'")
    conn2 = get_conn()
    c2 = conn2.cursor()
    try:
        c2.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (22, 'Season 22', 0)")
        c2.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (23, 'Season 23', 1)")
    except Exception:
        pass
    try:
        c2.execute("SELECT id, group_name FROM teams")
        teams = c2.fetchall()
        for tid, grp in teams:
            c2.execute("INSERT OR IGNORE INTO team_history (team_id, season_id, group_name) VALUES (?, 23, ?)", (tid, grp))
    except Exception:
        pass
    conn2.commit()
    conn2.close()

def import_sqlite_db(upload_bytes):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
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

def get_substitutions_log():
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

def get_player_profile(player_id):
    conn = get_conn()
    info = pd.read_sql(
        "SELECT p.id, p.name, p.rank, t.tag as team FROM players p LEFT JOIN teams t ON p.default_team_id=t.id WHERE p.id=?",
        conn,
        params=(int(player_id),),
    )
    stats = pd.read_sql(
        "SELECT match_id, map_index, agent, acs, kills, deaths, assists, is_sub FROM match_stats_map WHERE player_id=?",
        conn,
        params=(int(player_id),),
    )
    league = pd.read_sql(
        "SELECT msm.player_id, msm.acs, msm.kills, msm.deaths, msm.assists FROM match_stats_map msm",
        conn,
    )
    rank_df = pd.read_sql(
        "SELECT p.id as player_id, p.rank, msm.acs, msm.kills, msm.deaths, msm.assists FROM match_stats_map msm JOIN players p ON msm.player_id=p.id",
        conn,
    )
    conn.close()
    if info.empty:
        return {}
    rank_val = info.iloc[0]['rank']
    games = stats['match_id'].nunique() if not stats.empty else 0
    avg_acs = float(stats['acs'].mean()) if not stats.empty else 0.0
    total_k = int(stats['kills'].sum()) if not stats.empty else 0
    total_d = int(stats['deaths'].sum()) if not stats.empty else 0
    total_a = int(stats['assists'].sum()) if not stats.empty else 0
    kd = (total_k / (total_d if total_d != 0 else 1)) if not stats.empty else 0.0
    same_rank = rank_df[rank_df['rank'] == rank_val] if not rank_df.empty else pd.DataFrame()
    sr_avg_acs = float(same_rank['acs'].mean()) if not same_rank.empty else 0.0
    sr_k = float(same_rank['kills'].mean()) if not same_rank.empty else 0.0
    sr_d = float(same_rank['deaths'].mean()) if not same_rank.empty else 0.0
    sr_a = float(same_rank['assists'].mean()) if not same_rank.empty else 0.0
    lg_avg_acs = float(league['acs'].mean()) if not league.empty else 0.0
    lg_k = float(league['kills'].mean()) if not league.empty else 0.0
    lg_d = float(league['deaths'].mean()) if not league.empty else 0.0
    lg_a = float(league['assists'].mean()) if not league.empty else 0.0
    trend = pd.DataFrame()
    if not stats.empty:
        conn2 = get_conn()
        mmeta = pd.read_sql("SELECT id, week FROM matches", conn2)
        conn2.close()
        agg = stats.groupby('match_id').agg({'acs':'mean','kills':'sum','deaths':'sum'}).reset_index()
        agg = agg.merge(mmeta, left_on='match_id', right_on='id', how='left')
        agg['kda'] = agg['kills'] / agg['deaths'].replace(0, 1)
        agg['label'] = agg.apply(lambda r: f"W{int(r['week'] or 0)}-M{int(r['match_id'])}", axis=1)
        agg = agg.rename(columns={'acs':'avg_acs'})
        trend = agg[['label','avg_acs','kda']]
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
        'sr_avg_acs': round(sr_avg_acs, 1),
        'sr_k': round(sr_k, 1),
        'sr_d': round(sr_d, 1),
        'sr_a': round(sr_a, 1),
        'lg_avg_acs': round(lg_avg_acs, 1),
        'lg_k': round(lg_k, 1),
        'lg_d': round(lg_d, 1),
        'lg_a': round(lg_a, 1),
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
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
    return salt, hashed

def verify_password(password, salt, stored_hash):
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

def ensure_seed_admins():
    su = get_secret("ADMIN_SEED_USER")
    sp = get_secret("ADMIN_SEED_PWD")
    sr = get_secret("ADMIN_SEED_ROLE", "admin")
    conn = get_conn()
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
    conn.commit()
    conn.close()

def authenticate(username, password):
    conn = get_conn()
    row = conn.execute("SELECT username, password_hash, salt FROM admins WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if not row:
        return False
    _, ph, salt = row
    return verify_password(password, salt, ph)

def init_match_stats_map_table():
    conn = get_conn()
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

def get_standings():
    conn = get_conn()
    try:
        teams_df = pd.read_sql_query("SELECT id, name, group_name, logo_path FROM teams", conn)
        matches_df = pd.read_sql_query("SELECT * FROM matches WHERE status='completed' AND (UPPER(format)='BO1' OR format IS NULL)", conn)
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
    exclude_ids = set(teams_df[teams_df['name'].isin(['FAT1','FAT2'])]['id'].tolist())
    if exclude_ids:
        teams_df = teams_df[~teams_df['id'].isin(exclude_ids)]
        matches_df = matches_df[~(matches_df['team1_id'].isin(exclude_ids) | matches_df['team2_id'].isin(exclude_ids))]
    stats = {}
    for _, row in teams_df.iterrows():
        stats[row['id']] = {'Wins': 0, 'Losses': 0, 'RD': 0, 'Points': 0, 'Played': 0}
    for _, m in matches_df.iterrows():
        t1, t2 = m['team1_id'], m['team2_id']
        s1, s2 = m['score_t1'], m['score_t2']
        if t1 in stats:
            stats[t1]['Played'] += 1
            stats[t1]['RD'] += (s1 - s2)
            if s1 > s2:
                stats[t1]['Wins'] += 1
            else:
                stats[t1]['Losses'] += 1
        if t2 in stats:
            stats[t2]['Played'] += 1
            stats[t2]['RD'] += (s2 - s1)
            if s2 > s1:
                stats[t2]['Wins'] += 1
            else:
                stats[t2]['Losses'] += 1
        if s1 > s2 and t1 in stats:
            stats[t1]['Points'] += 3
        elif s2 > s1 and t2 in stats:
            stats[t2]['Points'] += 3
    standings = []
    for tid, data in stats.items():
        row = teams_df[teams_df['id'] == tid].iloc[0].to_dict()
        row.update(data)
        standings.append(row)
    df = pd.DataFrame(standings)
    if df.empty:
        return df
    return df.sort_values(by=['Points', 'RD'], ascending=False)

def get_player_leaderboard():
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
            LEFT JOIN teams t ON msm.team_id = t.id
            GROUP BY p.id, p.name, t.tag
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

def get_week_matches(week):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT m.id, m.week, m.group_name, m.status, m.format, m.maps_played,
               t1.name as t1_name, t2.name as t2_name,
               m.score_t1, m.score_t2, t1.id as t1_id, t2.id as t2_id
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.week = ?
        ORDER BY m.id
        """,
        conn,
        params=(week,),
    )
    conn.close()
    return df

def get_match_maps(match_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT map_index, map_name, team1_rounds, team2_rounds, winner_id FROM match_maps WHERE match_id=? ORDER BY map_index",
        conn,
        params=(match_id,),
    )
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

st.set_page_config(page_title="S23 Portal", layout="wide")

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
.main .block-container {
padding-top: 180px !important;
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
flex-wrap: wrap;
}
.status-indicator {
padding: 0.8rem 1.5rem;
border-radius: 8px;
font-family: 'Orbitron';
font-size: 0.8rem;
letter-spacing: 2px;
text-align: center;
background: rgba(255, 255, 255, 0.03);
border: 1px solid rgba(255, 255, 255, 0.1);
min-width: 220px;
box-shadow: 0 4px 15px rgba(0,0,0,0.2);
transition: all 0.3s ease;
}
.status-indicator:hover {
background: rgba(255, 255, 255, 0.05);
transform: translateY(-2px);
}
.status-online { color: #00ff88; border-color: rgba(0, 255, 136, 0.3); background: rgba(0, 255, 136, 0.08); text-shadow: 0 0 10px rgba(0, 255, 136, 0.3); }
.status-offline { color: var(--primary-red); border-color: rgba(255, 70, 85, 0.3); background: rgba(255, 70, 85, 0.08); text-shadow: 0 0 10px rgba(255, 70, 85, 0.3); }
.portal-options {
display: grid;
grid-template-columns: repeat(3, 1fr);
gap: 2.5rem;
width: 100%;
max-width: 1100px;
margin-top: 1rem;
}
.portal-card-wrapper {
background: var(--card-bg);
border: 1px solid rgba(63, 209, 255, 0.15);
padding: 0;
border-radius: 16px;
transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
position: relative;
overflow: hidden;
display: flex;
flex-direction: column;
height: 100%;
}
.portal-card-wrapper:hover:not(.disabled) {
transform: translateY(-12px);
border-color: var(--primary-blue);
box-shadow: 0 20px 50px rgba(63, 209, 255, 0.25);
}
.portal-card-content {
padding: 2.5rem 2rem;
text-align: center;
flex-grow: 1;
}
.portal-card-footer {
padding: 1.5rem;
background: rgba(0,0,0,0.2);
border-top: 1px solid rgba(255,255,255,0.05);
}
.portal-card-wrapper.disabled {
opacity: 0.5;
cursor: not-allowed;
filter: grayscale(0.8);
}
.portal-card-wrapper.disabled:hover::after {
content: "COMING SOON";
position: absolute;
top: 0;
left: 0;
right: 0;
bottom: 0;
background: rgba(15, 25, 35, 0.92);
display: flex;
align-items: center;
justify-content: center;
color: var(--primary-red);
font-family: 'Orbitron';
font-weight: bold;
font-size: 1rem;
letter-spacing: 2px;
z-index: 10;
}
[data-testid='stSidebarNav'] {display: none;}
[data-testid='stHeader'] {display: none;}
h1, h2, h3 {
font-family: 'Orbitron', sans-serif !important;
text-transform: uppercase;
letter-spacing: 2px;
font-weight: 700 !important;
}
.main-header {
color: var(--primary-blue);
text-shadow: 0 0 20px rgba(63, 209, 255, 0.3);
border-left: 5px solid var(--primary-red);
padding-left: 15px;
margin-top: 0.5rem !important;
margin-bottom: 2.5rem !important;
font-size: 3rem;
animation: fadeIn 0.8s ease-out;
}
h2, h3 { color: var(--primary-blue); }
@keyframes fadeIn {
from { opacity: 0; transform: translateY(5px); }
to { opacity: 1; transform: translateY(0); }
}
.stMarkdown, .stDataFrame, .stPlotlyChart, .element-container {
animation: fadeIn 0.4s ease-out forwards;
}
.nav-wrapper {
position: fixed;
top: 0;
left: 0;
right: 0;
height: var(--nav-height);
background: rgba(15, 25, 35, 0.98);
backdrop-filter: blur(20px);
border-bottom: 1px solid rgba(63, 209, 255, 0.2);
display: flex;
align-items: center;
padding: 0 2rem;
z-index: 9999;
justify-content: flex-start;
gap: 2rem;
box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
}
.nav-logo {
font-family: 'Orbitron';
color: var(--primary-blue);
font-size: 1.2rem;
font-weight: bold;
letter-spacing: 2px;
white-space: nowrap;
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
div[data-testid="column"] button.active-nav {
border-bottom: 2px solid var(--primary-red) !important;
color: white !important;
background: rgba(255, 255, 255, 0.05) !important;
border-radius: 4px 4px 0 0 !important;
}
/* Exit Button Style */
.exit-btn button {
border-color: var(--primary-red) !important;
color: var(--primary-red) !important;
}
.exit-btn button:hover {
background: rgba(255, 70, 85, 0.1) !important;
color: white !important;
}
</style>""", unsafe_allow_html=True)

ensure_base_schema()
init_admin_table()
init_match_stats_map_table()
ensure_upgrade_schema()
ensure_seed_admins()

# App Mode Logic
if 'app_mode' not in st.session_state:
    st.session_state['app_mode'] = 'portal'

# Use a placeholder to clear the screen during transitions
main_container = st.empty()

if st.session_state['app_mode'] == 'portal':
    with main_container.container():
        st.markdown("""<div class="portal-container">
<h1 style="color: var(--primary-blue); font-size: 3.5rem; text-shadow: 0 0 30px rgba(63, 209, 255, 0.4); margin-bottom: 0;">VALORANT S23 PORTAL</h1>
<p style="color: var(--text-dim); font-size: 0.9rem; letter-spacing: 5px; margin-bottom: 3rem; text-transform: uppercase;">System Status & Access Terminal</p>
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
        with st.form("admin_login_main"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            tok = st.text_input("Admin Token", type="password")
            if st.form_submit_button("LOGIN TO ADMIN PANEL", use_container_width=True):
                env_tok = get_secret("ADMIN_LOGIN_TOKEN", "")
                if authenticate(u, p) and hmac.compare_digest(tok or "", env_tok):
                    st.session_state['is_admin'] = True
                    st.session_state['username'] = u
                    st.session_state['page'] = "Admin Panel"
                    st.success("Access Granted")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
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
    pages.append("Admin Panel")

# Top Navigation Bar
st.markdown('<div class="nav-wrapper"><div class="nav-logo">VALORANT S23 • PORTAL</div></div>', unsafe_allow_html=True)

# Navigation Layout
nav_container = st.container()
with nav_container:
    # Use a specific ratio to keep the EXIT button small and others balanced
    cols = st.columns([0.8] + [1] * len(pages))
    
    with cols[0]:
        st.markdown('<div class="exit-btn">', unsafe_allow_html=True)
        if st.button("🏠 EXIT", key="exit_portal", use_container_width=True):
            st.session_state['app_mode'] = 'portal'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    for i, p in enumerate(pages):
        with cols[i+1]:
            is_active = st.session_state['page'] == p
            if st.button(p, key=f"nav_{p}", use_container_width=True, 
                         type="primary" if is_active else "secondary"):
                st.session_state['page'] = p
                st.rerun()
            
            if is_active:
                st.markdown('<div style="height: 3px; background: var(--primary-red); margin-top: -8px; box-shadow: 0 0 10px var(--primary-red); border-radius: 2px;"></div>', unsafe_allow_html=True)

page = st.session_state['page']

if page == "Overview & Standings":
    st.markdown('<h1 class="main-header">OVERVIEW & STANDINGS</h1>', unsafe_allow_html=True)
    
    df = get_standings()
    if not df.empty:
        conn = get_conn()
        hist = pd.read_sql_query(
            "SELECT team_id, COUNT(DISTINCT season_id) as season_count FROM team_history GROUP BY team_id",
            conn,
        )
        conn.close()
        df = df.merge(hist, left_on='id', right_on='team_id', how='left')
        df['season_count'] = df['season_count'].fillna(1).astype(int)
        df['logo_display'] = df['logo_path'].apply(lambda x: x if x and os.path.exists(x) else None)
        
        groups = sorted(df['group_name'].unique())
        
        for grp in groups:
            st.markdown(f'<h2 style="color: var(--primary-blue); font-family: \'Orbitron\'; border-left: 4px solid var(--primary-blue); padding-left: 15px; margin: 2rem 0 1rem 0;">GROUP {grp}</h2>', unsafe_allow_html=True)
            
            grp_df = df[df['group_name'] == grp]
            
            # Team Cards Grid
            t_cols = st.columns(min(len(grp_df), 3))
            for idx, (_, row) in enumerate(grp_df.iterrows()):
                with t_cols[idx % 3]:
                    logo_html = ""
                    if row['logo_display']:
                        with open(row['logo_display'], "rb") as f:
                            logo_html = f"<img src='data:image/png;base64,{base64.b64encode(f.read()).decode()}' width='40' style='border-radius: 4px;'/>"
                    else:
                        logo_html = "<div style='width:40px;height:40px;background:rgba(255,255,255,0.05);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);'>?</div>"
                    
                    st.markdown(f"""
                        <div class="custom-card" style="height: 100%;">
                            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
                                {logo_html}
                                <div style="font-weight: bold; color: var(--primary-blue); font-size: 1rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{row['name']}</div>
                            </div>
                            <div style="display: flex; justify-content: space-between; color: var(--text-dim); font-size: 0.8rem;">
                                <span>WINS: <span style="color: var(--text-main); font-family: 'Orbitron';">{row['Wins']}</span></span>
                                <span>PTS: <span style="color: var(--primary-blue); font-family: 'Orbitron';">{row['Points']}</span></span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("Roster"):
                        conn_r = get_conn()
                        roster = pd.read_sql_query("SELECT name, rank FROM players WHERE default_team_id=? ORDER BY name", conn_r, params=(int(row['id']),))
                        conn_r.close()
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
            for _, m in sched.iterrows():
                st.markdown(f"""
                <div class="custom-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; text-align: right; font-weight: bold; color: var(--primary-blue);">{m['t1_name']}</div>
                        <div style="margin: 0 20px; color: var(--text-dim); font-family: 'Orbitron';">VS</div>
                        <div style="flex: 1; text-align: left; font-weight: bold; color: var(--primary-red);">{m['t2_name']}</div>
                    </div>
                    <div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 10px;">{m['format']} • {m['group_name']}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("### Completed")
        comp = df[df['status'] == 'completed']
        for _, m in comp.iterrows():
            with st.container():
                winner_color_1 = "var(--primary-blue)" if m['score_t1'] > m['score_t2'] else "var(--text-main)"
                winner_color_2 = "var(--primary-red)" if m['score_t2'] > m['score_t1'] else "var(--text-main)"
                
                st.markdown(f"""
                <div class="custom-card" style="border-left: 4px solid {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--primary-red)'};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; text-align: right;">
                            <span style="font-weight: bold; color: {winner_color_1};">{m['t1_name']}</span>
                            <span style="font-size: 1.5rem; margin-left: 10px; font-family: 'Orbitron';">{m['score_t1']}</span>
                        </div>
                        <div style="margin: 0 20px; color: var(--text-dim); font-family: 'Orbitron';">-</div>
                        <div style="flex: 1; text-align: left;">
                            <span style="font-size: 1.5rem; margin-right: 10px; font-family: 'Orbitron';">{m['score_t2']}</span>
                            <span style="font-weight: bold; color: {winner_color_2};">{m['t2_name']}</span>
                        </div>
                    </div>
                    <div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 10px;">{m['format']} • {m['group_name']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("Match Details"):
                    maps_df = get_match_maps(int(m['id']))
                    if maps_df.empty:
                        st.caption("No map details")
                    else:
                        md = maps_df.copy()
                        md['Winner'] = md.apply(lambda r: m['t1_name'] if r['winner_id'] == m['t1_id'] else (m['t2_name'] if r['winner_id'] == m['t2_id'] else ''), axis=1)
                        md = md.rename(columns={
                            'map_index': 'Map',
                            'map_name': 'Name',
                            'team1_rounds': m['t1_name'],
                            'team2_rounds': m['t2_name'],
                        })
                        md['Map'] = md['Map'] + 1
                        st.dataframe(md[['Map', 'Name', m['t1_name'], m['t2_name'], 'Winner']], hide_index=True, use_container_width=True)

elif page == "Match Summary":
    st.markdown('<h1 class="main-header">MATCH SUMMARY</h1>', unsafe_allow_html=True)
    
    week = st.sidebar.selectbox("Week", [1, 2, 3, 4, 5], index=0, key="wk_sum")
    df = get_week_matches(week)
    
    if df.empty:
        st.info("No matches for this week.")
    else:
        opts = df.apply(lambda r: f"{r['t1_name']} vs {r['t2_name']} ({r['group_name']})", axis=1).tolist()
        sel = st.selectbox("Select Match", list(range(len(opts))), format_func=lambda i: opts[i])
        m = df.iloc[sel]
        
        # Match Score Card
        st.markdown(f"""
            <div class="custom-card" style="margin-bottom: 2rem; border-bottom: 4px solid {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--primary-red)'};">
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
                    <div style="flex: 1; text-align: right;">
                        <h2 style="margin: 0; color: {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--text-main)'}; font-family: 'Orbitron';">{m['t1_name']}</h2>
                    </div>
                    <div style="margin: 0 30px; display: flex; align-items: center; gap: 15px;">
                        <span style="font-size: 3rem; font-family: 'Orbitron'; color: var(--text-main);">{m['score_t1']}</span>
                        <span style="font-size: 1.5rem; color: var(--text-dim); font-family: 'Orbitron';">:</span>
                        <span style="font-size: 3rem; font-family: 'Orbitron'; color: var(--text-main);">{m['score_t2']}</span>
                    </div>
                    <div style="flex: 1; text-align: left;">
                        <h2 style="margin: 0; color: {'var(--primary-red)' if m['score_t2'] > m['score_t1'] else 'var(--text-main)'}; font-family: 'Orbitron';">{m['t2_name']}</h2>
                    </div>
                </div>
                <div style="text-align: center; color: var(--text-dim); font-size: 0.9rem; margin-top: 10px; letter-spacing: 2px;">{m['format'].upper()} • {m['group_name'].upper()}</div>
            </div>
        """, unsafe_allow_html=True)
        
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
            st.markdown(f"""
                <div class="custom-card" style="background: rgba(255,255,255,0.02); margin-bottom: 20px;">
                    <div style="display: flex; justify-content: center; align-items: center; gap: 40px;">
                        <div style="text-align: center;">
                            <div style="color: var(--text-dim); font-size: 0.8rem; margin-bottom: 5px;">{m['t1_name']}</div>
                            <div style="font-size: 2rem; font-family: 'Orbitron'; color: {'var(--primary-blue)' if curr_map['team1_rounds'] > curr_map['team2_rounds'] else 'var(--text-main)'};">{curr_map['team1_rounds']}</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-family: 'Orbitron'; color: var(--primary-blue); font-size: 1.2rem;">{curr_map['map_name'].upper()}</div>
                            <div style="color: var(--text-dim); font-size: 0.7rem;">WINNER: {m['t1_name'] if curr_map['winner_id'] == m['t1_id'] else m['t2_name']}</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="color: var(--text-dim); font-size: 0.8rem; margin-bottom: 5px;">{m['t2_name']}</div>
                            <div style="font-size: 2rem; font-family: 'Orbitron'; color: {'var(--primary-red)' if curr_map['team2_rounds'] > curr_map['team1_rounds'] else 'var(--text-main)'};">{curr_map['team2_rounds']}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Scoreboards
            conn_s = get_conn()
            s1 = pd.read_sql("SELECT p.name, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub FROM match_stats_map ms JOIN players p ON ms.player_id=p.id WHERE ms.match_id=? AND ms.map_index=? AND ms.team_id=?", conn_s, params=(int(m['id']), selected_map_idx, int(m['t1_id'])))
            s2 = pd.read_sql("SELECT p.name, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub FROM match_stats_map ms JOIN players p ON ms.player_id=p.id WHERE ms.match_id=? AND ms.map_index=? AND ms.team_id=?", conn_s, params=(int(m['id']), selected_map_idx, int(m['t2_id'])))
            conn_s.close()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<h4 style="color: var(--primary-blue); font-family: \'Orbitron\';">{m["t1_name"]} Scoreboard</h4>', unsafe_allow_html=True)
                if s1.empty:
                    st.info("No scoreboard data")
                else:
                    st.dataframe(s1.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)
            
            with c2:
                st.markdown(f'<h4 style="color: var(--primary-red); font-family: \'Orbitron\';">{m["t2_name"]} Scoreboard</h4>', unsafe_allow_html=True)
                if s2.empty:
                    st.info("No scoreboard data")
                else:
                    st.dataframe(s2.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)

elif page == "Match Predictor":
    st.markdown('<h1 class="main-header">MATCH PREDICTOR</h1>', unsafe_allow_html=True)
    st.write("Predict the outcome of a match based on team history and stats.")
    
    conn = get_conn()
    teams_df = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn)
    matches_df = pd.read_sql("SELECT * FROM matches WHERE status='completed'", conn)
    conn.close()
    
    tnames = teams_df['name'].tolist()
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
                played = matches_df[(matches_df['team1_id']==tid) | (matches_df['team2_id']==tid)]
                if played.empty:
                    return {'win_rate': 0.0, 'avg_score': 0.0, 'games': 0}
                wins = played[played['winner_id'] == tid].shape[0]
                total = played.shape[0]
                
                # Calculate avg score (rounds won)
                scores = []
                for _, r in played.iterrows():
                    if r['team1_id'] == tid:
                        scores.append(r['score_t1'])
                    else:
                        scores.append(r['score_t2'])
                avg_score = sum(scores)/len(scores) if scores else 0
                
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
            
            ml_pred = None
            try:
                from sklearn.ensemble import RandomForestClassifier
                # Placeholder for future ML implementation
                pass
            except ImportError:
                pass
                
            total = score1 + score2
            if total == 0:
                prob1 = 50.0
                prob2 = 50.0
            else:
                prob1 = (score1 / total) * 100
                prob2 = (score2 / total) * 100
                
            winner = t1_name if prob1 > prob2 else t2_name
            conf = max(prob1, prob2)
            
            st.markdown(f"""
            <div class="custom-card" style="text-align: center; border-top: 4px solid { 'var(--primary-blue)' if winner == t1_name else 'var(--primary-red)' };">
                <h2 style="margin: 0; color: { 'var(--primary-blue)' if winner == t1_name else 'var(--primary-red)' };">PREDICTION: {winner}</h2>
                <div style="font-size: 3rem; font-family: 'Orbitron'; margin: 10px 0;">{conf:.1f}%</div>
                <div style="color: var(--text-dim);">CONFIDENCE LEVEL</div>
            </div>
            """, unsafe_allow_html=True)

            # Probability Bar
            st.markdown(f"""
            <div style="width: 100%; background: rgba(255,255,255,0.05); height: 20px; border-radius: 10px; overflow: hidden; display: flex; margin: 20px 0;">
                <div style="width: {prob1}%; background: var(--primary-blue); height: 100%; transition: width 1s ease-in-out;"></div>
                <div style="width: {prob2}%; background: var(--primary-red); height: 100%; transition: width 1s ease-in-out;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-family: 'Orbitron'; font-size: 0.8rem;">
                <div style="color: var(--primary-blue);">{t1_name} ({prob1:.1f}%)</div>
                <div style="color: var(--primary-red);">{t2_name} ({prob2:.1f}%)</div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="custom-card">
                    <h3 style="color: var(--primary-blue); margin-top: 0;">{t1_name} Analysis</h3>
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
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="custom-card">
                    <h3 style="color: var(--primary-red); margin-top: 0;">{t2_name} Analysis</h3>
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
                </div>
                """, unsafe_allow_html=True)

elif page == "Player Leaderboard":
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
        
        for i, (_, row) in enumerate(top3.iterrows()):
            with cols[i]:
                st.markdown(f"""
                <div class="custom-card" style="text-align: center; border-bottom: 3px solid {colors[i]};">
                    <div style="font-size: 2rem;">{medals[i]}</div>
                    <div style="font-weight: bold; color: var(--primary-blue); font-size: 1.2rem; margin: 10px 0;">{row['name']}</div>
                    <div style="color: var(--text-dim); font-size: 0.8rem;">{row['team']}</div>
                    <div style="font-family: 'Orbitron'; font-size: 1.5rem; color: var(--text-main); margin-top: 10px;">{row['avg_acs']}</div>
                    <div style="font-size: 0.6rem; color: var(--text-dim);">AVG ACS</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        names = df['name'].tolist()
        sel = st.selectbox("Detailed Profile", ["Select a player..."] + names)
        if sel != "Select a player...":
            conn_pp = get_conn()
            pid_row = pd.read_sql("SELECT id FROM players WHERE name=?", conn_pp, params=(sel,))
            conn_pp.close()
            if not pid_row.empty:
                prof = get_player_profile(int(pid_row.iloc[0]['id']))
                if prof:
                    st.markdown(f"""
                    <div style="margin-top: 2rem; padding: 1rem; border-left: 5px solid var(--primary-blue); background: rgba(63, 209, 255, 0.05);">
                        <h2 style="margin: 0;">{prof['info'].get('name')}</h2>
                        <div style="color: var(--text-dim); font-family: 'Orbitron';">{prof['info'].get('team') or 'No Team'} • {prof['info'].get('rank') or 'Unranked'}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
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
                        sidf = pd.DataFrame({
                            'Role': ['Starter','Sub'],
                            'ACS': [sid['starter_acs'], sid['sub_acs']],
                            'KDA': [sid['starter_kda'], sid['sub_kda']],
                        })
                        st.caption("Substitution impact")
                        fig_sub = px.bar(sidf, x='Role', y=['ACS', 'KDA'], barmode='group',
                                         color_discrete_map={'ACS': '#3FD1FF', 'KDA': '#FF4655'})
                        st.plotly_chart(apply_plotly_theme(fig_sub), use_container_width=True)
                    if not prof['maps'].empty:
                        st.caption("Maps played")
                        st.dataframe(prof['maps'][['match_id','map_index','agent','acs','kills','deaths','assists','is_sub']], hide_index=True, use_container_width=True)

elif page == "Players Directory":
    st.markdown('<h1 class="main-header">PLAYERS DIRECTORY</h1>', unsafe_allow_html=True)
    
    conn = get_conn()
    try:
        players_df = pd.read_sql(
            """
            SELECT p.id, p.name, p.riot_id, p.rank, t.name AS team
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            ORDER BY p.name
            """,
            conn,
        )
    except Exception:
        players_df = pd.DataFrame(columns=['id','name','riot_id','rank','team'])
    conn.close()
    
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
        out = out[out.apply(lambda r: s in str(r['name']).lower() or s in str(r['riot_id']).lower(), axis=1)]
    
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
    st.markdown('<h1 class="main-header">TEAMS</h1>', unsafe_allow_html=True)
    
    conn = get_conn()
    teams = pd.read_sql("SELECT id, name, tag, group_name, logo_path FROM teams ORDER BY name", conn)
    all_players = pd.read_sql("SELECT id, name, default_team_id FROM players ORDER BY name", conn)
    conn.close()
    
    groups = ["All"] + sorted(teams['group_name'].dropna().unique().tolist())
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        g = st.selectbox("Filter by Group", groups)
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    show = teams if g == "All" else teams[teams['group_name'] == g]
    for _, row in show.iterrows():
        with st.container():
            # Team Header Card
            st.markdown(f"""
                <div class="custom-card" style="margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <div style="flex-shrink: 0;">
                            {"<img src='data:image/png;base64," + base64.b64encode(open(row['logo_path'], "rb").read()).decode() + "' width='60'/>" if row['logo_path'] and os.path.exists(row['logo_path']) else "<div style='width:60px;height:60px;background:rgba(255,255,255,0.05);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);'>?</div>"}
                        </div>
                        <div>
                            <h3 style="margin: 0; color: var(--primary-blue); font-family: 'Orbitron';">{row['name']} <span style="color: var(--text-dim); font-size: 0.9rem;">[{row['tag'] or ''}]</span></h3>
                            <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Group {row['group_name']}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Manage Roster & Details"):
                conn_r = get_conn()
                roster = pd.read_sql_query(
                    "SELECT id, name, rank FROM players WHERE default_team_id=? ORDER BY name",
                    conn_r,
                    params=(int(row['id']),),
                )
                conn_r.close()
                
                if roster.empty:
                    st.info("No players yet")
                else:
                    st.dataframe(roster[['name','rank']], hide_index=True, use_container_width=True)
                
                if st.session_state.get('is_admin'):
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption("Edit Team Details")
                        with st.form(f"edit_team_{row['id']}"):
                            new_name = st.text_input("Name", value=row['name'])
                            new_tag = st.text_input("Tag", value=row['tag'] or "")
                            new_group = st.text_input("Group", value=row['group_name'] or "")
                            new_logo = st.text_input("Logo Path", value=row['logo_path'] or "")
                            if st.form_submit_button("Update Team"):
                                conn_u = get_conn()
                                conn_u.execute("UPDATE teams SET name=?, tag=?, group_name=?, logo_path=? WHERE id=?", (new_name, new_tag or None, new_group or None, new_logo or None, int(row['id'])))
                                conn_u.commit()
                                conn_u.close()
                                st.success("Team updated")
                                st.rerun()
                    
                    with col2:
                        st.caption("Roster Management")
                        # Add player
                        unassigned = all_players[all_players['default_team_id'].isna()]
                        add_sel = st.selectbox(f"Add Player", [""] + unassigned['name'].tolist(), key=f"add_{row['id']}")
                        if add_sel:
                            pid = int(all_players[all_players['name'] == add_sel].iloc[0]['id'])
                            conn_a = get_conn()
                            conn_a.execute("UPDATE players SET default_team_id=? WHERE id=?", (int(row['id']), pid))
                            conn_a.commit()
                            conn_a.close()
                            st.success("Player added")
                            st.rerun()
                        
                        # Remove player
                        if not roster.empty:
                            rem_sel = st.selectbox(f"Remove Player", [""] + roster['name'].tolist(), key=f"rem_{row['id']}")
                            if rem_sel:
                                pid = int(roster[roster['name'] == rem_sel].iloc[0]['id'])
                                conn_d = get_conn()
                                conn_d.execute("UPDATE players SET default_team_id=NULL WHERE id=?", (pid,))
                                conn_d.commit()
                                conn_d.close()
                                st.success("Player removed")
                                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

elif page == "Admin Panel":
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
        conn = get_conn()
        weeks_df = pd.read_sql_query("SELECT DISTINCT week FROM matches ORDER BY week", conn)
        conn.close()
        wk_list = weeks_df['week'].tolist() if not weeks_df.empty else []
        wk = st.selectbox("Week", wk_list) if wk_list else None
        if wk is None:
            st.info("No matches yet")
        else:
            dfm = get_week_matches(wk)
            if dfm.empty:
                st.info("No matches for this week")
            else:
                match_opts = dfm.apply(lambda r: f"ID {r['id']}: {r['t1_name']} vs {r['t2_name']} ({r['group_name']})", axis=1).tolist()
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
                        nsel = st.selectbox(f"Name {i+1}", maps_catalog, index=(maps_catalog.index(pre_name) if pre_name in maps_catalog else 0), key=f"mname_{i}")
                        t1r = st.number_input(f"{m['t1_name']} rounds", min_value=0, value=pre_t1, key=f"t1r_{i}")
                        t2r = st.number_input(f"{m['t2_name']} rounds", min_value=0, value=pre_t2, key=f"t2r_{i}")
                        wsel = st.selectbox("Winner", ["", m['t1_name'], m['t2_name']], index=(1 if pre_win==int(m['t1_id']) else (2 if pre_win==int(m['t2_id']) else 0)), key=f"win_{i}")
                        wid = None
                        if wsel == m['t1_name']:
                            wid = int(m['t1_id'])
                        elif wsel == m['t2_name']:
                            wid = int(m['t2_id'])
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
                        winner_id = int(m['t1_id'])
                    elif s2 > s1:
                        winner_id = int(m['t2_id'])
                    conn_u.execute("UPDATE matches SET score_t1=?, score_t2=?, winner_id=?, status=?, format=?, maps_played=? WHERE id=?", (int(s1), int(s2), winner_id, 'completed', fmt, int(played), int(m['id'])))
                    conn_u.commit()
                    conn_u.close()
                    st.success("Saved match and maps")
                    st.rerun()

                st.divider()
                st.subheader("Per-Map Scoreboard")
                map_choice = st.selectbox("Select Map", list(range(1, max_maps+1)), index=0)
                map_idx = map_choice - 1
                conn_all0 = get_conn()
                all_df0 = pd.read_sql("SELECT id, name, riot_id FROM players ORDER BY name", conn_all0)
                conn_all0.close()
                name_to_riot = dict(zip(all_df0['name'].astype(str), all_df0['riot_id'].astype(str)))
                
                # Match ID input for automatic pre-filling from folder
                match_id_input = st.text_input("Enter Match ID to load JSON data", key=f"mid_{m['id']}_{map_idx}")
                
                if match_id_input:
                    json_filename = f"match_{match_id_input}.json"
                    json_path = os.path.join("matches", json_filename)
                    
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, 'r', encoding='utf-8') as f:
                                jsdata = json.load(f)
                            json_suggestions = {}
                            segments = jsdata.get("data", {}).get("segments", [])
                            for seg in segments:
                                if seg.get("type") == "player-summary":
                                    rid = seg.get("metadata", {}).get("platformInfo", {}).get("platformUserIdentifier")
                                    if rid:
                                        rid = str(rid).strip()
                                    agent = seg.get("metadata", {}).get("agentName")
                                    st_map = seg.get("stats", {})
                                    # In Tracker JSON, scorePerRound value is usually ACS
                                    acs = st_map.get("scorePerRound", {}).get("value", 0)
                                    k = st_map.get("kills", {}).get("value", 0)
                                    d = st_map.get("deaths", {}).get("value", 0)
                                    a = st_map.get("assists", {}).get("value", 0)
                                    if rid:
                                        json_suggestions[rid] = {
                                            'acs': int(acs) if acs is not None else 0, 
                                            'k': int(k) if k is not None else 0, 
                                            'd': int(d) if d is not None else 0, 
                                            'a': int(a) if a is not None else 0, 
                                            'agent': agent,
                                            'conf': 100.0
                                        }
                            st.session_state[f"ocr_{m['id']}_{map_idx}"] = json_suggestions
                            st.success(f"JSON file '{json_filename}' loaded and parsed.")
                        except Exception as e:
                            st.error(f"JSON Error: {str(e)}")
                    else:
                        st.warning(f"File '{json_filename}' not found in 'matches' folder.")

                for team_key, team_id, team_name in [("t1", int(m['t1_id']), m['t1_name']), ("t2", int(m['t2_id']), m['t2_name'])]:
                    st.caption(f"{team_name} players")
                    conn_p = get_conn()
                    roster_df = pd.read_sql("SELECT id, name, riot_id FROM players WHERE default_team_id=? ORDER BY name", conn_p, params=(team_id,))
                    agents_df = pd.read_sql("SELECT name FROM agents ORDER BY name", conn_p)
                    existing = pd.read_sql("SELECT * FROM match_stats_map WHERE match_id=? AND map_index=? AND team_id=?", conn_p, params=(int(m['id']), map_idx, team_id))
                    conn_p.close()
                    conn_all = get_conn()
                    all_df = pd.read_sql("SELECT id, name, riot_id FROM players ORDER BY name", conn_all)
                    conn_all.close()
                    roster_list = roster_df.apply(lambda r: (f"{str(r['riot_id'])} ({r['name']})" if pd.notna(r['riot_id']) and str(r['riot_id']).strip() else r['name']), axis=1).tolist()
                    roster_map = dict(zip(roster_list, roster_df['id']))
                    global_list = all_df.apply(lambda r: (f"{str(r['riot_id'])} ({r['name']})" if pd.notna(r['riot_id']) and str(r['riot_id']).strip() else r['name']), axis=1).tolist()
                    global_map = dict(zip(global_list, all_df['id']))
                    # Improved label_to_riot to handle NaN correctly
                    label_to_riot = {label: str(rid).strip() for label, rid in zip(global_list, all_df['riot_id']) if pd.notna(rid) and str(rid).strip()}
                    riot_to_label = {v: k for k, v in label_to_riot.items()}
                    agents_list = agents_df['name'].tolist()
                    rows = []
                    
                    sug = st.session_state.get(f"ocr_{m['id']}_{map_idx}", {})
                    
                    if not existing.empty:
                        for _, r in existing.iterrows():
                            pname = ""
                            if r['player_id']:
                                rp = get_conn().execute("SELECT name, riot_id FROM players WHERE id=?", (r['player_id'],)).fetchone()
                                if rp:
                                    pname = (f"{str(rp[1])} ({rp[0]})" if rp[1] else rp[0])
                            sfname = ""
                            if r['subbed_for_id']:
                                sp = get_conn().execute("SELECT name, riot_id FROM players WHERE id=?", (r['subbed_for_id'],)).fetchone()
                                if sp:
                                    sfname = (f"{str(sp[1])} ({sp[0]})" if sp[1] else sp[0])
                            rows.append({
                                'player': pname,
                                'is_sub': bool(r['is_sub']),
                                'subbed_for': sfname or (roster_list[0] if roster_list else ""),
                                'agent': r['agent'] or (agents_list[0] if agents_list else ""),
                                'acs': int(r['acs'] or 0),
                                'k': int(r['kills'] or 0),
                                'd': int(r['deaths'] or 0),
                                'a': int(r['assists'] or 0),
                            })
                    else:
                        # For new maps, try to match roster players to suggestions
                        for i in range(min(5, max(1,len(roster_list)))):
                            r_label = roster_list[i] if i < len(roster_list) else (global_list[0] if global_list else "")
                            r_rid = label_to_riot.get(r_label)
                            
                            row_data = {
                                'player': r_label,
                                'is_sub': False,
                                'subbed_for': roster_list[i] if i < len(roster_list) else "",
                                'agent': agents_list[0] if agents_list else "",
                                'acs': 0, 'k': 0, 'd': 0, 'a': 0
                            }
                            
                            # If we have a suggestion for this roster player, use it
                            if r_rid and r_rid in sug:
                                s = sug[r_rid]
                                row_data.update({
                                    'acs': s['acs'], 
                                    'k': s['k'], 
                                    'd': s['d'], 
                                    'a': s['a'],
                                    'agent': s.get('agent') or row_data['agent']
                                })
                                
                            rows.append(row_data)

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

                            psel = c1.selectbox(f"P{i}", global_list + [""], index=p_idx, label_visibility="collapsed")
                            is_sub = c2.checkbox(f"S{i}", value=rowd['is_sub'], label_visibility="collapsed")
                            sf_sel = c3.selectbox(f"SF{i}", roster_list + [""], index=(roster_list.index(rowd['subbed_for']) if rowd['subbed_for'] in roster_list else (0 if roster_list else 0)), label_visibility="collapsed")
                            ag_sel = c4.selectbox(f"Ag{i}", agents_list + [""], index=(agents_list.index(rowd['agent']) if rowd['agent'] in agents_list else (0 if agents_list else 0)), label_visibility="collapsed")
                            
                            rid_psel = label_to_riot.get(psel)
                            
                            # Final fallback: if selectbox changed, try to get suggestion again
                            current_sug = sug.get(rid_psel, {}) if rid_psel else {}
                            
                            val_acs = current_sug.get('acs', rowd['acs'])
                            val_k = current_sug.get('k', rowd['k'])
                            val_d = current_sug.get('d', rowd['d'])
                            val_a = current_sug.get('a', rowd['a'])
                            val_conf = current_sug.get('conf', '-')
                            
                            acs = c5.number_input(f"ACS{i}", min_value=0, value=int(val_acs), label_visibility="collapsed")
                            k = c6.number_input(f"K{i}", min_value=0, value=int(val_k), label_visibility="collapsed")
                            d = c7.number_input(f"D{i}", min_value=0, value=int(val_d), label_visibility="collapsed")
                            a = c8.number_input(f"A{i}", min_value=0, value=int(val_a), label_visibility="collapsed")
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
                            for e in entries:
                                if e['player_id']:
                                    conn_s.execute(
                                        "INSERT INTO match_stats_map (match_id, map_index, team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (int(m['id']), map_idx, team_id, e['player_id'], e['is_sub'], e['subbed_for_id'], e['agent'], e['acs'], e['kills'], e['deaths'], e['assists'])
                                    )
                            conn_s.commit()
                            conn_s.close()
                            st.success("Scoreboard saved")
                            st.rerun()

        st.divider()
        st.subheader("Players Admin")
        conn_pa = get_conn()
        players_df = pd.read_sql(
            """
            SELECT p.id, p.name, p.riot_id, p.rank, t.name AS team
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            ORDER BY p.name
            """,
            conn_pa
        )
        teams_list = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn_pa)
        conn_pa.close()
        team_names = teams_list['name'].tolist()
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
                    dtid_new = team_map.get(tmn_new) if tmn_new else None
                    conn_add.execute("INSERT INTO players (name, riot_id, rank, default_team_id) VALUES (?, ?, ?, ?)", (nm_new, rid_new, rk_new, dtid_new))
                    conn_add.commit()
                    conn_add.close()
                    st.success("Player added")
                    st.rerun()
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
            fdf = fdf[fdf.apply(lambda r: s in str(r['name']).lower() or s in str(r['riot_id']).lower(), axis=1)]
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
            for _, row in edited.iterrows():
                pid = row.get('id')
                if pd.isna(pid):
                    if st.session_state.get('role', 'admin') == 'dev':
                        nm = row.get('name')
                        rk = row.get('rank') or "Unranked"
                        tmn = row.get('team') or None
                        dtid = team_map.get(tmn) if tmn else None
                        conn_up.execute("INSERT INTO players (name, riot_id, rank, default_team_id) VALUES (?, ?, ?, ?)", (nm, row.get('riot_id'), rk, dtid))
                else:
                    nm = row.get('name')
                    rk = row.get('rank') or "Unranked"
                    tmn = (row.get('team') if pd.notna(row.get('team')) else None)
                    dtid = team_map.get(tmn) if tmn else None
                    conn_up.execute("UPDATE players SET name=?, riot_id=?, rank=?, default_team_id=? WHERE id=?", (nm, row.get('riot_id'), rk, dtid, int(pid)))
            conn_up.commit()
            conn_up.close()
            st.success("Players saved")
            st.rerun()

        st.divider()
        st.subheader("Schedule Manager")
        conn_sm = get_conn()
        teams_df = pd.read_sql("SELECT id, name, group_name FROM teams ORDER BY name", conn_sm)
        conn_sm.close()
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
    st.markdown('<h1 class="main-header">SUBSTITUTIONS LOG</h1>', unsafe_allow_html=True)
    
    df = get_substitutions_log()
    if df.empty:
        st.info("No substitutions recorded.")
    else:
        # Summary Metrics
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"""
                <div class="custom-card" style="text-align: center;">
                    <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Total Subs</div>
                    <div style="font-size: 2.5rem; font-family: 'Orbitron'; color: var(--primary-blue); margin: 10px 0;">{len(df)}</div>
                </div>
            """, unsafe_allow_html=True)
        with m2:
            top_team = df.groupby('team').size().idxmax() if not df.empty else "N/A"
            st.markdown(f"""
                <div class="custom-card" style="text-align: center;">
                    <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Most Active Team</div>
                    <div style="font-size: 1.5rem; font-family: 'Orbitron'; color: var(--primary-red); margin: 10px 0;">{top_team}</div>
                </div>
            """, unsafe_allow_html=True)
            
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
    conn_pl = get_conn()
    players_df = pd.read_sql("SELECT id, name FROM players ORDER BY name", conn_pl)
    conn_pl.close()
    
    st.markdown('<h1 class="main-header">PLAYER PROFILE</h1>', unsafe_allow_html=True)
    
    opts = players_df['name'].tolist()
    sel = st.selectbox("Select a Player", opts) if opts else None
    
    if sel:
        pid = int(players_df[players_df['name'] == sel].iloc[0]['id'])
        prof = get_player_profile(pid)
        
        if prof:
            # Header Card
            st.markdown(f"""
                <div class="custom-card" style="margin-bottom: 2rem;">
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <div style="background: var(--primary-blue); width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: var(--bg-dark);">
                            {prof['info'].get('name')[0].upper() if prof['info'].get('name') else 'P'}
                        </div>
                        <div>
                            <h2 style="margin: 0; color: var(--primary-blue); font-family: 'Orbitron';">{prof['info'].get('name')}</h2>
                            <div style="color: var(--text-dim); font-size: 1.1rem;">{prof['info'].get('team') or 'Free Agent'}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Metrics Grid
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                    <div class="custom-card" style="text-align: center;">
                        <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Games</div>
                        <div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{prof['games']}</div>
                    </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                    <div class="custom-card" style="text-align: center;">
                        <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Avg ACS</div>
                        <div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-blue); margin: 10px 0;">{prof['avg_acs']}</div>
                    </div>
                """, unsafe_allow_html=True)
            with m3:
                st.markdown(f"""
                    <div class="custom-card" style="text-align: center;">
                        <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">KD Ratio</div>
                        <div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-red); margin: 10px 0;">{prof['kd_ratio']}</div>
                    </div>
                """, unsafe_allow_html=True)
            with m4:
                st.markdown(f"""
                    <div class="custom-card" style="text-align: center;">
                        <div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Assists</div>
                        <div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{prof['total_assists']}</div>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Comparison Radar or Bar Chart
            st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">PERFORMANCE BENCHMARKS</h3>', unsafe_allow_html=True)
            
            cmp_df = pd.DataFrame({
                'Metric': ['ACS','Kills/Match','Deaths/Match','Assists/Match'],
                'Player': [prof['avg_acs'], prof['total_kills']/max(prof['games'],1), prof['total_deaths']/max(prof['games'],1), prof['total_assists']/max(prof['games'],1)],
                'Rank Avg': [prof['sr_avg_acs'], prof['sr_k'], prof['sr_d'], prof['sr_a']],
                'League Avg': [prof['lg_avg_acs'], prof['lg_k'], prof['lg_d'], prof['lg_a']],
            })
            
            # Plotly Bar Chart for comparison
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(name='Player', x=cmp_df['Metric'], y=cmp_df['Player'], marker_color='#3FD1FF'))
            fig_cmp.add_trace(go.Bar(name='Rank Avg', x=cmp_df['Metric'], y=cmp_df['Rank Avg'], marker_color='#FF4655', opacity=0.7))
            fig_cmp.add_trace(go.Bar(name='League Avg', x=cmp_df['Metric'], y=cmp_df['League Avg'], marker_color='#ECE8E1', opacity=0.5))
            
            fig_cmp.update_layout(barmode='group', height=400)
            st.plotly_chart(apply_plotly_theme(fig_cmp), use_container_width=True)
            
            if not prof['maps'].empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">RECENT MATCHES</h3>', unsafe_allow_html=True)
                maps_display = prof['maps'][['match_id','map_index','agent','acs','kills','deaths','assists','is_sub']].copy()
                maps_display.columns = ['Match ID', 'Map', 'Agent', 'ACS', 'K', 'D', 'A', 'Sub']
                st.dataframe(maps_display, hide_index=True, use_container_width=True)
