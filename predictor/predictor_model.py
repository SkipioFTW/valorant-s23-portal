import sqlite3
import pandas as pd
import numpy as np
import os
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'match_predictor_model.pkl')

def get_db_connection():
    # Database is in ../data/ relative to this script
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(root_dir, 'data', 'valorant_s23.db')
    return sqlite3.connect(db_path)

def extract_features(t1_id, t2_id, current_week=None):
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

    def get_team_metrics(tid):
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
        acs_res = pd.read_sql_query(f"SELECT AVG(acs) as avg_acs FROM match_stats_map WHERE team_id={tid}", conn)
        avg_acs = acs_res['avg_acs'].iloc[0] or 200.0 # Baseline
        
        # 3. Strength of Schedule (Avg WR of opponents)
        if not m.empty:
            opponents = np.where(m['team1_id'] == tid, m['team2_id'], m['team1_id'])
        else:
            opponents = []
        
        opp_wr = 0.5
        if opponents:
            opp_ids = ",".join(map(str, opponents))
            opp_m = pd.read_sql_query(f"SELECT id, winner_id FROM matches WHERE (team1_id IN ({opp_ids}) OR team2_id IN ({opp_ids})) AND status='completed'", conn)
            # This is a bit complex for a quick script, but let's simplify to just 0.5 for now or actual WR
            opp_wr = 0.5 # Placeholder for SOS
            
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
    
    m1 = get_team_metrics(t1_id)
    m2 = get_team_metrics(t2_id)
    conn.close()
    
    # Feature vector: [WR Diff, ACS Diff, H2H Diff, Week]
    features = [
        m1['recent_wr'] - m2['recent_wr'],
        m1['avg_acs'] - m2['avg_acs'],
        h2h_diff,
        current_week
    ]
    return np.array(features).reshape(1, -1)

def predict_match(t1_id, t2_id, week=None):
    if not os.path.exists(MODEL_PATH):
        return None # Fallback to heuristic
    
    try:
        model = joblib.load(MODEL_PATH)
        X = extract_features(t1_id, t2_id, week)
        probs = model.predict_proba(X)[0] # [Prob_Loss, Prob_Win] for T1
        return probs[1] # Probability of T1 winning
    except Exception as e:
        print(f"Prediction error: {e}")
        return None

def train_initial_model():
    """Run this to create the first model if matches exist"""
    conn = get_db_connection()
    matches = pd.read_sql_query("SELECT id, team1_id, team2_id, winner_id, week FROM matches WHERE status='completed'", conn)
    conn.close()
    
    if len(matches) < 3:
        print("Not enough data to train.")
        return
        
    X_train = []
    y_train = []
    
    for row in matches.itertuples():
        # For training, we should ideally only use data BEFORE this match
        # but for the first run, we'll use a simplified approach
        feat = extract_features(row.team1_id, row.team2_id, row.week)
        X_train.append(feat[0])
        y_train.append(1 if row.winner_id == row.team1_id else 0)
        
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, MODEL_PATH)
    print("Initial model trained successfully.")

if __name__ == "__main__":
    train_initial_model()
