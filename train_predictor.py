import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import jobpy
import os

def get_db_connection():
    return sqlite3.connect('valorant_s23.db')

def prepare_training_data():
    conn = get_db_connection()
    
    # 1. Get all completed matches
    matches = pd.read_sql_query("""
        SELECT id, team1_id, team2_id, score_t1, score_t2, winner_id, week, format
        FROM matches WHERE status='completed'
    """, conn)
    
    # 2. Get map stats
    map_stats = pd.read_sql_query("SELECT match_id, map_name, team1_rounds, team2_rounds, winner_id FROM match_maps", conn)
    
    # 3. Get player stats
    player_stats = pd.read_sql_query("SELECT match_id, team_id, acs, kills, deaths, assists FROM match_stats_map", conn)
    
    features = []
    targets = []
    
    for _, match in matches.iterrows():
        m_id = match['id']
        t1_id = match['team1_id']
        t2_id = match['team2_id']
        
        # We only want to train on matches where we have historical data BEFORE this match
        # For simplicity in this script, we'll calculate stats based on ALL matches except this one
        # but in a real production environment, you'd only use data prior to match['week']
        
        def get_team_features(tid, current_match_id, current_week):
            # Recent Form (last 3 matches)
            past_matches = matches[(matches['id'] != current_match_id) & 
                                   (matches['week'] < current_week) & 
                                   ((matches['team1_id'] == tid) | (matches['team2_id'] == tid))].sort_values('week', ascending=False).head(3)
            
            win_rate = 0
            if not past_matches.empty:
                wins = past_matches[past_matches['winner_id'] == tid].shape[0]
                win_rate = wins / len(past_matches)
            
            # Avg ACS (Player Impact)
            team_player_stats = player_stats[(player_stats['match_id'] != current_match_id) & (player_stats['team_id'] == tid)]
            avg_acs = team_player_stats['acs'].mean() if not team_player_stats.empty else 0
            
            return {
                'win_rate': win_rate,
                'avg_acs': avg_acs
            }
            
        f1 = get_team_features(t1_id, m_id, match['week'])
        f2 = get_team_features(t2_id, m_id, match['week'])
        
        # Difference features
        features.append([
            f1['win_rate'] - f2['win_rate'],
            f1['avg_acs'] - f2['avg_acs'],
            match['week']
        ])
        
        targets.append(1 if match['winner_id'] == t1_id else 0)
    
    return np.array(features), np.array(targets)

def train_model():
    X, y = prepare_training_data()
    if len(X) < 5:
        print("Not enough data to train ML model. Need at least 5 matches.")
        return None
        
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Save model
    import joblib
    joblib.dump(model, 'match_predictor_model.pkl')
    print("Model trained and saved as match_predictor_model.pkl")
    return model

if __name__ == "__main__":
    train_model()
