"""Run this script to authenticate Rapport with your Gmail account.

A browser window will open. Log in with your Google account and grant
Gmail readonly access. The token is cached to ~/.rapport/gmail_token.json.
You only need to do this once — tokens auto-refresh thereafter.
"""

import sys
from pathlib import Path

# Ensure python-sidecar is on the path
sys.path.insert(0, str(Path(__file__).parent))

from gmail_reader import _get_gmail_service

print("Opening browser for Gmail OAuth...")
service = _get_gmail_service()

if service:
    profile = service.users().getProfile(userId="me").execute()
    print(f"\n Authenticated as: {profile.get('emailAddress')}")
    print("Token saved to ~/.rapport/gmail_token.json")
else:
    print("\n Auth failed. Check that credentials.json is in python-sidecar/")
