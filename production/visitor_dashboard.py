import streamlit as st
import sqlite3
import os
import sys
import html
import json
import re
import pandas as pd
import hmac
import math
import time
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
import base64
import requests
from supabase import create_client, Client

# Path management for production/staging structure
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
 

def get_secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

def init_pending_tables(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    timestamp_def = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if is_postgres else "DATETIME DEFAULT CURRENT_TIMESTAMP"

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS pending_matches (
            id {pk_def},
            team_a TEXT,
            team_b TEXT,
            group_name TEXT,
            url TEXT,
            submitted_by TEXT,
            timestamp {timestamp_def},
            status TEXT DEFAULT 'new'
        )
    """)
    
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS pending_players (
            id {pk_def},
            riot_id TEXT,
            rank TEXT,
            tracker_link TEXT,
            submitted_by TEXT,
            timestamp {timestamp_def},
            status TEXT DEFAULT 'new',
            discord_handle TEXT
        )
    """)
    
    if should_close:
        conn.commit()
        conn.close()

def init_player_discord_column(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    # Check if discord_handle column exists
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    if is_postgres:
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='players'")
        columns = [row[0] for row in cur.fetchall()]
    else:
        cursor = conn.execute("PRAGMA table_info(players)")
        columns = [row[1] for row in cursor.fetchall()]

    if 'discord_handle' not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN discord_handle TEXT")
        
    if should_close:
        conn.commit()
        conn.close()

# Cache management helpers
def clear_caches_safe(min_interval_sec: int = 30):
    ts_key = 'last_cache_clear_ts'
    now = time.time()
    last = st.session_state.get(ts_key, 0)
    if now - last >= min_interval_sec:
        try:
            st.cache_data.clear()
        except Exception:
            pass
        st.session_state[ts_key] = now

def warm_caches():
    if st.session_state.get('cache_warmed'):
        return
    try:
        # Lightweight prefetch to speed up first navigation
        _ = get_all_players_directory(format_names=False)
        _ = get_standings()
        # Prefetch week 1 regular matches if available
        try:
            _ = get_week_matches(week=1)
        except Exception:
            pass
    except Exception:
        pass
    st.session_state['cache_warmed'] = True

def measure_latency(fn, *args, **kwargs):
    start = time.perf_counter()
    try:
        res = fn(*args, **kwargs)
    except Exception:
        res = None
    dur = (time.perf_counter() - start) * 1000.0
    return res, dur

# Use data folder for database
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "data", "valorant_s23.db")
SECRET_DB_PATH = get_secret("DB_PATH")

if SECRET_DB_PATH:
    # If the secret path exists as is, use it
    if os.path.exists(SECRET_DB_PATH):
        DB_PATH = SECRET_DB_PATH
    # If it's just a filename and exists in the data folder, use that
    elif os.path.exists(os.path.join(ROOT_DIR, "data", os.path.basename(SECRET_DB_PATH))):
        DB_PATH = os.path.join(ROOT_DIR, "data", os.path.basename(SECRET_DB_PATH))
    # Otherwise, fallback to secret but it might create an empty DB
    else:
        DB_PATH = SECRET_DB_PATH
else:
    DB_PATH = DEFAULT_DB_PATH

# Valorant Map Catalog
maps_catalog = ["Abyss", "Ascent", "Bind", "Breeze", "Fracture", "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset", "Corrode"]

# Supabase SDK Initialization
supabase_api_url = get_secret("SUPABASE_URL")
supabase_api_key = get_secret("SUPABASE_KEY")
supabase: Client = None

if supabase_api_url and supabase_api_key:
    try:
        # Strip quotes if they exist from streamlit secrets
        u = str(supabase_api_url).strip('"').strip("'")
        k = str(supabase_api_key).strip('"').strip("'")
        supabase = create_client(u, k)
    except Exception as e:
        st.error(f"Error initializing Supabase SDK: {e}")

# Enforce Supabase-only mode
if supabase is None:
    st.error("Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

class UnifiedCursorWrapper:
    def __init__(self, cur, is_sqlite):
        self.cur = cur
        self.is_sqlite = is_sqlite
    
    def execute(self, sql, params=None):
        final_sql = sql
        if self.is_sqlite and "%s" in sql:
            final_sql = sql.replace("%s", "?")
        if params:
            return self.cur.execute(final_sql, params)
        return self.cur.execute(final_sql)
        
    def __getattr__(self, name):
        return getattr(self.cur, name)
    
    def __iter__(self):
        return iter(self.cur)

    # Add Context Manager support
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.cur, "close"):
            self.cur.close()

class UnifiedDBWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.is_sqlite = isinstance(conn, sqlite3.Connection)
        
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
        
    def cursor(self):
        return UnifiedCursorWrapper(self.conn.cursor(), self.is_sqlite)
        
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()
    def rollback(self):
        self.conn.rollback()
    def __getattr__(self, name):
        return getattr(self.conn, name)
    
    # Add Context Manager support
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

@st.cache_resource(ttl=3600)
def get_db_connection_pool():
    # Priority: direct Postgres connection string
    db_url = get_secret("SUPABASE_DB_URL") or get_secret("DB_CONNECTION_STRING") or get_secret("DATABASE_URL")
    
    import psycopg2
    from psycopg2 import pool
    
    if db_url:
        db_url_str = str(db_url).strip().strip('"').strip("'")
        if db_url_str.startswith("postgresql"):
            try:
                # Add sslmode if not present
                params = db_url_str
                if "sslmode" not in db_url_str:
                    params += "?sslmode=require" if "?" not in db_url_str else "&sslmode=require"
                
                # Create a simple connection pool (minconn=1, maxconn=10)
                # Since streamlit is multi-threaded, a pool is safer than a single shared connection
                return psycopg2.pool.ThreadedConnectionPool(1, 10, params)
            except Exception:
                pass
    return None

def get_conn():
    # Try to get a connection from the pool first
    pool = get_db_connection_pool()
    if pool:
        try:
            conn = pool.getconn()
            # Wrap it in our UnifiedDBWrapper but add a custom close to return to pool
            wrapper = UnifiedDBWrapper(conn)
            # Monkey patch close to return to pool instead of closing
            original_close = wrapper.close
            def return_to_pool():
                try:
                    pool.putconn(conn)
                except Exception:
                    # If pool is closed or error, try closing connection directly
                    try:
                        conn.close()
                    except:
                        pass
            wrapper.close = return_to_pool
            # Also patch __exit__ to use our new close
            wrapper.__exit__ = lambda exc_type, exc_val, exc_tb: return_to_pool()
            return wrapper
        except Exception:
            pass

    # Fallback to local SQLite or direct connection if pool acts up
    # Priority: direct Postgres connection string (if pool failed)
    db_url = get_secret("SUPABASE_DB_URL") or get_secret("DB_CONNECTION_STRING") or get_secret("DATABASE_URL")
    
    import psycopg2
    conn = None
    
    if db_url:
        db_url_str = str(db_url).strip().strip('"').strip("'")
        if db_url_str.startswith("postgresql"):
            try:
                # Add sslmode if not present
                params = db_url_str
                if "sslmode" not in db_url_str:
                    params += "?sslmode=require" if "?" not in db_url_str else "&sslmode=require"
                conn = psycopg2.connect(params, connect_timeout=5)
            except Exception:
                # Silent failure, will fallback to SQLite
                pass
    
    if conn:
        return UnifiedDBWrapper(conn)
    
    # Fallback to local SQLite
    # Ensure data directory exists
    data_dir = os.path.join(ROOT_DIR, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    return UnifiedDBWrapper(sqlite3.connect(DB_PATH))

def run_connection_diagnostics():
    """Runs a series of tests to help the user fix connection issues."""
    st.markdown("### 🔍 Connection Diagnostics")
    
    # 1. Check Secrets
    db_url_diag = os.getenv("SUPABASE_DB_URL") or os.getenv("DB_CONNECTION_STRING")
    api_url_diag = os.getenv("SUPABASE_URL")
    api_key_diag = os.getenv("SUPABASE_KEY")
    
    cols = st.columns(3)
    with cols[0]:
        st.write("**DB URL**")
        if db_url_diag:
            st.success("Found ✅")
            if not str(db_url_diag).startswith("postgresql"):
                st.warning("Invalid prefix (should be `postgresql://`)")
        else:
            st.error("MISSING ❌")
            
    with cols[1]:
        st.write("**SUPABASE_URL (API)**")
        if api_url_diag:
            st.success("Found ✅")
        else:
            st.error("MISSING ❌")
            
    with cols[2]:
        st.write("**SUPABASE_KEY**")
        if api_key_diag:
            st.success("Found ✅")
        else:
            st.error("MISSING ❌")
            
    # 2. Test Supabase SDK Connectivity (HTTP)
    st.write("**Testing Supabase SDK (HTTP/REST)...**")
    if supabase:
        try:
            supabase.table("teams").select("count", count="exact").limit(1).execute()
            st.success("Supabase SDK connection SUCCESS! API is reachable.")
        except Exception as e:
            st.error(f"Supabase SDK failed: {e}")
    else:
        st.error("Supabase SDK is not initialized.")
        
    st.info("💡 If SDK works but PostgreSQL doesn't, Streamlit Cloud might be blocking port 5432. Try using port 6543 (transaction cooler) in your DB URL.")
    st.write("**Data Status (Supabase public schema)**")
    if supabase:
        try:
            c_matches = supabase.table("matches").select("count", count="exact").execute()
            c_maps = supabase.table("match_maps").select("count", count="exact").execute()
            c_statsmap = supabase.table("match_stats_map").select("count", count="exact").execute()
            weeks = supabase.table("matches").select("week").execute()
            st.info(f"Matches: {c_matches.count or 0} • Maps: {c_maps.count or 0} • StatsMap: {c_statsmap.count or 0}")
            if weeks.data:
                wkset = sorted(list(set([w.get('week') for w in weeks.data if w.get('week') is not None])))
                st.caption(f"Weeks present: {wkset}")
        except Exception as e:
            st.warning(f"Data status fetch failed: {e}")
    
    st.write("**Latency Measurements**")
    _, dur_players = measure_latency(get_all_players_directory, False)
    st.caption(f"Players directory load: {dur_players:.1f} ms")
    _, dur_standings = measure_latency(get_standings)
    st.caption(f"Standings compute/load: {dur_standings:.1f} ms")
    try:
        _, dur_week = measure_latency(get_week_matches, 1)
        st.caption(f"Week 1 matches load: {dur_week:.1f} ms")
    except Exception:
        pass

def should_use_cache():
    # If no admin is active in the last 5 minutes, we can use cache
    active_admin = get_active_admin_session()
    if active_admin:
        return False
    return True

def init_admin_table(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
        
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob_def = "BYTEA" if is_postgres else "BLOB"

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS admins (
            id {pk_def},
            username TEXT UNIQUE NOT NULL,
            password_hash {blob_def} NOT NULL,
            salt {blob_def} NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    if should_close:
        conn.commit()
        conn.close()

def init_session_activity_table(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_type = "TEXT PRIMARY KEY"
    real_type = "DOUBLE PRECISION" if is_postgres else "REAL"
    
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS session_activity (
            session_id {pk_type},
            username TEXT,
            role TEXT,
            last_activity {real_type},
            ip_address TEXT
        )
        """
    )
    
    # Column check logic
    if is_postgres:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='session_activity'")
            columns = [row[0] for row in cur.fetchall()]
            if 'ip_address' not in columns:
                cur.execute("ALTER TABLE session_activity ADD COLUMN ip_address TEXT")
    else:
        cursor = conn.execute("PRAGMA table_info(session_activity)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'ip_address' not in columns:
            conn.execute("ALTER TABLE session_activity ADD COLUMN ip_address TEXT")
        
    if should_close:
        conn.commit()
        conn.close()

def init_pending_tables(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    timestamp_def = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if is_postgres else "DATETIME DEFAULT CURRENT_TIMESTAMP"
    
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS pending_matches (
            id {pk_def},
            team_a TEXT,
            team_b TEXT,
            group_name TEXT,
            url TEXT,
            submitted_by TEXT,
            timestamp {timestamp_def}
        )
    """)
    
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS pending_players (
            id {pk_def},
            riot_id TEXT,
            rank TEXT,
            discord_handle TEXT,
            submitted_by TEXT,
            timestamp {timestamp_def}
        )
    """)
    
    if should_close:
        conn.commit()
        conn.close()

def get_visitor_ip():
    # 1. Try a fingerprint-based pseudo-IP FIRST for maximum stability
    # This fingerprint stays the same across refreshes on the same browser/device
    # even if the IP rotates or session_state is cleared.
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        h = _get_websocket_headers()
        if h:
            import hashlib
            # Combine User-Agent, Accept-Language, and Accept headers
            # to create a persistent ID for this specific browser.
            fingerprint_str = f"{h.get('User-Agent', '')}{h.get('Accept-Language', '')}{h.get('Accept', '')}"
            if fingerprint_str.strip():
                return f"fp_{hashlib.md5(fingerprint_str.encode()).hexdigest()[:12]}"
    except Exception:
        pass

    # 2. Fallback to st.context (Streamlit 1.34+)
    try:
        if hasattr(st, "context"):
            if hasattr(st.context, "remote_ip") and st.context.remote_ip:
                return st.context.remote_ip
            
            headers = st.context.headers
            for header in ["X-Forwarded-For", "X-Real-IP", "Forwarded"]:
                val = headers.get(header)
                if val:
                    return val.split(",")[0].strip()
    except Exception:
        pass

    # 3. Fallback to internal websocket headers
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        if headers:
            for header in ["X-Forwarded-For", "X-Real-IP", "Remote-Addr"]:
                val = headers.get(header)
                if val:
                    return val.split(",")[0].strip()
    except Exception:
        pass
            
    # Absolute last resort (will change on refresh)
    if 'pseudo_ip' not in st.session_state:
        import uuid
        st.session_state['pseudo_ip'] = f"tmp_{uuid.uuid4().hex[:8]}"
    return st.session_state['pseudo_ip']

def track_user_activity():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if not ctx:
            return
        session_id = ctx.session_id
        
        username = st.session_state.get('username')
        is_admin = st.session_state.get('is_admin', False)
        app_mode = st.session_state.get('app_mode', 'portal')
        
        role = 'visitor'
        if is_admin:
            role = st.session_state.get('role', 'admin')
        elif app_mode == 'admin':
            role = 'visitor' # Attempting to login
            
        ip_address = get_visitor_ip()
        
        # Throttling Logic: Only update DB if > 60s since last update OR if identity data changed
        now = time.time()
        last_track = st.session_state.get('last_track_time', 0)
        last_track_data = st.session_state.get('last_track_data', {})
        
        current_data = {'username': username, 'role': role, 'ip': ip_address}
        
        if (now - last_track < 60) and (current_data == last_track_data):
            # Skip DB write, just return
            return

        conn = get_conn()
        
        # Always update current session
        is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
        if is_postgres:
            conn.execute(
                """
                INSERT INTO session_activity (session_id, username, role, last_activity, ip_address) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET 
                    username = EXCLUDED.username, 
                    role = EXCLUDED.role, 
                    last_activity = EXCLUDED.last_activity, 
                    ip_address = EXCLUDED.ip_address
                """,
                (session_id, username, role, now, ip_address)
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO session_activity (session_id, username, role, last_activity, ip_address) VALUES (%s, %s, %s, %s, %s)",
                (session_id, username, role, now, ip_address)
            )
        
        # Cleanup old sessions (older than 30 minutes) - perform this less frequently too
        # checking modulo of current time to do it roughly every 5 mins
        if int(now) % 300 < 5: 
            conn.execute("DELETE FROM session_activity WHERE last_activity < %s", (now - 1800,))
            
        conn.commit()
        conn.close()
        
        # Update session state
        st.session_state['last_track_time'] = now
        st.session_state['last_track_data'] = current_data
        
    except Exception:
        pass

def get_active_user_count():
    conn = get_conn()
    # Count distinct IPs active in last 5 minutes
    res = conn.execute("SELECT COUNT(DISTINCT ip_address) FROM session_activity WHERE last_activity > %s", (time.time() - 300,)).fetchone()
    conn.close()
    return res[0] if res else 0

def get_active_admin_session():
    conn = get_conn()
    # Check for active admin/dev sessions in last 300 seconds (5 mins)
    curr_ip = get_visitor_ip()
    
    # Get all active admin sessions
    res = conn.execute(
        "SELECT username, role, ip_address FROM session_activity WHERE (role='admin' OR role='dev') AND last_activity > %s", 
        (time.time() - 300,)
    ).fetchall()
    conn.close()
    
    # Filter out current IP manually to handle potential logic issues
    for row in res:
        if row[2] != curr_ip:
            return row # Return the first session that isn't us
            
    return None

# Set page config immediately as the first streamlit command
st.set_page_config(page_title="S23 Portal v0.8.0", layout="wide", initial_sidebar_state="collapsed")

def ensure_base_schema(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    c = conn.cursor()
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    c.execute(f'''CREATE TABLE IF NOT EXISTS teams (
        id {pk_def},
        tag TEXT,
        name TEXT UNIQUE,
        group_name TEXT,
        captain TEXT,
        co_captain TEXT
    )''')
    c.execute(f'''CREATE TABLE IF NOT EXISTS players (
        id {pk_def},
        name TEXT UNIQUE,
        riot_id TEXT,
        rank TEXT,
        default_team_id INTEGER REFERENCES teams(id)
    )''')
    c.execute(f'''CREATE TABLE IF NOT EXISTS matches (
        id {pk_def},
        week INTEGER,
        group_name TEXT,
        team1_id INTEGER REFERENCES teams(id),
        team2_id INTEGER REFERENCES teams(id),
        winner_id INTEGER REFERENCES teams(id),
        score_t1 INTEGER DEFAULT 0,
        score_t2 INTEGER DEFAULT 0,
        status TEXT DEFAULT 'scheduled',
        format TEXT,
        maps_played INTEGER DEFAULT 0
    )''')
    c.execute(f'''CREATE TABLE IF NOT EXISTS match_maps (
        id {pk_def},
        match_id INTEGER NOT NULL REFERENCES matches(id),
        map_index INTEGER NOT NULL,
        map_name TEXT,
        team1_rounds INTEGER,
        team2_rounds INTEGER,
        winner_id INTEGER,
        UNIQUE(match_id, map_index)
    )''')
    c.execute(f'''CREATE TABLE IF NOT EXISTS match_stats (
        id {pk_def},
        match_id INTEGER NOT NULL REFERENCES matches(id),
        player_id INTEGER NOT NULL REFERENCES players(id),
        team_id INTEGER,
        acs INTEGER,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER
    )''')
    c.execute(f'''CREATE TABLE IF NOT EXISTS agents (
        id {pk_def},
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
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    if is_postgres:
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
        cols = [row[0] for row in cur.fetchall()]
    else:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]

    if column_name not in cols:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def_sql}")
        except Exception:
            pass
    # Try direct SQL if available to populate missing pieces (PostgreSQL)
    try:
        conn = get_conn()
        is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
        if is_postgres:
            if info.empty:
                info = pd.read_sql_query(
                    "SELECT p.id, p.name, p.riot_id, p.rank, t.tag AS team FROM players p LEFT JOIN teams t ON p.default_team_id=t.id WHERE p.id=%s",
                    conn,
                    params=(int(player_id),),
                )
            if stats.empty and not info.empty:
                stats = pd.read_sql_query(
                    """
                    SELECT msm.match_id, msm.map_index, msm.agent, msm.acs, msm.kills, msm.deaths, msm.assists, msm.is_sub,
                           m.week, mm.map_name
                    FROM match_stats_map msm
                    JOIN matches m ON msm.match_id = m.id
                    LEFT JOIN match_maps mm ON msm.match_id = mm.match_id AND msm.map_index = mm.map_index
                    WHERE msm.player_id=%s AND m.status='completed'
                    """,
                    conn,
                    params=(int(player_id),),
                )
            if bench is None and not info.empty:
                rank_val = info.iloc[0]['rank']
                bench = pd.read_sql_query(
                    """
                    SELECT 
                        AVG(msm.acs) as lg_acs, AVG(msm.kills) as lg_k, AVG(msm.deaths) as lg_d, AVG(msm.assists) as lg_a,
                        AVG(CASE WHEN p.rank = %s THEN msm.acs ELSE NULL END) as r_acs,
                        AVG(CASE WHEN p.rank = %s THEN msm.kills ELSE NULL END) as r_k,
                        AVG(CASE WHEN p.rank = %s THEN msm.deaths ELSE NULL END) as r_d,
                        AVG(CASE WHEN p.rank = %s THEN msm.assists ELSE NULL END) as r_a
                    FROM match_stats_map msm
                    JOIN matches m ON msm.match_id = m.id
                    JOIN players p ON msm.player_id = p.id
                    WHERE m.status = 'completed'
                    """,
                    conn,
                    params=(rank_val, rank_val, rank_val, rank_val),
                ).iloc[0]
    except Exception:
        pass
    
    if should_close:
        conn.commit()
        conn.close()

def ensure_upgrade_schema(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "PRIMARY KEY" if is_postgres else "PRIMARY KEY" # SERIAL handled in create
    serial_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    conn.execute(f'''CREATE TABLE IF NOT EXISTS seasons (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        start_date TEXT,
        end_date TEXT,
        is_active BOOLEAN DEFAULT FALSE
    )''')
    conn.execute(f'''CREATE TABLE IF NOT EXISTS team_history (
        id {serial_def},
        team_id INTEGER REFERENCES teams(id),
        season_id INTEGER REFERENCES seasons(id),
        final_rank INTEGER,
        group_name TEXT
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
    ensure_column("matches", "is_forfeit", "is_forfeit BOOLEAN DEFAULT 0", conn=conn)
    ensure_column("matches", "bracket_label", "bracket_label TEXT", conn=conn)
    ensure_column("match_maps", "is_forfeit", "is_forfeit INTEGER DEFAULT 0", conn=conn)
    
    # Notification & Tracking Columns
    ensure_column("matches", "reported", "reported BOOLEAN DEFAULT FALSE", conn=conn)
    ensure_column("matches", "channel_id", "channel_id TEXT", conn=conn)
    ensure_column("matches", "submitter_id", "submitter_id TEXT", conn=conn)

    ensure_column("pending_players", "notified", "notified BOOLEAN DEFAULT FALSE", conn=conn)
    ensure_column("pending_players", "channel_id", "channel_id TEXT", conn=conn)
    ensure_column("pending_players", "submitter_id", "submitter_id TEXT", conn=conn)

    ensure_column("pending_matches", "channel_id", "channel_id TEXT", conn=conn)
    ensure_column("pending_matches", "submitter_id", "submitter_id TEXT", conn=conn)

    ensure_column("players", "uuid", "uuid TEXT", conn=conn)
    
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    ignore_clause = "ON CONFLICT DO NOTHING" if is_postgres else "OR IGNORE"
    
    try:
        conn.execute(f"INSERT {ignore_clause} INTO seasons (id, name, is_active) VALUES (22, 'Season 22', 0)")
        conn.execute(f"INSERT {ignore_clause} INTO seasons (id, name, is_active) VALUES (23, 'Season 23', 1)")
    except Exception:
        pass
    try:
        conn.execute(f"INSERT {ignore_clause} INTO team_history (team_id, season_id, group_name) SELECT id, 23, group_name FROM teams")
    except Exception:
        pass
    
    if should_close:
        conn.commit()
        conn.close()

def init_match_stats_map_table(conn=None):
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS match_stats_map (
            id {pk_def},
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

# App Mode Logic
if 'app_mode' not in st.session_state:
    st.session_state['app_mode'] = 'portal'
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'login_attempts' not in st.session_state:
    st.session_state['login_attempts'] = 0
if 'last_login_attempt' not in st.session_state:
    st.session_state['last_login_attempt'] = 0
if 'page' not in st.session_state:
    st.session_state['page'] = "Overview & Standings"

def bootstrap_schema_once():
    if st.session_state.get('schema_initialized'):
        return
    init_session_activity_table()
    ensure_base_schema()
    ensure_upgrade_schema()
    init_admin_table()
    init_match_stats_map_table()
    init_pending_tables() # Moved here
    init_player_discord_column() # Moved here
    st.session_state['schema_initialized'] = True

bootstrap_schema_once()
track_user_activity()
warm_caches()

# Hide standard sidebar navigation and other streamlit elements
st.markdown("""<link href='https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@400;600&family=Inter:wght@400;700&display=swap' rel='stylesheet'>""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Hide Streamlit elements */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
.stAppDeployButton {display:none;}
[data-testid="stSidebar"] {display: none;}
[data-testid="stSidebarCollapsedControl"] {display: none;}

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
    # Allow relative paths that might contain 'assets' but prevent escaping project root
    clean_path = path.replace('\\', '/')
    if ".." in clean_path or clean_path.startswith('/') or ":" in clean_path:
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
            # If data extraction fails, we might still get text%s 
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
    Scraping is disabled in the cloud environment.
    Returns (None, error_message)
    """
    return None, "Scraping is disabled on Streamlit Cloud. Use JSON upload or GitHub."

@st.cache_data(ttl=600)
def list_files_from_github(path):
    """Lists files in a GitHub directory."""
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    token = get_secret("GH_TOKEN")
    branch = get_secret("GH_BRANCH", "main")
    if not owner or not repo or not token: return []
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}%sref={branch}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    for _ in range(2):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return [f for f in r.json() if f['type'] == 'file' and f['name'].endswith('.json')]
        except:
            pass
    return []

def delete_file_from_github(path, message="Delete file"):
    """Deletes a file from GitHub."""
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    token = get_secret("GH_TOKEN")
    branch = get_secret("GH_BRANCH", "main")
    if not owner or not repo or not token: return False
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
            payload = {"message": message, "sha": sha, "branch": branch}
            r_del = requests.delete(url, headers=headers, json=payload, timeout=10)
            return r_del.status_code in [200, 204]
    except: pass
    return False

def get_file_content_from_github(path):
    """Fetches and parses a JSON file from GitHub."""
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    token = get_secret("GH_TOKEN")
    branch = get_secret("GH_BRANCH", "main")
    if not owner or not repo or not token: return None
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}%sref={branch}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200: return r.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_match_from_github(match_id):
    """
    Attempts to fetch a match JSON from the GitHub repository.
    """
    owner = get_secret("GH_OWNER")
    repo = get_secret("GH_REPO")
    token = get_secret("GH_TOKEN")
    branch = get_secret("GH_BRANCH", "main")
    
    if not owner or not repo:
        return None, "GitHub configuration missing (GH_OWNER/GH_REPO)"
        
    # Use API for both public and private repos if token is available
    if token:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/assets/matches/match_{match_id}.json?ref={branch}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw"}
        for _ in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    return r.json(), None
            except Exception:
                pass
        return None, "GitHub API error"
    else:
        # Fallback to public raw URL
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/assets/matches/match_{match_id}.json"
        for _ in range(2):
            try:
                r = requests.get(raw_url, timeout=10)
                if r.status_code == 200:
                    return r.json(), None
            except Exception:
                pass
        return None, "GitHub file not found"


def parse_tracker_json(jsdata, team1_id, team2_id):
    """
    Parses Tracker.gg JSON data and matches it to team1_id and team2_id.
    Returns (json_suggestions, map_name, t1_rounds, t2_rounds)
    """
    import re
    json_suggestions = {}
    segments = jsdata.get("data", {}).get("segments", [])
    
    # First pass: find team names/IDs to identify which Tracker team is which
    tracker_team_1_id = None
    team_segments = [s for s in segments if s.get("type") == "team-summary"]
    
    # Get all players for matching
    all_players_df = get_all_players()
    riot_id_to_name = {}
    name_to_name = {}
    if not all_players_df.empty:
        # Create a case-insensitive map of riot_id -> player name
        riot_id_to_name = {str(r).strip().lower(): str(n) for r, n in zip(all_players_df['riot_id'], all_players_df['name']) if pd.notna(r)}
        # Also map name -> name for fallback
        name_to_name = {str(n).strip().lower(): str(n) for n in all_players_df['name'] if pd.notna(n)}

    if len(team_segments) >= 2:
        # Use Riot IDs to match teams
        t1_id_int = int(team1_id) if team1_id is not None else None
        t2_id_int = int(team2_id) if team2_id is not None else None
        
        # Team 1 Roster
        t1_roster_df = all_players_df[all_players_df['default_team_id'] == t1_id_int]
        t1_rids = [str(r).strip().lower() for r in t1_roster_df['riot_id'].dropna()]
        t1_names = [str(n).strip().lower() for n in t1_roster_df['name'].dropna()]
        t1_names_clean = [n.replace('@', '').strip() for n in t1_names]
        
        # Team 2 Roster
        t2_roster_df = all_players_df[all_players_df['default_team_id'] == t2_id_int]
        t2_rids = [str(r).strip().lower() for r in t2_roster_df['riot_id'].dropna()]
        t2_names = [str(n).strip().lower() for n in t2_roster_df['name'].dropna()]
        t2_names_clean = [n.replace('@', '').strip() for n in t2_names]
        
        team_ids_in_json = [ts.get("attributes", {}).get("teamId") for ts in team_segments]
        
        # Count matches for each Tracker team against our rosters
        # score[tracker_team_id][db_team_id]
        scores = {tid: {1: 0, 2: 0} for tid in team_ids_in_json}
        
        for p_seg in [s for s in segments if s.get("type") == "player-summary"]:
            t_id = p_seg.get("metadata", {}).get("teamId")
            if t_id in scores:
                rid = p_seg.get("metadata", {}).get("platformInfo", {}).get("platformUserIdentifier")
                if not rid: rid = p_seg.get("metadata", {}).get("platformInfo", {}).get("platformUserHandle")
                
                if rid:
                    rid_clean = str(rid).strip().lower()
                    name_part = rid_clean.split('#')[0]
                    
                    # Match vs Team 1
                    is_t1 = rid_clean in t1_rids or rid_clean in t1_names or name_part in t1_names or name_part in t1_names_clean
                    if not is_t1:
                        # Try partial match for name_part
                        for tn in t1_names_clean:
                            if name_part in tn or tn in name_part:
                                is_t1 = True
                                break
                    if is_t1: scores[t_id][1] += 1
                    
                    # Match vs Team 2
                    is_t2 = rid_clean in t2_rids or rid_clean in t2_names or name_part in t2_names or name_part in t2_names_clean
                    if not is_t2:
                        # Try partial match for name_part
                        for tn in t2_names_clean:
                            if name_part in tn or tn in name_part:
                                is_t2 = True
                                break
                    if is_t2: scores[t_id][2] += 1
        
        # Decision logic:
        # Option A: TrackerTeam0 is Team 1, TrackerTeam1 is Team 2
        score_a = scores[team_ids_in_json[0]][1] + scores[team_ids_in_json[1]][2]
        # Option B: TrackerTeam0 is Team 2, TrackerTeam1 is Team 1
        score_b = scores[team_ids_in_json[0]][2] + scores[team_ids_in_json[1]][1]
        
        if score_a >= score_b and score_a > 0:
            tracker_team_1_id = team_ids_in_json[0]
        elif score_b > score_a:
            tracker_team_1_id = team_ids_in_json[1]
        else:
            # Tie or 0 matches%s Default to first team
            tracker_team_1_id = team_ids_in_json[0]
    else:
        if team_segments:
            tracker_team_1_id = team_segments[0].get("attributes", {}).get("teamId")
        else:
            tracker_team_1_id = None

    for seg in segments:
        if seg.get("type") == "player-summary":
            metadata = seg.get("metadata", {})
            platform_info = metadata.get("platformInfo", {})
            rid = platform_info.get("platformUserIdentifier")
            
            # Tracker sometimes puts the name in platformUserHandle or platformUserIdentifier
            if not rid:
                rid = platform_info.get("platformUserHandle")
            
            if rid:
                rid = str(rid).strip()
            
            agent = metadata.get("agentName")
            st_map = seg.get("stats", {})
            acs = st_map.get("scorePerRound", {}).get("value", 0)
            k = st_map.get("kills", {}).get("value", 0)
            d = st_map.get("deaths", {}).get("value", 0)
            a = st_map.get("assists", {}).get("value", 0)
            t_id = metadata.get("teamId")
            
            our_team_num = 1 if t_id == tracker_team_1_id else 2
            
            if rid:
                rid_lower = rid.lower()
                # Try to find a match in our DB if direct match fails
                matched_name = riot_id_to_name.get(rid_lower)
                
                # If still no match, try matching the name part of rid (if it's Name#Tag) or rid itself against DB names
                if not matched_name:
                    name_part = rid.split('#')[0].lower()
                    matched_name = name_to_name.get(name_part) or name_to_name.get(rid_lower)
                
                # Store by riot_id but also provide the matched name if found
                json_suggestions[rid_lower] = {
                    'name': matched_name, # Found in DB or None
                    'tracker_name': rid,  # Original name from Tracker
                    'acs': int(acs) if acs is not None else 0, 
                    'k': int(k) if k is not None else 0, 
                    'd': int(d) if d is not None else 0, 
                    'a': int(a) if a is not None else 0, 
                    'agent': agent,
                    'team_num': our_team_num,
                    'conf': 100.0 if matched_name else 80.0
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
    if not image_path:
        return None
    
    # Resolve relative path against ROOT_DIR
    if not os.path.isabs(image_path):
        full_path = os.path.join(ROOT_DIR, image_path)
    else:
        full_path = image_path

    if not os.path.exists(full_path):
        return None
        
    try:
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

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
            q = f"INSERT OR REPLACE INTO {t} (" + ",".join(use) + ") VALUES (" + ",".join(["%s"]*len(use)) + ")"
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
    df = pd.DataFrame()
    if not supabase:
        return df
    try:
        base_res = supabase.table("match_stats_map")\
            .select("match_id, map_index, team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists")\
            .eq("is_sub", 1)\
            .execute()
        if not base_res.data:
            return df
        base = pd.DataFrame(base_res.data)
        if base.empty:
            return df
        m_ids = sorted(list(set(base['match_id'].tolist())))
        t_ids = sorted(list(set(base['team_id'].dropna().astype(int).tolist()))) if 'team_id' in base else []
        p_ids = sorted(list(set(pd.concat([base['player_id'].dropna(), base['subbed_for_id'].dropna()], ignore_index=True).astype(int).tolist()))) if 'player_id' in base else []

        m_res = supabase.table("matches").select("id, week, group_name, status").in_("id", m_ids).execute()
        mdf = pd.DataFrame(m_res.data) if m_res.data else pd.DataFrame(columns=['id','week','group_name','status'])
        if mdf.empty:
            return df
        mdf['status'] = mdf['status'].astype(str).str.lower()
        mdf = mdf[mdf['status'] == 'completed']
        if mdf.empty:
            return pd.DataFrame()

        tdf = pd.DataFrame()
        if t_ids:
            t_res = supabase.table("teams").select("id, name").in_("id", t_ids).execute()
            tdf = pd.DataFrame(t_res.data) if t_res.data else pd.DataFrame(columns=['id','name'])

        pdf = pd.DataFrame()
        if p_ids:
            p_res = supabase.table("players").select("id, name, riot_id").in_("id", p_ids).execute()
            pdf = pd.DataFrame(p_res.data) if p_res.data else pd.DataFrame(columns=['id','name','riot_id'])

        out = base.merge(mdf.rename(columns={'id':'match_id'}), on='match_id', how='inner')
        if not tdf.empty:
            out = out.merge(tdf.rename(columns={'id':'team_id','name':'team'}), on='team_id', how='left')
        if not pdf.empty:
            out = out.merge(pdf.rename(columns={'id':'player_id','name':'player','riot_id':'player_riot'}), on='player_id', how='left')
            out = out.merge(pdf.rename(columns={'id':'subbed_for_id','name':'subbed_for','riot_id':'sub_riot'}), on='subbed_for_id', how='left')

        out['player'] = out.apply(lambda r: f"{r['player']} ({r['player_riot']})" if r.get('player_riot') and str(r.get('player_riot')).strip() else r.get('player'), axis=1)
        out['subbed_for'] = out.apply(lambda r: f"{r['subbed_for']} ({r['sub_riot']})" if r.get('sub_riot') and str(r.get('sub_riot')).strip() else r.get('subbed_for'), axis=1)
        out = out.drop(columns=['player_riot','sub_riot'], errors='ignore')
        out = out[['match_id','map_index','week','group_name','team','player','subbed_for','agent','acs','kills','deaths','assists']]
        return out
    except Exception:
        return df

@st.cache_data(ttl=300)
def get_player_profile(player_id):
    import pandas as pd
    info = pd.DataFrame()
    stats = pd.DataFrame()
    bench = None
    
    # Try Supabase SDK First
    if supabase:
        try:
            # 1. Player Info
            res_p = supabase.table("players").select("*, teams!default_team_id(tag)").eq("id", player_id).execute()
            if res_p.data:
                item = res_p.data[0]
                item['team'] = item.get('teams', {}).get('tag')
                info = pd.DataFrame([item])
                
                res_s = supabase.table("match_stats_map").select("*").eq("player_id", player_id).execute()
                if res_s.data:
                    stats = pd.DataFrame(res_s.data)
                    if not stats.empty:
                        stats['match_id'] = pd.to_numeric(stats['match_id'], errors='coerce')
                        stats['map_index'] = pd.to_numeric(stats.get('map_index', 0), errors='coerce').fillna(0).astype(int)
                        mids = stats['match_id'].dropna().astype(int).unique().tolist()
                        mdf = pd.DataFrame(); mmdf = pd.DataFrame()
                        if mids:
                            res_m = supabase.table("matches").select("id,status,week,format").in_("id", mids).execute()
                            if res_m.data:
                                mdf = pd.DataFrame(res_m.data)
                                mdf['status'] = mdf['status'].astype(str).str.lower()
                                mdf = mdf.set_index('id')
                            # Join map names for each (match_id, map_index)
                            res_mm = supabase.table("match_maps").select("match_id,map_index,map_name,team1_rounds,team2_rounds").in_("match_id", mids).execute()
                            if res_mm.data:
                                mmdf = pd.DataFrame(res_mm.data)
                                mmdf['map_index'] = pd.to_numeric(mmdf.get('map_index', 0), errors='coerce').fillna(0).astype(int)
                                mmdf = mmdf[['match_id','map_index','map_name','team1_rounds','team2_rounds']]
                        # Merge match metadata (vectorized)
                        if not mdf.empty:
                            # mdf is already indexed by id from line 1643
                            # We can map or join. Join is cleaner if we match on index.
                            # stats['match_id'] is the foreign key.
                            stats = stats.join(mdf[['status', 'week', 'format']], on='match_id', how='left')
                        
                        # Merge map names and rounds
                        if not mmdf.empty:
                            stats = stats.merge(mmdf, on=['match_id','map_index'], how='left')
                            
                        stats['is_sub'] = pd.to_numeric(stats.get('is_sub', 0), errors='coerce').fillna(0)
                        
                        # Vectorized check for non-zero stats
                        cols_check = [c for c in ['acs','kills','deaths','assists'] if c in stats.columns]
                        if cols_check:
                            nz = stats[cols_check].sum(axis=1) > 0
                        else:
                            nz = False
                            
                        stats = stats[(stats['status'] == 'completed') | (nz)]
                    
                # 3. Benchmarks (League Avg & Rank Avg)
                rank_val = info.iloc[0]['rank']
                # We fetch all match stats for completed matches to compute averages
                # Note: For large datasets, this should be an RPC or a pre-computed view
                res_all = supabase.rpc("get_player_benchmarks", {"p_rank": rank_val}).execute()
                if res_all.data:
                    bench = pd.Series(res_all.data[0])
                else:
                    # Fallback to fetching and calculating in Pandas if RPC missing
                    res_m = supabase.table("matches").select("id").eq("status", "completed").execute()
                    c_ids = [m['id'] for m in res_m.data] if res_m.data else []
                    if c_ids:
                        # Fetch stats in chunks to avoid URL length limits
                        b_list = []
                        chunk_size = 100
                        for i in range(0, len(c_ids), chunk_size):
                            cid_chunk = c_ids[i:i+chunk_size]
                            try:
                                rs = supabase.table("match_stats_map")\
                                    .select("match_id,acs,kills,deaths,assists,player_id")\
                                    .in_("match_id", cid_chunk)\
                                    .execute()
                                if rs.data:
                                    b_list.extend(rs.data)
                            except Exception:
                                pass
                        if b_list:
                            bdf = pd.DataFrame(b_list)
                            # Ensure numeric for aggregation
                            for col in ['acs','kills','deaths','assists','player_id']:
                                if col in bdf.columns:
                                    bdf[col] = pd.to_numeric(bdf[col], errors='coerce')
                            # Get ranks for involved players
                            pids = bdf['player_id'].dropna().unique().tolist()
                            ranks_df = pd.DataFrame()
                            if pids:
                                res_pr = supabase.table("players").select("id,rank").in_("id", pids).execute()
                                if res_pr.data:
                                    ranks_df = pd.DataFrame(res_pr.data)
                                    ranks_df['id'] = pd.to_numeric(ranks_df['id'], errors='coerce')
                            if not ranks_df.empty:
                                bdf = bdf.merge(ranks_df.rename(columns={'id':'player_id'}), on='player_id', how='left')
                            # Compute league averages across all rows (staging parity)
                            lg_acs = float(bdf['acs'].mean()) if 'acs' in bdf.columns else 0.0
                            lg_k = float(bdf['kills'].mean()) if 'kills' in bdf.columns else 0.0
                            lg_d = float(bdf['deaths'].mean()) if 'deaths' in bdf.columns else 0.0
                            lg_a = float(bdf['assists'].mean()) if 'assists' in bdf.columns else 0.0
                            # Rank averages across rows with same rank
                            rbdf = bdf[bdf['rank'] == rank_val] if 'rank' in bdf.columns else pd.DataFrame()
                            if not rbdf.empty:
                                r_acs = float(rbdf['acs'].mean()) if 'acs' in rbdf.columns else 0.0
                                r_k = float(rbdf['kills'].mean()) if 'kills' in rbdf.columns else 0.0
                                r_d = float(rbdf['deaths'].mean()) if 'deaths' in rbdf.columns else 0.0
                                r_a = float(rbdf['assists'].mean()) if 'assists' in rbdf.columns else 0.0
                            else:
                                # Fallback: use league averages if no rank-specific data yet
                                r_acs, r_k, r_d, r_a = lg_acs, lg_k, lg_d, lg_a
                            bench = pd.Series({
                                'lg_acs': lg_acs, 'lg_k': lg_k, 'lg_d': lg_d, 'lg_a': lg_a,
                                'r_acs': r_acs, 'r_k': r_k, 'r_d': r_d, 'r_a': r_a
                            })
                        else:
                            # If no join, compute league-only averages as a fallback
                            res_bench = supabase.table("match_stats_map")\
                                .select("acs,kills,deaths,assists")\
                                .in_("match_id", c_ids)\
                                .execute()
                            if res_bench.data:
                                bdf = pd.DataFrame(res_bench.data)
                                bench = pd.Series({
                                    'lg_acs': bdf['acs'].mean(), 'lg_k': bdf['kills'].mean(), 
                                    'lg_d': bdf['deaths'].mean(), 'lg_a': bdf['assists'].mean(),
                                    'r_acs': None,'r_k': None,'r_d': None,'r_a': None
                                })
        except Exception:
            pass
    # Supabase-only: if not found via Supabase, return {}
    if info.empty:
        return {}
    if bench is None or not isinstance(bench, pd.Series):
        bench = pd.Series({'lg_acs': 0, 'lg_k': 0, 'lg_d': 0, 'lg_a': 0, 'r_acs': 0, 'r_k': 0, 'r_d': 0, 'r_a': 0})
            
    # Post-processing
    p_name = info.iloc[0]['name']
    p_riot = info.iloc[0]['riot_id']
    display_name = f"{p_name} ({p_riot})" if p_riot and str(p_riot).strip() else p_name
    
    trend = pd.DataFrame()
    if not stats.empty:
        agg = stats.groupby('match_id').agg({'acs':'mean','kills':'sum','deaths':'sum','week':'first'}).reset_index()
        agg['kda'] = agg['kills'] / agg['deaths'].replace(0, 1)
        agg['label'] = 'W' + agg['week'].fillna(0).astype(int).astype(str) + '-M' + agg['match_id'].astype(int).astype(str)
        agg = agg.rename(columns={'acs':'avg_acs'})
        trend = agg[['label','avg_acs','kda']]
        
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

    # Agent breakdowns and map summaries
    top_agent = None
    agents_df = pd.DataFrame()
    maps_df_summary = pd.DataFrame()
    if not stats.empty and 'agent' in stats.columns:
        ag = stats.groupby('agent').agg(
            maps=('match_id','nunique'),
            avg_acs=('acs','mean'),
            kills=('kills','sum'),
            deaths=('deaths','sum'),
            assists=('assists','sum')
        ).reset_index()
        ag['kda'] = ag['kills'] / ag['deaths'].replace(0, 1)
        ag = ag.sort_values(['maps','avg_acs'], ascending=[False, False])
        agents_df = ag
        if not ag.empty:
            top_agent = str(ag.iloc[0]['agent'])
    if not stats.empty and ('map_name' in stats.columns or 'map_index' in stats.columns):
        key_col = 'map_name' if 'map_name' in stats.columns and stats['map_name'].notna().any() else 'map_index'
        ms = stats.groupby(key_col).agg(avg_acs=('acs','mean'), maps=('match_id','nunique')).reset_index()
        ms = ms.sort_values(['avg_acs','maps'], ascending=[False, False])
        ms['map_label'] = ms[key_col].apply(lambda x: str(x) if key_col=='map_name' else f"Map {int(x)+1}")
        maps_df_summary = ms

    def _safe(v):
        try:
            x = float(v)
            if math.isnan(x):
                return 0.0
            return x
        except Exception:
            return 0.0
    # Sanitize NaN -> 0 for benchmark values
    pm_k = (total_k / max(games,1))
    pm_d = (total_d / max(games,1))
    pm_a = (total_a / max(games,1))
    def _safe(v):
        try:
            x = float(v)
            if math.isnan(x):
                return 0.0
            return x
        except Exception:
            return 0.0
    return {
        'info': info.iloc[0].to_dict(),
        'display_name': display_name,
        'games': int(games),
        'avg_acs': round(avg_acs, 1),
        'total_kills': total_k,
        'total_deaths': total_d,
        'total_assists': total_a,
        'kd_ratio': round(kd, 2),
        'top_agent': top_agent,
        'agents': agents_df,
        'maps_summary': maps_df_summary,
        'sr_avg_acs': round(_safe(bench.get('r_acs')), 1),
        'sr_k': round(_safe(bench.get('r_k')), 2),
        'sr_d': round(_safe(bench.get('r_d')), 2),
        'sr_a': round(_safe(bench.get('r_a')), 2),
        'lg_avg_acs': round(_safe(bench.get('lg_acs')), 1),
        'lg_k': round(_safe(bench.get('lg_k')), 2),
        'lg_d': round(_safe(bench.get('lg_d')), 2),
        'lg_a': round(_safe(bench.get('lg_a')), 2),
        'bench_meta': {
            'has_bench': bool(isinstance(bench, pd.Series)),
            'sr_nonzero': bool((_safe(bench.get('r_acs')) + _safe(bench.get('r_k')) + _safe(bench.get('r_d')) + _safe(bench.get('r_a'))) > 0),
            'lg_nonzero': bool((_safe(bench.get('lg_acs')) + _safe(bench.get('lg_k')) + _safe(bench.get('lg_d')) + _safe(bench.get('lg_a'))) > 0)
        },
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
    conn.execute("INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (%s, %s, %s, 1, %s)", (username, ph, salt, role))
    conn.commit()
    conn.close()

def create_admin_with_role(username, password, role):
    salt, ph = hash_password(password)
    conn = get_conn()
    conn.execute("INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (%s, %s, %s, 1, %s)", (username, ph, salt, role))
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
    is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
    ignore_clause = "ON CONFLICT DO NOTHING" if is_postgres else "OR IGNORE"
    
    if su and sp:
        row = c.execute("SELECT id, role FROM admins WHERE username=%s", (su,)).fetchone()
        if not row:
            salt, ph = hash_password(sp)
            c.execute(
                f"INSERT {ignore_clause} INTO admins (username, password_hash, salt, is_active, role) VALUES (%s, %s, %s, 1, %s)",
                (su, ph, salt, sr)
            )
        else:
            if row[1] != sr:
                c.execute("UPDATE admins SET role=%s WHERE id=%s", (sr, int(row[0])))
    su2 = get_secret("ADMIN2_USER")
    sp2 = get_secret("ADMIN2_PWD")
    sr2 = get_secret("ADMIN2_ROLE", "admin")
    if su2 and sp2:
        row2 = c.execute("SELECT id FROM admins WHERE username=%s", (su2,)).fetchone()
        if not row2:
            salt2, ph2 = hash_password(sp2)
            c.execute(
                "INSERT INTO admins (username, password_hash, salt, is_active, role) VALUES (%s, %s, %s, 1, %s)",
                (su2, ph2, salt2, sr2)
            )
    
    if should_close:
        conn.commit()
        conn.close()

def authenticate(username, password):
    conn = get_conn()
    row = conn.execute("SELECT username, password_hash, salt, role FROM admins WHERE username=%s AND is_active=1", (username,)).fetchone()
    conn.close()
    if not row:
        return None
    u, ph, salt, role = row
    if verify_password(password, salt, ph):
        return {"username": u, "role": role}
    return None

def upsert_match_maps(match_id, maps_data):
    # Try Supabase SDK First
    if supabase:
        try:
            for m in maps_data:
                item = {
                    "match_id": int(match_id),
                    "map_index": int(m['map_index']),
                    "map_name": m['map_name'],
                    "team1_rounds": int(m['team1_rounds']),
                    "team2_rounds": int(m['team2_rounds']),
                    "winner_id": int(m['winner_id']) if m['winner_id'] else None,
                    "is_forfeit": int(m.get('is_forfeit', 0))
                }
                # Supabase SDK upsert handles conflict based on unique constraints (match_id, map_index)
                supabase.table("match_maps").upsert(item).execute()
            return True
        except Exception:
            pass

    # Fallback to SQL (SQLite)
    conn = get_conn()
    try:
        c = conn.cursor()
        for m in maps_data:
            c.execute("SELECT id FROM match_maps WHERE match_id=%s AND map_index=%s", (match_id, m['map_index']))
            ex = c.fetchone()
            if ex:
                c.execute(
                    "UPDATE match_maps SET map_name=%s, team1_rounds=%s, team2_rounds=%s, winner_id=%s, is_forfeit=%s WHERE id=%s",
                    (m['map_name'], m['team1_rounds'], m['team2_rounds'], m['winner_id'], m.get('is_forfeit', 0), ex[0])
                )
            else:
                c.execute(
                    "INSERT INTO match_maps (match_id, map_index, map_name, team1_rounds, team2_rounds, winner_id, is_forfeit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (match_id, m['map_index'], m['map_name'], m['team1_rounds'], m['team2_rounds'], m['winner_id'], m.get('is_forfeit', 0))
                )
        conn.commit()
    except Exception:
        if 'conn' in locals(): conn.rollback()
    finally:
        conn.close()

@st.cache_data(ttl=900)
def _get_standings_cached():
    import pandas as pd
    import numpy as np
    
    teams_df = pd.DataFrame()
    matches_df = pd.DataFrame()
    
    # Try Supabase SDK First
    if supabase:
        try:
            # Fetch teams
            res_teams = supabase.table("teams").select("id, name, group_name, logo_path").execute()
            if res_teams.data:
                teams_df = pd.DataFrame(res_teams.data)
                
            # Fetch all matches from Supabase and join maps separately
            res_matches = supabase.table("matches").select("id, team1_id, team2_id, match_type, status, winner_id, format, week, score_t1, score_t2, maps_played, is_forfeit").execute()
            if res_matches.data:
                matches_df = pd.DataFrame(res_matches.data)
                if not matches_df.empty:
                    # Exclude playoffs
                    matches_df = matches_df[matches_df['match_type'].fillna('').str.lower() != 'playoff']
                    ids = matches_df['id'].tolist()
                    res_maps = supabase.table("match_maps").select("match_id, map_index, team1_rounds, team2_rounds, winner_id").in_("match_id", ids).execute()
                    if res_maps.data:
                        maps_df = pd.DataFrame(res_maps.data)
                        if not maps_df.empty:
                            # Aggregate rounds per match
                            agg = maps_df.groupby('match_id').agg({'team1_rounds':'sum','team2_rounds':'sum'}).reset_index()
                            agg.columns = ['id','agg_t1_rounds','agg_t2_rounds']
                            matches_df = matches_df.merge(agg, on='id', how='left')
                            # Count map wins per match per team via winner_id
                            cnt = maps_df.groupby(['match_id','winner_id']).size().reset_index(name='win_count')
                            # Merge counts for team1
                            m_t1 = matches_df.merge(cnt, left_on=['id','team1_id'], right_on=['match_id','winner_id'], how='left')
                            matches_df['wins_t1'] = m_t1['win_count'].fillna(0).astype(int)
                            # Merge counts for team2
                            m_t2 = matches_df.merge(cnt, left_on=['id','team2_id'], right_on=['match_id','winner_id'], how='left')
                            matches_df['wins_t2'] = m_t2['win_count'].fillna(0).astype(int)
        except Exception as e:
            # fall through to SQL if SDK fails
            pass

    # Fallback to SQL (SQLite) if SDK didn't provide data
    if teams_df.empty:
        conn = get_conn()
        try:
            teams_df = pd.read_sql_query("SELECT id, name, group_name, logo_path FROM teams", conn)
            # Join with match_maps to get round scores for BO1
            matches_df = pd.read_sql_query("""
                SELECT m.*, mm.team1_rounds, mm.team2_rounds 
                FROM matches m
                LEFT JOIN match_maps mm ON m.id = mm.match_id AND mm.map_index = 0
                WHERE m.status='completed' AND m.match_type='regular' AND (UPPER(m.format)='BO1' OR m.format IS NULL)
            """, conn)
        except Exception:
            conn.close()
            return pd.DataFrame()
        conn.close()
    
    if teams_df.empty:
        return pd.DataFrame()
    
    # Pre-calculate logo display safety to cache it
    # Build Supabase Storage URL for team logos based on team name
    def _safe_team_filename(name):
        nm = str(name or "").strip()
        nm = re.sub(r"[^A-Za-z0-9]+", "_", nm)
        nm = re.sub(r"_+", "_", nm).strip("_")
        return nm + ".png"
    base_url = str(get_secret("SUPABASE_URL", "")).strip('"').strip("'")
    if base_url:
        teams_df['logo_display'] = teams_df['name'].apply(lambda n: f"{base_url}/storage/v1/object/public/teams/{_safe_team_filename(n)}")
    else:
        teams_df['logo_display'] = None

    exclude_ids = set(teams_df[teams_df['name'].isin(['FAT1','FAT2'])]['id'].tolist())
    if exclude_ids:
        teams_df = teams_df[~teams_df['id'].isin(exclude_ids)]
        if not matches_df.empty:
            matches_df = matches_df[~(matches_df['team1_id'].isin(exclude_ids) | matches_df['team2_id'].isin(exclude_ids))]
    
    # Initialize stats using vectorization
    if matches_df.empty:
        for col in ['Wins', 'Losses', 'PD', 'Points', 'Points Against', 'Played']:
            teams_df[col] = 0
        return teams_df

    # Calculate match-level stats
    # Only count matches that are effectively played: completed OR have rounds/scores/forfeit/maps_played
    m = matches_df.copy()
    if 'status' in m.columns:
        m['status'] = m['status'].astype(str).str.lower()
    # Coerce types used in comparisons
    if 'maps_played' in m.columns:
        m['maps_played'] = pd.to_numeric(m['maps_played'], errors='coerce').fillna(0)
    if 'is_forfeit' in m.columns:
        m['is_forfeit'] = pd.to_numeric(m['is_forfeit'], errors='coerce').fillna(0)
    played_mask = (
        (m['status'] == 'completed') if 'status' in m.columns else False
    ) | (
        (m[['agg_t1_rounds','agg_t2_rounds']].sum(axis=1) > 0) if ('agg_t1_rounds' in m.columns and 'agg_t2_rounds' in m.columns) else False
    ) | (
        (m[['score_t1','score_t2']].sum(axis=1) > 0) if ('score_t1' in m.columns and 'score_t2' in m.columns) else False
    ) | (
        (m['maps_played'] > 0) if 'maps_played' in m.columns else False
    ) | (
        (m['is_forfeit'] == 1) if 'is_forfeit' in m.columns else False
    )
    try:
        m = m[played_mask]
    except Exception:
        pass
    
    # Ensure scores/rounds are numeric to prevent alignment/broadcasting errors
    cols_to_fix = ['score_t1', 'score_t2', 'agg_t1_rounds', 'agg_t2_rounds']
    for col in cols_to_fix:
        if col in m.columns:
            m[col] = pd.to_numeric(m[col], errors='coerce').fillna(0)
    # Ensure IDs are numeric and valid
    for id_col in ['id','team1_id','team2_id']:
        if id_col in m.columns:
            m[id_col] = pd.to_numeric(m[id_col], errors='coerce')
    if 'team1_id' in m.columns and 'team2_id' in m.columns:
        m = m[(m['team1_id'].notna()) & (m['team2_id'].notna())]
    
    # For BO1, if we have map rounds, use them instead of map wins for points/RD
    if 'agg_t1_rounds' in m.columns and 'agg_t2_rounds' in m.columns:
        if 'score_t1' not in m.columns:
            m['score_t1'] = 0
        if 'score_t2' not in m.columns:
            m['score_t2'] = 0
        m['score_t1'] = np.where(m['agg_t1_rounds'] > 0, m['agg_t1_rounds'], m['score_t1'])
        m['score_t2'] = np.where(m['agg_t2_rounds'] > 0, m['agg_t2_rounds'], m['score_t2'])
    # If we have map win counts, use them when scores are zero
    if 'wins_t1' in m.columns:
        m['wins_t1'] = pd.to_numeric(m['wins_t1'], errors='coerce').fillna(0).astype(int)
        m['score_t1'] = np.where((m['score_t1'] == 0) & (m['wins_t1'] > 0), m['wins_t1'], m['score_t1'])
    if 'wins_t2' in m.columns:
        m['wins_t2'] = pd.to_numeric(m['wins_t2'], errors='coerce').fillna(0).astype(int)
        m['score_t2'] = np.where((m['score_t2'] == 0) & (m['wins_t2'] > 0), m['wins_t2'], m['score_t2'])
    
    # Points for Team 1
    m['p1'] = np.where(m['score_t1'] > m['score_t2'], 15, np.minimum(m['score_t1'], 12))
    # Points for Team 2
    m['p2'] = np.where(m['score_t2'] > m['score_t1'], 15, np.minimum(m['score_t2'], 12))
    
    # Wins/Losses
    m['t1_win'] = (m['score_t1'] > m['score_t2']).astype(int)
    m['t2_win'] = (m['score_t2'] > m['score_t1']).astype(int)
    
    # Reshape to team-level
    t1_stats = m.groupby('team1_id').agg({
        't1_win': 'sum', 't2_win': 'sum', 'p1': 'sum', 'p2': 'sum', 'id': 'count'
    }).rename(columns={'t1_win': 'Wins', 't2_win': 'Losses', 'p1': 'Points', 'p2': 'Points Against', 'id': 'Played'})
    
    t2_stats = m.groupby('team2_id').agg({
        't2_win': 'sum', 't1_win': 'sum', 'p2': 'sum', 'p1': 'sum', 'id': 'count'
    }).rename(columns={'t2_win': 'Wins', 't1_win': 'Losses', 'p2': 'Points', 'p1': 'Points Against', 'id': 'Played'})

    # Combine stats
    combined = pd.concat([t1_stats, t2_stats]).groupby(level=0).sum()
    combined['PD'] = combined['Points'] - combined['Points Against']
    
    # Merge with teams_df
    df = teams_df.merge(combined, left_on='id', right_index=True, how='left').fillna(0)
    
    # Ensure correct types for numeric columns
    for col in ['Wins', 'Losses', 'PD', 'Points', 'Points Against', 'Played']:
        df[col] = df[col].astype(int)
        
    return df.sort_values(by=['Points', 'PD'], ascending=[False, False])

def get_standings():
    # Performance fix: Always use cache. Bypassing cache via .run() causes global lag.
    # Cache invalidation should typically happen via actions (mutations), not read checks.
    return _get_standings_cached()
@st.cache_data(ttl=600)
def _team_name_map():
    import pandas as pd
    df = get_teams_list_full()
    if df.empty:
        return {}
    return {int(r['id']): r['name'] for _, r in df.iterrows()}
def team_name_by_id(tid):
    try:
        return _team_name_map().get(int(tid)) or f"Team {tid}"
    except Exception:
        return f"Team {tid}"
@st.cache_data(ttl=600)
def _get_scheduled_matches_df():
    import pandas as pd
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("matches").select("id, week, group_name, status, team1_id, team2_id, match_type").eq("status","scheduled").execute()
            if res.data:
                df = pd.DataFrame(res.data)
        except Exception:
            pass
    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql("SELECT id, week, group_name, status, team1_id, team2_id, match_type FROM matches WHERE status='scheduled'", conn)
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df
@st.cache_data(ttl=600)
def get_remaining_matches_counts():
    import pandas as pd
    sm = _get_scheduled_matches_df()
    if sm.empty:
        return pd.DataFrame(columns=["team_id","remaining"])
    rows = []
    for _, r in sm.iterrows():
        rows.append({"team_id": int(r["team1_id"]), "remaining": 1})
        rows.append({"team_id": int(r["team2_id"]), "remaining": 1})
    df = pd.DataFrame(rows)
    return df.groupby("team_id").sum().reset_index()
def annotate_elimination_and_races(df):
    import pandas as pd
    rem = get_remaining_matches_counts()
    df = df.copy()
    df["remaining"] = df["id"].apply(lambda t: int(rem[rem["team_id"]==int(t)]["remaining"].iloc[0]) if not rem.empty and int(t) in rem["team_id"].astype(int).tolist() else 0)
    out = []
    races = []
    for grp in sorted(df["group_name"].unique()):
        gd = df[df["group_name"]==grp].sort_values(["Points","PD"], ascending=[False,False]).reset_index(drop=True)
        sixth_pts = int(gd.iloc[5]["Points"]) if len(gd) >= 6 else 0
        for i, r in enumerate(gd.itertuples()):
            max_pts = int(r.Points) + int(r.remaining) * 15
            eliminated = max_pts < sixth_pts
            out.append({"id": int(r.id), "eliminated": eliminated})
            if int(r.remaining)==1 and i+1>6 and (int(r.Points)+15)>=sixth_pts:
                races.append({"group": grp, "team_id": int(r.id)})
    adf = pd.DataFrame(out)
    df = df.merge(adf, on="id", how="left")
    return df, races
def build_standings_table_html(group_df):
    rows = []
    sorted_grp = group_df[['name','Played','Wins','Losses','Points','PD','remaining','eliminated']].sort_values(['Points','PD'], ascending=False).reset_index(drop=True)
    for idx, r in sorted_grp.itertuples():
        rank = idx + 1
        color = "rgba(255,255,255,0.03)"
        border = "transparent"
        if rank <= 2:
            border = "#2ECC71"
        elif 3 <= rank <= 6:
            border = "var(--primary-blue)"
        elif bool(r.eliminated):
            border = "var(--primary-red)"
        rows.append(f"<tr style='border-left:4px solid {border};'><td>{rank}</td><td>{html.escape(str(r.name))}</td><td>{int(r.Played)}</td><td>{int(r.Wins)}</td><td>{int(r.Losses)}</td><td>{int(r.PD)}</td><td>{int(r.Points)}</td><td>{int(r.remaining)}</td></tr>")
    return "<table class='valorant-table'><thead><tr><th>Rank</th><th>Team</th><th>Played</th><th>W</th><th>L</th><th>PD</th><th>PTS</th><th>Remaining</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
@st.cache_data(ttl=900)
def _get_player_leaderboard_cached():
    import pandas as pd
    df = pd.DataFrame()
    
    # Try Supabase SDK First
    if supabase:
        try:
            # 1. Get completed matches
            res_m = supabase.table("matches").select("id").eq("status", "completed").execute()
            comp_ids = [m['id'] for m in res_m.data] if res_m.data else []
            
            if comp_ids:
                # 2. Get stats for those matches
                res_s = supabase.table("match_stats_map")\
                    .select("player_id, match_id, acs, kills, deaths, assists")\
                    .in_("match_id", comp_ids)\
                    .execute()
                
                if res_s.data:
                    stats_df = pd.DataFrame(res_s.data)
                    # 3. Get players and teams
                    res_p = supabase.table("players").select("id, name, riot_id, default_team_id").execute()
                    res_t = supabase.table("teams").select("id, tag").execute()
                    
                    if res_p.data:
                        pdf = pd.DataFrame(res_p.data)
                        tdf = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame(columns=['id', 'tag'])
                        
                        # Join
                        m1 = stats_df.merge(pdf, left_on='player_id', right_on='id')
                        m2 = m1.merge(tdf, left_on='default_team_id', right_on='id', how='left')
                        
                        # Aggregate
                        df = m2.groupby(['player_id', 'name', 'riot_id', 'tag']).agg({
                            'match_id': 'nunique',
                            'acs': 'mean',
                            'kills': 'sum',
                            'deaths': 'sum',
                            'assists': 'sum'
                        }).reset_index()
                        
                        df.columns = ['player_id', 'name', 'riot_id', 'team', 'games', 'avg_acs', 'total_kills', 'total_deaths', 'total_assists']
                        df = df[df['games'] > 0]
        except Exception:
            pass

    # Supabase-only: no SQLite fallback
    
    if not df.empty:
        # Format name to include Riot ID if available
        df['name'] = df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
        df = df.drop(columns=['riot_id'])
        df['kd_ratio'] = df['total_kills'] / df['total_deaths'].replace(0, 1)
        df['avg_acs'] = df['avg_acs'].round(1)
        df['kd_ratio'] = df['kd_ratio'].round(2)
    return df.sort_values('avg_acs', ascending=False)

    return df.sort_values('avg_acs', ascending=False)

def get_player_leaderboard():
    return _get_player_leaderboard_cached()

@st.cache_data(ttl=60)
def get_week_matches(week):
    import pandas as pd
    df = pd.DataFrame()
    
    if supabase:
        try:
            res = supabase.table("matches")\
                .select("*, t1:teams!team1_id(name), t2:teams!team2_id(name)")\
                .order("id")\
                .execute()
            if res.data:
                m_list = []
                for item in res.data:
                    item['t1_name'] = item.get('t1', {}).get('name')
                    item['t2_name'] = item.get('t2', {}).get('name')
                    item['t1_id'] = item.get('team1_id')
                    item['t2_id'] = item.get('team2_id')
                    m_list.append(item)
                temp_df = pd.DataFrame(m_list)
                if not temp_df.empty:
                    def _eq_week(x):
                        try:
                            return int(x) == int(week)
                        except:
                            return str(x) == str(week)
                    def _not_playoff(x):
                        return str(x).lower() != 'playoff'
                    df = temp_df[temp_df['week'].apply(_eq_week) & temp_df['match_type'].apply(_not_playoff)]
                    if not df.empty:
                        ids = df['id'].tolist()
                        res_maps = supabase.table("match_maps").select("match_id, map_index, team1_rounds, team2_rounds").in_("match_id", ids).execute()
                        if res_maps.data:
                            maps_df = pd.DataFrame(res_maps.data)
                            if not maps_df.empty:
                                first_maps = maps_df.sort_values('map_index').groupby('match_id').first().reset_index()
                                first_maps = first_maps.rename(columns={'match_id':'id'})
                                df = df.merge(first_maps[['id','team1_rounds','team2_rounds']], on='id', how='left')
        except Exception:
            pass

    # Supabase-only: no SQLite fallback

    if not df.empty and 'team1_rounds' in df.columns:
        is_bo1 = (df['format'].str.upper() == 'BO1') | (df['format'].isna())
        df.loc[is_bo1 & df['team1_rounds'].notna(), 'score_t1'] = df.loc[is_bo1 & df['team1_rounds'].notna(), 'team1_rounds']
        df.loc[is_bo1 & df['team2_rounds'].notna(), 'score_t2'] = df.loc[is_bo1 & df['team2_rounds'].notna(), 'team2_rounds']
        df['score_t1'] = pd.to_numeric(df['score_t1'], errors='coerce').fillna(0).astype(int)
        df['score_t2'] = pd.to_numeric(df['score_t2'], errors='coerce').fillna(0).astype(int)
    return df

def parse_schedule_text(text, week):
    lines = text.split('\n')
    current_group = None
    teams_list = get_teams_list()
    name_to_id = {r['name'].lower(): r['id'] for _, r in teams_list.iterrows()}
    matches_to_add = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        group_match = re.match(r'^[—\-]+\s*(.+?)\s*[—\-]+$', line)
        if group_match:
            current_group = group_match.group(1).strip()
            continue
        if " vs " in line:
            parts = line.split(" vs ")
            if len(parts) == 2:
                t1_name = parts[0].strip()
                t2_name = parts[1].strip()
                t1_id = name_to_id.get(t1_name.lower())
                t2_id = name_to_id.get(t2_name.lower())
                if t1_id and t2_id:
                    matches_to_add.append({
                        "week": week,
                        "group": current_group if current_group else "Unknown",
                        "t1_id": t1_id,
                        "t2_id": t2_id,
                        "t1_name": t1_name,
                        "t2_name": t2_name
                    })
                else:
                    try:
                        st.warning(f"Unrecognized team name(s): '{t1_name}' (found: {t1_id is not None}), '{t2_name}' (found: {t2_id is not None})")
                    except Exception:
                        pass
    return matches_to_add
@st.cache_data(ttl=300)
def get_playoff_matches():
    import pandas as pd
    df = pd.DataFrame()
    
    if supabase:
        try:
            res = supabase.table("matches")\
                .select("*, t1:teams!team1_id(name), t2:teams!team2_id(name)")\
                .eq("match_type", "playoff")\
                .order("playoff_round", desc=False)\
                .order("bracket_pos", desc=False)\
                .execute()
            if res.data:
                m_list = []
                for item in res.data:
                    item['t1_name'] = item.get('t1', {}).get('name')
                    item['t2_name'] = item.get('t2', {}).get('name')
                    item['t1_id'] = item.get('team1_id')
                    item['t2_id'] = item.get('team2_id')
                    m_list.append(item)
                df = pd.DataFrame(m_list)
                if not df.empty:
                    ids = df['id'].tolist()
                    res_maps = supabase.table("match_maps").select("match_id, map_index, team1_rounds, team2_rounds, winner_id").in_("match_id", ids).execute()
                    if res_maps.data:
                        maps_df = pd.DataFrame(res_maps.data)
                        if not maps_df.empty:
                            first_maps = maps_df.sort_values('map_index').groupby('match_id').first().reset_index()
                            first_maps = first_maps.rename(columns={'match_id':'id'})
                            df = df.merge(first_maps[['id','team1_rounds','team2_rounds']], on='id', how='left')
        except Exception:
            pass

    # Supabase-only: no SQLite fallback

    if not df.empty and 'team1_rounds' in df.columns:
        is_bo1 = (df['format'].str.upper() == 'BO1') | (df['format'].isna())
        df.loc[is_bo1 & df['team1_rounds'].notna(), 'score_t1'] = df.loc[is_bo1 & df['team1_rounds'].notna(), 'team1_rounds']
        df.loc[is_bo1 & df['team2_rounds'].notna(), 'score_t2'] = df.loc[is_bo1 & df['team2_rounds'].notna(), 'team2_rounds']
        df['score_t1'] = pd.to_numeric(df['score_t1'], errors='coerce').fillna(0).astype(int)
        df['score_t2'] = pd.to_numeric(df['score_t2'], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=300)
def get_match_maps(match_id):
    import pandas as pd
    df = pd.DataFrame()
    
    if supabase:
        try:
            res = supabase.table("match_maps")\
                .select("*")\
                .eq("match_id", match_id)\
                .order("map_index")\
                .execute()
            if res.data:
                df = pd.DataFrame(res.data)
        except Exception:
            pass

    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql_query(
                "SELECT map_index, map_name, team1_rounds, team2_rounds, winner_id, is_forfeit FROM match_maps WHERE match_id=%s ORDER BY map_index",
                conn,
                params=(match_id,),
            )
        except Exception:
            conn.close()
            return pd.DataFrame()
        conn.close()
    return df

@st.cache_data(ttl=900)
def _get_all_players_directory_cached(format_names=True):
    import pandas as pd
    df = pd.DataFrame()
    
    if supabase:
        try:
            res = supabase.table("players")\
                .select("id, name, riot_id, rank, teams!default_team_id(name)")\
                .order("name")\
                .execute()
            if res.data:
                l = []
                for r in res.data:
                    item = {
                        'id': r.get('id'),
                        'name': r.get('name'),
                        'riot_id': r.get('riot_id'),
                        'rank': r.get('rank'),
                        'team': r.get('teams', {}).get('name') if r.get('teams') else None
                    }
                    l.append(item)
                df = pd.DataFrame(l)
        except Exception:
            pass

    if df.empty:
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
    
    if not df.empty and format_names:
        df['name'] = df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
    
    return df

def get_all_players_directory(format_names=True):
    return _get_all_players_directory_cached(format_names)

@st.cache_data(ttl=300)
def _get_map_stats_cached(match_id, map_index, team_id):
    import pandas as pd
    df = pd.DataFrame()
    
    if supabase:
        try:
            res = supabase.table("match_stats_map")\
                .select("*, players(name, riot_id)")\
                .eq("match_id", match_id)\
                .eq("map_index", map_index)\
                .eq("team_id", team_id)\
                .execute()
            if res.data:
                l = []
                for r in res.data:
                    item = r.copy()
                    p = r.get('players', {})
                    item['name'] = p.get('name')
                    item['riot_id'] = p.get('riot_id')
                    l.append(item)
                df = pd.DataFrame(l)
                if not df.empty:
                    df['name'] = df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
                    df = df.drop(columns=['riot_id'])
        except Exception:
            pass

    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql(
                """
                SELECT p.name, p.riot_id, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub 
                FROM match_stats_map ms 
                JOIN players p ON ms.player_id=p.id 
                WHERE ms.match_id=%s AND ms.map_index=%s AND ms.team_id=%s
                """, 
                conn, 
                params=(int(match_id), int(map_index), int(team_id))
            )
            if not df.empty:
                df['name'] = df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
                df = df.drop(columns=['riot_id'])
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df

def get_map_stats(match_id, map_index, team_id):
    if not should_use_cache():
        return _get_map_stats_cached.run(match_id, map_index, team_id)
    return _get_map_stats_cached(match_id, map_index, team_id)

@st.cache_data(ttl=900)
def _get_team_history_counts_cached():
    import pandas as pd
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("team_history").select("team_id, season_id").execute()
            if res.data:
                temp = pd.DataFrame(res.data)
                df = temp.groupby('team_id')['season_id'].nunique().reset_index(name='season_count')
        except Exception:
            pass
            
    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql_query(
                "SELECT team_id, COUNT(DISTINCT season_id) as season_count FROM team_history GROUP BY team_id",
                conn,
            )
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df

def get_team_history_counts():
    if not should_use_cache():
        return _get_team_history_counts_cached.run()
    return _get_team_history_counts_cached()

@st.cache_data(ttl=900)
def _get_all_players_cached():
    import pandas as pd
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("players").select("id, name, riot_id, rank, default_team_id").order("name").execute()
            if res.data:
                df = pd.DataFrame(res.data)
        except Exception:
            pass
            
    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql("SELECT id, name, riot_id, rank, default_team_id FROM players ORDER BY name", conn)
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df

def get_all_players():
    if not should_use_cache():
        return _get_all_players_cached.run()
    return _get_all_players_cached()

@st.cache_data(ttl=900)
def _get_teams_list_full_cached():
    import pandas as pd
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("teams").select("id, name, tag, group_name, logo_path").order("name").execute()
            if res.data:
                df = pd.DataFrame(res.data)
        except Exception:
            pass
            
    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql("SELECT id, name, tag, group_name, logo_path FROM teams ORDER BY name", conn)
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df

def get_teams_list_full():
    if not should_use_cache():
        return _get_teams_list_full_cached.run()
    return _get_teams_list_full_cached()

@st.cache_data(ttl=300)
def get_teams_list():
    import pandas as pd
    df = get_teams_list_full()
    return df[['id', 'name']] if not df.empty else pd.DataFrame(columns=['id', 'name'])

@st.cache_data(ttl=3600)
def _get_agents_list_cached():
    import pandas as pd
    if supabase:
        try:
            res = supabase.table("agents").select("name").order("name").execute()
            if res.data:
                return [r['name'] for r in res.data]
        except Exception:
            pass
            
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT name FROM agents ORDER BY name", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df['name'].tolist() if not df.empty else []

def get_agents_list():
    if not should_use_cache():
        return _get_agents_list_cached.run()
    return _get_agents_list_cached()

@st.cache_data(ttl=900)
def _get_match_weeks_cached():
    import pandas as pd
    if supabase:
        try:
            res = supabase.table("matches").select("week").execute()
            if res.data:
                return sorted(list(set([r['week'] for r in res.data if r['week'] is not None])))
        except Exception:
            pass
            
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT DISTINCT week FROM matches ORDER BY week", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df['week'].tolist() if not df.empty else []

def get_match_weeks():
    if not should_use_cache():
        return _get_match_weeks_cached.run()
    return _get_match_weeks_cached()

@st.cache_data(ttl=300)
def get_match_maps_cached(match_id):
    return get_match_maps(match_id)

@st.cache_data(ttl=900)
def _get_completed_matches_cached():
    import pandas as pd
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("matches").select("*").eq("status", "completed").execute()
            if res.data:
                df = pd.DataFrame(res.data)
        except Exception:
            pass
            
    if df.empty:
        conn = get_conn()
        try:
            df = pd.read_sql("SELECT * FROM matches WHERE status='completed'", conn)
        except Exception:
            df = pd.DataFrame()
        finally:
            conn.close()
    return df

def get_completed_matches():
    if not should_use_cache():
        return _get_completed_matches_cached.run()
    return _get_completed_matches_cached()

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
        active_users = get_active_user_count()
        admin_sess = get_active_admin_session()
        st.markdown("""<div class="portal-container">
<h1 class="portal-header">VALORANT S23 PORTAL</h1>
<p class="portal-subtitle">OFFICIAL TOURNAMENT DASHBOARD</p>
<div class="status-grid">
<div class="status-indicator status-online">● SYSTEM ONLINE</div>
<div class="status-indicator status-online">● ACTIVE USERS: """ + str(active_users) + """</div>
<div class="status-indicator """ + ("status-online" if admin_sess else "status-offline") + """">● ADMIN: """ + ("ONLINE" if admin_sess else "OFFLINE") + """</div>
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
        
        # Check for active admin sessions first
        active_admin = get_active_admin_session()
        
        if active_admin:
            st.error(f"Access Denied: Someone is actively working on the admin panel.")
            st.warning(f"Active User: {active_admin[0]} ({active_admin[1]})")
            
            with st.expander("🔍 UNLOCK ACCESS (Click here if you are stuck)"):
                curr_ip = get_visitor_ip()
                st.write(f"**Your Current ID:** `{curr_ip}`")
                st.write(f"**Blocking ID:** `{active_admin[2]}`")
                st.write("---")
                st.write("### Option 1: Unlock your specific ID")
                if st.button("🔓 UNLOCK MY ID", use_container_width=True):
                    try:
                        conn = get_conn()
                        conn.execute("DELETE FROM session_activity WHERE ip_address = %s AND (role = 'admin' OR role = 'dev')", (curr_ip,))
                        conn.commit()
                        conn.close()
                        st.success("Your ID has been cleared. Try logging in below.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                
                st.write("---")
                st.write("### Option 2: Force Unlock Everything (Requires Special Token)")
                force_token = st.text_input("Force Unlock Token", type="password", key="force_token_input")
                if st.button("☢️ FORCE UNLOCK EVERYTHING", use_container_width=True):
                    env_tok = get_secret("FORCE_UNLOCK_TOKEN", None)
                    # If FORCE_UNLOCK_TOKEN is not set, fallback to ADMIN_LOGIN_TOKEN as a safety measure
                    if env_tok is None:
                        env_tok = get_secret("ADMIN_LOGIN_TOKEN", None)
                        
                    if env_tok and hmac.compare_digest(force_token or "", env_tok):
                        try:
                            conn = get_conn()
                            conn.execute("DELETE FROM session_activity WHERE role = 'admin' OR role = 'dev'")
                            conn.commit()
                            conn.close()
                            st.success("ALL admin sessions cleared. You can now login.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        st.error("Invalid Force Unlock Token.")
            st.markdown("---")
        
        # EMERGENCY CLEAR (IP-based) - Removed as it is now inside the expander for cleaner UI
        
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
                # Check for active admin sessions first
                active_admin = get_active_admin_session()
                if active_admin:
                    st.error(f"Access Denied: Someone is actively working on the admin panel.")
                    st.warning(f"Active User: {active_admin[0]} ({active_admin[1]})")
                else:
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
                            # Update activity immediately with new role
                            track_user_activity()
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
    if "Playoffs" not in pages:
        pages.insert(pages.index("Admin Panel") if "Admin Panel" in pages else len(pages), "Playoffs")
    if "Admin Panel" not in pages:
        pages.append("Admin Panel")
    if "Diagnostics" not in pages:
        pages.append("Diagnostics")

# Top Navigation Bar
st.markdown('<div class="nav-wrapper"><div class="nav-logo">VALORANT S23 • PORTAL</div></div>', unsafe_allow_html=True)

# Navigation Layout
st.markdown('<div class="sub-nav-wrapper">', unsafe_allow_html=True)

# Define columns based on whether admin is logged in (to add logout button)
nav_cols_spec = [0.6] + [1] * len(pages)
if st.session_state['is_admin']:
    nav_cols_spec.append(0.8) # Column for logout

cols = st.columns(nav_cols_spec)

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

# Add Logout button if admin
if st.session_state['is_admin']:
    with cols[-1]:
        st.markdown('<div class="exit-btn">', unsafe_allow_html=True)
        if st.button(f"🚪 LOGOUT ({st.session_state['username']})", key="logout_btn", use_container_width=True):
            st.session_state['is_admin'] = False
            st.session_state['username'] = None
            st.session_state['app_mode'] = 'portal'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

page = st.session_state['page']

if page == "Overview & Standings":
    import pandas as pd
    st.markdown('<h1 class="main-header">OVERVIEW & STANDINGS</h1>', unsafe_allow_html=True)
    #if st.button("🔄 Refresh Data", key="refresh_overview", use_container_width=False):
    #    st.cache_data.clear()
    #    st.rerun()
    
    df = get_standings()
    if not df.empty:
        hist = get_team_history_counts()
        all_players_bench = get_all_players()
        # Pre-group rosters for efficiency
        rosters_by_team = {}
        if not all_players_bench.empty:
            all_players_bench = all_players_bench.copy()
            # Create display name for the table
            all_players_bench['display_name'] = all_players_bench.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
            for tid, group in all_players_bench.groupby('default_team_id'):
                # Keep all columns but we'll show display_name in the table
                rosters_by_team[int(tid)] = group

        df = df.merge(hist, left_on='id', right_on='team_id', how='left')
        df['season_count'] = df['season_count'].fillna(1).astype(int)
        
        df, race_candidates = annotate_elimination_and_races(df)
        groups = sorted(df['group_name'].unique())
        tab_objs = st.tabs([f"Group {g}" for g in groups])
        for tab, grp in zip(tab_objs, groups):
            with tab:
                grp_df = df[df['group_name'] == grp]
                st.markdown("<br>", unsafe_allow_html=True)
                table_html = build_standings_table_html(grp_df)
                st.markdown(table_html, unsafe_allow_html=True)
                st.caption("🏆 Top 6 teams from each group qualify for Playoffs (Top 2 get R1 BYE).")
                rc = [c for c in race_candidates if c["group"]==grp]
                if rc:
                    st.markdown("#### Playoff Races (Last Week)")
                    sm = _get_scheduled_matches_df()
                    for c in rc:
                        tid = c["team_id"]
                        row = grp_df[grp_df["id"]==tid].iloc[0] if not grp_df[grp_df["id"]==tid].empty else None
                        if row is None: continue
                        mrow = sm[(sm["status"]=="scheduled") & ((sm["team1_id"]==tid) | (sm["team2_id"]==tid))]
                        opp_id = None
                        if not mrow.empty:
                            mr = mrow.iloc[0]
                            opp_id = int(mr["team2_id"]) if int(mr["team1_id"])==tid else int(mr["team1_id"])
                        opp_name = df[df["id"]==opp_id]["name"].iloc[0] if opp_id and not df[df["id"]==opp_id].empty else "TBD"
                        st.markdown(f"""<div class="custom-card" style="margin-bottom:10px;">
<div style="font-size:0.8rem;color:var(--text-dim);">Group {html.escape(str(grp))}</div>
<div style="font-weight:bold;">{html.escape(str(row['name']))} vs {html.escape(str(opp_name))}</div>
<div style="font-size:0.8rem;">Can reach playoffs with a win if results favor.</div>
</div>""", unsafe_allow_html=True)
    else:
        st.info("No standings data available yet.")

elif page == "Matches":
    import pandas as pd
    st.markdown('<h1 class="main-header">MATCH SCHEDULE</h1>', unsafe_allow_html=True)
    week_options = [1, 2, 3, 4, 5, 6, "Playoffs"]
    week = st.selectbox("Select Week", week_options, index=0)
    
    if week == "Playoffs":
        df = get_playoff_matches()
    else:
        df = get_week_matches(week)
        
    if df.empty:
        st.info("No matches for this week.")
    else:
        if week == "Playoffs":
            st.markdown("### Playoff Brackets")
            # Group by playoff_round (1=Quarters, 2=Semis, 3=Finals etc.)
            rounds = sorted(df['playoff_round'].unique())
            cols = st.columns(len(rounds))
            for i, r_num in enumerate(rounds):
                with cols[i]:
                    r_name = {
                        1: "Round of 24",
                        2: "Round of 16",
                        3: "Quarter-Finals",
                        4: "Semi-Finals",
                        5: "Grand Finals"
                    }.get(r_num, f"Round {r_num}")
                    st.markdown(f"<h4 style='text-align: center; color: var(--primary-red);'>{r_name}</h4>", unsafe_allow_html=True)
                    # If Round 1, show BYEs
                    if r_num == 1:
                        standings = get_standings()
                        if not standings.empty:
                            # Group by group_name and get top 2
                            for g_name, g_df in standings.groupby('group_name'):
                                g_df = g_df.sort_values(['Points', 'PD'], ascending=False).head(2)
                                for team in g_df.itertuples():
                                    st.markdown(f"""<div class="custom-card" style="margin-bottom: 10px; padding: 10px; border-left: 3px solid var(--primary-blue); opacity: 0.8;">
<div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
<span style="color: var(--primary-blue); font-weight: bold;">{html.escape(str(team.name))}</span>
<span style="font-family: 'Orbitron'; color: var(--text-dim); font-size: 0.7rem;">BYE</span>
</div>
<div style="text-align: center; font-size: 0.6rem; color: var(--text-dim); margin-top: 5px;">ADVANCES TO R16</div>
</div>""", unsafe_allow_html=True)

                    r_matches = df[df['playoff_round'] == r_num].sort_values('bracket_pos')
                    for m in r_matches.itertuples():
                        winner_color_1 = "var(--primary-blue)" if m.status == 'completed' and m.winner_id == m.t1_id else "var(--text-main)"
                        winner_color_2 = "var(--primary-red)" if m.status == 'completed' and m.winner_id == m.t2_id else "var(--text-main)"
                        
                        # Use bracket label if names are TBD
                        t1_display = m.t1_name if m.t1_name else (m.bracket_label.split(' vs ')[0] if m.bracket_label and ' vs ' in m.bracket_label else "TBD")
                        t2_display = m.t2_name if m.t2_name else (m.bracket_label.split(' vs ')[1] if m.bracket_label and ' vs ' in m.bracket_label else "TBD")

                        st.markdown(f"""<div class="custom-card" style="margin-bottom: 10px; padding: 10px; border-left: 3px solid {winner_color_1 if m.winner_id == m.t1_id else winner_color_2};">
<div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
<span style="color: {winner_color_1}; font-weight: {'bold' if m.winner_id == m.t1_id else 'normal'};">{html.escape(str(t1_display))}</span>
<span style="font-family: 'Orbitron';">{int(m.score_t1) if m.status == 'completed' else '-'}</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-top: 5px;">
<span style="color: {winner_color_2}; font-weight: {'bold' if m.winner_id == m.t2_id else 'normal'};">{html.escape(str(t2_display))}</span>
<span style="font-family: 'Orbitron';">{int(m.score_t2) if m.status == 'completed' else '-'}</span>
</div>
<div style="text-align: center; font-size: 0.6rem; color: var(--text-dim); margin-top: 5px;">{html.escape(str(m.format))}</div>
</div>""", unsafe_allow_html=True)
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
                
                forfeit_badge = '<div style="text-align: center; margin-bottom: 5px;"><span style="background: rgba(255, 70, 85, 0.2); color: var(--primary-red); padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; border: 1px solid var(--primary-red);">FORFEIT</span></div>' if getattr(m, 'is_forfeit', 0) else ''
                
                st.markdown(f"""<div class="custom-card" style="border-left: 4px solid {'var(--primary-blue)' if m.score_t1 > m.score_t2 else 'var(--primary-red)'};">
{forfeit_badge}
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
    # Week selection moved from sidebar to main page
    col_wk1, col_wk2 = st.columns([1, 3])
    with col_wk1:
        week = st.selectbox("Select Week", wk_list if wk_list else [1], index=0, key="wk_sum")
    
    df = get_week_matches(week) if wk_list else pd.DataFrame()
    
    if df.empty:
        st.info("No matches for this week.")
    else:
        # Vectorized option generation
        opts = (df['t1_name'].fillna('') + " vs " + df['t2_name'].fillna('') + " (" + df['group_name'].fillna('') + ")").tolist()
        sel = st.selectbox("Select Match", list(range(len(opts))), format_func=lambda i: opts[i])
        m = df.iloc[sel]
        
        # Match Score Card
        forfeit_badge = '<div style="text-align: center; margin-bottom: 10px;"><span style="background: rgba(255, 70, 85, 0.2); color: var(--primary-red); padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; border: 1px solid var(--primary-red); letter-spacing: 2px;">FORFEIT MATCH</span></div>' if m.get('is_forfeit', 0) else ''
        
        st.markdown(f"""<div class="custom-card" style="margin-bottom: 2rem; border-bottom: 4px solid {'var(--primary-blue)' if m['score_t1'] > m['score_t2'] else 'var(--primary-red)'};">
{forfeit_badge}
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
    
    sm_df = _get_scheduled_matches_df()
    if not sm_df.empty:
        st.markdown("### 📅 Upcoming Matches Predictions")
        for wk in sorted(sm_df['week'].dropna().astype(int).unique()):
            st.markdown(f"#### Week {wk}")
            wk_df = sm_df[sm_df['week'] == wk]
            cols = st.columns(3)
            for i, r in enumerate(wk_df.itertuples()):
                with cols[i % 3]:
                    try:
                        import predictor_model
                        prob = predictor_model.predict_match(int(r.team1_id), int(r.team2_id), week=int(wk))
                    except Exception:
                        prob = 0.5
                    if prob is None:
                        prob = 0.5
                    t1_win_prob = prob * 100
                    winner = team_name_by_id(int(r.team1_id)) if t1_win_prob > 50 else team_name_by_id(int(r.team2_id))
                    conf = max(t1_win_prob, 100 - t1_win_prob)
                    color = "#2ECC71" if conf > 60 else "#F1C40F"
                    t1n = team_name_by_id(int(r.team1_id))
                    t2n = team_name_by_id(int(r.team2_id))
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 10px; margin-bottom: 10px; border-left: 4px solid {color};">
                        <div style="font-size: 0.8em; color: #aaa;">{html.escape(str(t1n))} vs {html.escape(str(t2n))}</div>
                        <div style="font-weight: bold; font-size: 1.1em; color: {color};">{html.escape(str(winner))}</div>
                        <div style="font-size: 0.9em;">{conf:.1f}% Confidence</div>
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown("---")
    
    teams_df = get_teams_list()
    matches_df = get_completed_matches()
    
    tnames = teams_df['name'].tolist() if not teams_df.empty else []
    c1, c2 = st.columns(2)
    
    # Check if user is admin or dev
    is_privileged = st.session_state.get('is_admin', False) or st.session_state.get('role') in ['admin', 'dev']
    
    t1_name = c1.selectbox("Team 1", tnames, index=0, disabled=not is_privileged)
    t2_name = c2.selectbox("Team 2", tnames, index=(1 if len(tnames)>1 else 0), disabled=not is_privileged)
    
    with st.expander("Advanced Options (Roster & Map)"):
        map_opts = ["Ascent", "Bind", "Breeze", "Fracture", "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset"]
        sel_maps = st.multiselect("Map(s) (Optional)", map_opts)
        try:
            t1_id = int(teams_df.loc[teams_df['name'] == t1_name, 'id'].iloc[0])
        except (IndexError, KeyError):
            t1_id = None
        try:
            t2_id = int(teams_df.loc[teams_df['name'] == t2_name, 'id'].iloc[0])
        except (IndexError, KeyError):
            t2_id = None
        all_players = get_all_players()
        player_map = {f"{r['name']} ({r['riot_id'] or ''})": r['id'] for _, r in all_players.iterrows()} if not all_players.empty else {}
        player_map_inv = {v: k for k, v in player_map.items()}
        t1_default = all_players[all_players['default_team_id'] == t1_id]['id'].tolist() if t1_id else []
        t2_default = all_players[all_players['default_team_id'] == t2_id]['id'].tolist() if t2_id else []
        t1_def_labels = [player_map_inv.get(pid) for pid in t1_default if pid in player_map_inv]
        t2_def_labels = [player_map_inv.get(pid) for pid in t2_default if pid in player_map_inv]
        ac1, ac2 = st.columns(2)
        with ac1:
            t1_sel = st.multiselect(f"{t1_name or 'Team 1'} Roster", list(player_map.keys()), default=t1_def_labels)
        with ac2:
            t2_sel = st.multiselect(f"{t2_name or 'Team 2'} Roster", list(player_map.keys()), default=t2_def_labels)
    
    if st.button("Predict Result", disabled=not is_privileged):
        if t1_name == t2_name:
            st.error("Select two different teams.")
        else:
            if t1_id is None or t2_id is None:
                st.error("Unrecognized team name(s). Please select valid teams.")
                st.stop()
            
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
            
            # Heuristic Score (Fallback if ML fails or data too small)
            score1 = (s1['win_rate'] * 40) + (s1['avg_score'] * 2) + (h2h_wins_t1 * 5)
            score2 = (s2['win_rate'] * 40) + (s2['avg_score'] * 2) + (h2h_wins_t2 * 5)
            
            ml_prob = None
            try:
                import predictor_model
                overrides = {
                    't1_players': [player_map[l] for l in (t1_sel if 't1_sel' in locals() else [])] if player_map else None,
                    't2_players': [player_map[l] for l in (t2_sel if 't2_sel' in locals() else [])] if player_map else None,
                    'map': sel_maps if 'sel_maps' in locals() and sel_maps else None
                }
                ml_prob = predictor_model.predict_match(t1_id, t2_id, overrides=overrides)
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
    max_games = int(df['games'].max()) if not df.empty and 'games' in df.columns else 0
    min_games = st.slider("Minimum Games Played", 0, max_games or 0, min(1, max_games) if (max_games or 0) > 0 else 0, key="leaderboard_min_games")
    if 'games' in df.columns:
        df = df[df['games'] >= min_games]
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
<h2 style="margin: 0;">{html.escape(str(prof.get('display_name', prof['info'].get('name'))))}</h2>
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
            out[['name', 'rank', 'team']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Name (Riot ID)", width="large"),
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
        all_players = all_players.copy()
        # Create display name for the table
        all_players['display_name'] = all_players.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
        for tid, group in all_players.groupby('default_team_id'):
            # Keep all columns for admin management, but we'll filter for display
            rosters_by_team[int(tid)] = group
    
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
            logo_img_html = f"<img src='data:image/png;base64,{b64}' width='60'/>" if b64 else "<div style='width:60px;height:60px;background:rgba(255,255,255,0.05);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);'>%s</div>"
            
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
                    st.dataframe(
                        roster[['display_name', 'rank']], 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={
                            "display_name": "Name",
                            "rank": "Rank"
                        }
                    )
                
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
                                    conn_u.execute("UPDATE teams SET name=%s, tag=%s, group_name=%s, logo_path=%s WHERE id=%s", (new_name, new_tag or None, new_group or None, new_logo or None, int(row.id)))
                                    conn_u.commit()
                                    conn_u.close()
                                    st.success("Team updated")
                                    st.rerun()
                    
                    with col2:
                        st.caption("Roster Management")
                        # Add player
                        unassigned = all_players[all_players['default_team_id'].isna()].copy()
                        
                        add_sel = st.selectbox(f"Add Player", [""] + unassigned['display_name'].tolist(), key=f"add_{row.id}")
                        if add_sel:
                            pid = int(unassigned[unassigned['display_name'] == add_sel].iloc[0]['id'])
                            conn_a = get_conn()
                            conn_a.execute("UPDATE players SET default_team_id=%s WHERE id=%s", (int(row.id), pid))
                            conn_a.commit()
                            conn_a.close()
                            st.success("Player added")
                            st.rerun()
                        
                        # Remove player
                        if not roster.empty:
                            rem_sel = st.selectbox(f"Remove Player", [""] + roster['display_name'].tolist(), key=f"rem_{row.id}")
                            if rem_sel:
                                pid = int(roster[roster['display_name'] == rem_sel].iloc[0]['id'])
                                conn_d = get_conn()
                                conn_d.execute("UPDATE players SET default_team_id=NULL WHERE id=%s", (pid,))
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
                1: "Round of 24", 
                2: "Round of 16", 
                3: "Quarter-finals", 
                4: "Semi-finals", 
                5: "Final"
            }[x])
            pos = c2.number_input("Bracket Position", min_value=1, max_value=8, value=1)
            fmt = c3.selectbox("Format", ["BO1", "BO3", "BO5"], index=1)
            
            c4, c5, c6 = st.columns([2, 2, 2])
            t1 = c4.selectbox("Team 1", tnames)
            t2 = c5.selectbox("Team 2", tnames)
            label = c6.text_input("Bracket Label (e.g. OMEGA#5 vs ALPHA#4)", help="Shown if teams are TBD")
            
            if st.form_submit_button("Add/Update Playoff Match"):
                conn = get_conn()
                t1_id = int(teams_df[teams_df['name'] == t1].iloc[0]['id']) if t1 else None
                t2_id = int(teams_df[teams_df['name'] == t2].iloc[0]['id']) if t2 else None
                
                # Check if exists
                existing = conn.execute("SELECT id FROM matches WHERE match_type='playoff' AND playoff_round=%s AND bracket_pos=%s", (round_idx, pos)).fetchone()
                
                if existing:
                    conn.execute("""
                        UPDATE matches SET team1_id=%s, team2_id=%s, format=%s, bracket_label=%s
                        WHERE id=%s
                    """, (t1_id, t2_id, fmt, label, existing[0]))
                else:
                    conn.execute("""
                        INSERT INTO matches (match_type, playoff_round, bracket_pos, team1_id, team2_id, format, status, score_t1, score_t2, bracket_label)
                        VALUES ('playoff', %s, %s, %s, %s, %s, 'scheduled', 0, 0, %s)
                    """, (round_idx, pos, t1_id, t2_id, fmt, label))
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
            
            # Pre-define IDs for both FF and regular logic
            t1_id_val = int(m.get('t1_id', m.get('team1_id')))
            t2_id_val = int(m.get('t2_id', m.get('team2_id')))
            
            # Match-level Forfeit
            is_match_ff = st.checkbox("Match-level Forfeit", value=bool(m.get('is_forfeit', 0)), key=f"po_match_ff_{m['id']}", help="Check if the entire match was a forfeit (13-0 result)")
            
            if is_match_ff:
                ff_winner_team = st.radio("Match Winner", [m['t1_name'], m['t2_name']], index=0 if m['score_t1'] >= m['score_t2'] else 1, horizontal=True, key="po_ff_winner")
                s1 = 13 if ff_winner_team == m['t1_name'] else 0
                s2 = 13 if ff_winner_team == m['t2_name'] else 0
                st.info(f"Forfeit Result: {m['t1_name']} {s1} - {s2} {m['t2_name']}")
                
                if st.button("Save Forfeit Playoff Match"):
                    conn_u = get_conn()
                    winner_id = t1_id_val if s1 > s2 else t2_id_val
                    conn_u.execute("UPDATE matches SET score_t1=%s, score_t2=%s, winner_id=%s, status=%s, format=%s, maps_played=%s, is_forfeit=1 WHERE id=%s", (int(s1), int(s2), winner_id, 'completed', fmt, 0, int(m['id'])))
                    # Clear any existing maps/stats if it's now a forfeit
                    conn_u.execute("DELETE FROM match_maps WHERE match_id=%s", (int(m['id']),))
                    conn_u.execute("DELETE FROM match_stats_map WHERE match_id=%s", (int(m['id']),))
                    conn_u.commit()
                    conn_u.close()
                    st.cache_data.clear()
                    st.success("Saved forfeit playoff match")
                    st.rerun()
            else:
                st.info("Match details are managed per-map below. The total match score will be automatically updated.")
                st.divider()
                st.subheader("Per-Map Scoreboard")
                fmt_constraints = {"BO1": (1,1), "BO3": (2,3), "BO5": (3,5)}
                min_maps, max_maps = fmt_constraints.get(fmt, (1,1))
                map_choice = st.selectbox("Select Map", list(range(1, max_maps+1)), index=0, key=f"po_map_choice_{m['id']}")
                map_idx = map_choice - 1
                
                # 1. Fetch existing map data for THIS map index
                existing_maps_df = get_match_maps(int(m['id']))
                existing_map = None
                if not existing_maps_df.empty:
                    rowx = existing_maps_df[existing_maps_df['map_index'] == map_idx]
                    if not rowx.empty:
                        existing_map = rowx.iloc[0]

                pre_map_name = existing_map['map_name'] if existing_map is not None else ""
                pre_map_t1 = int(existing_map['team1_rounds']) if existing_map is not None else 0
                pre_map_t2 = int(existing_map['team2_rounds']) if existing_map is not None else 0
                pre_map_win = int(existing_map['winner_id']) if existing_map is not None and pd.notna(existing_map['winner_id']) else None
                pre_map_ff = bool(existing_map['is_forfeit']) if existing_map is not None and 'is_forfeit' in existing_map else False

                # Override with scraped data if available
                scraped_map = st.session_state.get(f"scraped_data_po_{m['id']}_{map_idx}")
                if scraped_map:
                    pre_map_name = scraped_map['map_name']
                    pre_map_t1 = scraped_map['t1_rounds']
                    pre_map_t2 = scraped_map['t2_rounds']
                    if pre_map_t1 > pre_map_t2: pre_map_win = t1_id_val
                    elif pre_map_t2 > pre_map_t1: pre_map_win = t2_id_val

                # Match ID/URL input and JSON upload for automatic pre-filling
                st.write("#### 🤖 Auto-Fill from Tracker.gg")
                col_json1, col_json2 = st.columns([2, 1])
                with col_json1:
                    match_input = st.text_input("Tracker.gg Match URL or ID", key=f"po_mid_{m['id']}_{map_idx}", placeholder="https://tracker.gg/valorant/match/...")
                with col_json2:
                    if st.button("Apply Match Data", key=f"po_force_json_{m['id']}_{map_idx}", use_container_width=True):
                        if match_input:
                            # Clean Match ID
                            match_id_clean = match_input
                            if "tracker.gg" in match_input:
                                mid_match = re.search(r'match/([a-zA-Z0-9\-]+)', match_input)
                                if mid_match: match_id_clean = mid_match.group(1)
                            match_id_clean = re.sub(r'[^a-zA-Z0-9\-]', '', match_id_clean)
                        
                            json_path = os.path.join("assets", "matches", f"match_{match_id_clean}.json")
                            jsdata = None
                            source = ""
                        
                            # 1. Try local file first
                            if os.path.exists(json_path):
                                try:
                                    with open(json_path, 'r', encoding='utf-8') as f:
                                        jsdata = json.load(f)
                                    source = "Local Cache"
                                except: pass
                        
                            # 2. If not found locally, try GitHub repository
                            if not jsdata:
                                with st.spinner("Checking GitHub matches folder..."):
                                    jsdata, gh_err = fetch_match_from_github(match_id_clean)
                                    if jsdata:
                                        source = "GitHub Repository"
                                        # Save locally for next time
                                        try:
                                            if not os.path.exists(os.path.join("assets", "matches")): os.makedirs(os.path.join("assets", "matches"))
                                            with open(json_path, 'w', encoding='utf-8') as f:
                                                json.dump(jsdata, f, indent=4)
                                        except: pass

                            # 3. If still not found, attempt live scrape
                            if not jsdata:
                                with st.spinner("Fetching data from Tracker.gg..."):
                                    jsdata, err = scrape_tracker_match(match_id_clean)
                                    if jsdata:
                                        source = "Tracker.gg"
                                        if not os.path.exists("matches"): os.makedirs("matches")
                                        with open(json_path, 'w', encoding='utf-8') as f:
                                            json.dump(jsdata, f, indent=4)
                                    else:
                                        st.error(f"Live scrape failed: {err}")
                                        if gh_err: st.info(f"GitHub fetch also failed: {gh_err}")
                                        st.info("💡 **Tip:** If scraping is blocked, run the scraper script on your PC and upload the JSON file below.")
                            
                            if jsdata:
                                cur_t1_id = t1_id_val
                                cur_t2_id = t2_id_val
                                json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id, cur_t2_id)
                                st.session_state[f"ocr_po_{m['id']}_{map_idx}"] = json_suggestions
                                st.session_state[f"scraped_data_po_{m['id']}_{map_idx}"] = {'map_name': map_name, 't1_rounds': int(t1_r), 't2_rounds': int(t2_r)}
                                st.session_state[f"force_map_po_{m['id']}_{map_idx}"] = st.session_state.get(f"force_map_po_{m['id']}_{map_idx}", 0) + 1
                                st.session_state[f"force_apply_po_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_po_{m['id']}_{map_idx}", 0) + 1
                                st.success(f"Loaded {map_name} from {source}!")
                                st.rerun()

                uploaded_file = st.file_uploader("Or Upload Tracker.gg JSON", type=["json"], key=f"po_json_up_{m['id']}_{map_idx}")
                if uploaded_file:
                    try:
                        jsdata = json.load(uploaded_file)
                        cur_t1_id = t1_id_val
                        cur_t2_id = t2_id_val
                        json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id, cur_t2_id)
                        st.session_state[f"ocr_po_{m['id']}_{map_idx}"] = json_suggestions
                        st.session_state[f"scraped_data_po_{m['id']}_{map_idx}"] = {'map_name': map_name, 't1_rounds': int(t1_r), 't2_rounds': int(t2_r)}
                        st.session_state[f"force_map_po_{m['id']}_{map_idx}"] = st.session_state.get(f"force_map_po_{m['id']}_{map_idx}", 0) + 1
                        st.session_state[f"force_apply_po_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_po_{m['id']}_{map_idx}", 0) + 1
                        st.success(f"Loaded {map_name} from uploaded file!")
                    except Exception as e:
                        st.error(f"Invalid JSON file: {e}")

                # START UNIFIED FORM
                with st.form(key=f"po_unified_map_form_{m['id']}_{map_idx}"):
                    st.write(f"### Map Details & Scoreboard")
                    force_map_cnt = st.session_state.get(f"force_map_po_{m['id']}_{map_idx}", 0)
                    
                    mcol1, mcol2, mcol3, mcol4 = st.columns([2, 1, 1, 1])
                    with mcol1:
                        map_name_input = st.selectbox("Map Name", maps_catalog, index=(maps_catalog.index(pre_map_name) if pre_map_name in maps_catalog else 0), key=f"po_mname_uni_{map_idx}_{force_map_cnt}")
                    with mcol2:
                        t1r_input = st.number_input(f"{m['t1_name']} rounds", min_value=0, value=pre_map_t1, key=f"po_t1r_uni_{map_idx}_{force_map_cnt}")
                    with mcol3:
                        t2r_input = st.number_input(f"{m['t2_name']} rounds", min_value=0, value=pre_map_t2, key=f"po_t2r_uni_{map_idx}_{force_map_cnt}")
                    with mcol4:
                        win_options = ["", m['t1_name'], m['t2_name']]
                        win_idx = 1 if pre_map_win == t1_id_val else (2 if pre_map_win == t2_id_val else 0)
                        winner_input = st.selectbox("Map Winner", win_options, index=win_idx, key=f"po_win_uni_{map_idx}_{force_map_cnt}")
                    
                    is_forfeit_input = st.checkbox("Forfeit%s", value=pre_map_ff, key=f"po_ff_uni_{map_idx}_{force_map_cnt}")
                    st.divider()
                    
                    agents_list = get_agents_list()
                    all_df = get_all_players()
                    if not all_df.empty:
                        all_df['display_label'] = all_df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
                        global_list = all_df['display_label'].tolist()
                        global_map = dict(zip(global_list, all_df['id']))
                        has_riot = all_df['riot_id'].notna() & (all_df['riot_id'].str.strip() != "")
                        label_to_riot = dict(zip(all_df.loc[has_riot, 'display_label'], all_df.loc[has_riot, 'riot_id'].str.strip().str.lower()))
                        riot_to_label = {v: k for k, v in label_to_riot.items()}
                        player_lookup = {row.id: {'label': row.display_label, 'riot_id': str(row.riot_id).strip().lower() if pd.notna(row.riot_id) and str(row.riot_id).strip() else None} for row in all_df.itertuples()}
                    else:
                        global_list, global_map, label_to_riot, riot_to_label, player_lookup = [], {}, {}, {}, {}

                    conn_p = get_conn()
                    all_map_stats = pd.read_sql("SELECT * FROM match_stats_map WHERE match_id=%s AND map_index=%s", conn_p, params=(int(m['id']), map_idx))
                    conn_p.close()

                    all_teams_entries = []
                    for team_key, team_id, team_name in [("t1", t1_id_val, m['t1_name']), ("t2", t2_id_val, m['t2_name'])]:
                        st.write(f"#### {team_name} Scoreboard")
                        roster_df = all_df[all_df['default_team_id'] == team_id].sort_values('name')
                        roster_list = roster_df['display_label'].tolist() if not roster_df.empty else []
                        roster_map = dict(zip(roster_list, roster_df['id']))
                        existing = all_map_stats[all_map_stats['team_id'] == team_id]
                        sug = st.session_state.get(f"ocr_po_{m['id']}_{map_idx}", {})
                        our_team_num = 1 if team_key == "t1" else 2
                        force_apply = st.session_state.get(f"force_apply_po_{m['id']}_{map_idx}", False)
                        
                        rows = []
                        if not existing.empty and not force_apply:
                            for r in existing.itertuples():
                                pname = player_lookup.get(r.player_id, {}).get('label', "")
                                rid = player_lookup.get(r.player_id, {}).get('riot_id')
                                sfname = player_lookup.get(r.subbed_for_id, {}).get('label', "")
                                acs, k, d, a = int(r.acs or 0), int(r.kills or 0), int(r.deaths or 0), int(r.assists or 0)
                                agent = r.agent or (agents_list[0] if agents_list else "")
                                if rid and rid in sug and acs == 0 and k == 0:
                                    s = sug[rid]; acs, k, d, a = s['acs'], s['k'], s['d'], s['a']; agent = s.get('agent') or agent
                                rows.append({'player': pname, 'is_sub': bool(r.is_sub), 'subbed_for': sfname or (roster_list[0] if roster_list else ""), 'agent': agent, 'acs': acs, 'k': k, 'd': d, 'a': a})
                        else:
                            team_sug_rids = [rid for rid, s in sug.items() if s.get('team_num') == our_team_num]
                            json_roster_matches, json_subs = [], []
                            for rid in team_sug_rids:
                                s = sug[rid]; l_rid = rid.lower(); db_label = riot_to_label.get(l_rid)
                                if not db_label and s.get('name'):
                                    matched_name = s.get('name')
                                    for label in global_list:
                                        if label == matched_name or label.startswith(matched_name + " ("): db_label = label; break
                                if db_label and db_label in roster_list: json_roster_matches.append((rid, db_label, s))
                                else: json_subs.append((rid, db_label, s))
                            
                            used_roster = [mx[1] for mx in json_roster_matches]
                            missing_roster = [l for l in roster_list if l not in used_roster]
                            for rid, label, s in json_roster_matches:
                                rows.append({'player': label, 'is_sub': False, 'subbed_for': label, 'agent': s.get('agent') or (agents_list[0] if agents_list else ""), 'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']})
                            for rid, db_label, s in json_subs:
                                if len(rows) >= 5: break
                                sub_for = missing_roster.pop(0) if missing_roster else (roster_list[0] if roster_list else "")
                                rows.append({'player': db_label or "", 'is_sub': True, 'subbed_for': sub_for, 'agent': s.get('agent') or (agents_list[0] if agents_list else ""), 'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']})
                            while len(rows) < 5:
                                l = missing_roster.pop(0) if missing_roster else (roster_list[0] if roster_list else "")
                                rows.append({'player': l, 'is_sub': False, 'subbed_for': l, 'agent': agents_list[0] if agents_list else "", 'acs': 0, 'k': 0, 'd': 0, 'a': 0})

                        h1,h2,h3,h4,h5,h6,h7,h8,h9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                        h1.write("Player"); h2.write("Sub%s"); h3.write("Subbing For"); h4.write("Agent"); h5.write("ACS"); h6.write("K"); h7.write("D"); h8.write("A"); h9.write("Conf")
                        
                        team_entries = []
                        force_cnt = st.session_state.get(f"force_apply_po_{m['id']}_{map_idx}", 0)
                        for i, rowd in enumerate(rows):
                            c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                            p_idx = global_list.index(rowd['player']) if rowd['player'] in global_list else len(global_list)
                            input_key = f"po_uni_{m['id']}_{map_idx}_{team_key}_{i}_{force_cnt}"
                            psel = c1.selectbox(f"P_{input_key}", global_list + [""], index=p_idx, label_visibility="collapsed")
                            rid_psel = label_to_riot.get(psel)
                            is_sub = c2.checkbox(f"S_{input_key}", value=rowd['is_sub'], label_visibility="collapsed")
                            sf_sel = c3.selectbox(f"SF_{input_key}", roster_list + [""], index=(roster_list.index(rowd['subbed_for']) if rowd['subbed_for'] in roster_list else 0), label_visibility="collapsed")
                            ag_sel = c4.selectbox(f"Ag_{input_key}", agents_list + [""], index=(agents_list.index(rowd['agent']) if rowd['agent'] in agents_list else 0), label_visibility="collapsed")
                            cur_s = sug.get(rid_psel, {}) if rid_psel else {}
                            v_acs = cur_s.get('acs', rowd['acs']); v_k = cur_s.get('k', rowd['k']); v_d = cur_s.get('d', rowd['d']); v_a = cur_s.get('a', rowd['a'])
                            acs = c5.number_input(f"ACS_{input_key}_{rid_psel}", min_value=0, value=int(v_acs), label_visibility="collapsed")
                            k = c6.number_input(f"K_{input_key}_{rid_psel}", min_value=0, value=int(v_k), label_visibility="collapsed")
                            d = c7.number_input(f"D_{input_key}_{rid_psel}", min_value=0, value=int(v_d), label_visibility="collapsed")
                            a = c8.number_input(f"A_{input_key}_{rid_psel}", min_value=0, value=int(v_a), label_visibility="collapsed")
                            c9.write(cur_s.get('conf', '-'))
                            team_entries.append({'player_id': global_map.get(psel), 'is_sub': int(is_sub), 'subbed_for_id': roster_map.get(sf_sel), 'agent': ag_sel or None, 'acs': int(acs), 'kills': int(k), 'deaths': int(d), 'assists': int(a)})
                        all_teams_entries.append((team_id, team_entries))
                        st.divider()

                    submit_all = st.form_submit_button("Save Playoff Map & Scoreboard", use_container_width=True)
                    if submit_all:
                        wid = t1_id_val if winner_input == m['t1_name'] else (t2_id_val if winner_input == m['t2_name'] else None)
                        conn_s = get_conn()
                        try:
                            # Use DELETE + INSERT for maximum compatibility and to avoid ON CONFLICT issues
                            conn_s.execute("DELETE FROM match_maps WHERE match_id=%s AND map_index=%s", (int(m['id']), map_idx))
                            conn_s.execute("""
                                INSERT INTO match_maps (match_id, map_index, map_name, team1_rounds, team2_rounds, winner_id, is_forfeit)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (int(m['id']), map_idx, map_name_input, int(t1r_input), int(t2r_input), wid, int(is_forfeit_input)))

                            for t_id, t_entries in all_teams_entries:
                                conn_s.execute("DELETE FROM match_stats_map WHERE match_id=%s AND map_index=%s AND team_id=%s", (int(m['id']), map_idx, t_id))
                                for e in t_entries:
                                    if e['player_id']:
                                        conn_s.execute("""
                                            INSERT INTO match_stats_map (match_id, map_index, team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists)
                                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                        """, (int(m['id']), map_idx, t_id, e['player_id'], e['is_sub'], e['subbed_for_id'], e['agent'], e['acs'], e['kills'], e['deaths'], e['assists']))
                            
                            maps_df_final = pd.read_sql("SELECT winner_id, team1_rounds, team2_rounds FROM match_maps WHERE match_id=%s", conn_s, params=(int(m['id']),))
                            final_s1 = len(maps_df_final[maps_df_final['winner_id'] == t1_id_val])
                            final_s2 = len(maps_df_final[maps_df_final['winner_id'] == t2_id_val])
                            final_winner = t1_id_val if final_s1 > final_s2 else (t2_id_val if final_s2 > final_s1 else None)
                            played_cnt = len(maps_df_final[(maps_df_final['team1_rounds'] + maps_df_final['team2_rounds']) > 0])
                            
                            conn_s.execute("UPDATE matches SET score_t1=%s, score_t2=%s, winner_id=%s, status='completed', maps_played=%s, reported=false WHERE id=%s", 
                                         (final_s1, final_s2, final_winner, played_cnt, int(m['id'])))
                            conn_s.commit()
                            clear_caches_safe()
                            st.success(f"Saved Playoff Map {map_idx+1}!")
                            st.rerun()
                        except Exception as ex:
                            conn_s.rollback()
                            st.error(f"Error: {ex}")
                        finally:
                            conn_s.close()

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
            1: "Round of 24",
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
                        is_ff = m.get('is_forfeit', 0)
                        
                        t1_class = "team-winner" if status == 'completed' and s1 > s2 else ""
                        t2_class = "team-winner" if status == 'completed' and s2 > s1 else ""
                        
                        ff_marker = '<span style="color: var(--primary-red); font-size: 0.6rem; margin-left: 5px;">[FF]</span>' if is_ff else ''
                        
                        st.markdown(f"""
                        <div class="bracket-match">
                            <div class="match-team">
                                <span class="{t1_class}">{t1_display}</span>
                                <span style="font-family: 'Orbitron';">{s1}{ff_marker if s1 > s2 else ''}</span>
                            </div>
                            <div class="match-team">
                                <span class="{t2_class}">{t2_display}</span>
                                <span style="font-family: 'Orbitron';">{s2}{ff_marker if s2 > s1 else ''}</span>
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
        # Active User Count and System Status
        active_users = get_active_user_count()
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
            <div class="custom-card" style="text-align: center;">
                <h4 style="color: var(--primary-blue); margin-bottom: 0;">LIVE USERS</h4>
                <p style="font-size: 2rem; font-family: 'Orbitron'; margin: 10px 0;">{active_users}</p>
                <p style="color: var(--text-dim); font-size: 0.8rem;">Currently on website</p>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="custom-card" style="text-align: center;">
                <h4 style="color: #00ff88; margin-bottom: 0;">SYSTEM STATUS</h4>
                <p style="font-size: 1.2rem; font-family: 'Orbitron'; margin: 18px 0;">ONLINE</p>
                <p style="color: var(--text-dim); font-size: 0.8rem;">All systems operational</p>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            # Show current admin role
            role = st.session_state.get('role', 'admin').upper()
            st.markdown(f"""
            <div class="custom-card" style="text-align: center;">
                <h4 style="color: var(--primary-red); margin-bottom: 0;">SESSION ROLE</h4>
                <p style="font-size: 1.5rem; font-family: 'Orbitron'; margin: 15px 0;">{role}</p>
                <p style="color: var(--text-dim); font-size: 0.8rem;">{st.session_state.get('username')}</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)

        st.subheader("🤖 Bot Pending Requests")
        
        pm_df = pd.DataFrame()
        pp_df = pd.DataFrame()
        try:
            r_pm = supabase.table("pending_matches").select("*").execute()
            if r_pm.data:
                pm_df = pd.DataFrame(r_pm.data)
        except Exception:
            pass
        try:
            r_pp = supabase.table("pending_players").select("*").execute()
            if r_pp.data:
                pp_df = pd.DataFrame(r_pp.data)
        except Exception:
            pass
        
        col_pm, col_pp = st.columns(2)
        
        with col_pm:
            st.markdown("#### Pending Matches")
            if pm_df.empty:
                st.info("No pending match requests.")
            else:
                pm_display = pm_df.rename(columns={"team_a": "Team A", "team_b": "Team B", "submitted_by": "By"})
                st.dataframe(pm_display[["Team A", "Team B", "By"]], use_container_width=True, hide_index=True)
                sel_pm_id = st.selectbox("Select Match to Process", pm_df["id"].tolist(), format_func=lambda x: f"{pm_df[pm_df['id']==x]['team_a'].iloc[0]} vs {pm_df[pm_df['id']==x]['team_b'].iloc[0]}")
                if st.button("🚀 Process Match Request"):
                    req = pm_df[pm_df['id'] == sel_pm_id].iloc[0].to_dict()
                    st.session_state['pending_match_request'] = req
                    st.session_state['pending_match_db_id'] = sel_pm_id
                    
                    # AUTO-SELECT MATCH ID
                    try:
                        res_sched = supabase.table("matches")\
                            .select("id, week, status, t1:teams!team1_id(name), t2:teams!team2_id(name)")\
                            .eq("status", "scheduled")\
                            .execute()
                        if res_sched.data:
                            mm = pd.DataFrame(res_sched.data)
                            def _nm(x):
                                return str(x).strip().lower() if pd.notna(x) else ""
                            ta = _nm(req.get('team_a'))
                            tb = _nm(req.get('team_b'))
                            cand = mm[((mm['t1'].apply(lambda x: _nm(x.get('name'))) == ta) & (mm['t2'].apply(lambda x: _nm(x.get('name'))) == tb)) |
                                      ((mm['t1'].apply(lambda x: _nm(x.get('name'))) == tb) & (mm['t2'].apply(lambda x: _nm(x.get('name'))) == ta))]
                            if not cand.empty:
                                row0 = cand.iloc[0]
                                st.session_state['auto_selected_match_week'] = row0['week']
                                st.session_state['auto_selected_match_id'] = row0['id']
                                st.success(f"Linked to Scheduled Match (Week {row0['week']})!")
                            else:
                                st.warning("Could not find a scheduled match for these teams. Please select manually.")
                    except Exception:
                        st.warning("Scheduled match lookup failed. Please select manually.")
                        st.success(f"Linked to Scheduled Match (Week {m_row[1]})!")
                    else:
                        st.warning("Could not find a scheduled match for these teams. Please select manually.")
                    
                    st.session_state['scroll_to_editor'] = True
                    st.rerun()

                st.markdown("---")
                if st.button("📋 Copy All Pending Tracker Links"):
                    links = [f"{r.get('url','')}" for r in pm_df.to_dict('records') if r.get('url')]
                    if links:
                        st.code("\n".join(links), language="text")
                        st.success(f"Copied {len(links)} links to clipboard view!")
                    else:
                        st.warning("No links found.")

        with col_pp:
            st.markdown("#### Pending Players")
            if pp_df.empty:
                st.info("No pending player requests.")
            else:
                pp_display = pp_df.rename(columns={"riot_id": "Player", "rank": "Rank", "submitted_by": "By"})
                st.dataframe(pp_display[["Player", "Rank", "By"]], use_container_width=True, hide_index=True)
                sel_pp_id = st.selectbox("Select Player to Process", pp_df["id"].tolist(), format_func=lambda x: pp_df[pp_df['id']==x]['riot_id'].iloc[0])
                if st.button("🚀 Process Player Request"):
                    req = pp_df[pp_df['id'] == sel_pp_id].iloc[0].to_dict()
                    st.session_state['pending_player_request'] = req
                    st.session_state['pending_player_db_id'] = sel_pp_id
                    st.success("Request loaded into Player Add form below!")
                    st.rerun()
        
        st.divider()

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
        st.markdown('<div id="match-editor-anchor"></div>', unsafe_allow_html=True)
        st.subheader("Match Editor")
        
        # Auto-scroll helper
        if st.session_state.get('scroll_to_editor'):
            import streamlit.components.v1 as components
            components.html("""
                <script>
                    setTimeout(function() {
                        var el = window.parent.document.getElementById('match-editor-anchor');
                        if (el) el.scrollIntoView({behavior: 'smooth'});
                    }, 100);
                </script>
            """, height=0)
            st.session_state['scroll_to_editor'] = False

        wk_list = get_match_weeks()
        
        # USE AUTO-SELECTED WEEK IF AVAILABLE
        def_wk_idx = 0
        if 'auto_selected_match_week' in st.session_state:
            try:
                def_wk_idx = wk_list.index(st.session_state['auto_selected_match_week'])
            except: pass

        wk = st.selectbox("Week", wk_list, index=def_wk_idx, key="editor_week_select") if wk_list else None
        if wk is None:
            st.info("No matches yet")
        else:
            dfm = get_week_matches(wk)
            if dfm.empty:
                st.info("No matches for this week")
            else:
                # Vectorized option generation
                match_opts = ("ID " + dfm['id'].astype(str) + ": " + dfm['t1_name'].fillna('') + " vs " + dfm['t2_name'].fillna('') + " (" + dfm['group_name'].fillna('') + ")").tolist()
                
                # USE AUTO-SELECTED MATCH ID IF AVAILABLE
                def_idx = 0
                if 'auto_selected_match_id' in st.session_state:
                    try:
                        def_idx = dfm[dfm['id'] == st.session_state['auto_selected_match_id']].index[0]
                        # Wait, idx is relative to dfm, need the list index
                        def_idx = list(dfm['id']).index(st.session_state['auto_selected_match_id'])
                    except: pass

                idx = st.selectbox("Match", list(range(len(match_opts))), index=def_idx, format_func=lambda i: match_opts[i])
                m = dfm.iloc[idx]

                c0, c1, c2 = st.columns([1,1,1])
                with c0:
                    fmt = st.selectbox("Format", ["BO1","BO3","BO5"], index=["BO1","BO3","BO5"].index(str(m['format'] or "BO3").upper()))
                
                # Pre-define IDs for both FF and regular logic
                t1_id_val = int(m.get('t1_id', m.get('team1_id')))
                t2_id_val = int(m.get('t2_id', m.get('team2_id')))
                
                # Match-level Forfeit
                is_match_ff = st.checkbox("Match-level Forfeit", value=bool(m.get('is_forfeit', 0)), key=f"match_ff_{m['id']}", help="Check if the entire match was a forfeit (13-0 result)")
                
                if is_match_ff:
                    ff_winner_team = st.radio("Match Winner", [m['t1_name'], m['t2_name']], index=0 if m['score_t1'] >= m['score_t2'] else 1, horizontal=True)
                    s1 = 13 if ff_winner_team == m['t1_name'] else 0
                    s2 = 13 if ff_winner_team == m['t2_name'] else 0
                    st.info(f"Forfeit Result: {m['t1_name']} {s1} - {s2} {m['t2_name']}")
                    
                    if st.button("Save Forfeit Match"):
                        winner_id = t1_id_val if s1 > s2 else t2_id_val
                        supabase.table("matches").update({
                            "score_t1": int(s1),
                            "score_t2": int(s2),
                            "winner_id": winner_id,
                            "status": "completed",
                            "format": fmt,
                            "maps_played": 0,
                            "is_forfeit": 1
                        }).eq("id", int(m['id'])).execute()
                        supabase.table("match_maps").delete().eq("match_id", int(m['id'])).execute()
                        supabase.table("match_stats_map").delete().eq("match_id", int(m['id'])).execute()
                        clear_caches_safe()
                        st.success("Saved forfeit match")
                        st.rerun()
                else:
                    st.info("Match details are managed per-map below. The total match score will be automatically updated.")
                    st.divider()
                    st.subheader("Per-Map Scoreboard")
                    
                    fmt_constraints = {"BO1": (1,1), "BO3": (2,3), "BO5": (3,5)}
                    min_maps, max_maps = fmt_constraints.get(fmt, (1,1))
                    map_choice = st.selectbox("Select Map", list(range(1, max_maps+1)), index=0)
                    map_idx = map_choice - 1
                    
                    # 1. Fetch existing map data for THIS map index
                    existing_maps_df = get_match_maps(int(m['id']))
                    existing_map = None
                    if not existing_maps_df.empty:
                        rowx = existing_maps_df[existing_maps_df['map_index'] == map_idx]
                        if not rowx.empty:
                            existing_map = rowx.iloc[0]

                    pre_map_name = existing_map['map_name'] if existing_map is not None else ""
                    pre_map_t1 = int(existing_map['team1_rounds']) if existing_map is not None else 0
                    pre_map_t2 = int(existing_map['team2_rounds']) if existing_map is not None else 0
                    pre_map_win = int(existing_map['winner_id']) if existing_map is not None and pd.notna(existing_map['winner_id']) else None
                    pre_map_ff = bool(existing_map['is_forfeit']) if existing_map is not None and 'is_forfeit' in existing_map else False

                    # Override with scraped data if available
                    scraped_map = st.session_state.get(f"scraped_data_{m['id']}_{map_idx}")
                    if scraped_map:
                        pre_map_name = scraped_map['map_name']
                        pre_map_t1 = scraped_map['t1_rounds']
                        pre_map_t2 = scraped_map['t2_rounds']
                        if pre_map_t1 > pre_map_t2: pre_map_win = t1_id_val
                        elif pre_map_t2 > pre_map_t1: pre_map_win = t2_id_val

                    all_df0 = get_all_players()
                    name_to_riot = dict(zip(all_df0['name'].astype(str), all_df0['riot_id'].astype(str))) if not all_df0.empty else {}
                
                    # Match ID/URL input and JSON upload for automatic pre-filling
                    st.write("#### 🤖 Auto-Fill from Tracker.gg")
                    
                    # PRE-FILL FROM BOT REQUEST
                    def_val = ""
                    if 'pending_match_request' in st.session_state:
                        req = st.session_state['pending_match_request']
                        def_val = req.get('url', "")
                        st.info(f"Filling from Bot Request: {req.get('team_a')} vs {req.get('team_b')}")
                    
                    col_json1, col_json2 = st.columns([2, 1])
                    with col_json1:
                        match_input = st.text_input("Tracker.gg Match URL or ID", value=def_val, key=f"mid_{m['id']}_{map_idx}", placeholder="https://tracker.gg/valorant/match/...")
                    with col_json2:
                        if st.button("Apply Match Data", key=f"force_json_{m['id']}_{map_idx}", use_container_width=True):
                            if match_input:
                                # Clean Match ID
                                match_id_clean = match_input
                                if "tracker.gg" in match_input:
                                    mid_match = re.search(r'match/([a-zA-Z0-9\-]+)', match_input)
                                    if mid_match: match_id_clean = mid_match.group(1)
                                match_id_clean = re.sub(r'[^a-zA-Z0-9\-]', '', match_id_clean)
                            
                                json_path = os.path.join("assets", "matches", f"match_{match_id_clean}.json")
                                jsdata = None
                                source = ""
                            
                                # 1. Try local file first
                                if os.path.exists(json_path):
                                    try:
                                        with open(json_path, 'r', encoding='utf-8') as f:
                                            jsdata = json.load(f)
                                        source = "Local Cache"
                                    except: pass
                            
                                # 2. If not found locally, try GitHub repository
                                if not jsdata:
                                    with st.spinner("Checking GitHub matches folder..."):
                                        jsdata, gh_err = fetch_match_from_github(match_id_clean)
                                        if jsdata:
                                            source = "GitHub Repository"
                                            # Save locally for next time
                                            try:
                                                if not os.path.exists(os.path.join("assets", "matches")): os.makedirs(os.path.join("assets", "matches"))
                                                with open(json_path, 'w', encoding='utf-8') as f:
                                                    json.dump(jsdata, f, indent=4)
                                            except: pass

                                # 3. If still not found, attempt live scrape
                                if not jsdata:
                                    with st.spinner("Fetching data from Tracker.gg..."):
                                        jsdata, err = scrape_tracker_match(match_id_clean)
                                        if jsdata:
                                            source = "Tracker.gg"
                                            if not os.path.exists("matches"): os.makedirs("matches")
                                            with open(json_path, 'w', encoding='utf-8') as f:
                                                json.dump(jsdata, f, indent=4)
                                        else:
                                            st.error(f"Live scrape failed: {err}")
                                            if gh_err: st.info(f"GitHub fetch also failed: {gh_err}")
                                            st.info("💡 **Tip:** If scraping is blocked, run the scraper script on your PC and upload the JSON file below.")
                            
                                if jsdata:
                                    cur_t1_id = int(m.get('t1_id', m.get('team1_id')))
                                    cur_t2_id = int(m.get('t2_id', m.get('team2_id')))
                                    json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id, cur_t2_id)
                                    st.session_state[f"ocr_{m['id']}_{map_idx}"] = json_suggestions
                                    st.session_state[f"scraped_data_{m['id']}_{map_idx}"] = {'map_name': map_name, 't1_rounds': int(t1_r), 't2_rounds': int(t2_r)}
                                    st.session_state[f"force_map_{m['id']}_{map_idx}"] = st.session_state.get(f"force_map_{m['id']}_{map_idx}", 0) + 1
                                    st.session_state[f"force_apply_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0) + 1
                                    st.success(f"Loaded {map_name} from {source}!")
                                    st.rerun()

                    uploaded_file = st.file_uploader("Or Upload Tracker.gg JSON", type=["json"], key=f"json_up_{m['id']}_{map_idx}")
                    if uploaded_file:
                        try:
                            jsdata = json.load(uploaded_file)
                            cur_t1_id = int(m.get('t1_id', m.get('team1_id')))
                            cur_t2_id = int(m.get('t2_id', m.get('team2_id')))
                            json_suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, cur_t1_id, cur_t2_id)
                            st.session_state[f"ocr_{m['id']}_{map_idx}"] = json_suggestions
                            st.session_state[f"scraped_data_{m['id']}_{map_idx}"] = {'map_name': map_name, 't1_rounds': int(t1_r), 't2_rounds': int(t2_r)}
                            st.session_state[f"force_map_{m['id']}_{map_idx}"] = st.session_state.get(f"force_map_{m['id']}_{map_idx}", 0) + 1
                            st.session_state[f"force_apply_{m['id']}_{map_idx}"] = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0) + 1
                            st.success(f"Loaded {map_name} from uploaded file!")
                        except Exception as e:
                            st.error(f"Invalid JSON file: {e}")


                    # START UNIFIED FORM
                    with st.form(key=f"unified_map_form_{m['id']}_{map_idx}"):
                        st.write(f"### Map Details & Scoreboard")
                        force_map_cnt = st.session_state.get(f"force_map_{m['id']}_{map_idx}", 0)
                        
                        mcol1, mcol2, mcol3, mcol4 = st.columns([2, 1, 1, 1])
                        with mcol1:
                            map_name_input = st.selectbox("Map Name", maps_catalog, index=(maps_catalog.index(pre_map_name) if pre_map_name in maps_catalog else 0), key=f"mname_uni_{map_idx}_{force_map_cnt}")
                        with mcol2:
                            t1r_input = st.number_input(f"{m['t1_name']} rounds", min_value=0, value=pre_map_t1, key=f"t1r_uni_{map_idx}_{force_map_cnt}")
                        with mcol3:
                            t2r_input = st.number_input(f"{m['t2_name']} rounds", min_value=0, value=pre_map_t2, key=f"t2r_uni_{map_idx}_{force_map_cnt}")
                        with mcol4:
                            win_options = ["", m['t1_name'], m['t2_name']]
                            win_idx = 1 if pre_map_win == t1_id_val else (2 if pre_map_win == t2_id_val else 0)
                            winner_input = st.selectbox("Map Winner", win_options, index=win_idx, key=f"win_uni_{map_idx}_{force_map_cnt}")
                        
                        is_forfeit_input = st.checkbox("Forfeit%s", value=pre_map_ff, key=f"ff_uni_{map_idx}_{force_map_cnt}")
                        
                        st.divider()
                        
                        # Shared data for scoreboards
                        agents_list = get_agents_list()
                        all_df = get_all_players()
                        if not all_df.empty:
                            all_df['display_label'] = all_df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
                            global_list = all_df['display_label'].tolist()
                            global_map = dict(zip(global_list, all_df['id']))
                            has_riot = all_df['riot_id'].notna() & (all_df['riot_id'].str.strip() != "")
                            label_to_riot = dict(zip(all_df.loc[has_riot, 'display_label'], all_df.loc[has_riot, 'riot_id'].str.strip().str.lower()))
                            riot_to_label = {v: k for k, v in label_to_riot.items()}
                            player_lookup = {row.id: {'label': row.display_label, 'riot_id': str(row.riot_id).strip().lower() if pd.notna(row.riot_id) and str(row.riot_id).strip() else None} for row in all_df.itertuples()}
                        else:
                            global_list, global_map, label_to_riot, riot_to_label, player_lookup = [], {}, {}, {}, {}

                        conn_p = get_conn()
                        all_map_stats = pd.read_sql("SELECT * FROM match_stats_map WHERE match_id=%s AND map_index=%s", conn_p, params=(int(m['id']), map_idx))
                        conn_p.close()

                        all_teams_entries = [] # To store (team_id, entries)

                        for team_key, team_id, team_name in [("t1", t1_id_val, m['t1_name']), ("t2", t2_id_val, m['t2_name'])]:
                            st.write(f"#### {team_name} Scoreboard")
                            roster_df = all_df[all_df['default_team_id'] == team_id].sort_values('name')
                            roster_list = roster_df['display_label'].tolist() if not roster_df.empty else []
                            roster_map = dict(zip(roster_list, roster_df['id']))
                            
                            existing = all_map_stats[all_map_stats['team_id'] == team_id]
                            sug = st.session_state.get(f"ocr_{m['id']}_{map_idx}", {})
                            our_team_num = 1 if team_key == "t1" else 2
                            force_apply = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", False)
                            
                            rows = []
                            if not existing.empty and not force_apply:
                                for r in existing.itertuples():
                                    pname = player_lookup.get(r.player_id, {}).get('label', "")
                                    rid = player_lookup.get(r.player_id, {}).get('riot_id')
                                    sfname = player_lookup.get(r.subbed_for_id, {}).get('label', "")
                                    acs, k, d, a = int(r.acs or 0), int(r.kills or 0), int(r.deaths or 0), int(r.assists or 0)
                                    agent = r.agent or (agents_list[0] if agents_list else "")
                                    if rid and rid in sug and acs == 0 and k == 0:
                                        s = sug[rid]; acs, k, d, a = s['acs'], s['k'], s['d'], s['a']; agent = s.get('agent') or agent
                                    rows.append({'player': pname, 'is_sub': bool(r.is_sub), 'subbed_for': sfname or (roster_list[0] if roster_list else ""), 'agent': agent, 'acs': acs, 'k': k, 'd': d, 'a': a})
                            else:
                                team_sug_rids = [rid for rid, s in sug.items() if s.get('team_num') == our_team_num]
                                json_roster_matches, json_subs = [], []
                                for rid in team_sug_rids:
                                    s = sug[rid]; l_rid = rid.lower(); db_label = riot_to_label.get(l_rid)
                                    if not db_label and s.get('name'):
                                        matched_name = s.get('name')
                                        for label in global_list:
                                            if label == matched_name or label.startswith(matched_name + " ("): db_label = label; break
                                    if db_label and db_label in roster_list: json_roster_matches.append((rid, db_label, s))
                                    else: json_subs.append((rid, db_label, s))
                                
                                used_roster = [m[1] for m in json_roster_matches]
                                missing_roster = [l for l in roster_list if l not in used_roster]
                                for rid, label, s in json_roster_matches:
                                    rows.append({'player': label, 'is_sub': False, 'subbed_for': label, 'agent': s.get('agent') or (agents_list[0] if agents_list else ""), 'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']})
                                for rid, db_label, s in json_subs:
                                    if len(rows) >= 5: break
                                    sub_for = missing_roster.pop(0) if missing_roster else (roster_list[0] if roster_list else "")
                                    rows.append({'player': db_label or "", 'is_sub': True, 'subbed_for': sub_for, 'agent': s.get('agent') or (agents_list[0] if agents_list else ""), 'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']})
                                while len(rows) < 5:
                                    l = missing_roster.pop(0) if missing_roster else (roster_list[0] if roster_list else "")
                                    rows.append({'player': l, 'is_sub': False, 'subbed_for': l, 'agent': agents_list[0] if agents_list else "", 'acs': 0, 'k': 0, 'd': 0, 'a': 0})

                            # Render team table
                            h1,h2,h3,h4,h5,h6,h7,h8,h9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                            h1.write("Player"); h2.write("Sub%s"); h3.write("Subbing For"); h4.write("Agent"); h5.write("ACS"); h6.write("K"); h7.write("D"); h8.write("A"); h9.write("Conf")
                            
                            team_entries = []
                            force_cnt = st.session_state.get(f"force_apply_{m['id']}_{map_idx}", 0)
                            for i, rowd in enumerate(rows):
                                c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([2,1.2,2,2,1,1,1,1,0.8])
                                p_idx = global_list.index(rowd['player']) if rowd['player'] in global_list else len(global_list)
                                input_key = f"uni_{m['id']}_{map_idx}_{team_key}_{i}_{force_cnt}"
                                if sug: input_key += f"_{hash(str(sug))}"
                                
                                psel = c1.selectbox(f"P_{input_key}", global_list + [""], index=p_idx, label_visibility="collapsed")
                                rid_psel = label_to_riot.get(psel)
                                is_sub = c2.checkbox(f"S_{input_key}", value=rowd['is_sub'], label_visibility="collapsed")
                                sf_sel = c3.selectbox(f"SF_{input_key}", roster_list + [""], index=(roster_list.index(rowd['subbed_for']) if rowd['subbed_for'] in roster_list else 0), label_visibility="collapsed")
                                ag_sel = c4.selectbox(f"Ag_{input_key}", agents_list + [""], index=(agents_list.index(rowd['agent']) if rowd['agent'] in agents_list else 0), label_visibility="collapsed")
                                
                                cur_s = sug.get(rid_psel, {}) if rid_psel else {}
                                v_acs = cur_s.get('acs', rowd['acs']); v_k = cur_s.get('k', rowd['k']); v_d = cur_s.get('d', rowd['d']); v_a = cur_s.get('a', rowd['a'])
                                
                                acs = c5.number_input(f"ACS_{input_key}_{rid_psel}", min_value=0, value=int(v_acs), label_visibility="collapsed")
                                k = c6.number_input(f"K_{input_key}_{rid_psel}", min_value=0, value=int(v_k), label_visibility="collapsed")
                                d = c7.number_input(f"D_{input_key}_{rid_psel}", min_value=0, value=int(v_d), label_visibility="collapsed")
                                a = c8.number_input(f"A_{input_key}_{rid_psel}", min_value=0, value=int(v_a), label_visibility="collapsed")
                                c9.write(cur_s.get('conf', '-'))
                                
                                team_entries.append({'player_id': global_map.get(psel), 'is_sub': int(is_sub), 'subbed_for_id': roster_map.get(sf_sel), 'agent': ag_sel or None, 'acs': int(acs), 'kills': int(k), 'deaths': int(d), 'assists': int(a)})
                            
                            all_teams_entries.append((team_id, team_entries))
                            st.divider()

                        submit_all = st.form_submit_button("Save Map Details & Scoreboard", use_container_width=True)
                        if submit_all:
                            # 1. Determine Winner ID
                            wid = t1_id_val if winner_input == m['t1_name'] else (t2_id_val if winner_input == m['t2_name'] else None)
                            
                            # Use UnifiedDBWrapper for maximum robustness and consistent DELETE+INSERT pattern
                            conn_s = get_conn()
                            try:
                                # A. Save Map Info
                                conn_s.execute("DELETE FROM match_maps WHERE match_id=%s AND map_index=%s", (int(m['id']), map_idx))
                                conn_s.execute("""
                                    INSERT INTO match_maps (match_id, map_index, map_name, team1_rounds, team2_rounds, winner_id, is_forfeit)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (int(m['id']), map_idx, map_name_input, int(t1r_input), int(t2r_input), wid, int(is_forfeit_input)))

                                # B. Save Stats for both teams
                                conn_s.execute("DELETE FROM match_stats_map WHERE match_id=%s AND map_index=%s", (int(m['id']), map_idx))
                                for t_id, t_entries in all_teams_entries:
                                    for e in t_entries:
                                        if e['player_id']:
                                            conn_s.execute("""
                                                INSERT INTO match_stats_map (match_id, map_index, team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists)
                                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                            """, (int(m['id']), map_idx, t_id, e['player_id'], e['is_sub'], e['subbed_for_id'], e['agent'], e['acs'], e['kills'], e['deaths'], e['assists']))
                                
                                # C. Recalculate Match Totals
                                maps_df_final = pd.read_sql("SELECT winner_id, team1_rounds, team2_rounds FROM match_maps WHERE match_id=%s", conn_s, params=(int(m['id']),))
                                final_s1 = len(maps_df_final[maps_df_final['winner_id'] == t1_id_val])
                                final_s2 = len(maps_df_final[maps_df_final['winner_id'] == t2_id_val])
                                final_winner = t1_id_val if final_s1 > final_s2 else (t2_id_val if final_s2 > final_s1 else None)
                                played_cnt = len(maps_df_final[(maps_df_final['team1_rounds'] + maps_df_final['team2_rounds']) > 0])
                                
                                # Fetch metadata from pending if available for reporting
                                channel_id, submitter_id = None, None
                                if 'pending_match_db_id' in st.session_state:
                                    meta_df = pd.read_sql("SELECT channel_id, submitter_id FROM pending_matches WHERE id=%s", conn_s, params=(int(st.session_state['pending_match_db_id']),))
                                    if not meta_df.empty:
                                        channel_id = meta_df.iloc[0]['channel_id']
                                        submitter_id = meta_df.iloc[0]['submitter_id']

                                conn_s.execute("""
                                    UPDATE matches 
                                    SET score_t1=%s, score_t2=%s, winner_id=%s, status='completed', maps_played=%s, 
                                        reported=false, channel_id=%s, submitter_id=%s
                                    WHERE id=%s
                                """, (final_s1, final_s2, final_winner, played_cnt, channel_id, submitter_id, int(m['id'])))
                                
                                # D. Cleanup pending
                                if 'pending_match_db_id' in st.session_state:
                                    conn_s.execute("DELETE FROM pending_matches WHERE id=%s", (st.session_state['pending_match_db_id'],))
                                
                                conn_s.commit()
                            except Exception as ex:
                                conn_s.rollback()
                                st.error(f"Save failed: {ex}")
                                st.stop()
                            finally:
                                conn_s.close()
                                    
                            # Cleanup State
                            if 'pending_match_db_id' in st.session_state:
                                del st.session_state['pending_match_db_id']
                                del st.session_state['pending_match_request']
                                if 'auto_selected_match_id' in st.session_state: del st.session_state['auto_selected_match_id']
                                if 'auto_selected_match_week' in st.session_state: del st.session_state['auto_selected_match_week']

                            clear_caches_safe()
                            st.success(f"Successfully saved and updated totals!")
                            time.sleep(1)
                            st.rerun()

        st.divider()
        st.subheader("Players Admin")
        players_df = get_all_players_directory(format_names=False)
        teams_list = get_teams_list()
        
        team_names = teams_list['name'].tolist() if not teams_list.empty else []
        team_map = dict(zip(teams_list['name'], teams_list['id']))
        rvals = ["Unranked", "Iron/Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal 1/2", "Immortal 3/Radiant"]
        rvals_all = sorted(list(set(rvals + players_df['rank'].dropna().unique().tolist())))
        
        # Allow both admin and dev to manage players
        user_role = st.session_state.get('role', 'admin')
        if user_role in ['admin', 'dev']:
            st.subheader("Add Player")
            # PRE-FILL FROM BOT REQUEST
            def_name = ""
            def_rid = ""
            def_rk = rvals[0]
            def_tl = ""
            if 'pending_player_request' in st.session_state:
                preq = st.session_state['pending_player_request']
                def_rid = preq.get('riot_id', "")
                def_rk = preq.get('rank', rvals[0])
                def_tl = preq.get('tracker_link', "")
                
                # Format Name as @discord_handle if available
                discord_h = preq.get('discord_handle', "")
                if discord_h:
                    def_name = f"@{discord_h}"
                
                if def_rk not in rvals: def_rk = rvals[0]
                st.info(f"Filling from Bot Request: {def_rid}")

            with st.form("add_player_admin"):
                nm_new = st.text_input("Name (Discord Handle)", value=def_name, help="Format: @ExampleUser")
                rid_new = st.text_input("Riot ID", value=def_rid)
                uuid_new = st.text_input("UUID (Optional)", help="Discord User ID")
                rk_new = st.selectbox("Rank", rvals, index=rvals.index(def_rk))
                tl_new = st.text_input("Tracker Link", value=def_tl)
                tmn_new = st.selectbox("Team", [""] + team_names, index=0)
                add_ok = st.form_submit_button("Create Player")
                if add_ok and nm_new:
                    rid_clean = rid_new.strip() if rid_new else ""
                    nm_clean = nm_new.strip()
                    uuid_clean = uuid_new.strip() if uuid_new else None
                    dtid_new = team_map.get(tmn_new) if tmn_new else None
                    can_add = True
                    
                    saved_via_sdk = False
                    if supabase:
                        try:
                            # SDK Check for duplicates
                            if rid_clean:
                                res_rid = supabase.table("players").select("name").ilike("riot_id", rid_clean).execute()
                                if res_rid.data:
                                    st.error(f"Error: A player ('{res_rid.data[0]['name']}') already has Riot ID '{rid_clean}'.")
                                    can_add = False
                                    
                            if can_add:
                                res_name = supabase.table("players").select("id").ilike("name", nm_clean).execute()
                                if res_name.data:
                                    st.error(f"Error: A player named '{nm_clean}' already exists.")
                                    can_add = False
                                    
                            if can_add:
                                # Insert via SDK
                                res_in = supabase.table("players").insert({
                                    "name": nm_clean, 
                                    "riot_id": rid_clean, 
                                    "uuid": uuid_clean,
                                    "rank": rk_new, 
                                    "tracker_link": tl_new, 
                                    "default_team_id": dtid_new,
                                    "discord_handle": nm_clean
                                }).execute()
                                if res_in.data:
                                    if 'pending_player_db_id' in st.session_state:
                                        try:
                                            # Mark as accepted and not yet notified
                                            supabase.table("pending_players").update({
                                                "status": "accepted", 
                                                "notified": False
                                            }).eq("id", st.session_state['pending_player_db_id']).execute()
                                        except: pass
                                    saved_via_sdk = True
                                    st.success("Player added (Cloud)")
                        except Exception as e:
                            st.warning(f"Supabase SDK add failed: {e}")

                    if not saved_via_sdk and can_add:
                        conn_add = get_conn()
                        try:
                            if rid_clean:
                                existing_rid = pd.read_sql("SELECT name FROM players WHERE LOWER(riot_id) = %s", conn_add, params=(rid_clean.lower(),))
                                if not existing_rid.empty:
                                    st.error(f"Error: A player ('{existing_rid.iloc[0]['name']}') already has Riot ID '{rid_clean}'.")
                                    can_add = False
                            
                            if can_add:
                                existing_name = pd.read_sql("SELECT id FROM players WHERE LOWER(name) = %s", conn_add, params=(nm_clean.lower(),))
                                if not existing_name.empty:
                                    st.error(f"Error: A player named '{nm_clean}' already exists.")
                                    can_add = False
                                    
                            if can_add:
                                conn_add.execute("INSERT INTO players (name, riot_id, uuid, rank, tracker_link, default_team_id, discord_handle) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                                                 (nm_clean, rid_clean, uuid_clean, rk_new, tl_new, dtid_new, nm_clean))
                                
                                if 'pending_player_db_id' in st.session_state:
                                    try:
                                        # Mark as accepted and not yet notified
                                        conn_add.execute("UPDATE pending_players SET status='accepted', notified=false WHERE id=%s", (int(st.session_state['pending_player_db_id']),))
                                    except: pass
                                
                                conn_add.commit()
                                st.success("Player added (Local)")
                                saved_via_sdk = True # reuse flag to show success
                        except Exception as e:
                            if 'conn_add' in locals(): conn_add.rollback()
                            st.error(f"Error adding locally: {e}")
                        finally:
                            if 'conn_add' in locals(): conn_add.close()

                            clear_caches_safe()
                            if 'pending_player_db_id' in st.session_state:
                                del st.session_state['pending_player_db_id']
                                if 'pending_player_request' in st.session_state: del st.session_state['pending_player_request']
                            st.success("Successfully processed registration!")
                            time.sleep(1)
                            st.rerun()

            # REJECT BUTTON
            if 'pending_player_db_id' in st.session_state:
                if st.button("❌ Reject Request", use_container_width=True):
                    conn_rej = get_conn()
                    try:
                        conn_rej.execute("UPDATE pending_players SET status='rejected', notified=false WHERE id=%s", (int(st.session_state['pending_player_db_id']),))
                        conn_rej.commit()
                        del st.session_state['pending_player_db_id']
                        if 'pending_player_request' in st.session_state: del st.session_state['pending_player_request']
                        clear_caches_safe()
                        st.warning("Request Rejected.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error rejecting: {e}")
                    finally:
                        conn_rej.close()
            
            if st.button("🔍 Cleanup Duplicate Players", help="Merge players with exact same Riot ID or case-insensitive name"):
                merged_count = 0
                saved_via_sdk = False
                
                if supabase:
                    try:
                        res = supabase.table("players").select("id, name, riot_id").execute()
                        if res.data:
                            players = pd.DataFrame(res.data)
                            players['name_lower'] = players['name'].str.lower().str.strip()
                            players['riot_lower'] = players['riot_id'].str.lower().str.strip().fillna("")
                            
                            # 1. Exact Riot ID duplicates
                            riot_dupes = players[players['riot_lower'] != ""][players.duplicated('riot_lower', keep=False)]
                            for rid, group in riot_dupes.groupby('riot_lower'):
                                group = group.sort_values('id')
                                keep_id = group.iloc[0]['id']
                                remove_ids = group.iloc[1:]['id'].tolist()
                                for rid_to_rem in remove_ids:
                                    supabase.table("match_stats_map").update({"player_id": int(keep_id)}).eq("player_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats_map").update({"subbed_for_id": int(keep_id)}).eq("subbed_for_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats").update({"player_id": int(keep_id)}).eq("player_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats").update({"subbed_for_id": int(keep_id)}).eq("subbed_for_id", int(rid_to_rem)).execute()
                                    supabase.table("players").delete().eq("id", int(rid_to_rem)).execute()
                                    merged_count += 1
                            
                            # 2. Case-insensitive Name duplicates
                            res_after = supabase.table("players").select("id, name, riot_id").execute()
                            players_after = pd.DataFrame(res_after.data)
                            players_after['name_lower'] = players_after['name'].str.lower().str.strip()
                            name_dupes = players_after[players_after.duplicated('name_lower', keep=False)]
                            for name, group in name_dupes.groupby('name_lower'):
                                group = group.sort_values('id')
                                keep_id = group.iloc[0]['id']
                                remove_ids = group.iloc[1:]['id'].tolist()
                                for rid_to_rem in remove_ids:
                                    supabase.table("match_stats_map").update({"player_id": int(keep_id)}).eq("player_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats_map").update({"subbed_for_id": int(keep_id)}).eq("subbed_for_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats").update({"player_id": int(keep_id)}).eq("player_id", int(rid_to_rem)).execute()
                                    supabase.table("match_stats").update({"subbed_for_id": int(keep_id)}).eq("subbed_for_id", int(rid_to_rem)).execute()
                                    supabase.table("players").delete().eq("id", int(rid_to_rem)).execute()
                                    merged_count += 1
                            saved_via_sdk = True
                    except Exception as e:
                        st.warning(f"SDK Cleanup failed: {e}")

                if not saved_via_sdk:
                    conn_clean = get_conn()
                    try:
                        # Existing SQL logic...
                        players = pd.read_sql("SELECT id, name, riot_id FROM players", conn_clean)
                        players['name_lower'] = players['name'].str.lower().str.strip()
                        players['riot_lower'] = players['riot_id'].str.lower().str.strip().fillna("")
                        
                        riot_dupes = players[players['riot_lower'] != ""][players.duplicated('riot_lower', keep=False)]
                        for rid, group in riot_dupes.groupby('riot_lower'):
                            group = group.sort_values('id')
                            keep_id = group.iloc[0]['id']
                            remove_ids = group.iloc[1:]['id'].tolist()
                            for rid_to_rem in remove_ids:
                                conn_clean.execute("UPDATE match_stats_map SET player_id = %s WHERE player_id = %s", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("UPDATE match_stats_map SET subbed_for_id = %s WHERE subbed_for_id = %s", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("UPDATE match_stats SET player_id = %s WHERE player_id = %s", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("UPDATE match_stats SET subbed_for_id = %s WHERE subbed_for_id = %s", (int(keep_id), int(rid_to_rem)))
                                conn_clean.execute("DELETE FROM players WHERE id = %s", (int(rid_to_rem),))
                                merged_count += 1
                        
                        name_dupes = players[players.duplicated('name_lower', keep=False)]
                        for name, group in name_dupes.groupby('name_lower'):
                            group = group.sort_values('id')
                            keep_id = group.iloc[0]['id']
                            remove_ids = group.iloc[1:]['id'].tolist()
                            for rid_to_rem in remove_ids:
                                exists = conn_clean.execute("SELECT id FROM players WHERE id=%s", (int(rid_to_rem),)).fetchone()
                                if exists:
                                    conn_clean.execute("UPDATE match_stats_map SET player_id = %s WHERE player_id = %s", (int(keep_id), int(rid_to_rem)))
                                    conn_clean.execute("UPDATE match_stats_map SET subbed_for_id = %s WHERE subbed_for_id = %s", (int(keep_id), int(rid_to_rem)))
                                    conn_clean.execute("UPDATE match_stats SET player_id = %s WHERE player_id = %s", (int(keep_id), int(rid_to_rem)))
                                    conn_clean.execute("UPDATE match_stats SET subbed_for_id = %s WHERE subbed_for_id = %s", (int(keep_id), int(rid_to_rem)))
                                    conn_clean.execute("DELETE FROM players WHERE id = %s", (int(rid_to_rem),))
                                    merged_count += 1
                        conn_clean.commit()
                        saved_via_sdk = True
                    except Exception as e:
                        st.error(f"Cleanup error: {e}")
                    finally:
                        conn_clean.close()
                
                if merged_count > 0:
                    clear_caches_safe()
                    st.success(f"Successfully merged {merged_count} duplicate records.")
                    st.rerun()
                elif saved_via_sdk:
                    st.info("No duplicates found to merge.")

            st.markdown("---")
            st.subheader("Delete Player")
            with st.form("delete_player_admin"):
                # Fetch all players for the dropdown
                p_list_df = get_all_players()
                
                if not p_list_df.empty:
                    # Vectorized player options creation
                    p_list_df['display'] = p_list_df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
                    
                    p_options = dict(zip(p_list_df['display'], p_list_df['id']))
                    p_to_del_name = st.selectbox("Select Player to Delete", options=list(p_options.keys()))
                    p_to_del_id = p_options[p_to_del_name]
                    
                    confirm_del = st.checkbox("I understand this will remove all stats associated with this player.")
                    del_submitted = st.form_submit_button("Delete Player", type="primary")
                    
                    if del_submitted:
                        if not confirm_del:
                            st.warning("Please confirm the deletion.")
                        else:
                            saved_via_sdk = False
                            if supabase:
                                try:
                                    # Cleanup references in match_stats_map and match_stats
                                    supabase.table("match_stats_map").delete().eq("player_id", int(p_to_del_id)).execute()
                                    supabase.table("match_stats").delete().eq("player_id", int(p_to_del_id)).execute()
                                    
                                    # Set subbed_for_id to NULL
                                    supabase.table("match_stats_map").update({"subbed_for_id": None}).eq("subbed_for_id", int(p_to_del_id)).execute()
                                    supabase.table("match_stats").update({"subbed_for_id": None}).eq("subbed_for_id", int(p_to_del_id)).execute()
                                    
                                    # Delete player
                                    supabase.table("players").delete().eq("id", int(p_to_del_id)).execute()
                                    saved_via_sdk = True
                                    st.success(f"Player '{p_to_del_name}' deleted (Cloud).")
                                except Exception as e:
                                    st.warning(f"SDK Deletion failed: {e}")

                            if not saved_via_sdk:
                                conn_exec = get_conn()
                                try:
                                     conn_exec.execute("DELETE FROM match_stats_map WHERE player_id = %s", (int(p_to_del_id),))
                                     conn_exec.execute("DELETE FROM match_stats WHERE player_id = %s", (int(p_to_del_id),))
                                     conn_exec.execute("UPDATE match_stats_map SET subbed_for_id = NULL WHERE subbed_for_id = %s", (int(p_to_del_id),))
                                     conn_exec.execute("UPDATE match_stats SET subbed_for_id = NULL WHERE subbed_for_id = %s", (int(p_to_del_id),))
                                     conn_exec.execute("DELETE FROM players WHERE id = %s", (int(p_to_del_id),))
                                     conn_exec.commit()
                                     st.success(f"Player '{p_to_del_name}' deleted (Local).")
                                     saved_via_sdk = True
                                except Exception as e:
                                    st.error(f"Deletion error: {e}")
                                finally:
                                    conn_exec.close()
                            
                            if saved_via_sdk:
                                st.cache_data.clear()
                                st.rerun()
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
            num_rows=("dynamic" if user_role in ['admin', 'dev'] else "fixed"),
            use_container_width=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "team": st.column_config.SelectboxColumn("Team", options=[""] + team_names, required=False),
                    "rank": st.column_config.SelectboxColumn("Rank", options=rvals, required=False)
            },
            key="player_editor_main"
        )
        if st.button("Save Players"):
            error_found = False
            saved_via_sdk = False
            
            # Duplicate check
            current_players = pd.DataFrame()
            if supabase:
                try:
                    res = supabase.table("players").select("id, name, riot_id").execute()
                    if res.data: current_players = pd.DataFrame(res.data)
                except: pass
            
            if current_players.empty:
                conn_chk = get_conn()
                current_players = pd.read_sql("SELECT id, name, riot_id FROM players", conn_chk)
                conn_chk.close()
                
            current_players['name_lower'] = current_players['name'].str.lower().str.strip()
            current_players['riot_lower'] = current_players['riot_id'].str.lower().str.strip().fillna("")
            
            if not edited.empty:
                nm_lower = edited['name'].str.lower().str.strip()
                rid_lower = edited['riot_id'].str.lower().str.strip().fillna("")
                if nm_lower.duplicated().any():
                    dup_name = edited.loc[nm_lower.duplicated(), 'name'].iloc[0]
                    st.error(f"Error: Player name '{dup_name}' is duplicated in your edits.")
                    error_found = True
                elif rid_lower[rid_lower != ""].duplicated().any():
                    dup_rid = edited.loc[rid_lower[rid_lower != ""].duplicated(), 'riot_id'].iloc[0]
                    st.error(f"Error: Riot ID '{dup_rid}' is duplicated in your edits.")
                    error_found = True
                
                if not error_found:
                    for row in edited.itertuples():
                        pid = getattr(row, 'id', None)
                        nm = str(row.name).strip()
                        rid = str(row.riot_id).strip() if pd.notna(row.riot_id) else ""
                        others = current_players[current_players['id'] != pid] if pd.notna(pid) else current_players
                        if nm.lower() in others['name_lower'].values:
                            st.error(f"Error: Player name '{nm}' already exists. Changes not saved.")
                            error_found = True; break
                        if rid and rid.lower() in others['riot_lower'].values:
                            st.error(f"Error: Riot ID '{rid}' already exists. Changes not saved.")
                            error_found = True; break
            
            if not error_found:
                # Try SDK First
                if supabase:
                    try:
                        original_ids = set(fdf['id'].dropna().astype(int).tolist())
                        edited_ids = set(edited['id'].dropna().astype(int).tolist())
                        deleted_ids = original_ids - edited_ids
                        
                        if deleted_ids:
                            for pid in deleted_ids:
                                supabase.table("match_stats_map").delete().eq("player_id", pid).execute()
                                supabase.table("match_stats").delete().eq("player_id", pid).execute()
                                supabase.table("match_stats_map").update({"subbed_for_id": None}).eq("subbed_for_id", pid).execute()
                                supabase.table("match_stats").update({"subbed_for_id": None}).eq("subbed_for_id", pid).execute()
                                supabase.table("players").delete().eq("id", pid).execute()

                        for row in edited.itertuples():
                            pid = getattr(row, 'id', None)
                            nm = str(row.name).strip()
                            rid = str(row.riot_id).strip() if pd.notna(row.riot_id) else ""
                            rk = getattr(row, 'rank', "Unranked") or "Unranked"
                            tmn = getattr(row, 'team', None)
                            dtid = team_map.get(tmn) if pd.notna(tmn) else None
                            payload = {"name": nm, "riot_id": rid, "rank": rk, "default_team_id": dtid}
                            if pd.isna(pid):
                                if user_role in ['admin', 'dev']:
                                    supabase.table("players").insert(payload).execute()
                            else:
                                supabase.table("players").update(payload).eq("id", int(pid)).execute()
                        saved_via_sdk = True
                    except Exception as e:
                        st.warning(f"SDK Save Players failed: {e}")

                if not saved_via_sdk:
                    conn_up = get_conn()
                    try:
                        original_ids = set(fdf['id'].dropna().astype(int).tolist())
                        edited_ids = set(edited['id'].dropna().astype(int).tolist())
                        deleted_ids = original_ids - edited_ids
                        if deleted_ids:
                            for pid in deleted_ids:
                                 conn_up.execute("DELETE FROM match_stats_map WHERE player_id = %s", (pid,))
                                 conn_up.execute("DELETE FROM match_stats WHERE player_id = %s", (pid,))
                                 conn_up.execute("UPDATE match_stats_map SET subbed_for_id = NULL WHERE subbed_for_id = %s", (pid,))
                                 conn_up.execute("UPDATE match_stats SET subbed_for_id = NULL WHERE subbed_for_id = %s", (pid,))
                                 conn_up.execute("DELETE FROM players WHERE id = %s", (pid,))
                        for row in edited.itertuples():
                            pid = getattr(row, 'id', None); nm = str(row.name).strip(); rid = str(row.riot_id).strip() if pd.notna(row.riot_id) else ""
                            rk = getattr(row, 'rank', "Unranked") or "Unranked"; tmn = getattr(row, 'team', None); dtid = team_map.get(tmn) if pd.notna(tmn) else None
                            if pd.isna(pid):
                                if user_role in ['admin', 'dev']:
                                    conn_up.execute("INSERT INTO players (name, riot_id, rank, default_team_id) VALUES (%s, %s, %s, %s)", (nm, rid, rk, dtid))
                            else:
                                conn_up.execute("UPDATE players SET name=%s, riot_id=%s, rank=%s, default_team_id=%s WHERE id=%s", (nm, rid, rk, dtid, int(pid)))
                        conn_up.commit()
                        saved_via_sdk = True
                    except Exception as e:
                        if 'conn_up' in locals(): conn_up.rollback()
                        st.error(f"Error saving players locally: {e}")
                    finally:
                        conn_up.close()
                
                if saved_via_sdk:
                    st.cache_data.clear()
                    st.success("Players saved")
                    st.rerun()

        st.divider()
        st.subheader("Schedule Manager")
        teams_df = get_teams_list_full()
        weeks = list(range(1, 7)) # 6 weeks of regular season
        w = st.selectbox("Week", weeks, index=0, key="schedule_week_select_main")
        gnames = sorted([x for x in teams_df['group_name'].dropna().unique().tolist()])
        gsel = st.selectbox("Group", gnames + [""] , index=(0 if gnames else 0), key="schedule_group_select")
        tnames = teams_df['name'].tolist()
        t1 = st.selectbox("Team 1", tnames, key="schedule_team1_select")
        t2 = st.selectbox("Team 2", tnames, index=(1 if len(tnames)>1 else 0), key="schedule_team2_select")
        fmt = st.selectbox("Format", ["BO1","BO3","BO5"], index=1, key="schedule_format_select")
        if st.button("Add Match", key="schedule_add_match_btn"):
            id1 = int(teams_df[teams_df['name'] == t1].iloc[0]['id'])
            id2 = int(teams_df[teams_df['name'] == t2].iloc[0]['id'])
            
            saved_via_sdk = False
            if supabase:
                try:
                    payload = {
                        "week": int(w), 
                        "group_name": gsel or None, 
                        "status": "scheduled", 
                        "format": fmt, 
                        "team1_id": id1, 
                        "team2_id": id2, 
                        "score_t1": 0, 
                        "score_t2": 0, 
                        "maps_played": 0, 
                        "match_type": "regular"
                    }
                    supabase.table("matches").insert(payload).execute()
                    saved_via_sdk = True
                    st.success("Match added (Cloud)")
                except Exception as e:
                    st.warning(f"SDK Add Match failed: {e}")

            if not saved_via_sdk:
                conn_ins = get_conn()
                try:
                    conn_ins.execute("INSERT INTO matches (week, group_name, status, format, team1_id, team2_id, score_t1, score_t2, maps_played, match_type) VALUES (%s, %s, 'scheduled', %s, %s, %s, 0, 0, 0, 'regular')", (int(w), gsel or None, fmt, id1, id2))
                    conn_ins.commit()
                    st.success("Match added (Local)")
                except Exception as e:
                    st.error(f"Error adding match locally: {e}")
                finally:
                    conn_ins.close()
            st.rerun()
        
        st.markdown("### Bulk Add From Text (Preview)")
        week_bulk = st.selectbox("Week for pasted matches", weeks, index=weeks.index(w) if w in weeks else 0, key="bulk_week_select")
        fmt_bulk = st.selectbox("Format for pasted matches", ["BO1","BO3","BO5"], index=1, key="bulk_fmt_select")
        sched_text = st.text_area("Paste schedule text", height=160, placeholder="——— GROUP ————————— Team A vs Team B ...", key="bulk_text_area")
        if st.button("Parse Matches", key="bulk_parse_btn"):
            parsed = parse_schedule_text(sched_text or "", week_bulk)
            st.session_state['bulk_schedule_preview'] = {"matches": parsed, "week": week_bulk, "format": fmt_bulk}
        
        if st.session_state.get('bulk_schedule_preview'):
            prev = st.session_state['bulk_schedule_preview']
            matches_prev = prev.get("matches", [])
            if matches_prev:
                import pandas as pd
                df_prev = pd.DataFrame(matches_prev)
                if not df_prev.empty:
                    st.dataframe(df_prev[['week','group','t1_name','t2_name']], use_container_width=True, hide_index=True)
            else:
                st.info("No valid matches parsed.")
            
            cprev1, cprev2 = st.columns(2)
            with cprev1:
                if st.button("Confirm Save Parsed Matches", key="bulk_confirm_btn"):
                    added = 0
                    for m in matches_prev:
                        id1 = int(m['t1_id'])
                        id2 = int(m['t2_id'])
                        group_name = m['group'] if m['group'] and m['group'] != "Unknown" else gsel or None
                        saved_via_sdk = False
                        if supabase:
                            try:
                                payload = {
                                    "week": int(m['week']), 
                                    "group_name": group_name, 
                                    "status": "scheduled", 
                                    "format": prev.get("format", fmt), 
                                    "team1_id": id1, 
                                    "team2_id": id2, 
                                    "score_t1": 0, 
                                    "score_t2": 0, 
                                    "maps_played": 0, 
                                    "match_type": "regular"
                                }
                                supabase.table("matches").insert(payload).execute()
                                saved_via_sdk = True
                                added += 1
                            except Exception:
                                pass
                        if not saved_via_sdk:
                            conn_ins = get_conn()
                            try:
                                conn_ins.execute("INSERT INTO matches (week, group_name, status, format, team1_id, team2_id, score_t1, score_t2, maps_played, match_type) VALUES (%s, %s, 'scheduled', %s, %s, %s, 0, 0, 0, 'regular')", (int(m['week']), group_name, prev.get("format", fmt), id1, id2))
                                conn_ins.commit()
                                added += 1
                            except Exception:
                                pass
                            finally:
                                conn_ins.close()
                    st.success(f"Added {added} matches")
                    st.cache_data.clear()
                    st.session_state.pop('bulk_schedule_preview', None)
                    st.rerun()
            with cprev2:
                if st.button("Reset Preview", key="bulk_reset_btn"):
                    st.session_state.pop('bulk_schedule_preview', None)
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
    
    if not players_df.empty:
        players_df = players_df.copy()
        players_df['display_label'] = players_df.apply(lambda r: f"{r['name']} ({r['riot_id']})" if r['riot_id'] and str(r['riot_id']).strip() else r['name'], axis=1)
        
        opts = players_df['display_label'].tolist()
        sel = st.selectbox("Select a Player", opts)
        
        if sel:
            pid = int(players_df[players_df['display_label'] == sel].iloc[0]['id'])
            prof = get_player_profile(pid)
            # Initialize safe defaults to avoid NameError in templating
            pp_display_name = 'Player'
            pp_games = 0
            pp_avg_acs = 0
            pp_kd_ratio = 0
            pp_total_assists = 0
            pp_total_kills = 0
            pp_total_deaths = 0
            pp_sr_avg_acs = 0
            pp_sr_k = 0
            pp_sr_d = 0
            pp_sr_a = 0
            pp_lg_avg_acs = 0
            pp_lg_k = 0
            pp_lg_d = 0
            pp_lg_a = 0
            _info = {}
            
            if prof:
                import math
                _info = prof.get('info', {}) if isinstance(prof.get('info'), dict) else {}
                # Precomputed safe values to avoid NameError and missing keys
                pp_display_name = prof.get('display_name') or 'Player'
                pp_games = prof.get('games', 0) if prof.get('games') is not None else 0
                pp_avg_acs = prof.get('avg_acs', 0) if prof.get('avg_acs') is not None else 0
                pp_kd_ratio = prof.get('kd_ratio', 0) if prof.get('kd_ratio') is not None else 0
                pp_total_assists = prof.get('total_assists', 0) if prof.get('total_assists') is not None else 0
                pp_total_kills = prof.get('total_kills', 0) if prof.get('total_kills') is not None else 0
                pp_total_deaths = prof.get('total_deaths', 0) if prof.get('total_deaths') is not None else 0
                pp_sr_avg_acs = prof.get('sr_avg_acs', 0) if prof.get('sr_avg_acs') is not None else 0
                pp_sr_k = prof.get('sr_k', 0) if prof.get('sr_k') is not None else 0
                pp_sr_d = prof.get('sr_d', 0) if prof.get('sr_d') is not None else 0
                pp_sr_a = prof.get('sr_a', 0) if prof.get('sr_a') is not None else 0
                pp_lg_avg_acs = prof.get('lg_avg_acs', 0) if prof.get('lg_avg_acs') is not None else 0
                pp_lg_k = prof.get('lg_k', 0) if prof.get('lg_k') is not None else 0
                pp_lg_d = prof.get('lg_d', 0) if prof.get('lg_d') is not None else 0
                pp_lg_a = prof.get('lg_a', 0) if prof.get('lg_a') is not None else 0
                # Header Card
                st.markdown(f"""<div class="custom-card" style="margin-bottom: 2rem;">
<div style="display: flex; align-items: center; gap: 20px;">
<div style="background: var(--primary-blue); width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: var(--bg-dark);">
{html.escape(str((_info.get('name') or 'P')[0].upper()))}
</div>
<div>
<h2 style="margin: 0; color: var(--primary-blue); font-family: 'Orbitron';">{html.escape(str(pp_display_name))}</h2>
<div style="color: var(--text-dim); font-size: 1.1rem;">{html.escape(str(_info.get('team') or 'Free Agent'))}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            
            # Metrics Grid
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Games</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{pp_games}</div>
</div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Avg ACS</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-blue); margin: 10px 0;">{pp_avg_acs}</div>
</div>""", unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">KD Ratio</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--primary-red); margin: 10px 0;">{pp_kd_ratio}</div>
</div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="custom-card" style="text-align: center;">
<div style="color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Assists</div>
<div style="font-size: 2rem; font-family: 'Orbitron'; color: var(--text-main); margin: 10px 0;">{pp_total_assists}</div>
</div>""", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Comparison Radar or Bar Chart
            st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">PERFORMANCE BENCHMARKS</h3>', unsafe_allow_html=True)
            
            _games = pp_games or 0
            try:
                _games = float(_games)
            except Exception:
                _games = 0.0
            if isinstance(_games, float) and math.isnan(_games):
                _games = 0.0
            _games = int(_games)
            cmp_df = pd.DataFrame({
                'Metric': ['ACS','Kills/Match','Deaths/Match','Assists/Match'],
                'Player': [pp_avg_acs, pp_total_kills/max(_games,1), pp_total_deaths/max(_games,1), pp_total_assists/max(_games,1)],
                'Rank Avg': [pp_sr_avg_acs, pp_sr_k, pp_sr_d, pp_sr_a],
                'League Avg': [pp_lg_avg_acs, pp_lg_k, pp_lg_d, pp_lg_a],
            })
            
            # Plotly Bar Chart for comparison with dual axis
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            fig_cmp = make_subplots(specs=[[{"secondary_y": True}]])
            
            # ACS (Primary Y-Axis)
            fig_cmp.add_trace(go.Bar(name='Player', x=['ACS'], y=[pp_avg_acs], marker_color='#3FD1FF', showlegend=True, legendgroup='bench'), secondary_y=False)
            fig_cmp.add_trace(go.Bar(name='Rank Avg', x=['ACS'], y=[pp_sr_avg_acs], marker_color='#FF4655', opacity=0.8, showlegend=True, legendgroup='bench'), secondary_y=False)
            fig_cmp.add_trace(go.Bar(name='League Avg', x=['ACS'], y=[pp_lg_avg_acs], marker_color='#ECE8E1', opacity=0.8, showlegend=True, legendgroup='bench'), secondary_y=False)
            
            # Per-Match Stats (Secondary Y-Axis)
            other_metrics = ['Kills/Match', 'Deaths/Match', 'Assists/Match']
            player_others = [pp_total_kills/max(_games,1), pp_total_deaths/max(_games,1), pp_total_assists/max(_games,1)]
            rank_others = [pp_sr_k, pp_sr_d, pp_sr_a]
            league_others = [pp_lg_k, pp_lg_d, pp_lg_a]
            
            # Do not duplicate legend entries; keep only three keys
            fig_cmp.add_trace(go.Bar(name='Player', x=other_metrics, y=player_others, marker_color='#3FD1FF', showlegend=False, legendgroup='bench'), secondary_y=True)
            fig_cmp.add_trace(go.Bar(name='Rank Avg', x=other_metrics, y=rank_others, marker_color='#FF4655', opacity=0.8, showlegend=False, legendgroup='bench'), secondary_y=True)
            fig_cmp.add_trace(go.Bar(name='League Avg', x=other_metrics, y=league_others, marker_color='#ECE8E1', opacity=0.8, showlegend=False, legendgroup='bench'), secondary_y=True)
            
            fig_cmp.update_layout(
                barmode='group', 
                height=400,
                title_text="Performance vs Benchmarks (ACS on Left, Others on Right)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_cmp.update_yaxes(title_text="Average Combat Score (ACS)", secondary_y=False)
            fig_cmp.update_yaxes(title_text="K/D/A Per Match", secondary_y=True)
            try:
                max_acs = max(pp_avg_acs, pp_sr_avg_acs, pp_lg_avg_acs)
                fig_cmp.update_yaxes(range=[0, max_acs * 1.2], secondary_y=False)
                max_stats = max(player_others + rank_others + league_others)
                fig_cmp.update_yaxes(range=[0, max_stats * 1.2], secondary_y=True)
            except Exception:
                pass
            
            st.plotly_chart(apply_plotly_theme(fig_cmp), use_container_width=True)
            dbg_df = cmp_df.copy()
            try:
                dbg_df = dbg_df.round(2)
            except Exception:
                pass
            st.markdown('<h4 style="color: var(--text-dim); font-family: \'Orbitron\';">DEBUG: BENCHMARK VALUES</h4>', unsafe_allow_html=True)
            st.dataframe(dbg_df, use_container_width=True, hide_index=True)
            bm = prof.get('bench_meta', {}) if isinstance(prof, dict) else {}
            st.caption(f"Bench computed: {'yes' if bm.get('has_bench') else 'no'} • Rank non-zero: {'yes' if bm.get('sr_nonzero') else 'no'} • League non-zero: {'yes' if bm.get('lg_nonzero') else 'no'}")

            # ACS Trend
            tr_df = prof.get('trend')
            if isinstance(tr_df, pd.DataFrame) and not tr_df.empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">ACS TREND</h3>', unsafe_allow_html=True)
                acs_fig = go.Figure()
                acs_fig.add_trace(go.Scatter(x=tr_df['label'], y=tr_df['avg_acs'], mode='lines+markers', name='ACS', line=dict(color='#3FD1FF')))
                acs_fig.update_layout(height=320)
                st.plotly_chart(apply_plotly_theme(acs_fig), use_container_width=True)

                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">KDA TREND</h3>', unsafe_allow_html=True)
                kda_fig = go.Figure()
                kda_fig.add_trace(go.Scatter(x=tr_df['label'], y=tr_df['kda'], mode='lines+markers', name='KDA', line=dict(color='#FF4655')))
                kda_fig.update_layout(height=320)
                st.plotly_chart(apply_plotly_theme(kda_fig), use_container_width=True)
            
            # Agent Insights
            ag_df = prof.get('agents')
            if isinstance(ag_df, pd.DataFrame) and not ag_df.empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">AGENT INSIGHTS</h3>', unsafe_allow_html=True)
                import plotly.express as px
                # Usage Pie
                pie_fig = px.pie(ag_df, names='agent', values='maps', title='Usage by Agent', hole=0.35, color_discrete_sequence=['#3FD1FF','#FF4655','#ECE8E1','#0B192E'])
                st.plotly_chart(apply_plotly_theme(pie_fig), use_container_width=True)
                # Performance Bar
                bar_fig = px.bar(ag_df.sort_values('avg_acs', ascending=False), x='agent', y='avg_acs', title='Average ACS by Agent', color='avg_acs', color_continuous_scale='Blues')
                bar_fig.update_layout(height=360)
                st.plotly_chart(apply_plotly_theme(bar_fig), use_container_width=True)
                # Top Agent callout
                top_agent = prof.get('top_agent') or 'N/A'
                st.info(f"Top Agent: {top_agent} — Maps: {int(ag_df[ag_df['agent']==top_agent]['maps'].iloc[0]) if top_agent!='N/A' and not ag_df.empty else 0}, Avg ACS: {round(float(ag_df[ag_df['agent']==top_agent]['avg_acs'].iloc[0]) if top_agent!='N/A' and not ag_df.empty else 0,1)}")

            # Map Insights
            ms_df = prof.get('maps_summary')
            if isinstance(ms_df, pd.DataFrame) and not ms_df.empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">MAP PERFORMANCE</h3>', unsafe_allow_html=True)
                import plotly.express as px
                x_col = 'map_label' if 'map_label' in ms_df.columns else ('map_name' if 'map_name' in ms_df.columns else 'map_index')
                map_bar = px.bar(ms_df.sort_values('avg_acs', ascending=False), x=x_col, y='avg_acs', title='Average ACS by Map', color='avg_acs', color_continuous_scale='Teal')
                st.plotly_chart(apply_plotly_theme(map_bar), use_container_width=True)

            # Sub Impact Comparison
            si = prof.get('sub_impact')
            if isinstance(si, dict) and si:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">SUB IMPACT</h3>', unsafe_allow_html=True)
                sub_fig = make_subplots(specs=[[{"secondary_y": True}]])
                sub_fig.add_trace(go.Bar(name='Starter ACS', x=['ACS'], y=[si.get('starter_acs', 0.0)], marker_color='#3FD1FF'), secondary_y=False)
                sub_fig.add_trace(go.Bar(name='Sub ACS', x=['ACS'], y=[si.get('sub_acs', 0.0)], marker_color='#ECE8E1', opacity=0.7), secondary_y=False)
                sub_fig.add_trace(go.Bar(name='Starter KDA', x=['KDA'], y=[si.get('starter_kda', 0.0)], marker_color='#FF4655'), secondary_y=True)
                sub_fig.add_trace(go.Bar(name='Sub KDA', x=['KDA'], y=[si.get('sub_kda', 0.0)], marker_color='#FFA5AE', opacity=0.7), secondary_y=True)
                sub_fig.update_layout(barmode='group', height=320)
                sub_fig.update_yaxes(title_text='ACS', secondary_y=False)
                sub_fig.update_yaxes(title_text='KDA', secondary_y=True)
                st.plotly_chart(apply_plotly_theme(sub_fig), use_container_width=True)
            
            maps_df = prof.get('maps')
            if isinstance(maps_df, pd.DataFrame) and not maps_df.empty:
                st.markdown('<h3 style="color: var(--primary-blue); font-family: \'Orbitron\';">RECENT MATCHES</h3>', unsafe_allow_html=True)
                maps_display = maps_df[['match_id','map_index','agent','acs','kills','deaths','assists','is_sub']].copy()
                maps_display.columns = ['Match ID', 'Map', 'Agent', 'ACS', 'K', 'D', 'A', 'Sub']
                st.dataframe(maps_display, hide_index=True, use_container_width=True)

elif page == "Diagnostics":
    st.markdown('<h1 class="main-header">CONNECTION DIAGNOSTICS</h1>', unsafe_allow_html=True)
    st.info("Use this page to troubleshoot database connection issues and verify Supabase configuration.")
    run_connection_diagnostics()
    
    st.markdown("---")
    st.subheader("Manual Connection Test")
    if st.button("Run PostgreSQL Connection Test"):
        with st.spinner("Connecting..."):
            try:
                conn = get_conn()
                is_postgres = not getattr(conn, 'is_sqlite', isinstance(conn, sqlite3.Connection))
                if is_postgres:
                    st.success("✅ Successfully connected to PostgreSQL via psycopg2!")
                    # Try a simple query
                    res = conn.execute("SELECT 1").fetchone()
                    st.write(f"Test Query Result: {res}")
                else:
                    st.warning("⚠️ Connected to local SQLite fallback. PostgreSQL connection failing.")
                conn.close()
            except Exception as e:
                st.error(f"Connection Failed: {e}")
