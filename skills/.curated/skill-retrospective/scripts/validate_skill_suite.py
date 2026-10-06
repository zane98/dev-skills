#!/usr/bin/env python3
"""Validate skill structure and the schema of manual routing evaluation cases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MARKDOWN_LINK_RE = re.compile(r"\[[^]]+\]\(([^)]+)\)")
REQUIRED_CASE_FIELDS = {"id", "prompt", "expected_skills"}
MAX_SKILL_LINES = 500
CASE_LIST_FIELDS = ("expected_skills", "forbidden_skills", "required_actions", "forbidden_actions", "required_decisions")


def frontmatter_value(content: str, key: str) -> str | None:
    match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.DOTALL)
    if not match:
        return None
    value = re.search(rf"^{re.escape(key)}:\s*(.+)$", match.group(1), flags=re.MULTILINE)
    return value.group(1).strip().strip('"') if value else None


def validate_skill(skill_file: Path, errors: list[str]) -> None:
    content = skill_file.read_text(encoding="utf-8")
    name = frontmatter_value(content, "name")
    description = frontmatter_value(content, "description")
    folder = skill_file.parent.name

    if not name or not SKILL_NAME_RE.fullmatch(name):
        errors.append(f"{skill_file}: invalid frontmatter name")
    elif name != folder:
        errors.append(f"{skill_file}: name '{name}' does not match folder '{folder}'")
    if not description or "TODO" in description:
        errors.append(f"{skill_file}: missing completed description")
    if len(content.splitlines()) > MAX_SKILL_LINES:
        errors.append(
            f"{skill_file}: {len(content.splitlines())} lines exceeds the "
            f"{MAX_SKILL_LINES}-line progressive-disclosure limit"
        )

    # References contain important routing too; validating only the entrypoint
    # misses links broken by moving domain guidance between files.
    markdown_files = [skill_file, *sorted((skill_file.parent / "references").glob("**/*.md"))]
    for markdown_file in markdown_files:
        for target in MARKDOWN_LINK_RE.findall(markdown_file.read_text(encoding="utf-8")):
            target = target.strip().strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            destination = target.split("#", 1)[0]
            if destination and not (markdown_file.parent / destination).exists():
                errors.append(f"{markdown_file}: missing linked resource '{destination}'")

    interface = skill_file.parent / "agents" / "openai.yaml"
    if not interface.exists():
        return
    metadata = interface.read_text(encoding="utf-8")
    prompt_match = re.search(r'^\s*default_prompt:\s*"([^"]+)"\s*$', metadata, flags=re.MULTILINE)
    if not prompt_match or f"${name}" not in prompt_match.group(1):
        errors.append(f"{interface}: default_prompt must mention ${name}")


def validate_cases(cases_file: Path, skill_names: set[str], errors: list[str]) -> int:
    try:
        cases = json.loads(cases_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{cases_file}: invalid JSON: {error}")
        return 0

    if not isinstance(cases, list) or not cases:
        errors.append(f"{cases_file}: cases must be a non-empty array")
        return 0

    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not REQUIRED_CASE_FIELDS <= case.keys():
            errors.append(f"{cases_file}: every case needs {sorted(REQUIRED_CASE_FIELDS)}")
            continue
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id.strip() or case_id in case_ids:
            errors.append(f"{cases_file}: duplicate or invalid case id '{case_id}'")
            continue
        case_ids.add(case_id)
        if not isinstance(case["prompt"], str) or not case["prompt"].strip():
            errors.append(f"{cases_file}: case '{case_id}' has an empty prompt")
        valid_lists: dict[str, list[str]] = {}
        for key in CASE_LIST_FIELDS:
            values = case.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                errors.append(f"{cases_file}: case '{case_id}' {key} must be a string array")
                continue
            valid_lists[key] = values
            if len(values) != len(set(values)):
                errors.append(f"{cases_file}: case '{case_id}' has duplicates in {key}")
            if key in ("expected_skills", "forbidden_skills"):
                for skill in values:
                    if skill not in skill_names:
                        errors.append(f"{cases_file}: case '{case_id}' references unknown skill '{skill}'")
        if not valid_lists.get("expected_skills"):
            errors.append(f"{cases_file}: case '{case_id}' needs at least one expected skill")
        for required, forbidden in (("expected_skills", "forbidden_skills"), ("required_actions", "forbidden_actions")):
            overlap = set(valid_lists.get(required, [])) & set(valid_lists.get(forbidden, []))
            if overlap:
                errors.append(f"{cases_file}: case '{case_id}' requires and forbids {sorted(overlap)}")
    return len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, help="Additional installed skills used only to resolve case skill names")
    args = parser.parse_args()

    skill_files = sorted(args.skills_root.glob("*/SKILL.md"))
    errors: list[str] = []
    for skill_file in skill_files:
        validate_skill(skill_file, errors)

    skill_names = {skill_file.parent.name for skill_file in skill_files}
    if args.catalog_root:
        skill_names.update(p.parent.name for p in args.catalog_root.glob("*/SKILL.md"))
    case_count = validate_cases(args.cases, skill_names, errors)
    if errors:
        print("FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print(f"PASS: {len(skill_files)} skills and {case_count} routing cases are structurally valid.")
    characters = sum(len(p.read_text(encoding="utf-8")) for p in skill_files)
    print(f"Entrypoint size: {characters} characters; line limits do not measure decision quality.")
    if args.catalog_root:
        print("Additional catalog resolves names only; its files were not validated by this run.")
    print("Semantic routing and side effects require a fresh-agent replay and human review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
