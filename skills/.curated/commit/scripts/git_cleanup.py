#!/usr/bin/env python3
"""Inspect, verify scoped closeout, and delete Git state with fingerprint guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


STASH_SELECTOR = re.compile(r"^stash@\{\d+\}$")
GIT_STATE_PATHS = {
    "merge": "MERGE_HEAD",
    "rebase-merge": "rebase-merge",
    "rebase-apply": "rebase-apply",
    "cherry-pick": "CHERRY_PICK_HEAD",
    "revert": "REVERT_HEAD",
    "bisect": "BISECT_LOG",
}


class CleanupError(RuntimeError):
    pass


def git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise CleanupError(message or f"git {' '.join(args)} failed")
    return result


def text(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stdout.decode("utf-8", "surrogateescape").strip()


def repo_top(path: str) -> Path:
    candidate = Path(path).expanduser().resolve()
    return Path(text(git(candidate, "rev-parse", "--show-toplevel"))).resolve()


def head_sha(worktree: Path) -> str:
    result = git(worktree, "rev-parse", "--verify", "HEAD", check=False)
    return text(result) if result.returncode == 0 else "UNBORN"


def current_branch(worktree: Path) -> str | None:
    result = git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return text(result) if result.returncode == 0 else None


def operation_states(worktree: Path) -> list[str]:
    active = []
    for name, git_path in GIT_STATE_PATHS.items():
        result = git(worktree, "rev-parse", "--git-path", git_path)
        state_path = Path(text(result))
        if not state_path.is_absolute():
            state_path = (worktree / state_path).resolve()
        if state_path.exists():
            active.append(name)
    return active


def status_bytes(worktree: Path) -> bytes:
    return git(
        worktree,
        "status",
        "--porcelain=v2",
        "-z",
        "--branch",
        "--untracked-files=all",
        "--ignored=matching",
    ).stdout


def status_fingerprint(worktree: Path) -> str:
    digest = hashlib.sha256()
    digest.update(head_sha(worktree).encode())
    digest.update(b"\0")
    digest.update(status_bytes(worktree))
    digest.update(git(worktree, "diff", "--binary").stdout)
    digest.update(git(worktree, "diff", "--cached", "--binary").stdout)
    for args in (
        ("ls-files", "--others", "--exclude-standard", "-z"),
        ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
    ):
        paths = git(worktree, *args).stdout
        digest.update(paths)
        for raw_path in paths.split(b"\0"):
            if not raw_path:
                continue
            item = worktree / raw_path.decode("utf-8", "surrogateescape")
            if os.path.lexists(item):
                stat = item.lstat()
                digest.update(f"\0{stat.st_mode}\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
    for name in operation_states(worktree):
        digest.update(b"\0op:")
        digest.update(name.encode())
    return digest.hexdigest()


def parse_worktrees(repo: Path) -> list[dict[str, str | None]]:
    raw = git(repo, "worktree", "list", "--porcelain", "-z").stdout
    records: list[dict[str, str | None]] = []
    current: dict[str, str | None] = {}
    for field in raw.split(b"\0"):
        if not field:
            if current:
                records.append(current)
                current = {}
            continue
        decoded = field.decode("utf-8", "surrogateescape")
        key, _, value = decoded.partition(" ")
        current[key] = value or None
    if current:
        records.append(current)
    return records


def temp_roots() -> list[Path]:
    roots: set[Path] = set()
    for raw_path in (os.environ.get("TMPDIR"), tempfile.gettempdir(), "/tmp", "/private/tmp"):
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            roots.add(path)
    return sorted(roots, key=str)


def external_task_path_reason(repo: Path, path: Path) -> str | None:
    if path.parent.resolve() not in temp_roots():
        return None
    prefixes = (f"{repo.name}-", f"codex-{repo.name}-")
    if path.name.startswith(prefixes):
        return "repository-named system temporary path"
    return None


def task_path_kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    return "file"


def discover_task_paths(repo: Path) -> list[dict[str, str]]:
    candidates: dict[str, dict[str, str]] = {}

    def add(path: Path, reason: str) -> None:
        absolute = Path(os.path.abspath(path))
        if absolute == repo or not os.path.lexists(absolute):
            return
        candidates[str(absolute)] = {
            "path": str(absolute),
            "kind": task_path_kind(absolute),
            "reason": reason,
        }

    for root, reason in (
        (repo / ".codex" / "tmp", "Codex task temporary artifact"),
        (repo / ".claude" / "worktrees", "Claude task worktree artifact"),
    ):
        if root.is_dir():
            for child in sorted(root.iterdir(), key=lambda value: value.name):
                add(child, reason)

    for root in temp_roots():
        for child in root.iterdir():
            reason = external_task_path_reason(repo, child)
            if reason:
                add(child, reason)

    return [candidates[path] for path in sorted(candidates)]


def history_evidence(repo: Path, head: str, target_sha: str) -> dict[str, object]:
    """Commit reachability only; squash equivalence and cleanup permission are caller facts."""
    if head == "UNBORN":
        return {"head_in_target": None, "unique_commits": None}
    reachable = git(repo, "merge-base", "--is-ancestor", head, target_sha, check=False)
    if reachable.returncode not in (0, 1):
        raise CleanupError(text(reachable) or reachable.stderr.decode("utf-8", "replace").strip())
    unique = text(git(repo, "rev-list", f"{target_sha}..{head}")).splitlines()
    return {"head_in_target": reachable.returncode == 0, "unique_commits": unique}


def inspect_repo(repo: Path, target: str | None = None) -> dict[str, object]:
    target_sha = None
    if target is not None:
        result = git(repo, "rev-parse", "--verify", "--end-of-options", f"{target}^{{commit}}", check=False)
        if result.returncode:
            raise CleanupError(f"audit target does not resolve to a commit: {target}")
        target_sha = text(result)
    worktrees = []
    for entry in parse_worktrees(repo):
        path = Path(str(entry["worktree"])).resolve()
        if path.is_dir():
            item = {
                "path": str(path),
                "head": head_sha(path),
                "branch": current_branch(path),
                "operations": operation_states(path),
                "status_fingerprint": status_fingerprint(path),
                "status": status_bytes(path).decode("utf-8", "backslashreplace"),
                "dirty": bool(git(path, "status", "--porcelain", "--untracked-files=all").stdout),
                "has_ignored": bool(git(path, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").stdout),
            }
        else:
            item = {
                "path": str(path), "head": entry.get("HEAD") or "UNBORN",
                "branch": str(entry["branch"]).removeprefix("refs/heads/") if entry.get("branch") else None,
                "operations": [], "status_fingerprint": None, "status": None,
                "dirty": None, "has_ignored": None, "inspection_error": "registered worktree directory is missing",
            }
        if target_sha:
            item["history"] = history_evidence(repo, str(item["head"]), target_sha)
        worktrees.append(item)

    branches = []
    raw_branches = text(
        git(repo, "for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/heads")
    )
    for line in raw_branches.splitlines():
        if line:
            name, sha = line.split("\t", 1)
            item = {"name": name, "sha": sha}
            if target_sha:
                item["history"] = history_evidence(repo, sha, target_sha)
            branches.append(item)

    stashes = []
    raw_stashes = text(git(repo, "stash", "list", "--format=%gd\t%H\t%gs"))
    for line in raw_stashes.splitlines():
        if line:
            selector, sha, subject = line.split("\t", 2)
            stashes.append({"selector": selector, "sha": sha, "subject": subject})

    state = {
        "repo": str(repo),
        "current_branch": current_branch(repo),
        "branches": branches,
        "stashes": stashes,
        "worktrees": worktrees,
        "task_path_candidates": discover_task_paths(repo),
    }
    if target_sha:
        state["delivery_audit"] = {
            "target": target,
            "target_sha": target_sha,
            "evidence": "local Git commit reachability at the recorded target SHA; no fetch or platform query",
            "not_proven": [
                "platform PR/MR merge status", "squash/rebase patch equivalence",
                "live remote refs or target freshness", "task ownership or active owner",
                "delivery of uncommitted or ignored content", "deletion authorization or safety",
            ],
        }
    return state


def verify_closeout(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    state = inspect_repo(repo)
    errors: list[str] = []

    branches = [str(item["name"]) for item in state["branches"]]
    if branches != [args.target]:
        errors.append(
            f"local branches must be exactly [{args.target}], found {branches}"
        )

    if state["current_branch"] != args.target:
        errors.append(
            f"current branch must be {args.target}, found {state['current_branch']}"
        )

    stashes = state["stashes"]
    if stashes:
        errors.append(f"stash must be empty, found {len(stashes)} entries")

    worktrees = state["worktrees"]
    if len(worktrees) != 1:
        errors.append(f"exactly one worktree is required, found {len(worktrees)}")

    operations: list[str] = []
    for worktree in worktrees:
        path = str(worktree["path"])
        for operation in worktree["operations"]:
            operations.append(f"{path}:{operation}")
    if operations:
        errors.append(f"Git operations still in progress: {operations}")

    pending = text(
        git(
            repo,
            "status",
            "--porcelain=v2",
            "--untracked-files=all",
        )
    )
    if pending:
        errors.append("tracked or non-ignored untracked worktree content remains")

    task_paths = state["task_path_candidates"]
    if task_paths:
        errors.append(
            "task path candidates must be deleted or classified as a blocking active/unique path: "
            + json.dumps([item["path"] for item in task_paths], ensure_ascii=False)
        )

    if errors:
        raise CleanupError(
            "closeout invariant failed: "
            + json.dumps(errors, ensure_ascii=False)
        )

    print(
        json.dumps(
            {
                "verified": True,
                "repo": str(repo),
                "target": args.target,
                "local_branches": branches,
                "stash_count": 0,
                "worktree_count": 1,
                "worktree_clean": True,
                "task_path_candidate_count": 0,
            },
            ensure_ascii=False,
        )
    )


def read_scope_manifest(repo: Path, manifest_path: str) -> dict[str, object]:
    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CleanupError(f"duplicate manifest key: {key}")
            result[key] = value
        return result

    try:
        scope = json.loads(
            Path(manifest_path).expanduser().read_text(encoding="utf-8"),
            object_pairs_hook=unique_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CleanupError(f"cannot read scope manifest: {exc}") from exc
    required = {"version", "repo", "task", "branches", "stash_shas", "worktrees", "temp_paths"}
    if not isinstance(scope, dict) or not required <= scope.keys():
        raise CleanupError("manifest must contain version, repo, task, branches, stash_shas, worktrees, temp_paths")
    if scope.keys() - required - {"empty_scope_reason"}:
        raise CleanupError("manifest contains unknown fields")
    if type(scope["version"]) is not int or scope["version"] != 1:
        raise CleanupError("manifest version must be 1")
    for key in ("repo", "task"):
        if not isinstance(scope[key], str) or not scope[key].strip() or "\0" in scope[key]:
            raise CleanupError(f"manifest {key} must be a nonempty string")
    if not Path(scope["repo"]).is_absolute() or Path(scope["repo"]).resolve() != repo:
        raise CleanupError("manifest repo must be an absolute path matching --repo")
    for key in ("branches", "stash_shas", "worktrees", "temp_paths"):
        values = scope[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() or "\0" in value
            for value in values
        ):
            raise CleanupError(f"manifest {key} must be a list of nonempty strings")
        if len(values) != len(set(values)):
            raise CleanupError(f"manifest {key} contains duplicate entries")
    for branch in scope["branches"]:
        if branch.startswith(("-", "refs/")) or git(
            repo, "check-ref-format", f"refs/heads/{branch}", check=False
        ).returncode:
            raise CleanupError(f"invalid manifest local branch: {branch}")
    for sha in scope["stash_shas"]:
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha):
            raise CleanupError("manifest stash_shas must contain full lowercase commit SHAs, not stash selectors")
    for key in ("worktrees", "temp_paths"):
        for raw_path in scope[key]:
            path = Path(raw_path)
            if not path.is_absolute() or raw_path != os.path.normpath(raw_path) or raw_path != str(path):
                raise CleanupError(f"manifest {key} must contain normalized absolute paths")
            if path == repo or path == Path(path.anchor):
                raise CleanupError(f"manifest {key} cannot contain the repository or filesystem root")
    empty = not any(scope[key] for key in ("branches", "stash_shas", "worktrees", "temp_paths"))
    reason = scope.get("empty_scope_reason")
    if empty and (not isinstance(reason, str) or not reason.strip()):
        raise CleanupError("empty scope requires a nonempty empty_scope_reason; no resources are then verified")
    if not empty and "empty_scope_reason" in scope:
        raise CleanupError("empty_scope_reason is only valid when all resource lists are empty")
    return scope


def verify_task_closeout(args: argparse.Namespace) -> None:
    """Read-only absence check; ownership and manifest completeness are caller facts."""
    repo = repo_top(args.repo)
    scope = read_scope_manifest(repo, args.manifest)
    errors: list[str] = []
    branches = set(text(git(repo, "for-each-ref", "--format=%(refname)", "refs/heads")).splitlines())
    for branch in scope["branches"]:
        if f"refs/heads/{branch}" in branches:
            errors.append(f"task branch remains: {branch}")
    stashes = set(text(git(repo, "stash", "list", "--format=%H")).splitlines())
    for sha in scope["stash_shas"]:
        if sha in stashes:
            errors.append(f"task stash remains: {sha}")
    registered = {Path(str(entry["worktree"])).resolve() for entry in parse_worktrees(repo)}
    for raw_path in scope["worktrees"]:
        path = Path(raw_path)
        if os.path.lexists(path) or path.resolve() in registered:
            errors.append(f"task worktree remains on disk or in Git registry: {path}")
    for raw_path in scope["temp_paths"]:
        if os.path.lexists(raw_path):
            errors.append(f"task temporary path remains: {raw_path}")
    if errors:
        raise CleanupError("task closeout invariant failed: " + json.dumps(errors, ensure_ascii=False))
    print(json.dumps({
        "verified": True,
        "mode": "task",
        "repo": str(repo),
        "task": scope["task"],
        "resource_counts": {key: len(scope[key]) for key in ("branches", "stash_shas", "worktrees", "temp_paths")},
        "empty_scope_reason": scope.get("empty_scope_reason"),
        "verification_scope": "absence of manifest-listed local resources only",
        "not_proven": ["manifest completeness", "task changes delivered", "remote delivery", "repository-wide cleanliness"],
    }, ensure_ascii=False))


def resolve_local_branch(repo: Path, branch: str) -> str:
    if branch.startswith("-") or branch.startswith("refs/"):
        raise CleanupError("pass a local branch name, not an option or full ref")
    result = git(repo, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}", check=False)
    if result.returncode:
        raise CleanupError(f"local branch does not exist: {branch}")
    return text(result)


def protected_branches(repo: Path, extra: list[str]) -> set[str]:
    protected = set(extra)
    for remote in text(git(repo, "remote")).splitlines():
        result = git(repo, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD", check=False)
        if result.returncode == 0:
            remote_head = text(result)
            prefix = f"{remote}/"
            if remote_head.startswith(prefix):
                protected.add(remote_head[len(prefix) :])
    return protected


def delete_branch(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    if args.branch in protected_branches(repo, args.protect):
        raise CleanupError(f"refusing to delete protected/default branch: {args.branch}")
    actual = resolve_local_branch(repo, args.branch)
    if actual != args.expect_sha:
        raise CleanupError(f"branch moved: expected {args.expect_sha}, found {actual}")
    ref = f"refs/heads/{args.branch}"
    if any(entry.get("branch") == ref for entry in parse_worktrees(repo)):
        raise CleanupError(f"refusing to delete a checked-out branch: {args.branch}")
    # The expected old object is checked under Git's ref lock, not just above.
    git(repo, "update-ref", "--no-deref", "-d", ref, args.expect_sha)
    # Config is outside the ref transaction; another owner may recreate this
    # name after deletion. Do not erase its new upstream metadata.
    print(json.dumps({"deleted_branch": args.branch, "sha": actual, "branch_config_cleanup": "not_attempted"}, ensure_ascii=False))


def drop_stash(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    if not STASH_SELECTOR.fullmatch(args.selector):
        raise CleanupError("stash must use an exact selector such as stash@{2}")
    # Native stash drop cannot bind a selector to an expected SHA. Only the
    # sole entry can be deleted by a native prepared ref transaction; retain
    # multiple entries until Git provides conditional reflog deletion.
    ref_format = text(git(repo, "config", "--get", "extensions.refStorage", check=False))
    if ref_format not in ("", "files"):
        raise CleanupError("safe stash deletion requires the files ref backend")
    ref_path = git_path(repo, "refs/stash")
    log_path = git_path(repo, "logs/refs/stash")
    if ref_path.is_symlink() or log_path.is_symlink() or git(repo, "symbolic-ref", "-q", "refs/stash", check=False).returncode == 0:
        raise CleanupError("refusing a symbolic stash ref or reflog")
    try:
        tip = text(git(repo, "rev-parse", "--verify", "refs/stash^{commit}"))
        original = log_path.read_bytes()
        lines = original.splitlines(keepends=True)
        width = len(tip)
        pattern = re.compile(rb"([0-9a-f]{" + str(width).encode() + rb"}) ([0-9a-f]{" + str(width).encode() + rb"}) (.+)\n")
        entries = [pattern.fullmatch(line) for line in lines]
        if not entries or any(entry is None for entry in entries) or entries[-1][2].decode() != tip:
            raise CleanupError("stash reflog is malformed or does not match its ref")
        index = len(entries) - 1 - int(args.selector[7:-1])
        if index < 0:
            raise CleanupError(f"stash selector does not exist: {args.selector}")
        actual = entries[index][2].decode()
        if actual != args.expect_sha:
            raise CleanupError(f"stash moved: expected {args.expect_sha}, found {actual}")
        if len(entries) != 1:
            raise CleanupError("safe stash deletion only supports a sole entry; multiple entries were left unchanged")
        # SHA alone cannot detect an ABA store returning to the same SHA.
        # Recheck the complete log while native prepare holds Git's locks.
        delete_final_stash(repo, tip, log_path, original)
    except (OSError, UnicodeError) as exc:
        raise CleanupError(f"cannot safely delete stash: {exc}") from exc
    print(json.dumps({"dropped_stash": args.selector, "sha": actual}, ensure_ascii=False))


def delete_final_stash(repo: Path, tip: str, log_path: Path, original: bytes) -> None:
    process = subprocess.Popen(
        ["git", "-C", str(repo), "update-ref", "--no-deref", "--stdin"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    try:
        process.stdin.write(f"start\ndelete refs/stash {tip}\nprepare\n".encode())
        process.stdin.flush()
        if process.stdout.readline() != b"start: ok\n" or process.stdout.readline() != b"prepare: ok\n":
            _, error = process.communicate()
            raise CleanupError(error.decode("utf-8", "replace").strip() or "Git could not prepare stash deletion")
        if log_path.is_symlink() or log_path.read_bytes() != original or git(repo, "symbolic-ref", "-q", "refs/stash", check=False).returncode == 0:
            raise CleanupError("stash reflog changed before native transaction prepare; no stash was deleted")
        output, error = process.communicate(input=b"commit\n")
        if process.returncode or output != b"commit: ok\n":
            raise CleanupError(error.decode("utf-8", "replace").strip() or "Git did not confirm stash deletion")
    except (OSError, UnicodeError) as exc:
        raise CleanupError(f"cannot safely delete final stash: {exc}") from exc
    finally:
        if process.poll() is None:
            process.communicate(input=b"abort\n")


def git_path(repo: Path, name: str) -> Path:
    path = Path(text(git(repo, "rev-parse", "--git-path", name)))
    return path if path.is_absolute() else repo / path


def find_worktree(repo: Path, raw_path: str) -> tuple[Path, bool]:
    target = Path(raw_path).expanduser().resolve()
    entries = parse_worktrees(repo)
    for index, entry in enumerate(entries):
        path = Path(str(entry["worktree"])).resolve()
        if path == target:
            return path, index == 0
    raise CleanupError(f"not a registered worktree: {target}")


def verify_worktree(worktree: Path, expected_head: str, expected_status: str) -> None:
    actual_head = head_sha(worktree)
    if actual_head != expected_head:
        raise CleanupError(f"worktree HEAD moved: expected {expected_head}, found {actual_head}")
    actual_status = status_fingerprint(worktree)
    if actual_status != expected_status:
        raise CleanupError(
            f"worktree state changed: expected {expected_status}, found {actual_status}"
        )


def remove_worktree(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    worktree, is_main = find_worktree(repo, args.path)
    if is_main:
        raise CleanupError("cannot remove the main worktree; use clean-worktree")
    verify_worktree(worktree, args.expect_head, args.expect_status)
    if args.unlock:
        git(repo, "worktree", "unlock", str(worktree), check=False)
    git(repo, "worktree", "remove", "--force", str(worktree))
    print(json.dumps({"removed_worktree": str(worktree)}, ensure_ascii=False))


def abort_operations(worktree: Path, states: list[str]) -> None:
    commands = {
        "merge": ("merge", "--abort"),
        "rebase-merge": ("rebase", "--abort"),
        "rebase-apply": ("rebase", "--abort"),
        "cherry-pick": ("cherry-pick", "--abort"),
        "revert": ("revert", "--abort"),
        "bisect": ("bisect", "reset"),
    }
    seen: set[tuple[str, ...]] = set()
    for state in states:
        command = commands[state]
        if command not in seen:
            git(worktree, *command)
            seen.add(command)


def clean_worktree(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    worktree, _ = find_worktree(repo, args.path)
    verify_worktree(worktree, args.expect_head, args.expect_status)
    states = operation_states(worktree)
    if states and not args.abort_operation:
        raise CleanupError(f"Git operation in progress: {', '.join(states)}")
    if states:
        abort_operations(worktree, states)
    git(worktree, "reset", "--hard", "HEAD")
    clean_args = ["clean", "-ffd"]
    for pattern in args.exclude:
        clean_args.extend(["-e", pattern])
    git(worktree, *clean_args)
    print(
        json.dumps(
            {
                "cleaned_worktree": str(worktree),
                "excluded": args.exclude,
                "ignored": "preserved",
            },
            ensure_ascii=False,
        )
    )


def safe_cleanup_path(repo: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repo)
    except ValueError:
        reason = external_task_path_reason(repo, candidate)
        if reason is None:
            raise CleanupError("path is neither inside the worktree nor a discovered repository-named temporary path")
    else:
        if candidate == repo:
            raise CleanupError("refusing to delete the worktree root")
        if candidate.name == ".git" or ".git" in relative.parts:
            raise CleanupError("refusing to delete Git metadata")
        resolved_parent = candidate.parent.resolve()
        try:
            resolved_parent.relative_to(repo.resolve())
        except ValueError as exc:
            raise CleanupError("path escapes the worktree") from exc
    if not os.path.lexists(candidate):
        raise CleanupError(f"path does not exist: {candidate}")
    return candidate


def path_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()

    def visit(item: Path, relative: str) -> None:
        stat = item.lstat()
        digest.update(relative.encode("utf-8", "surrogateescape"))
        digest.update(f"\0{stat.st_mode}\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
        if item.is_symlink():
            digest.update(b"\0link:")
            digest.update(os.readlink(item).encode("utf-8", "surrogateescape"))
        elif item.is_dir():
            for child in sorted(item.iterdir(), key=lambda value: value.name):
                visit(child, f"{relative}/{child.name}")
        elif item.is_file():
            with item.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)

    visit(path, path.name)
    return digest.hexdigest()


def fingerprint_path(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    path = safe_cleanup_path(repo, args.path)
    print(json.dumps({"path": str(path), "fingerprint": path_fingerprint(path)}, ensure_ascii=False))


def delete_path(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    path = safe_cleanup_path(repo, args.path)
    actual = path_fingerprint(path)
    if actual != args.expect_fingerprint:
        raise CleanupError(f"path changed: expected {args.expect_fingerprint}, found {actual}")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(json.dumps({"deleted_path": str(path), "fingerprint": actual}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--repo", default=".")
    inspect_parser.add_argument("--target", help="optional commit/ref for read-only reachability evidence; does not prove PR merge or safe deletion")
    inspect_parser.set_defaults(func=lambda args: print(json.dumps(inspect_repo(repo_top(args.repo), args.target), ensure_ascii=False, indent=2)))

    verify_parser = subparsers.add_parser("verify-closeout")
    verify_parser.add_argument("--repo", default=".")
    verify_parser.add_argument("--target", required=True)
    verify_parser.set_defaults(func=verify_closeout)

    task_verify_parser = subparsers.add_parser("verify-task-closeout", help="read-only absence check for an explicit task scope manifest")
    task_verify_parser.add_argument("--repo", default=".")
    task_verify_parser.add_argument("--manifest", required=True)
    task_verify_parser.set_defaults(func=verify_task_closeout)

    branch_parser = subparsers.add_parser("delete-branch")
    branch_parser.add_argument("branch")
    branch_parser.add_argument("--repo", default=".")
    branch_parser.add_argument("--expect-sha", required=True)
    branch_parser.add_argument("--protect", action="append", required=True)
    branch_parser.set_defaults(func=delete_branch)

    stash_parser = subparsers.add_parser("drop-stash")
    stash_parser.add_argument("selector")
    stash_parser.add_argument("--repo", default=".")
    stash_parser.add_argument("--expect-sha", required=True)
    stash_parser.set_defaults(func=drop_stash)

    remove_parser = subparsers.add_parser("remove-worktree")
    remove_parser.add_argument("path")
    remove_parser.add_argument("--repo", default=".")
    remove_parser.add_argument("--expect-head", required=True)
    remove_parser.add_argument("--expect-status", required=True)
    remove_parser.add_argument("--unlock", action="store_true")
    remove_parser.set_defaults(func=remove_worktree)

    clean_parser = subparsers.add_parser("clean-worktree")
    clean_parser.add_argument("path")
    clean_parser.add_argument("--repo", default=".")
    clean_parser.add_argument("--expect-head", required=True)
    clean_parser.add_argument("--expect-status", required=True)
    clean_parser.add_argument("--exclude", action="append", default=[])
    clean_parser.add_argument("--abort-operation", action="store_true")
    clean_parser.set_defaults(func=clean_worktree)

    fingerprint_parser = subparsers.add_parser("fingerprint-path")
    fingerprint_parser.add_argument("path")
    fingerprint_parser.add_argument("--repo", default=".")
    fingerprint_parser.set_defaults(func=fingerprint_path)

    path_parser = subparsers.add_parser("delete-path")
    path_parser.add_argument("path")
    path_parser.add_argument("--repo", default=".")
    path_parser.add_argument("--expect-fingerprint", required=True)
    path_parser.set_defaults(func=delete_path)

    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except CleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
