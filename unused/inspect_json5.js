const fs = require('fs');
const path = require('path');
const filePath = path.join(__dirname, 'assets', 'matches', 'match_01be3cb9-87eb-47be-8ed3-e728c69916d2.json');
const rawData = fs.readFileSync(filePath, 'utf8');
const json = JSON.parse(rawData);

const out = {};

const ps = json.data.segments.find(s => s.type === 'player-summary');
if (ps && ps.stats) {
    out.playerSummary = Object.keys(ps.stats);
}

const rs = json.data.segments.find(s => s.type === 'round-summary');
if (rs && rs.stats) {
    out.roundSummary = Object.keys(rs.stats);
}

fs.writeFileSync('keys_dump.json', JSON.stringify(out, null, 2));
console.log("Dumped to keys_dump.json");
