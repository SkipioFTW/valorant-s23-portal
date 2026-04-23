# Phase 3 Research: Premium Discord Integration

## Analysis of Current Bot State

Based on inspection of the `new_app_repo/Skipio-bot` directory:

### 1. Existing Commands
- **Analytics (`cogs/analytics.py`)**: 
  - `/standings`: Group rankings with S23/S24 filtering.
  - `/leaderboard`: Player rankings by ACS, K/D, ADR, KAST, HS%.
  - `/player_info`: Detailed player stats with Riot ID, Rank, Team, Archetype, Combat Stats, Agent Pool, and Recent Form.
  - `/team_info`: Team roster, record, map pool, and recent results.
  - `/compare_players` & `/compare_teams`: Head-to-head comparisons.
- **AI (`cogs/ai.py`)**:
  - `/ask_ai`: One-off question to the AI Analyst API.
  - `/stats_chart`: Interactive performance trends (ACS, K/D, etc.) using matplotlib.
- **Matches (`cogs/matches.py`)**:
  - Commands for match lookups (likely).

### 2. Gaps vs Phase Goals
- **Missing `/stats` command**: While `/player_info` exists, users typically expect `/stats`. This should be added as an alias or a more concise version.
- **AI Thread Integration**: The current `/ask_ai` is a stateless slash command. "Premium" integration often implies thread-based conversations where context is preserved.
- **S24 Alignment**: Verification is needed to ensure all commands default to S24 and correctly handle the transition.

## Proposed "Premium" Features
1. **Threaded AI Chat**: Instead of just an embed response, initiate a Discord thread for the question if requested, allowing follow-up questions.
2. **Enhanced /stats**: A beautiful, consolidated stats command that might include a small version of the radar chart or recent form by default.
3. **League Intelligence Sync**: Ensure the AI in Discord is using the "v8.0" intelligence (standings math, playoff rules) developed in Phase 2.

## Verification Plan
1. Test all slash commands in a test server.
2. Verify S23 vs S24 data separation in Discord responses.
3. Proof point: AI correctly identifies S23 winners vs S24 current leaders in Discord.
