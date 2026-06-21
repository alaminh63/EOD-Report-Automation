#!/usr/bin/env python3
"""
Send daily PDF report to Google Chat space.

Usage:
    python3 send_chat.py              # sends today's PDF
    python3 send_chat.py --preview    # show message without sending
    python3 send_chat.py --pdf /path/to/file.pdf
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

SUMMARY_FILE = ROOT_DIR / "data" / "summary.md"
TOKEN_FILE = ROOT_DIR / "config" / "token.json"
CREDS_FILE = ROOT_DIR / "config" / "credentials.json"
DOWNLOADS_DIR = Path.home() / "Downloads"
SPACE_NAME = os.getenv("GOOGLE_CHAT_SPACE", "spaces/AAQAmsfYrL8")

SCOPES = [
    "https://www.googleapis.com/auth/chat.messages.create",
    "https://www.googleapis.com/auth/chat.import",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


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
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def find_today_pdf() -> Path | None:
    today = date.today().strftime("%Y-%m-%d")
    pdf = DOWNLOADS_DIR / f"CloudGen_Report_{today}.pdf"
    return pdf if pdf.exists() else None


def build_caption() -> str:
    return "*Status Update*"


def upload_to_drive_and_send(pdf_path: Path, caption: str):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    # Upload PDF to Drive
    print("Uploading PDF to Google Drive...")
    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf")
    file_meta = {"name": pdf_path.name}
    uploaded = drive.files().create(body=file_meta, media_body=media, fields="id,webViewLink").execute()
    file_id = uploaded.get("id")
    link = uploaded.get("webViewLink")

    # Make publicly readable (anyone with link)
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    print(f"✅ Uploaded: {link}")

    # Send message with link to Chat
    token = creds.token
    message = f"{caption}\n{link}"
    send_text_only(message, token)


def send_text_only(text: str, token: str):
    url = f"https://chat.googleapis.com/v1/{SPACE_NAME}/messages"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"text": text},
    )
    if resp.status_code in (200, 201):
        print("✅ Text message sent")
    else:
        print(f"❌ Failed: {resp.status_code} — {resp.text}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", help="PDF file path (default: today's report)")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf) if args.pdf else find_today_pdf()
    caption = build_caption()

    if args.preview:
        print("── Caption ──")
        print(caption)
        print("── PDF ──")
        print(pdf_path or "⚠️  No PDF found — run ./report first")
        return

    if not pdf_path or not pdf_path.exists():
        print("⚠️  No PDF found. Run ./report first to generate it.")
        print("Sending text only...")
        creds = get_credentials()
        send_text_only(caption, creds.token)
        return

    print(f"Sending {pdf_path.name} to Google Chat...")
    upload_to_drive_and_send(pdf_path, caption)


if __name__ == "__main__":
    main()
