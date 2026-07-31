#!/usr/bin/env python3
"""Push to GitHub using stored token.
Reads token from .github_token file (not in git repo).
Usage: python scripts/push.py"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TOKEN_FILE = os.path.expanduser("~/.github_token")


def main():
    if not os.path.exists(TOKEN_FILE):
        print(f"ERROR: Token file not found: {TOKEN_FILE}")
        print(f"Create it with: echo ghp_YOUR_TOKEN > {TOKEN_FILE}")
        sys.exit(1)

    token = open(TOKEN_FILE, "r").read().strip()
    remote_url = f"https://{token}@github.com/17mohammad1718-png/jajiga-tracker.git"

    # Set remote with token
    subprocess.run(
        ["git", "remote", "set-url", "origin", remote_url],
        cwd=PROJECT_ROOT, check=True,
    )

    # Push
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr, end="")

    # Clean remote
    subprocess.run(
        ["git", "remote", "set-url", "origin",
         "https://github.com/17mohammad1718-png/jajiga-tracker.git"],
        cwd=PROJECT_ROOT, check=True,
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
