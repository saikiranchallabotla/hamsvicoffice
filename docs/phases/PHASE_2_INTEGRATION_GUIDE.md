# PHASE_2_INTEGRATION_GUIDE.md

## Phase 2 Integration Checklist

After Phase 1 (models, settings, docker-compose), Phase 2 adds middleware, decorators, tasks, and APIs.

---

## ✅ Files Created in Phase 2

### Core Application Files
1. **core/middleware.py** (67 lines)
   - OrganizationMiddleware: Attaches request.organization
   - OrgScopingMiddleware: Placeholder for defense-in-depth
   
2. **core/decorators.py** (135 lines)
   - @org_required: Ensure org membership
   - @org_scoped: Verify URL slug matches org
   - @role_required: Enforce minimum role
   - @api_org_scoped: API version
   - @handle_org_access_error: Catch org access errors
   
3. **core/tasks.py** (380 lines)
   - process_excel_upload: Async Excel parsing
   - generate_bill_pdf: Async bill generation
   - generate_workslip_pdf: Async workslip generation
   - cleanup_old_files: Maintenance task
   
4. **core/signals.py** (60 lines)
   - create_user_profile: Auto-create org on signup
   - save_user_profile: Ensure profile exists
   
5. **core/api_views.py** (310 lines)
   - job_status: GET job progress
   - upload_status: GET upload status
   - download_output_file: GET file with tracking
   - list_outputs: GET all output files
   - create_job: POST create + enqueue job

### Configuration Updates
6. **core/apps.py** (Updated)
   - Added: Signal registration in ready()
   
7. **estimate_site/urls.py** (Updated)
   - Added: 5 API route patterns
   
8. **estimate_site/settings.py** (Updated)
   - Activated: OrganizationMiddleware

### Documentation
9. **SAAS_PHASE_2_COMPLETE.md** - Detailed phase overview
10. **PHASE_2_SUMMARY.md** - Quick reference

---

## 📋 Pre-Integration Verification

Before using Phase 2, verify Phase 1 is complete:

```bash
# Check Phase 1 files exist
ls core/models.py        # ✓ Should exist with 6 new models
ls core/managers.py      # ✓ Should exist with custom managers
ls core/admin.py         # ✓ Should be updated with 9 registrations
ls .env.example          # ✓ Should exist
ls docker-compose.yml    # ✓ Should exist
```

---

## 🚀 Step-by-Step Integration

### Step 1: Verify All Files Created
```bash
# Check Phase 2 files
ls core/middleware.py
ls core/decorators.py
ls core/tasks.py
ls core/signals.py
ls core/api_views.py

# Check updates
grep "OrganizationMiddleware" estimate_site/settings.py
grep "api_views" estimate_site/urls.py
grep "def ready" core/apps.py
```

### Step 2: Start Services

```bash
# Terminal 1: PostgreSQL
docker-compose up postgres

# Terminal 2: Redis
docker-compose up redis

# Wait for both to be healthy
# Check: docker-compose ps
```

### Step 3: Run Migrations

```bash
# Create migration files for new models (Phase 1)
python manage.py makemigrations core --noinput

# Verify migration file was created
ls core/migrations/000*.py  # Should show new migration

# Apply migrations
python manage.py migrate
```

### Step 4: Create Superuser (Optional)

```bash
python manage.py createsuperuser
# Follow prompts
# Note: Signals will auto-create Organization + Membership
```

### Step 5: Start Django Dev Server

```bash
python manage.py runserver 0.0.0.0:8000
```

### Step 6: Start Celery Worker

```bash
# In new terminal
celery -A estimate_site worker -l info -Q excel_processing
```

### Step 7: Test Basic Functionality

```bash
# Visit http://localhost:8000/admin/
# Login with superuser credentials
# Check: Organization auto-created
# Check: Membership shows user as OWNER
```

---

## 🧪 Testing Phase 2 Features

### Test 1: Org Middleware
```python
# In Django shell
python manage.py shell

from django.test import RequestFactory
from core.middleware import OrganizationMiddleware
from django.contrib.auth.models import User

# Create test user
user = User.objects.first()

# Simulate request
factory = RequestFactory()
request = factory.get('/')
request.user = user

# Test middleware
middleware = OrganizationMiddleware(lambda r: None)
middleware(request)

# Check organization attached
print(request.organization)  # Should print Organization object
```

### Test 2: Task Execution
```bash
# Upload an Excel file via web interface
# Watch Celery worker output:
# [tasks] process_excel_upload[...]: Started
# [tasks] process_excel_upload[...]: Success

# Check Job status in admin
# admin > Jobs > (find your job)
# status should be COMPLETED
# Check created OutputFile
```

### Test 3: API Endpoints
```bash
# Get JWT token or use sessionid cookie
curl http://localhost:8000/api/jobs/1/status/ -H "Cookie: sessionid=..."

# Should return JSON:
# {
#   "id": 1,
#   "status": "completed",
#   "progress": 100,
#   "outputs": [...]
# }
```

### Test 4: Decorators
```python
# In a view
from core.decorators import org_required, role_required

@role_required('owner', 'admin')
@org_required
def admin_only_view(request):
    return HttpResponse("Only admins can see this")

# Try accessing:
# - As non-owner: Should get 403 Forbidden
# - As owner: Should work fine
```

---

## 🔄 Data Flow Examples

### Example 1: User Signup → Auto Org Creation
```
1. User visits /register/
2. Fills form: username, email, password
3. POST to auth_views.register()
4. User object created by Django auth
5. post_save signal fires
6. create_user_profile signal handler executes:
   - Creates UserProfile
   - Creates Organization (name: "user's Organization", plan: FREE)
   - Creates Membership (role: OWNER)
7. User redirected to dashboard
8. request.organization available in all views
```

### Example 2: Excel Upload → Async Processing
```
1. User visits /uploads/ (to be created Phase 3)
2. Selects Excel file
3. File uploaded, Upload object created
4. Frontend calls POST /api/jobs/create/
   - Request: {"upload_id": 1, "job_type": "excel_parse"}
5. Job created (status: PENDING)
6. Celery task enqueued: process_excel_upload(upload_id=1)
7. API returns: {"job_id": 1, "status_url": "/api/jobs/1/status/"}
8. Frontend polls GET /api/jobs/1/status/
   - Iteration 1: progress=10%, current_step="Reading Excel..."
   - Iteration 2: progress=30%, current_step="Parsing data..."
   - Iteration 3: progress=100%, current_step="Complete", outputs=[...]
9. User sees progress bar updated
10. When complete, download links appear
11. User clicks download → GET /api/outputs/1/download/
    - download_count incremented
    - Signed URL returned (or direct file for local storage)
```

### Example 3: Role-Based Access Control
```
1. User A (member) tries to access org settings
2. Hits view: @role_required('owner', 'admin')
3. Middleware provides: request.organization
4. Decorator checks: Membership(user=A, org=?).role
5. Role is 'member', not in ['owner', 'admin']
6. Returns: 403 Forbidden "Requires owner or admin role"

vs.

1. User B (owner) tries same
2. Membership(user=B, org=?).role = 'owner'
3. Role in ['owner', 'admin']: True
4. View executes normally
```

---

## 📁 File Structure After Phase 2

```
core/
├── __init__.py
├── admin.py           # Updated with 9 model registrations
├── apps.py            # Updated: ready() calls signals
├── models.py          # From Phase 1: 6 new models + managers
├── managers.py        # From Phase 1: Custom QuerySet managers
├── middleware.py      # NEW: Organization scoping
├── decorators.py      # NEW: Permission enforcement
├── tasks.py           # NEW: Celery async tasks
├── signals.py         # NEW: Auto org creation
├── api_views.py       # NEW: JSON API endpoints
├── views.py           # From Phase 0: Existing views (to refactor Phase 3)
├── auth_views.py      # From Phase 0: Auth views (to refactor Phase 3)
├── utils_excel.py     # From Phase 0: Excel utilities (used by tasks)
├── migrations/
│   ├── __init__.py
│   ├── 0001-0011.py   # From Phase 1
│   └── 0012_*.py      # From Phase 1 (pending apply)
└── templates/
    └── ...            # From Phase 0
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "No module named 'core.signals'"
**Solution:** Check core/apps.py has ready() method with import
```python
def ready(self):
    import core.signals  # Must be here
```

### Issue 2: "ModuleNotFoundError: No module named 'celery'"
**Solution:** Install Celery from requirements.txt
```bash
pip install -r requirements.txt
```

### Issue 3: "ConnectionError: Error 111 connecting to 127.0.0.1:6379"
**Solution:** Start Redis service
```bash
docker-compose up redis
```

### Issue 4: "psycopg2 not found" (when using PostgreSQL)
**Solution:** Install psycopg2-binary
```bash
pip install psycopg2-binary
```

### Issue 5: Middleware not attaching request.organization
**Solution:** Check middleware order in settings.py
- Must be AFTER auth middleware
- Must be BEFORE view execution
- Standard Django middleware should come before custom

---

## ✅ Success Criteria

Phase 2 is successfully integrated when:

- [ ] All 5 new Python files exist and have no syntax errors
- [ ] Settings.py activates OrganizationMiddleware
- [ ] urls.py includes all 5 API routes
- [ ] Migrations apply without errors
- [ ] New user signups auto-create Organization + Membership
- [ ] request.organization available in views
- [ ] @org_required, @role_required decorators work
- [ ] Celery tasks enqueue and execute
- [ ] /api/jobs/{id}/status/ returns job progress as JSON
- [ ] /api/outputs/{id}/download/ works and increments counter

---

## 📝 Next: Phase 3 - View Refactoring

Once Phase 2 integration is complete, Phase 3 will:

1. Add @org_required to all existing views
2. Refactor views to enqueue tasks instead of in-request processing
3. Update response handling to use job polling
4. Add org context to templates
5. Create upload.html, job_status.html templates

**Estimated scope:** 15-20 file modifications, 2-3 hours work

---

## 📞 Support Notes

### For Backend Issues
- Check Celery worker logs: `celery -A estimate_site worker -l debug`
- Check Django logs in: `logs/` directory (created by settings.py)
- Check database: `psql -U postgres -d hamsvic` (if using PostgreSQL)

### For Frontend Issues
- Check browser console for JavaScript errors
- Verify API endpoints return JSON 200 (not 403/404)
- Check org_id in all API requests

### For Performance
- Celery task queue monitoring: `celery -A estimate_site events`
- Database query logging: Set DEBUG=True in .env
- Redis memory: `redis-cli info memory`

