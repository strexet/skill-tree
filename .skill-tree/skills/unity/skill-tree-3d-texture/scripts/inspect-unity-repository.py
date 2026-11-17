#!/usr/bin/env python3
"""Read-only inventory for Unity repositories."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

TRANSIENT_DIRS = {
    ".git",
    "Library",
    "Temp",
    "Obj",
    "Logs",
    "Build",
    "Builds",
    "UserSettings",
    "MemoryCaptures",
    "Recordings",
    ".gradle",
    "DerivedData",
    "node_modules",
    "__pycache__",
}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def walk_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in TRANSIENT_DIRS and not name.startswith(".tmp")]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            if any(path.match(pattern) for pattern in patterns):
                found.append(path)
    return sorted(found)


def git_status(root: Path) -> dict[str, object]:
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        return {"root": top, "status": status}
    except (OSError, subprocess.CalledProcessError):
        return {"root": None, "status": []}


def unity_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in TRANSIENT_DIRS]
        current = Path(dirpath)
        if (current / "Assets").is_dir() and (current / "Packages").is_dir() and (current / "ProjectSettings").is_dir():
            roots.append(current)
            dirnames[:] = []
    return sorted(roots)


def read_small(path: Path, limit: int = 4096) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def todo_counts(root: Path) -> dict[str, int]:
    counts = {"TODO": 0, "FIXME": 0, "HACK": 0}
    for path in walk_files(root, ("*.cs", "*.asmdef", "*.asmref", "*.json", "*.md", "*.yaml", "*.yml")):
        text = read_small(path, 200000)
        for key in counts:
            counts[key] += text.count(key)
    return counts


def inventory(root: Path) -> dict[str, object]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"invalid target path: {root}")
    roots = unity_roots(root)
    transient_present = sorted([name for name in TRANSIENT_DIRS if (root / name).exists()])
    versions = []
    for unity_root in roots:
        version_path = unity_root / "ProjectSettings/ProjectVersion.txt"
        versions.append({"root": rel(unity_root, root), "ProjectVersion.txt": read_small(version_path).strip()})
    return {
        "target": str(root.resolve()),
        "git": git_status(root),
        "unityRoots": [rel(path, root) for path in roots],
        "unityVersions": versions,
        "packages": [rel(path, root) for path in walk_files(root, ("Packages/manifest.json", "Packages/packages-lock.json"))],
        "assemblies": [rel(path, root) for path in walk_files(root, ("*.asmdef", "*.asmref"))],
        "scenes": [rel(path, root) for path in walk_files(root, ("*.unity",))],
        "serializedAssets": [rel(path, root) for path in walk_files(root, ("*.prefab", "*.asset"))[:200]],
        "nativePluginDirs": [rel(path, root) for path in [root / "Assets/Plugins/Android", root / "Assets/Plugins/iOS"] if path.exists()],
        "buildScripts": [rel(path, root) for path in walk_files(root, ("*.cs", "*.sh", "*.ps1", "*.yml", "*.yaml")) if "build" in path.name.lower() or "ci" in path.name.lower()],
        "ciFiles": [rel(path, root) for path in walk_files(root, (".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml", "Jenkinsfile"))],
        "markdown": [rel(path, root) for path in walk_files(root, ("*.md",))],
        "transientDirectoriesPresent": transient_present,
        "todoCounts": todo_counts(root),
    }


def render_markdown(data: dict[str, object]) -> str:
    lines = ["# Unity Repository Inventory", ""]
    for key, value in data.items():
        lines.append(f"## {key}")
        if isinstance(value, list):
            if not value:
                lines.append("- None found")
            else:
                for item in value:
                    lines.append(f"- `{item}`")
        elif isinstance(value, dict):
            lines.append("```json")
            lines.append(json.dumps(value, indent=2, sort_keys=True))
            lines.append("```")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="repository path to inspect")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = inventory(args.target.resolve())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    output = json.dumps(data, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(data)
    if args.output:
        args.output.write_text(output, encoding="utf-8", newline="\n")
    else:
        print(output, end="" if output.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
