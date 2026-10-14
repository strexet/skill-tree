#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/create-documentation-snapshot.py; generator: skill-tree/scripts/sync-skill-references.py
"""Create explicit-request-only Markdown documentation snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EXCLUDE_PARTS = {"Library", "Temp", "Obj", "Logs", "Build", "Builds", "UserSettings", "node_modules", ".git", "artifacts", "history", "vendor", "Packages", "packages", "ThirdParty", "third-party", ".agents", ".claude", ".codex"}


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
    if rel in {"README.md", "AGENTS.md"} or rel.startswith("skill-tree/documents/"):
        return True
    text = path.read_text(encoding="utf-8", errors="replace")[:20000].lower()
    keywords = ["architecture", "feature", "future", "build", "test", "dependency", "agent", "project"]
    return "generated file" not in text[:500] and any(keyword in text for keyword in keywords)


def member_name(path: Path, root: Path, stamp: str, duplicate_basenames: set[str], used: set[str], style: str = 'kebab') -> str:
    rel = path.relative_to(root).as_posix()
    stem = rel.removesuffix(".md") if path.name in duplicate_basenames else path.stem
    if style == 'dotted':
        stem = stem.replace('/', '__')
        separator = '.snapshot-'
    else:
        stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        separator = '-snapshot-'
    name = f"{stem}{separator}{stamp}.md"
    counter = 2
    while name.casefold() in used:
        name = f"{stem}-{counter}{separator}{stamp}.md"
        counter += 1
    used.add(name.casefold())
    return name


def candidates(root: Path, include: list[str] | None) -> list[Path]:
    def permitted(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            return False
        return path.suffix == '.md' and not any(part in EXCLUDE_PARTS for part in path.relative_to(root).parts)
    tracked = sorted(path for path in tracked_markdown(root) if path.is_file() and permitted(path))
    if include is None:
        return [path for path in tracked if relevant(path, root)]
    selected = set()
    for selection in include:
        path = Path(selection)
        path = path if path.is_absolute() else root / path
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"snapshot scope escapes repository: {selection}")
        # Normalize lexical paths before exclusion checks; symlink escape checks use resolved paths above.
        path = root / Path(os.path.relpath(path, root))
        if path.is_file():
            if not permitted(path):
                raise ValueError(f"snapshot scope requires permitted Markdown: {selection}")
            selected.add(path)  # Explicitly selected new files need not be tracked yet.
        elif path.is_dir():
            if any(part in EXCLUDE_PARTS for part in path.relative_to(root).parts):
                raise ValueError(f"snapshot scope is excluded: {selection}")
            members = [candidate for candidate in tracked if candidate.is_relative_to(path) and relevant(candidate, root)]
            if not members:
                raise ValueError(f"snapshot directory has no relevant Markdown: {selection}")
            selected.update(members)
        else:
            raise ValueError(f"snapshot scope does not exist: {selection}")
    if not selected:
        raise ValueError('snapshot scope requires at least one Markdown document')
    return sorted(selected)


def snapshot_notice(source: str, name: str, stamp: str) -> str:
    date, time = stamp[:10], stamp[11:]
    return f"""<!--
SNAPSHOT DOCUMENT
Snapshot date: {date}
Snapshot time: {time}
Original source path: {source}
Archive file name: {name}
Relevance check: Included after confirming that the source contains repository-specific project, architecture, feature, build, test, dependency, platform, implementation-plan, or AI-agent workflow information.
Snapshot warning: The snapshot is a dated copy for AI-agent context. The live repository document, project state, dependencies, generated files, and implementation may drift after snapshot creation. Check the live source path and current repository before changing behavior.
-->

"""


def create(root: Path, output: Path | None, dry_run: bool, *, include: list[str] | None = None, member_style: str = 'kebab', output_dir: str = 'artifacts', timestamp: str | None = None) -> tuple[Path, list[str]]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"invalid target path: {root}")
    if member_style not in {'kebab', 'dotted'} or output_dir not in {'artifacts', 'root'}:
        raise ValueError('unsupported snapshot naming/output policy')
    now = timestamp or dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{2}-\d{2}', now):
        raise ValueError('timestamp requires YYYY-MM-DD-HH-MM')
    dt.datetime.strptime(now, '%Y-%m-%d-%H-%M')
    included = candidates(root, include)
    safe_name = re.sub(r"[^a-z0-9]+", "-", repo_name(root).lower()).strip("-") or "repository"
    destination = root if output_dir == 'root' else root / 'skill-tree/artifacts'
    archive = output or (destination / f"{safe_name}-documents-snapshot-{now}.zip")
    if archive.suffix.lower() != '.zip':
        raise ValueError('snapshot archive requires a .zip output path')
    report = [path.relative_to(root).as_posix() for path in included]
    if dry_run:
        return archive, report
    if archive.exists():
        raise ValueError('snapshot archive exists; choose another output path')
    used: set[str] = set()
    basename_counts: dict[str, int] = {}
    for path in included:
        basename_counts[path.name] = basename_counts.get(path.name, 0) + 1
    duplicate_basenames = {name for name, count in basename_counts.items() if count > 1}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staged: list[Path] = []
        for path in included:
            rel = path.relative_to(root).as_posix()
            name = member_name(path, root, now, duplicate_basenames, used, member_style)
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
    parser.add_argument("--include", nargs='+', action='append', help='Select Markdown files or directories; repeat to combine scopes')
    parser.add_argument("--member-style", choices=['kebab', 'dotted'], default='kebab')
    parser.add_argument("--output-dir", choices=['artifacts', 'root'], default='artifacts')
    parser.add_argument("--timestamp", help='Explicit snapshot timestamp in YYYY-MM-DD-HH-MM')
    args = parser.parse_args(argv)
    try:
        include = [selection for group in args.include for selection in group] if args.include is not None else None
        archive, report = create(args.target.resolve(), args.output, args.dry_run, include=include, member_style=args.member_style, output_dir=args.output_dir, timestamp=args.timestamp)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"archive: {archive}")
    print(f"included: {len(report)}")
    for item in report:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
