"""Read canonical input for Director planning and freeze exact parent-owned scope."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path, PurePosixPath
import subprocess


COMMANDS = {'plan-preview', 'plan-freeze', 'plan-context', 'plan-impact'}
PLAN_SELECTOR = {'objective_id', 'plan_id', 'plan_revision'}
FIXTURE = 'tests/fixtures/director'
NARRATIVE = 'narrative-state.py'
NARRATIVE_SHA = 'ad6618d06fc1b2cac79694a64ff5733bdd03a330e0714851e04e185d108c1388'


class PlanSources:
    """Resolve only supported adapters against verified canonical bindings."""

    def __init__(self, director, objectives, compiler, registry, bindings):
        self.D = director
        self.O = objectives
        self.C = compiler
        self.registry = registry
        self.bindings = bindings
        self.source = Path(__file__).resolve().parents[2]
        self.profiles = {}

    def root(self, area):
        return self.O._child_root(self.registry, self.bindings, area['id'])

    def area_root(self, area):
        return self.D._area_path(self.root(area), area['scope'])

    def owned_profile(self, area, root):
        if area['queue_id'] not in self.profiles:
            proof = self.D._inspect_profile(root)
            if proof.get('kind') == 'repository-local-source':
                if area['role'] != 'source-maintenance':
                    return None
                relative = '.skill-tree/common/scripts/workflow-state.py'
                helper = self.D._safe_path(root, relative)
                expected = self.D.WF.file_hash(Path(__file__).with_name('workflow-state.py'))
                if not helper.is_file() or self.D.WF.file_hash(helper) != expected:
                    return None
                return expected
            self.profiles[area['queue_id']] = proof.get('sha256')
        return self.profiles[area['queue_id']]

    def narrative(self):
        path = Path(__file__).with_name(NARRATIVE)
        if path.is_symlink() or self.D.WF.file_hash(path) != NARRATIVE_SHA:
            return None
        return self.D.WF.owned_module('director_narrative_source', path)

    def fixture(self):
        manifest, digest = self.D._read(self.source, FIXTURE + '/fixture-manifest.json')
        if not isinstance(manifest, dict) or manifest.get('schema') != 1:
            return None, None
        return manifest, digest

    def fixture_bytes(self, area, row):
        relative = PurePosixPath(row['path']).relative_to(PurePosixPath(area['scope']))
        digest = self.D.WF.file_hash(self.D._safe_path(self.area_root(area), relative.as_posix()))
        return digest

    def fixture_evidence(self, area, capability):
        manifest, sha = self.fixture()
        if manifest is None:
            return None
        key = {
            'fixture-canon': 'story', 'fixture-artifact': 'art', 'fixture-consumer': 'game',
        }[capability]
        if area['scope'] != manifest['areas'].get(key):
            return None
        row = {'story': manifest['story']['accepted'], 'art': manifest['artifact'], 'game': manifest['consumer']}[key]
        observed = self.fixture_bytes(area, row)
        return {'manifest_sha256': sha, 'record_sha256': observed} if observed == row['sha256'] else None

    def qualify(self, area, capability):
        if capability not in {'core-task', 'narrative-canon', 'fixture-canon', 'fixture-artifact', 'fixture-consumer'}:
            return None
        try:
            root = self.root(area)
            profile = self.owned_profile(area, root)
            if profile is None:
                return None
            if capability.startswith('fixture-'):
                evidence = self.fixture_evidence(area, capability)
            elif capability == 'narrative-canon':
                module = self.narrative()
                directory = self.D._safe_path(self.area_root(area), '.narrative/snapshots')
                evidence = {'helper_sha256': NARRATIVE_SHA} if module is not None and directory.is_dir() else None
            else:
                evidence = {'interface': area['interface'], 'queue_id': area['queue_id']}
            if evidence is None:
                return None
            branch = self.D.WS.local_git(root, 'symbolic-ref', '--quiet', 'HEAD', accepted=(0, 1))
            head = self.D.WS.local_git_text(root, 'rev-parse', '--verify', 'HEAD^{commit}')
        except (ValueError, OSError, subprocess.TimeoutExpired):
            return None
        qualification = {'area_id': area['id'], 'capability': capability, 'head': head,
                         'ref': branch.stdout.decode().strip(), 'profile_sha256': profile, 'evidence': evidence}
        return {'head': head, 'profile_sha256': profile, 'qualification_sha256': self.C.digest(qualification)}

    def child_task(self, area, child):
        root = self.root(area)
        store = self.D.WF.Store(root, route_queue=False, neutral=True)
        task_id = child['task_id']
        tasks = self.D.WF.parse(store.text())
        task = next((record for record in tasks if record['id'] == task_id), None)
        if task is not None:
            return {'task_id': task_id, 'body_sha256': self.D.WF.digest(task['body'].encode())}
        if not self.D.WF.valid_id(task_id, 'T'):
            return None
        matches = [row for row in store.outcomes() if row.get('task_id') == task_id]
        if len(matches) != 1 or matches[0].get('disposition') != 'completed':
            return None
        outcome, = matches
        fingerprint = outcome.get('task_context', {}).get('content_fingerprint')
        registry = store.load().get('run_registry') or {}
        run = registry.get('runs', {}).get(outcome.get('run_id'), {})
        if not self.D._sha(fingerprint) or run.get('completion_refs', {}).get(task_id) != outcome.get('id'):
            return None
        return {'task_id': task_id, 'body_sha256': fingerprint}

    def fixture_pin(self, area, pin):
        manifest, _ = self.fixture()
        if manifest is None:
            return {'status': 'unsupported'}
        selected = manifest['story'] if pin['adapter'] == 'fixture-narrative' else manifest['artifact']
        role = 'story' if pin['adapter'] == 'fixture-narrative' else 'art'
        if area['scope'] != manifest['areas'][role]:
            return {'status': 'unsupported'}
        if pin['record_id'] != selected['id']:
            return {'status': 'missing'}
        records = [selected['accepted'], selected['changed']] if role == 'story' else [selected]
        row = next((item for item in records if item['revision'] == pin['revision']), None)
        if row is None:
            return {'status': 'missing'}
        if pin.get('path', row['path']) != row['path'] or 'snapshot' in pin:
            return {'status': 'changed'}
        actual = self.fixture_bytes(area, row)
        if actual is None:
            return {'status': 'missing'}
        if actual != row['sha256'] or pin['sha256'] != actual:
            return {'status': 'changed'}
        return {'status': 'verified', 'revision': row['revision'], 'sha256': actual}

    def narrative_pin(self, area, pin):
        module = self.narrative()
        if module is None:
            return {'status': 'unsupported'}
        snapshot = pin.get('snapshot')
        if not module.valid_digest(snapshot):
            return {'status': 'missing'}
        project = module.Project(self.area_root(area))
        relative = project.snapshot_path(snapshot).relative_to(project.root).as_posix()
        if pin.get('path', relative) != relative:
            return {'status': 'changed'}
        if not project.snapshot_path(snapshot).is_file():
            return {'status': 'missing'}
        archive = project.snapshot(snapshot)
        record = archive['proposal']['entries'].get(pin['record_id'])
        if record is None:
            return {'status': 'missing'}
        revision = record['revision']
        if (pin['revision'], pin['sha256']) != (revision, revision):
            return {'status': 'changed'}
        return {'status': 'verified', 'revision': revision, 'sha256': revision}

    def core_pin(self, area, pin):
        relative = '.skill-tree/documents/future.md'
        if not self.C.task_id(pin['record_id'], {'P', 'T'}):
            return {'status': 'missing'}
        if pin.get('path', relative) != relative or 'snapshot' in pin:
            return {'status': 'changed'}
        task = self.child_task(area, {'task_id': pin['record_id']})
        if task is None:
            return {'status': 'missing'}
        sha = task['body_sha256']
        if (pin['revision'], pin['sha256']) != (sha, sha):
            return {'status': 'changed'}
        return {'status': 'verified', 'revision': sha, 'sha256': sha}

    def pin(self, area, pin):
        adapter = {
            'core-task': self.core_pin,
            'narrative-canon': self.narrative_pin,
            'fixture-narrative': self.fixture_pin,
            'fixture-artworkshop': self.fixture_pin,
        }.get(pin['adapter'])
        if adapter is None:
            return {'status': 'unsupported'}
        try:
            return adapter(area, pin)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            return {'status': 'unavailable'}

    def validate_write_paths(self, director_root, plan):
        for item in plan['assignments']:
            if item['workspace'] == 'artifact':
                parent = f".skill-tree/artifacts/director/candidates/{item['id']}"
                for relative in item['write_paths']:
                    self.D._safe_path(director_root, f'{parent}/{relative}')
            else:
                area = self.registry['areas'][item['area']['id']]
                for relative in item['write_paths']:
                    self.D._safe_path(self.area_root(area), relative)


class DirectorPlans:
    def __init__(self, registry, director, objectives, compiler):
        self.D = director
        self.O = objectives
        self.C = compiler
        self.registry = registry
        self.ledger = self.O.ObjectiveLedger(registry)

    def preview(self, request):
        self.D._object(request, {'plan_id', 'plan_revision', 'objective_id', 'objective_revision',
                                 'objective_sha256', 'assignments'})
        ledger, registry, bindings, basis = self.ledger._load(request['objective_id'])
        return self._compile(request, ledger, registry, bindings, basis)

    def _compile(self, request, ledger, registry, bindings, basis):
        revision = request['objective_revision']
        self.D._require(type(revision) is int and 0 < revision <= len(ledger['revisions']),
                        'Exact objective revision is unavailable')
        objective = {'director_id': ledger['director_id'], 'objective_id': ledger['objective_id'],
                     'revision': ledger['revisions'][revision - 1]}
        sources = PlanSources(self.D, self.O, self.C, registry, bindings)
        compiled = self.C.compile_plan(registry, objective, request, sources.qualify, sources.pin, sources.child_task)
        sources.validate_write_paths(self.registry.root, compiled['plan'])
        preview = {**compiled, 'objective_current': objective['revision']['sha256'] == ledger['current']['sha256']}
        return {**preview, 'preview_sha256': self.C.digest({'preview': preview, 'basis': basis})}

    def freeze(self, payload):
        fields = {'plan_id', 'plan_revision', 'objective_id', 'objective_revision', 'objective_sha256', 'assignments'}
        self.D._object(payload, fields | {'expected_preview_sha256'})
        self.D._require(self.D._sha(payload['expected_preview_sha256']),
                        'Freezing requires the exact reviewed preview digest')
        request = {key: payload[key] for key in fields}
        key = self.O._plan_key(request['plan_id'], request['plan_revision'])

        def record(ledger, registry, bindings, basis):
            preview = self._compile(request, ledger, registry, bindings, basis)
            self.D._require(preview['objective_current'] and preview['preview_sha256'] == payload['expected_preview_sha256'],
                            'Plan, sources or current objective changed since preview')
            plan = preview['plan']
            assignments = {}
            for item in plan['assignments']:
                area = registry['areas'][item['area']['id']]
                task_id = item['child'].get('task_id', '')
                assignments[item['id']] = {'area': self.O._area_identity(area),
                                           'task_ids': [task_id] if self.D.WF.valid_id(task_id, 'T') else []}
            pin = {name: request[name] for name in ('plan_id', 'plan_revision', 'objective_revision', 'objective_sha256')}
            pin.update(plan_sha256=preview['sha256'], assignments=assignments, frozen=deepcopy(plan))
            existing = ledger['plans'].get(key)
            if existing is not None:
                self.D._require(existing == pin, 'Plan identity already pins different content')
                return {'status': 'unchanged', 'plan_id': request['plan_id'], 'plan_revision': request['plan_revision'],
                        'plan_sha256': pin['plan_sha256']}
            ledger['plans'][key] = pin
            return {'status': 'frozen', 'plan_id': request['plan_id'], 'plan_revision': request['plan_revision'],
                    'plan_sha256': pin['plan_sha256']}

        return self.ledger._write('plan-freeze', payload, record)

    def frozen(self, selector):
        self.D._object(selector, PLAN_SELECTOR)
        key = self.O._plan_key(selector['plan_id'], selector['plan_revision'])
        ledger, _, _, _ = self.ledger._load(selector['objective_id'])
        pin = ledger['plans'].get(key)
        plan = pin.get('frozen') if isinstance(pin, dict) else None
        self.D._require(isinstance(plan, dict) and self.C.digest(plan) == pin.get('plan_sha256')
                        and (plan['plan_id'], plan['plan_revision']) == (selector['plan_id'], selector['plan_revision'])
                        and plan['objective']['objective_id'] == selector['objective_id']
                        and (plan['objective']['objective_revision'], plan['objective']['objective_sha256'])
                        == (pin['objective_revision'], pin['objective_sha256']),
                        'Exact immutable frozen plan is unavailable or changed')
        return plan, pin['plan_sha256']

    def context(self, selector):
        plan, sha = self.frozen(selector)
        return {'plan_id': plan['plan_id'], 'plan_revision': plan['plan_revision'], 'plan_sha256': sha,
                **self.C.context(plan)}

    def impact(self, payload):
        self.D._object(payload, PLAN_SELECTOR | {'changed'})
        plan, sha = self.frozen({key: payload[key] for key in PLAN_SELECTOR})
        return {'plan_id': plan['plan_id'], 'plan_revision': plan['plan_revision'], 'plan_sha256': sha,
                **self.C.impact(plan, payload['changed'])}

    def run(self, command, payload):
        operations = {'plan-preview': self.preview, 'plan-freeze': self.freeze,
                      'plan-context': self.context, 'plan-impact': self.impact}
        return operations[command](payload)
