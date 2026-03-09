const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'assets', 'matches', 'match_01be3cb9-87eb-47be-8ed3-e728c69916d2.json');
const rawData = fs.readFileSync(filePath, 'utf8');
const json = JSON.parse(rawData);

const segments = (json.data && json.data.segments) || [];

// Look for a player-round segment that has kill events or similar
let foundKills = false;
for (const seg of segments) {
    if (seg.type === 'player-round') {
        if (seg.metadata && seg.metadata.kills && seg.metadata.kills.length > 0) {
            console.log("Found kills in player-round metadata:");
            console.log(JSON.stringify(seg.metadata.kills.slice(0, 2), null, 2));
            foundKills = true;
            break;
        }
        if (seg.stats && seg.stats.kills && seg.stats.kills.value > 0) {
            // Found a round where player got a kill, lets inspect the full segment
            console.log("Player had kills in this round. Segment keys:", Object.keys(seg));
            console.log("Metadata keys:", Object.keys(seg.metadata || {}));
            console.log("Does it have kill events?", !!seg.metadata.kills);
            foundKills = true;
            break;
        }
    }
}

if (!foundKills) {
    console.log("No detailed kill events found in player-round metadata.");
}
