#!/usr/bin/env python3
"""Synchronize generated skill files from canonical source documents."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def generated_notice(source: str) -> str:
    return f"""<!--
GENERATED FILE
Source: {source}
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

"""


def generated_python(source: str, text: str) -> str:
    notice = f"""# GENERATED FILE
# Source: {source}
# Generator: scripts/sync_skill_references.py
# Do not edit manually. Update the source file and rerun the generator.

"""
    if text.startswith("#!"):
        shebang, rest = text.split("\n", 1)
        return f"{shebang}\n{notice}{rest}"
    return notice + text


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
    common_dir = root / "common/references"
    common_future = read_text(common_dir / "FUTURE_WORKFLOW.md")
    common_pending = read_text(common_dir / "PENDING_TASK_FORMAT.md")
    common_contract = read_text(common_dir / "DOCUMENTATION_OUTPUT_CONTRACT.md")
    common_discovery = read_text(common_dir / "REPOSITORY_DISCOVERY_CHECKLIST.md")
    common_snapshot = read_text(common_dir / "SNAPSHOT_RULES.md")
    common_scripts = root / "common/scripts"
    future_validator = read_text(common_scripts / "validate_future_document.py")
    task_selector = read_text(common_scripts / "select_prioritized_task.py")
    unity_pending = extract_section(source, PENDING_TEMPLATE_START, PENDING_TEMPLATE_END)
    return {
        root / "skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md": source,
        root / "skills/skill-tree-unity-repo-documentation/references/COMMON_DOCUMENTATION_OUTPUT_CONTRACT.md": generated_notice("common/references/DOCUMENTATION_OUTPUT_CONTRACT.md")
        + common_contract,
        root / "skills/skill-tree-unity-repo-documentation/references/COMMON_REPOSITORY_DISCOVERY_CHECKLIST.md": generated_notice("common/references/REPOSITORY_DISCOVERY_CHECKLIST.md")
        + common_discovery,
        root / "skills/skill-tree-repo-documentation/references/DOCUMENTATION_OUTPUT_CONTRACT.md": generated_notice("common/references/DOCUMENTATION_OUTPUT_CONTRACT.md")
        + common_contract,
        root / "skills/skill-tree-repo-documentation/references/REPOSITORY_DISCOVERY_CHECKLIST.md": generated_notice("common/references/REPOSITORY_DISCOVERY_CHECKLIST.md")
        + common_discovery,
        root / "skills/skill-tree-repo-documentation/references/PENDING_TASK_FORMAT.md": generated_notice("common/references/PENDING_TASK_FORMAT.md")
        + common_pending,
        root / "skills/skill-tree-repo-documentation-audit/references/DOCUMENTATION_OUTPUT_CONTRACT.md": generated_notice("common/references/DOCUMENTATION_OUTPUT_CONTRACT.md")
        + common_contract,
        root / "skills/skill-tree-repo-documentation-audit/references/REPOSITORY_DISCOVERY_CHECKLIST.md": generated_notice("common/references/REPOSITORY_DISCOVERY_CHECKLIST.md")
        + common_discovery,
        root / "skills/skill-tree-repo-documentation-audit/references/PENDING_TASK_FORMAT.md": generated_notice("common/references/PENDING_TASK_FORMAT.md")
        + common_pending,
        root / "skills/skill-tree-unity-repo-documentation-audit/references/COMMON_DOCUMENTATION_OUTPUT_CONTRACT.md": generated_notice("common/references/DOCUMENTATION_OUTPUT_CONTRACT.md")
        + common_contract,
        root / "skills/skill-tree-unity-repo-documentation-audit/references/COMMON_REPOSITORY_DISCOVERY_CHECKLIST.md": generated_notice("common/references/REPOSITORY_DISCOVERY_CHECKLIST.md")
        + common_discovery,
        root / "skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md": generated_notice("common/references/FUTURE_WORKFLOW.md")
        + common_future,
        root / "skills/skill-tree-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md": generated_notice("common/references/FUTURE_WORKFLOW.md")
        + common_future,
        root / "skills/skill-tree-process-future-pending/references/PENDING_TASK_FORMAT.md": generated_notice("common/references/PENDING_TASK_FORMAT.md")
        + common_pending,
        root / "skills/skill-tree-implement-next-future-task/references/PENDING_TASK_FORMAT.md": generated_notice("common/references/PENDING_TASK_FORMAT.md")
        + common_pending,
        root / "skills/skill-tree-unity-process-future-pending/references/COMMON_FUTURE_WORKFLOW.md": generated_notice("common/references/FUTURE_WORKFLOW.md")
        + common_future,
        root / "skills/skill-tree-unity-implement-next-future-task/references/COMMON_FUTURE_WORKFLOW.md": generated_notice("common/references/FUTURE_WORKFLOW.md")
        + common_future,
        root / "skills/skill-tree-unity-process-future-pending/references/PENDING_TASK_FORMAT.md": generated_notice("REPO_INIT_INSTRUCTIONS.md")
        + unity_pending,
        root / "skills/skill-tree-unity-implement-next-future-task/references/PENDING_TASK_FORMAT.md": generated_notice("REPO_INIT_INSTRUCTIONS.md")
        + unity_pending,
        root / "skills/skill-tree-unity-process-future-pending/references/FUTURE_TASK_STANDARD.md": generated_notice("REPO_INIT_INSTRUCTIONS.md")
        + extract_section(source, FUTURE_START, FUTURE_END),
        root / "skills/skill-tree-unity-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md": generated_notice("REPO_INIT_INSTRUCTIONS.md")
        + extract_section(source, EXECUTION_START, EXECUTION_END),
        root / "skills/skill-tree-unity-repo-documentation-audit/references/PENDING_TASK_FORMAT.md": generated_notice("REPO_INIT_INSTRUCTIONS.md")
        + unity_pending,
        root / "skills/skill-tree-create-documents-snapshot/references/SNAPSHOT_RULES.md": generated_notice("common/references/SNAPSHOT_RULES.md")
        + common_snapshot,
        root / "skills/skill-tree-unity-create-documents-snapshot/references/SNAPSHOT_RULES.md": generated_notice("common/references/SNAPSHOT_RULES.md")
        + common_snapshot,
        root / "skills/skill-tree-process-future-pending/scripts/validate_future_document.py": generated_python("common/scripts/validate_future_document.py", future_validator),
        root / "skills/skill-tree-unity-process-future-pending/scripts/validate_future_document.py": generated_python("common/scripts/validate_future_document.py", future_validator),
        root / "skills/skill-tree-implement-next-future-task/scripts/select_prioritized_task.py": generated_python("common/scripts/select_prioritized_task.py", task_selector),
        root / "skills/skill-tree-unity-implement-next-future-task/scripts/select_prioritized_task.py": generated_python("common/scripts/select_prioritized_task.py", task_selector),
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
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
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
