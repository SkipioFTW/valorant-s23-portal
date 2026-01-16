import sqlite3
import pandas as pd

DB_PATH = "valorant_s23.db"

def find_substring_duplicates():
    conn = sqlite3.connect(DB_PATH)
    players = pd.read_sql("SELECT id, name, riot_id FROM players", conn)
    players['name_clean'] = players['name'].str.lower().str.strip().str.replace('@', '')
    
    found = []
    sorted_players = players.sort_values('name_clean')
    
    p_list = list(sorted_players.itertuples())
    for i, p1 in enumerate(p_list):
        for j, p2 in enumerate(p_list):
            if p1.id == p2.id: continue
            if p1.name_clean in p2.name_clean and len(p1.name_clean) > 2:
                # Check if they have the same Riot ID or one is missing
                r1 = str(p1.riot_id).lower() if p1.riot_id else ""
                r2 = str(p2.riot_id).lower() if p2.riot_id else ""
                
                if r1 == r2 or r1 == "" or r2 == "":
                    found.append((p1.id, p1.name, p2.id, p2.name))
    
    if found:
        print(f"Found {len(found)} potential substring duplicates:")
        for id1, n1, id2, n2 in found:
            print(f"  '{n1}' (ID {id1}) and '{n2}' (ID {id2})")
    else:
        print("No substring duplicates found.")
    conn.close()

if __name__ == "__main__":
    find_substring_duplicates()
