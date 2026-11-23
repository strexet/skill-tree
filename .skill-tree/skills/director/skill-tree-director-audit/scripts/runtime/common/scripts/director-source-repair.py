"""Route verified Director findings through the approved Core source workflow."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


COMMANDS = {'repair-preview', 'repair-intake', 'repair-process', 'repair-start',
            'repair-candidate-preview', 'repair-candidate-apply', 'repair-candidate-read', 'repair-integrate'}
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
EFFECTS = {'intake', 'process', 'launch', 'freeze-candidate', 'integrate'}
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
                      'finding_sha256': plan['finding']['finding_sha256'], 'scenario': plan['scenario'],
                      **({'maintenance': plan['maintenance']} if 'maintenance' in plan else {})})


def _check():
    return {'id': CHECK, 'recipe_id': RECIPE, 'criteria': [ASSERTION], 'sources': [SOURCE, 'README.md'],
            'parameters': {}, 'assertion': ASSERTION, 'timing': 'immediate', 'test_first': True}


def _repair_scenario(finding):
    reproduction = finding.get('reproduction', {})
    if reproduction.get('kind') != 'director-resource-check':
        return scenario()
    conditions = finding['conditions']
    return {'id': 'director-resource-check', **conditions,
            'assertion': f"The {conditions['assertion_id']} control reports {finding['expected']}.",
            'expected': finding['expected'], 'observed': finding['observed'],
            'resource': reproduction['resource'], 'fixtures': reproduction['fixtures'], 'parameters': reproduction['parameters'],
            'recipe_sha256': reproduction['recipe_sha256']}


def _case_check(plan):
    spec = plan['scenario']
    if spec['id'] == SCENARIO:
        return _check()
    return {'id': spec['assertion_id'], 'recipe_id': spec['recipe_id'], 'assertion': spec['assertion'],
            'sources': [plan['finding']['scope']['source_path'], *spec['fixtures']], 'parameters': spec['parameters'],
            'criteria': [spec['assertion']], 'timing': 'immediate', 'test_first': True}


def _case_title(plan):
    if plan['scenario']['id'] == SCENARIO:
        return TITLE
    return 'Correct ' + plan['finding']['component'] + ' result for ' + plan['scenario']['assertion_id']


class DirectorSourceRepair:
    def __init__(self, registry, audit):
        self.registry, self.audit = registry, audit
        self.store = D.WF.Store(registry.root, route_queue=False, neutral=True)
        self.dispatch = D.WF.director_dispatch_helper()
        self.objectives = D._objective_helper()

    def _area(self, source_path):
        registry, bindings, _ = self.registry._load()
        D._require(registry is not None, 'Register the exact Director source-maintenance area')
        areas = [item for item in registry['areas'].values() if item['role'] == 'source-maintenance']
        D._require(len(areas) == 1, 'Register precisely one canonical source-maintenance area')
        area = areas[0]
        D._require({'intake', 'process', 'launch'} <= set(area['allowed_effects'])
                   and D._scope(source_path).is_relative_to(D._scope(area['scope'])),
                   'The source-maintenance area lacks the exact authorized repair scope')
        root = self.objectives._child_root(registry, bindings, area['id'])
        return registry['director_id'], self.objectives._area_identity(area), root

    def _maintenance(self, finding, root):
        """A guided installation binds the failing product area to its own source branch."""
        canonical = self.registry.root / 'sources/skill-tree'
        if root != canonical:
            return None
        areas = {row['area_id'] for row in finding['evidence']}
        D._require(len(areas) == 1, 'Select evidence from one registered project for the repair')
        project = areas.pop()
        registry, bindings, _ = self.registry._load()
        area = registry['areas'][project]
        checkout = self.objectives._child_root(registry, bindings, project)
        D._require(area['role'] != 'source-maintenance' and checkout != root, 'Select a product maintenance branch')
        maintained = _load_module('director-maintenance').inspect(self.registry.root, project)
        D._require(Path(maintained['checkout']) == root, 'The project maintenance checkout changed')
        return {'project_id': project, 'branch': maintained['branch'], 'base_commit': maintained['base_commit'],
                'product_queue_id': area['queue_id'], 'source_queue_id': maintained['queue_id']}

    def _source_tree(self, root, maintenance):
        if not maintenance:
            return root
        maintained = _load_module('director-maintenance').inspect(self.registry.root, maintenance['project_id'])
        return Path(maintained['project_checkout'])

    def preview(self, request):
        D._object(request, {'audit', 'finding_sha256'})
        D._require(D._sha(request['finding_sha256']), 'Select an exact sanitized audit finding')
        audit = self.audit.read(request['audit'])
        matches = [item for item in audit['findings'] if item.get('finding_sha256') == request['finding_sha256']]
        D._require(len(matches) == 1, 'Current audit does not contain one exact source-ready finding')
        plan, root = self.proposal(matches[0])
        result = {'repair_id': _repair_id(plan), 'plan': plan, 'audit_sha256': audit['audit_sha256'],
                  'audit_run_sha256': audit['director_status']['run_sha256'],
                  'queue_sha256': D.WF.file_hash(root / '.skill-tree/documents/future.md'), 'effects': sorted(EFFECTS)}
        return {**result, 'preview_sha256': D._digest(result)}

    def proposal(self, finding):
        """Verify the same current maintenance source for an audit or a diagnostic finding."""
        pattern = (finding.get('classification'), finding.get('component'), finding.get('symptom'))
        snapshot = (pattern == ('source-defect', 'documentation-snapshot', 'markdown-extension-omitted')
                    and finding.get('scope') == {'source_path': SOURCE, 'operation': OPERATION}
                    and finding.get('conditions') == {'recipe_id': RECIPE, 'lane': 'unit', 'assertion_id': CHECK})
        diagnostic = (finding.get('classification') == 'source-defect'
                      and finding.get('reproduction', {}).get('kind') == 'director-resource-check')
        D._require((snapshot or diagnostic) and finding.get('evidence'),
                   'Selected audit evidence does not qualify for this bounded source repair')
        source_path = finding['scope']['source_path']
        director, area, root = self._area(source_path)
        maintenance = self._maintenance(finding, root)
        tree = self._source_tree(root, maintenance)
        source = D._safe_path(tree, source_path)
        D._require(D.WF.file_hash(source) == finding['generation']['source_sha256']
                   and (not snapshot or source.read_bytes().count(DEFECT) == 1), 'The exact controlled source generation changed')
        spec = _repair_scenario(finding)
        if diagnostic:
            for path, digest in spec['fixtures'].items():
                D._require(D.WF.file_hash(D._safe_path(tree, path)) == digest, 'Reproduction input differs in maintenance source')
        plan = {'schema': 1, 'director_id': director, 'source': area, 'finding': finding, 'scenario': spec}
        if diagnostic:
            recipe, _ = D.WF.recipe_for(D.WF.Store(root, neutral=True), _case_check(plan))
            D._require(D._portable_recipe(root, root, recipe, source_path, source_path) == spec['recipe_sha256'],
                       'Maintenance reproduction recipe differs from the executed product check')
        if maintenance:
            plan['maintenance'] = maintenance
        return plan, root

    def _load(self, repair_id, *, verify_original=True):
        receipt, _ = D._read(self.registry.root, _archive('repair', repair_id))
        D._require(receipt and receipt['repair_id'] == repair_id and _repair_id(receipt['preview']['plan']) == repair_id
                   and D._digest({key: value for key, value in receipt.items() if key != 'receipt_sha256'}) == receipt['receipt_sha256'],
                   'The exact owner-approved repair intake is unavailable or changed')
        plan = receipt['preview']['plan']
        source_path = plan['finding']['scope']['source_path']
        director, area, root = self._area(source_path)
        D._require(plan.get('maintenance') == self._maintenance(plan['finding'], root), 'Maintenance branch binding changed')
        D._require(plan['director_id'] == director and plan['source'] == area,
                   'Registered source authority changed after repair approval')
        if verify_original:
            tree = self._source_tree(root, plan.get('maintenance'))
            D._require(D.WF.file_hash(D._safe_path(tree, source_path)) == plan['finding']['generation']['source_sha256'],
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
                D._require(preview is not None, 'Original source repair preview unavailable')
                source_path = preview['plan']['finding']['scope']['source_path']
                director, area, root = self._area(source_path)
                tree = self._source_tree(root, preview['plan'].get('maintenance'))
                audited_run = payload['request']['audit']['director_run_id']
                run_path = '.skill-tree/director/runs/' + audited_run.lower() + '.json'
                D._require(preview is not None and preview['repair_id'] == repair_id
                           and preview['preview_sha256'] == payload['expected_preview_sha256']
                           and preview['plan']['director_id'] == director and preview['plan']['source'] == area
                           and preview['audit_run_sha256'] == D.WF.file_hash(D._safe_path(self.registry.root, run_path))
                           and preview['queue_sha256'] == D.WF.file_hash(root / '.skill-tree/documents/future.md')
                           and preview['plan']['finding']['generation']['source_sha256'] == D.WF.file_hash(D._safe_path(tree, source_path)),
                           'Source repair preview or queue changed before owner selection')
                case = {'schema': 1, 'repair_id': repair_id, 'preview': preview, 'owner': owner, 'effects': effects,
                        'request_sha256': owner_key['request_sha256'], 'recorded_at': D.WF.now()}
                case['receipt_sha256'] = D._digest(case)
                self.store.expect_unchanged(relative, baseline)
                self.store.commit({relative: D.WF.dump(case)})
            else:
                D._require(case['request_sha256'] == owner_key['request_sha256'], 'Original source repair approval differs')
        case, root = self._load(repair_id)
        plan = case['preview']['plan']
        finding = plan['finding']['finding_sha256']
        assertion = plan['scenario']['assertion']
        return self._deliver(case, root, 'intake', {'expected_source_hash': case['preview']['queue_sha256'],
            'title': _case_title(plan), 'description': f'The original Director source finding is `{finding}`. {assertion}',
            'expected_behavior': assertion, 'classification': {'kind': 'defect', 'reason': 'Verified installed resource failed the recorded control.'}})

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
        plan = case['preview']['plan']
        finding = plan['finding']['finding_sha256']
        check = _case_check(plan)
        body = (f"Goal:\n- {check['assertion']}\n\nTouch:\n- {plan['finding']['scope']['source_path']}\n\n"
                f"Source:\n- Director finding `{finding}`.\n\nValidation:\n```json\n"
                + json.dumps({'checks': [check]}, sort_keys=True) + f"\n```\n\nAcceptance:\n- {check['assertion']}\n")
        return self._deliver(case, root, 'process', {'expected_source_hash': payload['expected_source_hash'],
            'selectors': [pending], 'dispositions': {pending: {'status': 'promoted', 'reason': 'The observed fixture bounds the source repair.'}},
            'tasks': [{'title': _case_title(plan), 'body': body, 'parent_pending_ids': [pending]}]})

    def start(self, payload):
        D._object(payload, {'repair_id', 'task_id', 'expected_source_hash', 'owner', 'workspace'})
        case, root = self._authorized(payload, 'launch')
        result = self._observed(case, root, 'process')['observed_result']
        task = payload['task_id']
        D._require(result is not None and result['created_ids'] == [task], 'Launch only the exact processed repair T')
        work = payload['workspace']
        D._object(work, {'base_branch', 'branch', 'worktree'}, {'local_base', 'local_base_authorization', 'remote'})
        maintenance = case['preview']['plan'].get('maintenance')
        if maintenance:
            D._require(work['base_branch'] == maintenance['branch'] and work.get('local_base') is True,
                       'Use the registered local project maintenance branch as the source base')
            remote = _load_module('director-maintenance').inspect(self.registry.root, maintenance['project_id'])['remote']
            D._require(work.get('remote', remote) == remote, 'Use the registered upstream remote for this project source repair')
            work = {**work, 'remote': remote}
        return self._deliver(case, root, 'start', {**work, 'expected_source_hash': payload['expected_source_hash']},
                             {'mode': 'next', 'selector': task, 'limits': None})

    def _package_pins(self, worktree, target, flavor, base_oid, operation, helper, source_path):
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
        D._require(value['output_digests'][operation][helper] == D.WF.file_hash(worktree / source_path),
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

    def _resource_check(self, row, worktree, spec, source_path, digest, *, red):
        result = 'red' if red else 'pass'
        D._require(row and row['result'] == result and row['actual_lane'] == spec['lane']
                   and row['classification'] == 'executed-control' and len(row['evidence']) == 1
                   and row['sources'] == {source_path: digest, **spec['fixtures']}
                   and row['counts'] == {'expected': 1, 'discovered': 1, 'passed': int(not red), 'failed': int(red), 'skipped': 0}
                   and (not red or row.get('failure_category') == 'expected-behavior'),
                   'Candidate requires matching executed resource checks')
        ref = row['evidence'][0]
        proof, sha = D._read(worktree, ref['path'])
        D._require(ref.get('available') and sha == ref['sha256'] and proof == {
            'schema': 1, 'kind': 'director-resource-check', 'assertion_id': spec['assertion_id'],
            'installed_path': source_path, 'expected': spec['expected'], 'observed': spec['observed'] if red else spec['expected']},
            'Resource evidence is missing, changed or from another scenario')
        return {'result': 'fail' if red else 'pass', 'scenario_sha256': D._digest(spec),
                'record_sha256': D._digest(row), 'attempt_id': row['attempt_id'],
                'evidence': {key: ref[key] for key in ('path', 'sha256')}}

    def candidate_preview(self, payload):
        D._object(payload, {'repair_id', 'pending_id', 'task_id', 'run_id', 'outcome_id', 'composition_target',
                            'flavor', 'provider', 'owner', 'review_ref'})
        case, root = self._authorized(payload, 'freeze-candidate')
        D._require(D._token(payload['review_ref']) and D._token(payload['provider']), 'Candidate requires exact owner review and a selected host')
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
        source_path = finding['scope']['source_path']
        spec = case['preview']['plan']['scenario']
        snapshot = spec['id'] == SCENARIO
        old = D.WS.local_git(worktree, 'show', base_oid + ':' + source_path).stdout
        before = D.WF.digest(old)
        current = D._safe_path(worktree, source_path).read_bytes()
        after = D.WF.digest(current)
        rows = D.WS.local_git(worktree, 'diff', '--numstat', '-z', '--no-renames', '--no-ext-diff', base_oid, '--').stdout.split(b'\0')[:-1]
        changed = [row.split(b'\t', 2)[2] for row in rows]
        D._require(before == finding['generation']['source_sha256'] and before != after and changed == [source_path.encode()]
                   and (not snapshot or old.count(DEFECT) == 1 and current == old.replace(DEFECT, REPAIRED)
                        and (worktree / 'README.md').read_bytes() == INPUT),
                   'Candidate contains changes outside the exact reviewed repair')
        checks = outcome['check_results']
        D._require(len(checks) == 1 and checks[0]['check']['id'] == spec['assertion_id']
                   and checks[0]['check']['recipe_id'] == spec['recipe_id'] and checks[0]['check']['assertion'] == spec['assertion']
                   and isinstance(checks[0].get('red'), dict) and checks[0]['red']['definition'] == checks[0]['result']['definition'],
                   'Canonical outcome does not bind the same original assertion and check')
        if not snapshot:
            store = D.WF.Store(root, run_id=run['id'])
            store.load()
            recipe, environment = D.WF.recipe_for(store, checks[0]['check'])
            D._require(D._portable_recipe(worktree, root, recipe, source_path, source_path) == spec['recipe_sha256']
                       and checks[0]['red']['environment_identity'] == checks[0]['result']['environment_identity'] == environment,
                       'Reviewed source checks must execute the original portable recipe')
        verified = {}
        for label, row, digest, red in [('original', checks[0]['red'], before, True), ('repaired', checks[0]['result'], after, False)]:
            verified[label] = (self._observed_check(row, worktree, digest, red=red) if snapshot else
                               self._resource_check(row, worktree, spec, source_path, digest, red=red))
        target = D._root(payload['composition_target'])
        D._require(target != root and target != worktree, 'Select a separate reviewed package composition target')
        verified_profile = D._inspect_profile(target)
        receipt, receipt_sha = D._read(target, '.skill-tree/installation/profile.json')
        D._require(verified_profile['kind'] == 'owned-profile' and verified_profile['sha256'] == receipt_sha
                   and receipt['flavor'] == payload['flavor'] and payload['provider'] != 'generic'
                   and any(record['name'] == finding['scope']['operation']
                           and payload['provider'] in record.get('providers', [record['provider']])
                           for record in receipt['destinations'].values()),
                   'Candidate requires a verified composition target owned by the selected host')
        packages = self._package_pins(worktree, target, payload['flavor'], base_oid, finding['scope']['operation'],
                                      'scripts/create-documentation-snapshot.py' if snapshot else spec['resource'], source_path)
        source_inventory = packages.pop('source_inventory_sha256')
        plan = case['preview']['plan']
        body = {'schema': 1, 'kind': 'director-source-repair-candidate', 'finding_sha256': finding['finding_sha256'],
                'route': {'area_id': plan['source']['id'], 'queue_id': plan['source']['queue_id'], 'pending_id': payload['pending_id'],
                          'processing_run_id': processed['id'], **selected},
                'owner': payload['owner'], 'source': {'revision': 'source-inventory:' + source_inventory, 'source_inventory_sha256': source_inventory},
                'packages': {'flavor': payload['flavor'], 'provider': payload['provider'], **packages}, 'scenario': spec, 'checks': verified,
                'review': {'reference': payload['review_ref'], 'source_path': source_path, 'source_base_commit': base_oid,
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

    def integrate(self, payload):
        D._object(payload, {'candidate_sha256', 'repair_id', 'owner'})
        owner = _owner(payload['owner'])
        case, root = self._load(payload['repair_id'], verify_original=False)
        plan = case['preview']['plan']
        D._require('integrate' in case['effects'] and owner['actor'] == case['owner']['actor'] and plan.get('maintenance'),
                   'Authorize integration on the exact project maintenance branch')
        candidate = self.candidate_read({'candidate_sha256': payload['candidate_sha256']})
        finding, review = plan['finding'], candidate['review']
        D._require(candidate['finding_sha256'] == finding['finding_sha256']
                   and candidate['route']['queue_id'] == plan['source']['queue_id']
                   and candidate['owner']['actor'] == owner['actor'], 'Candidate belongs to another source repair')
        dispatched = self._observed(case, root, 'start')['observed_result']
        D._require(dispatched and dispatched['id'] == candidate['route']['run_id'], 'Candidate has a different repair run')
        source_path = finding['scope']['source_path']
        base = review['source_base_commit']
        D._require(source_path == review['source_path'] and base == dispatched['workspace']['base_commit']
                   and dispatched['workspace']['base_branch'] == plan['maintenance']['branch'],
                   'Reviewed source repair base changed')
        ref = 'refs/skill-tree/director/candidates/' + candidate['candidate_sha256']
        if D.WS.local_git(root, 'show-ref', '--verify', '--quiet', ref, accepted=(0, 1)).returncode:
            tree = self.objectives._read_run_root(root, dispatched)
            D._require(tree is not None and D.WF.file_hash(D._safe_path(tree, source_path)) == review['after_sha256'],
                       'Recover the verified candidate bytes before integration')
            entry = D.WS.local_git(root, 'ls-tree', '-z', base, '--', source_path).stdout
            mode = entry.split(b' ', 1)[0].decode()
            D._require(mode in {'100644', '100755'}, 'Candidate requires an existing regular source file')
            blob = D.WS.local_git_text(tree, 'hash-object', '-w', '--no-filters', '--', source_path)
            D._require(D.WF.digest(D.WS.local_git(root, 'cat-file', 'blob', blob).stdout) == review['after_sha256'],
                       'Reviewed source bytes changed during integration')
            with tempfile.TemporaryDirectory() as directory:
                index = Path(directory) / 'index'
                D.WS.local_git(root, 'read-tree', base, index=index)
                D.WS.local_git(root, 'update-index', '--cacheinfo', mode, blob, source_path, index=index)
                proposed = D.WS.local_git(root, 'write-tree', index=index).stdout.decode().strip()
            oid = D.WS.local_git_text(root, 'commit-tree', proposed, '-p', base, '-m', _case_title(plan),
                                      '-m', 'Skill-Tree-Candidate: ' + candidate['candidate_sha256'])
            # A concurrent retry may have already reserved the same reviewed tree.
            D.WS.local_git(root, 'update-ref', ref, oid, '', accepted=(0, 128))
        commit = D.WS.local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}')
        return _load_module('director-maintenance').integrate(self.registry.root, plan['maintenance']['project_id'],
                   expected_head=base, candidate_commit=commit, reviewed_paths={source_path: review['after_sha256']}, owner=owner)

    def run(self, command, payload):
        return {'repair-preview': self.preview, 'repair-intake': self.intake, 'repair-process': self.process,
                'repair-start': self.start, 'repair-candidate-preview': self.candidate_preview,
                'repair-candidate-apply': self.candidate_apply, 'repair-candidate-read': self.candidate_read, 'repair-integrate': self.integrate}[command](payload)


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
