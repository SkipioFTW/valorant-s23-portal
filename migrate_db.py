
import os
import psycopg2
import sys

# Hardcoded from bots/discord_bot/.env
DB_URL = "postgresql://postgres.tekwoxehaktajyizaacj:rbb6a6RxkVBruepZ@aws-1-eu-north-1.pooler.supabase.com:6543/postgres"

def migrate():
    try:
        print(f"Connecting to {DB_URL.split('@')[1]}...")
        conn = psycopg2.connect(DB_URL, sslmode='require')
        cur = conn.cursor()
        
        # 1. Rename discord_handle -> tracker_link in players
        try:
            print("Checking for discord_handle column...")
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='players' AND column_name='discord_handle'")
            if cur.fetchone():
                print("Renaming discord_handle to tracker_link...")
                cur.execute("ALTER TABLE players RENAME COLUMN discord_handle TO tracker_link")
            else:
                print("Column discord_handle not found (already renamed?). checking tracker_link...")
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='players' AND column_name='tracker_link'")
                if cur.fetchone():
                    print("tracker_link exists.")
                else:
                    print("Warning: Neither discord_handle nor tracker_link columns found!")
        except Exception as e:
            print(f"Error checking/renaming player column: {e}")
            conn.rollback()

        # 2. Add tracker_link to pending_players
        try:
            print("Checking pending_players schema...")
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pending_players' AND column_name='tracker_link'")
            if not cur.fetchone():
                print("Adding tracker_link to pending_players...")
                cur.execute("ALTER TABLE pending_players ADD COLUMN tracker_link TEXT")
            else:
                print("tracker_link already in pending_players.")
        except Exception as e:
            print(f"Error altering pending_players: {e}")
            conn.rollback()

        # 3. Add discord_handle to pending_players (for submitter name)
        try:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pending_players' AND column_name='discord_handle'")
            if not cur.fetchone():
               print("Adding discord_handle to pending_players...")
               cur.execute("ALTER TABLE pending_players ADD COLUMN discord_handle TEXT")
            else:
               print("discord_handle already in pending_players.")
        except Exception as e:
            print(f"Error adding discord_handle to pending_players: {e}")
            conn.rollback()

        conn.commit()
        print("Migration successful.")
        conn.close()
    except Exception as e:
        print(f"Migration failed completely: {e}")

if __name__ == "__main__":
    migrate()
