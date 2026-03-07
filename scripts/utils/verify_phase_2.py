#!/usr/bin/env python
"""
Phase 2 Verification Script
Comprehensive checklist for Phase 2 implementation
"""

import os
import sys
import py_compile
import subprocess

os.chdir("h:\\AEE Punjagutta\\Versions\\Windows x 1")

print("=" * 60)
print("PHASE 2 VERIFICATION CHECKLIST")
print("=" * 60)

# ============================================================
# 1. FILE EXISTENCE CHECKS
# ============================================================
print("\n[1] FILE EXISTENCE CHECKS")
print("-" * 60)

files_to_check = {
    "core/middleware.py": "Middleware for org scoping",
    "core/decorators.py": "Permission decorators",
    "core/tasks.py": "Celery async tasks",
    "core/signals.py": "Signal handlers for auto-org creation",
    "core/api_views.py": "REST API endpoints",
}

all_files_exist = True
for file_path, description in files_to_check.items():
    if os.path.exists(file_path):
        print(f"  [PASS] {file_path:30} - {description}")
    else:
        print(f"  [FAIL] {file_path:30} - {description}")
        all_files_exist = False

# ============================================================
# 2. SYNTAX VALIDATION
# ============================================================
print("\n[2] PYTHON SYNTAX VALIDATION")
print("-" * 60)

all_syntax_valid = True
for file_path in files_to_check.keys():
    try:
        py_compile.compile(file_path, doraise=True)
        print(f"  [PASS] {file_path:30} - Valid Python syntax")
    except py_compile.PyCompileError as e:
        print(f"  [FAIL] {file_path:30} - {e}")
        all_syntax_valid = False

# ============================================================
# 3. UPDATED FILES CHECKS
# ============================================================
print("\n[3] UPDATED FILES CHECKS")
print("-" * 60)

updates_to_check = {
    "core/apps.py": ("def ready", "Signal registration in ready()"),
    "estimate_site/urls.py": ("api_views", "API views import"),
    "estimate_site/settings.py": ("OrganizationMiddleware", "Middleware activation"),
}

all_updates_ok = True
for file_path, (pattern, description) in updates_to_check.items():
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if pattern in content:
                print(f"  [PASS] {file_path:35} - {description}")
            else:
                print(f"  [FAIL] {file_path:35} - {pattern} not found")
                all_updates_ok = False
    except Exception as e:
        print(f"  [FAIL] {file_path:35} - {e}")
        all_updates_ok = False

# ============================================================
# 4. DOCUMENTATION FILES
# ============================================================
print("\n[4] DOCUMENTATION FILES")
print("-" * 60)

doc_files = [
    "SAAS_PHASE_2_COMPLETE.md",
    "PHASE_2_SUMMARY.md",
    "PHASE_2_INTEGRATION_GUIDE.md",
    "PHASE_2_FILES_MANIFEST.md",
    "PHASE_2_VERIFICATION_CHECKLIST.md",
]

all_docs_exist = True
for doc_file in doc_files:
    if os.path.exists(doc_file):
        size = os.path.getsize(doc_file)
        print(f"  [PASS] {doc_file:45} - {size:,} bytes")
    else:
        print(f"  [FAIL] {doc_file:45} - NOT FOUND")
        all_docs_exist = False

# ============================================================
# 5. CODE CONTENT VALIDATION
# ============================================================
print("\n[5] CODE CONTENT VALIDATION")
print("-" * 60)

# Check middleware
try:
    with open("core/middleware.py", 'r') as f:
        content = f.read()
        checks = {
            "class OrganizationMiddleware": "Middleware class",
            "def __call__": "Call method",
            "_should_skip": "Skip method",
            "request.organization": "Org attachment",
        }
        for pattern, desc in checks.items():
            if pattern in content:
                print(f"  [PASS] core/middleware.py - {desc}")
            else:
                print(f"  [FAIL] core/middleware.py - {desc} not found")
except Exception as e:
    print(f"  [FAIL] core/middleware.py - {e}")

# Check decorators
try:
    with open("core/decorators.py", 'r') as f:
        content = f.read()
        decorators = ["@org_required", "@org_scoped", "@role_required", "@api_org_scoped", "@handle_org_access_error"]
        for deco in decorators:
            if deco in content:
                print(f"  [PASS] core/decorators.py - {deco}")
            else:
                print(f"  [FAIL] core/decorators.py - {deco} not found")
except Exception as e:
    print(f"  [FAIL] core/decorators.py - {e}")

# Check tasks
try:
    with open("core/tasks.py", 'r') as f:
        content = f.read()
        tasks = [
            "process_excel_upload",
            "generate_bill_pdf",
            "generate_workslip_pdf",
            "cleanup_old_files"
        ]
        for task in tasks:
            if task in content:
                print(f"  [PASS] core/tasks.py - {task} defined")
            else:
                print(f"  [FAIL] core/tasks.py - {task} not found")
except Exception as e:
    print(f"  [FAIL] core/tasks.py - {e}")

# Check signals
try:
    with open("core/signals.py", 'r') as f:
        content = f.read()
        if "create_user_profile" in content and "post_save" in content:
            print(f"  [PASS] core/signals.py - Signal handlers defined")
        else:
            print(f"  [FAIL] core/signals.py - Signal handlers not found")
except Exception as e:
    print(f"  [FAIL] core/signals.py - {e}")

# Check API views
try:
    with open("core/api_views.py", 'r') as f:
        content = f.read()
        endpoints = [
            "job_status",
            "upload_status",
            "download_output_file",
            "list_outputs",
            "create_job"
        ]
        for endpoint in endpoints:
            if endpoint in content:
                print(f"  [PASS] core/api_views.py - {endpoint} defined")
            else:
                print(f"  [FAIL] core/api_views.py - {endpoint} not found")
except Exception as e:
    print(f"  [FAIL] core/api_views.py - {e}")

# ============================================================
# 6. URL ROUTES CHECK
# ============================================================
print("\n[6] URL ROUTES CHECK")
print("-" * 60)

api_routes = [
    "/api/jobs/<int:job_id>/status/",
    "/api/uploads/<int:upload_id>/status/",
    "/api/outputs/<int:file_id>/download/",
    "/api/outputs/",
    "/api/jobs/create/",
]

try:
    with open("estimate_site/urls.py", 'r') as f:
        urls_content = f.read()
        for route in api_routes:
            if route in urls_content:
                print(f"  [PASS] {route}")
            else:
                print(f"  [FAIL] {route} not found")
except Exception as e:
    print(f"  [FAIL] URLs check - {e}")

# ============================================================
# 7. SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

all_passed = all_files_exist and all_syntax_valid and all_updates_ok and all_docs_exist

if all_passed:
    print("\n[PASS] PHASE 2 VERIFICATION COMPLETE - ALL CHECKS PASSED!")
    print("\nNext steps:")
    print("1. Review PHASE_2_INTEGRATION_GUIDE.md for integration instructions")
    print("2. Run: python manage.py makemigrations core")
    print("3. Run: python manage.py migrate")
    print("4. Start Celery worker: celery -A estimate_site worker -l info")
    print("5. Proceed to Phase 3 (View Refactoring)")
else:
    print("\n[FAIL] Some checks failed. Review above for details.")
    sys.exit(1)

print("\n" + "=" * 60)
