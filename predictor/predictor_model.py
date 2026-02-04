import sqlite3
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'match_predictor_model.pkl')

def get_db_connection():
    # Database is in ../data/ relative to this script
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(root_dir, 'data', 'valorant_s23.db')
    return sqlite3.connect(db_path)

def extract_features(t1_id, t2_id, current_week=None, overrides=None):
    """
    Extract features for prediction:
    1. Recent Form (last 3 matches)
    2. Head-to-Head
    3. Player Impact (Avg ACS)
    4. Map Performance (optional if map specified)
    """
    conn = get_db_connection()
    if current_week is None:
        # Get latest week from DB
        try:
            res = pd.read_sql_query("SELECT MAX(week) as w FROM matches", conn)
            current_week = int(res['w'].iloc[0] or 0) + 1
        except:
            current_week = 1

    overrides = overrides or {}

    def get_team_metrics(tid, team_key):
        # All matches for this team
        m = pd.read_sql_query(f"""
            SELECT id, winner_id, score_t1, score_t2, team1_id, team2_id, week 
            FROM matches 
            WHERE (team1_id={tid} OR team2_id={tid}) AND status='completed'
            ORDER BY week DESC
        """, conn)
        
        # 1. Recent Form (last 3)
        recent = m.head(3)
        wins = recent[recent['winner_id'] == tid].shape[0]
        recent_wr = wins / len(recent) if not recent.empty else 0.5
        
        # 2. Player Impact (Avg ACS)
        # Check overrides first
        if overrides.get(f'{team_key}_players'):
            # Calculate from specific players
            pids = ",".join(map(str, overrides[f'{team_key}_players']))
            if pids:
                acs_res = pd.read_sql_query(f"SELECT AVG(acs) as avg_acs FROM match_stats_map WHERE player_id IN ({pids})", conn)
                avg_acs = acs_res['avg_acs'].iloc[0]
                if avg_acs is None: avg_acs = 200.0
            else:
                avg_acs = 200.0
        else:
            acs_res = pd.read_sql_query(f"SELECT AVG(acs) as avg_acs FROM match_stats_map WHERE team_id={tid}", conn)
            avg_acs = acs_res['avg_acs'].iloc[0] or 200.0 # Baseline
        
        # 3. Strength of Schedule (Avg WR of opponents)
        # ... (keep existing simple placeholder or expand)
            
        return {
            'recent_wr': recent_wr,
            'avg_acs': avg_acs,
            'total_games': len(m)
        }

    # Head to Head
    h2h = pd.read_sql_query(f"""
        SELECT winner_id FROM matches 
        WHERE ((team1_id={t1_id} AND team2_id={t2_id}) OR (team1_id={t2_id} AND team2_id={t1_id}))
        AND status='completed'
    """, conn)
    h2h_t1 = h2h[h2h['winner_id'] == t1_id].shape[0]
    h2h_t2 = h2h[h2h['winner_id'] == t2_id].shape[0]
    h2h_diff = h2h_t1 - h2h_t2
    
    m1 = get_team_metrics(t1_id, 't1')
    m2 = get_team_metrics(t2_id, 't2')
    
    # 4. Map Performance
    map_diff = 0.0
    selected_maps = overrides.get('map')
    if selected_maps:
        if isinstance(selected_maps, str):
            selected_maps = [selected_maps]
            
        t1_map_wr_sum = 0
        t2_map_wr_sum = 0
        valid_maps = 0
        
        for mname in selected_maps:
            if mname == "Any": continue
            
            def get_map_stats(tid, mn):
                # Get wins and total played on this map
                q = f"""
                SELECT count(*) as total, sum(case when mm.winner_id={tid} then 1 else 0 end) as wins
                FROM match_maps mm
                JOIN matches m ON mm.match_id = m.id
                WHERE (m.team1_id={tid} OR m.team2_id={tid}) 
                AND mm.map_name='{mn}' AND m.status='completed'
                """
                res = pd.read_sql_query(q, conn).iloc[0]
                total = res['total']
                wins = res['wins']
                return (wins / total) if total > 0 else 0.5 # Default to 0.5 if no history
            
            t1_map_wr_sum += get_map_stats(t1_id, mname)
            t2_map_wr_sum += get_map_stats(t2_id, mname)
            valid_maps += 1
            
        if valid_maps > 0:
            map_diff = (t1_map_wr_sum - t2_map_wr_sum) / valid_maps

    conn.close()
    
    # Feature vector: [WR Diff, ACS Diff, H2H Diff, Week, Map Diff]
    features = [
        m1['recent_wr'] - m2['recent_wr'],
        m1['avg_acs'] - m2['avg_acs'],
        h2h_diff,
        current_week,
        map_diff
    ]
    return np.array(features).reshape(1, -1)

def predict_match(t1_id, t2_id, week=None, overrides=None):
    if not os.path.exists(MODEL_PATH):
        return None # Fallback to heuristic
    
    try:
        model = joblib.load(MODEL_PATH)
        X = extract_features(t1_id, t2_id, week, overrides)
        probs = model.predict_proba(X)[0] # [Prob_Loss, Prob_Win] for T1
        return probs[1] # Probability of T1 winning
    except Exception as e:
        print(f"Prediction error: {e}")
        return None

def train_model():
    """Retrain the model using all completed matches"""
    conn = get_db_connection()
    try:
        matches = pd.read_sql_query("""
            SELECT m.id, m.team1_id, m.team2_id, m.winner_id, m.week, mm.map_name 
            FROM matches m
            LEFT JOIN match_maps mm ON m.id = mm.match_id
            WHERE m.status='completed'
            GROUP BY m.id
        """, conn)
    finally:
        conn.close()
    
    if len(matches) < 3:
        print("Not enough data to train (need at least 3 completed matches).")
        return False
        
    X_train = []
    y_train = []
    
    for row in matches.itertuples():
        # For training, we should ideally only use data BEFORE this match
        # but for the first run, we'll use a simplified approach
        overrides = {}
        if row.map_name:
            overrides['map'] = row.map_name
            
        feat = extract_features(row.team1_id, row.team2_id, row.week, overrides=overrides)
        X_train.append(feat[0])
        y_train.append(1 if row.winner_id == row.team1_id else 0)
        
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, MODEL_PATH)
    print("Model retrained successfully.")
    return True

if __name__ == "__main__":
    train_model()
