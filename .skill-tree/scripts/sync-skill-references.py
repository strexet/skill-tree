#!/usr/bin/env python3
"""Generate standalone flavor packages with the canonical deterministic composer."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

def expected_outputs(root):
    result=subprocess.run(['node',str(root/'bin/compose.js')],capture_output=True,text=True,timeout=60,check=True)
    return {root/path:content for path,content in json.loads(result.stdout).items()}

def sync_review_snapshot(root, check):
    source = root / 'examples/3d/workshop/review'
    package = root / 'common/scripts/3d-review'
    if not check:
        package.mkdir(exist_ok=True)
    errors = []
    for name in ('review.py', 'visual.py', 'evidence.py'):
        dest = package / name
        content = (source / name).read_bytes()
        if check:
            if not dest.is_file() or dest.read_bytes() != content:
                errors.append(str(dest.relative_to(root)))
        else:
            dest.write_bytes(content)
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    errors=sync_review_snapshot(root,args.check)
    if errors:
        print('Stale bundled 3D review resources: '+', '.join(errors),file=sys.stderr)
        return 1
    outputs=expected_outputs(root)
    actual={p for p in (root/'skills').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for path in sorted(actual-set(outputs)):
        if args.check:errors.append(str(path.relative_to(root)))
        else:path.unlink()
    for path,text in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text()!=text:errors.append(str(path.relative_to(root)))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    if not args.check:
        for directory in sorted((p for p in (root/'skills').rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
            if not any(directory.iterdir()):directory.rmdir()
    if errors:print('Stale generated resources: '+', '.join(errors),file=sys.stderr);return 1
    print('skill references current' if args.check else 'skill references synchronized');return 0
if __name__=='__main__':raise SystemExit(main())
