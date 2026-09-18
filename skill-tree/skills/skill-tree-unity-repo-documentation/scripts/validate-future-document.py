#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/validate-future-document.py; generator: skill-tree/scripts/sync-skill-references.py
"""Validate current task headers, queue structure and prioritized contracts."""
import argparse
import json
import re
import importlib.util
import sys
from pathlib import Path

def runtime():
    path=Path(__file__).with_name('workflow-state.py')
    spec=importlib.util.spec_from_file_location('skill_tree_workflow',path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def validate(path,strict=False):
    try:
        module=runtime();text=path.read_text();tasks=module.index(text)
        if strict and re.search(r'\b(?:TODO|TBD|FIXME)\b',text):raise ValueError('Unresolved placeholder')
        return {'ok':True,'errors':[],'tasks':tasks}
    except (ValueError,OSError) as exc:return {'ok':False,'errors':[str(exc)],'tasks':[]}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('future',type=Path);parser.add_argument('--strict',action='store_true');parser.add_argument('--format',choices=['text','json'],default='text');args=parser.parse_args(argv);result=validate(args.future,args.strict)
    print(json.dumps(result,indent=2) if args.format=='json' else ('future document valid' if result['ok'] else '\n'.join(result['errors'])));return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
