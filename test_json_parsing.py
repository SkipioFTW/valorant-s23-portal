import os
import json
import pandas as pd
import sqlite3
import re

DB_PATH = "valorant_s23.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_all_players():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM players", conn)
    conn.close()
    return df

def parse_tracker_json(jsdata, team1_id, team2_id):
    """
    Parses Tracker.gg JSON data and matches it to team1_id and team2_id.
    Returns (json_suggestions, map_name, t1_rounds, t2_rounds)
    """
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
        
        print(f"DEBUG: Team 1 Roster (from DB): RIDs={t1_rids}, Names={t1_names}")
        print(f"DEBUG: Team 2 Roster (from DB): RIDs={t2_rids}, Names={t2_names}")
        
        team_ids_in_json = [ts.get("attributes", {}).get("teamId") for ts in team_segments]
        
        # Count matches for each Tracker team against our rosters
        # score[tracker_team_id][db_team_id]
        scores = {tid: {1: 0, 2: 0} for tid in team_ids_in_json}
        
        p_segs = [s for s in segments if s.get("type") == "player-summary"]
        print(f"DEBUG: Found {len(p_segs)} player-summary segments")
        
        for p_seg in p_segs:
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
                        for tn in t1_names_clean:
                            if name_part in tn or tn in name_part:
                                is_t1 = True
                                break
                    if is_t1:
                        scores[t_id][1] += 1
                        print(f"DEBUG: Player {rid_clean} matched Team 1 roster (Tracker Team: {t_id})")
                    
                    # Match vs Team 2
                    is_t2 = rid_clean in t2_rids or rid_clean in t2_names or name_part in t2_names or name_part in t2_names_clean
                    if not is_t2:
                        for tn in t2_names_clean:
                            if name_part in tn or tn in name_part:
                                is_t2 = True
                                break
                    if is_t2:
                        scores[t_id][2] += 1
                        print(f"DEBUG: Player {rid_clean} matched Team 2 roster (Tracker Team: {t_id})")
        
        print(f"DEBUG: Scores per Tracker Team: {scores}")
        
        # Decision logic:
        # Option A: TrackerTeam0 is Team 1, TrackerTeam1 is Team 2
        score_a = scores[team_ids_in_json[0]][1] + scores[team_ids_in_json[1]][2]
        # Option B: TrackerTeam0 is Team 2, TrackerTeam1 is Team 1
        score_b = scores[team_ids_in_json[0]][2] + scores[team_ids_in_json[1]][1]
        
        print(f"DEBUG: Score Option A (T0=T1, T1=T2): {score_a}")
        print(f"DEBUG: Score Option B (T0=T2, T1=T1): {score_b}")

        if score_a >= score_b and score_a > 0:
            tracker_team_1_id = team_ids_in_json[0]
            print(f"DEBUG: Option A selected. Tracker Team '{tracker_team_1_id}' is Team 1.")
        elif score_b > score_a:
            tracker_team_1_id = team_ids_in_json[1]
            print(f"DEBUG: Option B selected. Tracker Team '{tracker_team_1_id}' is Team 1.")
        else:
            # Tie or 0 matches? Default to first team
            tracker_team_1_id = team_ids_in_json[0]
            print(f"DEBUG: Tie or no matches, defaulting to Tracker Team '{tracker_team_1_id}' as Team 1.")
    else:
        if team_segments:
            tracker_team_1_id = team_segments[0].get("attributes", {}).get("teamId")
        else:
            tracker_team_1_id = None

    for seg in segments:
        if seg.get("type") == "player-summary":
            metadata = seg.get("metadata", {})
            platform_info = metadata.get("platformInfo", {})
            rid = platform_info.get("platformUserIdentifier") or platform_info.get("platformUserHandle")
            
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
                matched_name = riot_id_to_name.get(rid_lower)
                
                if not matched_name:
                    name_part = rid.split('#')[0].lower()
                    matched_name = name_to_name.get(name_part) or name_to_name.get(rid_lower)
                
                json_suggestions[rid_lower] = {
                    'name': matched_name,
                    'tracker_name': rid,
                    'acs': int(acs) if acs is not None else 0, 
                    'k': int(k) if k is not None else 0, 
                    'd': int(d) if d is not None else 0, 
                    'a': int(a) if a is not None else 0, 
                    'agent': agent,
                    'team_num': our_team_num
                }
    
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
            
    return json_suggestions, map_name, t1_r, t2_r

def test_json(match_id_in_db, json_filename):
    # Convert to standard int if it's numpy.int64
    match_id_in_db = int(match_id_in_db)
    
    print(f"\n{'='*60}")
    print(f"TESTING MATCH ID {match_id_in_db} WITH {json_filename}")
    print(f"{'='*60}")
    
    conn = get_conn()
    try:
        match_query = pd.read_sql("SELECT * FROM matches WHERE id=?", conn, params=(match_id_in_db,))
        if match_query.empty:
            print(f"❌ Error: Match ID {match_id_in_db} not found in database.")
            return
        m = match_query.iloc[0]
        t1_id = int(m['team1_id'])
        t2_id = int(m['team2_id'])
        
        t1_name_query = pd.read_sql("SELECT name FROM teams WHERE id=?", conn, params=(t1_id,))
        t2_name_query = pd.read_sql("SELECT name FROM teams WHERE id=?", conn, params=(t2_id,))
        
        t1_name = t1_name_query.iloc[0]['name'] if not t1_name_query.empty else f"Team {t1_id}"
        t2_name = t2_name_query.iloc[0]['name'] if not t2_name_query.empty else f"Team {t2_id}"
    finally:
        conn.close()
    
    print(f"DB Match: {t1_name} (ID: {t1_id}) vs {t2_name} (ID: {t2_id})")
    
    json_path = os.path.join("matches", json_filename)
    with open(json_path, 'r', encoding='utf-8') as f:
        jsdata = json.load(f)
    
    suggestions, map_name, t1_r, t2_r = parse_tracker_json(jsdata, t1_id, t2_id)
    
    print(f"\nRESULT:")
    print(f"Map: {map_name}")
    print(f"Score: {t1_name} {t1_r} - {t2_r} {t2_name}")
    
    print(f"\nPLAYER SUGGESTIONS:")
    print(f"{'Team':<6} | {'Tracker Name':<25} | {'Matched Name':<20} | {'Agent':<12} | {'ACS':<5} | {'K/D/A'}")
    print("-" * 90)
    
    for rid, s in sorted(suggestions.items(), key=lambda x: (x[1]['team_num'], x[1]['name'] or '')):
        team_label = f"T{s['team_num']}"
        matched = s['name'] or "---"
        kda = f"{s['k']}/{s['d']}/{s['a']}"
        print(f"{team_label:<6} | {s['tracker_name']:<25} | {matched:<20} | {s['agent']:<12} | {s['acs']:<5} | {kda}")

if __name__ == "__main__":
    # You can change these to test different matches
    try:
        # Manually test Match ID 1 (TBA vs G&T) with the Breeze JSON
        # Team 1 is Total Bad Asses (ID: 46), Team 2 is GIN AND TOXIC (ID: 16)
        breeze_json = "match_4e473784-f3f5-450e-9f1b-66ba5e90be01.json"
        
        if os.path.exists(os.path.join("matches", breeze_json)):
            test_json(1, breeze_json)
        else:
            print(f"Breeze JSON {breeze_json} not found in matches/ folder.")
            
        # Also test Match ID 1 with the Bind JSON
        bind_json = "match_0a6ecd9e-c88f-41c4-ab49-58c0c5c8fd7d.json"
        if os.path.exists(os.path.join("matches", bind_json)):
            test_json(1, bind_json)
            
    except Exception as e:
        print(f"Error during test: {e}")
