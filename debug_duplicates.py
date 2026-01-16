import sqlite3
import pandas as pd

DB_PATH = "valorant_s23.db"

def check_duplicates():
    conn = sqlite3.connect(DB_PATH)
    
    print("Checking for duplicate players by name (case-insensitive)...")
    players_df = pd.read_sql("SELECT id, name, riot_id, default_team_id FROM players", conn)
    players_df['name_lower'] = players_df['name'].str.lower()
    duplicates_name = players_df[players_df.duplicated('name_lower', keep=False)].sort_values('name_lower')
    if not duplicates_name.empty:
        print(f"Found {len(duplicates_name)} case-insensitive duplicate entries for {duplicates_name['name_lower'].nunique()} unique names.")
        print(duplicates_name[['id', 'name', 'riot_id', 'default_team_id']])
    else:
        print("No case-insensitive duplicates found by name.")

    print("\nChecking for duplicate players by Riot ID...")
    # Drop rows with null Riot ID for this check
    riot_ids = players_df[players_df['riot_id'].notna() & (players_df['riot_id'] != "")]
    duplicates_riot = riot_ids[riot_ids.duplicated('riot_id', keep=False)].sort_values('riot_id')
    if not duplicates_riot.empty:
        print(f"Found {len(duplicates_riot)} duplicate entries for {duplicates_riot['riot_id'].nunique()} unique Riot IDs.")
        print(duplicates_riot[['id', 'name', 'riot_id', 'default_team_id']])
    else:
        print("No duplicates found by Riot ID.")

    print("\nChecking for players with same name after trimming spaces...")
    players_df['name_trimmed'] = players_df['name'].str.strip()
    dup_trimmed = players_df[players_df.duplicated('name_trimmed', keep=False)].sort_values('name_trimmed')
    if not dup_trimmed.empty:
        print(f"Found {len(dup_trimmed)} players with same name after trimming.")
        print(dup_trimmed[['id', 'name', 'riot_id', 'default_team_id']])
    else:
        print("No players found with same name after trimming.")

    conn.close()

if __name__ == "__main__":
    check_duplicates()
