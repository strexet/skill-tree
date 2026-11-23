"""Verify the Git context reader's subprocess boundaries."""

import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


BACKEND = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'common/scripts/context-search.py'))


class ContextSearchTests(unittest.TestCase):
    def test_git_output_cannot_exceed_the_byte_limit(self):
        def command(root, *args):
            return [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"x" * 1000000)']

        with self.assertRaisesRegex(ValueError, 'output exceeds the byte limit'):
            BACKEND['git_output'](command, Path('.'), 'grep', max_bytes=16)

    def test_git_commands_disable_protocols_and_lazy_fetch(self):
        def command(root, *args):
            return [sys.executable, '-c',
                    'import os; print(repr(os.environ["GIT_ALLOW_PROTOCOL"]), os.environ["GIT_NO_LAZY_FETCH"])']

        self.assertEqual(BACKEND['git_output'](command, Path('.'), 'cat-file'), b"'' 1\n")

    @unittest.skipUnless(os.name == 'posix', 'Subprocess group cleanup uses POSIX signals')
    def test_deadline_closes_stdout_inherited_by_a_descendant(self):
        def command(root, *args):
            return [sys.executable, '-c',
                    'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])']

        output = BACKEND['git_output']
        start = time.monotonic()
        with patch.dict(output.__globals__, GIT_TIMEOUT=0.1):
            with self.assertRaises(subprocess.TimeoutExpired):
                output(command, Path('.'), 'grep')
        self.assertLess(time.monotonic() - start, 4)


if __name__ == '__main__':
    unittest.main()
