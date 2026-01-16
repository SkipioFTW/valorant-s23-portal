# Administrator Guide: VALORANT S23 Portal

## **Accessing the Admin Panel**
To access the administrative tools, navigate to the **ADMIN LOGIN** section from the main portal entry.

---

## **Unlocking & Session Management**
The system is designed to prevent multiple administrators from making conflicting changes at the same time. 

### **The Lock System**
If you see an "Access Denied" message, someone is already logged in. You have two options:
1.  **Option 1: Unlock your specific ID**: Use this if you refreshed the page or your browser crashed. It clears the lock for **your device only**.
2.  **Option 2: Force Unlock Everything**: Use this as a last resort if a session from another admin is stuck. This requires the **Force Unlock Token**.

### **⚠️ Important: Logging Out**
**DO NOT simply close the browser tab or refresh the page.**
- Always use the **Logout** button in the sidebar.
- This immediately releases the session lock.
- If you refresh or close without logging out, the system will keep you "locked out" for 60 seconds.

---

## **Task Walkthroughs**

### **1. Updating Match Scores & Data**
**Tab**: `Admin Panel`
1.  Navigate to the **Match Editor** section at the bottom of the page.
2.  Select the **Week** of the tournament.
3.  Select the specific **Match** from the dropdown list.
4.  Enter the overall scores for Team 1 and Team 2.
5.  **Forfeits**: If a match was a forfeit (13-0), check the "Match-level Forfeit" box and select the winner.

### **2. Importing Data from Tracker.gg**
**⚠️ CRITICAL: Use Match IDs, not full Links.**
Currently, the scraper works best when provided with the **Match ID** only.
- **Full Link**: `https://tracker.gg/valorant/match/0a6ecd9e-c88f-41c4-ab49-58c0c5c8fd7d`
- **Match ID**: `0a6ecd9e-c88f-41c4-ab49-58c0c5c8fd7d` (The last part of the URL).

**Steps**:
1.  In the **Match Editor** (Admin Panel), open a "Map" expander (e.g., Map 1).
2.  Paste the **Match ID** into the "Tracker.gg Link" field.
3.  The system will automatically scrape the map name, round scores, and all player statistics (ACS, K/D/A, Agents).
4.  Review the auto-filled scoreboard and click **Save Match**.

### **3. Adding or Editing Players**
**Tab**: `Players Directory`
1.  Navigate to the **Players Directory** tab in the top navigation bar.
2.  Scroll to the bottom of the page.
3.  You will find the **Admin: Add Player** form (visible only to logged-in admins).
4.  Enter the Name, Riot ID, and select their Team.

### **4. Managing Teams**
**Tab**: `Teams`
1.  Navigate to the **Teams** tab.
2.  Each team card will have an **Edit** button (visible to admins).
3.  You can update team names, group assignments, and logos.

### **5. Database Backups**
**Tab**: `Admin Panel`
1.  Navigate to the **Cloud Backup** section.
2.  Click **Backup DB to GitHub** to save all current standings, matches, and player data to the cloud.
3.  This is highly recommended after every match day.

---

## **Admin Roles**
- **Admin**: Standard access for managing matches, players, and teams.
- **Dev**: Full access including database resets, account creation for other admins, and manual SQL imports.
