import json

with open("match_cf0262d5.json", "r", encoding="utf-8") as f:
    match_json = json.load(f)

players = []

for seg in match_json["data"]["segments"]:
    if seg["type"] != "player":
        continue

    players.append({
        "riot_id": seg["attributes"]["platformUserIdentifier"],
        "team": seg["attributes"]["team"],
        "agent": seg["attributes"]["agent"],
        "kills": seg["stats"]["kills"]["value"],
        "deaths": seg["stats"]["deaths"]["value"],
        "assists": seg["stats"]["assists"]["value"],
        "acs": seg["stats"]["scorePerRound"]["value"],
    })

print(players)
