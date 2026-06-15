#!/usr/bin/env python3
"""Validate the Unity repository skills source tree."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT_FILES = [
    ".editorconfig",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "INSTALL.md",
    "README.md",
    "REPO_INIT_INSTRUCTIONS.md",
    "SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md",
    "LICENSE",
    "install.sh",
    "install.ps1",
    "package.json",
    "bin/install.js",
    "config/providers.json",
    "docs/AGENT_COMPATIBILITY.md",
    "docs/INSTALLATION_ARCHITECTURE.md",
    "docs/MIGRATION.md",
    "docs/SECURITY.md",
    "src/init-rules/unity-repository-skills.md",
]
SKILLS = {
    "skill-tree-unity-repo-documentation": {
        "references": [
            "REPO_INIT_INSTRUCTIONS.md",
            "DOCUMENTATION_OUTPUT_CONTRACT.md",
            "UNITY_DISCOVERY_CHECKLIST.md",
        ],
        "scripts": [
            "inspect_unity_repository.py",
            "validate_unity_documentation.py",
        ],
    },
    "skill-tree-create-documents-snapshot": {
        "references": ["SNAPSHOT_RULES.md"],
        "scripts": ["create_documentation_snapshot.py"],
    },
    "skill-tree-process-future-pending": {
        "references": ["FUTURE_TASK_STANDARD.md", "PENDING_PROCESSING_CHECKLIST.md"],
        "scripts": ["validate_future_document.py"],
    },
    "skill-tree-implement-next-future-task": {
        "references": ["FUTURE_EXECUTION_RULES.md", "IMPLEMENTATION_HANDOFF_CHECKLIST.md"],
        "scripts": ["select_prioritized_task.py"],
    },
    "skill-tree-unity-repo-documentation-audit": {
        "references": ["PENDING_TASK_FORMAT.md"],
        "scripts": [],
    },
}
DISPLAY_NAMES = {
    "skill-tree-unity-repo-documentation": "Skill-Tree: Initialize Documents",
    "skill-tree-unity-repo-documentation-audit": "Skill-Tree: Audit Documents",
    "skill-tree-process-future-pending": "Skill-Tree: Process Pending Tasks",
    "skill-tree-implement-next-future-task": "Skill-Tree: Implement Next Task",
    "skill-tree-create-documents-snapshot": "Skill-Tree: Create Snapshot",
}
ADAPTERS = ["codex", "claude-code", "gemini-cli", "github-copilot", "cursor", "windsurf", "cline", "generic"]


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = read(path)
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields, text[end + 5 :]


def check_structure(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel in ROOT_FILES:
        if not (repo / rel).exists():
            errors.append(f"missing required file: {rel}")
    for adapter in ADAPTERS:
        if not (repo / "adapters" / adapter / "README.md").is_file():
            errors.append(f"missing adapter README: {adapter}")
    for rel in ["tests/README.md", "tests/test_installer.js", "tests/test_provider_matrix.js"]:
        if not (repo / rel).exists():
            errors.append(f"missing test file: {rel}")
    try:
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        tracked = []
    for rel in tracked:
        parts = Path(rel).parts
        if "__pycache__" in parts or rel.endswith(".pyc"):
            errors.append(f"committed cache file: {rel}")
    for path in repo.rglob("*"):
        if path.is_file() and re.search(r"snapshot-\d{4}-\d{2}-\d{2}", path.name):
            errors.append(f"snapshot-named live file: {path.relative_to(repo)}")
    return errors


def check_skills(repo: Path) -> list[str]:
    errors: list[str] = []
    for name, required in SKILLS.items():
        if not name.startswith("skill-tree-"):
            errors.append(f"{name}: missing skill-tree- prefix")
        skill_dir = repo / "skills" / name
        if not skill_dir.is_dir():
            errors.append(f"missing skill folder: {name}")
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"missing SKILL.md: {name}")
            continue
        fields, body = parse_frontmatter(skill_file)
        if fields.get("name") != name:
            errors.append(f"{name}: frontmatter name mismatch")
        if not fields.get("description"):
            errors.append(f"{name}: missing description")
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", name):
            errors.append(f"{name}: invalid kebab-case name")
        for ref in required["references"]:
            if not (skill_dir / "references" / ref).is_file():
                errors.append(f"{name}: missing reference {ref}")
        for script in required["scripts"]:
            if not (skill_dir / "scripts" / script).is_file():
                errors.append(f"{name}: missing script {script}")
        for rel in re.findall(r"(references/[A-Za-z0-9_.\-/]+|scripts/[A-Za-z0-9_.\-/]+)", body):
            if not (skill_dir / rel).exists():
                errors.append(f"{name}: referenced local resource missing: {rel}")
        text = read(skill_file)
        if "/Users/" in text or "\\Users\\" in text:
            errors.append(f"{name}: absolute machine path in SKILL.md")
        if "../" in text:
            errors.append(f"{name}: possible sibling/root dependency in SKILL.md")
        expected_display = DISPLAY_NAMES.get(name)
        openai_yaml = skill_dir / "agents" / "openai.yaml"
        if expected_display:
            if f"# {expected_display}" not in text:
                errors.append(f"{name}: H1 display name mismatch")
            if not openai_yaml.is_file():
                errors.append(f"{name}: missing agents/openai.yaml")
            elif f'display_name: "{expected_display}"' not in read(openai_yaml):
                errors.append(f"{name}: openai display name mismatch")
    for skill_dir in sorted((repo / "skills").iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file() and not skill_dir.name.startswith("skill-tree-"):
            errors.append(f"{skill_dir.name}: canonical skill missing skill-tree- prefix")
    return errors


def check_sync(repo: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, "scripts/sync_skill_references.py", "--check"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    return [] if result.returncode == 0 else ["reference synchronization drift", result.stderr.strip()]


def check_providers(repo: Path) -> list[str]:
    errors: list[str] = []
    data = json.loads(read(repo / "config/providers.json"))
    providers = data.get("providers", [])
    ids = [provider.get("id") for provider in providers]
    if len(ids) != len(set(ids)):
        errors.append("duplicate provider id")
    by_id = {provider["id"]: provider for provider in providers}
    for provider_id in data.get("tier1Required", []):
        if provider_id not in by_id:
            errors.append(f"missing Tier 1 provider: {provider_id}")
    for provider in providers:
        ident = provider.get("id", "")
        if not ident or not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", ident):
            errors.append(f"invalid provider id: {ident}")
        if not provider.get("skillsProfile"):
            errors.append(f"{ident}: missing skillsProfile")
        if provider.get("tier") == 1 and not provider.get("officialDocs"):
            errors.append(f"{ident}: Tier 1 missing official docs")
        detect = provider.get("detect", [])
        directory_only = bool(detect) and all(item.get("kind") == "directory" for item in detect)
        if directory_only and not provider.get("soft"):
            errors.append(f"{ident}: directory-only probe must be soft")
        if provider.get("soft") is True and ident in {"claude-code", "codex", "gemini-cli"}:
            errors.append(f"{ident}: core command provider should not be soft")
    text = read(repo / "bin/install.js")
    if "claude-code" in text and "providers.json" not in text:
        errors.append("installer appears to hard-code provider data")
    return errors


def check_python_scripts(repo: Path) -> list[str]:
    errors: list[str] = []
    absolute_home_pattern = re.compile(r"/Users/[A-Za-z0-9_.-]+")
    for path in sorted(repo.rglob("*.py")):
        rel = path.relative_to(repo)
        text = read(path)
        try:
            ast.parse(text, filename=str(rel))
        except SyntaxError as exc:
            errors.append(f"{rel}: syntax error {exc}")
        if "if __name__ == \"__main__\"" not in text:
            errors.append(f"{rel}: missing guarded entry point")
        if "main(" not in text:
            errors.append(f"{rel}: missing main()")
        if re.search(r"^\s*import\s+(requests|yaml|click|pytest)\b", text, re.MULTILINE):
            errors.append(f"{rel}: third-party import")
        if absolute_home_pattern.search(text):
            errors.append(f"{rel}: hard-coded local path")
    return errors


def check_behavior(repo: Path) -> list[str]:
    errors: list[str] = []
    process = read(repo / "skills/skill-tree-process-future-pending/SKILL.md")
    implement = read(repo / "skills/skill-tree-implement-next-future-task/SKILL.md")
    doc = read(repo / "skills/skill-tree-unity-repo-documentation/SKILL.md")
    audit = read(repo / "skills/skill-tree-unity-repo-documentation-audit/SKILL.md")
    snapshot = read(repo / "skills/skill-tree-create-documents-snapshot/SKILL.md")
    if "Do not implement" not in process:
        errors.append("process skill does not explicitly forbid implementation")
    if "MUST NOT process pending work from `FUTURE.md` alone" not in process:
        errors.append("process skill does not forbid FUTURE-only processing")
    if "Questions and required clarifications" not in process:
        errors.append("process skill does not require questions")
    if "Never select from Pending Queue or Backlog" not in implement:
        errors.append("implement skill does not forbid Backlog/Pending selection")
    if "MUST NOT implement from `FUTURE.md` alone" not in implement:
        errors.append("implement skill does not forbid FUTURE-only implementation")
    if "Stop if absent" not in implement:
        errors.append("implement skill does not stop on missing named task")
    if "blocking unresolved questions" not in implement:
        errors.append("implement skill does not stop on blocking questions")
    if "references/REPO_INIT_INSTRUCTIONS.md" not in doc:
        errors.append("documentation skill does not read source reference")
    if "FEATURES.md` limited to current implemented or partial behavior" not in doc:
        errors.append("documentation skill does not enforce FEATURES/FUTURE split")
    if "meaningful discovered issues" not in doc:
        errors.append("documentation skill does not add discovered issues to FUTURE")
    if "MUST NOT audit docs by comparing documents only" not in audit:
        errors.append("documentation audit skill does not require code-aware audit")
    if "Recreate missing required docs from current repository evidence" not in audit:
        errors.append("documentation audit skill does not recreate missing docs from evidence")
    if "Add meaningful findings to active `FUTURE.md` Backlog" not in audit:
        errors.append("documentation audit skill does not add issues to FUTURE")
    if "Ensure `FUTURE.md` contains `## Pending Task Format` before `## Pending Queue`" not in audit:
        errors.append("documentation audit skill does not repair missing pending task format")
    if "references/PENDING_TASK_FORMAT.md" not in audit:
        errors.append("documentation audit skill does not read pending task format reference")
    if "Do not add documentation/audit findings to Pending Queue" not in doc:
        errors.append("documentation skill does not forbid Pending for discovered findings")
    if "Do not add documentation/audit findings to Pending Queue" not in audit:
        errors.append("documentation audit skill does not forbid Pending for discovered findings")
    if "Do not create or update `Documents/DOCUMENTS_SNAPSHOT.md`" not in snapshot:
        errors.append("snapshot skill does not own snapshot docs boundary")
    if "create_documentation_snapshot.py" not in snapshot:
        errors.append("snapshot skill does not reference snapshot helper")
    return errors


def check_docs(repo: Path, strict: bool) -> list[str]:
    errors: list[str] = []
    placeholder_exempt = {
        "REPO_INIT_INSTRUCTIONS.md",
        "SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md",
        "skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md",
        "skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md",
        "skills/skill-tree-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md",
        "docs/MIGRATION.md",
    }
    for path in sorted(repo.rglob("*.md")):
        rel = path.relative_to(repo).as_posix()
        text = read(path)
        if text.count("```") % 2:
            errors.append(f"{rel}: unbalanced fenced code blocks")
        if re.search(r"/Users/[A-Za-z0-9_.-]+", text):
            errors.append(f"{rel}: absolute local path")
        if strict and rel not in placeholder_exempt and re.search(r"\b(TODO|TBD|FIXME|\?\?\?)\b", text):
            errors.append(f"{rel}: placeholder marker")
    package = json.loads(read(repo / "package.json"))
    if package.get("license") != "MIT":
        errors.append("package.json license must be MIT")
    return errors


def validate(strict: bool) -> dict[str, object]:
    repo = root()
    errors: list[str] = []
    errors.extend(check_structure(repo))
    errors.extend(check_skills(repo))
    errors.extend(check_sync(repo))
    errors.extend(check_providers(repo))
    errors.extend(check_python_scripts(repo))
    errors.extend(check_behavior(repo))
    errors.extend(check_docs(repo, strict))
    return {"ok": not errors, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    result = validate(args.strict)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("skill repository valid")
    else:
        for error in result["errors"]:
            print(f"error: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
