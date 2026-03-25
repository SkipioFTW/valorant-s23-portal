import csv
import os
import math
import numpy as np
import pandas as pd
from collections import defaultdict

# Constants
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
#DB_PATH = "valorant_s22.db" # Though user wants CSV only, we keep this for compatibility with existing scripts

def resolve_team_name(name, summaries):
    """Fuzzy match team name to existing summaries."""
    name_low = name.lower().strip()
    if name_low in summaries:
        return name
    for k in summaries.keys():
        if name_low in k.lower():
            return k
    return name

def extract_team_summaries_from_team_data(path):
    """
    Parses Team Data.csv and Group Standings to get Points and +/-.
    R = points + 0.5 * (+/-)
    """
    summaries = {}
    
    # 1. Load Points from Standings Files
    standing_files = [
        "FLV S22 Statistics - Clubs Standings.csv",
        "FLV S22 Statistics - Diamonds Standings.csv",
        "FLV S22 Statistics - Hearts Standings.csv",
        "FLV S22 Statistics - Spades Standings.csv"
    ]
    
    for f_name in standing_files:
        f_path = os.path.join(DATA_DIR, f_name)
        if not os.path.exists(f_path):
            continue
        try:
            # Standings usually have empty first col, then Standings, Team, Points, Points Against, +/-, Wins, Games
            df = pd.read_csv(f_path, skiprows=1)
            # Find the actual columns
            # The structure from view_file: ,Standings,Team,Points,Points Against,+/-,Wins,Games,,,
            # Pandas might name them Unnamed: 0, Standings, Team, Points, etc.
            team_col = 'Team'
            pts_col = 'Points'
            diff_col = '+/-'
            
            for _, row in df.iterrows():
                t_name = str(row[team_col]).strip() if team_col in row else None
                if not t_name or t_name == 'nan' or t_name == '':
                    continue
                
                pts = float(row[pts_col]) if pts_col in row and not pd.isna(row[pts_col]) else 0.0
                diff = float(row[diff_col]) if diff_col in row and not pd.isna(row[diff_col]) else 0.0
                
                # Formula: R = points + 0.5 * (+/-)
                rating_r = pts + 0.5 * diff
                
                summaries[t_name] = {
                    "points": pts,
                    "diff": diff,
                    "rating_r": rating_r,
                    "name": t_name
                }
        except Exception as e:
            print(f"Error parsing {f_name}: {e}")

    # 2. Augment with Player Data for Lineup Strength (S)
    for team_name in list(summaries.keys()):
        # Try to find team CSV
        team_csv = f"FLV S22 Statistics - {team_name}.csv"
        # Handle cases where team name might have slight mismatch with filename (e.g. Baguette 5 vs The Baguette 5)
        potential_path = os.path.join(DATA_DIR, team_csv)
        if not os.path.exists(potential_path):
            # Try searching
            found = False
            for f in os.listdir(DATA_DIR):
                if team_name.lower() in f.lower() and f.endswith(".csv") and "Standings" not in f and "Team Data" not in f:
                    potential_path = os.path.join(DATA_DIR, f)
                    found = True
                    break
            if not found:
                summaries[team_name]["strength_s"] = 0
                continue
        
        try:
            # Parse Averages row
            with open(potential_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            avg_row = None
            for row in rows:
                if row and row[0].strip().lower() == "averages":
                    avg_row = row
                    break
            
            if avg_row:
                # Based on Baguette 5 CSV structure:
                # Averages, Yoru, 306, 22.4, 15.5, 1.62, 200.2, 69, 7.52, 12, , Clove, 305 ...
                # We need to average these across the players in the row
                acs_list = []
                kd_list = []
                adr_list = []
                kast_list = []
                
                # Each player block is exactly 10 columns (Krast, Agent, ACS, Kills, Deaths, K/D, ADR, DDΔ, KAST%, Score)
                # But in the CSV it starts at index 2 (ACS) for the first player.
                i = 2
                while i < len(avg_row):
                    try:
                        if avg_row[i]: acs_list.append(float(avg_row[i]))
                        if i+3 < len(avg_row) and avg_row[i+3]: kd_list.append(float(avg_row[i+3]))
                        if i+4 < len(avg_row) and avg_row[i+4]: adr_list.append(float(avg_row[i+4]))
                        if i+6 < len(avg_row) and avg_row[i+6]: 
                            kast_val = float(str(avg_row[i+6]).replace('%', ''))
                            # If KAST is provided as a fraction (e.g. 0.75), convert to % (75)
                            if kast_val <= 1.0:
                                kast_val *= 100
                            kast_list.append(kast_val)
                    except:
                        pass
                    i += 10 # Jump to next player start
                
                if acs_list:
                    avg_acs = sum(acs_list) / len(acs_list)
                    avg_kd = sum(kd_list) / len(kd_list) if kd_list else 1.0
                    avg_adr = sum(adr_list) / len(adr_list) if adr_list else 130.0
                    avg_kast = sum(kast_list) / len(kast_list) if kast_list else 70.0
                    
                    # Formula: S = (ACS - 200) + 100(K/D - 1) + 0.5(ADR - 130) + 0.2(KAST - 70)
                    s = (avg_acs - 200) + 100*(avg_kd - 1) + 0.5*(avg_adr - 130) + 0.2*(avg_kast - 70)
                    summaries[team_name]["strength_s"] = s
                else:
                    summaries[team_name]["strength_s"] = 0
            else:
                summaries[team_name]["strength_s"] = 0
        except Exception as e:
            print(f"Error parsing player data for {team_name}: {e}")
            summaries[team_name]["strength_s"] = 0

    # 3. Blended Rating (B)
    # Z-score normalization for S
    s_values = [v["strength_s"] for v in summaries.values()]
    if len(s_values) > 1:
        s_mean = sum(s_values) / len(s_values)
        s_std = math.sqrt(sum((x - s_mean)**2 for x in s_values) / len(s_values))
        if s_std == 0: s_std = 1
        
        for t in summaries:
            z = (summaries[t]["strength_s"] - s_mean) / s_std
            # B = R + 10 * Z
            summaries[t]["rating_b"] = summaries[t]["rating_r"] + 10 * z
    else:
        for t in summaries:
            summaries[t]["rating_b"] = summaries[t]["rating_r"]

    return summaries

def calibrated_match_prob(t1, t2, summaries, calibration=None):
    """Calculates win probability for t1 against t2."""
    if t1 not in summaries or t2 not in summaries:
        return 0.5
    
    b1 = summaries[t1]["rating_b"]
    b2 = summaries[t2]["rating_b"]
    delta = b1 - b2
    
    alpha = 1.0
    std_x = 1.0
    if calibration:
        alpha = calibration.get("alpha", 1.0)
        std_x = calibration.get("std_x", 1.0)
    
    x_prime = delta / std_x
    prob = 1 / (1 + math.exp(-alpha * x_prime))
    return prob

def series_win_prob_single_game(p, fmt):
    """Calculates series win probability from single game p."""
    if fmt == "bo1":
        return p
    elif fmt == "bo3":
        # Winner needs 2 games. Prob = p*p (2-0) + 2 * p*p*(1-p) (2-1)
        # Simplified: p^2 * (3 - 2p)
        return p**2 * (3 - 2*p)
    elif fmt == "bo5":
        # Winner needs 3 games.
        # k=3: p^3 * (1-p)^0 * C(3-1, 3-1) = p^3
        # k=4: p^3 * (1-p)^1 * C(4-1, 3-1) = 3 * p^3 * (1-p)
        # k=5: p^3 * (1-p)^2 * C(5-1, 3-1) = 6 * p^3 * (1-p)^2
        return p**3 * (1 + 3*(1-p) + 6*(1-p)**2)
    return p

def train_logistic_calibration(summaries):
    """Placeholder for training - in this standalone version we can use defaults or simple logic."""
    # Since we don't have historical match results CSV easily parsable in one go here,
    # we'll return default calibration values that usually work for this scale.
    # In a real scenario, this would parse match_reports_clean.csv.
    return {
        "alpha": 1.5, # Empirically selected
        "std_x": 10.0, # Approximate std of rating differences
        "ratings": {t: v["rating_b"] for t, v in summaries.items()}
    }

def print_team_breakdown(team, summaries):
    if team not in summaries:
        print(f"Team {team} not found.")
        return
    s = summaries[team]
    print(f"Breakdown for {team}:")
    print(f"  Points: {s['points']}")
    print(f"  +/-: {s['diff']}")
    print(f"  Base Rating (R): {s['rating_r']:.2f}")
    if 'strength_s' in s:
        print(f"  Player Strength (S): {s['strength_s']:.2f}")
    print(f"  Blended Rating (B): {s['rating_b']:.2f}")

def analyze_team_with_llm(team, summaries, model="llama3.1"):
    # This feature requires a local LLM or API, which might not be present.
    return None

def main():
    # Example usage if run directly
    summaries = extract_team_summaries_from_team_data(DATA_DIR)
    for team in summaries:
        print_team_breakdown(team, summaries)

if __name__ == "__main__":
    main()
