# Daily Report Automation — Setup Guide

## One-time setup (~10 minutes)

### Step 1 — Install Python dependencies

```bash
cd /home/cloudgen-7/CloudGen/Projects/DDR
pip install -r requirements.txt
```

---

### Step 2 — Create Google Cloud credentials

1. Go to: https://console.cloud.google.com/
2. Create project → name it **"CloudGen Reports"**
3. Enable APIs (search each one):
   - **Google Docs API** → Enable
   - **Google Drive API** → Enable
4. Go to **APIs & Services → OAuth consent screen**
   - User type: External
   - App name: "CloudGen Daily Report"
   - Add your email (`alamin@cloudgen.bd`) as test user → Save
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Name: "Daily Report"
   - Click Create
7. Click **Download JSON**
8. Rename file to `credentials.json`
9. Move to: `/home/cloudgen-7/CloudGen/Projects/DDR/credentials.json`

---

### Step 3 — First run (one-time browser login)

```bash
cd /home/cloudgen-7/CloudGen/Projects/DDR
python3 daily_report.py --tasks "Test|Test|Test|Test|Test"
```

Browser opens → login with Google account → allow permissions.
`token.json` saved — won't ask again for ~1 year.

---

## Daily usage

### Via Claude Code (recommended)

```
/daily-report

Today I worked on:
[paste your work description here]
```

Claude formats into 5 clean tasks → updates Google Doc → downloads PDF.

### Direct command

```bash
python3 /home/cloudgen-7/CloudGen/Projects/DDR/daily_report.py \
  --tasks "Task 1 module|Task 2 module|Task 3 module|Task 4 module|Task 5 module" \
  --completed "0,1,2,3,4" \
  --status "On Track"
```

### JSON input

```bash
echo '{
  "tasks": ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"],
  "completed": [0, 1, 2, 3, 4],
  "status": "On Track"
}' | python3 /home/cloudgen-7/CloudGen/Projects/DDR/daily_report.py --stdin
```

---

## Output

| Output | Location |
|--------|----------|
| PDF | `~/Downloads/CloudGen_Report_YYYY-MM-DD.pdf` |
| Markdown | `~/work_updates/YYYY-MM-DD.md` |
| Google Doc | Same URL, auto-updated |

---

## Files

```
DDR/
├── daily_report.py     # Main automation script
├── requirements.txt    # Python dependencies
├── SETUP.md            # This file
├── credentials.json    # YOU add this (Step 2)
└── token.json          # Auto-created on first run
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| "credentials.json not found" | Complete Step 2 |
| "Access denied" | Enable Docs API + Drive API in Google Cloud |
| "Token expired" | Delete `token.json`, re-run |
| Tasks not updating | Doc structure may have changed — ask Claude to fix |
