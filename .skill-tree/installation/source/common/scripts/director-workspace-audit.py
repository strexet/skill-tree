"""Request bounded read-only documentation audits from registered projects."""
import json
from pathlib import Path
import subprocess
import sys
import uuid


HERE = Path(__file__).resolve().parent
PROFILE = '.skill-tree/installation/profile.json'
AUDITOR = 'skill-tree-repo-documentation-audit'
VALIDATOR = 'validate-repository-documentation.py'
SCRIPTS = (VALIDATOR, 'workflow-state.py', 'run-workspaces.py',
           'validate-document-rules.py', 'validate-future-document.py')
OBSERVATION = ('documentation-structure', 'navigation-manifest', 'future-checkpoint-consistency')
GAPS = ('product-source-behavior', 'native-runtime', 'arbitrary-logs')
UNAVAILABLE = (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired)


def child_response(checkout):
    # Run the independently invoked validator from the reviewed Director copy.
    # Its inputs and cwd are the child project. A fresh cache prefix avoids
    # loading stale bytecode from either installation.
    prefix = HERE / ('.workspace-audit-source-' + uuid.uuid4().hex)
    return subprocess.run([sys.executable, '-I', '-B', '-X', f'pycache_prefix={prefix}',
                           str(HERE / VALIDATOR), str(checkout), '--format', 'json'],
                          cwd=checkout, capture_output=True, timeout=45)


class WorkspaceAudit:
    def __init__(self, director, objectives, registry, quiet):
        self.d = director
        self.o = objectives
        self.registry = registry
        self.quiet = quiet

    def audit_inputs(self, checkout, auditor):
        d, wf = self.d, self.d.WF
        inputs = [wf.NAVIGATION, wf.OUTCOME_LEDGER, PROFILE, '.skill-tree/config/repository.json', 'AGENTS.md', 'README.md']
        inputs.extend(f"{auditor['destination']}/scripts/{name}" for name in SCRIPTS)
        try:
            manifest, _ = d._read(checkout, wf.NAVIGATION)
        except ValueError:
            manifest = None  # Let the validator report a malformed manifest.
        declared = manifest.get('source_digests') if isinstance(manifest, dict) else None
        if isinstance(declared, dict):
            inputs.extend(declared)
        paths = {path: d._safe_path(checkout, path) for path in set(inputs)}
        hashes = {name: wf.file_hash(path) if path.is_file() else None for name, path in paths.items()}
        d._require(hashes[PROFILE] == auditor['profile_sha256'], 'Child profile changed during audit preflight')
        script_hashes = {name: hashes[f"{auditor['destination']}/scripts/{name}"] for name in SCRIPTS}
        d._require(d._digest(script_hashes) == auditor['toolchain_sha256'], 'Child audit tool changed during preflight')
        documents = '.skill-tree/documents'
        folder = d._safe_path(checkout, documents)
        hashes[documents] = wf.binding_snapshot(checkout, [documents]) if folder.exists() else None
        return hashes

    def auditor(self, checkout, project):
        d, wf = self.d, self.d.WF
        owned = d._inspect_profile(checkout)
        if owned['kind'] != 'owned-profile':
            return None
        profile, digest = d._read(checkout, PROFILE)
        d._require(digest == owned['sha256'], 'Child profile changed during audit preflight')
        project['flavor'] = owned['flavor']
        expected = {name: wf.file_hash(HERE / name) for name in SCRIPTS}
        d._require(all(d._sha(value) for value in expected.values()), 'Director audit validator is incomplete')
        for destination, package in sorted(profile['destinations'].items()):
            if package['name'] != AUDITOR:
                continue
            if any(package['files'].get(f'scripts/{name}') != digest for name, digest in expected.items()):
                continue
            return {'operation': AUDITOR, 'destination': destination, 'lane': 'child-tool',
                    'profile_sha256': owned['sha256'], 'package_sha256': package['identity'],
                    'tool_sha256': expected[VALIDATOR], 'toolchain_sha256': d._digest(expected), 'checks': list(OBSERVATION)}
        return None

    def audit_project(self, registry, bindings, area):
        d, wf = self.d, self.d.WF
        project = {'project_id': area['id'], 'role': area['role'], 'scope': area['scope'],
                   'repo_id': area['repo_id'], 'queue_id': area['queue_id'], 'capabilities': area['capabilities']}
        if 'audit' not in area['allowed_effects']:
            return {**project, 'status': 'denied', 'reason': 'project-audit-not-authorized'}
        if area['scope'] != '.':
            return {**project, 'status': 'unsupported', 'reason': 'no-child-auditor-for-narrow-scope'}
        try:
            checkout = self.o._child_root(registry, bindings, area['id'])
        except UNAVAILABLE:
            return {**project, 'status': 'unavailable', 'reason': 'canonical-project-binding-unavailable'}
        try:
            self.quiet(checkout)
        except ValueError:
            return {**project, 'status': 'blocked', 'reason': 'project-writer-or-installer-in-progress'}
        try:
            project['git_head'] = d.WS.local_git_text(checkout, 'rev-parse', 'HEAD')
            branch = d.WS.local_git(checkout, 'symbolic-ref', '--quiet', '--short', 'HEAD', accepted=(0, 1))
            project['git_branch'] = branch.stdout.decode().strip() or None
            audit = self.auditor(checkout, project)
            if audit is None:
                return {**project, 'status': 'unsupported', 'reason': 'matching-owned-child-auditor-unavailable'}
            inputs = self.audit_inputs(checkout, audit)
        except UNAVAILABLE:
            return {**project, 'status': 'unavailable', 'reason': 'child-audit-preflight-unavailable'}
        audit['request_sha256'] = d._digest({'project': project, 'auditor': audit, 'inputs': inputs})
        try:
            capture = child_response(checkout)
            response = json.loads(capture.stdout)
            d._object(response, {'ok', 'errors', 'warnings'})
            d._require(type(response['ok']) is bool and not capture.stderr
                       and all(isinstance(response[key], list) and all(isinstance(item, str) for item in response[key])
                               for key in ('errors', 'warnings'))
                       and response['ok'] == (not response['errors'])
                       and capture.returncode == int(not response['ok']), 'Unexpected child audit response')
        except UNAVAILABLE:
            return {**project, 'auditor': audit, 'status': 'unavailable', 'reason': 'child-audit-response-unavailable'}
        try:
            self.quiet(checkout)
            d._require(self.o._child_root(registry, bindings, area['id']) == checkout
                       and project['git_head'] == d.WS.local_git_text(checkout, 'rev-parse', 'HEAD')
                       and inputs == self.audit_inputs(checkout, audit), 'Child scope changed during audit')
        except UNAVAILABLE:
            return {**project, 'auditor': audit, 'status': 'unavailable', 'reason': 'child-audit-scope-changed'}
        # Raw diagnostics stay in the child. A digest binds actual stdout.
        verdict = 'pass' if response['ok'] else 'findings'
        result = {'verdict': verdict, 'error_count': len(response['errors']),
                  'warning_count': len(response['warnings']), 'stdout_sha256': wf.digest(capture.stdout)}
        return {**project, 'auditor': audit, 'status': 'observed', 'result': result}

    def read(self, request=None):
        d = self.d
        request = {} if request is None else request
        d._object(request, set(), {'project_ids'})
        self.quiet(self.registry.root)
        registry, bindings, basis = self.registry._load()
        d._require(registry is not None, 'Register Director projects before requesting a workspace audit')
        projects = {area_id: area for area_id, area in registry['areas'].items()
                    if area['role'] != 'source-maintenance'}
        if 'project_ids' in request:
            selected = d._tokens(request['project_ids'], 'Workspace audit project IDs')
            d._require(selected and set(selected) <= projects.keys(), 'Select exact registered project IDs')
        else:
            selected = projects.keys()
        results = [self.audit_project(registry, bindings, projects[name]) for name in sorted(selected)]
        self.quiet(self.registry.root)
        d._require(all(digest == d.WF.file_hash(d._safe_path(self.registry.root, path)) for path, digest in basis.items()),
                   'Registered workspace scope changed during audit')
        status = 'completed' if all(row['status'] == 'observed' for row in results) else 'partial'
        report = {'schema': 1, 'director_id': registry['director_id'], 'registry_revision': registry['revision'],
                  'status': status if results else 'empty', 'projects': results, 'coverage_gaps': list(GAPS)}
        return {**report, 'audit_sha256': d._digest(report)}
