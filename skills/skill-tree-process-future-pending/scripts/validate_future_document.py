#!/usr/bin/env python3
"""Validate FUTURE.md queue structure and prioritized task contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

QUEUE_ORDER = ["Pending Queue", "Prioritized Next Changes", "Backlog"]
REQUIRED_SECTIONS = [
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
VALID_STATUSES = {"Ready", "Blocked pending answers"}


@dataclass
class Task:
    title: str
    line: int
    body: str


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFC", value)
    text = re.sub(r"\s+", " ", text.strip())
    return text.casefold()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def heading_level(line: str) -> int:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    return len(match.group(1)) if match else 0


def heading_text(line: str) -> str:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    return match.group(2).strip() if match else ""


def find_queue_ranges(lines: list[str]) -> tuple[dict[str, tuple[int, int]], list[str]]:
    found: list[tuple[str, int]] = []
    errors: list[str] = []
    for index, line in enumerate(lines):
        if heading_level(line) == 2 and heading_text(line) in QUEUE_ORDER:
            found.append((heading_text(line), index))

    names = [name for name, _ in found]
    for required in QUEUE_ORDER:
        if required not in names:
            errors.append(f"missing queue: {required}")
    if len(names) != len(set(names)):
        errors.append("duplicate queue heading")
    if [name for name in names if name in QUEUE_ORDER] != QUEUE_ORDER:
        errors.append("queue order must be Pending Queue, Prioritized Next Changes, Backlog")

    ranges: dict[str, tuple[int, int]] = {}
    for i, (name, start) in enumerate(found):
        end = found[i + 1][1] if i + 1 < len(found) else len(lines)
        ranges[name] = (start, end)
    return ranges, errors


def parse_prioritized_tasks(text: str) -> tuple[list[Task], list[str]]:
    lines = text.splitlines()
    ranges, errors = find_queue_ranges(lines)
    if "Prioritized Next Changes" not in ranges:
        return [], errors
    start, end = ranges["Prioritized Next Changes"]
    tasks: list[Task] = []
    current_title: str | None = None
    current_line = 0
    current_body: list[str] = []
    for index in range(start + 1, end):
        line = lines[index]
        if heading_level(line) == 3:
            if current_title is not None:
                tasks.append(Task(current_title, current_line, "\n".join(current_body).rstrip() + "\n"))
            current_title = heading_text(line)
            current_line = index + 1
            current_body = [line]
        elif current_title is not None:
            current_body.append(line)
        elif line.strip().startswith("- ") or heading_level(line) > 3:
            errors.append(f"content before prioritized task heading at line {index + 1}")
    if current_title is not None:
        tasks.append(Task(current_title, current_line, "\n".join(current_body).rstrip() + "\n"))
    return tasks, errors


def validate_task(task: Task, strict: bool) -> list[str]:
    errors: list[str] = []
    body = task.body
    for section in REQUIRED_SECTIONS:
        pattern = rf"(?m)^{re.escape(section)}:\s*$"
        if not re.search(pattern, body):
            errors.append(f"{task.title}: missing section `{section}:`")

    status_match = re.search(r"(?m)^Status:\s*(.+?)\s*$", body)
    status = status_match.group(1).strip() if status_match else ""
    if status and status not in VALID_STATUSES:
        errors.append(f"{task.title}: invalid status `{status}`")

    has_blocker = "[Unresolved — blocks implementation]" in body or "[Unresolved - blocks implementation]" in body
    if has_blocker and status != "Blocked pending answers":
        errors.append(f"{task.title}: blocking question requires `Status: Blocked pending answers`")
    if status == "Blocked pending answers" and not has_blocker:
        errors.append(f"{task.title}: blocked status requires a blocking unresolved question")

    if strict:
        placeholders = ["TODO", "TBD", "<placeholder>", "???"]
        for placeholder in placeholders:
            if placeholder in body:
                errors.append(f"{task.title}: unresolved placeholder `{placeholder}`")
    return errors


def validate(path: Path, strict: bool = False) -> dict[str, object]:
    errors: list[str] = []
    if not path.exists():
        return {"ok": False, "errors": [f"file missing: {path}"], "tasks": []}
    text = read(path)
    tasks, parse_errors = parse_prioritized_tasks(text)
    errors.extend(parse_errors)
    if "Implement next" in _backlog_text(text) and "Backlog" in _backlog_text(text):
        errors.append("Backlog must not describe Implement next selection")
    seen: dict[str, Task] = {}
    for task in tasks:
        key = normalize_name(task.title)
        if key in seen:
            errors.append(f"duplicate prioritized task name: {task.title}")
        seen[key] = task
        errors.extend(validate_task(task, strict))
    return {
        "ok": not errors,
        "errors": errors,
        "tasks": [{"title": task.title, "line": task.line} for task in tasks],
    }


def _backlog_text(text: str) -> str:
    lines = text.splitlines()
    ranges, _ = find_queue_ranges(lines)
    if "Backlog" not in ranges:
        return ""
    start, end = ranges["Backlog"]
    return "\n".join(lines[start:end])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("future", type=Path, help="path to FUTURE.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    result = validate(args.future, args.strict)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(f"valid FUTURE.md: {args.future}")
    else:
        for error in result["errors"]:
            print(f"error: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
