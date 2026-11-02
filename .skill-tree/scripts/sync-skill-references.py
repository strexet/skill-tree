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

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1];outputs=expected_outputs(root);errors=[]
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
