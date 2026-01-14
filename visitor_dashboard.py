import streamlit as st
import sqlite3
import pandas as pd
import os
import hashlib
import hmac
import secrets

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
    try:
        c.execute("ALTER TABLE players ADD COLUMN rank TEXT")
    except sqlite3.OperationalError:
        pass
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
    try:
        c.execute("ALTER TABLE teams ADD COLUMN logo_path TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (22, 'Season 22', 0)")
    c.execute("INSERT OR IGNORE INTO seasons (id, name, is_active) VALUES (23, 'Season 23', 1)")
    c.execute("SELECT id, group_name FROM teams")
    teams = c.fetchall()
    for tid, grp in teams:
        c.execute("INSERT OR IGNORE INTO team_history (team_id, season_id, group_name) VALUES (?, 23, ?)", (tid, grp))
    conn.commit()
    conn.close()

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
    conn.execute("INSERT INTO admins (username, password_hash, salt, is_active) VALUES (?, ?, ?, 1)", (username, ph, salt))
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
        matches_df = pd.read_sql_query("SELECT * FROM matches WHERE status='completed'", conn)
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
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
                stats[t1]['Points'] += 15
            else:
                stats[t1]['Losses'] += 1
                stats[t1]['Points'] += s1
        if t2 in stats:
            stats[t2]['Played'] += 1
            stats[t2]['RD'] += (s2 - s1)
            if s2 > s1:
                stats[t2]['Wins'] += 1
                stats[t2]['Points'] += 15
            else:
                stats[t2]['Losses'] += 1
                stats[t2]['Points'] += s2
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
            SELECT p.name, t.tag as team,
                   COUNT(ms.id) as games,
                   AVG(ms.acs) as avg_acs,
                   SUM(ms.kills) as total_kills,
                   SUM(ms.deaths) as total_deaths,
                   SUM(ms.assists) as total_assists
            FROM match_stats ms
            JOIN players p ON ms.player_id = p.id
            LEFT JOIN teams t ON ms.team_id = t.id
            GROUP BY p.id
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

st.set_page_config(page_title="S23 Portal", layout="wide")

st.title("Valorant S23 • Portal")

ensure_base_schema()
init_admin_table()
init_match_stats_map_table()
ensure_upgrade_schema()

auth_box = st.sidebar.container()
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

# Seed admin from secrets or environment
seed_user = get_secret("ADMIN_SEED_USER")
seed_pwd = get_secret("ADMIN_SEED_PWD")
if not admin_exists() and seed_user and seed_pwd:
    try:
        create_admin(seed_user, seed_pwd)
    except:
        pass

with auth_box:
    if not admin_exists():
        st.info("Admin not configured. Set ADMIN_SEED_USER and ADMIN_SEED_PWD.")
    else:
        if not st.session_state['is_admin']:
            st.subheader("Admin Login")
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                tok = st.text_input("Admin Token", type="password")
                s = st.form_submit_button("Login")
                if s:
                    env_tok = get_secret("ADMIN_LOGIN_TOKEN", "")
                    if authenticate(u, p) and hmac.compare_digest(tok or "", env_tok):
                        st.session_state['is_admin'] = True
                        st.session_state['username'] = u
                        st.success("Logged in")
                        st.rerun()
                    else:
                        st.error("Invalid credentials or token")
        else:
            st.success(f"Admin: {st.session_state['username']}")
            if st.button("Logout"):
                st.session_state['is_admin'] = False
                st.session_state['username'] = None
                st.rerun()

pages = [
    "Overview & Standings",
    "Matches",
    "Match Summary",
    "Player Leaderboard",
    "Players Directory",
    "Teams",
]
if st.session_state['is_admin']:
    pages.append("Admin Panel")
page = st.sidebar.radio("Go to", pages)

if page == "Overview & Standings":
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
        groups = df['group_name'].unique()
        cols = st.columns(len(groups))
        for i, grp in enumerate(groups):
            with cols[i % len(cols)]:
                st.subheader(f"Group {grp}")
                grp_df = df[df['group_name'] == grp]
                for _, row in grp_df.iterrows():
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if row['logo_display']:
                            st.image(row['logo_display'], width=50)
                    with c2:
                        st.markdown(f"**{row['name']}**")
                        st.caption(f"Seasons: {row['season_count']} • W: {row['Wins']} • Pts: {row['Points']}")
                        with st.expander("Roster"):
                            conn_r = get_conn()
                            roster = pd.read_sql_query(
                                "SELECT name, rank FROM players WHERE default_team_id=? ORDER BY name",
                                conn_r,
                                params=(int(row['id']),),
                            )
                            conn_r.close()
                            if roster.empty:
                                st.write("No players yet")
                            else:
                                st.dataframe(roster, hide_index=True, use_container_width=True)
                st.dataframe(
                    grp_df[['name', 'season_count', 'Played', 'Wins', 'Losses', 'Points', 'RD']],
                    hide_index=True,
                    column_config={"season_count": st.column_config.NumberColumn("Seasons")},
                )
    else:
        st.info("No standings data yet.")

elif page == "Matches":
    week = st.sidebar.selectbox("Week", [1, 2, 3, 4, 5], index=0)
    df = get_week_matches(week)
    if df.empty:
        st.info("No matches for this week.")
    else:
        st.subheader("Scheduled")
        sched = df[df['status'] != 'completed']
        if sched.empty:
            st.caption("None")
        else:
            for _, m in sched.iterrows():
                st.write(f"{m['t1_name']} vs {m['t2_name']} • {m['format']}")
        st.subheader("Completed")
        comp = df[df['status'] == 'completed']
        for _, m in comp.iterrows():
            st.markdown(f"**{m['t1_name']} {m['score_t1']}–{m['score_t2']} {m['t2_name']}** • {m['format']}")
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
    week = st.sidebar.selectbox("Week", [1, 2, 3, 4, 5], index=0, key="wk_sum")
    df = get_week_matches(week)
    if df.empty:
        st.info("No matches for this week.")
    else:
        opts = df.apply(lambda r: f"ID {r['id']}: {r['t1_name']} vs {r['t2_name']} ({r['group_name']})", axis=1).tolist()
        sel = st.selectbox("Match", list(range(len(opts))), format_func=lambda i: opts[i])
        m = df.iloc[sel]
        st.subheader(f"{m['t1_name']} {m['score_t1']}–{m['score_t2']} {m['t2_name']} • {m['format']}")
        maps_df = get_match_maps(int(m['id']))
        if maps_df.empty:
            st.info("No maps recorded")
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
            st.divider()
            for i in sorted(maps_df['map_index'].unique().tolist()):
                st.caption(f"Map {i+1}")
                conn_s = get_conn()
                s1 = pd.read_sql("SELECT p.name, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub FROM match_stats_map ms JOIN players p ON ms.player_id=p.id WHERE ms.match_id=? AND ms.map_index=? AND ms.team_id=?", conn_s, params=(int(m['id']), i, int(m['t1_id'])))
                s2 = pd.read_sql("SELECT p.name, ms.agent, ms.acs, ms.kills, ms.deaths, ms.assists, ms.is_sub FROM match_stats_map ms JOIN players p ON ms.player_id=p.id WHERE ms.match_id=? AND ms.map_index=? AND ms.team_id=?", conn_s, params=(int(m['id']), i, int(m['t2_id'])))
                conn_s.close()
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**{m['t1_name']}**")
                    if s1.empty:
                        st.caption("No scoreboard")
                    else:
                        st.dataframe(s1.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)
                with c2:
                    st.markdown(f"**{m['t2_name']}**")
                    if s2.empty:
                        st.caption("No scoreboard")
                    else:
                        st.dataframe(s2.rename(columns={'name':'Player','agent':'Agent','acs':'ACS','kills':'K','deaths':'D','assists':'A','is_sub':'Sub'}), hide_index=True, use_container_width=True)

elif page == "Player Leaderboard":
    df = get_player_leaderboard()
    if df.empty:
        st.info("No player stats yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

elif page == "Players Directory":
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
    ranks = ["Unranked", "Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"]
    c1, c2 = st.columns([2, 1])
    with c1:
        rf = st.multiselect("Rank", ranks, default=ranks)
    with c2:
        q = st.text_input("Search name or Riot ID")
    out = players_df[players_df['rank'].isin(rf)]
    if q:
        s = q.lower()
        out = out[out.apply(lambda r: s in str(r['name']).lower() or s in str(r['riot_id']).lower(), axis=1)]
    st.dataframe(out, use_container_width=True, hide_index=True)

elif page == "Teams":
    conn = get_conn()
    teams = pd.read_sql("SELECT id, name, tag, group_name, logo_path FROM teams ORDER BY name", conn)
    all_players = pd.read_sql("SELECT id, name, default_team_id FROM players ORDER BY name", conn)
    conn.close()
    groups = ["All"] + sorted(teams['group_name'].dropna().unique().tolist())
    g = st.selectbox("Group", groups)
    show = teams if g == "All" else teams[teams['group_name'] == g]
    for _, row in show.iterrows():
        c1, c2 = st.columns([1, 3])
        with c1:
            lp = row['logo_path'] if row['logo_path'] and os.path.exists(row['logo_path']) else None
            if lp:
                st.image(lp, width=80)
        with c2:
            st.markdown(f"**{row['name']}**" + (f" • {row['tag']}" if pd.notna(row['tag']) else ""))
            st.caption(f"Group {row['group_name']}")
            conn_r = get_conn()
            roster = pd.read_sql_query(
                "SELECT id, name, rank FROM players WHERE default_team_id=? ORDER BY name",
                conn_r,
                params=(int(row['id']),),
            )
            conn_r.close()
            if roster.empty:
                st.write("No players yet")
            else:
                st.dataframe(roster[['name','rank']], hide_index=True, use_container_width=True)
            if st.session_state.get('is_admin'):
                st.divider()
                st.caption("Edit Team")
                with st.form(f"edit_team_{row['id']}"):
                    new_name = st.text_input("Name", value=row['name'])
                    new_tag = st.text_input("Tag", value=row['tag'] or "")
                    new_group = st.text_input("Group", value=row['group_name'] or "")
                    new_logo = st.text_input("Logo Path", value=row['logo_path'] or "")
                    save_team = st.form_submit_button("Save Team")
                    if save_team:
                        conn_u = get_conn()
                        conn_u.execute("UPDATE teams SET name=?, tag=?, group_name=?, logo_path=? WHERE id=?", (new_name, new_tag or None, new_group or None, new_logo or None, int(row['id'])))
                        conn_u.commit()
                        conn_u.close()
                        st.success("Team updated")
                        st.rerun()
                st.caption("Manage Roster")
                # Add player to roster
                unassigned = all_players[all_players['default_team_id'].isna()]
                add_sel = st.selectbox(f"Add Player to {row['name']}", [p for p in unassigned['name'].tolist()] + [""], index=len(unassigned['name'].tolist()))
                if add_sel:
                    pid = int(all_players[all_players['name'] == add_sel].iloc[0]['id'])
                    conn_a = get_conn()
                    conn_a.execute("UPDATE players SET default_team_id=? WHERE id=?", (int(row['id']), pid))
                    conn_a.commit()
                    conn_a.close()
                    st.success("Player added")
                    st.rerun()
                # Remove player from roster
                if not roster.empty:
                    rem_sel = st.selectbox(f"Remove Player from {row['name']}", [p for p in roster['name'].tolist()] + [""], index=len(roster['name'].tolist()))
                    if rem_sel:
                        pid = int(roster[roster['name'] == rem_sel].iloc[0]['id'])
                        conn_d = get_conn()
                        conn_d.execute("UPDATE players SET default_team_id=NULL WHERE id=?", (pid,))
                        conn_d.commit()
                        conn_d.close()
                        st.success("Player removed")
                        st.rerun()

elif page == "Admin Panel":
    if not st.session_state.get('is_admin'):
        st.warning("Admin only")
    else:
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
                maps_catalog = ["Ascent","Bind","Breeze","Fracture","Haven","Icebox","Lotus","Pearl","Split","Sunset"]
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
                for team_key, team_id, team_name in [("t1", int(m['t1_id']), m['t1_name']), ("t2", int(m['t2_id']), m['t2_name'])]:
                    st.caption(f"{team_name} players")
                    conn_p = get_conn()
                    roster_df = pd.read_sql("SELECT id, name FROM players WHERE default_team_id=? ORDER BY name", conn_p, params=(team_id,))
                    agents_df = pd.read_sql("SELECT name FROM agents ORDER BY name", conn_p)
                    existing = pd.read_sql("SELECT * FROM match_stats_map WHERE match_id=? AND map_index=? AND team_id=?", conn_p, params=(int(m['id']), map_idx, team_id))
                    conn_p.close()
                    roster_list = roster_df['name'].tolist()
                    roster_map = dict(zip(roster_df['name'], roster_df['id']))
                    agents_list = agents_df['name'].tolist()
                    rows = []
                    if not existing.empty:
                        for _, r in existing.iterrows():
                            pname = ""
                            if r['player_id']:
                                rp = get_conn().execute("SELECT name FROM players WHERE id=?", (r['player_id'],)).fetchone()
                                pname = rp[0] if rp else ""
                            sfname = ""
                            if r['subbed_for_id']:
                                sp = get_conn().execute("SELECT name FROM players WHERE id=?", (r['subbed_for_id'],)).fetchone()
                                sfname = sp[0] if sp else ""
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
                    rows = rows or ([{'player': roster_list[i] if i < len(roster_list) else "", 'is_sub': False, 'subbed_for': roster_list[i] if i < len(roster_list) else "", 'agent': agents_list[0] if agents_list else "", 'acs': 0, 'k':0,'d':0,'a':0} for i in range(min(5, max(1,len(roster_list))))])
                    with st.form(f"sb_{team_key}_{map_idx}"):
                        h1,h2,h3,h4,h5,h6,h7,h8 = st.columns([2,1.2,2,2,1,1,1,1])
                        h1.write("Player")
                        h2.write("Sub?")
                        h3.write("Subbing For")
                        h4.write("Agent")
                        h5.write("ACS")
                        h6.write("K")
                        h7.write("D")
                        h8.write("A")
                        entries = []
                        for i, rowd in enumerate(rows):
                            c1,c2,c3,c4,c5,c6,c7,c8 = st.columns([2,1.2,2,2,1,1,1,1])
                            psel = c1.selectbox(f"P{i}", roster_list + [""], index=(roster_list.index(rowd['player']) if rowd['player'] in roster_list else len(roster_list)), label_visibility="collapsed")
                            is_sub = c2.checkbox(f"S{i}", value=rowd['is_sub'], label_visibility="collapsed")
                            sf_sel = c3.selectbox(f"SF{i}", roster_list + [""], index=(roster_list.index(rowd['subbed_for']) if rowd['subbed_for'] in roster_list else (0 if roster_list else 0)), label_visibility="collapsed")
                            ag_sel = c4.selectbox(f"Ag{i}", agents_list + [""], index=(agents_list.index(rowd['agent']) if rowd['agent'] in agents_list else (0 if agents_list else 0)), label_visibility="collapsed")
                            acs = c5.number_input(f"ACS{i}", min_value=0, value=rowd['acs'], label_visibility="collapsed")
                            k = c6.number_input(f"K{i}", min_value=0, value=rowd['k'], label_visibility="collapsed")
                            d = c7.number_input(f"D{i}", min_value=0, value=rowd['d'], label_visibility="collapsed")
                            a = c8.number_input(f"A{i}", min_value=0, value=rowd['a'], label_visibility="collapsed")
                            entries.append({
                                'player_id': roster_map.get(psel),
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
        cfa, cfb, cfc = st.columns([2,2,2])
        with cfa:
            tf = st.multiselect("Team", [""] + team_names, default=[""] + team_names)
        with cfb:
            rf = st.multiselect("Rank", rvals, default=rvals)
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
            num_rows="dynamic",
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
