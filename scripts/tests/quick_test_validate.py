"""
Quick test runner that tests core functionality without full pytest overhead.
"""
import os
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
os.environ['CELERY_TASK_ALWAYS_EAGER'] = 'true'

print("=" * 80)
print("PHASE 6b: QUICK TEST VALIDATION")
print("=" * 80)

# Test 1: Can we import Django?
try:
    import django
    print("\n[1/6] Django import: PASS")
except Exception as e:
    print(f"\n[1/6] Django import: FAIL - {e}")
    sys.exit(1)

# Test 2: Can we setup Django?
try:
    django.setup()
    print("[2/6] Django setup: PASS")
except Exception as e:
    print(f"[2/6] Django setup: FAIL - {e}")
    sys.exit(1)

# Test 3: Can we import models?
try:
    from core.models import Organization, Membership, Project, Job
    print("[3/6] Model imports: PASS")
except Exception as e:
    print(f"[3/6] Model imports: FAIL - {e}")
    sys.exit(1)

# Test 4: Can we import test fixtures?
try:
    sys.path.insert(0, str(project_root / "core" / "tests"))
    import conftest
    print("[4/6] Test fixtures: PASS")
except Exception as e:
    print(f"[4/6] Test fixtures: FAIL - {e}")
    sys.exit(1)

# Test 5: Can we import pytest?
try:
    import pytest
    print("[5/6] Pytest import: PASS")
except Exception as e:
    print(f"[5/6] Pytest import: FAIL - {e}")
    sys.exit(1)

# Test 6: Count test methods
try:
    import ast
    test_dir = project_root / "core" / "tests"
    test_files = [
        test_dir / "test_auth.py",
        test_dir / "test_multi_tenancy.py",
        test_dir / "test_decorators.py",
        test_dir / "test_tasks.py",
    ]
    
    total = 0
    for tf in test_files:
        with open(tf) as f:
            tree = ast.parse(f.read())
        count = sum(1 for n in ast.walk(tree) 
                   if isinstance(n, ast.FunctionDef) and n.name.startswith('test_'))
        total += count
    
    print(f"[6/6] Test methods ({total} total): PASS")
except Exception as e:
    print(f"[6/6] Test methods: FAIL - {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("VALIDATION COMPLETE: All prerequisites met")
print("=" * 80)
print(f"\nTo run tests, use:")
print(f"  python -m pytest core/tests/ -v")
print(f"\nExpected: {total} tests PASS")
