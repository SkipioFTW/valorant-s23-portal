import os
from dotenv import load_dotenv
from supabase import create_client

def check():
    load_dotenv("new_app_repo/.env.local")
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    print("--- TEAMS CONSTRAINTS ---")
    res = supabase.rpc('exec_sql', {
        'query_text': "SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'teams'"
    }).execute()
    print(res.data)

    print("\n--- PLAYERS CONSTRAINTS ---")
    res = supabase.rpc('exec_sql', {
        'query_text': "SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'players'"
    }).execute()
    print(res.data)

if __name__ == "__main__":
    check()
