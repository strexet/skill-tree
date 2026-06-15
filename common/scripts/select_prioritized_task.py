#!/usr/bin/env python3
"""Select one task from FUTURE.md Prioritized Next Changes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

EXIT_FILE_MISSING = 2
EXIT_SECTION_MISSING = 3
EXIT_NO_TASKS = 4
EXIT_NAMED_ABSENT = 5
EXIT_DUPLICATE = 6
EXIT_MALFORMED = 7
EXIT_BLOCKED = 8


@dataclass
class Task:
    title: str
    line: int
    body: str
    blocked: bool


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFC", value)
    text = re.sub(r"\s+", " ", text.strip())
    return text.casefold()


def heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def prioritized_range(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        parsed = heading(line)
        if parsed == (2, "Prioritized Next Changes"):
            start = index
            continue
        if start is not None and parsed and parsed[0] == 2:
            return start, index
    return (start, len(lines)) if start is not None else None


def parse_tasks(text: str) -> tuple[list[Task], bool]:
    lines = text.splitlines()
    section = prioritized_range(lines)
    if section is None:
        return [], False
    start, end = section
    tasks: list[Task] = []
    current_title: str | None = None
    current_line = 0
    current_body: list[str] = []
    malformed = False
    for index in range(start + 1, end):
        parsed = heading(lines[index])
        if parsed and parsed[0] == 3:
            if current_title is not None:
                body = "\n".join(current_body).rstrip() + "\n"
                tasks.append(Task(current_title, current_line, body, is_blocked(body)))
            current_title = parsed[1]
            current_line = index + 1
            current_body = [lines[index]]
        elif current_title is not None:
            current_body.append(lines[index])
        elif lines[index].strip() and not lines[index].strip().startswith("<!--"):
            malformed = True
    if current_title is not None:
        body = "\n".join(current_body).rstrip() + "\n"
        tasks.append(Task(current_title, current_line, body, is_blocked(body)))
    for task in tasks:
        if "Questions and required clarifications:" not in task.body:
            malformed = True
    return tasks, not malformed


def is_blocked(body: str) -> bool:
    return (
        "Status: Blocked pending answers" in body
        or "[Unresolved — blocks implementation]" in body
        or "[Unresolved - blocks implementation]" in body
    )


def select_task(path: Path, name: str | None) -> tuple[int, dict[str, object]]:
    if not path.exists():
        return EXIT_FILE_MISSING, {"ok": False, "error": f"file missing: {path}"}
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if prioritized_range(text.splitlines()) is None:
        return EXIT_SECTION_MISSING, {"ok": False, "error": "Prioritized Next Changes section missing"}
    tasks, well_formed = parse_tasks(text)
    if not tasks:
        return EXIT_NO_TASKS, {"ok": False, "error": "no prioritized tasks"}
    if not well_formed:
        return EXIT_MALFORMED, {"ok": False, "error": "malformed prioritized task"}
    selected: Task
    if name is None:
        selected = tasks[0]
    else:
        key = normalize_name(name)
        matches = [task for task in tasks if normalize_name(task.title) == key]
        if not matches:
            return EXIT_NAMED_ABSENT, {"ok": False, "error": "named task not found in Prioritized Next Changes"}
        if len(matches) > 1:
            return EXIT_DUPLICATE, {"ok": False, "error": "duplicate normalized prioritized task names"}
        selected = matches[0]
    if selected.blocked:
        return EXIT_BLOCKED, {
            "ok": False,
            "error": "selected task has blocking unresolved questions",
            "title": selected.title,
            "line": selected.line,
            "body": selected.body,
        }
    return 0, {"ok": True, "title": selected.title, "line": selected.line, "body": selected.body}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("future", type=Path, help="path to FUTURE.md")
    parser.add_argument("--name", help="prioritized task title to select")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    code, result = select_task(args.future, args.name)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("ok"):
        print(result["body"], end="")
    else:
        print(f"error: {result['error']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
