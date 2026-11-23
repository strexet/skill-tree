"""Check Director's local Git view inside a desktop host."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'common/scripts/run-workspaces.py'
spec = importlib.util.spec_from_file_location('workspaces', path)
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


class HostGit(unittest.TestCase):
    def test_local_git_uses_project_and_ignores_host_presentation_and_remote_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_CONFIG_')}
            env.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='color.ui', GIT_CONFIG_VALUE_0='never',
                       GIT_CONFIG_KEY_1='credential.https://example.invalid/.useHttpPath', GIT_CONFIG_VALUE_1='true')
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(ws.local_git_text(root, 'rev-parse', '--show-toplevel'), str(root))
                self.assertEqual(ws.local_git(root, 'config', '--get', 'credential.https://example.invalid/.useHttpPath',
                                             accepted=(1,)).returncode, 1)
                self.assertEqual(os.environ['GIT_CONFIG_COUNT'], '2')

    def test_null_devices_stay_in_the_environment_of_the_local_git_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            with patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull}), \
                    patch.object(subprocess, 'run', wraps=subprocess.run) as runner:
                self.assertEqual(ws.local_git_text(root, 'rev-parse', '--show-toplevel'), str(root))
                child = runner.call_args.kwargs['env']
                self.assertEqual(child['GIT_CONFIG_GLOBAL'], os.devnull)
                self.assertEqual(child['GIT_CONFIG_SYSTEM'], os.devnull)

    def test_rejects_repository_index_execution_and_malformed_overrides(self):
        for values, message in [
            ({'GIT_CONFIG_GLOBAL': 'another.gitconfig'}, 'GIT_CONFIG_GLOBAL'),
            ({'GIT_CONFIG_SYSTEM': os.devnull + '.config'}, 'GIT_CONFIG_SYSTEM'),
            ({'GIT_CONFIG': os.devnull}, 'GIT_CONFIG'),
            ({'GIT_DIR': 'other'}, 'GIT_DIR'), ({'GIT_INDEX_FILE': 'other'}, 'GIT_INDEX_FILE'),
            ({'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath', 'GIT_CONFIG_VALUE_0': 'unused'}, 'index 0'),
            ({'GIT_CONFIG_COUNT': '1'}, 'index 0'), ({'GIT_CONFIG_COUNT': '-1'}, 'count'),
            ({'GIT_CONFIG_KEY_2': 'color.ui'}, 'outside'),
        ]:
            with self.subTest(values=values), patch.dict(os.environ, values, clear=True):
                with self.assertRaisesRegex(ws.RunError, message):
                    ws.local_git_environment()


if __name__ == '__main__':
    unittest.main()
