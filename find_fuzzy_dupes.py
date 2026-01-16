import sqlite3
import pandas as pd
from difflib import SequenceMatcher

DB_PATH = "valorant_s23.db"

def fuzzy_match(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_fuzzy_duplicates():
    conn = sqlite3.connect(DB_PATH)
    players = pd.read_sql("SELECT id, name, riot_id FROM players", conn)
    players['name_clean'] = players['name'].str.lower().str.strip().str.replace('@', '')
    
    found = []
    names = players['name_clean'].tolist()
    ids = players['id'].tolist()
    
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ratio = fuzzy_match(names[i], names[j])
            if ratio > 0.9 and names[i] != names[j]:
                found.append((ids[i], names[i], ids[j], names[j], ratio))
    
    if found:
        print(f"Found {len(found)} potential fuzzy duplicates:")
        for id1, n1, id2, n2, r in found:
            print(f"  {n1} (ID {id1}) vs {n2} (ID {id2}) - Ratio: {r:.2f}")
    else:
        print("No fuzzy duplicates found.")
    conn.close()

if __name__ == "__main__":
    find_fuzzy_duplicates()
