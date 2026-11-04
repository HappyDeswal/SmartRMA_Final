#!/usr/bin/env python3
"""Run isolated feature/security regression tests without touching saved cases."""
import os
import sys
from pathlib import Path
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if __name__ == '__main__':
    tests_dir = str(Path(__file__).resolve().parent)
    suite = unittest.defaultTestLoader.discover(tests_dir, pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
