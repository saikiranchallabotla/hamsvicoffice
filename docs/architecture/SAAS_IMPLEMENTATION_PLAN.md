# Production-Ready Multi-Tenant SaaS Implementation Plan

## PROJECT SCAN RESULTS

### Current State
- ✅ Authentication: Django auth exists (user login), added in previous step
- ⚠️ Database: SQLite (must migrate to PostgreSQL)
- ❌ Multi-tenancy: User-scoped but no Organization model
- ❌ File storage: Local media files only
- ❌ Background jobs: None (all Excel processing in-request)
- ❌ Async processing: No Celery/Redis
- ✅ Excel processing: Exists in views.py (must move to tasks)

### Key Files to Modify
```
estimate_site/
├── settings.py              # Database, storages, Celery config
├── urls.py                  # Add job status endpoints, uploads
├── middleware.py            # [NEW] Org scoping middleware
├── celery.py               # [NEW] Celery app config
└── asgi.py                 # [UPDATE] Add Celery support

core/
├── models.py               # [UPDATE] Add Organization, Membership, Upload, Job, OutputFile
├── views.py                # [UPDATE] Refactor to use jobs, add job status endpoints
├── auth_views.py           # [UPDATE] Add org context to login/register
├── tasks.py                # [NEW] Celery tasks for Excel processing
├── admin.py                # [UPDATE] Add new models to admin
├── managers.py             # [NEW] QuerySet managers for org scoping
└── templates/
    ├── upload.html         # [NEW] File upload interface
    ├── job_status.html     # [NEW] Job polling page
    └── outputs.html        # [NEW] Download outputs list

requirements.txt            # [UPDATE] Add PostgreSQL, Celery, Redis, django-storages, python-dotenv
.env                       # [NEW] Environment variables template
docker-compose.yml         # [NEW] Local dev with Postgres + Redis
manage.py                  # No changes
```

---

## IMPLEMENTATION PHASES

### PHASE 1: Database & Models (6-8 hours)
1. Add Organization & Membership models
2. Create Upload, Job, OutputFile models
3. Add org scoping to existing models (Project, Estimate, etc.)
4. Create QuerySet managers for org filtering
5. Create migrations

### PHASE 2: Settings & Infrastructure (4-6 hours)
1. Update settings.py for PostgreSQL + environment variables
2. Add django-storages for S3/DO Spaces
3. Add Celery + Redis configuration
4. Create .env template

### PHASE 3: Background Jobs System (8-10 hours)
1. Extract Excel logic from views into Celery tasks
2. Create Job model with status tracking
3. Implement job polling endpoint (/jobs/<id>/status/)
4. Error handling & logging

### PHASE 4: View Refactoring (10-12 hours)
1. Add org scoping middleware
2. Update existing views to use jobs
3. Create upload → job → output workflow
4. Add login requirements to all views

### PHASE 5: Admin & UI (4-6 hours)
1. Register models in Django admin
2. Create minimal templates (upload, job status, outputs)
3. Add org context to auth views

### PHASE 6: Testing & Documentation (4-6 hours)
1. Add org scoping tests
2. Create local dev setup guide (docker-compose)
3. Production deployment guide

---

## DETAILED IMPLEMENTATION STEPS

### Step 1: Create New Models
- Organization (name, plan, created_at, owner=FK(User))
- Membership (org=FK, user=FK, role=[admin/member])
- Upload (org=FK, user=FK, file, status, created_at)
- Job (org=FK, user=FK, upload=FK, task_id, status, progress, result, error_log, created_at, started_at, completed_at)
- OutputFile (org=FK, user=FK, job=FK, file, download_count)
- EstimateSnapshot (store rate/input snapshots at time of generation)

### Step 2: Add QuerySet Managers
```python
# All models get org scoping
class OrgScopedManager(models.Manager):
    def for_org(self, organization):
        return self.filter(organization=organization)

# In views: Model.objects.for_org(request.user.organization)
```

### Step 3: Middleware for Org Context
```python
# Every request: request.organization = user.organization
# Every view: enforce org scoping on all queries
```

### Step 4: Celery Tasks
```python
# tasks.py
@shared_task
def process_excel_upload(upload_id, job_id):
    # Extract current logic from views
    # Load workbook → parse → generate output → save to S3
    # Update Job model with progress, result, errors
    # Return download URL (signed S3 URL)
```

### Step 5: View Updates
```python
# Old: @login_required + generate Excel in-request
# New: @login_required + @require_org_access + create Job + enqueue task + return job_id

# New endpoint: /jobs/<id>/status/ → JSON {"status": "pending|running|completed|failed", "progress": 50, "output_url": "..."}
```

---

## FILE CHANGES SUMMARY

| File | Changes | Lines |
|------|---------|-------|
| models.py | +200 | Add 5 new models + managers |
| views.py | +300 | Add job endpoints, refactor to use tasks |
| tasks.py | +800 | Extract Excel logic from views |
| settings.py | +100 | DB, storage, Celery config |
| middleware.py | +50 | Org scoping enforcement |
| managers.py | +100 | QuerySet org filtering |
| auth_views.py | +50 | Org context in login |
| admin.py | +100 | Register new models |
| urls.py | +20 | Add /jobs/, /upload/, /outputs/ routes |
| requirements.txt | +10 | New dependencies |
| .env | +30 | Template variables |
| docker-compose.yml | +40 | Postgres + Redis |
| **TOTAL** | **~1900 lines** | |

---

## PRODUCTION CHECKLIST

- [ ] PostgreSQL configured + tested
- [ ] S3/DO Spaces credentials in .env
- [ ] Celery workers running (celery -A estimate_site worker)
- [ ] Redis running (redis-server or container)
- [ ] Job polling endpoint tested
- [ ] Org scoping middleware active
- [ ] All views require @login_required
- [ ] File uploads go to S3 with signed URLs
- [ ] Excel tasks run async, no in-request processing
- [ ] Error handling & logging set up
- [ ] Admin panel works for all new models
- [ ] Tests pass (org scoping, job workflow)

---

## ESTIMATED EFFORT
- **Model design & migrations:** 6-8 hrs
- **Settings & infrastructure:** 4-6 hrs
- **Celery task extraction:** 8-10 hrs
- **View refactoring:** 10-12 hrs
- **Admin & UI:** 4-6 hrs
- **Testing & docs:** 4-6 hrs
- **TOTAL:** 36-48 hours of development

---

## NEXT: Detailed implementation will proceed Phase by Phase
