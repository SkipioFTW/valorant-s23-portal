# ROADMAP.md

> **Current Milestone**: v2.0-BROADCAST-AND-ELO
> **Goal**: Introduce a dedicated production suite for OBS overlays and implement a rank-relative custom ELO system (Skipio Indicator).

## Must-Haves
- [ ] **Broadcast Hub UI**: A dashboard for stream operators to generate and copy OBS overlay links.
- [ ] **Standings Overlay**: Animated, transparent-background overlay for specific groups.
- [ ] **Playoffs Overlay**: Animated tournament bracket overlay.
- [ ] **Player Comparison Overlay**: Head-to-head visual comparison of two selected players.
- [ ] **Matchup Overlay**: A rotating/carousel overlay showing matchup details between two teams.
- [ ] **Skipio Indicator (Custom ELO)**: A new mathematical formula that calculates player rating relative to their rank and peers.
- [ ] **ELO Integration**: Display the Skipio Indicator on the leaderboard, player profiles, and Discord bot.

## Phases

### Phase 1: Broadcast Architecture & Hub UI
**Status**: ⬜ Not Started
**Objective**: Set up the transparent `/overlay/*` routing structure in Next.js and build the control panel where production staff can select parameters and generate OBS links.

### Phase 2: Core Animated Overlays
**Status**: ⬜ Not Started
**Objective**: Design and implement the Standings, Playoffs, and Player Comparison overlays with premium, FLV-branded animations tailored for broadcast.

### Phase 3: Matchup Carousel Overlay
**Status**: ⬜ Not Started
**Objective**: Build the dynamic matchup overlay that automatically transitions between different informational cards (team stats, key players, etc.) during a stream.

### Phase 4: Skipio Indicator Formula & Data Pipeline
**Status**: ✅ Complete
**Goal**: Research, mathematically formulate, and implement the custom ELO system. Ensure it factors in base stats weighted against the player's specific rank distribution.

### Phase 5: Polish & Integration
**Status**: ⬜ Not Started
**Objective**: Integrate the Skipio Indicator into all front-facing UI components (Leaderboard, Discord Bot) and ensure overlay animations run seamlessly at 60fps in OBS.
