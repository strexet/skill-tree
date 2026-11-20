"""Route one reviewed snapshot finding through the existing Core source workflow."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys


COMMANDS = {'repair-preview', 'repair-intake', 'repair-process', 'repair-start',
            'repair-candidate-preview', 'repair-candidate-apply', 'repair-candidate-read'}
ARCHIVE = '.skill-tree/director/source-repairs/'
SOURCE = '.skill-tree/common/scripts/create-documentation-snapshot.py'
OPERATION = 'skill-tree-create-documents-snapshot'
RECIPE = 'director-snapshot-canary'
CHECK = 'snapshot-scope-preserves-markdown-extension'
SCENARIO = 'director-documentation-snapshot-readme'
ASSERTION = 'The dry-run report preserves the Markdown extension of README.md.'
INPUT = b'# Director snapshot canary\n\nThis document is the selected Markdown input.\n'
STAMP = '2000-01-01-00-00'
TITLE = 'Preserve Markdown extensions in snapshot dry-run reports'
OWNER_FIELDS = {'actor', 'kind', 'reference'}
EFFECTS = {'intake', 'process', 'launch', 'freeze-candidate'}
DEFECT = b'''print(f"- {item.removesuffix('.md')}")'''
REPAIRED = b'print(f"- {item}")'


def _load_module(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = _load_module('director-state')


def scenario():
    return {'id': SCENARIO, 'recipe_id': RECIPE, 'lane': 'unit', 'assertion_id': CHECK,
            'assertion': ASSERTION, 'input_sha256': D.WF.digest(INPUT)}


def observation(source_sha, fixed):
    return {'schema': 1, 'kind': 'director-snapshot-canary-result', 'assertion_id': CHECK,
            'observed': 'markdown-extension-preserved' if fixed else 'markdown-extension-omitted',
            'exit_code': 0, 'selected_count': 1, 'input_sha256': scenario()['input_sha256'], 'helper_sha256': source_sha}


def observe_snapshot(script, project, *, argv=None):
    """Run the fixed one-file CLI scenario and normalize only the output path."""
    project = D._root(str(project))
    D._require((project / 'README.md').read_bytes() == INPUT, 'Snapshot test input bytes changed')
    flags = [str(project), '--dry-run', '--include', 'README.md', '--timestamp', STAMP]
    args = [sys.executable, '-B', str(script), *flags]
    if argv is not None:
        D._require(argv == ['python3', '-B', script.relative_to(project).as_posix(), *flags],
                   'Prepared unit recipe does not match the fixed snapshot scenario')
        args = argv
    process = subprocess.run(args, cwd=project, capture_output=True, text=True, timeout=30)
    rows = process.stdout.splitlines()
    D._require(process.returncode == 0 and not process.stderr and len(rows) == 3 and rows[0].startswith('archive: ')
               and rows[1] == 'included: 1' and rows[2] in {'- README', '- README.md'},
               'The actual snapshot command did not exercise the selected one-file assertion')
    archive = Path(rows[0][len('archive: '):])
    D._require(archive.is_absolute() and archive.resolve().is_relative_to(project)
               and not archive.exists(), 'The snapshot dry-run unexpectedly produced an archive')
    return observation(D.WF.file_hash(script), rows[2] == '- README.md')


def _owner(value):
    D._object(value, OWNER_FIELDS)
    D._require(D._token(value['actor']) and D._token(value['reference']), 'Source repair requires exact owner authority')
    D.WF.clarification_evidence({key: value[key] for key in ('kind', 'reference')})
    return value


def _archive(kind, digest):
    D._require(D._sha(digest), 'Select an exact reviewed source repair identity')
    return f'{ARCHIVE}{kind}-{digest}.json'


def _repair_id(plan):
    return D._digest({'director_id': plan['director_id'], 'source': plan['source'],
                      'finding_sha256': plan['finding']['finding_sha256'], 'scenario': plan['scenario']})


def _check():
    return {'id': CHECK, 'recipe_id': RECIPE, 'criteria': [ASSERTION], 'sources': [SOURCE, 'README.md'],
            'parameters': {}, 'assertion': ASSERTION, 'timing': 'immediate', 'test_first': True}


def _task_body(finding_sha):
    return (f'Goal:\n- Preserve the Markdown extension in the exact snapshot dry-run report.\n\n'
            f'Touch:\n- {SOURCE}\n\nSource:\n- The original sanitized Director finding is `{finding_sha}`.\n\n'
            f'Validation:\n```json\n{json.dumps({"checks": [_check()]}, sort_keys=True)}\n```\n\nAcceptance:\n- {ASSERTION}\n')


class DirectorSourceRepair:
    def __init__(self, registry, audit):
        self.registry, self.audit = registry, audit
        self.store = D.WF.Store(registry.root, route_queue=False, neutral=True)
        self.dispatch = D.WF.director_dispatch_helper()
        self.objectives = D._objective_helper()

    def _area(self):
        registry, bindings, _ = self.registry._load()
        D._require(registry is not None, 'Register the exact Director source-maintenance area')
        areas = [item for item in registry['areas'].values() if item['role'] == 'source-maintenance']
        D._require(len(areas) == 1, 'Register precisely one canonical source-maintenance area')
        area = areas[0]
        D._require({'intake', 'process', 'launch'} <= set(area['allowed_effects'])
                   and D._scope(SOURCE).is_relative_to(D._scope(area['scope'])),
                   'The source-maintenance area lacks the exact authorized repair scope')
        root = self.objectives._child_root(registry, bindings, area['id'])
        return registry['director_id'], self.objectives._area_identity(area), root

    def preview(self, request):
        D._object(request, {'audit', 'finding_sha256'})
        D._require(D._sha(request['finding_sha256']), 'Select an exact sanitized audit finding')
        audit = self.audit.read(request['audit'])
        matches = [item for item in audit['findings'] if item.get('finding_sha256') == request['finding_sha256']]
        D._require(len(matches) == 1, 'Current audit does not contain one exact source-ready finding')
        finding = matches[0]
        pattern = (finding.get('classification'), finding.get('component'), finding.get('symptom'))
        D._require(pattern == ('source-defect', 'documentation-snapshot', 'markdown-extension-omitted')
                   and finding.get('scope') == {'source_path': SOURCE, 'operation': OPERATION}
                   and finding.get('conditions') == {'recipe_id': RECIPE, 'lane': 'unit', 'assertion_id': CHECK}
                   and finding.get('evidence'), 'Selected audit evidence does not qualify for this bounded source repair')
        director, area, root = self._area()
        source = D._safe_path(root, SOURCE)
        D._require(D.WF.file_hash(source) == finding['generation']['source_sha256']
                   and source.read_bytes().count(DEFECT) == 1, 'The exact controlled source generation changed')
        plan = {'schema': 1, 'director_id': director, 'source': area, 'finding': finding, 'scenario': scenario()}
        result = {'repair_id': _repair_id(plan), 'plan': plan, 'audit_sha256': audit['audit_sha256'],
                  'audit_run_sha256': audit['director_status']['run_sha256'],
                  'queue_sha256': D.WF.file_hash(root / '.skill-tree/documents/future.md'), 'effects': sorted(EFFECTS)}
        return {**result, 'preview_sha256': D._digest(result)}

    def _load(self, repair_id):
        receipt, _ = D._read(self.registry.root, _archive('repair', repair_id))
        D._require(receipt and receipt['repair_id'] == repair_id and _repair_id(receipt['preview']['plan']) == repair_id
                   and D._digest({key: value for key, value in receipt.items() if key != 'receipt_sha256'}) == receipt['receipt_sha256'],
                   'The exact owner-approved repair intake is unavailable or changed')
        director, area, root = self._area()
        plan = receipt['preview']['plan']
        D._require(plan['director_id'] == director and plan['source'] == area,
                   'Registered source authority changed after repair approval')
        D._require(D.WF.file_hash(root / SOURCE) == plan['finding']['generation']['source_sha256'],
                   'The protected original source generation changed')
        return receipt, root

    def _envelope(self, case):
        plan = case['preview']['plan']
        return {'schema': 1, 'director_id': plan['director_id'], 'assignment_id': 'repair-' + case['repair_id'],
                'queue_id': plan['source']['queue_id'], 'plan_sha256': case['repair_id']}

    def _observed(self, case, root, operation):
        return self.dispatch.observe(D.WF.Store(root, neutral=True), {
            'operation': operation, 'director_dispatch': self._envelope(case),
        })

    def _deliver(self, case, root, operation, request, start=None):
        D._require(D._sha(request['expected_source_hash']), 'Use the exact inspected source queue digest')
        request = {**request, 'director_dispatch': self._envelope(case)}
        self.dispatch.retain_intent(self.store, operation, request, start_context=start)
        response = {'operation': operation, 'request': request}
        if start is not None:
            response['start'] = start
        delivered = self.dispatch.apply(D.WF.Store(root, neutral=True), response)
        observed = self._observed(case, root, operation)
        D._require(observed['receipt'] is not None, 'Reconcile the original exact source repair delivery')
        return {'repair_id': case['repair_id'], 'operation': operation, 'result': delivered,
                'dispatch_receipt_sha256': observed['receipt']['receipt_sha256']}

    def intake(self, payload):
        D._object(payload, {'request', 'repair_id', 'expected_preview_sha256', 'owner', 'authorized_effects'})
        owner = _owner(payload['owner'])
        effects = D._tokens(payload['authorized_effects'], 'Source repair effects')
        D._require('intake' in effects and set(effects) <= EFFECTS, 'Owner selection does not authorize this exact repair intake')
        repair_id = payload['repair_id']
        relative = _archive('repair', repair_id)
        owner_key = {'kind': 'director-source-repair-intake', 'repair_id': repair_id, 'request_sha256': D._digest(payload)}
        previous, _ = D._read(self.registry.root, relative)
        journal, _ = D._read(self.registry.root, '.skill-tree/.transaction.json')
        replaying = bool(journal and journal.get('local_delivery') == owner_key
                         and [entry['path'] for entry in journal.get('writes', [])] == [relative])
        preview = None if previous is not None or replaying else self.preview(payload['request'])
        with self.store.lock(local_delivery=owner_key):
            case, baseline = D._read(self.registry.root, relative)
            if case is None:
                director, area, root = self._area()
                audited_run = payload['request']['audit']['director_run_id']
                run_path = '.skill-tree/director/runs/' + audited_run.lower() + '.json'
                D._require(preview is not None and preview['repair_id'] == repair_id
                           and preview['preview_sha256'] == payload['expected_preview_sha256']
                           and preview['plan']['director_id'] == director and preview['plan']['source'] == area
                           and preview['audit_run_sha256'] == D.WF.file_hash(D._safe_path(self.registry.root, run_path))
                           and preview['queue_sha256'] == D.WF.file_hash(root / '.skill-tree/documents/future.md')
                           and preview['plan']['finding']['generation']['source_sha256'] == D.WF.file_hash(root / SOURCE),
                           'Source repair preview or queue changed before owner selection')
                case = {'schema': 1, 'repair_id': repair_id, 'preview': preview, 'owner': owner, 'effects': effects,
                        'request_sha256': owner_key['request_sha256'], 'recorded_at': D.WF.now()}
                case['receipt_sha256'] = D._digest(case)
                self.store.expect_unchanged(relative, baseline)
                self.store.commit({relative: D.WF.dump(case)})
            else:
                D._require(case['request_sha256'] == owner_key['request_sha256'], 'Original source repair approval differs')
        case, root = self._load(repair_id)
        finding = case['preview']['plan']['finding']['finding_sha256']
        return self._deliver(case, root, 'intake', {'expected_source_hash': case['preview']['queue_sha256'],
            'title': TITLE, 'description': f'The original Director source finding is `{finding}`. {ASSERTION}',
            'expected_behavior': 'Repeat the exact one-file dry-run without writing an archive.',
            'classification': {'kind': 'defect', 'reason': 'The controlled report omits an existing Markdown extension.'}})

    def _authorized(self, payload, flag):
        case, root = self._load(payload['repair_id'])
        owner = _owner(payload['owner'])
        D._require(flag in case['effects'] and owner['actor'] == case['owner']['actor'],
                   'Original owner authority does not select this source repair effect')
        return case, root

    def process(self, payload):
        D._object(payload, {'repair_id', 'pending_id', 'expected_source_hash', 'owner'})
        case, root = self._authorized(payload, 'process')
        result = self._observed(case, root, 'intake')['observed_result']
        pending = payload['pending_id']
        D._require(result is not None and result['id'] == pending, 'Process only the exact chosen repair Pending ID')
        finding = case['preview']['plan']['finding']['finding_sha256']
        return self._deliver(case, root, 'process', {'expected_source_hash': payload['expected_source_hash'],
            'selectors': [pending], 'dispositions': {pending: {'status': 'promoted', 'reason': 'The observed fixture bounds the source repair.'}},
            'tasks': [{'title': TITLE, 'body': _task_body(finding), 'parent_pending_ids': [pending]}]})

    def start(self, payload):
        D._object(payload, {'repair_id', 'task_id', 'expected_source_hash', 'owner', 'workspace'})
        case, root = self._authorized(payload, 'launch')
        result = self._observed(case, root, 'process')['observed_result']
        task = payload['task_id']
        D._require(result is not None and result['created_ids'] == [task], 'Launch only the exact processed repair T')
        work = payload['workspace']
        D._object(work, {'base_branch', 'branch', 'worktree'}, {'local_base', 'local_base_authorization', 'remote'})
        return self._deliver(case, root, 'start', {**work, 'expected_source_hash': payload['expected_source_hash']},
                             {'mode': 'next', 'selector': task, 'limits': None})

    def _package_pins(self, worktree, target, flavor, base_oid):
        composer = Path(__file__).resolve().parents[2] / 'lib/composer.js'
        code = """
const [file,source,target,flavor] = process.argv.slice(1);
const c = require(file), profile = c.resolveProfile(source,target,flavor);
const output = c.compose(source,profile,c.operationNames(source,flavor));
const inputs = c.sourceInputs(source);
console.log(JSON.stringify({source_inventory_sha256:c.hash(c.json(inputs)), source_paths:Object.keys(inputs),
  environment_id:profile.environment_id,output_digests:output.output_digests}));
"""
        result = subprocess.run(['node', '-e', code, str(composer), str(worktree / '.skill-tree'), str(target), flavor],
                                capture_output=True, text=True, timeout=45)
        D._require(result.returncode == 0, 'Candidate cannot compose the exact package inventory: ' + result.stderr.strip())
        value = json.loads(result.stdout)
        prior = set(D.WS.local_git(worktree, 'ls-tree', '-r', '-z', '--name-only', base_oid, '--', '.skill-tree').stdout.split(b'\0'))
        D._require(all(('.skill-tree/' + path).encode() in prior for path in value.pop('source_paths')),
                   'Candidate package inventory contains an unreviewed new source input')
        helper = 'scripts/create-documentation-snapshot.py'
        D._require(value['output_digests'][OPERATION][helper] == D.WF.file_hash(worktree / SOURCE),
                   'Composed repair helper does not match source')
        return value

    def _observed_check(self, row, worktree, source_sha, *, red):
        result = 'red' if red else 'pass'
        counts = {'expected': 1, 'discovered': 1, 'passed': int(not red), 'failed': int(red), 'skipped': 0}
        D._require(row and row['result'] == result and row['actual_lane'] == 'unit' and row['counts'] == counts
                   and row['classification'] == 'executed-control' and row['sources'] == {SOURCE: source_sha, 'README.md': scenario()['input_sha256']}
                   and (not red or row.get('failure_category') == 'expected-behavior') and len(row['evidence']) == 1,
                   'Candidate requires matching Core test-first and repaired check records')
        ref = row['evidence'][0]
        proof, sha = D._read(worktree, ref['path'])
        D._require(sha == ref['sha256'] and proof == observation(source_sha, not red),
                   'Observed CLI check evidence is missing, changed or from another scenario')
        return {'result': 'fail' if red else 'pass', 'scenario_sha256': D._digest(scenario()),
                'record_sha256': D._digest(row), 'attempt_id': row['attempt_id'],
                'evidence': {key: ref[key] for key in ('path', 'sha256')}}

    def candidate_preview(self, payload):
        D._object(payload, {'repair_id', 'pending_id', 'task_id', 'run_id', 'outcome_id', 'composition_target',
                            'flavor', 'provider', 'owner', 'review_ref'})
        case, root = self._authorized(payload, 'freeze-candidate')
        D._require(D._token(payload['review_ref']) and payload['provider'] == 'codex', 'Candidate requires exact owner review and Codex packaging')
        intake, processed, launched = (self._observed(case, root, operation)['observed_result']
                                       for operation in ('intake', 'process', 'start'))
        task_id = payload['task_id']
        D._require(intake and processed and launched and intake['id'] == payload['pending_id']
                   and processed['created_ids'] == [task_id] and launched['id'] == payload['run_id'],
                   'Candidate requires original Pending, processed T and exact WR receipts')
        selected = {key: payload[key] for key in ('task_id', 'run_id', 'outcome_id')}
        outcome, run = self.objectives._exact_outcome(root, **selected)
        D._require(outcome['disposition'] == 'completed' and run['phase'] == 'completed'
                   and run['snapshot'] == run['admitted_task_ids'] == [task_id]
                   and outcome['parent_pending_ids'] == [payload['pending_id']],
                   'Candidate requires preserved original repair lineage and bounded task scope')
        worktree = self.objectives._read_run_root(root, run)
        D._require(worktree is not None, 'The original source repair worktree is unavailable')
        finding = case['preview']['plan']['finding']
        base_oid = run['workspace']['base_commit']
        D._require(re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', base_oid) is not None, 'Candidate requires exact source baseline identity')
        old = D.WS.local_git(worktree, 'show', base_oid + ':' + SOURCE).stdout
        before = D.WF.digest(old)
        current = D._safe_path(worktree, SOURCE).read_bytes()
        after = D.WF.digest(current)
        rows = D.WS.local_git(worktree, 'diff', '--numstat', '-z', '--no-renames', '--no-ext-diff', base_oid, '--').stdout.split(b'\0')[:-1]
        changed = [row.split(b'\t', 2)[2] for row in rows]
        D._require(before == finding['generation']['source_sha256'] and old.count(DEFECT) == 1
                   and current == old.replace(DEFECT, REPAIRED) and changed == [SOURCE.encode()]
                   and (worktree / 'README.md').read_bytes() == INPUT,
                   'Candidate contains changes outside the exact reviewed repair')
        checks = outcome['check_results']
        D._require(len(checks) == 1 and checks[0]['check']['id'] == CHECK and checks[0]['check']['recipe_id'] == RECIPE
                   and checks[0]['check']['assertion'] == ASSERTION and isinstance(checks[0].get('red'), dict)
                   and checks[0]['red']['definition'] == checks[0]['result']['definition'],
                   'Canonical outcome does not bind the same original assertion and check')
        verified = {'original': self._observed_check(checks[0]['red'], worktree, before, red=True),
                    'repaired': self._observed_check(checks[0]['result'], worktree, after, red=False)}
        target = D._root(payload['composition_target'])
        D._require(target != root and target != worktree, 'Select a separate reviewed package composition target')
        packages = self._package_pins(worktree, target, payload['flavor'], base_oid)
        source_inventory = packages.pop('source_inventory_sha256')
        plan = case['preview']['plan']
        body = {'schema': 1, 'kind': 'director-source-repair-candidate', 'finding_sha256': finding['finding_sha256'],
                'route': {'area_id': plan['source']['id'], 'queue_id': plan['source']['queue_id'], 'pending_id': payload['pending_id'],
                          'processing_run_id': processed['id'], **selected},
                'owner': payload['owner'], 'source': {'revision': 'source-inventory:' + source_inventory, 'source_inventory_sha256': source_inventory},
                'packages': {'flavor': payload['flavor'], 'provider': payload['provider'], **packages}, 'scenario': scenario(), 'checks': verified,
                'review': {'reference': payload['review_ref'], 'source_path': SOURCE, 'source_base_commit': base_oid,
                           'before_sha256': before, 'after_sha256': after, 'outcome_sha256': D._digest(outcome),
                           'original_audit_evidence': finding['evidence']}}
        return {**body, 'candidate_sha256': D._digest(body)}

    def candidate_apply(self, payload):
        D._object(payload, {'request', 'expected_candidate_sha256'})
        digest = payload['expected_candidate_sha256']
        relative = _archive('candidate', digest)
        action = {'kind': 'director-source-repair-candidate', 'candidate_sha256': digest}
        case_path = _archive('repair', payload['request']['repair_id'])
        case_before = D.WF.file_hash(D._safe_path(self.registry.root, case_path))
        observed = self.candidate_preview(payload['request'])
        D._require(observed['candidate_sha256'] == digest, 'Exact reviewed candidate changed before freezing')
        with self.store.lock(local_delivery=action):
            candidate, baseline = D._read(self.registry.root, relative)
            self.store.expect_unchanged(case_path, case_before)
            if candidate is not None:
                D._require(candidate == observed, 'Exact frozen candidate bytes changed')
                return candidate
            self.store.expect_unchanged(relative, baseline)
            self.store.commit({relative: D.WF.dump(observed)})
            return observed

    def candidate_read(self, payload):
        D._object(payload, {'candidate_sha256'})
        digest = payload['candidate_sha256']
        record, _ = D._read(self.registry.root, _archive('candidate', digest))
        D._require(record and record['candidate_sha256'] == digest
                   and D._digest({key: value for key, value in record.items() if key != 'candidate_sha256'}) == digest,
                   'Exact frozen source repair candidate is unavailable or changed')
        return record

    def run(self, command, payload):
        return {'repair-preview': self.preview, 'repair-intake': self.intake, 'repair-process': self.process,
                'repair-start': self.start, 'repair-candidate-preview': self.candidate_preview,
                'repair-candidate-apply': self.candidate_apply, 'repair-candidate-read': self.candidate_read}[command](payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    try:
        registry = D.DirectorRegistry(args.root)
        audit = _load_module('director-audit').DirectorAudit(registry)
        result = DirectorSourceRepair(registry, audit).run(args.command, json.loads(args.input.read_bytes()))
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f'{error}\n')
    print(D.WF.dump(result), end='')


if __name__ == '__main__':
    main()
