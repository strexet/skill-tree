"""Start the reviewed Director implementation from the installed operation."""
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess
import sys


RUNTIME = 'scripts/runtime/'


def owned(root, relative):
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or '\\' in part for part in parts):
        raise ValueError('Director package paths require owned relative inputs')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Director package resources cannot be symlinks')
    return path.read_bytes()


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        manifest = json.loads(owned(root, 'references/plugin-bindings.json'))
        operation = manifest['operation']
        if operation != root.name or not operation.startswith('skill-tree-director-'):
            raise ValueError('Director package does not match the selected operation')
        helpers = {'skill-tree-director-review': 'director-handoff.py', 'skill-tree-director-audit': 'director-audit.py'}
        helper = helpers.get(operation, 'director-state.py')
        if operation == 'skill-tree-director-audit' and sys.argv[1:2] and sys.argv[1].startswith('repair-'):
            helper = 'director-source-repair.py'
        if operation == 'skill-tree-director-review' and sys.argv[1:2] and sys.argv[1].startswith(('adopt-', 'milestone-')):
            helper = 'director-evidence.py'
        entry = RUNTIME + ('lib/director-canary.js' if operation == 'skill-tree-director-install' else 'common/scripts/' + helper)
        inventory = manifest['owned_resources']
        runtime = {relative: expected for relative, expected in inventory.items() if relative.startswith(RUNTIME)}
        if entry not in runtime:
            raise ValueError('The reviewed Director runtime inventory is unavailable')
        for relative, expected in runtime.items():
            if sha256(owned(root, relative)).hexdigest() != expected:
                raise ValueError('Director package resource changed: ' + relative)
        if operation == 'skill-tree-director-install':
            return subprocess.run(['node', str(root / entry), *sys.argv[1:]], check=False).returncode
        runpy.run_path(str(root / entry), run_name='__main__')
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
