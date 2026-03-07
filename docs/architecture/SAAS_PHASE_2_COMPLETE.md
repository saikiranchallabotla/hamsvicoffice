# SAAS_PHASE_2_COMPLETE.md

## Phase 2: Middleware & Job System - COMPLETE

Implementation of organization-scoped middleware, async task processing, and API endpoints.

---

## Files Created

### 1. **core/middleware.py** (NEW)
Organization-scoping middleware that attaches user's organization to request object.

**Key Components:**
- `OrganizationMiddleware`: Attaches `request.organization` from user's primary Membership
- `OrgScopingMiddleware`: Placeholder for additional defense-in-depth checks
- Automatic org filtering for authenticated requests
- Graceful handling of users with no organization (future: redirect to org selection)

**Usage in views:**
```python
@org_required  # From decorators.py
def my_view(request):
    org = request.organization  # Available via middleware
    projects = Project.objects.for_org(org)
```

---

### 2. **core/decorators.py** (NEW)
View-level permission decorators for organization and role enforcement.

**Available Decorators:**

1. **@org_required**
   - Ensures user has active organization membership
   - Attaches request.organization
   - Redirects to org selection if needed

2. **@org_scoped(org_slug)**
   - Verifies URL slug matches user's organization
   - Prevents cross-organization access
   - Returns 403 Forbidden if mismatch

3. **@role_required('owner', 'admin')**
   - Enforces minimum role for action
   - Checks Membership.role in allowed list
   - Returns 403 Forbidden if insufficient permissions

4. **@api_org_scoped**
   - API version of org_scoped (returns JSON errors)
   - For REST endpoints

5. **@handle_org_access_error**
   - Catches ObjectDoesNotExist and returns 404
   - Prevents information leakage about cross-org objects

**Example Usage:**
```python
@role_required('owner', 'admin')
@org_required
def manage_team(request):
    # Only owners/admins can access
    org = request.organization
    members = Membership.objects.for_org(org)
```

---

### 3. **core/tasks.py** (NEW)
Celery tasks for asynchronous Excel processing and file generation.

**Key Tasks:**

1. **process_excel_upload(upload_id)**
   - Parse uploaded Excel file
   - Extract data and store in Job.result
   - Create OutputFile with parsed JSON
   - Handles retries (up to 3) with exponential backoff
   - Progress tracking: 10% → 30% → 50% → 100%

2. **generate_bill_pdf(job_id, project_id)**
   - Generate bill PDF from job data
   - Calls existing utility `generate_bill()`
   - Creates OutputFile with PDF
   - Stores in S3/local storage with org-scoped path

3. **generate_workslip_pdf(job_id, project_id)**
   - Generate workslip PDF from job data
   - Calls existing utility `generate_workslip()`
   - Creates OutputFile with PDF

4. **cleanup_old_files(days=30)**
   - Optional maintenance task
   - Deletes unused output files older than N days
   - Can be scheduled with django-celery-beat

**Task Configuration:**
- Queue: 'excel_processing' (routes all tasks to dedicated queue)
- Hard limit: 30 minutes
- Soft limit: 25 minutes
- Serializer: JSON only
- Max retries: 3 (for process_excel_upload)

**Error Handling:**
- All errors logged to Job.error_log (list of dicts)
- Job.error_message stores last error
- Job.status set to FAILED on error
- Retry logic with exponential backoff (60s, 120s, 240s)

**Storage:**
- Output files stored in: `outputs/{org_slug}/{filename}`
- Signed URLs used for S3/DO Spaces (1hr expiry)
- Local fallback for dev environment

---

### 4. **core/signals.py** (NEW)
Django signals for automatic organization setup on user creation.

**Signal Handlers:**

1. **create_user_profile (post_save User)**
   - Auto-creates UserProfile when new User created
   - Auto-creates Organization with FREE plan
   - Auto-creates OWNER Membership for the user
   - Sets org name to "{first_name}'s Organization"
   - Sets org slug to lowercased username

2. **save_user_profile (post_save User)**
   - Ensures UserProfile exists for all Users
   - Fallback for manual User creation via admin

**Effect:**
- New user signups automatically get their own organization
- User is automatically org owner
- Can be refactored later to allow user to join existing orgs

---

### 5. **core/apps.py** (UPDATED)
Added signal registration to app ready() hook.

**Change:**
```python
def ready(self):
    import core.signals  # Registers signal handlers
```

---

### 6. **core/api_views.py** (NEW)
REST-like JSON API endpoints for job/upload management.

**Endpoints:**

1. **GET /api/jobs/{job_id}/status/**
   - Returns: status, progress, current_step, outputs, errors
   - Used for frontend polling of job progress
   - Includes list of generated output files with download URLs

2. **GET /api/uploads/{upload_id}/status/**
   - Returns: upload status, file size, associated job
   - Allows frontend to track upload/job relationship

3. **GET /api/outputs/{file_id}/download/**
   - Download output file with auto-tracking
   - Increments download_count
   - Returns signed URL for S3 (or direct file for local storage)

4. **GET /api/outputs/**
   - List all output files for organization
   - Optional filter: ?job_id={id}
   - Returns: filename, file_type, download_count, created_at

5. **POST /api/jobs/create/**
   - Create new job and enqueue task
   - Body: `{"upload_id": ..., "job_type": "excel_parse|generate_bill|generate_workslip", "metadata": {}}`
   - Returns: job_id, status_url, celery_task_id
   - Auto-routes to appropriate Celery task

**Security:**
- All endpoints require `@org_required` decorator
- All queries filtered to user's organization
- Prevents cross-org file access
- CSRF protection via decorator parameter

**Frontend Usage (JavaScript):**
```javascript
// Poll for job progress
async function pollJobStatus(jobId) {
    const response = await fetch(`/api/jobs/${jobId}/status/`);
    const data = await response.json();
    
    console.log(data.progress);  // 0-100
    console.log(data.current_step);  // "Reading Excel file..."
    console.log(data.outputs);  // [ {filename, download_url, ...} ]
    
    if (!data.is_complete) {
        setTimeout(() => pollJobStatus(jobId), 1000);
    }
}
```

---

### 7. **estimate_site/urls.py** (UPDATED)
Added API route patterns.

**New Routes:**
```python
path('api/jobs/<int:job_id>/status/', ...)
path('api/uploads/<int:upload_id>/status/', ...)
path('api/outputs/<int:file_id>/download/', ...)
path('api/outputs/', ...)
path('api/jobs/create/', ...)
```

---

### 8. **estimate_site/settings.py** (UPDATED)
Activated OrganizationMiddleware.

**Change:**
```python
MIDDLEWARE = [
    ...
    'core.middleware.OrganizationMiddleware',  # Added
]
```

---

## Architecture Flow

### Upload → Job → Task → OutputFile

```
1. User uploads Excel file
   └─> Create Upload object (PROCESSING status)
   
2. Frontend calls POST /api/jobs/create/
   └─> Create Job object (PENDING status)
   └─> Link Upload to Job
   └─> Enqueue Celery task
   └─> Return job_id + status_url
   
3. Celery task executes (async, in background)
   └─> Update Job.progress, current_step
   └─> Parse Excel file
   └─> Store result in Job.result (JSON)
   └─> Create OutputFile(s) with content
   └─> Set Job.status = COMPLETED
   └─> Set Upload.status = COMPLETED
   
4. Frontend polls GET /api/jobs/{job_id}/status/
   └─> Gets progress: 10% → 30% → 50% → 100%
   └─> Gets current_step description
   └─> When complete, gets output file URLs
   
5. User downloads output file
   └─> GET /api/outputs/{file_id}/download/
   └─> Increments download_count
   └─> Returns signed URL (S3) or direct file (local)
```

---

## Organization Scoping Flow

```
User Login
  └─> Django auth succeeds
  └─> Middleware runs: request.organization = user.membership.organization
  
View execution
  └─> @org_required decorator checks request.organization exists
  └─> View code accesses request.organization
  └─> All queries use .for_org(request.organization)
  └─> Manager enforces filtering at QuerySet level
  └─> User cannot access other org's data
  
API calls
  └─> request.organization attached by middleware
  └─> API view filters queries by organization
  └─> Response only contains user's org data
```

---

## Async Processing Configuration

### Celery Settings (in settings.py)
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'

CELERY_TASK_ROUTES = {
    'core.tasks.process_excel_upload': {'queue': 'excel_processing'},
    'core.tasks.generate_bill_pdf': {'queue': 'excel_processing'},
    'core.tasks.generate_workslip_pdf': {'queue': 'excel_processing'},
}

CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes soft limit
```

### Running Workers
```bash
# Start worker (from manage.py directory)
celery -A estimate_site worker -l info -Q excel_processing

# Start beat scheduler (for periodic tasks)
celery -A estimate_site beat -l info

# Monitor with Flower (optional)
celery -A estimate_site events
```

---

## Database Changes

### New models (Phase 1)
- ✅ Organization
- ✅ Membership
- ✅ Upload
- ✅ Job
- ✅ OutputFile

### Updated models (Phase 1)
- ✅ Project (added organization FK)
- ✅ Estimate (added organization FK, job FK, rate_snapshot)
- ✅ SelfFormattedTemplate (added organization FK)

### Signal-triggered automatic creation
- Organization + Membership created on User signup
- UserProfile created on User creation

---

## Testing Recommendations

### Manual Testing

1. **User Signup**
   ```
   Create new user via /register/
   Check: Organization auto-created with FREE plan
   Check: Membership auto-created with OWNER role
   ```

2. **Organization Middleware**
   ```
   Login as user
   Check: request.organization available in views
   Check: Cannot access other org's data via URL manipulation
   ```

3. **Excel Upload & Processing**
   ```
   Upload Excel file → Job created
   Check: /api/jobs/{id}/status/ returns progress 10% → 100%
   Check: OutputFile created with parsed JSON
   Check: Download link works (signed URL or direct file)
   ```

4. **Decorators**
   ```
   Try accessing admin-only view as member → 403 Forbidden
   Try accessing other org's project → 404 Not Found
   Try accessing before membership → Redirect to org selection
   ```

### Unit Tests (to be created in Phase 5)
- test_org_scoping.py: Verify org isolation
- test_job_tasks.py: Mock Celery task execution
- test_api_views.py: Test all API endpoints
- test_signals.py: Verify org/membership auto-creation

---

## Next Steps (Phase 3)

### Priority: Update Existing Views

The existing views (home, bill_document, self_formatted_generate, etc.) currently:
- ✗ Don't use request.organization
- ✗ Don't enforce org scoping
- ✗ Process Excel in-request (blocking)

**Phase 3 will:**
1. Refactor views to use @org_required, @role_required
2. Extract Excel processing to Celery tasks
3. Update response handling to use job polling
4. Add org context to all templates

**Files to modify in Phase 3:**
- core/views.py (all view functions)
- core/auth_views.py (register, login, dashboard)
- core/utils_excel.py (refactor for Celery compatibility)
- core/templates/*.html (add job status polling)

---

## Deployment Checklist

Before going to production:

- [ ] Run migrations: `python manage.py migrate`
- [ ] Set `DEBUG=False` in .env
- [ ] Configure PostgreSQL in .env (DB_ENGINE=postgresql)
- [ ] Configure S3 in .env (STORAGE_TYPE=s3, AWS_* vars)
- [ ] Configure Redis in .env (CELERY_BROKER_URL)
- [ ] Set strong SECRET_KEY in .env
- [ ] Configure ALLOWED_HOSTS for domain
- [ ] Start Celery worker: `celery -A estimate_site worker`
- [ ] Start Celery beat: `celery -A estimate_site beat` (optional)
- [ ] Test job processing end-to-end
- [ ] Monitor logs for errors

---

## Key Improvements Over Phase 1

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| **Org Access** | Models support org FK | Middleware + decorators enforce it |
| **Excel Processing** | (Planned for Phase 2) | Now async via Celery tasks |
| **File Storage** | (Configured in settings) | OutputFile model + API |
| **User Requests** | Excel processing blocks HTTP | Enqueued as background job |
| **Job Tracking** | Job model created | Job polling API added |
| **Error Handling** | (N/A) | Error log, retry logic, status tracking |
| **Security** | Managers filter org | + Middleware + Decorators |

---

## Summary

Phase 2 completes the async job processing infrastructure and organization-scoping enforcement:

✅ Organization middleware attaches org to every request
✅ Decorators enforce org access at view level
✅ Celery tasks handle Excel processing asynchronously
✅ Job status tracking via polling API
✅ Output files managed with download tracking
✅ Signal handlers auto-create org on signup
✅ All API endpoints return org-scoped data

**Status:** Ready for Phase 3 (View Refactoring)
**Est. Completion:** Phase 3 integration, Phase 4 templates, Phase 5 tests, Phase 6 deployment docs
