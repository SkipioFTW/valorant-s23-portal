# Match Prediction Model Report: Valorant S23 Portal

## 1. Overview
The match prediction system has been upgraded from a simple heuristic to a **Random Forest Machine Learning Model**. This model analyzes historical team performance, player impact, and recent form to predict the probability of a team winning their next matchup.

## 2. Mathematical Foundation & Features

The model uses a feature vector $X$ for each match, representing the difference between Team 1 and Team 2:

$$X = [ \Delta WR_{recent}, \Delta ACS_{avg}, \Delta H2H, Week ]$$

### Key Features:
1.  **Recent Form ($\Delta WR_{recent}$)**:
    - Calculates the Win Rate over the **last 3 matches**.
    - This captures "Momentum" and recent strategy shifts.
    - Weighting: $WR = \frac{\sum Wins_{last3}}{3}$

2.  **Player Impact ($\Delta ACS_{avg}$)**:
    - Aggregates the **Average Combat Score (ACS)** of all players in the team across all previous matches.
    - This measures the "firepower" or "peaking" status of the roster.

3.  **Head-to-Head History ($\Delta H2H$)**:
    - The historical win difference between the two specific teams.
    - $H2H = Wins_{T1 \text{ vs } T2} - Wins_{T2 \text{ vs } T1}$

4.  **Temporal Context (Week)**:
    - Includes the current week number to account for league progression and meta shifts over time.

## 3. Machine Learning Architecture

- **Algorithm**: Random Forest Classifier.
- **Why Random Forest?**:
    - Handles non-linear relationships between features (e.g., ACS might matter more in early weeks).
    - Robust against outliers and small datasets (crucial for a seasonal league).
    - Provides **Probability Estimates** (`predict_proba`) rather than just a binary "Win/Loss" result, allowing for the "Confidence Level" display.

## 4. Standings & Points System Update

The standings logic has been completely overhauled to match the new league requirements:

### Points Calculation:
- **Match Win**: 15 Points.
- **Round Win**: 1 Point per round won.
- **Overtime Rule**: 
    - If a match hits Overtime (Score $> 12$ and Diff $\ge 2$):
        - **Winner**: 15 Points.
        - **Loser**: 12 Points (automatic floor).

### Tie-Breaking (Points Against):
- **Every round lost** by a team is recorded as **"Points Against"**.
- In the event of a tie in total points, the team with the **Lower Points Against** receives the higher standing.

## 5. Integration
The model is hosted in `predictor_model.py` and is automatically called by the `visitor_dashboard.py`. If the model hasn't been trained yet (due to lack of data), the system gracefully falls back to the original heuristic to ensure the UI never breaks.
