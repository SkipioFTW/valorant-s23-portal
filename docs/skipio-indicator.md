# Skipio Indicator — Technical Documentation

**Version 2.0 (Blended, Volume-Independent ELO)**  
**League**: FLV Valorant Tournament  
**Author**: FLV Production Suite  

---

## 1. Overview

The **Skipio Indicator** is the official player rating system for the FLV Valorant Tournament League. It is a **custom ELO system** designed to measure player skill in a way that is:

1. **Rank-Relative** — an Immortal player is only compared to other Immortals, a Gold to other Golds.
2. **Context-Aware** — if everyone in a specific match had a low-scoring game, a player is not unfairly punished for the conditions of that match.
3. **Volume-Independent** — a player who plays 2 matches and dominates both will have a higher ELO than a player who plays 50 mediocre matches. Quantity of games does not reward or punish; only quality of performance does.

---

## 2. Fundamental Concepts

### 2.1 Raw Performance Score

For every **map appearance** in a completed match, a player receives a **Raw Score**. This is a weighted combination of four combat statistics:

```
RawScore = (ACS × 0.40) + (K/D × 30 × 0.30) + (ADR × 0.20) + (KAST × 0.10)
```

| Stat | Weight | Reason |
|------|--------|--------|
| **ACS** (Avg. Combat Score) | 40% | Primary measure of overall combat impact |
| **K/D** (Kill/Death ratio) | 30% | Efficiency and survival |
| **ADR** (Avg. Damage per Round) | 20% | Raw damage contribution |
| **KAST** (Kill/Assist/Survive/Trade %) | 10% | Team play, consistency, clutch factor |

> **Note**: K/D is multiplied by 30 to normalise it to the same numerical scale as the other metrics (~100–300).

---

### 2.2 Rank Groups

Because the league contains players of vastly different skill levels, direct comparisons between an Iron player and an Immortal player would be meaningless. Players are therefore assigned to one of four **Rank Groups**:

| Group | Ranks |
|-------|-------|
| **Group 1** (Low) | Iron, Bronze |
| **Group 2** (Mid) | Silver, Gold |
| **Group 3** (High) | Platinum, Diamond |
| **Group 4** (Elite) | Ascendant, Immortal, Radiant |

All comparisons are made **within** these groups.

---

## 3. The Blended Comparison Formula

Each map appearance is evaluated using **two independent benchmarks**, blended 50/50:

### 3.1 Global Peer Comparison (50%)

The player's Raw Score is compared against the **overall season average** of all players in their Rank Group across every single completed match.

```
GlobalNorm = (RawScore / GlobalGroupAvg) × 100
```

- `GlobalGroupAvg` = average Raw Score of all players in the same Rank Group, across all completed matches in league history.
- A result of **100** means the player performed exactly at their rank-group average.
- A result of **120** means 20% above average.

### 3.2 Lobby Peer Comparison (50%)

The player's Raw Score is compared against only the other players **in the same Rank Group** who played **in that exact same match**.

```
LobbyNorm = (RawScore / LobbyGroupAvg) × 100
```

- `LobbyGroupAvg` = average Raw Score of all players in the same Rank Group within that specific match.
- **Edge case**: If the player is the **only** member of their Rank Group in a match (e.g., the only Diamond player), `LobbyNorm` falls back to `GlobalNorm` (i.e., 100% weight on the global comparison for that appearance).

### 3.3 The Blended Score

Both normalised scores are blended with equal weight:

```
BlendedScore = (GlobalNorm × 0.50) + (LobbyNorm × 0.50)
```

**Why blend both?**

| Scenario | What happens |
|----------|-------------|
| Slow, low-kill tactical match for everyone | `LobbyNorm` ≈ 100 (protected from mass punishment), `GlobalNorm` < 100. Blending softens the penalty. |
| Player stat-pads against weak opponents | `GlobalNorm` may still be high, but `LobbyNorm` will normalise it against the actual lobby. |
| Normal match | Both converge naturally to the same result. |

---

## 4. The Volume-Independent ELO Rating

### 4.1 Computing the Final ELO

After accumulating a `BlendedScore` for every map appearance in a player's career, the final ELO is calculated as:

```
AverageBlendedScore = mean(BlendedScore₁, BlendedScore₂, ..., BlendedScoreₙ)

ELO = 1000 + (AverageBlendedScore − 100) × 20
```

**Base ELO: 1000.** A player who performs exactly at their rank average in every single match will have exactly `1000` ELO.

### 4.2 Why This Is Volume-Independent

The formula uses the **arithmetic mean** (average) of all `BlendedScores`, not a running sum.

| Player | Maps Played | Avg Performance | ELO |
|--------|-------------|-----------------|-----|
| Player A | 5 maps | 110 (10% above avg) | `1000 + (10×20) = 1200` |
| Player B | 50 maps | 110 (10% above avg) | `1000 + (10×20) = 1200` |
| Player C | 50 maps | 103 (3% above avg) | `1000 + (3×20) = 1060` |
| Player D | 5 maps | 90 (10% below avg) | `1000 + (-10×20) = 800` |

Player A and Player B have **identical ELOs** despite an enormous difference in games played. Player D is punished for performing poorly regardless of their low game count.

### 4.3 Minimum Maps Requirement

To prevent outliers from distorting the leaderboard (e.g., a player who had one extraordinary game), a minimum of **3 map appearances** is required before a player appears on the Skipio Leaderboard.

---

## 5. Performance Tiers

ELO ratings are mapped to human-readable **performance tiers**:

| ELO Range | Tier | Meaning |
|-----------|------|---------|
| **1400+** | 🔥 Godlike | Transcendental performance vs. rank peers |
| **1200 – 1399** | 💎 Elite | Consistent dominant outperformer |
| **1050 – 1199** | 🟢 Strong | Reliable above-average contributor |
| **950 – 1049** | ⚪ Baseline | Standard rank performance |
| **850 – 949** | 🟠 Below Average | Underperforming relative to rank peers |
| **< 850** | 🔴 Struggling | Significant underperformance |

---

## 6. Worked Example

**Scenario**: A Gold player (Rank Group 2) plays 3 maps.

**League-wide Gold Group average**: `RawScore = 150`

### Map 1 — Dominated
- Stats: ACS=280, K/D=1.8, ADR=165, KAST=75
- `RawScore = (280×0.4) + (1.8×30×0.3) + (165×0.2) + (75×0.1) = 112 + 16.2 + 33 + 7.5 = 168.7`
- Lobby had 3 Gold players with avg `RawScore = 145`
- `GlobalNorm = (168.7/150)×100 = 112.5`
- `LobbyNorm = (168.7/145)×100 = 116.3`
- `BlendedScore = (112.5×0.5) + (116.3×0.5) = 114.4`

### Map 2 — Rough game (but so was everyone's)
- Stats: ACS=160, K/D=1.0, ADR=120, KAST=60
- `RawScore = 64 + 9 + 24 + 6 = 103`
- Lobby Gold avg `RawScore = 105` (everyone struggled)
- `GlobalNorm = (103/150)×100 = 68.7`
- `LobbyNorm = (103/105)×100 = 98.1`
- `BlendedScore = (68.7×0.5) + (98.1×0.5) = 83.4`

> **Notice**: Without the lobby comparison, this map would have a `GlobalNorm` of 68.7, severely punishing the player. But since everyone in the lobby had a hard match, the `LobbyNorm` of 98.1 softens the blow.

### Map 3 — Solid performance
- Stats: ACS=230, K/D=1.5, ADR=145, KAST=72
- `RawScore = 92 + 13.5 + 29 + 7.2 = 141.7`
- Lobby Gold avg `RawScore = 140`
- `GlobalNorm = (141.7/150)×100 = 94.5`
- `LobbyNorm = (141.7/140)×100 = 101.2`
- `BlendedScore = (94.5×0.5) + (101.2×0.5) = 97.9`

### Final ELO Calculation

```
AverageBlendedScore = (114.4 + 83.4 + 97.9) / 3 = 98.57

ELO = 1000 + (98.57 − 100) × 20
ELO = 1000 + (−1.43 × 20)
ELO = 1000 − 28.6
ELO ≈ 971
```

**Result**: 971 ELO — "⚪ Baseline" tier. Despite dominating Map 1, the rough Map 2 (softened by context) and a slightly below-average Map 3 put the player just below the league average. A fair and accurate assessment.

---

## 7. Implementation Reference

### 7.1 TypeScript (Next.js Web Portal)

**Location**: `new_app_repo/src/lib/data.ts`

**Key functions**:
- `getRankGroup(rankStr)` — maps rank strings to Rank Group IDs 1–4
- `calculateRawScore(acs, kd, adr, kast)` — computes the weighted Raw Score
- `getSkipioTier(elo)` — maps an ELO value to a performance tier label & colour
- `getSkipioLeaderboard(rankFilter?)` — the main data pipeline; returns a sorted `SkipioEntry[]`

**Leaderboard page**: `/skipio` — supports optional rank filtering via query param `?rank=Gold`

### 7.2 Python (Discord Bot)

**Location**: `new_app_repo/Skipio-bot/cogs/analytics.py`

**Commands**:
- `/elo [player]` — shows a single player's Skipio ELO, tier, maps played, and avg raw score
- `/skipio-leaderboard [rank] [min_games]` — shows the top-10 ELO ratings, optionally filtered by rank tier

Both commands use the same mathematical formula as the TypeScript implementation — all stats are fetched from the shared PostgreSQL database and computed in-memory.

---

## 8. Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **50/50 blend** | Equal weight to global context (rank difficulty) and local context (match difficulty). Adjustable in future seasons. |
| **×20 ELO multiplier** | A 10% performance difference from average = ±200 ELO, which matches the spread of typical ELO systems and makes the tiers feel meaningful. |
| **Base of 1000** | Industry standard baseline that gives room to fall (toward 0) and rise (past 1400+) without artificial floors. |
| **3 min maps** | Prevents single-game outliers from distorting leaderboard rankings. |
| **Rank Groups not individual ranks** | Small league sizes mean some individual ranks (e.g., Radiant) may have 1–2 players, making per-rank averages statistically meaningless. Groups of 2–4 ranks ensure robust sample sizes. |

---

## 9. Data Sources

All data is sourced from the FLV Valorant League database (Supabase / PostgreSQL):

| Table | Purpose |
|-------|---------|
| `players` | Player name, Riot ID, current rank |
| `matches` | Match status (only `completed` matches are included) |
| `match_stats_map` | Per-map per-player stats: ACS, kills, deaths, ADR, KAST |

> **Only `completed` matches are ever included.** Scheduled, upcoming, or cancelled matches have zero impact on any player's ELO.

---

*For questions about the formula or to request adjustments, contact the FLV Production Team.*
