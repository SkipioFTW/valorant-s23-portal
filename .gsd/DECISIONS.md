# DECISIONS.md (ADR)

> **ADR-001**: GSD Methodology
> **Date**: 2026-03-25
> **Status**: Accepted
> **Concept**: Use GSD (Get Shit Done) for project management and documentation.

## Phase 1: Foundation (Multi-Season Support) Decisions

**Date:** 2026-03-26

### Scope
- Add \`season_id\` to the \`matches\` table (FK to \`seasons.id\`).
- Create \`player_history\` table (\`player_id\`, \`season_id\`, \`rank\`) to track ranks per season.
- Preserve S23 match and team history while adding S24.

### Approach
- Chose: **Option B: Page-Specific Paths**
- Reason: Better SEO, bookmarking, and clearer context for the AI agent (e.g., \`/standings/s23\`).
- **Default Behavior**: All views and queries will default to the latest season if no specific season is requested.

### Constraints

## Phase 3: Premium Discord Integration Decisions

**Date:** 2026-04-23

### Scope
- **Compact /stats**: The `/stats` command will be a compact snapshot of player performance, distinctly more concise than `/player_info`.
- **Data Pruning**: Remove empty/non-functional stats from all commands (plants, defuses, survived, traded, clutches, ability_casts) to maintain data integrity.
- **S24 Default**: All commands must default to Season 24.

### Approach
- **Threaded AI Chat (Option B)**: The `/ask_ai` command will initiate a Discord thread for continuous conversation rather than a single response.
- **Auto-Archive**: AI threads will be set to auto-archive after 1 hour of inactivity.
- **Cooldowns**: Implement a cooldown on AI requests to prevent API overload.

### Constraints
- Must not break existing functionality in `analytics.py`, `ai.py`, or `matches.py`.

## Phase 4: S24 Launch & Final Polish Decisions

**Date:** 2026-04-26

### Scope
- **Rosters/Ranks**: User confirmed these are already updated. No programmatic changes required.
- **Schedule**: User confirmed schedule is correct. No changes required.
- **AI Intelligence**: Focus on absolute reliability for complex queries (standings calculations, rule-based questions, tie-breakers).

### Approach
- **Verification**: Hybrid approach using both manual checklists (`AUDIT.md`) and automated validation scripts (checking AI/API responses).
- **Target**: "The best it could be"—optimizing prompt context and internal reasoning.

### Constraints
- Do not modify existing roster/rank data unless a bug is discovered.
