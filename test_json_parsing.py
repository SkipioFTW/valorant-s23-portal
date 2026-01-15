import os
import sys

print("🚀 Starting JSON Parsing Test Script...")
print("⏳ Loading libraries (this may take a few seconds)...")

import json
import pandas as pd
import sqlite3
from difflib import SequenceMatcher
import re

DB_PATH = "valorant_s23.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def test_parse(match_id, json_match_id, map_idx=0):
    print(f"\n--- Testing JSON Parsing for Match {match_id} and JSON {json_match_id} ---")
    
    # 1. Load Match Info
    conn = get_conn()
    m = pd.read_sql("SELECT * FROM matches WHERE id=?", conn, params=(match_id,)).iloc[0]
    
    # Get team names
    t1_name = pd.read_sql("SELECT name FROM teams WHERE id=?", conn, params=(int(m['team1_id']),)).iloc[0]['name']
    t2_name = pd.read_sql("SELECT name FROM teams WHERE id=?", conn, params=(int(m['team2_id']),)).iloc[0]['name']
    print(f"Match: {t1_name} vs {t2_name}")
    
    # 2. Load JSON
    json_path = f"matches/match_{json_match_id}.json"
    if not os.path.exists(json_path):
        print(f"❌ Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        jsdata = json.load(f)
    
    json_suggestions = {}
    segments = jsdata.get("data", {}).get("segments", [])
    
    # First pass: find team names/IDs to identify which Tracker team is which
    tracker_team_1_id = None
    team_segments = [s for s in segments if s.get("type") == "team-summary"]
    if len(team_segments) >= 2:
        # Use Riot IDs to match teams
        t1_roster = pd.read_sql("SELECT riot_id FROM players WHERE default_team_id=?", conn, params=(int(m['team1_id']),))['riot_id'].dropna().tolist()
        t1_roster = [str(r).strip() for r in t1_roster]
        
        potential_t1_id = team_segments[0].get("attributes", {}).get("teamId")
        t1_matches = 0
        for p_seg in [s for s in segments if s.get("type") == "player-summary"]:
            if p_seg.get("metadata", {}).get("teamId") == potential_t1_id:
                rid = p_seg.get("metadata", {}).get("platformInfo", {}).get("platformUserIdentifier")
                if rid and str(rid).strip() in t1_roster:
                    t1_matches += 1
        
        if t1_matches >= 1:
            tracker_team_1_id = potential_t1_id
            print(f"Matched Tracker Team 0 to {t1_name}")
        else:
            tracker_team_1_id = team_segments[1].get("attributes", {}).get("teamId")
            print(f"Matched Tracker Team 1 to {t1_name}")

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
                json_suggestions[rid] = {
                    'acs': int(acs) if acs is not None else 0, 
                    'k': int(k) if k is not None else 0, 
                    'd': int(d) if d is not None else 0, 
                    'a': int(a) if a is not None else 0, 
                    'agent': agent,
                    'team_num': our_team_num
                }

    print(f"Total suggestions found: {len(json_suggestions)}")

    # 3. Simulate Scoreboard Generation for Team 1 and Team 2
    all_df = pd.read_sql("SELECT id, name, riot_id FROM players ORDER BY name", conn)
    global_list = all_df.apply(lambda r: (f"{str(r['riot_id'])} ({r['name']})" if pd.notna(r['riot_id']) and str(r['riot_id']).strip() else r['name']), axis=1).tolist()
    label_to_riot = {label: str(rid).strip() for label, rid in zip(global_list, all_df['riot_id']) if pd.notna(rid) and str(rid).strip()}
    riot_to_label = {v: k for k, v in label_to_riot.items()}

    for team_key, team_id, team_name in [("t1", int(m['t1_id']), t1_name), ("t2", int(m['t2_id']), t2_name)]:
        print(f"\n--- {team_name} Scoreboard ---")
        roster_df = pd.read_sql("SELECT id, name, riot_id FROM players WHERE default_team_id=? ORDER BY name", conn, params=(team_id,))
        roster_list = roster_df.apply(lambda r: (f"{str(r['riot_id'])} ({r['name']})" if pd.notna(r['riot_id']) and str(r['riot_id']).strip() else r['name']), axis=1).tolist()
        
        our_team_num = 1 if team_key == "t1" else 2
        sug = json_suggestions
        
        rows = []
        team_sug_rids = [rid for rid, s in sug.items() if s.get('team_num') == our_team_num]
        
        used_roster_indices = set()
        for rid in team_sug_rids:
            s = sug[rid]
            db_label = riot_to_label.get(rid)
            if db_label:
                is_sub = False
                subbed_for = ""
                if db_label in roster_list:
                    idx = roster_list.index(db_label)
                    used_roster_indices.add(idx)
                    subbed_for = db_label
                else:
                    is_sub = True
                
                rows.append({
                    'player': db_label,
                    'is_sub': is_sub,
                    'subbed_for': subbed_for,
                    'agent': s.get('agent'),
                    'acs': s['acs'], 'k': s['k'], 'd': s['d'], 'a': s['a']
                })

        # Fill remaining with roster
        remaining_slots = 5 - len(rows)
        if remaining_slots > 0:
            for i, r_label in enumerate(roster_list):
                if i not in used_roster_indices and len(rows) < 5:
                    rows.append({
                        'player': r_label,
                        'is_sub': False,
                        'subbed_for': r_label,
                        'agent': "None",
                        'acs': 0, 'k': 0, 'd': 0, 'a': 0
                    })
        
        # Assign subbed_for
        unused_roster = [roster_list[i] for i in range(len(roster_list)) if i not in used_roster_indices]
        for row in rows:
            if row['is_sub'] and not row['subbed_for'] and unused_roster:
                row['subbed_for'] = unused_roster.pop(0)
            elif not row['subbed_for'] and roster_list:
                row['subbed_for'] = roster_list[0]

        # Final fallback
        while len(rows) < 5:
            rows.append({'player': "Empty", 'is_sub': False, 'subbed_for': "None", 'agent': "None", 'acs': 0, 'k': 0, 'd': 0, 'a': 0})

        # Output Results
        df_res = pd.DataFrame(rows)
        print(df_res.to_string(index=False))

    conn.close()

if __name__ == "__main__":
    # Check if matches folder exists
    if not os.path.exists("matches"):
        os.makedirs("matches")
        print("📁 Created 'matches' folder.")
    
    # Check for JSON files
    json_files = [f for f in os.listdir("matches") if f.endswith(".json")]
    if not json_files:
        print("❌ No JSON files found in 'matches/' folder.")
        print("👉 Please run 'python get_tracker_json.py' first to download a match JSON.")
        sys.exit(0)
    
    # List matches
    conn = get_conn()
    matches = pd.read_sql("SELECT m.id, t1.name as t1_name, t2.name as t2_name FROM matches m JOIN teams t1 ON m.team1_id=t1.id JOIN teams t2 ON m.team2_id=t2.id LIMIT 10", conn)
    conn.close()
    
    print("Available Matches:")
    print(matches)
    
    m_id = input("\nEnter Match ID from above: ")
    j_id = input("Enter JSON Match ID (e.g. fef14b8b-ddc7-4b91-b91c-905327c74325): ")
    
    test_parse(int(m_id), j_id)
