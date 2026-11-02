#!/usr/bin/env python3
"""Generate portable resources from the canonical resource map."""
import argparse
import json
from pathlib import Path
import sys

def expected_outputs(root):
    mapping=json.loads((root/'config/resource-map.json').read_text());outputs={}
    for name,groups in mapping.items():
        for group,resources in groups.items():
            for destination,source in resources.items():
                path=root/source
                if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Source outside canonical root')
                text=path.read_text()
                notice=f'Source: .skill-tree/{source}; generator: .skill-tree/scripts/sync-skill-references.py'
                if path.suffix=='.py':
                    header='# GENERATED FILE\n# '+notice+'\n'
                    if text.startswith('#!'):
                        first,rest=text.split('\n',1);text=first+'\n'+header+rest
                    else:text=header+text
                else:text='<!-- GENERATED FILE; '+notice+' -->\n\n'+text
                outputs[root/'skills'/name/group/destination]=text
    return outputs

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1];errors=[]
    for path,text in expected_outputs(root).items():
        if args.check:
            if not path.is_file() or path.read_text()!=text:errors.append(str(path.relative_to(root)))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    if errors:print('Stale generated resources: '+', '.join(errors),file=sys.stderr);return 1
    print('skill references current' if args.check else 'skill references synchronized');return 0
if __name__=='__main__':raise SystemExit(main())
