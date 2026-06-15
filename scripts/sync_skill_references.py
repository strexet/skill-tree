#!/usr/bin/env python3
"""Synchronize generated skill references from REPO_INIT_INSTRUCTIONS.md."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

NOTICE = """<!--
GENERATED FILE
Source: REPO_INIT_INSTRUCTIONS.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

"""

FUTURE_START = "## 14. Document Specification — `Documents/FUTURE.md`"
FUTURE_END = "## 15. Document Specification — `Documents/RULES.md`"
EXECUTION_START = "### 14.4 Command semantics"
EXECUTION_END = "## 15. Document Specification — `Documents/RULES.md`"
PENDING_TEMPLATE_START = "### 14.8 Pending item template"
PENDING_TEMPLATE_END = "### 14.9 Task lifecycle"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def find_unique_heading(text: str, heading: str) -> int:
    needle = heading + "\n"
    positions: list[int] = []
    start = 0
    while True:
        pos = text.find(needle, start)
        if pos == -1:
            break
        if pos == 0 or text[pos - 1] == "\n":
            positions.append(pos)
        start = pos + len(needle)
    if not positions:
        raise ValueError(f"Missing heading: {heading}")
    if len(positions) > 1:
        raise ValueError(f"Ambiguous heading: {heading}")
    return positions[0]


def extract_section(text: str, start_heading: str, end_heading: str) -> str:
    start = find_unique_heading(text, start_heading)
    end = find_unique_heading(text, end_heading)
    if end <= start:
        raise ValueError(f"Heading order invalid: {start_heading} before {end_heading}")
    return text[start:end].rstrip() + "\n"


def expected_outputs(root: Path) -> dict[Path, str]:
    source = read_text(root / "REPO_INIT_INSTRUCTIONS.md")
    return {
        root / "skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md": source,
        root / "skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md": NOTICE
        + extract_section(source, FUTURE_START, FUTURE_END),
        root / "skills/skill-tree-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md": NOTICE
        + extract_section(source, EXECUTION_START, EXECUTION_END),
        root / "skills/skill-tree-unity-repo-documentation-audit/references/PENDING_TASK_FORMAT.md": NOTICE
        + extract_section(source, PENDING_TEMPLATE_START, PENDING_TEMPLATE_END),
    }


def check(outputs: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            errors.append(f"missing: {path}")
            continue
        actual = read_text(path)
        if actual != expected:
            errors.append(f"stale: {path}")
            diff = difflib.unified_diff(
                actual.splitlines(),
                expected.splitlines(),
                fromfile=str(path),
                tofile=f"{path} (expected)",
                lineterm="",
            )
            errors.extend(list(diff)[:40])
    return errors


def write(outputs: dict[Path, str]) -> None:
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated references are stale")
    args = parser.parse_args(argv)

    try:
        outputs = expected_outputs(repo_root())
        if args.check:
            errors = check(outputs)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print("skill references current")
            return 0
        write(outputs)
        print("skill references synchronized")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
