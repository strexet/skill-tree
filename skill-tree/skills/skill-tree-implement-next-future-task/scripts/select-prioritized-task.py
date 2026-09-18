#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/select-prioritized-task.py; generator: skill-tree/scripts/sync-skill-references.py
"""Select the highest-priority or exact prioritized task."""
import argparse
import json
import importlib.util
import sys
from pathlib import Path

def runtime():
    path=Path(__file__).with_name('workflow-state.py')
    spec=importlib.util.spec_from_file_location('skill_tree_workflow',path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('future',type=Path);parser.add_argument('--name');parser.add_argument('--id');parser.add_argument('--format',choices=['text','json'],default='text');args=parser.parse_args(argv)
    try:
        module=runtime();task=module.select(module.parse(args.future.read_text()),args.id or args.name);result={'ok':True,**task};code=0
    except FileNotFoundError as exc:result={'ok':False,'error':str(exc)};code=2
    except ValueError as exc:
        error=str(exc);code=8 if 'blocking' in error else 4 if 'No prioritized' in error else 5 if 'Absent' in error else 7;result={'ok':False,'error':error}
    if args.format=='json':print(json.dumps(result,indent=2))
    elif code:print(result['error'],file=sys.stderr)
    else:print(result['body'],end='')
    return code
if __name__=='__main__':raise SystemExit(main())
