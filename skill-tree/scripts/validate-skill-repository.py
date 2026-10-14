#!/usr/bin/env python3
"""Validate portable source structure, generated resources and document rules."""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

EXCEPTIONS={'SKILL.md','README.md','AGENTS.md','CLAUDE.md','GEMINI.md','LICENSE','package.json','package-lock.json'}

def validate(strict=False):
    core=Path(__file__).resolve().parents[1];repo=core.parent;errors=[]
    mapping=json.loads((core/'config/resource-map.json').read_text())
    for rel in ['AGENTS.md','README.md','LICENSE','package.json','install.sh','install.ps1']:
        if not (repo/rel).is_file():errors.append('Missing root entrypoint: '+rel)
    if json.loads((repo/'package.json').read_text()).get('license')!='MIT':errors.append('Package license must remain MIT')
    for path in core.rglob('*'):
        if any(part in {'__pycache__','artifacts','.git'} for part in path.parts):continue
        if path.name in {'.writer-lock','.transaction.json'}:continue
        if path.name not in EXCEPTIONS and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)*',path.name):errors.append('Invalid owned name: '+str(path.relative_to(core)))
        if path.suffix=='.py':
            try:ast.parse(path.read_text())
            except SyntaxError as exc:errors.append(str(exc))
    actual={p.parent.name for p in (core/'skills').glob('*/SKILL.md')}
    if actual!=set(mapping):errors.append('Skill catalog and resource map disagree')
    for name,resources in mapping.items():
        package=core/'skills'/name;text=(package/'SKILL.md').read_text()
        if not re.fullmatch(r'skill-tree-[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64:errors.append('Invalid skill name: '+name)
        match=re.match(r'---\n(.*?)\n---\n',text,re.S)
        if not match or 'name: '+name+'\n' not in match[1]+'\n':errors.append('Invalid frontmatter: '+name)
        if match:
            desc=re.search(r'(?m)^description: (.+)$',match[1])
            if not desc or len(desc[1])>1024:errors.append('Invalid description: '+name)
        for rel in re.findall(r'(?:references|scripts)/[a-z0-9-]+\.[a-z]+',text):
            if not (package/rel).is_file():errors.append('Missing local resource: '+name+'/'+rel)
        if '../' in text or '/Users/' in text:errors.append('Nonportable skill entrypoint: '+name)
        for group,files in resources.items():
            for dest,source in files.items():
                if not (package/group/dest).is_file() or not (core/source).is_file():errors.append('Missing mapped resource: '+name+'/'+dest)
        metadata=package/'agents/openai.yaml'
        if not metadata.is_file():errors.append('Missing UI metadata: '+name)
    result=subprocess.run([sys.executable,str(core/'scripts/sync-skill-references.py'),'--check'],capture_output=True,text=True)
    if result.returncode:errors.append(result.stderr.strip())
    matrix=json.loads((core/'config/providers.json').read_text());ids=[p['id'] for p in matrix['providers']]
    if len(ids)!=len(set(ids)):errors.append('Duplicate provider ID')
    for p in matrix['providers']:
        probes=p.get('detect',[])
        if probes and all(d.get('kind')=='directory' for d in probes) and not p.get('soft'):errors.append('Directory-only provider must be soft: '+p['id'])
    if strict:
        rulepath=core/'common/scripts/validate-document-rules.py';spec=importlib.util.spec_from_file_location('document_rules',rulepath);rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
        for path in [*core.rglob('*.md'),repo/'README.md',repo/'AGENTS.md',repo/'CLAUDE.md',repo/'GEMINI.md']:
            if 'fixtures' not in path.parts and 'artifacts' not in path.parts:
                errors.extend(rules.check(path,warnings_as_errors=True))
    manifest=core/'skill-tree.json'
    if manifest.exists():
        validator=core/'common/scripts/validate-repository-documentation.py'
        spec=importlib.util.spec_from_file_location('repository_documentation',validator);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        errors.extend(module.validate_manifest(repo)['errors'])
    return {'ok':not errors,'errors':errors}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--strict',action='store_true');parser.add_argument('--format',choices=['text','json'],default='text');args=parser.parse_args(argv);result=validate(args.strict)
    print(json.dumps(result,indent=2) if args.format=='json' else ('skill repository valid' if result['ok'] else '\n'.join(result['errors'])));return int(not result['ok'])
if __name__=='__main__':raise SystemExit(main())
