---
phase: 3
plan: 2
wave: 2
---

# Plan 3.2: Premium AI Thread Integration

## Objective
Upgrade the AI integration in Discord from a simple slash command to a persistent, thread-based conversation model.

## Context
- .gsd/SPEC.md
- new_app_repo/Skipio-bot/cogs/ai.py
- new_app_repo/portal/api/chat (reference to how the chat API works)

## Tasks

<task type="auto">
  <name>Implement Thread-based AI Chat with Auto-Archive</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/ai.py
  </files>
  <action>
    Modify or extend the `/ask_ai` command to:
    - Create a public Discord thread for the conversation.
    - Set the thread's auto-archive duration to 60 minutes (1 hour).
    - Listen for new messages in that thread and forward them to the AI API with history.
    - Handle the "history" parameter in the API payload to maintain context within the thread.
  </action>
  <verify>Check thread creation code for `auto_archive_duration=60` and history management logic.</verify>
  <done>AI chat occurs in public threads that auto-archive after 1 hour of inactivity.</done>
</task>

<task type="auto">
  <name>Implement AI Cooldown & v8.0 Sync</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/ai.py
  </files>
  <action>
    - Add a `discord.app_commands.checks.cooldown` to the `/ask_ai` command to prevent spamming the AI backend.
    - Ensure the `ask_ai` command payload sends the appropriate `seasonId` (defaulting to S24) to leverage Phase 2's League Intelligence.
  </action>
  <verify>Check for @app_commands.checks.cooldown decorator and seasonId in the payload.</verify>
  <done>AI requests are rate-limited and use S24 League Intelligence by default.</done>
</task>

## Success Criteria
- [ ] Users can have multi-turn conversations with the AI in Discord threads.
- [ ] AI conversation history is correctly passed to the backend API.
