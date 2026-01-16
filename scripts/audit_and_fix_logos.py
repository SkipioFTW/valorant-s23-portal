
import sqlite3
import os
import shutil
import difflib

# Configuration
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, 'data', 'valorant_s23.db')
TEAMS_DIR = os.path.join(ROOT_DIR, 'assets', 'teams')
BACKUP_DIR = os.path.join(ROOT_DIR, 'assets', 'teams_backup')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def backup_images():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")
    
    # Copy all files from TEAMS_DIR to BACKUP_DIR
    for filename in os.listdir(TEAMS_DIR):
        src = os.path.join(TEAMS_DIR, filename)
        dst = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            # print(f"Backed up: {filename}")
    print(f"Backup complete. {len(os.listdir(BACKUP_DIR))} files in backup.")

def audit_and_fix():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all teams
    cursor.execute("SELECT id, name, logo_path FROM teams")
    teams = cursor.fetchall()
    
    # Get actual files
    files = [f for f in os.listdir(TEAMS_DIR) if os.path.isfile(os.path.join(TEAMS_DIR, f))]
    
    print(f"Checking {len(teams)} teams against {len(files)} files...")
    
    updates = []
    
    for team_id, name, logo_path in teams:
        status = "OK"
        new_path = None
        
        # Normalize path separators
        if logo_path:
            logo_path = logo_path.replace('\\', '/')
        
        full_path = os.path.join(ROOT_DIR, logo_path) if logo_path else None
        
        if not logo_path or not os.path.exists(full_path):
            status = "MISSING"
            
            # Try to find a match
            # 1. Exact match with .png
            candidates = [f for f in files if f.lower() == f"{name}.png".lower()]
            if not candidates:
                # 2. Match with underscore replacement
                name_snake = name.replace(" ", "_")
                candidates = [f for f in files if f.lower() == f"{name_snake}.png".lower()]
            
            if not candidates:
                # 3. Fuzzy match
                matches = difflib.get_close_matches(name, [f.replace('.png', '').replace('_', ' ') for f in files], n=1, cutoff=0.7)
                if matches:
                    # Find the original filename for this match
                    target_name = matches[0]
                    # This is reverse mapping, might be tricky if multiple files map to same name, but usually fine
                    for f in files:
                        if f.replace('.png', '').replace('_', ' ') == target_name:
                            candidates = [f]
                            break
            
            if candidates:
                found_file = candidates[0]
                new_path = f"assets/teams/{found_file}"
                print(f"[FIX] Team '{name}': '{logo_path}' -> '{new_path}'")
                updates.append((new_path, team_id))
            else:
                print(f"[FAIL] Team '{name}': No matching logo found. Current: '{logo_path}'")
        else:
            # Check if we should normalize the path in DB (e.g. backslashes)
            if '\\' in logo_path:
                 normalized = logo_path.replace('\\', '/')
                 updates.append((normalized, team_id))
                 print(f"[NORM] Team '{name}': path normalized to '{normalized}'")

    if updates:
        print(f"Applying {len(updates)} updates to database...")
        cursor.executemany("UPDATE teams SET logo_path=? WHERE id=?", updates)
        conn.commit()
    else:
        print("No database updates needed.")
        
    conn.close()

if __name__ == "__main__":
    backup_images()
    audit_and_fix()
