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
  <name>Implement Thread-based AI Chat</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/ai.py
  </files>
  <action>
    Modify or extend the `/ask_ai` command to:
    - Create a public Discord thread if the user wants a continuous conversation.
    - Listen for new messages in that thread and forward them to the AI API with history.
    - Handle the "history" parameter in the API payload to maintain context within the thread.
  </action>
  <verify>Check ai.py for thread creation logic and message listener.</verify>
  <done>AI responds to follow-up messages within the created Discord thread, maintaining context.</done>
</task>

<task type="auto">
  <name>AI League Intelligence Sync</name>
  <files>
    - new_app_repo/Skipio-bot/cogs/ai.py
  </files>
  <action>
    Ensure the `ask_ai` command payload sends the appropriate `seasonId` and any other metadata required for the "v8.0" intelligence.
    - Update system messages if necessary (or verify they are handled server-side).
  </action>
  <verify>Verify the payload structure in ai.py matches the latest /api/chat requirements.</verify>
  <done>AI responses in Discord reflect the same advanced intelligence as the web portal.</done>
</task>

## Success Criteria
- [ ] Users can have multi-turn conversations with the AI in Discord threads.
- [ ] AI conversation history is correctly passed to the backend API.
