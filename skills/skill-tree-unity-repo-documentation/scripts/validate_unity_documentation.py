#!/usr/bin/env python3
"""Validate structural Unity repository documentation contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_ROOT = ["README.md", "AGENTS.md"]
REQUIRED_DOCS = [
    "PROJECT.md",
    "TECHNICAL.md",
    "FEATURES.md",
    "FUTURE.md",
    "RULES.md",
    "REPOSITORY_MAP.md",
    "BUILD_AND_RELEASE.md",
    "TESTING.md",
    "DEPENDENCIES.md",
    "DOCUMENTS_SNAPSHOT.md",
]
QUEUE_HEADINGS = ["## Pending Queue", "## Prioritized Next Changes", "## Backlog"]
REQUIRED_TASK_SECTIONS = [
    "Goal",
    "Current behavior",
    "Desired behavior",
    "Touch",
    "Discovery allowance",
    "Out of scope",
    "Implementation constraints",
    "Questions and required clarifications",
    "Validation",
    "Acceptance",
    "Documentation updates",
    "Risks",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def find_markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)", text)


def validate_future(path: Path, strict: bool) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing FUTURE.md: {path}"]
    text = read(path)
    last = -1
    for heading in QUEUE_HEADINGS:
        index = text.find(heading)
        if index == -1:
            errors.append(f"FUTURE.md missing `{heading}`")
        elif index < last:
            errors.append("FUTURE.md queue headings are out of order")
        last = index
    prioritized = text.split("## Prioritized Next Changes", 1)[-1].split("## Backlog", 1)[0]
    names: set[str] = set()
    for match in re.finditer(r"(?m)^###\s+(.+?)\s*$", prioritized):
        title = re.sub(r"\s+", " ", match.group(1).strip()).casefold()
        if title in names:
            errors.append(f"duplicate prioritized task: {match.group(1).strip()}")
        names.add(title)
        task_body = prioritized[match.start() :]
        next_match = re.search(r"(?m)^###\s+", task_body[1:])
        if next_match:
            task_body = task_body[: next_match.start() + 1]
        for section in REQUIRED_TASK_SECTIONS:
            if not re.search(rf"(?m)^{re.escape(section)}:\s*$", task_body):
                errors.append(f"{match.group(1).strip()}: missing `{section}:`")
    if strict and re.search(r"\b(TODO|TBD|FIXME|\?\?\?)\b", text):
        errors.append("FUTURE.md contains unresolved scaffold placeholder")
    return errors


def validate(root: Path, strict: bool = False) -> dict[str, object]:
    errors: list[str] = []
    if not root.exists() or not root.is_dir():
        return {"ok": False, "errors": [f"invalid target path: {root}"]}
    for name in REQUIRED_ROOT:
        if not (root / name).is_file():
            errors.append(f"missing root file: {name}")
    docs = root / "Documents"
    for name in REQUIRED_DOCS:
        if not (docs / name).is_file():
            errors.append(f"missing document: Documents/{name}")
    for path in root.glob("**/*.md"):
        rel = path.relative_to(root).as_posix()
        if ".snapshot-" in path.name or "snapshot" in path.stem.lower() and path.parent == docs:
            errors.append(f"snapshot marker in live markdown filename: {rel}")
        text = read(path)
        if strict and re.search(r"\b(TODO|TBD|FIXME|\?\?\?)\b", text):
            errors.append(f"placeholder in {rel}")
        for link in find_markdown_links(text):
            clean = link.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"broken relative link in {rel}: {link}")
        for claim in re.findall(r"`(/[^`]+)`", text):
            if claim.startswith(str(root)):
                errors.append(f"absolute local path claim in {rel}: {claim}")
    errors.extend(validate_future(docs / "FUTURE.md", strict))
    return {"ok": not errors, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    result = validate(args.target, args.strict)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(f"valid documentation contract: {args.target}")
    else:
        for error in result["errors"]:
            print(f"error: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
