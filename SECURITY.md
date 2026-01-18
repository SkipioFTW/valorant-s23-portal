# Security Enhancements & Protocols

## Overview
This document outlines the security measures and protocols implemented in the VALORANT S23 Portal application.

## 1. Cross-Site Scripting (XSS) Prevention
*   **Strict Template Rendering**: A dedicated `render_html(template_string, **kwargs)` function has been implemented to handle all dynamic HTML generation.
*   **Auto-Escaping**: All variable inputs passed to `render_html` are automatically escaped using `html.escape()`, preventing the injection of malicious scripts via user input.
*   **Safe Usage**: Direct calls to `st.markdown(..., unsafe_allow_html=True)` are restricted to static or pre-sanitized content.

## 2. Session Management
*   **IP-Based Access Control**: Admin sessions are validated against the user's IP address.
    *   **Blocking Logic**: Login attempts are blocked if *another* IP address is currently active in an admin session.
    *   **Refresh Allowance**: Users can refresh their browser or open new tabs from the same IP address without being locked out.
*   **Session Clearing**: An "Unlock Access" feature allows admins (with a special `FORCE_UNLOCK_TOKEN`) to clear stuck sessions.
*   **Auto-Logout**: Explicit logout functionality clears session state and redirects to the public portal.

## 3. Data Integrity & Caching
*   **Immediate Consistency**: Admin actions (Adding/Removing players, Editing Teams) trigger `st.cache_data.clear()` to ensure the UI reflects changes immediately, preventing "stale data" confusion.
*   **Database Isolation**:
    *   **Production**: `data/valorant_s23.db`
    *   **Git Ignore**: All `.db` files in `data/*` are ignored by Git to prevent accidental exposure of production data or overwriting of remote databases.

## 4. Secret Management
*   **Validation**: The application validates critical secrets (`ADMIN_LOGIN_TOKEN`, `GH_TOKEN`, etc.) at startup and halts if they are missing.
*   **Storage**: Secrets are managed via `.streamlit/secrets.toml` (local) or environment variables (deployment), which are excluded from version control.

## 5. Deployment Protocol
*   **Staging Isolation**: The `staging/` directory is git-ignored. Code is verified in staging before being manually copied to `production/`.
*   **Testing Assets**: Test scripts (e.g., `create_test_admin.py`) and dummy secrets are strictly confined to the local environment and excluded from Git.
