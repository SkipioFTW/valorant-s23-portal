import sqlite3
import json

def inspect_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tables in {db_path}: {tables}")
    
    schema = {}
    for table in tables:
        cur.execute(f"PRAGMA table_info('{table}')")
        schema[table] = cur.fetchall()
        
    print("\n--- SCHEMAS ---")
    for table, info in schema.items():
        print(f"\n[{table}]")
        for col in info:
            print(f"  {col[1]} ({col[2]})")
            
    # Sample some data from likely tables
    for table in ['teams', 'players']:
        if table in tables:
            print(f"\n--- SAMPLE DATA FROM {table} ---")
            cur.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = cur.fetchall()
            for row in rows:
                print(row)
                
    conn.close()

if __name__ == "__main__":
    inspect_db("flv s24.db")
