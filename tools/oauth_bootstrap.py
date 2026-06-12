"""One-shot Google OAuth bootstrap (run once on Mac).

Reads ./data/credentials.json (downloaded from Google Cloud Console as a
"Desktop app" OAuth client), opens your browser, completes the consent
flow for Gmail + Calendar scopes, and writes ./data/token.json.

After this finishes, the gmail-watcher container reads token.json
(via a shared volume) without ever needing a browser.

Usage:
    python tools/oauth_bootstrap.py
    # add --force to re-auth even if a valid token already exists
    # add --test to verify Gmail + Calendar API access using the saved token
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CREDS = DATA / "credentials.json"
TOKEN = DATA / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",       # read inbox + mark read
    "https://www.googleapis.com/auth/calendar.events",    # create/edit calendar events
]


def load_or_run_flow(force: bool = False) -> Credentials:
    DATA.mkdir(parents=True, exist_ok=True)

    if not CREDS.exists():
        print(f"\n[!] {CREDS} not found.")
        print("    1. Go to https://console.cloud.google.com/apis/credentials")
        print("    2. Create OAuth client ID → Application type: 'Desktop app'")
        print("    3. Download the JSON and save it as: data/credentials.json")
        print("    4. Re-run this script.\n")
        sys.exit(1)

    creds: Credentials | None = None
    if TOKEN.exists() and not force:
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if creds and creds.valid:
        print(f"[ok] existing token at {TOKEN} is valid — nothing to do.")
        return creds

    if creds and creds.expired and creds.refresh_token and not force:
        print("[..] refreshing expired token")
        creds.refresh(Request())
    else:
        print("[..] launching browser for consent flow")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")

    TOKEN.write_text(creds.to_json())
    os.chmod(TOKEN, 0o600)
    print(f"[ok] wrote {TOKEN}")
    return creds


def smoke_test(creds: Credentials) -> None:
    print("\n[..] hitting Gmail API")
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = gmail.users().getProfile(userId="me").execute()
    print(f"[ok] gmail account: {profile.get('emailAddress')} "
          f"({profile.get('messagesTotal')} messages total)")

    print("[..] hitting Calendar API")
    cal = build("calendar", "v3", credentials=creds, cache_discovery=False)
    # calendar.events scope can't list calendars (needs calendar.readonly),
    # but it can list/insert events on the primary calendar — which is what
    # this pipeline actually does.
    events = cal.events().list(calendarId="primary", maxResults=1).execute()
    print(f"[ok] primary calendar reachable: {events.get('summary')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-run consent flow")
    ap.add_argument("--test", action="store_true", help="hit Gmail + Calendar APIs after auth")
    args = ap.parse_args()

    creds = load_or_run_flow(force=args.force)
    if args.test:
        smoke_test(creds)


if __name__ == "__main__":
    main()
