#!/usr/bin/env python
"""Direct test runner to bypass pytest hanging issues."""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
os.environ['CELERY_TASK_ALWAYS_EAGER'] = 'true'

sys.path.insert(0, str(Path(__file__).parent))

print("Setting up Django...")
django.setup()
print("✓ Django setup complete\n")

# Import and run tests
from django.test.utils import get_runner
from django.conf import settings

TestRunner = get_runner(settings)
test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)

# Run all tests
print("="*70)
print("Running Test Suite")
print("="*70)

failures = test_runner.run_tests(["core.tests"])

if failures:
    print(f"\n❌ {failures} test(s) FAILED")
    sys.exit(1)
else:
    print("\n✅ All tests PASSED")
    sys.exit(0)
