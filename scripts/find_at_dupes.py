import sqlite3
import pandas as pd

import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "valorant_s23.db")

def find_at_duplicates():
    conn = sqlite3.connect(DB_PATH)
    players = pd.read_sql("SELECT id, name, riot_id, default_team_id FROM players", conn)
    names = set(players['name'])
    
    found = False
    for n in names:
        if n.startswith('@'):
            clean_name = n[1:]
            if clean_name in names:
                print(f"Potential duplicate: '{n}' and '{clean_name}'")
                p1 = players[players['name'] == n].iloc[0]
                p2 = players[players['name'] == clean_name].iloc[0]
                print(f"  ID {p1['id']}: Riot ID {p1['riot_id']}, Team {p1['default_team_id']}")
                print(f"  ID {p2['id']}: Riot ID {p2['riot_id']}, Team {p2['default_team_id']}")
                found = True
    
    if not found:
        print("No '@' duplicates found.")
    conn.close()

if __name__ == "__main__":
    find_at_duplicates()
