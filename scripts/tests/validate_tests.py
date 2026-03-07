#!/usr/bin/env python
"""Quick validation that all code is syntactically correct."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

output = []
output.append(f"Python Version: {sys.version}\n\n")

# Try importing all test files for syntax errors
test_dir = Path(__file__).parent / "core" / "tests"
test_files = [
    test_dir / "conftest.py",
    test_dir / "test_auth.py",
    test_dir / "test_multi_tenancy.py",
    test_dir / "test_decorators.py",
    test_dir / "test_tasks.py",
]

import py_compile

output.append("="*70 + "\n")
output.append("SYNTAX VALIDATION OF TEST FILES\n")
output.append("="*70 + "\n\n")

all_valid = True
for test_file in test_files:
    try:
        py_compile.compile(str(test_file), doraise=True)
        output.append(f"✓ {test_file.name:30} - Valid syntax\n")
    except py_compile.PyCompileError as e:
        output.append(f"❌ {test_file.name:30} - {e}\n")
        all_valid = False

output.append("\n" + "="*70 + "\n")

if all_valid:
    output.append("✅ All test files have valid Python syntax\n\n")
    
    # Count total tests
    import ast
    
    total_tests = 0
    for test_file in test_files[1:]:  # Skip conftest
        with open(test_file) as f:
            tree = ast.parse(f.read())
            
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                total_tests += 1
    
    output.append(f"Total test methods defined: {total_tests}\n")
    output.append("\n✅ TEST SUITE READY FOR EXECUTION\n")
    output.append("Run with: python -m pytest core/tests/ -v\n")
else:
    output.append("❌ Some test files have syntax errors\n")

# Write to file
with open("test_validation_result.txt", "w") as f:
    f.writelines(output)

# Print to console
text = "".join(output)
print(text)
sys.exit(0 if all_valid else 1)
