#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/validate-document-rules.py; generator: skill-tree/scripts/sync-skill-references.py
"""Check owned document naming and common prose-rule violations."""
import argparse
import json
from pathlib import Path
import re

EXCEPTIONS={'SKILL.md','README.md','AGENTS.md','CLAUDE.md','GEMINI.md','LICENSE','package.json','package-lock.json'}
PRONOUNS=re.compile(r"\b(?:i|me|my|mine|we|us|our|ours|you|your|yours|he|him|his|she|her|hers|they|them|their|theirs|it|its|itself|this|these|those|that)\b",re.I)
HISTORY=re.compile(r'\b(?:previous version|formerly|used to|last updated|last verified|added by owner|historical documents)\b',re.I)

def prose(text):
    text=re.sub(r'^<!--.*?-->','',text,flags=re.S)
    text=re.sub(r'```.*?```','',text,flags=re.S)
    text=re.sub(r'`[^`]*`','',text)
    text=re.sub(r'\[[^]]*\]\([^)]*\)',lambda m:m.group(0).split('](')[0][1:],text)
    text=re.sub(r'https?://\S+','',text)
    return text

def check(path):
    errors=[]
    if path.name not in EXCEPTIONS and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)*',path.name):errors.append('Owned filename requires lowercase kebab-case')
    return errors+check_text(path.read_text())

def check_text(text):
    errors=[];clean=prose(text)
    if re.search(r'[\u0400-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]',clean):errors.append('English prose required')
    for match in PRONOUNS.finditer(clean):errors.append('Explicit entity required: '+match[0])
    if HISTORY.search(clean):errors.append('Current declarative prose required')
    return errors

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('paths',type=Path,nargs='+');args=parser.parse_args(argv);errors=[]
    for path in args.paths:
        candidates=sorted(path.rglob('*.md')) if path.is_dir() else [path]
        for candidate in candidates:
            if 'artifacts' not in candidate.parts and 'fixtures' not in candidate.parts:
                errors.extend(str(candidate)+': '+e for e in check(candidate))
    print(json.dumps({'ok':not errors,'errors':errors},indent=2));return int(bool(errors))
if __name__=='__main__':raise SystemExit(main())
