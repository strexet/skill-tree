#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/validate-document-rules.py; generator: skill-tree/scripts/sync-skill-references.py
"""Report located errors and review warnings in owned Markdown prose."""
import argparse
import json
from pathlib import Path
import re

EXCEPTIONS={'SKILL.md','README.md','AGENTS.md','CLAUDE.md','GEMINI.md','LICENSE','package.json','package-lock.json'}
PRONOUNS=re.compile(r"\b(?:i|me|my|mine|we|us|our|ours|you|your|yours|he|him|his|she|her|hers|they|them|their|theirs|it|its|itself)\b",re.I)
DEMONSTRATIVES=re.compile(r'\b(?:this|these|those|that)\b',re.I)
HISTORY=re.compile(r'\b(?:previous version|formerly|used to|last updated|last verified|added by owner|historical documents)\b',re.I)
NON_ENGLISH=re.compile(r'[\u0400-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]+')

def prose(text):
    """Mask literal spans while preserving source offsets and line breaks."""
    patterns=[r'<!--.*?-->',r'(?m)^\s*```[^\n]*\n.*?^\s*```[^\n]*(?:\n|$)',r'(?m)^\s*~~~[^\n]*\n.*?^\s*~~~[^\n]*(?:\n|$)',r'`[^`\n]*`',r'(?<!\w)["\u201c][^"\u201d\n]*["\u201d]',r"(?<!\w)'[^'\n]+'(?!\w)",r'https?://\S+']
    clean=text
    def mask(match):return re.sub(r'[^\n]',' ',match[0])
    for pattern in patterns:clean=re.sub(pattern,mask,clean,flags=re.S)
    # Link labels remain prose; only destinations are literal identifiers.
    clean=re.sub(r'(?<=\])\([^\n)]*\)',mask,clean)
    return clean

def diagnostics(text,path=None):
    clean=prose(text);result=[]
    def add(rule,severity,message,start,end):
        line=text.count('\n',0,start)+1;column=start-(text.rfind('\n',0,start)+1)+1
        value={'rule':rule,'severity':severity,'message':message,'line':line,'column':column,'excerpt':text[start:end]}
        if path is not None:value['path']=str(path)
        result.append(value)
    for match in NON_ENGLISH.finditer(clean):add('english-prose','error','English prose required',match.start(),match.end())
    for match in PRONOUNS.finditer(clean):
        # Unquoted title-case labels require review rather than automatic rejection.
        label=match[0][0].isupper() and match[0].lower() in {'my','your','our'} and re.match(r' +[A-Z][a-z]+',clean[match.end():])
        add('explicit-entity','warning' if label else 'error','Explicit entity required: '+match[0],match.start(),match.end())
    for match in DEMONSTRATIVES.finditer(clean):
        # Relative clauses and complementizers are grammatical rather than ambiguous subjects.
        previous=clean[:match.start()].rstrip()
        if match[0].lower()=='that' and previous and previous[-1] not in '.!?:\n':continue
        add('entity-reference','warning','Review entity reference: '+match[0],match.start(),match.end())
    for match in HISTORY.finditer(clean):
        if match[0].lower()=='used to' and re.search(r'\b(?:be|is|are|was|were)\s*$',clean[:match.start()],re.I):continue
        add('current-prose','error','Current declarative prose required',match.start(),match.end())
    return sorted(result,key=lambda value:(value['line'],value['column'],value['rule']))

def check_text(text,warnings_as_errors=False):
    return [item['message'] for item in diagnostics(text) if item['severity']=='error' or warnings_as_errors]

def inspect(path):
    try:result=diagnostics(path.read_text(),path)
    except (OSError,UnicodeError) as exc:
        return [{'path':str(path),'line':1,'column':1,'rule':'document-read','severity':'error','message':'Cannot read document: '+str(exc),'excerpt':''}]
    if path.name not in EXCEPTIONS and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)*',path.name):
        result.insert(0,{'path':str(path),'line':1,'column':1,'rule':'owned-filename','severity':'error','message':'Owned filename requires lowercase kebab-case','excerpt':path.name})
    return result

def describe(item):
    return f"{item.get('path','<text>')}:{item['line']}:{item['column']}: {item['message']}"

def check(path,warnings_as_errors=False):
    return [describe(item) for item in inspect(path) if item['severity']=='error' or warnings_as_errors]

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('paths',type=Path,nargs='+');parser.add_argument('--warnings-as-errors',action='store_true');args=parser.parse_args(argv);items=[]
    for path in args.paths:
        candidates=sorted(path.rglob('*.md')) if path.is_dir() else [path]
        for candidate in candidates:
            if 'artifacts' not in candidate.parts and 'fixtures' not in candidate.parts:items.extend(inspect(candidate))
    errors=[describe(item) for item in items if item['severity']=='error' or args.warnings_as_errors]
    warnings=[describe(item) for item in items if item['severity']=='warning']
    print(json.dumps({'ok':not errors,'errors':errors,'warnings':warnings,'diagnostics':items},indent=2));return int(bool(errors))
if __name__=='__main__':raise SystemExit(main())
