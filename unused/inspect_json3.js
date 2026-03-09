const fs = require('fs');
const path = require('path');
const filePath = path.join(__dirname, 'assets', 'matches', 'match_01be3cb9-87eb-47be-8ed3-e728c69916d2.json');
const rawData = fs.readFileSync(filePath, 'utf8');
const json = JSON.parse(rawData);

const playerSummary = json.data.segments.find(s => s.type === 'player-summary');
if (playerSummary && playerSummary.stats) {
    console.log("Player Summary Stats Keys:");
    for (const key of Object.keys(playerSummary.stats)) {
        console.log(`- ${key}: ${playerSummary.stats[key].value} (${playerSummary.stats[key].displayValue})`);
    }
} else {
    console.log("No player-summary found");
}
