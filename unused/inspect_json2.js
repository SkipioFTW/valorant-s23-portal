const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'assets', 'matches', 'match_01be3cb9-87eb-47be-8ed3-e728c69916d2.json');
const rawData = fs.readFileSync(filePath, 'utf8');
const json = JSON.parse(rawData);

let foundPaths = [];

function searchObj(obj, currentPath) {
    if (!obj || typeof obj !== 'object') return;

    if (Array.isArray(obj)) {
        obj.forEach((item, index) => searchObj(item, `${currentPath}[${index}]`));
    } else {
        for (const [key, value] of Object.entries(obj)) {
            const nextPath = `${currentPath}.${key}`;
            if (key.toLowerCase().includes('victim') || key.toLowerCase().includes('killer') || key === 'killEvents' || (key === 'kills' && Array.isArray(value))) {
                foundPaths.push(nextPath);
            }
            searchObj(value, nextPath);
        }
    }
}

searchObj(json, 'root');
console.log("Found paths:", foundPaths.slice(0, 10));
if (foundPaths.length === 0) {
    console.log("No killer/victim/killEvents arrays found in the entire JSON.");
}
