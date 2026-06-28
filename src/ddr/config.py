"""Central config — env controls everything, fails fast with clear errors."""

import json
import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# ── Data files ────────────────────────────────────────────────────────────────
_proj_path = ROOT_DIR / "data" / "project.json"
_tpl_path = ROOT_DIR / "data" / "templates.json"

if not _proj_path.exists():
    raise FileNotFoundError(f"Missing: {_proj_path}")
if not _tpl_path.exists():
    raise FileNotFoundError(f"Missing: {_tpl_path}")

_proj = json.loads(_proj_path.read_text())
_templates = json.loads(_tpl_path.read_text())
_tpl_name = _proj.get("template_name", "daily_report")
_tpl = _templates.get(_tpl_name, {})

# ── Project metadata (env overrides project.json) ────────────────────────────
PROJECT_NAME: str = os.getenv("PROJECT_NAME") or _proj.get("project_name", "Project")
DEVELOPER_NAME: str = os.getenv("DEVELOPER_NAME") or _proj.get("developer_name", "")
DEVELOPER_ROLE: str = os.getenv("DEVELOPER_ROLE") or _proj.get("developer_role", "")
COMPANY_NAME: str = os.getenv("COMPANY_NAME") or _proj.get("company_name", "CloudGen")

_start_raw = os.getenv("PROJECT_START_DATE") or _proj.get("project_start_date", "")
if not _start_raw:
    raise ValueError("project_start_date not set in project.json or .env")
PROJECT_START_DATE: date = date.fromisoformat(_start_raw)

# ── Google Account ────────────────────────────────────────────────────────────
CREDS_FILE = Path(os.getenv("GOOGLE_CREDENTIALS_FILE") or ROOT_DIR / "config" / "credentials.json")
TOKEN_FILE = Path(os.getenv("GOOGLE_TOKEN_FILE") or ROOT_DIR / "config" / "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/chat.messages.create",
]

# ── Google Doc ────────────────────────────────────────────────────────────────
DOC_ID: str = _tpl.get("doc_id") or os.getenv("GOOGLE_DOC_ID", "")
if not DOC_ID:
    raise ValueError(
        "Google Doc ID not configured.\n"
        "Set GOOGLE_DOC_ID in .env  OR  set doc_id in data/templates.json"
    )

# ── Google Chat ───────────────────────────────────────────────────────────────
SPACE_NAME: str = os.getenv("GOOGLE_CHAT_SPACE", "")

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "")

# ── Local paths ───────────────────────────────────────────────────────────────
TASK_FILE = ROOT_DIR / "data" / "task.md"
SUMMARY_FILE = ROOT_DIR / "data" / "summary.md"
DOWNLOADS_DIR = Path.home() / "Downloads"
WORK_UPDATES_DIR = ROOT_DIR / "data" / "work_updates"

# ── Doc section markers ───────────────────────────────────────────────────────
SECTION_TODO = "Today's To-Do List"      # curly apostrophe
SECTION_TODO_ALT = "Today's To-Do List"  # straight apostrophe
SECTION_COMPLETED = "✅ Completed Tasks"


# ── Day counters ──────────────────────────────────────────────────────────────
def calendar_day_number() -> int:
    return max(1, (date.today() - PROJECT_START_DATE).days + 1)


def working_day_number() -> int:
    current = PROJECT_START_DATE
    today = date.today()
    day = 0
    while current <= today:
        if current.weekday() < 5:
            day += 1
        current += timedelta(days=1)
    return max(1, day)
