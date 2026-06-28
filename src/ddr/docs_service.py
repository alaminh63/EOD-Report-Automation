"""Google Docs update — fixed index math, apostrophe-agnostic, variable task count."""

import unicodedata
from datetime import date

from . import config
from .google_auth import get_credentials


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).replace("’", "'").replace("‘", "'")


def get_paragraphs(doc: dict) -> list[dict]:
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
                "elements": para.get("elements", []),
            })
    return result


def find_section_items(paragraphs: list[dict], header: str, stop_header: str) -> list[dict]:
    norm_header = _normalize(header)
    norm_stop = _normalize(stop_header)
    items = []
    in_section = False
    for para in paragraphs:
        norm_text = _normalize(para["text"].strip())
        if norm_header in norm_text:
            in_section = True
            continue
        if in_section and norm_stop and norm_stop in norm_text:
            break
        if in_section and para["isList"]:
            items.append(para)
    return items


def _rep(old: str, new: str) -> dict:
    return {
        "replaceAllText": {
            "containsText": {"text": old, "matchCase": True},
            "replaceText": new,
        }
    }


def update_doc(tasks: list[str]) -> dict:
    """Update Doc date, day count, task list. Returns doc metadata."""
    from googleapiclient.discovery import build

    if not tasks:
        raise ValueError("tasks list is empty")

    creds = get_credentials()
    docs = build("docs", "v1", credentials=creds)

    today = date.today()
    report_date = today.strftime("%d/%m/%Y")
    day_num = config.calendar_day_number()

    doc = docs.documents().get(documentId=config.DOC_ID).execute()
    paragraphs = get_paragraphs(doc)

    # ── 1. Replace date + day count ─────────────────────────────────────────
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
            documentId=config.DOC_ID, body={"requests": replace_requests}
        ).execute()

    # ── 2. Re-fetch and update task list ────────────────────────────────────
    doc = docs.documents().get(documentId=config.DOC_ID).execute()
    paragraphs = get_paragraphs(doc)

    todo_items = find_section_items(
        paragraphs, config.SECTION_TODO, config.SECTION_COMPLETED
    )
    if not todo_items:
        todo_items = find_section_items(
            paragraphs, config.SECTION_TODO_ALT, config.SECTION_COMPLETED
        )
    if not todo_items:
        raise RuntimeError(
            f"Section '{config.SECTION_TODO}' not found in Doc. "
            "Doc structure may have changed."
        )

    index_requests = _build_sync_requests(todo_items, tasks)
    if index_requests:
        docs.documents().batchUpdate(
            documentId=config.DOC_ID, body={"requests": index_requests}
        ).execute()

    doc_url = f"https://docs.google.com/document/d/{config.DOC_ID}/edit"
    return {"doc_url": doc_url, "report_date": report_date, "day_num": day_num}


def _text_end_index(item: dict) -> int:
    """Get the end index of text content (excludes trailing newline/bullet chars)."""
    start = item["startIndex"]
    for el in reversed(item["elements"]):
        if "textRun" in el:
            content = el["textRun"].get("content", "")
            stripped_len = len(content.rstrip("\n"))
            if stripped_len:
                # endIndex of this element minus what we stripped
                el_end = el.get("endIndex", start)
                return el_end - (len(content) - stripped_len)
    return start


def _build_sync_requests(todo_items: list[dict], tasks: list[str]) -> list[dict]:
    """Sync bullet list to match tasks. Processes in reverse to preserve indices."""
    requests = []
    existing_count = len(todo_items)
    task_count = len(tasks)

    # Delete extra bullets (more existing than tasks) — reverse order
    if existing_count > task_count:
        for item in reversed(todo_items[task_count:]):
            requests.append({
                "deleteContentRange": {
                    "range": {
                        "startIndex": item["startIndex"],
                        "endIndex": item["endIndex"],
                    }
                }
            })

    # Update existing items (up to min of both counts) — reverse order
    update_count = min(existing_count, task_count)
    for i in reversed(range(update_count)):
        item = todo_items[i]
        new_text = tasks[i]
        old_text = item["text"].strip()
        if old_text == new_text:
            continue

        text_end = _text_end_index(item)
        start = item["startIndex"]

        if old_text:
            requests.append({
                "deleteContentRange": {
                    "range": {"startIndex": start, "endIndex": text_end}
                }
            })
        if new_text:
            requests.append({
                "insertText": {
                    "location": {"index": start},
                    "text": new_text
                }
            })

    # Append new bullets if more tasks than existing
    # Note: insertions after deletes — indices already adjusted by reverse processing
    if task_count > existing_count and todo_items:
        last_end = todo_items[-1]["endIndex"]
        for i in range(existing_count, task_count):
            new_text = tasks[i]
            requests.append({
                "insertText": {
                    "location": {"index": last_end},
                    "text": f"{new_text}\n"
                }
            })
            requests.append({
                "createParagraphBullets": {
                    "range": {
                        "startIndex": last_end,
                        "endIndex": last_end + len(new_text) + 1
                    },
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                }
            })
            last_end += len(new_text) + 1

    return requests
