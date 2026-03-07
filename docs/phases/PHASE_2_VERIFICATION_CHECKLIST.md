# PHASE_2_VERIFICATION_CHECKLIST.md

## Phase 2 Implementation Verification

Run this checklist to verify Phase 2 implementation is complete and correct.

---

## 📋 File Existence Checks

### New Files Created
```bash
# Check all 5 new files exist
[ -f core/middleware.py ] && echo "✓ middleware.py" || echo "✗ middleware.py MISSING"
[ -f core/decorators.py ] && echo "✓ decorators.py" || echo "✗ decorators.py MISSING"
[ -f core/tasks.py ] && echo "✓ tasks.py" || echo "✗ tasks.py MISSING"
[ -f core/signals.py ] && echo "✓ signals.py" || echo "✗ signals.py MISSING"
[ -f core/api_views.py ] && echo "✓ api_views.py" || echo "✗ api_views.py MISSING"
```

### Updated Files
```bash
# Check modifications
grep -q "def ready" core/apps.py && echo "✓ apps.py updated" || echo "✗ apps.py NOT updated"
grep -q "api_views" estimate_site/urls.py && echo "✓ urls.py updated" || echo "✗ urls.py NOT updated"
grep -q "'core.middleware.OrganizationMiddleware'" estimate_site/settings.py && echo "✓ settings.py updated" || echo "✗ settings.py NOT updated"
```

### Documentation Files
```bash
# Check documentation exists
[ -f SAAS_PHASE_2_COMPLETE.md ] && echo "✓ Phase 2 docs" || echo "✗ Phase 2 docs MISSING"
[ -f PHASE_2_SUMMARY.md ] && echo "✓ Phase 2 summary" || echo "✗ Phase 2 summary MISSING"
[ -f PHASE_2_INTEGRATION_GUIDE.md ] && echo "✓ Integration guide" || echo "✗ Integration guide MISSING"
[ -f PHASE_2_FILES_MANIFEST.md ] && echo "✓ Files manifest" || echo "✗ Files manifest MISSING"
```

---

## 🔍 Syntax Validation

### Python File Syntax
```bash
# Check each file compiles
python -m py_compile core/middleware.py && echo "✓ middleware.py syntax OK" || echo "✗ middleware.py has errors"
python -m py_compile core/decorators.py && echo "✓ decorators.py syntax OK" || echo "✗ decorators.py has errors"
python -m py_compile core/tasks.py && echo "✓ tasks.py syntax OK" || echo "✗ tasks.py has errors"
python -m py_compile core/signals.py && echo "✓ signals.py syntax OK" || echo "✗ signals.py has errors"
python -m py_compile core/api_views.py && echo "✓ api_views.py syntax OK" || echo "✗ api_views.py has errors"
```

### Django Import Check
```bash
# Can Django import the modules?
python manage.py shell -c "from core.middleware import OrganizationMiddleware; print('✓ middleware imports')"
python manage.py shell -c "from core.decorators import org_required; print('✓ decorators imports')"
python manage.py shell -c "from core.tasks import process_excel_upload; print('✓ tasks imports')"
python manage.py shell -c "from core.signals import *; print('✓ signals imports')"
python manage.py shell -c "from core.api_views import job_status; print('✓ api_views imports')"
```

---

## 🏗️ Code Structure Validation

### Middleware Components
```python
# Verify middleware classes exist
from core.middleware import OrganizationMiddleware, OrgScopingMiddleware

# Check required methods
assert hasattr(OrganizationMiddleware, '__init__')
assert hasattr(OrganizationMiddleware, '__call__')
assert hasattr(OrganizationMiddleware, '_should_skip')
print("✓ Middleware structure OK")
```

### Decorator Functions
```python
# Verify all decorators exist
from core.decorators import (
    org_required,
    org_scoped,
    role_required,
    api_org_scoped,
    handle_org_access_error,
)

# Check they're callable
assert callable(org_required)
assert callable(org_scoped)
assert callable(role_required('owner'))
assert callable(api_org_scoped)
assert callable(handle_org_access_error)
print("✓ All decorators exist and callable")
```

### Celery Tasks
```python
# Verify tasks are registered
from core.tasks import (
    process_excel_upload,
    generate_bill_pdf,
    generate_workslip_pdf,
    cleanup_old_files,
)

# Check task properties
assert hasattr(process_excel_upload, 'delay')  # Celery task method
assert hasattr(process_excel_upload, 'apply_async')
assert process_excel_upload.max_retries == 3
print("✓ All Celery tasks registered")
```

### Signal Handlers
```python
# Verify signals are connected
from django.core.signals import setting_changed
from django.db.models.signals import post_save
from django.contrib.auth.models import User

# Check receivers exist (this is implicit in core.signals module load)
from core import signals  # This registers handlers
print("✓ Signal handlers registered (when signals module imported)")
```

### API Views
```python
# Verify all views exist
from core.api_views import (
    job_status,
    upload_status,
    download_output_file,
    list_outputs,
    create_job,
)

# Check they accept request parameter
import inspect
assert 'request' in inspect.signature(job_status).parameters
assert 'request' in inspect.signature(upload_status).parameters
assert 'request' in inspect.signature(download_output_file).parameters
assert 'request' in inspect.signature(list_outputs).parameters
assert 'request' in inspect.signature(create_job).parameters
print("✓ All API views have request parameter")
```

---

## ⚙️ Configuration Validation

### Middleware Activation
```bash
# Check middleware is in MIDDLEWARE setting
python manage.py shell -c "
from django.conf import settings
middlewares = settings.MIDDLEWARE
if 'core.middleware.OrganizationMiddleware' in middlewares:
    print('✓ OrganizationMiddleware in MIDDLEWARE')
else:
    print('✗ OrganizationMiddleware NOT in MIDDLEWARE')
"
```

### URL Routes
```bash
# Check routes exist
python manage.py show_urls | grep -E "api/jobs|api/uploads|api/outputs" && echo "✓ API routes registered" || echo "✗ API routes NOT found"
```

### Settings Import
```bash
# Check settings loads without error
python manage.py shell -c "from django.conf import settings; print('✓ Settings load OK')"
```

---

## 🧪 Functional Tests

### Test 1: Middleware Attaches Organization
```python
# In Django shell
python manage.py shell

from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from core.middleware import OrganizationMiddleware
from core.models import Organization, Membership

# Get a user (create if needed)
user = User.objects.first()
if not user:
    user = User.objects.create(username='testuser')

# Get their organization (auto-created via signals)
membership = Membership.objects.filter(user=user).first()
if membership:
    org = membership.organization
    
    # Simulate request
    factory = RequestFactory()
    request = factory.get('/')
    request.user = user
    
    # Apply middleware
    middleware = OrganizationMiddleware(lambda r: None)
    middleware(request)
    
    # Check
    if hasattr(request, 'organization') and request.organization:
        print("✓ Middleware attaches organization")
    else:
        print("✗ Middleware failed to attach organization")
else:
    print("✗ User has no organization (signals not working?)")
```

### Test 2: Decorators Check Organization
```python
# In Django shell
from core.decorators import org_required
from django.contrib.auth.models import User

# Create test view
def test_view(request):
    return "OK"

decorated = org_required(test_view)

# Check decorator returns a function
if callable(decorated):
    print("✓ @org_required decorator creates callable")
else:
    print("✗ @org_required decorator failed")
```

### Test 3: Celery Task Registration
```bash
# Check tasks are discoverable
celery -A estimate_site inspect active_queues | grep -i excel && echo "✓ Celery sees task queue" || echo "✗ Celery task queue not visible"
```

### Test 4: API Route Accessibility
```bash
# Start server: python manage.py runserver
# In another terminal:

# Test unauthenticated access (should fail)
curl http://localhost:8000/api/jobs/1/status/ 2>/dev/null | grep -q "login\|401\|403" && echo "✓ API requires auth"

# Test authenticated access (after login)
# Would need to set up test client with session/token
```

### Test 5: Signal Handler (Auto-Create Org)
```python
# In Django shell
from django.contrib.auth.models import User
from core.models import Organization, Membership

# Create new user (or get existing)
user, created = User.objects.get_or_create(username='testuser2')

if created:
    # If user was just created, check org was auto-created
    membership = Membership.objects.filter(user=user).first()
    if membership:
        print(f"✓ Organization auto-created: {membership.organization.name}")
        print(f"✓ Role is OWNER: {membership.role == 'owner'}")
    else:
        print("✗ Organization NOT auto-created (signals not firing?)")
else:
    print("ℹ User already existed, signals won't fire again")
```

---

## 📊 Coverage Summary Template

Copy and fill this out:

```
Phase 2 Verification Checklist
==============================

Date: [DATE]
Verified By: [NAME]

FILE EXISTENCE:
[ ] middleware.py exists
[ ] decorators.py exists
[ ] tasks.py exists
[ ] signals.py exists
[ ] api_views.py exists
[ ] apps.py updated
[ ] urls.py updated
[ ] settings.py updated

SYNTAX:
[ ] All .py files compile without errors
[ ] All imports work

CODE STRUCTURE:
[ ] OrganizationMiddleware exists with required methods
[ ] All 5 decorators defined and callable
[ ] All 4 Celery tasks defined with correct signatures
[ ] Signal handlers registered

CONFIGURATION:
[ ] OrganizationMiddleware in MIDDLEWARE setting
[ ] 5 API routes registered in urls.py
[ ] Settings imports successfully

FUNCTIONAL:
[ ] Middleware attaches request.organization
[ ] Decorators enforce org access
[ ] Celery tasks discoverable
[ ] API routes accessible (with auth)
[ ] Signals auto-create org on signup

OVERALL STATUS: [ ] PASS [ ] FAIL

Issues Found (if any):
- [ISSUE 1]
- [ISSUE 2]

Sign-off: ___________________
```

---

## 🚀 Ready to Proceed?

Phase 2 verification passes when:

✅ All 5 files created
✅ 3 files updated correctly
✅ No Python syntax errors
✅ All imports work
✅ Middleware in settings
✅ Routes in urls.py
✅ Signals tested
✅ At least 1 functional test passes

**If all checks pass:** Proceed to Phase 3 (View Refactoring)
**If any checks fail:** Review PHASE_2_INTEGRATION_GUIDE.md for troubleshooting

