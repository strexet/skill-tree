"""Verify current visual review scope, evidence and host presentation."""

from hashlib import sha256
from math import isclose, isfinite
from pathlib import PurePosixPath
import re

from evidence import evidence_file, hash_file, parse_record, png_dimensions, require


VIEW_ROLES = {'front', 'side', 'side-right', 'top', 'rear', 'section', 'attachment', 'perspective-a', 'perspective-b'}
GEOMETRY_STAGES = {'G2', 'G3', 'G4'}
ORTHOGRAPHIC_REFERENCE = 'orthographic-neutral'
ORTHOGRAPHIC_STAGES = {'G1', 'G2'}
ORTHOGRAPHIC_ROLES = {'front', 'side', 'top'}
ORTHOGRAPHIC_SYMMETRY_ROLES = {'front-back': 'rear', 'left-right': 'side-right'}
PERSPECTIVE_ROLES = {'perspective-a', 'perspective-b'}


def orthographic_input(stage):
    return f'orthographic-{stage.lower()}'


def named(values, label):
    require(isinstance(values, list) and all(isinstance(value, str) and
            re.fullmatch(r'[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*', value) for value in values) and len(set(values)) == len(values),
            f'Invalid {label} names')
    return values


def pinned_path(root, value, label):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, f'Invalid {label} pin')
    return evidence_file(root, value['path'])


def pin(root, value, label):
    path = pinned_path(root, value, label)
    require(hash_file(path) == value['sha256'], f'{label} bytes differ from the pin')
    return path


def record(root, value, label):
    raw = pinned_path(root, value, label).read_bytes()
    require(sha256(raw).hexdigest() == value['sha256'], f'{label} bytes differ from the pin')
    return parse_record(raw, label)


def matches(value, expected, label):
    require(isinstance(value, dict) and all(key in value and value[key] == item for key, item in expected.items()),
            f'{label} differs from the exact review scope')


def current_artifact(results, reviewed, check_id, fixture):
    check = results.get(check_id, {})
    proof = check.get('evidence', {})
    require(check_id in reviewed and check.get('required') and check.get('state') == 'pass',
            f'Current visual evidence is missing or unreviewed: {check_id}')
    artifact = proof.get('artifact_sha256') or proof.get('visual_artifact_sha256')
    require(artifact or (fixture and proof.get('source') == 'fixture'),
            f'Current visual artifact is missing: {check_id}')
    return artifact


def verify_views(stage, extra, views, results, reviewed, fixture, orthographic_reference=False):
    required = set(named(extra, 'required additional view'))
    if stage in GEOMETRY_STAGES or orthographic_reference:
        required |= ORTHOGRAPHIC_ROLES
    require(required <= VIEW_ROLES and isinstance(views, dict) and required <= views.keys() <= VIEW_ROLES,
            'Required stage views are missing')
    native_images = []
    for role, check_id in views.items():
        artifact = current_artifact(results, reviewed, check_id, fixture)
        proof = results[check_id]['evidence']
        require(role in proof.get('view_roles', []), f'Current proof does not identify the {role} view')
        if stage in {'G3', 'G4'}:
            require(results[check_id]['producer'] == 'blender' and (fixture or proof.get('native')),
                    f'The {role} view requires a native Blender capture')
            if not fixture:
                native_images.append(artifact)
    require(len(native_images) == len(set(native_images)), 'Blender stage views must show distinct native images')
    return sorted(views)


def orthographic_symmetry(receipt):
    symmetry = receipt.get('symmetry')
    require(isinstance(symmetry, dict) and symmetry.keys() == ORTHOGRAPHIC_SYMMETRY_ROLES.keys(),
            'Orthographic reference review requires front-back and left-right symmetry classification')
    classifications = {}
    for plane, finding in symmetry.items():
        require(isinstance(finding, dict) and finding.keys() == {'classification', 'notes'} and
                finding['classification'] in ('symmetric', 'asymmetric') and
                isinstance(finding['notes'], str) and finding['notes'].strip(),
                f'Orthographic {plane} symmetry needs a classification and observation')
        classifications[plane] = finding['classification']
    return classifications


def verify_orthographic_reference(root, receipt_pin, candidate, scope_digest, results, review, views, preview,
                                  fixture, g1_pin=None):
    receipt = record(root, receipt_pin, 'orthographic reference review')
    stage = candidate['stage']
    source = orthographic_input(stage)
    require(candidate['components'].get(source) == receipt_pin['sha256'] and
            source in candidate.get('stage_inputs', {}).get(stage, []),
            'The stage fingerprint must bind the exact orthographic review receipt')
    matches(receipt, {'schema': 1, 'asset_id': candidate['asset_id'], 'asset_revision': candidate['revision'],
                     'stage': candidate['stage'], 'scope_digest': scope_digest, 'reviewer': review['reviewer'],
                     'result': 'pass'}, 'Orthographic reference review')
    named([receipt.get('pose_or_state_id')], 'neutral pose or state')
    axes = receipt.get('subject_frame')
    scale = receipt.get('pixels_per_unit')
    require(isinstance(axes, str) and axes.strip() and type(scale) in {int, float} and isfinite(scale) and scale > 0,
            'Orthographic reference review needs one subject frame and positive shared scale')
    observations = receipt.get('observations')
    require(isinstance(observations, dict) and set(observations) == {'pose', 'proportions', 'orientation'} and
            all(isinstance(value, str) and value.strip() for value in observations.values()),
            'Orthographic reference review requires pose, proportion and orientation observations')
    symmetry = orthographic_symmetry(receipt)
    roles = ORTHOGRAPHIC_ROLES | {ORTHOGRAPHIC_SYMMETRY_ROLES[plane] for plane, classification in symmetry.items()
                                  if classification == 'asymmetric'}
    if stage == 'G2':
        g1 = record(root, g1_pin, 'G1 orthographic predecessor')
        g1_input = orthographic_input('G1')
        stage_inputs = candidate.get('stage_inputs', {})
        require(candidate['dependencies'].get(g1_input) == g1_pin['sha256'] and
                all(g1_input in stage_inputs.get(stage, []) for stage in ORTHOGRAPHIC_STAGES),
                'G2 must bind the exact G1 orthographic predecessor in both stage fingerprints')
        matches(g1, {'schema': 1, 'asset_id': candidate['asset_id'], 'stage': 'G1', 'scope_digest': scope_digest,
                     'pose_or_state_id': receipt['pose_or_state_id'], 'result': 'pass'},
                'G1 orthographic predecessor')
        require(orthographic_symmetry(g1) == symmetry,
                'G2 orthographic symmetry differs from the accepted G1 design')
    panels = receipt.get('views')
    require(isinstance(panels, dict) and ORTHOGRAPHIC_ROLES <= panels.keys() <=
            (ORTHOGRAPHIC_ROLES | set(ORTHOGRAPHIC_SYMMETRY_ROLES.values())),
            'Orthographic reference review requires front, side and top panels')
    require(roles <= panels.keys() and panels.keys() <= views.keys(),
            'Orthographic reference review requires primary views for asymmetric planes: ' +
            ', '.join(sorted((roles - panels.keys()) | (panels.keys() - views.keys()))))
    crops = {}
    for role in sorted(panels):
        panel = panels[role]
        require(isinstance(panel, dict) and {'check_id', 'evidence_digest', 'artifact', 'projection'} <= panel.keys() <=
                {'check_id', 'evidence_digest', 'artifact', 'projection', 'bbox'}, 'Invalid orthographic reference panel')
        check_id = views[role]
        check = results[check_id]
        matches(panel, {'check_id': check_id, 'evidence_digest': check['evidence_digest'],
                        'projection': 'orthographic'}, f'Orthographic {role} panel')
        require(check['kind'] == 'visual-sheet' and check_id in preview['checks'],
                'The approval preview must include every primary orthographic view')
        artifact = panel['artifact']
        path = pin(root, artifact, f'orthographic {role} panel')
        evidence = check['evidence']
        require(path.suffix.casefold() in {'.png', '.svg'} and
                (evidence.get('visual_artifact_sha256') == artifact['sha256'] or
                 (fixture and evidence.get('source') == 'fixture')),
                f'Orthographic {role} panel differs from the reviewed sheet')
        box = panel.get('bbox')
        if path.suffix.casefold() == '.png':
            width, height = png_dimensions(path)
            box = box if 'bbox' in panel else [0, 0, width, height]
            require(isinstance(box, list) and len(box) == 4 and all(type(value) is int for value in box),
                    f'Orthographic {role} panel needs four crop coordinates')
            x, y, w, h = box
            require(x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= width and y + h <= height,
                    f'Orthographic {role} panel exceeds the source image')
        else:
            require('bbox' not in panel, 'A shared orthographic sheet with crops requires PNG evidence')
        known = crops.setdefault(artifact['sha256'], [])
        require(all(separate_crops(box, previous) for previous in known),
                'Orthographic views reuse or overlap the same source panel')
        known.append(box)
    return {'receipt_sha256': receipt_pin['sha256'], 'pose_or_state_id': receipt['pose_or_state_id'],
            'primary_views': sorted(roles), **({'g1_receipt_sha256': g1_pin['sha256']} if stage == 'G2' else {})}


def separate_crops(first, second):
    if first is None or second is None:
        return False
    x, y, w, h = first
    a, b, c, d = second
    return x + w <= a or a + c <= x or y + h <= b or b + d <= y


def verify_comparison(root, change, proof, candidate, scope_digest, results, review, reviewed, fixture):
    require(isinstance(change, dict), 'A visual change scope is required')
    if change.get('kind') == 'initial':
        require(set(change) == {'kind'} and proof is None, 'An initial review cannot carry a revision comparison')
        return {'kind': 'initial'}
    require(change.get('kind') == 'revision' and set(change) == {'kind', 'baseline', 'editable', 'protected'},
            'A scoped revision requires an exact baseline and protected features')
    editable = set(named(change['editable'], 'editable feature'))
    protected = set(named(change['protected'], 'protected feature'))
    require(editable and protected and editable.isdisjoint(protected), 'Editable and protected features must be distinct')
    identity = {'asset_id': candidate['asset_id'], 'stage': candidate['stage'], 'scope_digest': scope_digest}
    baseline = record(root, change['baseline'], 'protected revision baseline')
    matches(baseline, identity, 'Protected baseline')
    require(baseline.get('origin') in {'accepted', 'owner-named'} and
            isinstance(baseline.get('asset_revision'), str) and baseline['asset_revision'] != candidate['revision'],
            'Protected baseline must identify a different accepted or owner-named revision')
    if baseline['origin'] == 'accepted':
        require(isinstance(baseline.get('packet_digest'), str) and re.fullmatch(r'[0-9a-f]{64}', baseline['packet_digest']),
                'An accepted baseline requires its exact packet digest')
    comparison = record(root, proof, 'protected revision comparison')
    matches(comparison, {**identity, 'asset_revision': candidate['revision'],
                         'baseline_sha256': change['baseline']['sha256'], 'reviewer': review.get('reviewer')}, 'Protected comparison')
    current = comparison.get('reviewed_evidence')
    require(isinstance(current, dict) and current and all(key in reviewed and results[key]['state'] == 'pass' and
            value == results[key]['evidence_digest'] for key, value in current.items()),
            'The protected comparison must bind currently reviewed evidence')
    changed = set(named(comparison.get('changed'), 'observed changed feature'))
    before, after = baseline.get('protected'), comparison.get('protected')
    require(changed and changed <= editable and isinstance(before, dict) and isinstance(after, dict) and
            set(before) == set(after) == protected, 'The observed change or protected feature set differs from the scope')
    for feature, expected in before.items():
        observed = after[feature]
        require(isinstance(expected, dict) and isinstance(observed, dict), f'Invalid protected feature: {feature}')
        if 'view' in expected:
            pin(root, expected['view'], f'baseline view for {feature}')
            artifact = current_artifact(results, reviewed, observed.get('check_id'), fixture)
            require(observed.get('result') == 'unchanged' and observed.get('baseline_view_sha256') == expected['view']['sha256'] and
                    observed.get('check_id') in current and (fixture or artifact == observed.get('current_view_sha256')),
                    f'Protected appearance changed: {feature}')
        elif 'tolerance' in expected:
            tolerance, old, new = expected['tolerance'], expected.get('value'), observed.get('value')
            require(all(type(value) in {int, float} and isfinite(value) for value in (tolerance, old, new)) and
                    tolerance >= 0 and isinstance(expected.get('unit'), str) and expected['unit'] and
                    observed.get('unit') == expected['unit'] and abs(new-old) <= tolerance,
                    f'Protected measurement changed: {feature}')
        else:
            require(set(expected) == set(observed) == {'value'} and expected['value'] == observed['value'] and
                    type(expected['value']) is type(observed['value']), f'Protected value changed: {feature}')
    return {'kind': 'revision', 'baseline_sha256': change['baseline']['sha256'], 'comparison_sha256': proof['sha256'],
            'baseline_origin': baseline['origin'], 'baseline_revision': baseline['asset_revision'],
            'baseline_packet_digest': baseline.get('packet_digest')}


def capture_index(root, source, env, target):
    path = pinned_path(root, source, 'native scene capture index')
    native = record(root, source, 'native scene capture index')
    matches(native, {'status': 'captured', 'scene_path': env['scene_path'], 'scene_sha256': env['scene_sha256'], 'target': target},
            'Native scene capture index')
    profile = env.get('capture_profile', {})
    fields = {'quality': 'profile', 'pipeline': 'pipeline', 'graphics_api': 'graphics_api',
              'color_space': 'color_space', 'width': 'width', 'height': 'height'}
    require(set(profile) == set(fields) and isinstance(target.get('editor_version'), str) and target['editor_version'],
            'Whole-scene QA requires a pinned Editor and complete capture profile')
    matches(native, {'editor': target['editor_version'], **{name: profile[key] for key, name in fields.items()}},
            'Native scene capture profile')
    frames = native.get('frames')
    require(isinstance(frames, list) and all(isinstance(frame, dict) for frame in frames), 'Native capture frames are missing')
    names = named([frame.get('name') for frame in frames], 'native frame')
    require(names, 'Native capture frames are missing')
    return path, native, dict(zip(names, frames, strict=True))


def named_coverage(value, required, label):
    names = set(named(list(required) if isinstance(required, dict) else required, label))
    require(isinstance(value, dict) and set(value) == names, f'Incomplete scene {label} coverage')
    return value


def vector(value):
    return isinstance(value, list) and len(value) == 3 and all(type(item) in {int, float} and isfinite(item) for item in value)


def direction(value):
    return vector(value) and isclose(sum(item*item for item in value), 1.0, abs_tol=.01)


def dot(left, right):
    return sum(a*b for a,b in zip(left, right, strict=True))


def offset(point, origin):
    return [a-b for a,b in zip(point, origin, strict=True)]


def verify_assembled_scene(root, env, plan, qa_pin, target, scope_digest, fixture):
    require(isinstance(plan, dict) and set(plan) == {'kind', 'areas', 'openings', 'joins', 'fixtures'} and
            plan['areas'] and plan['joins'] and all(isinstance(plan[key], dict) for key in ('openings', 'joins', 'fixtures')),
            'Incomplete assembled scene QA plan')
    qa = record(root, qa_pin, 'whole-scene QA receipt')
    matches(qa, {'environment_id': env['id'], 'environment_revision': env['revision'],
                 'scene_sha256': env['scene_sha256'], 'scope_digest': scope_digest,
                 'origin': 'fixture' if fixture else 'native', 'result': 'pass'}, 'Whole-scene QA receipt')
    require(isinstance(qa.get('reviewer'), str) and qa['reviewer'].strip() and isinstance(qa.get('findings'), list) and
            all(isinstance(row, dict) and row.get('status') == 'cleared' for row in qa['findings']),
            'Whole-scene QA has unresolved visible findings or no reviewer')
    capture_path, native, frames = capture_index(root, qa['capture_index'], env, target)
    used = set()

    def frame(name):
        require(isinstance(name, str) and name in frames, f'Missing native scene view: {name}')
        used.add(name)
        return frames[name]

    area_views = named_coverage(qa.get('areas'), plan['areas'], 'area')
    for name in named(list(area_views.values()), 'area view'):
        frame(name)
    for opening, route in named_coverage(qa.get('openings'), plan['openings'], 'opening').items():
        crossing = plan['openings'][opening]
        require(isinstance(crossing, dict) and set(crossing) == {'center', 'normal', 'radius_m'} and
                vector(crossing['center']) and direction(crossing['normal']) and type(crossing['radius_m']) in {int,float} and
                isfinite(crossing['radius_m']) and crossing['radius_m'] > 0, 'Invalid traversal crossing geometry')
        require(isinstance(route, dict) and set(route) == {'forward', 'reverse'}, 'Both traversal directions are required')
        names = []
        for approach, sign in (('forward',1),('reverse',-1)):
            ordered = route[approach]
            samples = [frame(name) for name in named(ordered, 'traversal frame')]
            require(len(samples) == 3 and all(vector(sample.get('camera_position')) and direction(sample.get('camera_forward'))
                    for sample in samples), 'Traversal needs ordered before, through and after poses')
            offsets = [offset(sample['camera_position'], crossing['center']) for sample in samples]
            center = offsets[1]
            before, through, after = (dot(position, crossing['normal']) * sign for position in offsets)
            require(before < 0 < after and before < through < after and
                    dot(center, center) <= crossing['radius_m']**2 and
                    dot(samples[1]['camera_forward'],crossing['normal'])*sign > .15,
                    'Traversal samples do not cross the planned opening in the recorded direction')
            names.extend(ordered)
        require(len(set(names)) == len(names), 'Traversal evidence must show independent opposite approaches')
    for identity, join in named_coverage(qa.get('joins'), plan['joins'], 'join').items():
        require(isinstance(join, dict) and set(join) in ({'grazing'}, {'grazing', 'shadow_control'}), 'A grazing join view is required')
        grazing = frame(join['grazing'])
        expected = plan['joins'][identity]
        require(isinstance(expected, dict) and set(expected) == {'normal', 'shadow_control_required'} and
                type(expected['shadow_control_required']) is bool and
                (not expected['shadow_control_required'] or 'shadow_control' in join),
                'The planned join needs its shadow control')
        normal = expected['normal']
        require(direction(normal) and direction(grazing.get('camera_forward')) and abs(dot(normal, grazing['camera_forward'])) <= .6,
                'Native join view does not show the planned grazing angle')
        if 'shadow_control' in join:
            control = frame(join['shadow_control'])
            require(grazing.get('shadows') is True and control.get('shadows') is False and
                    all(field in grazing and grazing[field] == control.get(field) for field in
                        ('camera_position', 'camera_forward', 'field_of_view')), 'Join shadow control is not a matched native view')
    light_records = named_coverage(qa.get('fixtures'), list(plan['fixtures']), 'fixture')
    local_lights = named_coverage(native.get('local_lights'), list(plan['fixtures']), 'native local light')
    for identity, spec in plan['fixtures'].items():
        require(isinstance(spec, dict) and set(spec) == {'emitter_path', 'light_path', 'receiver'} and
                all(isinstance(value, str) and value.strip() for value in spec.values()), 'Incomplete source lighting plan')
        observed = light_records[identity]
        matches(observed, spec, 'Fixture lighting')
        matches(local_lights[identity], {key: spec[key] for key in ('emitter_path', 'light_path')}, 'Native light inventory')
        on, off = frame(observed['on']), frame(observed['off'])
        matches(on, {'light_path': spec['light_path'], 'light_enabled': True}, 'Fixture-on view')
        matches(off, {'light_path': spec['light_path'], 'light_enabled': False}, 'Fixture-off view')
        require(on['image_sha256'] != off['image_sha256'] and all(field in on and on[field] == off.get(field) for field in
                ('camera_position', 'camera_forward', 'field_of_view')) and type(observed.get('receiver_pixels')) is int and
                observed['receiver_pixels'] > 0 and on.get('receiver') == spec['receiver'] and
                on.get('receiver_pixels') == observed['receiver_pixels'],
                'Fixture illumination lacks a matched receiving-surface control')
    prefix = PurePosixPath(capture_path.relative_to(root).as_posix()).parent
    expected_size = (env['capture_profile']['width'], env['capture_profile']['height'])
    for name in used:
        path = pin(root, {'path': (prefix / (name+'.png')).as_posix(), 'sha256': frames[name]['image_sha256']}, 'native scene view')
        require(png_dimensions(path) == expected_size, 'Native scene view size differs from the capture profile')
    return {'scene_sha256': env['scene_sha256'], 'receipt_sha256': qa_pin['sha256'],
            'native_index_sha256': qa['capture_index']['sha256'], 'views_verified': len(used)}


def verify_scenes(root, stage, plan, proofs, environments, candidate, scope_digest, fixture):
    require(isinstance(plan, dict) and isinstance(proofs, dict), 'Scene QA plan and evidence must be objects')
    if stage != 'G5':
        require(not plan and not proofs, 'Whole-scene QA belongs to Unity look review')
        return {}
    require(set(plan) == set(environments), 'Every assigned look environment needs an explicit QA scope')
    assembled = {}
    for identity, env in environments.items():
        spec = plan[identity]
        kind = spec.get('kind') if isinstance(spec, dict) else None
        if kind == 'assembled':
            require(not env['neutral'] and identity in proofs, 'The current assembled look requires whole-scene QA')
            assembled[identity] = verify_assembled_scene(root, env, spec, proofs[identity], candidate['target'], scope_digest, fixture)
        else:
            require(kind == ('neutral' if env['neutral'] else 'existing') and set(spec) == {'kind'},
                    'Scene QA scope must declare an assembled, existing or neutral environment')
    require(set(proofs) == set(assembled), 'Whole-scene QA evidence differs from the assembled scene plan')
    return assembled


def verify_preview(root, preview, results, reviewed, fixture):
    require(isinstance(preview, dict) and set(preview) <= {'artifact', 'checks', 'composition'}, 'A current preview is required')
    checks = named(preview.get('checks'), 'preview check')
    require(checks, 'A preview must name current reviewed checks')
    artifacts = {key: current_artifact(results, reviewed, key, fixture) for key in checks}
    artifact = preview['artifact']
    path = pin(root, artifact, 'current review preview')
    require(path.suffix.casefold() in {'.png', '.svg', '.gif'}, 'Unsupported review preview format')
    if path.suffix.casefold() == '.png':
        png_dimensions(path)
    if 'composition' in preview:
        composition = record(root, preview['composition'], 'preview composition')
        matches(composition, {'artifact_sha256': artifact['sha256'], 'source_artifacts': artifacts}, 'Preview composition')
    else:
        require(len(checks) == 1 and (fixture or next(iter(artifacts.values())) == artifact['sha256']),
                'The direct preview differs from its reviewed artifact')
    return artifact


def evaluate(root, policy, mode, candidate, scope_digest, results, review, environments, fixture, digest):
    orthographic_reference = (candidate.get('reference_workflow') == ORTHOGRAPHIC_REFERENCE and
                              candidate['stage'] in ORTHOGRAPHIC_STAGES)
    if policy is None and fixture and not orthographic_reference:
        return None
    if mode != 'final':
        return {'state': 'deferred'}
    try:
        require(isinstance(policy, dict) and set(policy) == {'version', 'scope', 'evidence'} and
                type(policy['version']) is int and policy['version'] == 1, 'Current visual review policy is required')
        scope, proof = policy['scope'], policy['evidence']
        required_proof = {'comparison', 'views', 'scenes', 'preview'}
        if orthographic_reference:
            required_proof.add('orthographic_reference')
            if candidate['stage'] == 'G2':
                required_proof.add('orthographic_g1')
        require(isinstance(scope, dict) and set(scope) == {'change', 'extra_views', 'scenes'} and isinstance(proof, dict) and
                set(proof) == required_proof, 'Visual review scope or evidence is incomplete')
        reviewed = review.get('reviewed_checks', []) if review['state'] == 'reviewed' else []
        views = verify_views(candidate['stage'], scope['extra_views'], proof['views'], results, reviewed, fixture,
                             orthographic_reference)
        comparison = verify_comparison(root, scope['change'], proof['comparison'], candidate, scope_digest, results, review, reviewed, fixture)
        scenes = verify_scenes(root, candidate['stage'], scope['scenes'], proof['scenes'], environments, candidate, scope_digest, fixture)
        preview = verify_preview(root, proof['preview'], results, reviewed, fixture)
        extra = {}
        if orthographic_reference:
            preview_roles = {role for check_id in proof['preview']['checks']
                             for role in results[check_id]['evidence'].get('view_roles', [])}
            require(not PERSPECTIVE_ROLES.intersection((*views, *preview_roles)),
                    'Perspective views belong to review after the orthographic reference handoff')
            extra['orthographic_reference'] = verify_orthographic_reference(
                root, proof['orthographic_reference'], candidate, scope_digest, results, review, proof['views'],
                proof['preview'], fixture, proof.get('orthographic_g1'))
        return {'state': 'verified', 'scope_sha256': digest(scope), 'views': views, 'comparison': comparison,
                'scenes': scenes, 'preview': preview, **extra}
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
        return {'state': 'blocked', 'reason': str(error)}


def presentation_matches(host, decision, packet):
    policy = packet['visual_policy']
    observed = host.get('presentation')
    if not isinstance(observed, dict) or observed.get('method') not in {'inline', 'posted-link'}:
        return False
    expected = {'packet_digest': packet['packet_digest'], 'scope_sha256': policy['scope_sha256'],
                'preview': policy['preview']}
    if any(observed.get(key) != value for key, value in expected.items()):
        return False
    if observed['method'] == 'posted-link' and observed.get('link_target') != policy['preview']['path']:
        return False
    if not all(isinstance(observed.get(key), str) and observed[key].strip() for key in
               ('conversation', 'presentation_event', 'prompt_event')):
        return False
    before, after = observed.get('presentation_sequence'), observed.get('prompt_sequence')
    return (baseline_matches(host, packet) and type(before) is int and type(after) is int and 0 < before < after and
            observed['presentation_event'] != observed['prompt_event'] and
            decision.get('prompt_event') == observed['prompt_event'] and decision.get('conversation') == observed['conversation'])


def baseline_matches(host, packet):
    comparison = packet['visual_policy']['comparison']
    if comparison['kind'] == 'initial':
        return True
    if comparison['baseline_origin'] == 'owner-named':
        baseline = host.get('named_visual_baseline')
        return (isinstance(baseline, dict) and baseline.get('sha256') == comparison['baseline_sha256'] and
                isinstance(baseline.get('owner_reference'), str) and bool(baseline['owner_reference'].strip()))
    expected = {'status':'accepted', 'asset_id':packet['asset_id'], 'revision':comparison['baseline_revision'],
                'stage':packet['stage'], 'scope_digest':packet['scope_digest'], 'packet_digest':comparison['baseline_packet_digest']}
    history = host.get('previous', [])
    return isinstance(history, list) and sum(isinstance(row,dict) and all(row.get(key)==value for key,value in expected.items())
                                             for row in history) == 1
