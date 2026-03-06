"""GitHub API service for PR management in the change request workflow."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _parse_github_repo(remote_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub remote URL.

    Supports HTTPS and SSH formats:
      https://github.com/owner/repo.git
      git@github.com:owner/repo.git
    """
    # HTTPS
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", remote_url)
    if m:
        return m.group(1), m.group(2)
    # SSH
    m = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if m:
        return m.group(1), m.group(2)
    # Token-injected HTTPS  (https://oauth2:TOKEN@github.com/owner/repo.git)
    m = re.match(r"https?://[^@]+@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", remote_url)
    if m:
        return m.group(1), m.group(2)
    return None


async def _github_request(
    method: str,
    path: str,
    token: str,
    body: dict | None = None,
) -> dict:
    """Make an authenticated request to the GitHub REST API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


async def create_pull_request(
    remote_url: str,
    auth_token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> dict | None:
    """Create a GitHub Pull Request.

    Returns a dict with keys: number, html_url, title.
    Returns None if repo is not on GitHub or creation fails.
    """
    parsed = _parse_github_repo(remote_url)
    if not parsed:
        logger.info("Remote URL is not GitHub, skipping PR creation: %s", remote_url)
        return None

    owner, repo = parsed
    try:
        data = await _github_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            auth_token,
            {
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
        )
        return {
            "number": data["number"],
            "html_url": data["html_url"],
            "title": data["title"],
        }
    except httpx.HTTPStatusError as exc:
        # 422 often means PR already exists for this head/base combo
        if exc.response.status_code == 422:
            logger.info("PR may already exist for %s → %s: %s", head_branch, base_branch, exc)
            # Try to find the existing PR
            try:
                existing = await _github_request(
                    "GET",
                    f"/repos/{owner}/{repo}/pulls?head={owner}:{head_branch}&base={base_branch}&state=open",
                    auth_token,
                )
                if existing:
                    pr = existing[0]
                    return {
                        "number": pr["number"],
                        "html_url": pr["html_url"],
                        "title": pr["title"],
                    }
            except Exception:
                logger.warning("Failed to find existing PR", exc_info=True)
        logger.warning("GitHub PR creation failed: %s", exc, exc_info=True)
        return None
    except Exception:
        logger.warning("GitHub PR creation failed", exc_info=True)
        return None


async def merge_pull_request(
    remote_url: str,
    auth_token: str,
    pr_number: int,
    merge_method: str = "merge",
) -> bool:
    """Merge a GitHub Pull Request.

    merge_method: "merge", "squash", or "rebase".
    Returns True on success.
    """
    parsed = _parse_github_repo(remote_url)
    if not parsed:
        return False

    owner, repo = parsed
    try:
        await _github_request(
            "PUT",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            auth_token,
            {"merge_method": merge_method},
        )
        return True
    except httpx.HTTPStatusError as exc:
        # 405 = not mergeable, 409 = conflict
        logger.warning("GitHub PR merge failed (status %s): %s", exc.response.status_code, exc)
        return False
    except Exception:
        logger.warning("GitHub PR merge failed", exc_info=True)
        return False


async def close_pull_request(
    remote_url: str,
    auth_token: str,
    pr_number: int,
) -> bool:
    """Close a GitHub Pull Request without merging."""
    parsed = _parse_github_repo(remote_url)
    if not parsed:
        return False

    owner, repo = parsed
    try:
        await _github_request(
            "PATCH",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            auth_token,
            {"state": "closed"},
        )
        return True
    except Exception:
        logger.warning("GitHub PR close failed", exc_info=True)
        return False


async def add_pr_comment(
    remote_url: str,
    auth_token: str,
    pr_number: int,
    body: str,
) -> bool:
    """Add a comment to a GitHub Pull Request."""
    parsed = _parse_github_repo(remote_url)
    if not parsed:
        return False

    owner, repo = parsed
    try:
        await _github_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            auth_token,
            {"body": body},
        )
        return True
    except Exception:
        logger.warning("GitHub PR comment failed", exc_info=True)
        return False


def extract_pr_number(pr_url: str) -> int | None:
    """Extract PR number from a GitHub PR URL like https://github.com/owner/repo/pull/42."""
    m = re.search(r"/pull/(\d+)", pr_url)
    return int(m.group(1)) if m else None
