"""Low-level Git operations via subprocess.

Thin wrapper around the git CLI - avoids heavy dependencies like GitPython.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitCommitInfo:
    sha: str
    message: str
    author: str
    date: str


class GitOpsError(Exception):
    """Raised when a git operation fails."""


def _run(
    args: list[str],
    cwd: str | Path,
    env_extra: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitOpsError(f"git command timed out after {timeout}s: {' '.join(args)}") from exc


def _auth_env(auth_type: str, auth_token: str = "", ssh_key_path: str = "") -> dict[str, str]:
    """Build environment variables for git authentication."""
    extra: dict[str, str] = {}
    if auth_type == "ssh_key" and ssh_key_path:
        extra["GIT_SSH_COMMAND"] = f'ssh -i "{ssh_key_path}" -o StrictHostKeyChecking=no'
    elif auth_type == "token" and auth_token:
        # GIT_ASKPASS trick: point to a script that echoes the token
        # We use GIT_TERMINAL_PROMPT=0 and embed creds in the URL instead
        extra["GIT_TERMINAL_PROMPT"] = "0"
    return extra


def _inject_token_into_url(url: str, token: str) -> str:
    """Inject token into HTTPS URL for authentication."""
    if not token or not url.startswith("https://"):
        return url
    # https://github.com/... -> https://oauth2:TOKEN@github.com/...
    return url.replace("https://", f"https://oauth2:{token}@", 1)


def init_repo(
    local_path: str | Path,
    remote_url: str = "",
    branch: str = "main",
    auth_type: str = "token",
    auth_token: str = "",
    ssh_key_path: str = "",
) -> bool:
    """Initialize a new git repo or clone from remote."""
    path = Path(local_path).resolve()
    env = _auth_env(auth_type, auth_token, ssh_key_path)

    if remote_url:
        effective_url = remote_url
        if auth_type == "token" and auth_token:
            effective_url = _inject_token_into_url(remote_url, auth_token)

        # First check if the remote has any commits via ls-remote
        ls_result = _run(
            ["git", "ls-remote", effective_url],
            cwd=path.parent if path.parent.exists() else Path.home(),
            env_extra=env,
            timeout=30,
        )
        remote_has_commits = ls_result.returncode == 0 and bool(ls_result.stdout.strip())

        if remote_has_commits:
            # Clone from non-empty remote
            result = _run(
                ["git", "clone", "--branch", branch, "--single-branch", effective_url, str(path)],
                cwd=path.parent,
                env_extra=env,
                timeout=120,
            )
            if result.returncode != 0:
                # Branch might not exist, try plain clone + create branch
                result2 = _run(
                    ["git", "clone", effective_url, str(path)],
                    cwd=path.parent,
                    env_extra=env,
                    timeout=120,
                )
                if result2.returncode != 0:
                    raise GitOpsError(f"git clone failed: {result2.stderr}")
                _run(["git", "checkout", "-b", branch], cwd=path, env_extra=env)
        else:
            # Empty remote repo (or ls-remote failed) — init locally and add remote
            path.mkdir(parents=True, exist_ok=True)
            _run(["git", "init", "-b", branch], cwd=path)
            _run(["git", "remote", "add", "origin", effective_url], cwd=path, env_extra=env)
            logger.info("Empty remote repo — initialized locally with remote origin")
    else:
        # Local-only repo
        path.mkdir(parents=True, exist_ok=True)
        result = _run(["git", "init", "-b", branch], cwd=path)
        if result.returncode != 0:
            raise GitOpsError(f"git init failed: {result.stderr}")

    # Configure committer identity for this repo
    _run(["git", "config", "user.email", "soas-git-sync@localhost"], cwd=path)
    _run(["git", "config", "user.name", "SOAS Git Sync"], cwd=path)

    logger.info("Git repo initialized at %s", path)
    return True


def pull(
    local_path: str | Path,
    auth_type: str = "token",
    auth_token: str = "",
    ssh_key_path: str = "",
) -> str:
    """Pull from remote. Returns 'up-to-date', 'merged', or 'conflict'."""
    path = Path(local_path)
    env = _auth_env(auth_type, auth_token, ssh_key_path)

    # Rewrite remote URL with token if needed
    if auth_type == "token" and auth_token:
        remote_url = get_remote_url(path)
        if remote_url and "oauth2:" not in remote_url:
            effective_url = _inject_token_into_url(remote_url, auth_token)
            _run(["git", "remote", "set-url", "origin", effective_url], cwd=path, env_extra=env)

    result = _run(["git", "pull", "--rebase", "origin", "HEAD"], cwd=path, env_extra=env, timeout=120)

    if result.returncode != 0:
        stderr = result.stderr.lower()
        if "conflict" in stderr:
            # Abort the rebase to keep things clean
            _run(["git", "rebase", "--abort"], cwd=path, env_extra=env)
            return "conflict"
        if "no remote" in stderr or "no such remote" in stderr:
            return "no-remote"
        raise GitOpsError(f"git pull failed: {result.stderr}")

    if "already up to date" in result.stdout.lower():
        return "up-to-date"
    return "merged"


def commit(local_path: str | Path, message: str) -> str | None:
    """Stage all changes and commit. Returns SHA or None if nothing to commit."""
    path = Path(local_path)

    _run(["git", "add", "-A"], cwd=path)

    # Check if there's anything to commit
    status = _run(["git", "status", "--porcelain"], cwd=path)
    if not status.stdout.strip():
        return None

    result = _run(["git", "commit", "-m", message], cwd=path)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout.lower():
            return None
        raise GitOpsError(f"git commit failed: {result.stderr}")

    # Get the SHA
    sha_result = _run(["git", "rev-parse", "HEAD"], cwd=path)
    return sha_result.stdout.strip() if sha_result.returncode == 0 else None


def push(
    local_path: str | Path,
    auth_type: str = "token",
    auth_token: str = "",
    ssh_key_path: str = "",
) -> bool:
    """Push to remote. Returns True on success."""
    path = Path(local_path)
    env = _auth_env(auth_type, auth_token, ssh_key_path)

    # Rewrite remote URL with token if needed
    if auth_type == "token" and auth_token:
        remote_url = get_remote_url(path)
        if remote_url and "oauth2:" not in remote_url:
            effective_url = _inject_token_into_url(remote_url, auth_token)
            _run(["git", "remote", "set-url", "origin", effective_url], cwd=path, env_extra=env)

    result = _run(["git", "push", "-u", "origin", "HEAD"], cwd=path, env_extra=env, timeout=120)
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if "no such remote" in stderr or "no remote" in stderr:
            logger.info("No remote configured, skipping push")
            return False
        raise GitOpsError(f"git push failed: {result.stderr}")
    return True


def get_remote_url(local_path: str | Path) -> str:
    """Get the remote origin URL."""
    result = _run(["git", "remote", "get-url", "origin"], cwd=local_path)
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    # Strip embedded credentials for display
    if "oauth2:" in url:
        import re
        url = re.sub(r"oauth2:[^@]+@", "", url)
    return url


def get_last_commit(local_path: str | Path) -> GitCommitInfo | None:
    """Get the last commit info."""
    result = _run(
        ["git", "log", "-1", "--format=%H%n%s%n%an%n%aI"],
        cwd=local_path,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    lines = result.stdout.strip().split("\n")
    if len(lines) < 4:
        return None
    return GitCommitInfo(sha=lines[0], message=lines[1], author=lines[2], date=lines[3])


def get_changed_files(local_path: str | Path, since_sha: str = "") -> list[str]:
    """Get list of files changed since a given commit SHA."""
    if since_sha:
        result = _run(["git", "diff", "--name-only", since_sha, "HEAD"], cwd=local_path)
    else:
        result = _run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=local_path)
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


# ---------------------------------------------------------------------------
# Branch management
# ---------------------------------------------------------------------------


def branch_exists(local_path: str | Path, branch_name: str) -> bool:
    """Check whether a local branch exists."""
    result = _run(
        ["git", "branch", "--list", branch_name],
        cwd=local_path,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def create_branch(
    local_path: str | Path,
    branch_name: str,
    from_branch: str = "main",
) -> None:
    """Create a new branch from *from_branch*.  No-op if it already exists."""
    if branch_exists(local_path, branch_name):
        return
    result = _run(["git", "branch", branch_name, from_branch], cwd=local_path)
    if result.returncode != 0:
        raise GitOpsError(f"git branch {branch_name} failed: {result.stderr}")
    logger.info("Created branch %s from %s", branch_name, from_branch)


def delete_branch(local_path: str | Path, branch_name: str) -> None:
    """Delete a local branch.  No-op if it doesn't exist."""
    if not branch_exists(local_path, branch_name):
        return
    result = _run(["git", "branch", "-D", branch_name], cwd=local_path)
    if result.returncode != 0:
        logger.warning("Failed to delete branch %s: %s", branch_name, result.stderr)
    else:
        logger.info("Deleted local branch %s", branch_name)


def delete_remote_branch(
    local_path: str | Path,
    branch_name: str,
    auth_type: str = "token",
    auth_token: str = "",
    ssh_key_path: str = "",
) -> None:
    """Delete a branch from the remote.  No-op on failure."""
    env = _auth_env(auth_type, auth_token, ssh_key_path)
    if auth_type == "token" and auth_token:
        remote_url = get_remote_url(local_path)
        if remote_url and "oauth2:" not in remote_url:
            effective_url = _inject_token_into_url(remote_url, auth_token)
            _run(["git", "remote", "set-url", "origin", effective_url], cwd=local_path, env_extra=env)
    result = _run(
        ["git", "push", "origin", "--delete", branch_name],
        cwd=local_path,
        env_extra=env,
        timeout=30,
    )
    if result.returncode == 0:
        logger.info("Deleted remote branch %s", branch_name)
    else:
        logger.warning("Failed to delete remote branch %s: %s", branch_name, result.stderr)


def list_branches(local_path: str | Path) -> list[str]:
    """Return all local branch names."""
    result = _run(
        ["git", "branch", "--list", "--format=%(refname:short)"],
        cwd=local_path,
    )
    if result.returncode != 0:
        return []
    return [b for b in result.stdout.strip().split("\n") if b]


def current_branch(local_path: str | Path) -> str:
    """Return the currently checked-out branch name."""
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_path)
    return result.stdout.strip() if result.returncode == 0 else ""


# ---------------------------------------------------------------------------
# Worktree management
# ---------------------------------------------------------------------------


def add_worktree(
    repo_path: str | Path,
    worktree_path: str | Path,
    branch_name: str,
) -> None:
    """Create a git worktree for *branch_name* at *worktree_path*.

    The branch must already exist.  If the worktree already exists this is a
    no-op.
    """
    wt = Path(worktree_path)
    if wt.exists() and (wt / ".git").exists():
        return  # worktree already set up
    # Prune stale worktree entries (e.g. after container rebuild removes dirs)
    _run(["git", "worktree", "prune"], cwd=repo_path)
    wt.parent.mkdir(parents=True, exist_ok=True)
    result = _run(
        ["git", "worktree", "add", str(wt), branch_name],
        cwd=repo_path,
    )
    if result.returncode != 0:
        stderr = result.stderr
        if "already checked out" in stderr.lower():
            # worktree might exist at a different path – tolerate
            return
        raise GitOpsError(f"git worktree add failed: {stderr}")
    logger.info("Created worktree at %s for branch %s", wt, branch_name)


def remove_worktree(repo_path: str | Path, worktree_path: str | Path) -> None:
    """Remove a git worktree."""
    result = _run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=repo_path,
    )
    if result.returncode != 0:
        logger.warning("Failed to remove worktree %s: %s", worktree_path, result.stderr)


def list_worktrees(repo_path: str | Path) -> list[dict[str, str]]:
    """List all worktrees.  Returns list of {path, branch, sha}."""
    result = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_path)
    if result.returncode != 0:
        return []
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current["sha"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
    if current:
        worktrees.append(current)
    return worktrees


# ---------------------------------------------------------------------------
# Commit in any path (works for both main repo and worktrees)
# ---------------------------------------------------------------------------


def commit_in_path(path: str | Path, message: str) -> str | None:
    """Stage all changes and commit in *path* (repo or worktree).

    Returns the commit SHA or ``None`` if nothing to commit.
    """
    path = Path(path)
    _run(["git", "add", "-A"], cwd=path)

    status = _run(["git", "status", "--porcelain"], cwd=path)
    if not status.stdout.strip():
        return None

    result = _run(["git", "commit", "-m", message], cwd=path)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout.lower():
            return None
        raise GitOpsError(f"git commit failed: {result.stderr}")

    sha_result = _run(["git", "rev-parse", "HEAD"], cwd=path)
    return sha_result.stdout.strip() if sha_result.returncode == 0 else None


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


@dataclass
class MergeResult:
    status: str  # "merged", "up-to-date", "conflict"
    conflicts: list[str]
    sha: str | None


def merge_branch(
    worktree_path: str | Path,
    source_branch: str,
    message: str,
    strategy_option: str | None = None,
) -> MergeResult:
    """Merge *source_branch* into the branch checked out at *worktree_path*.

    If *strategy_option* is ``"theirs"`` the merge favours the incoming branch
    (force-overwrite semantics).

    Returns a ``MergeResult``.
    """
    wt = Path(worktree_path)
    cmd = ["git", "merge", source_branch, "-m", message]
    if strategy_option:
        cmd.extend(["-X", strategy_option])

    result = _run(cmd, cwd=wt)

    if result.returncode == 0:
        stdout = result.stdout.lower()
        if "already up to date" in stdout:
            return MergeResult(status="up-to-date", conflicts=[], sha=None)
        sha_result = _run(["git", "rev-parse", "HEAD"], cwd=wt)
        sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None
        return MergeResult(status="merged", conflicts=[], sha=sha)

    # Merge failed – likely a conflict
    stderr = result.stderr + result.stdout
    if "conflict" in stderr.lower() or "merge conflict" in stderr.lower():
        # Collect conflicted files
        ls_result = _run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=wt)
        conflicts = [f for f in ls_result.stdout.strip().split("\n") if f]
        # Abort merge to keep worktree clean
        _run(["git", "merge", "--abort"], cwd=wt)
        return MergeResult(status="conflict", conflicts=conflicts, sha=None)

    raise GitOpsError(f"git merge failed: {stderr}")


# ---------------------------------------------------------------------------
# Cross-branch reads and diffs
# ---------------------------------------------------------------------------


def get_file_at_branch(
    repo_path: str | Path,
    branch_name: str,
    file_path: str,
) -> str | None:
    """Read a file's contents at a specific branch without checkout.

    Uses ``git show branch:path``.  Returns ``None`` if the file does not
    exist on that branch.
    """
    result = _run(
        ["git", "show", f"{branch_name}:{file_path}"],
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def diff_branches(
    repo_path: str | Path,
    branch_a: str,
    branch_b: str,
) -> list[str]:
    """List file paths that differ between two branches."""
    result = _run(
        ["git", "diff", "--name-only", branch_a, branch_b],
        cwd=repo_path,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def branch_commit_sha(repo_path: str | Path, branch_name: str) -> str | None:
    """Get the HEAD commit SHA of a branch."""
    result = _run(["git", "rev-parse", branch_name], cwd=repo_path)
    return result.stdout.strip() if result.returncode == 0 else None


def is_repo(local_path: str | Path) -> bool:
    """Check if a path is a git repository."""
    result = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=local_path)
    return result.returncode == 0 and result.stdout.strip() == "true"


def test_remote(
    remote_url: str,
    auth_type: str = "token",
    auth_token: str = "",
    ssh_key_path: str = "",
) -> dict:
    """Test connectivity to a remote git URL. Returns {ok, message}."""
    env = _auth_env(auth_type, auth_token, ssh_key_path)
    effective_url = remote_url
    if auth_type == "token" and auth_token:
        effective_url = _inject_token_into_url(remote_url, auth_token)

    try:
        result = _run(
            ["git", "ls-remote", "--heads", effective_url],
            cwd=Path.home(),
            env_extra=env,
            timeout=30,
        )
        if result.returncode == 0:
            branches = [
                line.split("\t")[-1].replace("refs/heads/", "")
                for line in result.stdout.strip().split("\n")
                if line
            ]
            return {"ok": True, "message": f"Connected. Branches: {', '.join(branches) or 'empty repo'}"}
        return {"ok": False, "message": result.stderr.strip()}
    except GitOpsError as exc:
        return {"ok": False, "message": str(exc)}
