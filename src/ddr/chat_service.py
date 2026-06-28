"""Google Chat — sends real report content (fixes L2, H5)."""

from datetime import date

import requests as http

from . import config
from .google_auth import get_credentials


def build_message(tasks: list[str], doc_url: str, pdf_link: str, day_num: int) -> str:
    today = date.today().strftime("%d/%m/%Y")
    task_lines = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(tasks))
    lines = [
        f"*📋 {config.COMPANY_NAME} Daily Report — {today} (Day {day_num})*",
        f"*Developer:* {config.DEVELOPER_NAME} | {config.DEVELOPER_ROLE}",
        f"*Project:* {config.PROJECT_NAME}",
        "",
        "*Today's Tasks:*",
        task_lines,
        "",
        f"📄 <{pdf_link}|Download PDF>  |  📝 <{doc_url}|View Doc>",
    ]
    return "\n".join(lines)


def send_to_chat(message: str) -> dict:
    if not config.SPACE_NAME:
        raise ValueError(
            "GOOGLE_CHAT_SPACE not set in .env\n"
            "Format: spaces/YOUR_SPACE_ID"
        )

    creds = get_credentials()
    url = f"https://chat.googleapis.com/v1/{config.SPACE_NAME}/messages"
    resp = http.post(
        url,
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
        json={"text": message},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
