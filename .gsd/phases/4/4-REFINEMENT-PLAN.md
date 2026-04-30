---
phase: 4
plan: 4
wave: 1
---

# Plan 4.4: Skipio ELO Refinement & Visibility

## Objective
Add rank filtering to web/bot leaderboards, integrate the page into the main navigation, and add performance thresholds.

## Tasks

<task type="auto">
  <name>Update Data Layer & Navigation</name>
  <files>
    - new_app_repo/src/lib/data.ts
    - new_app_repo/src/components/Navbar.tsx
  </files>
  <action>
    - Update `getSkipioLeaderboard` in `data.ts` to accept `rankFilter?: string`.
    - Add `Skipio ELO` to `mainNavItems` in `Navbar.tsx`.
  </action>
  <verify>Check Navbar and data.ts exports.</verify>
  <done>Navigation is updated and data layer supports filtering.</done>
</task>

<task type="auto">
  <name>Polish Web Leaderboard</name>
  <files>
    - new_app_repo/src/app/(main)/skipio/page.tsx
  </files>
  <action>
    - Add rank filtering UI (dropdown).
    - Add "Rating Guide" section.
    - Add performance tier badges (Struggling -> Godlike) to rows.
  </action>
  <verify>npm run build</verify>
  <done>The web leaderboard is now searchable and features performance indicators.</done>
</task>

<task type="auto">
  <name>Enhance Discord Bot</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/analytics.py
  </files>
  <action>
    - Add `/elo-leaderboard` command with rank filtering.
    - Update `/elo` command to show performance tier.
  </action>
  <verify>Python syntax check.</verify>
  <done>Bot commands are updated to support ELO leaderboards and tiers.</done>
</task>
