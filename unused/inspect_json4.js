const fs = require('fs');
const path = require('path');
const filePath = path.join(__dirname, 'assets', 'matches', 'match_01be3cb9-87eb-47be-8ed3-e728c69916d2.json');
const rawData = fs.readFileSync(filePath, 'utf8');
const json = JSON.parse(rawData);

const playerSummary = json.data.segments.find(s => s.type === 'player-summary');
if (playerSummary && playerSummary.stats) {
    console.log("Player Summary Stats Keys:");
    for (const key of Object.keys(playerSummary.stats)) {
        const stat = playerSummary.stats[key];
        const val = typeof stat === 'object' && stat !== null ? stat.value : stat;
        console.log(`- ${key}: ${val}`);
    }
} else {
    console.log("No player-summary found");
}

console.log("\n=====================\n");

const roundSummary = json.data.segments.find(s => s.type === 'round-summary');
if (roundSummary && roundSummary.stats) {
    console.log("Round Summary Stats Keys:");
    for (const key of Object.keys(roundSummary.stats)) {
        const stat = roundSummary.stats[key];
        const val = typeof stat === 'object' && stat !== null ? stat.value : stat;
        console.log(`- ${key}: ${val}`);
    }
} else {
    console.log("No round-summary found");
}
