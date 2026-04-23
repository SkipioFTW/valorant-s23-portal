---
phase: 3
plan: 3
wave: 3
---

# Plan 3.3: Production Polish & Verification

## Objective
Perform a final audit of the Discord bot's features and ensure it is ready for the S24 launch.

## Context
- .gsd/SPEC.md
- .gsd/ROADMAP.md
- new_app_repo/Skipio-bot/

## Tasks

<task type="checkpoint:human-verify">
  <name>Comprehensive Command Audit</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
    - new_app_repo/Skipio-bot/cogs/ai.py
    - new_app_repo/Skipio-bot/cogs/matches.py
  </files>
  <action>
    Run the bot and test every major command:
    - `/stats` (and `/player_info`)
    - `/leaderboard`
    - `/standings`
    - `/ask_ai` (including thread continuity)
    - `/stats_chart`
  </action>
  <verify>User confirms all commands work as expected in a test server.</verify>
  <done>All commands verified to return correct data for both S23 and S24.</done>
</task>

<task type="auto">
  <name>Final Code Cleanup</name>
  <files>
    - new_app_repo/Skipio-bot/
  </files>
  <action>
    - Remove any debug print statements.
    - Ensure error handling is robust (no bot crashes on bad input).
    - Update documentation (BOT_SETUP.md) if new commands were added.
  </action>
  <verify>Linter check or manual review of commit-ready code.</verify>
  <done>Production-ready code with no stray debug logs.</done>
</task>

## Success Criteria
- [ ] 100% of Discord commands verified against S24 data.
- [ ] Documentation updated to reflect new Premium features.
