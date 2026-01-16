import sqlite3
import pandas as pd

conn = sqlite3.connect('valorant_s23.db')
print("Checking player matching...")
# Check some players from the test output
tracker_names = ['noobhumbler1995#sit', 'goopy#plrbn', 'ladybug#glhf']
for tn in tracker_names:
    res = pd.read_sql("SELECT name, riot_id FROM players WHERE LOWER(riot_id) = ?", conn, params=(tn,))
    if not res.empty:
        print(f"Found match for {tn}: {res.iloc[0]['name']}")
    else:
        # Try matching name part
        name_part = tn.split('#')[0]
        res_name = pd.read_sql("SELECT name, riot_id FROM players WHERE LOWER(name) = ? OR LOWER(name) = ?", conn, params=(tn, name_part))
        if not res_name.empty:
            print(f"Found name match for {tn}: {res_name.iloc[0]['name']} (Riot ID: {res_name.iloc[0]['riot_id']})")
        else:
            print(f"No match for {tn}")

conn.close()
