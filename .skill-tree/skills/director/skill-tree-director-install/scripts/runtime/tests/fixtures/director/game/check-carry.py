"""Run the portable cave-lantern consumer assertion on exact fixture inputs."""

import json
from pathlib import Path
import sys


def main(requirement_path, artifact_path):
    requirement = json.loads(Path(requirement_path).read_text(encoding='utf-8'))
    artifact = json.loads(Path(artifact_path).read_text(encoding='utf-8'))
    if requirement['requirement_id'] != artifact['requirement_id']:
        print('requirement identity mismatch', file=sys.stderr)
        return 1
    expected = requirement['attachment']
    observed = artifact['attachment']
    if expected != observed:
        print(f'attachment mismatch: expected {expected}, found {observed}', file=sys.stderr)
        return 1
    print(json.dumps({
        'requirement_id': requirement['requirement_id'],
        'requirement_revision': requirement['revision'],
        'artifact_id': artifact['id'],
        'artifact_revision': artifact['revision'],
        'attachment': observed,
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
