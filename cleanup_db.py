import sqlite3
import pandas as pd

DB_PATH = "valorant_s23.db"

def cleanup_duplicates():
    conn = sqlite3.connect(DB_PATH)
    
    print("--- Cleaning up Player Duplicates ---")
    # Get all players
    players = pd.read_sql("SELECT * FROM players", conn)
    players['name_lower'] = players['name'].str.lower().str.strip()
    players['riot_lower'] = players['riot_id'].str.lower().str.strip().fillna("")
    
    # 1. Exact Name + Riot ID Duplicates
    print("Checking for exact Name + Riot ID duplicates...")
    players['combined'] = players['name_lower'] + "||" + players['riot_lower']
    dupes = players[players.duplicated('combined', keep=False)].sort_values('combined')
    
    if not dupes.empty:
        print(f"Found {len(dupes)} duplicates. Merging...")
        for key, group in dupes.groupby('combined'):
            # Keep the one with most info
            # Priority: has team_id, has rank, has riot_id
            group = group.copy()
            group['info_score'] = (group['default_team_id'].notna().astype(int) * 2 + 
                                  group['rank'].notna().astype(int) + 
                                  (group['riot_id'] != "").astype(int))
            group = group.sort_values('info_score', ascending=False)
            
            keep_id = int(group.iloc[0]['id'])
            remove_ids = group.iloc[1:]['id'].astype(int).tolist()
            
            print(f"  Keeping ID {keep_id} ({group.iloc[0]['name']}), removing {remove_ids}")
            
            for rid in remove_ids:
                # Update references
                conn.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (keep_id, rid))
                conn.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (keep_id, rid))
                # Delete duplicate
                conn.execute("DELETE FROM players WHERE id = ?", (rid,))
        conn.commit()
    else:
        print("No exact Name + Riot ID duplicates found.")

    # 2. Name duplicates with empty Riot IDs
    print("\nChecking for name duplicates where some have Riot IDs and some don't...")
    players = pd.read_sql("SELECT * FROM players", conn) # Refresh
    players['name_lower'] = players['name'].str.lower().str.strip()
    
    for name, group in players.groupby('name_lower'):
        if len(group) > 1:
            # Check if one has a Riot ID and others don't
            has_riot = group[group['riot_id'].notna() & (group['riot_id'] != "")]
            if not has_riot.empty and len(has_riot) < len(group):
                keep_id = int(has_riot.iloc[0]['id'])
                remove_ids = group[~group['id'].isin(has_riot['id'])]['id'].astype(int).tolist()
                print(f"  Merging name '{name}': Keeping ID {keep_id} (has Riot ID), removing {remove_ids} (no Riot ID)")
                for rid in remove_ids:
                    conn.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (keep_id, rid))
                    conn.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (keep_id, rid))
                    conn.execute("DELETE FROM players WHERE id = ?", (rid,))
    conn.commit()

    # 3. Riot ID duplicates (same Riot ID, different names)
    print("\nChecking for Riot ID duplicates...")
    players = pd.read_sql("SELECT * FROM players", conn) # Refresh
    riot_ids = players[players['riot_id'].notna() & (players['riot_id'] != "")]
    riot_ids['riot_lower'] = riot_ids['riot_id'].str.lower().str.strip()
    
    dupe_riots = riot_ids[riot_ids.duplicated('riot_lower', keep=False)].sort_values('riot_lower')
    if not dupe_riots.empty:
        print(f"Found {len(dupe_riots)} Riot ID duplicates. Merging...")
        for riot, group in dupe_riots.groupby('riot_lower'):
            # Keep the one with most info or longer name?
            group = group.copy()
            group['info_score'] = (group['default_team_id'].notna().astype(int) * 2 + 
                                  group['rank'].notna().astype(int))
            group = group.sort_values('info_score', ascending=False)
            
            keep_id = int(group.iloc[0]['id'])
            remove_ids = group.iloc[1:]['id'].astype(int).tolist()
            print(f"  Merging Riot ID '{riot}': Keeping ID {keep_id} ({group.iloc[0]['name']}), removing {remove_ids}")
            for rid in remove_ids:
                conn.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (keep_id, rid))
                conn.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (keep_id, rid))
                conn.execute("DELETE FROM players WHERE id = ?", (rid,))
        conn.commit()
    else:
        print("No Riot ID duplicates found.")

    conn.close()
    print("\n--- Cleanup Complete ---")

if __name__ == "__main__":
    cleanup_duplicates()
