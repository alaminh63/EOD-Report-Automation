"""Unified Google OAuth — single token, full scope set, safe refresh."""

from . import config


def get_credentials():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not config.CREDS_FILE.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {config.CREDS_FILE}\n"
            "Complete Step 2 in SETUP.md to create Google OAuth credentials."
        )

    creds = None
    if config.TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(config.TOKEN_FILE), config.SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                config.TOKEN_FILE.unlink(missing_ok=True)
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.CREDS_FILE), config.SCOPES
            )
            creds = flow.run_local_server(port=0)

        config.TOKEN_FILE.write_text(creds.to_json())

    return creds
