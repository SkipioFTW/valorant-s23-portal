import json
import os
from datetime import datetime
import predict_season_winner as model

def main():
    # Load summaries from CSVs (no longer from DB as per user request)
    summaries = model.extract_team_summaries_from_team_data(model.DATA_DIR)
    
    if not summaries:
        print("No team data found in CSVs.")
        return
        
    calibr = model.train_logistic_calibration(summaries)
    if calibr is None:
        print("No calibration data")
        return
        
    payload = {
        "alpha": calibr["alpha"],
        "std_x": calibr["std_x"],
        "ratings": calibr["ratings"],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    out_path = os.path.join(os.getcwd(), "calibration.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    print(f"Calibration saved to {out_path}")

if __name__ == "__main__":
    main()

