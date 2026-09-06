#!/usr/bin/env python3
"""Create a YouTube OAuth refresh token for GitHub Actions."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _read_env_file(path: Path) -> dict[str, str]:
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def _value(explicit: str | None, env: dict[str, str], *names: str) -> str | None:
    if explicit:
        return explicit
    for name in names:
        value = os.getenv(name) or env.get(name)
        if value:
            return value
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local Google OAuth flow and print a YouTube refresh token."
    )
    parser.add_argument(
        "--client-secrets",
        type=Path,
        help="OAuth client JSON downloaded from Google Cloud (recommended).",
    )
    parser.add_argument("--client-id", help="OAuth client ID; falls back to YOUTUBE_CLIENT_ID.")
    parser.add_argument(
        "--client-secret", help="OAuth client secret; falls back to YOUTUBE_CLIENT_SECRET."
    )
    parser.add_argument(
        "--env-file", type=Path, default=Path(".env"), help="dotenv file to use (default: .env)."
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Local callback port (default: 8080)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = _read_env_file(args.env_file) if args.env_file.is_file() else {}
    client_id = _value(args.client_id, env, "YOUTUBE_CLIENT_ID")
    client_secret = _value(args.client_secret, env, "YOUTUBE_CLIENT_SECRET")

    if args.client_secrets:
        if not args.client_secrets.is_file():
            raise SystemExit(f"Client secrets file not found: {args.client_secrets}")
        flow = InstalledAppFlow.from_client_secrets_file(str(args.client_secrets), SCOPES)
    elif client_id and client_secret:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            SCOPES,
        )
    else:
        raise SystemExit(
            "Provide --client-secrets, or set --client-id/--client-secret "
            "(or YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET in .env)."
        )

    print("A browser window will open for YouTube authorization.")
    credentials = flow.run_local_server(
        host="localhost", port=args.port, access_type="offline", prompt="consent"
    )
    print("\nOAuth completed successfully. Your refresh token is:\n")
    print(credentials.refresh_token)
    print("\nAdd these values to GitHub repository Secrets:")
    print("  YOUTUBE_CLIENT_ID       = your OAuth client ID")
    print("  YOUTUBE_CLIENT_SECRET   = your OAuth client secret")
    print("  YOUTUBE_REFRESH_TOKEN   = the refresh token printed above")
    print("\nGitHub path: Settings > Secrets and variables > Actions")
    print("> New repository secret.")


if __name__ == "__main__":
    main()
