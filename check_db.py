import sqlite3
import pandas as pd

DB_PATH = "valorant_s23.db"

def check_db():
    conn = sqlite3.connect(DB_PATH)
    print("Tables:")
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    print(tables)
    
    print("\nMatches count:")
    matches = pd.read_sql("SELECT count(*) FROM matches", conn)
    print(matches)
    
    if not matches.empty and matches.iloc[0,0] > 0:
        print("\nSample matches:")
        sample = pd.read_sql("SELECT id, team1_id, team2_id, status FROM matches LIMIT 5", conn)
        print(sample)
    
    conn.close()

if __name__ == "__main__":
    check_db()
