# PHASE_3_PROGRESS.md

## Phase 3: View Refactoring - Progress Tracking

**Overall Status:** Phase 3a COMPLETE, Phase 3b STARTING

---

## Progress Summary

| Phase | Task | Status | Completion |
|-------|------|--------|------------|
| **3a** | ✅ Auth Views Refactoring | COMPLETE | 100% |
| **3b** | Core View Helpers | 🔄 IN PROGRESS | 0% |
| **3c** | Excel Processing Views | PENDING | 0% |
| **3d** | Project Management Views | PENDING | 0% |
| **3e** | Category/Item Views | PENDING | 0% |
| **3f** | Output/Download Views | PENDING | 0% |
| **3g** | Templates & UI | PENDING | 0% |
| | | | |
| **TOTAL** | | **14% (1/7)** | |

---

## Phase 3a: Auth Views - COMPLETE ✅

**Files Modified:** core/auth_views.py
**Changes:** ~150 lines
**Time Spent:** 1.5 hours
**Status:** Ready for Phase 3b

### What Was Done
- ✅ Added @org_required decorator to 6 protected views
- ✅ Integrated signals for auto-org creation
- ✅ Filtered all queries by organization
- ✅ Updated dashboard to show org context
- ✅ Org-scoped estimates, projects, profile
- ✅ Syntax validated

### View Changes Summary
```
register()           → Auto-org via signals
login_view()         → No changes
logout_view()        → No changes
dashboard()          → @org_required, org-scoped
profile_view()       → @org_required, org-scoped
my_estimates()       → @org_required, org-scoped
view_estimate()      → @org_required, org-scoped
delete_estimate()    → @org_required, org-scoped
save_estimate()      → @org_required, org-scoped
```

### Security Improvements
- Organization isolation enforced at view level
- Decorator requires org membership
- All queries filtered by organization
- 404 for cross-org access attempts

---

## Phase 3b: Core View Helpers - STARTING NOW

**Goal:** Add imports, helpers, and prepare views.py for refactoring

**Timeline:** 2-3 hours

**Files to Modify:**
- core/views.py (~7989 lines)

**Tasks:**
1. Add imports at top
   - `from .decorators import org_required, role_required`
   - `from .tasks import process_excel_upload, generate_bill_pdf, generate_workslip_pdf`
   - `from .models import Organization, Membership, Upload, Job, OutputFile`

2. Create helper functions
   - `get_org_from_request(request)` - Safe org extraction
   - `enqueue_excel_task(job_id, task_name)` - Wrapper for Celery tasks
   - `check_org_access(user, org)` - Verify org membership

3. Update imports in views
   - Add org models to imports
   - Add task imports
   - Add decorator imports

4. Prepare Excel processing functions
   - Review bill_document(), self_formatted_document()
   - Identify Excel generation blocks
   - Mark for task extraction

---

## Phase 3c: Excel Processing - PLANNED

**Goal:** Replace in-request Excel with async tasks

**Key Views to Refactor:**
- bill_document() → Enqueue generate_bill_pdf task
- self_formatted_document() → Enqueue task
- estimate() → Show job status instead of file
- bill() → Use job processing
- workslip() → Use job processing

**Expected Changes:**
- Remove inline Excel generation
- Create Upload + Job + Task
- Return job status URL instead of file
- ~400-500 lines of code changes

---

## Phase 3d: Project Views - PLANNED

**Goal:** Add org scoping to project management

**Key Views to Refactor:**
- my_projects() → Filter by org
- create_project() → Create with org FK
- load_project() → Org check
- delete_project() → Org check
- save_project() → Org check
- new_project() → Create in org

**Expected Changes:**
- Add @org_required to all
- Filter Project queries by org
- ~100-150 lines of code changes

---

## Phase 3e: Category/Item Views - PLANNED

**Goal:** Add org scoping to data navigation

**Key Views:**
- datas() → Org filter
- datas_groups() → Org filter
- datas_items() → Org filter
- fetch_item() → Org check
- select_project() → Org filter
- choose_category() → Org filter

**Expected Changes:**
- Add org context to all
- Filter by org where needed
- ~100 lines of code changes

---

## Phase 3f: Output/Download - PLANNED

**Goal:** Use OutputFile model and signed URLs

**Key Views:**
- output_panel() → Show OutputFile records
- download_output() → Use signed URLs
- clear_output() → Clean OutputFiles

**Expected Changes:**
- Replace direct file responses
- Use OutputFile + signed URLs
- Track downloads
- ~80-100 lines of code changes

---

## Phase 3g: Templates - PLANNED

**Goal:** Add job status polling and progress UI

**Files to Create/Modify:**
- job_status.html (new) - Poll job progress
- bill.html (update) - Show job status
- estimate.html (update) - Show job status
- self_formatted.html (update) - Show job status
- my_projects.html (update) - Add org context
- output.html (update) - Link to OutputFiles

**Expected Changes:**
- JavaScript for polling /api/jobs/{id}/status/
- Progress bars
- Download links
- ~200-300 lines of HTML/JS

---

## Summary Table

| Phase | Scope | Files | Lines | Hours | Status |
|-------|-------|-------|-------|-------|--------|
| 3a | Auth views | 1 | ~150 | 1.5 | ✅ DONE |
| 3b | Helpers | 1 | ~100 | 2 | 🔄 NEXT |
| 3c | Excel tasks | 1 | ~400-500 | 4-5 | ⏳ PLANNED |
| 3d | Projects | 1 | ~100-150 | 2-3 | ⏳ PLANNED |
| 3e | Categories | 1 | ~100 | 2 | ⏳ PLANNED |
| 3f | Downloads | 1 | ~80-100 | 1-2 | ⏳ PLANNED |
| 3g | Templates | 6 | ~200-300 | 2-3 | ⏳ PLANNED |
| | **TOTAL** | **~8** | **~1,130-1,400** | **14-18** | |

---

## Key Metrics

### Completion
- **Phase 3a:** 100% ✅
- **Phase 3b:** 0% (starting now)
- **Phase 3c-g:** 0% (planned)
- **Overall Phase 3:** 14% (1/7 sub-phases)

### Code Quality
- ✅ All new code passes syntax validation
- ✅ Decorators applied correctly
- ✅ Organization isolation enforced
- ✅ Backward compatible (Phase 1/2 work preserved)

### Next Immediate Actions
1. Start Phase 3b: Add imports to views.py
2. Create helper functions
3. Prepare major views for refactoring
4. Verify no import errors

---

## Risk Tracking

| Risk | Severity | Mitigation |
|------|----------|-----------|
| views.py is large (7989 lines) | HIGH | Refactor incrementally, test after each |
| Breaking existing functionality | HIGH | Thorough testing, keep old views as fallback |
| User experience impact | MEDIUM | Async transitions hidden from UI (show spinner) |
| Celery not running | MEDIUM | Graceful fallback, error messages |
| Database migration issues | MEDIUM | Test with fresh db first |

---

## Success Criteria for Phase 3

### Code Quality
- [ ] All views have @org_required or are intentionally public
- [ ] All queries filtered by organization
- [ ] No direct user-scoped queries (except UserProfile)
- [ ] All Excel generation uses Celery tasks
- [ ] Syntax valid for all files

### Functionality
- [ ] Users see only their org's data
- [ ] Cannot access other org's projects/estimates
- [ ] Excel generation works async
- [ ] Job status polling works
- [ ] Downloads use signed URLs
- [ ] Output files tracked

### Testing
- [ ] Manual tests pass (register, login, create estimate, etc.)
- [ ] Cross-org access prevention verified
- [ ] Task execution verified
- [ ] No syntax/import errors

### Documentation
- [ ] Each sub-phase has completion document
- [ ] Code changes well-commented
- [ ] Examples provided
- [ ] Testing notes included

---

## Rollback Plan

If critical issues arise:
1. Revert specific sub-phase only (doesn't affect others)
2. Keep Phase 1/2 infrastructure intact
3. Old views can coexist with new (use feature flags)
4. Database rollback via migrations (Phase 1 already created)

---

## Next Steps

**Immediate (Now):** Start Phase 3b
- Read views.py structure
- Add imports
- Create helpers
- No view logic changes yet

**Short Term (Next 2-3 hours):** Phase 3b completion
- All imports ready
- Helper functions defined
- views.py prepared for major refactoring

**Medium Term (Next 4-5 hours):** Phase 3c (Excel async)
- Major Excel-processing views refactored
- Tasks integrated
- Job status working

**Long Term:** Phase 3d-g
- All remaining views refactored
- Templates updated
- Full Phase 3 completion

---

## Resources

- Implementation Plan: PHASE_3_IMPLEMENTATION_PLAN.md
- Phase 3a Details: PHASE_3A_COMPLETE.md
- Decorators Reference: core/decorators.py
- Managers Reference: core/managers.py
- Phase 2 Docs: PHASE_2_INTEGRATION_GUIDE.md

