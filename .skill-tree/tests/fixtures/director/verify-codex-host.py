"""Check the structure and exact links of a trusted Director host capture."""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


BASE = '.skill-tree/history/validation/director/'
MANIFEST = BASE + 'codex-host.json'
RESULT = BASE + 'codex-host-result.json'
PROFILE = '.skill-tree/installation/profile.json'
MANIFEST_KIND = 'director-codex-host-manifest'
RESULT_KIND = 'director-codex-host-result'
CHECK = 'director-actual-codex'
TASK = 'T-0440b3b6-2c5a-4bab-a932-670f06a14663'
RECIPE = 'director-codex-observed'
WORKER_TOOLS = {'collaboration.spawn_agent', 'collaboration.followup_task'}
OWNER_TOOLS = {'codex-user-message', 'functions.request_user_input_async'}
SOURCE_PATHS = {
    '.skill-tree/common/scripts/director-state.py',
    '.skill-tree/common/scripts/director-run.py',
    '.skill-tree/common/scripts/director-questions.py',
    '.skill-tree/common/scripts/director-dispatch.py',
    '.skill-tree/validation-recipes.json',
    '.skill-tree/tests/fixtures/director/verify-codex-host.py',
}
QUESTION_FIELDS = {
    'director_dispatch', 'director_run_id', 'child_run_id', 'task_id', 'start_receipt_sha256',
    'question_id', 'attempt_id', 'question_sha256',
}


class InvalidCapture(ValueError):
    pass


def check(test, message):
    if not test:
        raise InvalidCapture(message)


def fields(value, expected, reason):
    check(isinstance(value, dict) and value.keys() == expected, reason)


def digest(content):
    return sha256(content).hexdigest()


def core_digest(value):
    return digest((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def hashes(*values):
    return all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) for value in values)


def exact_id(value, prefix):
    return isinstance(value, str) and re.fullmatch(re.escape(prefix) + r'-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value)


def nonempty(*values):
    return all(isinstance(value, str) and value.strip() and '\0' not in value for value in values)


def instant(value):
    check(nonempty(value), 'Capture timestamp is unavailable')
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    check(timestamp.tzinfo is not None, 'Capture timestamp needs a timezone')
    return timestamp


def read(root, relative):
    result = root
    for part in relative.split('/'):
        check(part not in {'', '.', '..'} and '\\' not in part and '\0' not in part,
              'Capture paths must be portable')
        result = result / part
        check(not result.is_symlink(), 'Symlinks are unsupported for native capture inputs')
    return result.read_bytes()


def with_receipt(record, reason):
    check(isinstance(record, dict) and hashes(record.get('receipt_sha256')), reason)
    body = {key: value for key, value in record.items() if key != 'receipt_sha256'}
    check(core_digest(body) == record['receipt_sha256'], reason)


def manifest_inputs(root, manifest):
    fields(manifest, {'schema', 'kind', 'task_id', 'check_id', 'source_run_id', 'fixture_id', 'profile_sha256',
                      'sources', 'result_path', 'created_at'}, 'Malformed native capture manifest')
    check(manifest['schema'] == 1 and manifest['kind'] == MANIFEST_KIND and manifest['task_id'] == TASK
          and manifest['check_id'] == CHECK and exact_id(manifest['source_run_id'], 'WR')
          and nonempty(manifest['fixture_id']) and manifest['result_path'] == RESULT,
          'Capture manifest does not cover the exact Director native check')
    fields(manifest['sources'], SOURCE_PATHS, 'Capture manifest must cover all selected authored inputs')
    for relative, expected in manifest['sources'].items():
        check(hashes(expected) and digest(read(root, relative)) == expected, 'Capture source changed: ' + relative)
    profile_bytes = read(root, PROFILE)
    check(digest(profile_bytes) == manifest['profile_sha256'], 'The owning installation profile changed')
    profile = json.loads(profile_bytes)
    recipe = profile.get('recipes', {}).get(RECIPE, {})
    check(recipe.get('lane') == 'native'
          and recipe.get('argv') == ['python3', '.skill-tree/tests/fixtures/director/verify-codex-host.py', '{project_root}'],
          'The admitted owning profile lacks the exact Director native recipe')
    return instant(manifest['created_at'])


def worker(actor, prepared):
    fields(actor, {'provider', 'tool', 'actor_id', 'context_id', 'request_sha256', 'return_sha256',
                   'requested_at', 'returned_at', 'creation_reference'}, 'Malformed actor observation')
    check(actor['provider'] == 'Codex collaboration' and actor['tool'] in WORKER_TOOLS
          and nonempty(actor['actor_id'], actor['context_id'], actor['creation_reference'])
          and hashes(actor['request_sha256'], actor['return_sha256']), 'Actual collaboration identity is unavailable')
    requested, returned = instant(actor['requested_at']), instant(actor['returned_at'])
    check(prepared <= requested <= returned, 'Worker call must follow native check preparation')
    return returned


def start_identity(start, scope):
    with_receipt(start, 'Original canonical start receipt is unavailable or invalid')
    identity = start['identity']
    check(identity['operation'] == 'start' and identity['director_id'] == scope['director_id']
          and identity['assignment_id'] == scope['assignment_id'] and identity['queue_id'] == scope['queue_id']
          and start['plan_sha256'] == scope['plan_sha256'] and start['result']['id'] == scope['child_run_id']
          and core_digest(start['result']['workspace']) == scope['workspace_sha256'],
          'Original canonical WR or worktree does not match the capture')


def question(row, scope, start, origin):
    fields(row, {'context', 'hold', 'release'}, 'Malformed question checkpoint evidence')
    context, hold, release = (row[name] for name in ('context', 'hold', 'release'))
    fields(context, QUESTION_FIELDS, 'Question lacks exact canonical child input')
    dispatch = context['director_dispatch']
    check((dispatch['director_id'], dispatch['assignment_id'], dispatch['queue_id'], dispatch['plan_sha256'])
          == (scope['director_id'], scope['assignment_id'], scope['queue_id'], scope['plan_sha256'])
          and (context['director_run_id'], context['child_run_id'], context['task_id'])
          == (scope['director_run_id'], scope['child_run_id'], scope['child_task_id'])
          and context['start_receipt_sha256'] == start['receipt_sha256']
          and exact_id(context['question_id'], 'DQ') and exact_id(context['attempt_id'], 'DA')
          and hashes(context['question_sha256']), 'Question does not name the preserved exact WR and attempt')
    context_sha = core_digest(context)
    for expected, receipt in (('director-question-hold', hold), ('director-question-release', release)):
        with_receipt(receipt, 'Question effect receipt is unavailable or invalid')
        check(receipt['effect'] == expected and receipt['context_sha256'] == context_sha
              and receipt['workspace_sha256'] == scope['workspace_sha256']
              and receipt['child_run_id'] == scope['child_run_id'] and receipt['task_id'] == scope['child_task_id'],
              'The question checkpoint changed run, task or worktree')
    answer = release['answer']
    check(answer['origin'] == origin and nonempty(answer['choice'], answer['actor'], answer['authority_ref'])
          and hashes(answer['evidence_sha256']), 'Release does not bind the expected answer origin')
    observed_hold, observed_release = instant(hold['recorded_at']), instant(release['recorded_at'])
    check(observed_hold <= observed_release, 'Release predates the original hold')
    return context, answer, observed_hold, observed_release


def owner_answer(value, context, answer, hold_at, release_at):
    fields(value, {'kind', 'tool', 'actor', 'reference', 'choice', 'question_id', 'attempt_id',
                   'child_run_id', 'observed_at', 'answer_sha256'}, 'Malformed owner observation')
    check(value['kind'] in {'owner-message', 'submitted-answer'} and value['tool'] in OWNER_TOOLS
          and nonempty(value['reference'], value['actor'], value['choice']) and hashes(value['answer_sha256']),
          'Actual owner event is unavailable')
    check(all(value[key] == context[key] for key in ('question_id', 'attempt_id', 'child_run_id'))
          and (value['actor'], value['choice']) == (answer['actor'], answer['choice'])
          and value['answer_sha256'] == core_digest({key: value[key] for key in ('actor', 'reference', 'kind')})
          and value['answer_sha256'] == answer['evidence_sha256'],
          'Observed owner input differs from the exact question release')
    observed = instant(value['observed_at'])
    check(hold_at <= observed <= release_at, 'Owner answer must arrive while the exact child question is held')
    return observed


def controls(value, scope, material, owner_at, hold_at, release_at, finished_at):
    fields(value, {'restart', 'wrong_recipient', 'duplicate', 'independent_sibling', 'same_run_progress'},
           'Required native controls are unavailable')
    restart, wrong, duplicate, sibling, progress = (value[key] for key in
        ('restart', 'wrong_recipient', 'duplicate', 'independent_sibling', 'same_run_progress'))
    marker = material['hold']['receipt_sha256']
    check(restart['observer_invocation_id'] != restart['previous_invocation_id']
          and nonempty(restart['observer_invocation_id'], restart['previous_invocation_id'])
          and restart['hold_receipt_sha256'] == marker and restart['child_run_id'] == scope['child_run_id']
          and restart['workspace_sha256'] == scope['workspace_sha256']
          and hold_at <= instant(restart['observed_at']) <= owner_at,
          'A fresh Director process did not recover the original held child')
    check(wrong['rejected'] is True and wrong['before_sha256'] == wrong['after_sha256']
          and hashes(wrong['before_sha256']) and wrong['hold_receipt_sha256'] == marker
          and hold_at <= instant(wrong['observed_at']) <= owner_at, 'Wrong-recipient guard failed or changed the held child')
    check(duplicate['before_sha256'] == duplicate['after_sha256'] and hashes(duplicate['before_sha256'])
          and duplicate['release_receipt_sha256'] == material['release']['receipt_sha256']
          and release_at <= instant(duplicate['observed_at']) <= finished_at, 'Duplicate answer did not replay exactly')
    receipt = sibling['intake_receipt']
    with_receipt(receipt, 'Sibling does not supply a canonical intake receipt')
    check(receipt['identity']['director_id'] == scope['director_id'] and receipt['identity']['operation'] == 'intake'
          and receipt['identity']['assignment_id'] != scope['assignment_id']
          and receipt['identity']['queue_id'] != scope['queue_id'] and receipt['plan_sha256'] == scope['plan_sha256']
          and exact_id(receipt['result']['id'], 'P') and sibling['hold_receipt_sha256'] == marker
          and sibling['held_before_sha256'] == sibling['held_after_sha256'] and hashes(sibling['held_before_sha256'])
          and hold_at <= instant(sibling['observed_at']) <= owner_at, 'Independent sibling intake did not preserve the hold')
    check(progress['child_run_id'] == scope['child_run_id'] and progress['workspace_sha256'] == scope['workspace_sha256']
          and progress['task_id'] == scope['child_task_id'] and progress['from_phase'] != progress['to_phase']
          and nonempty(progress['from_phase'], progress['to_phase'])
          and progress['to_phase'] != 'blocked' and hashes(progress['observed_sha256'])
          and release_at <= instant(progress['observed_at']) <= finished_at,
          'Original WR did not demonstrate scoped resumed progress')


def verify(root):
    manifest_raw = read(root, MANIFEST)
    manifest = json.loads(manifest_raw)
    created = manifest_inputs(root, manifest)
    report = json.loads(read(root, RESULT))
    fields(report, {'schema', 'kind', 'manifest_sha256', 'attempt_id', 'prepared_at', 'scope', 'worker',
                    'start_receipt', 'fact', 'material', 'owner', 'controls', 'finished_at'}, 'Malformed native result')
    check(report['schema'] == 1 and report['kind'] == RESULT_KIND and report['manifest_sha256'] == digest(manifest_raw)
          and exact_id(report['attempt_id'], 'C'), 'Result is not linked to the exact prepared check manifest')
    prepared = instant(report['prepared_at'])
    finished = instant(report['finished_at'])
    check(created <= prepared <= finished, 'Native capture order is invalid')
    scope = report['scope']
    fields(scope, {'director_id', 'director_run_id', 'assignment_id', 'queue_id', 'plan_id', 'plan_sha256',
                   'child_task_id', 'child_run_id', 'workspace_sha256', 'fixture_id'}, 'Malformed native qualification scope')
    check(scope['fixture_id'] == manifest['fixture_id'] and nonempty(scope['director_id'], scope['assignment_id'])
          and all(exact_id(scope[field], prefix) for field, prefix in (
              ('director_run_id', 'DR'), ('queue_id', 'Q'), ('plan_id', 'PL'), ('child_task_id', 'T'), ('child_run_id', 'WR')))
          and hashes(scope['plan_sha256'], scope['workspace_sha256']), 'Native capture has wrong scope identity')
    worker_return = worker(report['worker'], prepared)
    start_identity(report['start_receipt'], scope)
    fact = report['fact']
    fields(fact, {'question', 'pin', 'observed_bytes_sha256'}, 'Malformed internal factual answer')
    internal, internal_answer, fact_hold, fact_release = question(
        fact['question'], scope, report['start_receipt'], 'approved-default')
    pin = fact['pin']
    check(pin.get('status') == 'verified' and nonempty(pin.get('record_id'), pin.get('revision'))
          and hashes(pin.get('sha256')) and pin['sha256'] == fact['observed_bytes_sha256']
          and internal_answer['evidence_sha256'] == core_digest(pin),
          'Internal factual resolution lacks current verified source evidence')
    material, answer, hold, release = question(report['material'], scope, report['start_receipt'], 'owner')
    check(material['question_id'] != internal['question_id'] and material['attempt_id'] != internal['attempt_id']
          and worker_return <= fact_hold <= fact_release <= hold <= release <= finished,
          'Internal and material questions must preserve ordered, distinct handoffs')
    observed_owner = owner_answer(report['owner'], material, answer, hold, release)
    controls(report['controls'], scope, report['material'], observed_owner, hold, release, finished)
    return {'status': 'pass', 'lane': 'native', 'task_id': TASK, 'check_id': CHECK,
            'attempt_id': report['attempt_id'], 'child_run_id': scope['child_run_id'],
            'scope': 'Trusted Codex host capture and structurally verified canonical fixture evidence'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root.resolve(strict=True)), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
