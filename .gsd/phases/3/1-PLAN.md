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
  <name>Data Pruning & /player_info Cleanup</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
  </files>
  <action>
    - Remove non-functional metrics from the `player_info` command and its SQL query: plants, defuses, survived, traded, clutches, ability_casts.
    - Clean up the embed to remove the empty "Impact" and "Objectives" blocks if they only contained those metrics.
  </action>
  <verify>Check analytics.py to ensure the SQL query and embed field construction no longer reference the pruned metrics.</verify>
  <done>/player_info only shows valid data (ACS, K/D, ADR, KAST, HS%, Agent Pool, Recent Form).</done>
</task>

<task type="auto">
  <name>Implement Compact /stats snapshot</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
  </files>
  <action>
    Implement a `/stats` command that provides a compact snapshot of a player.
    - Show key metrics: ACS, K/D, ADR, KAST.
    - Use a simpler embed than `/player_info` for quick reference.
    - Support @mention and name strings.
  </action>
  <verify>Check for @app_commands.command(name="stats") in analytics.py.</verify>
  <done>/stats displays a high-level summary suitable for quick viewing.</done>
</task>

<task type="auto">
  <name>S24 Season Alignment</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
    - new_app_repo/Skipio-bot/database.py
  </files>
  <action>
    - Review all SQL queries in `analytics.py` to ensure they use the `season_id` filtering correctly and default to S24.
    - Update `get_default_season` in `database.py` if it still points to S23.
  </action>
  <verify>Verify SQL filters and default season value.</verify>
  <done>Bot defaults to S24 across all analytics commands.</done>
</task>

## Success Criteria
- [ ] `/stats` command is available and functional.
- [ ] Database defaults to S24 for all Discord queries.
