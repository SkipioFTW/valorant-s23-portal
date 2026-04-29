import os
import psycopg2
from dotenv import load_dotenv

# Load credentials from new_app_repo/Skipio-bot/.env
load_dotenv("new_app_repo/Skipio-bot/.env")

DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DB_CONNECTION_STRING")

if not DB_URL:
    print("Error: Database connection string not found.")
    exit(1)

try:
    conn = psycopg2.connect(DB_URL, sslmode='require')
    cur = conn.cursor()
    
    tables = ['matches', 'player_team_history']
    
    query = """
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name IN %s 
    ORDER BY table_name, ordinal_position
    """
    
    cur.execute(query, (tuple(tables),))
    rows = cur.fetchall()
    
    current_table = ""
    for table, col, dtype in rows:
        if table != current_table:
            print(f"\n[{table}]")
            current_table = table
        print(f"  {col}: {dtype}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
