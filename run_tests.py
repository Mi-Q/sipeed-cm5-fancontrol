#!/usr/bin/env python3
import unittest
import sys

loader = unittest.TestLoader()
suite = loader.discover(start_dir='tests')
runner = unittest.TextTestRunner(verbosity=2)
res = runner.run(suite)
sys.exit(0 if res.wasSuccessful() else 1)
