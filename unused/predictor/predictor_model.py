import os
import math
import joblib
from functools import lru_cache
from supabase import create_client, Client

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'match_predictor_model.pkl')

@lru_cache(maxsize=1)
def get_supabase_client():
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not url or not key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "new_app_repo", ".env.local")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if k == "NEXT_PUBLIC_SUPABASE_URL": url = v.strip("'\" ")
                        if k == "SUPABASE_SERVICE_ROLE_KEY" or k == "NEXT_PUBLIC_SUPABASE_ANON_KEY": key = v.strip("'\" ")

    return create_client(url, key)

# ==============================================================================
# OLD PREDICTION MODEL LOGIC (Adapted for live Supabase Data + Deep Stats)
# ==============================================================================

def extract_team_summaries_from_supabase():
    """
    Parses Live Supabase Data to get Points and +/-.
    R = points + 0.5 * (+/-)
    S = Player Strength (ACS, KD, ADR, KAST + NEW Deep Stats [Plants, Defuses, Clutches])
    B = R + 10 * Z(S)
    """
    summaries = {}
    supabase = get_supabase_client()
    
    # 1. Load Points from Standings
    # In live DB, we calculate from matches
    res_m = supabase.table("matches").select("team1_id, team2_id, winner_id, score_t1, score_t2").eq("status", "completed").execute()
    
    # Initialize all teams
    res_t = supabase.table("teams").select("id, name").execute()
    for team in res_t.data:
        summaries[team['id']] = {
            "name": team['name'],
            "points": 0,
            "diff": 0,
            "rating_r": 0,
            "strength_s": 0,
            "rating_b": 0,
            "match_count": 0
        }

    for m in res_m.data:
        t1, t2 = m['team1_id'], m['team2_id']
        s1, s2 = m['score_t1'] or 0, m['score_t2'] or 0
        winner = m['winner_id']
        
        if t1 not in summaries or t2 not in summaries: continue

        diff1 = s1 - s2
        diff2 = s2 - s1
        summaries[t1]['diff'] += diff1
        summaries[t2]['diff'] += diff2
        summaries[t1]['match_count'] += 1
        summaries[t2]['match_count'] += 1
        
        if winner == t1:
            summaries[t1]['points'] += 15
            summaries[t2]['points'] += min(s2, 12)
        elif winner == t2:
            summaries[t2]['points'] += 15
            summaries[t1]['points'] += min(s1, 12)

    for sid, sdata in summaries.items():
        # Formula: R = points + 0.5 * (+/-)
        sdata['rating_r'] = sdata['points'] + 0.5 * sdata['diff']

    # 2. Augment with Player Data for Lineup Strength (S) including DEEP STATS
    res_p = supabase.table('players').select('id, default_team_id').not_.is_('default_team_id', 'null').execute()
    player_to_team = {p['id']: p['default_team_id'] for p in res_p.data}
    
    res_s = supabase.table('match_stats_map').select('player_id, kills, deaths, acs, adr, kast, plants, defuses, clutches, survived').execute()
    
    team_pstats = {}
    for row in res_s.data:
        pid = row['player_id']
        if pid not in player_to_team: continue
        tid = player_to_team[pid]
        
        if tid not in team_pstats:
            team_pstats[tid] = {'k':0, 'd':0, 'acs':0, 'adr':0, 'kast':0, 'plants':0, 'defuses':0, 'clutches':0, 'survived':0, 'rounds':0}
            
        ts = team_pstats[tid]
        ts['k'] += row['kills'] or 0
        ts['d'] += row['deaths'] or 0
        ts['acs'] += row['acs'] or 0
        ts['adr'] += row['adr'] or 0
        ts['kast'] += row['kast'] or 0
        ts['plants'] += row['plants'] or 0
        ts['defuses'] += row['defuses'] or 0
        ts['clutches'] += row['clutches'] or 0
        ts['survived'] += row['survived'] or 0
        ts['rounds'] += 1

    s_values = []
    for tid, ts in team_pstats.items():
        if ts['rounds'] == 0:
            summaries[tid]["strength_s"] = 0
            continue
        
        avg_acs = ts['acs'] / ts['rounds']
        avg_adr = ts['adr'] / ts['rounds']
        avg_kast = ts['kast'] / ts['rounds']
        avg_kd = ts['k'] / max(1, ts['d'])
        
        # Deep stats / round
        avg_plants = ts['plants'] / ts['rounds']
        avg_defuses = ts['defuses'] / ts['rounds']
        avg_clutch = ts['clutches'] / ts['rounds']
        avg_surv = ts['survived'] / ts['rounds']
        
        # Original Formula: S = (ACS - 200) + 100(K/D - 1) + 0.5(ADR - 130) + 0.2(KAST - 70)
        base_s = (avg_acs - 200) + 100*(avg_kd - 1) + 0.5*(avg_adr - 130) + 0.2*(avg_kast - 70) 
        
        # Deep Data Addition Formula
        deep_s = (avg_plants * 2.0) + (avg_defuses * 2.0) + (avg_clutch * 10.0) + (avg_surv * 1.5)
        
        s_val = base_s + deep_s
        if tid in summaries:
            summaries[tid]["strength_s"] = s_val
            s_values.append(s_val)

    # 3. Blended Rating (B)
    # Z-score normalization for S
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
        return p**2 * (3 - 2*p)
    elif fmt == "bo5":
        return p**3 * (1 + 3*(1-p) + 6*(1-p)**2)
    return p

def train_logistic_calibration(summaries):
    return {
        "alpha": 1.5,
        "std_x": 10.0,
        "ratings": {t: v["rating_b"] for t, v in summaries.items()}
    }

def print_team_breakdown(team, summaries):
    if team not in summaries:
        print(f"Team {team} not found.")
        return
    s = summaries[team]
    print(f"Breakdown for {s['name']}:")
    print(f"  Points: {s['points']}")
    print(f"  +/-: {s['diff']}")
    print(f"  Base Rating (R): {s['rating_r']:.2f}")
    if 'strength_s' in s:
        print(f"  Player Strength (S): {s['strength_s']:.2f}")
    print(f"  Blended Rating (B): {s['rating_b']:.2f}")

# ==============================================================================
# APP FACING INTEGRATION
# ==============================================================================

def predict_match(t1_id, t2_id, week=None, overrides=None):
    """
    Adapter for the current app's prediction format.
    """
    try:
        summaries = extract_team_summaries_from_supabase()
        calibration = train_logistic_calibration(summaries)
        
        prob = calibrated_match_prob(t1_id, t2_id, summaries, calibration)
        return prob
    except Exception as e:
        print(f"Prediction error: {e}")
        return 0.50

def train_model():
    """Retrain the model - no longer required for ML, but implemented for compatibility"""
    print("Model effectively trained instantly via logic constraints (R, S, B formula + Deep Stats).")
    return True

if __name__ == "__main__":
    train_model()
