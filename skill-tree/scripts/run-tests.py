#!/usr/bin/env python3
"""Run kebab-case Python behavioral tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

def main():
    suite=unittest.TestSuite();root=Path(__file__).resolve().parents[1]
    for path in sorted((root/'tests').glob('test-*.py')):
        spec=importlib.util.spec_from_file_location(path.stem.replace('-','_'),path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    return int(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
if __name__=='__main__':raise SystemExit(main())
