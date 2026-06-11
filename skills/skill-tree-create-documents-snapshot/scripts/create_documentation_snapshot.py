#!/usr/bin/env python3
"""Create explicit-request-only Markdown documentation snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EXCLUDE_PARTS = {"Library", "Temp", "Obj", "Logs", "Build", "Builds", "UserSettings", "node_modules", ".git"}


def repo_name(root: Path) -> str:
    return root.resolve().name


def tracked_markdown(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        return [root / line for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.CalledProcessError):
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in EXCLUDE_PARTS]
            for filename in filenames:
                if filename.endswith(".md"):
                    files.append(Path(dirpath) / filename)
        return sorted(files)


def relevant(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    if rel in {"README.md", "AGENTS.md"} or rel.startswith("Documents/"):
        return True
    text = path.read_text(encoding="utf-8", errors="replace")[:20000].lower()
    keywords = ["unity", "architecture", "feature", "future", "build", "test", "dependency", "agent"]
    return any(keyword in text for keyword in keywords)


def member_name(path: Path, root: Path, stamp: str, used: set[str]) -> str:
    rel = path.relative_to(root).as_posix()
    stem = path.stem if path.name == rel else rel.replace("/", "__").removesuffix(".md")
    name = f"{stem}.snapshot-{stamp}.md"
    counter = 2
    while name in used:
        name = f"{stem}.{counter}.snapshot-{stamp}.md"
        counter += 1
    used.add(name)
    return name


def snapshot_notice(source: str, name: str, stamp: str) -> str:
    date, time = stamp.rsplit("-", 1)[0], stamp.rsplit("-", 1)[1]
    return f"""<!--
SNAPSHOT DOCUMENT
Snapshot date: {date}
Snapshot time: {time}
Original source path: {source}
Archive file name: {name}
Relevance check: Included after confirming that the source contains repository-specific Unity project, architecture, feature, build, test, dependency, platform, implementation-plan, or AI-agent workflow information.
Snapshot warning: This is a dated copy for AI-agent context. The live repository document, Unity project state, packages, serialized assets, and implementation may drift after this snapshot. Check the live source path and current repository before changing behavior.
-->

"""


def create(root: Path, output: Path | None, dry_run: bool) -> tuple[Path, list[str]]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"invalid target path: {root}")
    now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    candidates = [path for path in tracked_markdown(root) if not any(part in EXCLUDE_PARTS for part in path.parts)]
    included = [path for path in candidates if path.exists() and relevant(path, root)]
    archive = output or (root / f"{repo_name(root)}-documents-snapshot-{now}.zip")
    report = [path.relative_to(root).as_posix() for path in included]
    if dry_run:
        return archive, report
    used: set[str] = set()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staged: list[Path] = []
        for path in included:
            rel = path.relative_to(root).as_posix()
            name = member_name(path, root, now, used)
            target = tmp_path / name
            target.write_text(snapshot_notice(rel, name, now) + path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            staged.append(target)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for path in staged:
                zip_file.write(path, path.name)
    with zipfile.ZipFile(archive, "r") as zip_file:
        for info in zip_file.infolist():
            if "/" in info.filename:
                raise ValueError(f"archive member is not at zip root: {info.filename}")
            content = zip_file.read(info.filename).decode("utf-8", errors="replace")
            if not content.startswith("<!--\nSNAPSHOT DOCUMENT"):
                raise ValueError(f"archive member lacks snapshot notice: {info.filename}")
    return archive, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        archive, report = create(args.target.resolve(), args.output, args.dry_run)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"archive: {archive}")
    print(f"included: {len(report)}")
    for item in report:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
