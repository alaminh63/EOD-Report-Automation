"""Drive PDF export + upload."""

from datetime import date
from pathlib import Path

from . import config
from .google_auth import get_credentials


def export_pdf(save_path: Path | None = None) -> Path:
    """Export Google Doc as PDF. Returns local file path."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    today = date.today().strftime("%Y-%m-%d")
    pdf_path = save_path or (config.DOWNLOADS_DIR / f"CloudGen_Report_{today}.pdf")

    config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_bytes = drive.files().export(
        fileId=config.DOC_ID, mimeType="application/pdf"
    ).execute()
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def upload_pdf(pdf_path: Path) -> str:
    """Upload PDF to Drive and return shareable link."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf")
    uploaded = drive.files().create(
        body={"name": pdf_path.name},
        media_body=media,
        fields="id,webViewLink"
    ).execute()

    file_id = uploaded.get("id")
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return uploaded.get("webViewLink", "")
