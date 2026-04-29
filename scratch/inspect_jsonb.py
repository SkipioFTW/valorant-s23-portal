import os
import psycopg2
import json
from dotenv import load_dotenv

# Load credentials from new_app_repo/Skipio-bot/.env
load_dotenv("new_app_repo/Skipio-bot/.env")

DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DB_CONNECTION_STRING")

try:
    conn = psycopg2.connect(DB_URL, sslmode='require')
    cur = conn.cursor()
    
    # Get a sample of JSONB columns
    cur.execute("SELECT clutches_details, ability_casts FROM match_stats_map WHERE clutches_details IS NOT NULL LIMIT 1")
    row = cur.fetchone()
    
    if row:
        print("--- clutches_details ---")
        print(json.dumps(row[0], indent=2))
        print("\n--- ability_casts ---")
        print(json.dumps(row[1], indent=2))
    else:
        print("No rows found with clutches_details.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
