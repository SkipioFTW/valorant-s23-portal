# Valorant Portal Deployment Guide

This guide explains how to manage the two environments (Production and Staging) and how to push changes to GitHub.

## 1. Running the App Locally

You must run the app from the **project root directory** (where this file is located).

### To run Production:
```powershell
streamlit run production/visitor_dashboard.py
```

### To run Staging:
```powershell
streamlit run staging/visitor_dashboard.py
```

### To run the Tracker Scraper (Bulk Scraper):
```powershell
# For production data
streamlit run production/get_tracker_json.py

# For staging data
streamlit run staging/get_tracker_json.py
```

---

## 2. Development Workflow (Staging to Production)

When you have finished testing a new feature in `staging/` and want to move it to `production/`:

### Step A: Copy files from Staging to Production
Run these commands in your terminal:
```powershell
copy staging/visitor_dashboard.py production/visitor_dashboard.py
copy staging/tracker_scraper.py production/tracker_scraper.py
copy staging/get_tracker_json.py production/get_tracker_json.py
```

### Step B: (Optional) Sync Databases
If you made database changes in staging and want them in production:
```powershell
copy data/valorant_s23_staging.db data/valorant_s23.db
```
*Note: Be careful, this will overwrite your production data with staging data.*

---

## 3. Pushing to GitHub

The `.gitignore` file is configured to **exclude** the `staging/` folder. This means your development work stays local until you copy it to the `production/` folder.

### Step A: Stage your changes
```powershell
git add .
```

### Step B: Commit your changes
```powershell
git commit -m "Your description of the changes"
```

### Step C: Push to GitHub
```powershell
git push origin main
```

---

## 4. Important Notes

- **Paths**: The app automatically detects its location and finds the `assets/` and `data/` folders. Do not change the folder names.
- **Database**: 
  - Production uses: `data/valorant_s23.db`
  - Staging uses: `data/valorant_s23_staging.db`
- **GitHub Sync**: When you push, only the `production/`, `assets/`, `data/`, `docs/`, `predictor/`, and `scripts/` folders are sent to GitHub. The `staging/` folder remains private on your machine.
