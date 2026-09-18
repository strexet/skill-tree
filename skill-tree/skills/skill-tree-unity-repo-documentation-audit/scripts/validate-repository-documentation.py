#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/validate-repository-documentation.py; generator: skill-tree/scripts/sync-skill-references.py
"""Validate current target documentation and metadata ownership."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

REQUIRED=['project.md','technical.md','features.md','future.md','rules.md','repository-map.md','build-and-release.md','testing.md','dependencies.md']

def load(name):
    path=Path(__file__).with_name(name+'.py');spec=importlib.util.spec_from_file_location(name.replace('-','_'),path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def validate(root,strict=False):
    errors=[];docs=root/'skill-tree/documents'
    for rel in ['README.md','AGENTS.md','skill-tree/skill-tree.json']+['skill-tree/documents/'+name for name in REQUIRED]:
        if not (root/rel).is_file():errors.append('Missing '+rel)
    if (docs/'future.md').exists():
        result=load('validate-future-document').validate(docs/'future.md',strict);errors+=result['errors']
    rules=load('validate-document-rules')
    if strict:
        for path in docs.glob('*.md'):errors += [str(path)+': '+e for e in rules.check(path)]
    return {'ok':not errors,'errors':errors}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);parser.add_argument('--strict',action='store_true');parser.add_argument('--format',choices=['text','json'],default='text');args=parser.parse_args(argv);result=validate(args.root,args.strict);print(json.dumps(result,indent=2));return int(not result['ok'])
if __name__=='__main__':raise SystemExit(main())
