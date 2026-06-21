#!/usr/bin/env python3
"""
CloudGen Daily Report — updates Report Date + To-Do list in Google Doc, downloads PDF.

task.md format:
    ## todo
    - Task 1
    - Task 2
    - Task 3
    - Task 4
    - Task 5

Usage:
    ./report              (reads task.md automatically)
    ./report --tasks "T1|T2|T3|T4|T5"
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

DOC_ID = os.getenv("GOOGLE_DOC_ID", "")
_start = os.getenv("PROJECT_START_DATE", "2026-06-17")
PROJECT_START_DATE = date.fromisoformat(_start)
CREDS_FILE = ROOT_DIR / "config" / "credentials.json"
TOKEN_FILE = ROOT_DIR / "config" / "token.json"
TASK_FILE = ROOT_DIR / "data" / "task.md"
DOWNLOADS_DIR = Path.home() / "Downloads"
WORK_UPDATES_DIR = ROOT_DIR / "data" / "work_updates"

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

SECTION_TODO = "Today’s To-Do List"
SECTION_COMPLETED = "✅ Completed Tasks (From To-Do)"


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDS_FILE}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def read_tasks_from_file() -> list:
    if not TASK_FILE.exists():
        print(f"ERROR: task.md not found at {TASK_FILE}")
        sys.exit(1)
    tasks = []
    in_todo = False
    for line in TASK_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("## todo") or line.startswith("## tasks"):
            in_todo = True
            continue
        if line.startswith("##"):
            in_todo = False
            continue
        if in_todo and line.startswith("- "):
            tasks.append(line[2:].strip())
    return tasks


def get_paragraphs(doc: dict) -> list:
    result = []
    for el in doc.get("body", {}).get("content", []):
        if "paragraph" in el:
            para = el["paragraph"]
            text = "".join(
                e.get("textRun", {}).get("content", "")
                for e in para.get("elements", [])
            ).rstrip("\n")
            result.append({
                "text": text,
                "startIndex": el.get("startIndex", 0),
                "endIndex": el.get("endIndex", 0),
                "isList": para.get("bullet") is not None,
            })
    return result


def get_list_items_in_section(paragraphs, section_header, next_header) -> list:
    items = []
    in_section = False
    for para in paragraphs:
        text = para["text"].strip()
        if section_header in text:
            in_section = True
            continue
        if in_section and next_header and next_header in text:
            break
        if in_section and para["isList"]:
            items.append(para)
    return items


def run(tasks: list):
    from googleapiclient.discovery import build

    creds = get_credentials()
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    today = date.today()
    report_date = today.strftime("%d/%m/%Y")
    day_num = max(1, (today - PROJECT_START_DATE).days + 1)

    doc = docs.documents().get(documentId=DOC_ID).execute()
    paragraphs = get_paragraphs(doc)

    # ── 1. Replace date + day count (simple text replace) ─────────────────────
    replace_requests = []
    for para in paragraphs:
        text = para["text"]
        if text.startswith("Report Date:"):
            new = f"Report Date: {report_date}"
            if text != new:
                replace_requests.append(_rep(text, new))
        elif text.startswith("Total Running Days:"):
            new = f"Total Running Days: {day_num} Days"
            if text != new:
                replace_requests.append(_rep(text, new))

    if replace_requests:
        docs.documents().batchUpdate(
            documentId=DOC_ID, body={"requests": replace_requests}
        ).execute()

    # ── 2. Update To-Do list items (re-fetch doc after text replacements) ─────
    doc = docs.documents().get(documentId=DOC_ID).execute()
    paragraphs = get_paragraphs(doc)

    todo_items = get_list_items_in_section(paragraphs, SECTION_TODO, SECTION_COMPLETED)

    # Build index-based requests in REVERSE order (indices shift on edit)
    index_requests = []
    for i, item in reversed(list(enumerate(todo_items))):
        new_text = tasks[i] if i < len(tasks) else ""
        old_text = item["text"].strip()
        start = item["startIndex"]
        end = item["endIndex"]

        if old_text == new_text:
            continue

        if old_text:
            # Delete old text (keep trailing newline at end-1)
            index_requests.append({
                "deleteContentRange": {
                    "range": {"startIndex": start, "endIndex": end - 1}
                }
            })
            if new_text:
                index_requests.append({
                    "insertText": {"location": {"index": start}, "text": new_text}
                })
        elif new_text:
            # Empty list item — insert before newline
            index_requests.append({
                "insertText": {"location": {"index": start}, "text": new_text}
            })

    if index_requests:
        docs.documents().batchUpdate(
            documentId=DOC_ID, body={"requests": index_requests}
        ).execute()

    print(f"✅ Doc updated — {report_date}, Day {day_num}")
    print(f"📋 Tasks: {len(tasks)}")
    for i, t in enumerate(tasks, 1):
        print(f"   {i}. {t}")

    # ── 3. Download PDF ────────────────────────────────────────────────────────
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    pdf_path = DOWNLOADS_DIR / f"CloudGen_Report_{today.strftime('%Y-%m-%d')}.pdf"
    pdf_bytes = drive.files().export(fileId=DOC_ID, mimeType="application/pdf").execute()
    pdf_path.write_bytes(pdf_bytes)
    print(f"📄 PDF: {pdf_path}")

    # ── 4. Save local markdown ─────────────────────────────────────────────────
    WORK_UPDATES_DIR.mkdir(exist_ok=True)
    md_path = WORK_UPDATES_DIR / f"{today.strftime('%Y-%m-%d')}.md"
    lines = [f"# CloudGen Report — {report_date}", f"Day {day_num}", "", "## Tasks", ""]
    for t in tasks:
        lines.append(f"- {t}")
    lines.append("")
    md_path.write_text("\n".join(lines))
    print(f"📝 Saved: {md_path}")


def _rep(old: str, new: str) -> dict:
    return {"replaceAllText": {"containsText": {"text": old, "matchCase": True}, "replaceText": new}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", help="Pipe-separated tasks: 'T1|T2|T3|T4|T5'")
    args = parser.parse_args()

    if args.tasks:
        tasks = [t.strip() for t in args.tasks.split("|")]
    else:
        tasks = read_tasks_from_file()

    if not tasks:
        print("ERROR: No tasks found. Add tasks to task.md")
        sys.exit(1)

    print(f"Running report with {len(tasks)} tasks...")
    run(tasks)


if __name__ == "__main__":
    main()
