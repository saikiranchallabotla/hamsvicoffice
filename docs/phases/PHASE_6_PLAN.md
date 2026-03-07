# Phase 6: Comprehensive Testing & Validation - PLAN

**Status:** 🔄 IN PLANNING  
**Objective:** Validate all Phases 1-5 with comprehensive testing  
**Scope:** Unit tests, integration tests, multi-tenancy validation, security checks  
**Expected Duration:** 2-3 hours  

---

## Executive Summary

After completing Phases 1-5 (complete Django multi-tenant transformation), Phase 6 focuses on **comprehensive testing** to validate:

✅ Multi-tenant isolation (User A cannot access User B's data)  
✅ View authentication (No anonymous access to protected views)  
✅ Organization scoping (All queries properly filtered)  
✅ Async job workflows (Celery tasks complete successfully)  
✅ File generation & download (Excel outputs work correctly)  
✅ Error handling (Proper error responses on failures)  

---

## What Needs Testing

### 1. Authentication & Authorization
- [ ] Login required on protected views
- [ ] Home page accessible without login
- [ ] Logout clears session properly
- [ ] Redirect to login on unauthorized access
- [ ] Session timeout works correctly

### 2. Multi-Tenancy Isolation (CRITICAL)
- [ ] User A cannot list User B's projects
- [ ] User A cannot create projects in User B's org
- [ ] User A cannot access User B's self-formatted templates
- [ ] User A cannot download User B's output files
- [ ] Job queries properly filtered by org

### 3. View Workflows
- [ ] Home → Login → Dashboard → Select Project → Choose Category
- [ ] Load items → Set quantities → Generate output
- [ ] Generate estimate → Download file
- [ ] Create/save/delete projects
- [ ] Create/save/delete self-formatted templates

### 4. Async Operations (Celery)
- [ ] Celery task enqueued successfully
- [ ] Job status updates (progress, current_step)
- [ ] Job completion creates OutputFile
- [ ] Job failure sets error_message
- [ ] Retry logic works on transient failures

### 5. File Operations
- [ ] Excel generated with correct sheets
- [ ] Styles/borders applied correctly
- [ ] Formulas calculated properly
- [ ] OutputFile downloadable via signed URL
- [ ] File cleanup removes old files

### 6. Database Queries
- [ ] Queries use select_related/prefetch_related
- [ ] No N+1 query problems
- [ ] Org filtering applied to all model queries
- [ ] Session data properly scoped

### 7. Error Handling
- [ ] Missing file returns 404
- [ ] Invalid org returns 403
- [ ] Database errors return 500
- [ ] Form validation errors returned properly
- [ ] Async task failures logged

### 8. API Endpoints
- [ ] /api/jobs/{id}/status/ returns correct JSON
- [ ] Job download URL is signed/temporary
- [ ] CSRF token validated on POST
- [ ] Invalid JSON returns 400

---

## Testing Structure

### Test Files to Create
```
core/tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── test_auth.py                   # Auth tests
├── test_multi_tenancy.py          # Org isolation tests
├── test_views.py                  # View tests
├── test_decorators.py             # Decorator tests
├── test_tasks.py                  # Celery task tests
├── test_workflows.py              # Integration tests
├── test_api.py                    # API endpoint tests
└── test_models.py                 # Model tests
```

### Test Categories

#### **Unit Tests** (Fast, isolated)
- Decorator functionality
- Helper functions
- Model methods
- Form validation

#### **Integration Tests** (Moderate, multi-component)
- View + Template rendering
- Database operations
- Session management
- File I/O

#### **System Tests** (Slow, full workflow)
- Login → Project Creation → Output Generation
- Celery task execution end-to-end
- Multi-user concurrent access
- File download & cleanup

---

## Testing Strategy

### 1. Test Fixtures & Factories
Create reusable test data:
```python
@pytest.fixture
def test_org():
    return Organization.objects.create(name="Test Org")

@pytest.fixture
def test_user(test_org):
    user = User.objects.create(username="testuser", password="test123")
    Membership.objects.create(user=user, organization=test_org, role="owner")
    return user

@pytest.fixture
def test_project(test_org, test_user):
    return Project.objects.create(
        organization=test_org,
        name="Test Project",
        category="electrical"
    )

@pytest.fixture
def authenticated_client(test_user):
    client = Client()
    client.force_login(test_user)
    return client
```

### 2. Test Organization Isolation
```python
def test_user_cannot_access_other_org_project(test_user, other_org_project):
    """User A cannot access User B's project"""
    client = Client()
    client.force_login(test_user)
    response = client.get(f'/project/{other_org_project.id}/')
    assert response.status_code == 403  # Forbidden
```

### 3. Test View Workflows
```python
def test_complete_output_generation_workflow(authenticated_client, test_project):
    """User selects items, generates output, downloads file"""
    # Step 1: Select category
    response = authenticated_client.get('/datas/electrical/')
    assert response.status_code == 200
    
    # Step 2: Select project
    response = authenticated_client.post('/save_project/electrical/', {
        'project_id': test_project.id
    })
    assert response.status_code == 302
    
    # Step 3: Toggle items (add to selection)
    response = authenticated_client.post('/toggle_item/electrical/Switchgear/', {
        'item': 'Item Name'
    })
    assert response.status_code == 302
    
    # Step 4: Generate output (async)
    response = authenticated_client.post('/datas/electrical/download/', {
        'qty_map': json.dumps({...}),
        'work_name': 'Test Work'
    })
    assert response.status_code == 200
    data = response.json()
    assert 'job_id' in data
    
    # Step 5: Poll job status
    job_id = data['job_id']
    response = authenticated_client.get(f'/api/jobs/{job_id}/status/')
    assert response.status_code == 200
```

### 4. Test Celery Tasks
```python
def test_generate_output_excel_task(test_user, test_project):
    """Celery task generates Excel successfully"""
    job = Job.objects.create(
        organization=test_user.organization,
        user=test_user,
        job_type='generate_output_excel',
        status=Job.JobStatus.QUEUED
    )
    
    result = generate_output_excel(
        job.id,
        'electrical',
        json.dumps({...}),
        'Test Work',
        'original'
    )
    
    # Refresh job from DB
    job.refresh_from_db()
    assert job.status == Job.JobStatus.COMPLETED
    assert job.progress == 100
    assert OutputFile.objects.filter(job=job).exists()
```

### 5. Test Multi-Tenancy
```python
def test_job_query_isolation(test_user, other_org_user):
    """Each user sees only their org's jobs"""
    # User A creates job
    job_a = Job.objects.create(
        organization=test_user.organization,
        user=test_user,
        status=Job.JobStatus.COMPLETED
    )
    
    # User B creates job
    job_b = Job.objects.create(
        organization=other_org_user.organization,
        user=other_org_user,
        status=Job.JobStatus.COMPLETED
    )
    
    # User A should only see their job
    user_a_jobs = Job.objects.filter(user=test_user)
    assert job_a in user_a_jobs
    assert job_b not in user_a_jobs
```

---

## Test Execution Plan

### Step 1: Set Up Test Infrastructure
- Create conftest.py with fixtures
- Create factories for test data
- Set up test database configuration
- Configure pytest.ini

### Step 2: Write Unit Tests
- Decorator tests (org_required, login_required)
- Helper function tests
- Model method tests
- ~20-30 unit tests

### Step 3: Write Integration Tests
- View tests (GET/POST)
- Template rendering tests
- Session tests
- File operation tests
- ~15-20 integration tests

### Step 4: Write System Tests
- Complete workflow tests
- Celery task tests
- Multi-user concurrent access
- ~5-10 system tests

### Step 5: Run All Tests
```bash
pytest -v --cov=core
```

### Step 6: Generate Coverage Report
```bash
pytest --cov=core --cov-report=html
```

---

## Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| Views | 0% | >80% |
| Models | 0% | >80% |
| Decorators | 0% | >95% |
| Tasks | 0% | >85% |
| **Overall** | **0%** | **>75%** |

---

## Key Test Scenarios

### Scenario 1: Login & Access Control
```
1. Anonymous user tries to access /datas/
   → Redirect to login
2. User logs in successfully
   → Redirect to dashboard
3. User logs out
   → Session cleared
4. User tries to access protected view
   → Redirect to login
```

### Scenario 2: Multi-Tenancy Isolation
```
1. User A and User B have different organizations
2. User A creates a project
3. User B tries to access User A's project
   → 403 Forbidden
4. User A can see their own project
5. User B cannot see User A's project in list
```

### Scenario 3: Output Generation Workflow
```
1. User selects items from electrical category
2. User generates output (async job)
3. Job enqueued to Celery → status=QUEUED
4. Celery worker picks up job → status=RUNNING
5. Task generates Excel file
6. OutputFile created → status=COMPLETED
7. User polls job status → gets file_id
8. User downloads file via signed URL
```

### Scenario 4: Error Handling
```
1. User uploads invalid file → 400 Bad Request
2. User accesses non-existent project → 404 Not Found
3. User from Org A accesses Org B data → 403 Forbidden
4. Database error during generation → 500 Server Error
5. Celery task fails → Job.status=FAILED + error_log
```

---

## Test Dependencies

### Required Packages (Already Installed)
- pytest
- pytest-django
- pytest-cov
- factory-boy (for test factories)

### Configuration

**pytest.ini:**
```ini
[pytest]
DJANGO_SETTINGS_MODULE = estimate_site.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov=core --cov-report=term-missing
```

**settings.py (test mode):**
```python
if 'test' in sys.argv:
    # Use in-memory SQLite for tests
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    # Disable Celery for unit tests (use eager mode)
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
```

---

## Expected Issues & Mitigations

### Issue 1: Celery Task Testing
**Problem:** Celery tasks need Redis/RabbitMQ  
**Mitigation:** Use CELERY_TASK_ALWAYS_EAGER = True in tests

### Issue 2: File I/O in Tests
**Problem:** Creating/deleting real files slow  
**Mitigation:** Use in-memory BytesIO for testing

### Issue 3: Multi-User Concurrency
**Problem:** Race conditions hard to test  
**Mitigation:** Use database transactions + explicit commit points

### Issue 4: Excel Generation Performance
**Problem:** Generating large Excel files slow  
**Mitigation:** Use small test datasets with limited items

---

## Success Criteria

### All Tests Pass ✅
- [ ] 0 failing tests
- [ ] 0 errors
- [ ] All assertions pass

### Code Coverage ✅
- [ ] Views: >80%
- [ ] Models: >80%
- [ ] Overall: >75%

### Multi-Tenancy ✅
- [ ] User isolation verified
- [ ] No data leakage between orgs
- [ ] Org filtering applied everywhere

### Performance ✅
- [ ] All tests complete in <5 minutes
- [ ] No N+1 queries detected
- [ ] Celery tasks execute correctly

---

## Post-Testing Actions

### If Tests Pass ✅
1. Document test results
2. Create PHASE_6_COMPLETE.md
3. Generate coverage report
4. Prepare for Phase 7 (Staging Deployment)

### If Tests Fail ❌
1. Debug failures
2. Fix implementation
3. Re-run tests
4. Verify all pass before moving forward

---

## Phase 6 Timeline

| Step | Time | Task |
|------|------|------|
| 1 | 20 min | Set up test infrastructure |
| 2 | 30 min | Write unit tests |
| 3 | 30 min | Write integration tests |
| 4 | 20 min | Write system tests |
| 5 | 10 min | Run all tests |
| 6 | 10 min | Generate coverage report |
| 7 | 10 min | Document results |
| **TOTAL** | **130 min** | **~2 hours** |

---

## Next Steps

**Ready to proceed with Phase 6 Testing?**

YES → Start Step 1: Set up test infrastructure (pytest fixtures, factories)

---

**Phase 6 Objective:**
Validate all Phases 1-5 with comprehensive testing to ensure:
- ✅ Multi-tenant isolation working
- ✅ All views properly authenticated
- ✅ Async workflows functioning
- ✅ No security vulnerabilities
- ✅ Ready for production staging deployment
