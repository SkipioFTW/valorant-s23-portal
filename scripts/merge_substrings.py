import sqlite3
import pandas as pd

import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "valorant_s23.db")

def merge_players(keep_id, remove_id, conn):
    print(f"  Merging ID {remove_id} into {keep_id}...")
    # Update references
    conn.execute("UPDATE match_stats_map SET player_id = ? WHERE player_id = ?", (keep_id, remove_id))
    conn.execute("UPDATE match_stats_map SET subbed_for_id = ? WHERE subbed_for_id = ?", (keep_id, remove_id))
    # Delete duplicate
    conn.execute("DELETE FROM players WHERE id = ?", (remove_id,))

def cleanup_substring_duplicates():
    conn = sqlite3.connect(DB_PATH)
    
    # List of known pairs to merge based on the substring analysis
    # (remove_id, keep_id)
    # We'll try to keep the one that looks more 'official' or has a team
    to_merge = [
        (572, 7),   # cyteri -> @ARX Cyteri
        (170, 47),  # Hiru/The mango? -> @Chief Q (Hiru/The mango?)
        (25, 237),  # @Kai. -> kai.5784
        (46, 166),  # @Kazumai -> kitsunekazumai
        (68, 519),  # @Limit -> limit7078
        (76, 208),  # @milan -> milan1738
        (520, 195), # nickjunyor -> El Psy Kongroo(nickjunyor)
        (153, 2),   # Pengu -> @10T | Penguin_0z
        (169, 69),  # Solace -> @bransxn(solace)
        (115, 513), # Vessellll -> vessel (vessel has ID 513, let's check which is better)
        (574, 107), # zdyzze -> Infinite ZDYZZE
        (509, 15),  # zyroni -> @CM | Zyroni
        (3, 546)    # @CLAWS -> clawsator
    ]
    
    print("--- Merging Substring Duplicates ---")
    for remove_id, keep_id in to_merge:
        try:
            # Verify both exist
            p_remove = conn.execute("SELECT name FROM players WHERE id=?", (remove_id,)).fetchone()
            p_keep = conn.execute("SELECT name FROM players WHERE id=?", (keep_id,)).fetchone()
            
            if p_remove and p_keep:
                print(f"Merging '{p_remove[0]}' (ID {remove_id}) into '{p_keep[0]}' (ID {keep_id})")
                merge_players(keep_id, remove_id, conn)
            else:
                if not p_remove: print(f"Skipping: ID {remove_id} not found.")
                if not p_keep: print(f"Skipping: ID {keep_id} not found.")
        except Exception as e:
            print(f"Error merging {remove_id} and {keep_id}: {e}")
            
    conn.commit()
    conn.close()
    print("--- Cleanup Complete ---")

if __name__ == "__main__":
    cleanup_substring_duplicates()
