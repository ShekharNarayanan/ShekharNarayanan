import os
import re
import sys
from datetime import datetime, timezone, date

import requests

README_PATH = "README.md"

# Only match GitHub repo URLs. GitLab links are ignored automatically.
RE_GH = re.compile(r"https?://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)(?:/)?(?:\s|$)")

# Idempotency: remove any prior prefix/suffix we added.
RE_PREFIX = re.compile(r"^\s*(?:🟢|🟡|⚪)\s+")
RE_SUFFIX = re.compile(r"\s*\(last updated: [^)]+\)\s*$", re.IGNORECASE)

def days_ago_label(days: int) -> str:
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days}d ago"

def emoji_for_days(days: int) -> str:
    if days <= 7:
        return "🟢"
    if days <= 15:
        return "🟡"
    return "⚪"

def get_pushed_at(owner: str, repo: str, token: str) -> datetime | None:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()

    pushed_at = r.json().get("pushed_at")
    if not pushed_at:
        return None
    return datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).astimezone(timezone.utc)

def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("Missing GITHUB_TOKEN env var (expected in GitHub Actions).", file=sys.stderr)
        return 2

    if not os.path.exists(README_PATH):
        print(f"README not found at {README_PATH}", file=sys.stderr)
        return 2

    with open(README_PATH, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    today = date.today()
    updated_lines = []
    changed = False

    for line in lines:
        m = RE_GH.search(line)
        if not m:
            updated_lines.append(line)
            continue

        owner, repo = m.group(1), m.group(2)

        base = RE_PREFIX.sub("", line)
        base = RE_SUFFIX.sub("", base).rstrip()

        try:
            pushed = get_pushed_at(owner, repo, token)
        except requests.HTTPError:
            new_line = f"⚪ {base} (last updated: unknown)".rstrip()
            updated_lines.append(new_line)
            if new_line != line.rstrip():
                changed = True
            continue

        if pushed is None:
            new_line = f"⚪ {base} (last updated: unknown)".rstrip()
            updated_lines.append(new_line)
            if new_line != line.rstrip():
                changed = True
            continue

        days = (today - pushed.date()).days
        new_line = f"{emoji_for_days(days)} {base} (last updated: {days_ago_label(days)})".rstrip()
        updated_lines.append(new_line)

        if new_line != line.rstrip():
            changed = True

    if changed:
        with open(README_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(updated_lines) + "\n")
        print("README updated.")
    else:
        print("No README changes needed.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())