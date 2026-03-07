# PHASE_3_IMPLEMENTATION_PLAN.md

## Phase 3: View Refactoring - Implementation Plan

**Goal:** Refactor existing views to use organization scoping, decorators, and async job processing

**Timeline:** 12-16 hours spread across multiple steps

---

## Overview

Phase 3 transforms existing views from:
- ❌ User-scoped to ✅ Organization-scoped
- ❌ In-request Excel processing to ✅ Async Celery tasks
- ❌ Unprotected to ✅ Permission-decorated
- ❌ Direct file responses to ✅ Job-based async returns

---

## Views to Refactor

### Authentication Views (core/auth_views.py) - 10 functions
1. `register()` - Auto-create org + membership
2. `login_view()` - Attach org to session
3. `logout_view()` - No changes needed
4. `dashboard()` - Show org stats
5. `profile_view()` - Add org context
6. `my_estimates()` - Filter by org
7. `view_estimate()` - Add org check
8. `delete_estimate()` - Add org check
9. `save_estimate()` - Filter by org

### Main Views (core/views.py) - 25+ functions
#### Excel Processing Views (use async tasks)
- `bill_document()` → Call task + return job URL
- `bill()` → Use estimate jobs
- `self_formatted_document()` → Call task
- `estimate()` → Show job status
- `workslip()` → Show job status

#### Project Management Views (add org scoping)
- `my_projects()` → Filter by org
- `create_project()` → Add org FK
- `load_project()` → Org check
- `delete_project()` → Org check
- `save_project()` → Org check
- `new_project()` → Create in org

#### Category/Item Navigation (add org scoping)
- `datas()` → Org context
- `datas_groups()` → Filter by org
- `datas_items()` → Filter by org
- `fetch_item()` → Org check
- `select_project()` → Org filter
- `choose_category()` → Org filter

#### Output/Download Views (track + serve from storage)
- `output_panel()` → Show OutputFile records
- `download_output()` → Use signed URLs
- `clear_output()` → Clean OutputFiles

#### Self-Formatted Views (add org scoping)
- `self_formatted_form_page()` → Org filter
- `self_formatted_generate()` → Call task
- `self_formatted_save_format()` → Org FK
- `self_formatted_use_format()` → Org check
- `self_formatted_edit_format()` → Org check
- `self_formatted_delete_format()` → Org check

#### Temp Works Views (add org scoping)
- `tempworks_home()` → Org filter
- `temp_groups()` → Org filter
- `temp_items()` → Org filter
- `temp_add_item()` → Org scoped
- `temp_save_state()` → Org scoped
- `temp_remove_item()` → Org scoped
- `temp_download_output()` → Org scoped

---

## Refactoring Strategy

### Step 1: Update auth_views.py
- Add `@org_required` to protected views
- Update register() to create org + membership
- Update login_view() to set org context
- Filter all queries by organization

### Step 2: Update views.py imports & helpers
- Add org_required import
- Add task imports
- Create helper: get_org_from_request()
- Update all Excel processing to call tasks

### Step 3: Refactor Excel processing views
- `bill_document()` → Enqueue task, return job URL
- `self_formatted_document()` → Enqueue task, return job URL
- `estimate()` / `bill()` → Show job status + download
- Remove in-request Excel generation

### Step 4: Refactor project management views
- Add `@org_required` to all
- Filter Project.objects by org
- Add org FK when creating projects

### Step 5: Refactor category/item navigation
- Add org scoping to datas() and related views
- Filter categories by org

### Step 6: Refactor output/download views
- Update to use OutputFile model
- Generate signed URLs instead of direct responses
- Track download count

### Step 7: Refactor self-formatted & temp works
- Add org scoping
- Update task calls
- Filter by org

---

## Files to Modify

### 1. core/auth_views.py (315 lines)
**Changes:**
- Add imports: decorators, signals handled by Phase 2
- Add `@org_required` to protected views
- Update register() to use signals
- Add org context to dashboard, profile

**Lines changed:** ~100-150

### 2. core/views.py (7989 lines) - LARGEST FILE
**Changes:**
- Add imports at top: `from .decorators import org_required`
- Add imports: `from .tasks import process_excel_upload, generate_bill_pdf, generate_workslip_pdf`
- Replace all Excel processing in views with task calls
- Add `@org_required` to views
- Filter all Project/Estimate queries by organization
- Update responses: direct files → job URLs

**Impact areas:**
- Line 77-87: home(), workslip() - May need org context
- Line 2584: bill() - Async task call
- Line 4941: bill_document() - Major refactor
- Line 5466: self_formatted_document() - Major refactor
- Line 5680-5693: my_projects(), create_project() - Add org
- Line 6254-6323: save_project(), load_project() - Org checks
- Line 6441: delete_project() - Org check
- Line 6944-7108: self_formatted views - Add org
- Line 7210-7386: temp works views - Add org

**Lines changed:** ~500-700

### 3. Templates (HTML files - minimal changes)
**Changes:**
- Show job status instead of direct file downloads
- Add progress bars for async jobs
- Add download links to OutputFiles
- Update form submissions to create jobs

**Files:**
- bill.html → Show job status
- estimate.html → Show job status
- self_formatted.html → Show job status
- my_projects.html → Add org context
- output.html → Link to OutputFiles

---

## Decorator Patterns

### For Auth-Required Views
```python
@org_required
def my_view(request):
    org = request.organization
    items = Project.objects.for_org(org)
```

### For Role-Protected Views
```python
@role_required('owner', 'admin')
@org_required
def manage_org(request):
    # Only owners/admins
```

### For API Views
```python
@org_required
def api_endpoint(request):
    org = request.organization
    return JsonResponse({...})
```

---

## Task Patterns

### Old Way (In-Request)
```python
def bill_document(request):
    # Heavy Excel processing
    excel_bytes = generate_bill(...)
    return HttpResponse(excel_bytes, ...)
```

### New Way (Async)
```python
@org_required
def bill_document(request):
    # Create upload
    upload = Upload.objects.create(...)
    
    # Create job
    job = Job.objects.create(
        organization=request.organization,
        upload=upload,
        job_type='generate_bill'
    )
    
    # Enqueue task
    task = generate_bill_pdf.delay(job.id, ...)
    job.celery_task_id = task.id
    job.save()
    
    # Return job URL
    return redirect('job_status', job_id=job.id)
```

---

## Database Considerations

### New Fields Needed
- Project.organization (FK) - Already added Phase 1
- Estimate.organization (FK) - Already added Phase 1
- Estimate.job (FK) - Already added Phase 1
- SelfFormattedTemplate.organization (FK) - Already added Phase 1

### Queries to Update
```python
# Old
projects = Project.objects.filter(user=request.user)

# New
projects = Project.objects.for_org(request.organization)
```

---

## Testing Strategy

### Manual Testing
1. ✓ Register new user
   - Check: Organization auto-created
   - Check: Can see projects in org
   - Check: Can't see other org's projects

2. ✓ Create project
   - Check: Project in org
   - Check: Belongs to correct org

3. ✓ Generate bill (async)
   - Check: Job created
   - Check: Task enqueued
   - Check: Job status updates
   - Check: File generated after completion

4. ✓ Permission enforcement
   - Check: Can't access other org's data
   - Check: Decorators prevent cross-org access
   - Check: 404 for non-existent/other org

### Unit Tests (Phase 5)
- test_org_scoping.py: Verify org isolation
- test_async_jobs.py: Mock Celery tasks
- test_decorators.py: Verify permission checks
- test_views.py: View org filtering

---

## Rollout Plan

### Phase 3a: Auth Views (2-3 hours)
1. Update auth_views.py
2. Test user registration + org creation
3. Test login with org context

### Phase 3b: Core View Helpers (2 hours)
1. Add imports to views.py
2. Create helper functions
3. Add org parameter to all queries

### Phase 3c: Excel Processing (4-5 hours)
1. Refactor bill_document()
2. Refactor self_formatted_document()
3. Refactor estimate/bill views
4. Test task execution

### Phase 3d: Project Views (2-3 hours)
1. Add org scoping to project views
2. Update queries
3. Test org isolation

### Phase 3e: Category/Item Views (2 hours)
1. Add org scoping
2. Test navigation

### Phase 3f: Output/Download (1-2 hours)
1. Update download views
2. Use signed URLs
3. Track downloads

### Phase 3g: Templates (2-3 hours)
1. Add job status polling
2. Add progress bars
3. Update forms

---

## Success Criteria

- ✓ All views have `@org_required` or are public
- ✓ All queries filtered by organization
- ✓ No in-request Excel processing
- ✓ All Excel generation uses Celery tasks
- ✓ Job status API working
- ✓ File downloads use OutputFile + signed URLs
- ✓ User can't access other org's data
- ✓ All tests passing

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Large views.py hard to refactor | Break into smaller views, refactor incrementally |
| Breaking existing functionality | Thorough testing after each change |
| Users with multiple orgs | Phase 4 will add org selector |
| Partial async rollout | Gradual refactoring, tests verify behavior |

---

## Next Steps After Phase 3

### Phase 4: Organization Management
- Org settings view
- Team member management
- Role-based permissions UI

### Phase 5: Testing & Hardening
- Unit tests for all new logic
- Integration tests for async flows
- Performance testing with Celery

### Phase 6: Deployment & Docs
- Production deployment guide
- Migration guide for existing data
- User documentation

---

## Code Examples

### Before Phase 3
```python
@login_required
def my_projects(request):
    projects = Project.objects.filter(user=request.user)
    return render(request, 'projects.html', {'projects': projects})
```

### After Phase 3
```python
@org_required
def my_projects(request):
    org = request.organization
    projects = Project.objects.for_org(org)
    return render(request, 'projects.html', {'projects': projects, 'org': org})
```

### Before Phase 3 (Excel)
```python
@login_required
def bill_document(request):
    # 50+ lines of Excel processing
    excel_bytes = generate_bill(...)
    return HttpResponse(excel_bytes, ...)
```

### After Phase 3 (Async)
```python
@org_required
def bill_document(request):
    upload = Upload.objects.create(...)
    job = Job.objects.create(
        organization=request.organization,
        upload=upload,
        job_type='generate_bill'
    )
    task = generate_bill_pdf.delay(job.id)
    job.celery_task_id = task.id
    job.save()
    
    return JsonResponse({
        'job_id': job.id,
        'status_url': reverse('job_status', args=[job.id])
    })
```

---

## Estimated Effort

| Component | Hours | Priority |
|-----------|-------|----------|
| Phase 3a: Auth views | 3 | HIGH |
| Phase 3b: Helpers | 2 | HIGH |
| Phase 3c: Excel processing | 5 | HIGH |
| Phase 3d: Projects | 3 | HIGH |
| Phase 3e: Categories | 2 | MEDIUM |
| Phase 3f: Downloads | 2 | MEDIUM |
| Phase 3g: Templates | 3 | MEDIUM |
| **TOTAL** | **20 hours** | |

**Can be split across multiple sessions. Each sub-phase is standalone testable.**

