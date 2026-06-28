# DDR — Daily Report Automation Setup

## One-time setup (~15 minutes)

### Step 1 — Install dependencies

```bash
cd /home/cloudgen-7/CloudGen/Projects/DDR
pip install -r requirements.txt
```

---

### Step 2 — Configure .env

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_DOC_ID=1mbVdn6llomVeO4HdntmMal4R11jlNaVsfeqnMUJZE2k
GOOGLE_CHAT_SPACE=spaces/AAQAmsfYrL8
ANTHROPIC_API_KEY=your_key_from_console.anthropic.com
```

---

### Step 3 — Google Cloud credentials

1. Go to: https://console.cloud.google.com/
2. Create (or select) a project
3. Enable these APIs:
   - Google Docs API
   - Google Drive API
   - Google Chat API
4. **APIs & Services → OAuth consent screen**
   - User type: External
   - App name: "CloudGen Daily Report"
   - Add `alamin@cloudgen.bd` as test user → Save
5. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Name: "Daily Report"
   - Download JSON → rename to `credentials.json`
6. Move to: `config/credentials.json`

> ⚠️ Testing mode tokens expire every 7 days. Delete `config/token.json` and re-run Step 4 to refresh.

---

### Step 4 — First run (one-time browser login)

```bash
cd /home/cloudgen-7/CloudGen/Projects/DDR
python -c "from src.ddr.google_auth import get_credentials; get_credentials(); print('Auth OK')"
```

Browser opens → login → allow all permissions → `config/token.json` saved.

---

## Daily usage

### Web UI (recommended)

```bash
cd /home/cloudgen-7/CloudGen/Projects/DDR
uvicorn src.ddr.web.app:app --reload --port 8765
```

Open: http://localhost:8765

**Workflow:**
1. Describe your day in plain text
2. Click **✨ AI Format** → Claude formats into task list
3. Edit tasks if needed (add/remove rows freely)
4. Toggle "Send to Chat" if wanted
5. Click **🚀 Generate Report**

---

### CLI

```bash
# Uses data/task.md automatically
python -c "from src.ddr.pipeline import run; r = run(); print(r.to_dict())"

# With description (AI formats)
python -c "
from src.ddr.pipeline import run
r = run(description='Fixed auth bug and built package pages', task_count=5)
print(r.to_dict())
"
```

---

### Claude Code skill

```
/daily-report
Today I worked on: [description]
```

---

## File structure

```
DDR/
├── src/ddr/
│   ├── config.py          # Central config loader
│   ├── google_auth.py     # Unified OAuth (docs + drive + chat scopes)
│   ├── docs_service.py    # Google Docs update (variable task count)
│   ├── drive_service.py   # PDF export + Drive upload
│   ├── chat_service.py    # Google Chat send (real content)
│   ├── tasks_parser.py    # task.md parser (strips checkboxes)
│   ├── summary_service.py # summary.md dedup + append
│   ├── ai_formatter.py    # Claude Haiku task formatter
│   ├── pipeline.py        # Full pipeline orchestrator
│   └── web/
│       ├── app.py         # FastAPI routes
│       └── templates/
│           └── index.html # Web UI (plain HTML + JS)
├── scripts/               # Legacy CLI (still work)
├── data/
│   ├── task.md            # Active tasks (## todo section)
│   ├── summary.md         # Running work log
│   ├── project.json       # Project metadata
│   ├── templates.json     # Doc ID mapping
│   └── work_updates/      # Daily markdown archives (gitignored)
├── config/
│   ├── credentials.json   # YOU add this (Step 3) — gitignored
│   └── token.json         # Auto-created on first run — gitignored
├── .env                   # YOU create from .env.example — gitignored
└── requirements.txt
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `credentials.json not found` | Complete Step 3 |
| `Google Doc ID not configured` | Set GOOGLE_DOC_ID in .env |
| `ANTHROPIC_API_KEY not set` | Add to .env |
| `RefreshError` / token expired | Delete `config/token.json`, re-run Step 4 |
| `Section not found in Doc` | Doc structure changed — check `SECTION_TODO` in config.py |
| Chat 403 error | Token missing chat scope — delete token.json, re-run Step 4 |
