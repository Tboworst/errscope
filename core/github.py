import os
import requests

GITHUB_API = "https://api.github.com"


def github_configured():
    return bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPO"))


def _headers():
    return {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def create_issue(fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen, service, environment):
    """
    Open a GitHub issue for an error group.
    Returns (issue_number, issue_url) on success, raises on failure.
    """
    repo = os.environ.get("GITHUB_REPO")
    if not repo or not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPO must be set")

    chain_lines = "\n  ".join(fn_chain.split("->"))
    title_msg = norm_msg[:60] + ("…" if len(norm_msg) > 60 else "")
    title = f"[{service}] {exc_type}: {title_msg}"

    body = f"""## Error Group

**Exception**: `{exc_type}`
**Service**: `{service}`
**Environment**: `{environment}`
**Occurrences**: {count}
**First seen**: {first_seen}
**Last seen**: {last_seen}

## Message

```
{norm_msg}
```

## Call Chain

```
{chain_lines}
```

---
*Tracked by Beacon · Fingerprint: `{fp}`*
"""

    resp = requests.post(
        f"{GITHUB_API}/repos/{repo}/issues",
        json={"title": title, "body": body, "labels": ["bug", "beacon"]},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["number"], data["html_url"]


def close_issue(issue_number):
    """Close a GitHub issue by number. No-ops if not configured."""
    repo = os.environ.get("GITHUB_REPO")
    if not repo or not os.environ.get("GITHUB_TOKEN"):
        return
    resp = requests.patch(
        f"{GITHUB_API}/repos/{repo}/issues/{issue_number}",
        json={"state": "closed"},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
