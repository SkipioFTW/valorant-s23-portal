# Phase 4 Decisions

**Date**: 2026-04-30

## Formula Weights
**Decided**: Approved
- ACS: 40% weight
- K/D: 30% weight
- ADR: 20% weight
- KAST: 10% weight

## Rank Normalization (Q2)
**Decided**: Peer-relative comparison
- Compare each player's performance against the **average stats of all other players at the same rank** in the league (not a static multiplier).
- This ensures Immortal vs. Immortal and Gold vs. Gold — a player who massively outperforms their rank peers earns a much higher ELO.
- If a rank has <3 data points, fall back to the nearest rank tier.

## Aggregation Model (Q3)
**Decided**: Historical ELO
- Each player starts at a **base of 1000 ELO**.
- After each **completed** match, their ELO is adjusted up or down based on their performance score relative to what was "expected" for their rank.
- **Must include ALL historical matches** (all seasons), not just the current one.
- Final score is the player's cumulative ELO after all their matches.

## Bonus System (Q4)
**Decided**: No bonuses. Keep the formula pure.

## Display & Delivery
**Decided**:
1. A dedicated **Skipio ELO Leaderboard** page on the web portal.
2. A **Discord bot command** (e.g., `/elo [player_name]`) that returns a player's current Skipio Indicator rating.
