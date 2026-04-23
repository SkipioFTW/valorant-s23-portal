---
phase: 3
plan: 1
wave: 1
---

# Plan 3.1: Core Command Enhancements

## Objective
Finalize the core analytics commands in Discord, including adding the `/stats` alias and ensuring full S24 compliance.

## Context
- .gsd/SPEC.md
- .gsd/phases/3/RESEARCH.md
- new_app_repo/Skipio-bot/cogs/analytics.py

## Tasks

<task type="auto">
  <name>Add /stats command</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
  </files>
  <action>
    Implement a `/stats` slash command that acts as a wrapper or alias for the existing `player_info` command logic. 
    - Ensure it supports both `@mention` and name strings.
    - Ensure it defaults to the latest active season (S24).
  </action>
  <verify>Check analytics.py for the new @app_commands.command(name="stats") decorator or wrapper.</verify>
  <done>Running the bot would show /stats in the slash command list.</done>
</task>

<task type="auto">
  <name>S24 Season Alignment</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
    - new_app_repo/Skipio-bot/database.py
  </files>
  <action>
    - Review all SQL queries in `analytics.py` to ensure they use the `season_id` filtering correctly.
    - Verify `get_default_season` in `database.py` returns 'S24'.
  </action>
  <verify>Search for 'S24' in database.py and verify SQL season filters in analytics.py.</verify>
  <done>All commands default to S24 and correctly filter data when a season is specified.</done>
</task>

## Success Criteria
- [ ] `/stats` command is available and functional.
- [ ] Database defaults to S24 for all Discord queries.
