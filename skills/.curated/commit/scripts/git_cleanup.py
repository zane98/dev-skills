#!/usr/bin/env python3
"""Inspect and delete local Git development state with compare-and-swap guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
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


def inspect_repo(repo: Path) -> dict[str, object]:
    worktrees = []
    for entry in parse_worktrees(repo):
        path = Path(str(entry["worktree"])).resolve()
        worktrees.append(
            {
                "path": str(path),
                "head": head_sha(path),
                "branch": current_branch(path),
                "operations": operation_states(path),
                "status_fingerprint": status_fingerprint(path),
                "status": status_bytes(path).decode("utf-8", "backslashreplace"),
            }
        )

    branches = []
    raw_branches = text(
        git(repo, "for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/heads")
    )
    for line in raw_branches.splitlines():
        if line:
            name, sha = line.split("\t", 1)
            branches.append({"name": name, "sha": sha})

    stashes = []
    raw_stashes = text(git(repo, "stash", "list", "--format=%gd\t%H\t%gs"))
    for line in raw_stashes.splitlines():
        if line:
            selector, sha, subject = line.split("\t", 2)
            stashes.append({"selector": selector, "sha": sha, "subject": subject})

    return {
        "repo": str(repo),
        "current_branch": current_branch(repo),
        "branches": branches,
        "stashes": stashes,
        "worktrees": worktrees,
    }


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
    git(repo, "branch", "-D", "--", args.branch)
    print(json.dumps({"deleted_branch": args.branch, "sha": actual}, ensure_ascii=False))


def drop_stash(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    if not STASH_SELECTOR.fullmatch(args.selector):
        raise CleanupError("stash must use an exact selector such as stash@{2}")
    actual = text(git(repo, "rev-parse", "--verify", f"{args.selector}^{{commit}}"))
    if actual != args.expect_sha:
        raise CleanupError(f"stash moved: expected {args.expect_sha}, found {actual}")
    git(repo, "stash", "drop", args.selector)
    print(json.dumps({"dropped_stash": args.selector, "sha": actual}, ensure_ascii=False))


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


def safe_local_path(repo: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repo)
    except ValueError as exc:
        raise CleanupError("path escapes the worktree") from exc
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
    path = safe_local_path(repo, args.path)
    print(json.dumps({"path": str(path), "fingerprint": path_fingerprint(path)}, ensure_ascii=False))


def delete_path(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    path = safe_local_path(repo, args.path)
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
    inspect_parser.set_defaults(func=lambda args: print(json.dumps(inspect_repo(repo_top(args.repo)), ensure_ascii=False, indent=2)))

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
