#!/usr/bin/env python3
"""Read-only audits and cleanup mutations run only against temporary repositories."""

import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HELPER = Path(__file__).with_name("git_cleanup.py")
SPEC = importlib.util.spec_from_file_location("git_cleanup", HELPER)
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class ScopedCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="git-scope-verification-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Scope Test")
        self.git("config", "user.email", "scope@example.invalid")
        (self.repo / "tracked.txt").write_text("base\n")
        self.git("add", "tracked.txt")
        self.git("commit", "-m", "initial")
        self.git("branch", "other-task")
        (self.repo / "tracked.txt").write_text("other task stash\n")
        self.git("stash", "push", "-m", "other task")
        self.other_stash = self.git("rev-parse", "stash@{0}").strip()
        self.other_worktree = self.root / "other-worktree"
        self.git("worktree", "add", str(self.other_worktree), "other-task")
        (self.other_worktree / "other-wip.txt").write_text("other worktree WIP\n")
        (self.repo / "tracked.txt").write_text("user WIP\n")
        (self.repo / "user-untracked.txt").write_text("user untracked WIP\n")
        (self.repo / ".codex" / "tmp" / "other-task").mkdir(parents=True)
        (self.repo / ".codex" / "tmp" / "other-task" / "artifact").write_text("other artifact\n")
        self.manifest_path = self.root / "scope.json"
        self.scope = {
            "version": 1,
            "repo": str(self.repo),
            "task": "completed task",
            "branches": ["codex/completed-task"],
            "stash_shas": ["0" * 40],
            "worktrees": [str(self.root / "completed-worktree")],
            "temp_paths": [str(self.repo / "completed-temp")],
        }

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, env=self.env,
            capture_output=True, text=True,
        ).stdout

    def snapshot(self):
        """Inventory paths and bytes, including all refs, Git objects, indexes and WIP."""
        result = {}
        for path in sorted(self.root.rglob("*")):
            name = str(path.relative_to(self.root))
            if path.is_symlink():
                result[name] = ("symlink", os.readlink(path))
            elif path.is_file():
                result[name] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
            else:
                result[name] = ("directory", None)
        return result

    def verify(self, scope=None, raw=None, full=False, omit_manifest=False):
        if not full:
            self.manifest_path.write_text(raw if raw is not None else json.dumps(scope if scope is not None else self.scope))
        before = self.snapshot()
        command = [sys.executable, str(HELPER), "verify-closeout" if full else "verify-task-closeout", "--repo", str(self.repo)]
        if full:
            command += ["--target", "main"]
        elif not omit_manifest:
            command += ["--manifest", str(self.manifest_path)]
        helper_env = dict(self.env)
        helper_env.pop("GIT_OPTIONAL_LOCKS", None)
        result = subprocess.run(command, capture_output=True, text=True, env=helper_env)
        self.assertEqual(before, self.snapshot(), "verification changed or deleted fixture content")
        return result

    def audit(self, target="main"):
        before = self.snapshot()
        command = [sys.executable, str(HELPER), "inspect", "--repo", str(self.repo)]
        if target is not None:
            command += [f"--target={target}"]
        helper_env = dict(self.env)
        helper_env.pop("GIT_OPTIONAL_LOCKS", None)
        result = subprocess.run(command, capture_output=True, text=True, env=helper_env)
        self.assertEqual(before, self.snapshot(), "audit changed refs, indexes or fixture content")
        return result

    def worktree_git(self, path, *args):
        return subprocess.run(
            ["git", "-C", str(path), *args], check=True, env=self.env,
            capture_output=True, text=True,
        ).stdout

    def test_audit_proves_reachable_commits_but_preserves_dirty_worktrees(self):
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["delivery_audit"]["target_sha"], self.git("rev-parse", "main").strip())
        for branch in output["branches"]:
            self.assertTrue(branch["history"]["head_in_target"])
            self.assertEqual(branch["history"]["unique_commits"], [])
        for worktree in output["worktrees"]:
            self.assertTrue(worktree["dirty"], worktree)
            self.assertTrue(worktree["history"]["head_in_target"])
        self.assertIn("deletion authorization or safety", output["delivery_audit"]["not_proven"])
        self.assertIn("delivery of uncommitted or ignored content", output["delivery_audit"]["not_proven"])

    def test_audit_exposes_new_delta_after_previously_included_head(self):
        self.worktree_git(self.other_worktree, "add", "other-wip.txt")
        self.worktree_git(self.other_worktree, "commit", "-m", "original delivered work")
        original_head = self.git("rev-parse", "other-task").strip()
        self.git("branch", "audit-target", original_head)
        self.git("branch", "merged-snapshot", original_head)
        (self.other_worktree / "new-delta.txt").write_text("new work after delivery\n")
        self.worktree_git(self.other_worktree, "add", "new-delta.txt")
        self.worktree_git(self.other_worktree, "commit", "-m", "new delta")
        current_head = self.git("rev-parse", "other-task").strip()
        result = self.audit("audit-target")
        self.assertEqual(result.returncode, 0, result.stderr)
        branches = {item["name"]: item for item in json.loads(result.stdout)["branches"]}
        self.assertTrue(branches["merged-snapshot"]["history"]["head_in_target"])
        self.assertFalse(branches["other-task"]["history"]["head_in_target"])
        self.assertEqual(branches["other-task"]["history"]["unique_commits"], [current_head])

    def test_squash_equal_trees_are_not_reported_as_unmerged_or_safe_to_delete(self):
        self.worktree_git(self.other_worktree, "add", "other-wip.txt")
        self.worktree_git(self.other_worktree, "commit", "-m", "source one")
        (self.other_worktree / "second.txt").write_text("second source commit\n")
        self.worktree_git(self.other_worktree, "add", "second.txt")
        self.worktree_git(self.other_worktree, "commit", "-m", "source two")
        target_worktree = self.root / "squash-target"
        self.git("worktree", "add", "-b", "squash-target", str(target_worktree), "main")
        self.worktree_git(target_worktree, "merge", "--squash", "other-task")
        self.worktree_git(target_worktree, "commit", "-m", "squashed delivery")
        self.assertEqual(self.git("diff", "other-task", "squash-target"), "")
        result = self.audit("squash-target")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        source = next(item for item in output["branches"] if item["name"] == "other-task")
        self.assertFalse(source["history"]["head_in_target"])
        self.assertEqual(len(source["history"]["unique_commits"]), 2)
        self.assertIn("squash/rebase patch equivalence", output["delivery_audit"]["not_proven"])
        self.assertIn("platform PR/MR merge status", output["delivery_audit"]["not_proven"])
        self.assertNotIn("merge_status", source)

    def test_cherry_picked_work_remains_a_reachability_question(self):
        self.worktree_git(self.other_worktree, "add", "other-wip.txt")
        self.worktree_git(self.other_worktree, "commit", "-m", "source change")
        target_worktree = self.root / "rebased-target"
        self.git("worktree", "add", "-b", "rebased-target", str(target_worktree), "main")
        self.worktree_git(target_worktree, "commit", "--allow-empty", "-m", "different base")
        self.worktree_git(target_worktree, "cherry-pick", "other-task")
        self.assertEqual(self.git("diff", "other-task", "rebased-target"), "")
        result = self.audit("rebased-target")
        self.assertEqual(result.returncode, 0, result.stderr)
        source = next(item for item in json.loads(result.stdout)["branches"] if item["name"] == "other-task")
        self.assertFalse(source["history"]["head_in_target"])
        self.assertEqual(source["history"]["unique_commits"], [self.git("rev-parse", "other-task").strip()])

    def test_audit_separates_ignored_content_from_dirty_and_reports_detached_head(self):
        clean_worktree = self.root / "clean-worktree"
        self.git("worktree", "add", "--detach", str(clean_worktree), "main")
        self.worktree_git(clean_worktree, "config", "core.excludesFile", str(self.root / "ignore"))
        (self.root / "ignore").write_text("ignored-artifact\n")
        (clean_worktree / "ignored-artifact").write_text("unique local material\n")
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        worktree = next(item for item in json.loads(result.stdout)["worktrees"] if item["path"] == str(clean_worktree))
        self.assertIsNone(worktree["branch"])
        self.assertFalse(worktree["dirty"])
        self.assertTrue(worktree["has_ignored"])
        self.assertTrue(worktree["history"]["head_in_target"])
        (clean_worktree / "tracked.txt").write_text("new staged work\n")
        self.worktree_git(clean_worktree, "add", "tracked.txt")
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        worktree = next(item for item in json.loads(result.stdout)["worktrees"] if item["path"] == str(clean_worktree))
        self.assertTrue(worktree["dirty"])

    def test_audit_missing_target_fails_without_mutation_or_traceback(self):
        for target in ("missing-target", "--all"):
            with self.subTest(target=target):
                result = self.audit(target)
                self.assertEqual(result.returncode, 2)
                self.assertIn("target does not resolve", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_audit_missing_registered_worktree_is_unknown_not_clean(self):
        self.other_worktree.rename(self.root / "moved-other-worktree")
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        worktree = next(item for item in json.loads(result.stdout)["worktrees"] if item["path"] == str(self.other_worktree))
        self.assertIsNone(worktree["dirty"])
        self.assertIsNone(worktree["status_fingerprint"])
        self.assertIn("missing", worktree["inspection_error"])
        self.assertTrue(worktree["history"]["head_in_target"])

    def test_original_inspect_without_target_still_works_without_claiming_delivery(self):
        result = self.audit(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertNotIn("delivery_audit", output)
        self.assertTrue(output["worktrees"])
        self.assertTrue(all("history" not in item for item in output["branches"]))

    def test_other_task_resources_and_wip_are_preserved(self):
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["verified"])
        self.assertEqual(output["mode"], "task")
        self.assertEqual(output["resource_counts"], {"branches": 1, "stash_shas": 1, "worktrees": 1, "temp_paths": 1})
        self.assertIn("manifest completeness", output["not_proven"])
        self.assertIn("remote delivery", output["not_proven"])
        self.assertIn("repository-wide cleanliness", output["not_proven"])
        self.assertEqual(self.git("rev-parse", "stash@{0}").strip(), self.other_stash)
        self.assertEqual((self.repo / "tracked.txt").read_text(), "user WIP\n")

    def test_each_task_resource_is_rejected_without_deletion(self):
        cases = {
            "branches": ["other-task"],
            "stash_shas": [self.other_stash],
            "worktrees": [str(self.other_worktree)],
            "temp_paths": [str(self.repo / "user-untracked.txt")],
        }
        for key, values in cases.items():
            with self.subTest(resource=key):
                result = self.verify(scope=dict(self.scope, **{key: values}))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("task closeout invariant failed", result.stderr)

    def test_stash_identity_survives_selector_shift(self):
        self.git("stash", "push", "-m", "newer task stash")
        self.assertEqual(self.git("rev-parse", "stash@{1}").strip(), self.other_stash)
        result = self.verify(scope=dict(self.scope, stash_shas=[self.other_stash]))
        self.assertEqual(result.returncode, 2)
        self.assertIn(self.other_stash, result.stderr)

    def test_missing_worktree_directory_with_registration_is_rejected(self):
        moved = self.root / "moved-worktree"
        self.other_worktree.rename(moved)
        result = self.verify(scope=dict(self.scope, worktrees=[str(self.other_worktree)]))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Git registry", result.stderr)

    def test_dangling_symlink_is_residual(self):
        link = self.repo / "dangling-task-artifact"
        link.symlink_to(self.root / "absent-target")
        result = self.verify(scope=dict(self.scope, temp_paths=[str(link)]))
        self.assertEqual(result.returncode, 2)
        self.assertTrue(link.is_symlink())

    def test_empty_scope_needs_explicit_reason_and_reports_zero_resources(self):
        empty = dict(self.scope, branches=[], stash_shas=[], worktrees=[], temp_paths=[])
        result = self.verify(scope=empty)
        self.assertEqual(result.returncode, 2)
        self.assertIn("empty_scope_reason", result.stderr)
        result = self.verify(scope=dict(empty, empty_scope_reason="No task-local disposable resources were created."))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(sum(output["resource_counts"].values()), 0)
        self.assertIn("No task-local", output["empty_scope_reason"])

    def test_malformed_and_misbound_manifests_are_rejected(self):
        malformed = [
            "", "{", "null", "[]", "{}",
            json.dumps(dict(self.scope, version=True)),
            json.dumps(dict(self.scope, version=2)),
            json.dumps(dict(self.scope, repo=str(self.other_worktree))),
            json.dumps(dict(self.scope, task=" ")),
            json.dumps(dict(self.scope, branches="codex/task")),
            json.dumps(dict(self.scope, branches=[None])),
            json.dumps(dict(self.scope, branches=["codex/task", "codex/task"])),
            json.dumps(dict(self.scope, branches=["refs/heads/task"])),
            json.dumps(dict(self.scope, branches=["bad branch"])),
            json.dumps(dict(self.scope, stash_shas=["stash@{0}"])),
            json.dumps(dict(self.scope, stash_shas=[self.other_stash[:12]])),
            json.dumps(dict(self.scope, worktrees=["relative/path"])),
            json.dumps(dict(self.scope, temp_paths=[str(self.repo / "x" / ".." / "gone")])),
            json.dumps(dict(self.scope, temp_paths=[str(self.repo) + "//gone"])),
            json.dumps(dict(self.scope, temp_paths=[str(self.repo)])),
            json.dumps(dict(self.scope, temp_paths=["/"])),
            json.dumps(dict(self.scope, typo=[])),
            json.dumps(dict(self.scope, empty_scope_reason="Not empty")),
            json.dumps(dict(self.scope, empty_scope_reason=None)),
            json.dumps(self.scope)[:-1] + ',"task":"duplicate key"}',
        ]
        for raw in malformed:
            with self.subTest(raw=raw):
                result = self.verify(raw=raw)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn('"verified": true', result.stdout)
                self.assertNotIn("Traceback", result.stderr)
        result = self.verify(omit_manifest=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--manifest", result.stderr)

    def test_full_closeout_still_rejects_other_task_resources(self):
        result = self.verify(full=True)
        self.assertEqual(result.returncode, 2)
        for detail in ("local branches", "stash must be empty", "exactly one worktree", "worktree content remains", "task path candidates"):
            self.assertIn(detail, result.stderr)


class CleanupRaceTests(unittest.TestCase):
    setUp = ScopedCloseoutTests.setUp
    git = ScopedCloseoutTests.git

    def args(self, **values):
        return argparse.Namespace(repo=str(self.repo), **values)

    def run_cleanup(self, operation, **values):
        with redirect_stdout(io.StringIO()):
            operation(self.args(**values))

    def stash_shas(self):
        return self.git("stash", "list", "--format=%H").splitlines()

    def add_stash(self, title):
        (self.repo / "tracked.txt").write_text(f"{title}\n")
        self.git("stash", "push", "-m", title)
        return self.git("rev-parse", "stash@{0}").strip()

    def test_branch_expected_sha_is_checked_by_the_deletion_transaction(self):
        self.git("branch", "codex/delete")
        old = self.git("rev-parse", "codex/delete").strip()
        tree = self.git("rev-parse", "main^{tree}").strip()
        newer = self.git("commit-tree", tree, "-p", old, "-m", "concurrent branch work").strip()
        original_git = cleanup.git
        raced = False

        def interpose(repo, *args, **kwargs):
            nonlocal raced
            if (args[0] == "update-ref" and "-d" in args) or args[:2] == ("branch", "-D"):
                raced = True
                self.git("update-ref", "refs/heads/codex/delete", newer, old)
            return original_git(repo, *args, **kwargs)

        with patch.object(cleanup, "git", interpose), self.assertRaises(cleanup.CleanupError):
            self.run_cleanup(cleanup.delete_branch, branch="codex/delete", expect_sha=old, protect=["main"])
        self.assertTrue(raced)
        self.assertEqual(self.git("rev-parse", "codex/delete").strip(), newer)

    def test_current_and_linked_worktree_branches_are_preserved(self):
        for branch in ("main", "other-task"):
            with self.subTest(branch=branch), self.assertRaises(cleanup.CleanupError):
                self.run_cleanup(cleanup.delete_branch, branch=branch, expect_sha=self.git("rev-parse", branch).strip(), protect=[])
            self.git("rev-parse", branch)

    def test_symbolic_branch_deletion_does_not_delete_its_target(self):
        old = self.git("rev-parse", "main").strip()
        self.git("symbolic-ref", "refs/heads/codex/alias", "refs/heads/main")
        self.run_cleanup(cleanup.delete_branch, branch="codex/alias", expect_sha=old, protect=["main"])
        self.assertEqual(self.git("rev-parse", "main").strip(), old)
        self.assertEqual(self.git("branch", "--list", "codex/alias"), "")

    def test_unchecked_out_branch_is_deleted_by_expected_sha(self):
        self.git("branch", "codex/delete")
        self.git("config", "branch.codex/delete.remote", "origin")
        old = self.git("rev-parse", "codex/delete").strip()
        self.run_cleanup(cleanup.delete_branch, branch="codex/delete", expect_sha=old, protect=["main"])
        self.assertEqual(self.git("branch", "--list", "codex/delete"), "")
        result = subprocess.run(["git", "-C", str(self.repo), "config", "--get", "branch.codex/delete.remote"], capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b"origin")

    def test_branch_recreated_after_deletion_keeps_new_upstream_metadata(self):
        self.git("branch", "codex/delete")
        old = self.git("rev-parse", "codex/delete").strip()
        original_git = cleanup.git

        def interpose(repo, *args, **kwargs):
            result = original_git(repo, *args, **kwargs)
            if args == ("update-ref", "--no-deref", "-d", "refs/heads/codex/delete", old):
                self.git("branch", "codex/delete", old)
                self.git("config", "branch.codex/delete.remote", "new-owner-remote")
            return result

        with patch.object(cleanup, "git", interpose):
            self.run_cleanup(cleanup.delete_branch, branch="codex/delete", expect_sha=old, protect=["main"])
        self.assertEqual(self.git("rev-parse", "codex/delete").strip(), old)
        self.assertEqual(self.git("config", "--get", "branch.codex/delete.remote").strip(), "new-owner-remote")

    def test_stash_selector_shift_before_lock_is_rejected_without_dropping_either(self):
        expected = self.other_stash
        original_git = cleanup.git
        newer = None

        def interpose(repo, *args, **kwargs):
            nonlocal newer
            if args == ("rev-parse", "--verify", "refs/stash^{commit}"):
                newer = self.add_stash("concurrent task stash")
            return original_git(repo, *args, **kwargs)

        with patch.object(cleanup, "git", interpose), self.assertRaises(cleanup.CleanupError):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=expected)
        self.assertEqual(self.stash_shas(), [newer, expected])
        self.assertFalse((self.repo / ".git/refs/stash.lock").exists())

    def test_multiple_stash_entries_are_rejected_without_any_file_edits(self):
        newest = self.add_stash("newer task")
        files = [self.repo / ".git/refs/stash", self.repo / ".git/logs/refs/stash"]
        before = [path.read_bytes() for path in files]
        for selector, expected in (("stash@{0}", newest), ("stash@{1}", self.other_stash)):
            with self.subTest(selector=selector), self.assertRaisesRegex(cleanup.CleanupError, "only supports a sole entry"):
                self.run_cleanup(cleanup.drop_stash, selector=selector, expect_sha=expected)
            self.assertEqual([path.read_bytes() for path in files], before)
            self.assertEqual(self.stash_shas(), [newest, self.other_stash])
        self.assertFalse((self.repo / ".git/refs/stash.lock").exists())

    def test_sole_stash_is_deleted_by_native_git(self):
        self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertEqual(self.stash_shas(), [])
        self.assertFalse((self.repo / ".git/refs/stash").exists())
        self.assertFalse((self.repo / ".git/logs/refs/stash").exists())

    def test_final_stash_ref_deletion_preserves_a_new_concurrent_stash(self):
        original_delete = cleanup.delete_final_stash
        newer = None

        def interpose(repo, tip, log_path, original):
            nonlocal newer
            newer = self.add_stash("concurrent before native prepare")
            return original_delete(repo, tip, log_path, original)

        with patch.object(cleanup, "delete_final_stash", interpose), self.assertRaises(cleanup.CleanupError):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertIsNotNone(newer)
        self.assertEqual(self.stash_shas(), [newer, self.other_stash])
        self.assertEqual(self.git("rev-parse", "refs/stash").strip(), newer)

    def test_final_stash_deletion_rejects_a_new_same_sha_reflog_entry(self):
        original_delete = cleanup.delete_final_stash
        newer = None

        def interpose(repo, tip, log_path, original):
            nonlocal newer
            newer = self.add_stash("intermediate concurrent stash")
            self.git("stash", "store", "-m", "concurrent same object", tip)
            return original_delete(repo, tip, log_path, original)

        with patch.object(cleanup, "delete_final_stash", interpose), self.assertRaisesRegex(cleanup.CleanupError, "reflog changed"):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertEqual(self.stash_shas(), [self.other_stash, newer, self.other_stash])
        self.assertFalse((self.repo / ".git/refs/stash.lock").exists())

    def test_final_stash_native_prepare_blocks_concurrent_git_writes(self):
        original_git = cleanup.git
        attempts = []

        def interpose(repo, *args, **kwargs):
            if args == ("symbolic-ref", "-q", "refs/stash") and (self.repo / ".git/refs/stash.lock").exists():
                attempts.append(subprocess.run(["git", "-C", str(self.repo), "stash", "store", "-m", "concurrent same object", self.other_stash], capture_output=True, env=self.env))
            return original_git(repo, *args, **kwargs)

        with patch.object(cleanup, "git", interpose):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertTrue(attempts)
        self.assertTrue(all(result.returncode for result in attempts))
        self.assertEqual(self.stash_shas(), [])

    def test_final_packed_stash_is_deleted_from_a_linked_worktree(self):
        self.git("pack-refs", "--all", "--prune")
        packed = self.repo / ".git/packed-refs"
        self.assertIn("refs/stash", packed.read_text())
        for name in ("refs/stash", "logs/refs/stash"):
            self.assertEqual(cleanup.git_path(self.other_worktree, name).resolve(), (self.repo / ".git" / name).resolve())
        with redirect_stdout(io.StringIO()):
            cleanup.drop_stash(argparse.Namespace(repo=str(self.other_worktree), selector="stash@{0}", expect_sha=self.other_stash))
        self.assertEqual(self.stash_shas(), [])
        self.assertNotIn("refs/stash", packed.read_text())
        self.assertEqual(self.git("rev-parse", "main").strip(), self.git("rev-parse", "other-task").strip())

    def test_failure_after_native_prepare_aborts_with_original_stash_unchanged(self):
        files = [self.repo / ".git/refs/stash", self.repo / ".git/logs/refs/stash"]
        before = [path.read_bytes() for path in files]
        original_git = cleanup.git

        def interpose(repo, *args, **kwargs):
            if args == ("symbolic-ref", "-q", "refs/stash") and (self.repo / ".git/refs/stash.lock").exists():
                raise cleanup.CleanupError("injected failure after native prepare")
            return original_git(repo, *args, **kwargs)

        with patch.object(cleanup, "git", interpose), self.assertRaisesRegex(cleanup.CleanupError, "injected failure after native prepare"):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertEqual([path.read_bytes() for path in files], before)
        self.assertEqual(self.stash_shas(), [self.other_stash])
        self.assertFalse((self.repo / ".git/refs/stash.lock").exists())
        self.assertFalse((self.repo / ".git/logs/refs/stash.lock").exists())

    def test_existing_native_ref_lock_is_preserved_and_prevents_deletion(self):
        path = self.repo / ".git/refs/stash.lock"
        path.write_text("owned by another Git process")
        with self.assertRaises(cleanup.CleanupError):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertEqual(path.read_text(), "owned by another Git process")
        self.assertEqual(self.stash_shas(), [self.other_stash])

    def test_non_files_ref_backend_is_rejected_before_mutation(self):
        original_git = cleanup.git

        def interpose(repo, *args, **kwargs):
            if args == ("config", "--get", "extensions.refStorage"):
                return subprocess.CompletedProcess(args, 0, b"reftable\n", b"")
            return original_git(repo, *args, **kwargs)

        before = (self.repo / ".git/logs/refs/stash").read_bytes()
        with patch.object(cleanup, "git", interpose), self.assertRaises(cleanup.CleanupError):
            self.run_cleanup(cleanup.drop_stash, selector="stash@{0}", expect_sha=self.other_stash)
        self.assertEqual((self.repo / ".git/logs/refs/stash").read_bytes(), before)
        self.assertEqual(self.stash_shas(), [self.other_stash])


if __name__ == "__main__":
    unittest.main()
