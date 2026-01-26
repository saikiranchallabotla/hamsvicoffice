# User Data Storage Analysis - Commercialization Roadmap

## Current State: ❌ NO USER AUTHENTICATION OR PERSISTENT USER DATA

### What's Currently Being Stored:
1. **Session-Only Data** (expires when browser closes):
   - `ws_estimate_rows` - workslip rows
   - `ws_exec_map` - execution mapping
   - `ws_tp_percent` - transport percentage
   - `ws_supp_items` - supplementary items
   - `ws_estimate_grand_total` - total amount
   - `ws_work_name` - work name

2. **Database Models** (Project, SelfFormattedTemplate, BackendWorkbook):
   - ❌ NO USER ASSOCIATION
   - ❌ NO TIMESTAMPS FOR USER AUDIT
   - ❌ NO ACCESS CONTROL
   - Projects are stored globally without ownership
   - Anyone accessing the app can see/edit all projects

3. **File Uploads**:
   - `media/self_formatted/` - uploaded files with no user tracking
   - No deletion mechanism
   - No file quota or usage limits

4. **Django Setup**:
   - `DEBUG = True` (insecure for production)
   - `SECRET_KEY` exposed in code
   - `ALLOWED_HOSTS = ['*']` (accepts any domain)
   - No custom User model
   - No authentication required for views

---

## Critical Changes Needed for Commercialization

### Priority 1: User Authentication & Authorization (HIGH)
- [ ] Implement user login/registration system
- [ ] Add `ForeignKey(User)` to all user-related models
- [ ] Create user profile model (company name, subscription tier, etc.)
- [ ] Add login_required decorators to all views
- [ ] Implement role-based access control (admin, manager, user)
- [ ] Session timeout for security

### Priority 2: Data Persistence (HIGH)
- [ ] Move session data to database models
- [ ] Create `Estimate` or `Bill` model with user association
- [ ] Add soft-delete for audit trails
- [ ] Create `WorkslipInstance` model to save user's workslips
- [ ] Implement save/load functionality

### Priority 3: Security (HIGH)
- [ ] Remove exposed `SECRET_KEY` - use environment variables
- [ ] Set `DEBUG = False` in production
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Enable HTTPS/SSL
- [ ] Add CSRF protection validation
- [ ] Implement rate limiting on API endpoints

### Priority 4: Usage Tracking (MEDIUM)
- [ ] Add `created_at`, `updated_at` to all models
- [ ] Track who created/modified each estimate
- [ ] Log user actions for audit
- [ ] Implement usage analytics

### Priority 5: Subscription/Billing (MEDIUM)
- [ ] Create `Subscription` model
- [ ] Track user tier (free, pro, enterprise)
- [ ] Implement feature limits per tier
- [ ] Add usage quotas (estimates per month, file storage, etc.)

### Priority 6: Data Privacy (MEDIUM)
- [ ] Implement GDPR compliance (data export, deletion)
- [ ] Add privacy policy
- [ ] Create data retention policies
- [ ] Encrypt sensitive data
- [ ] Implement proper database backups

---

## Database Model Changes Required

### Add User Association to Models:
```python
class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # ADD THIS
    name = models.CharField(max_length=255)  # Remove unique=True
    category = models.CharField(max_length=50, null=True, blank=True)
    items_json = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ADD THIS
    
    class Meta:
        unique_together = ['user', 'name']  # Add this for user-specific uniqueness
```

### New Models to Create:
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    subscription_tier = models.CharField(max_length=20, choices=[...])
    created_at = models.DateTimeField(auto_now_add=True)

class Estimate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)
    work_name = models.CharField(max_length=255)
    estimate_data = models.JSONField()  # Store all workslip data
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## Estimated Effort

| Phase | Tasks | Effort | Priority |
|-------|-------|--------|----------|
| Auth System | Login/Register/Profile | 40-60 hrs | P1 |
| Data Models | Update models + migrations | 30-40 hrs | P1 |
| Views & Permissions | Add login_required + authorization | 50-70 hrs | P1 |
| Database Schema | Backfill user data | 20-30 hrs | P1 |
| Security Hardening | Environment vars, HTTPS, etc. | 30-40 hrs | P1 |
| Subscription System | Pricing tiers, limits | 40-60 hrs | P2 |
| Testing | Auth tests, permission tests | 30-40 hrs | P1 |
| **TOTAL** | | **240-340 hours** | |

---

## Recommendation

**Do NOT sell this product in current state.** It's currently:
- A shared, multi-tenant system with zero isolation
- Session-based (data lost on logout)
- No user tracking or billing
- Security risks for production

**Start with Phase 1 (Auth + Models)** - this is 100-140 hours and creates the foundation for everything else.

