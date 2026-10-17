#!/usr/bin/env python3
"""Refresh the auto-updated sections of README.md.

Fills three marker blocks:
  RECENT_REPOS    - 5 most recently pushed public, non-fork repos
  RECENT_ACTIVITY - 5 most recent public events
  UPDATED         - timestamp (IST)

Uses only the standard library. Set GITHUB_TOKEN to avoid rate limits.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "harshal1996sahadeokar")
README = os.environ.get("README_PATH", "README.md")
IST = timezone(timedelta(hours=5, minutes=30))


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def replace_block(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        print(f"warning: marker {name} not found", file=sys.stderr)
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def recent_repos():
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=30&type=owner")
    # skip forks, archived repos and the profile repo itself
    repos = [r for r in repos if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()]
    lines = ["### Recently pushed", "", "| Repo | What | Lang | Updated |", "|---|---|---|---|"]
    for r in repos[:5]:
        desc = (r["description"] or "—").replace("|", "/")
        lang = r["language"] or "—"
        updated = r["pushed_at"][:10]
        lines.append(f"| [{r['name']}]({r['html_url']}) | {desc} | {lang} | {updated} |")
    if len(lines) == 4:
        lines.append("| _No public repos yet_ | | | |")
    return "\n".join(lines)


def describe(event):
    repo = event["repo"]["name"]
    link = f"[{repo}](https://github.com/{repo})"
    kind = event["type"]
    payload = event.get("payload", {})
    if kind == "PushEvent":
        n = len(payload.get("commits", [])) or payload.get("size", 1)
        return f"Pushed {n} commit{'s' if n != 1 else ''} to {link}"
    if kind == "PullRequestEvent":
        return f"{payload.get('action', 'updated').capitalize()} a PR in {link}"
    if kind == "IssuesEvent":
        return f"{payload.get('action', 'updated').capitalize()} an issue in {link}"
    if kind == "CreateEvent":
        return f"Created {payload.get('ref_type', 'repo')} in {link}"
    if kind == "ReleaseEvent":
        return f"Published a release in {link}"
    return None


def recent_activity():
    events = api(f"/users/{USER}/events/public?per_page=50")
    lines = ["### Recent activity", ""]
    seen = set()
    for e in events:
        text = describe(e)
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(f"- {text} · {e['created_at'][:10]}")
        if len(seen) == 5:
            break
    if len(lines) == 2:
        lines.append("- _No recent public activity_")
    return "\n".join(lines)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = replace_block(text, "RECENT_REPOS", recent_repos())
    text = replace_block(text, "RECENT_ACTIVITY", recent_activity())
    stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    text = replace_block(text, "UPDATED", stamp).replace(
        f"<!-- UPDATED:START -->\n{stamp}\n<!-- UPDATED:END -->",
        f"<!-- UPDATED:START -->{stamp}<!-- UPDATED:END -->",
    )
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print("README updated")


if __name__ == "__main__":
    main()
