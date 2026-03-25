import json
import os
import sys
import predict_season_winner as model

def load_calibration():
    path = os.path.join(os.getcwd(), "calibration.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def main():
    team_data_path = os.path.join(model.DATA_DIR, "FLV S22 Statistics - Team Data.csv")
    summaries = model.extract_team_summaries_from_team_data(team_data_path)
    if len(sys.argv) == 2 or (len(sys.argv) >= 3 and sys.argv[2].startswith("--")):
        t = model.resolve_team_name(sys.argv[1], summaries)
        model.print_team_breakdown(t, summaries)
        use_llm = any(a.lower().startswith("--llm") for a in sys.argv[1:])
        if use_llm:
            model_name = "llama3.1"
            for a in sys.argv[1:]:
                if a.lower().startswith("--llm-model="):
                    model_name = a.split("=", 1)[1]
            text = model.analyze_team_with_llm(t, summaries, model=model_name)
            if text:
                print("AI Analysis:")
                print(text)
            else:
                print("AI Analysis unavailable. Ensure a local Ollama server is running.")
        return
    if len(sys.argv) < 3:
        print("Usage: python predict_cli.py \"Team A\" \"Team B\" [bo1|bo3|bo5]\n       or: python predict_cli.py \"Team\" [--llm] [--llm-model=name] for team breakdown")
        return
    fmt = "bo3"
    if len(sys.argv) >= 4 and sys.argv[3].lower() in {"bo1", "bo3", "bo5"}:
        fmt = sys.argv[3].lower()
    t1 = model.resolve_team_name(sys.argv[1], summaries)
    t2 = model.resolve_team_name(sys.argv[2], summaries)
    if t1 not in summaries or t2 not in summaries:
        print("Unknown team name(s)")
        known = ", ".join(sorted(summaries.keys()))
        print(f"Known teams: {known}")
        return
    calibr = load_calibration()
    p = model.calibrated_match_prob(t1, t2, summaries, calibr)
    p_series = model.series_win_prob_single_game(p, fmt)
    print(f"Match win probability ({fmt}): {t1} vs {t2}")
    print(f"{t1}: {p_series*100:.2f}% | {t2}: {(1-p_series)*100:.2f}%")

if __name__ == "__main__":
    main()
