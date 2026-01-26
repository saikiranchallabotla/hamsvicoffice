# SSR Estimation - SaaS Architecture Blueprint

## Executive Summary

Transform the multi-module Django engineering webapp into a production-grade SaaS with:
- OTP-first authentication
- Module-wise subscriptions with Razorpay
- Powerful admin control panel
- Modern Bootstrap 5 UI
- Scalability for 1000+ users

---

## 1. SCREEN LIST & NAVIGATION FLOW

### 1.1 Public Pages (Unauthenticated)
```
/                       → Landing page (hero, features, pricing preview)
/pricing/               → Public pricing page
/accounts/login/        → Phone/Email + OTP login
/accounts/register/     → Registration form
/accounts/verify-otp/   → OTP verification
/help/                  → Public help center
/terms/                 → Terms of service
/privacy/               → Privacy policy
```

### 1.2 User Dashboard (Authenticated)
```
/dashboard/             → Main dashboard (module cards, subscription status)
├── /modules/
│   ├── /estimate/      → Estimate module
│   ├── /workslip/      → Workslip module
│   ├── /bill/          → Bill module
│   └── /self-formatted/→ Self-formatted templates
├── /my-subscription/   → Current subscriptions, usage, renew/cancel
├── /payments/          → Payment history, invoices
├── /profile/           → Profile settings
│   ├── /profile/edit/  → Edit profile
│   ├── /profile/phone/ → Change phone (OTP verify)
│   ├── /profile/email/ → Change email (OTP verify)
│   └── /profile/sessions/ → Active sessions
├── /settings/          → Notification prefs, export data, delete account
└── /support/           → My tickets, new ticket
```

### 1.3 Admin Panel (`/admin-panel/`)
```
/admin-panel/                   → Admin dashboard (stats, charts)
├── /admin-panel/users/         → User management
│   ├── /admin-panel/users/<id>/→ User detail + subscriptions
│   └── /admin-panel/users/<id>/grant-access/ → Manual access grant
├── /admin-panel/modules/       → Module management
│   └── /admin-panel/modules/<id>/pricing/ → Edit pricing
├── /admin-panel/subscriptions/ → All subscriptions
├── /admin-panel/payments/      → Payment transactions
├── /admin-panel/coupons/       → Coupon management
├── /admin-panel/datasets/      → Master data management
│   ├── /admin-panel/datasets/<id>/upload/ → Upload Excel/CSV
│   ├── /admin-panel/datasets/<id>/versions/ → Version history
│   └── /admin-panel/datasets/<id>/rollback/<v>/ → Rollback
├── /admin-panel/tickets/       → Support tickets
├── /admin-panel/announcements/ → Announcements
└── /admin-panel/audit-log/     → Audit trail
```

### 1.4 Navigation Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         LANDING PAGE                            │
│                    [Login] [Register] [Pricing]                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOGIN (Phone/Email)                        │
│                         Enter OTP                               │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│     NEW USER?           │     │    EXISTING USER        │
│  Complete Profile Form  │     │                         │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DASHBOARD                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │Estimate │ │Workslip │ │  Bill   │ │  Self   │              │
│  │ Active  │ │ Locked  │ │ Expired │ │Formatted│              │
│  │ [Open]  │ │[Subscribe]│ [Renew] │ │ [Open]  │              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
│                                                                 │
│  ┌─ Sidebar ─────────────────────────────────────────────────┐ │
│  │ Dashboard                                                  │ │
│  │ My Subscription                                            │ │
│  │ Payment History                                            │ │
│  │ Profile & Settings                                         │ │
│  │ Help & Support                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. DATABASE SCHEMA

### 2.1 Complete Model Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ACCOUNTS APP                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐       │
│  │     User     │──────│   UserProfile    │      │   UserSession    │       │
│  │   (Django)   │ 1:1  │                  │      │                  │       │
│  └──────────────┘      │ phone            │      │ user (FK)        │       │
│         │              │ phone_verified   │      │ session_key      │       │
│         │              │ company_name     │      │ ip_address       │       │
│         │              │ gstin            │      │ device_type      │       │
│         │              │ address          │      │ user_agent       │       │
│         │              │ role             │      │ last_activity    │       │
│         │              │ avatar           │      │ is_active        │       │
│         │              └──────────────────┘      └──────────────────┘       │
│         │                                                                    │
│  ┌──────────────────┐      ┌──────────────────┐                             │
│  │    OTPToken      │      │   OTPRateLimit   │                             │
│  │                  │      │                  │                             │
│  │ identifier       │      │ identifier       │                             │
│  │ otp_hash         │      │ hourly_count     │                             │
│  │ channel          │      │ daily_count      │                             │
│  │ purpose          │      │ locked_until     │                             │
│  │ attempts         │      │ last_request_at  │                             │
│  │ expires_at       │      └──────────────────┘                             │
│  └──────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           SUBSCRIPTIONS APP                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐       │
│  │    Module    │──────│  ModulePricing   │      │     Coupon       │       │
│  │              │ 1:N  │                  │      │                  │       │
│  │ code         │      │ module (FK)      │      │ code             │       │
│  │ name         │      │ duration_months  │      │ discount_type    │       │
│  │ description  │      │ base_price       │      │ discount_value   │       │
│  │ icon         │      │ sale_price       │      │ valid_until      │       │
│  │ features     │      │ gst_percent      │      │ usage_limit      │       │
│  │ is_active    │      │ usage_limit      │      │ times_used       │       │
│  │ trial_days   │      └──────────────────┘      └──────────────────┘       │
│  │ display_order│                                                            │
│  └──────────────┘                                                            │
│         │                                                                    │
│         │ N:1                                                                │
│         ▼                                                                    │
│  ┌────────────────────────┐         ┌──────────────────────────────┐        │
│  │ UserModuleSubscription │─────────│          Payment             │        │
│  │                        │ N:1     │                              │        │
│  │ user (FK)              │         │ order_id (unique)            │        │
│  │ module (FK)            │         │ user (FK)                    │        │
│  │ pricing (FK)           │         │ gateway_order_id             │        │
│  │ status                 │         │ gateway_payment_id           │        │
│  │ started_at             │         │ subtotal                     │        │
│  │ expires_at             │         │ discount_amount              │        │
│  │ cancelled_at           │         │ gst_amount                   │        │
│  │ cancel_at_period_end   │         │ total_amount                 │        │
│  │ usage_count            │         │ status                       │        │
│  │ usage_limit            │         │ pricing_snapshot (JSON)      │        │
│  │ auto_renew             │         │ coupon (FK, nullable)        │        │
│  │ payment (FK)           │         │ billing_name/email/gstin     │        │
│  └────────────────────────┘         └──────────────────────────────┘        │
│                                              │                               │
│                                              │ 1:1                           │
│                                              ▼                               │
│                                     ┌──────────────────┐                    │
│                                     │     Invoice      │                    │
│                                     │                  │                    │
│                                     │ invoice_number   │                    │
│                                     │ payment (FK)     │                    │
│                                     │ user (FK)        │                    │
│                                     │ line_items (JSON)│                    │
│                                     │ cgst/sgst/igst   │                    │
│                                     │ total_amount     │                    │
│                                     │ pdf_file         │                    │
│                                     └──────────────────┘                    │
│                                                                              │
│  ┌──────────────────────────┐      ┌──────────────────────────┐             │
│  │   ModuleAccessOverride   │      │        UsageLog          │             │
│  │                          │      │                          │             │
│  │ user (FK)                │      │ user (FK)                │             │
│  │ module (FK)              │      │ module_code              │             │
│  │ access_type (grant/revoke│      │ action                   │             │
│  │ reason                   │      │ resource_id              │             │
│  │ granted_by (FK)          │      │ metadata (JSON)          │             │
│  │ valid_until              │      │ ip_address               │             │
│  │ created_at               │      │ created_at               │             │
│  └──────────────────────────┘      └──────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                             DATASETS APP                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐   │
│  │ DatasetCategory  │──────│     Dataset      │──────│  DatasetVersion  │   │
│  │                  │ 1:N  │                  │ 1:N  │                  │   │
│  │ name             │      │ category (FK)    │      │ dataset (FK)     │   │
│  │ slug             │      │ name             │      │ version          │   │
│  │ description      │      │ slug             │      │ data (JSON)      │   │
│  └──────────────────┘      │ description      │      │ row_count        │   │
│                            │ schema (JSON)    │      │ is_published     │   │
│                            │ current_version  │      │ published_at     │   │
│                            │ row_count        │      │ published_by     │   │
│                            │ is_active        │      │ import_job (FK)  │   │
│                            └──────────────────┘      │ changelog        │   │
│                                     │                └──────────────────┘   │
│                                     │ 1:N                                    │
│                                     ▼                                        │
│                            ┌──────────────────┐                             │
│                            │ DatasetImportJob │                             │
│                            │                  │                             │
│                            │ dataset (FK)     │                             │
│                            │ file_name        │                             │
│                            │ status           │                             │
│                            │ total_rows       │                             │
│                            │ valid_rows       │                             │
│                            │ error_count      │                             │
│                            │ errors_json      │                             │
│                            │ parsed_data      │                             │
│                            │ initiated_by     │                             │
│                            │ is_dry_run       │                             │
│                            │ completed_at     │                             │
│                            └──────────────────┘                             │
│                                                                              │
│  ┌──────────────────────────┐                                               │
│  │       AuditLog           │                                               │
│  │                          │                                               │
│  │ user (FK)                │                                               │
│  │ action                   │                                               │
│  │ model_name               │                                               │
│  │ object_id                │                                               │
│  │ changes (JSON)           │                                               │
│  │ ip_address               │                                               │
│  │ created_at               │                                               │
│  └──────────────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUPPORT APP                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐      ┌──────────────────┐                             │
│  │   FAQCategory    │──────│     FAQItem      │                             │
│  │                  │ 1:N  │                  │                             │
│  │ name             │      │ category (FK)    │                             │
│  │ slug             │      │ question         │                             │
│  │ order            │      │ answer           │                             │
│  └──────────────────┘      │ is_published     │                             │
│                            │ helpful_count    │                             │
│                            └──────────────────┘                             │
│                                                                              │
│  ┌──────────────────┐      ┌──────────────────┐                             │
│  │   HelpGuide      │      │  SupportTicket   │──────┐                      │
│  │                  │      │                  │ 1:N  │                      │
│  │ module (FK,null) │      │ user (FK)        │      ▼                      │
│  │ title            │      │ subject          │ ┌──────────────────┐        │
│  │ content (rich)   │      │ category         │ │  TicketMessage   │        │
│  │ video_url        │      │ status           │ │                  │        │
│  │ order            │      │ priority         │ │ ticket (FK)      │        │
│  │ is_published     │      │ assigned_to      │ │ sender (FK)      │        │
│  └──────────────────┘      │ created_at       │ │ message          │        │
│                            │ resolved_at      │ │ attachments      │        │
│                            └──────────────────┘ │ is_admin_reply   │        │
│                                                  │ created_at       │        │
│  ┌──────────────────┐                           └──────────────────┘        │
│  │   Announcement   │                                                        │
│  │                  │                                                        │
│  │ title            │                                                        │
│  │ content          │                                                        │
│  │ type (info/warn) │                                                        │
│  │ is_active        │                                                        │
│  │ show_from        │                                                        │
│  │ show_until       │                                                        │
│  │ target_modules   │                                                        │
│  └──────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Indexes

```python
# accounts/models.py
class UserProfile(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
        ]

# subscriptions/models.py
class UserModuleSubscription(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', 'module']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = ['user', 'module']

class Payment(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway_order_id']),
            models.Index(fields=['created_at']),
        ]
```

---

## 3. APIs / ENDPOINTS

### 3.1 Authentication (`/accounts/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET/POST | `/accounts/login/` | Login page |
| GET/POST | `/accounts/register/` | Registration |
| GET/POST | `/accounts/verify-otp/` | OTP verification |
| POST | `/accounts/resend-otp/` | Resend OTP (AJAX) |
| POST | `/accounts/logout/` | Logout current session |
| POST | `/accounts/logout-all/` | Logout all devices |
| GET | `/accounts/sessions/` | Active sessions |
| POST | `/accounts/sessions/<id>/revoke/` | Revoke session |

### 3.2 Auth API (`/api/auth/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/auth/request-otp/` | Request OTP (JSON) |
| POST | `/api/auth/verify-otp/` | Verify OTP (JSON) |
| POST | `/api/auth/logout/` | Logout (JSON) |
| GET | `/api/auth/me/` | Current user info |

### 3.3 Profile & Settings (`/profile/`, `/settings/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET/POST | `/profile/` | View/edit profile |
| GET/POST | `/profile/change-phone/` | Change phone + OTP |
| GET/POST | `/profile/change-email/` | Change email + OTP |
| POST | `/settings/export-data/` | Export my data (background job) |
| POST | `/settings/delete-account/` | Request account deletion |
| GET/POST | `/settings/notifications/` | Notification preferences |

### 3.4 Subscriptions (`/subscriptions/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/subscriptions/` | My subscriptions |
| GET | `/pricing/` | Pricing page |
| POST | `/subscriptions/checkout/` | Create payment order |
| POST | `/subscriptions/verify-payment/` | Verify & activate |
| POST | `/subscriptions/<id>/cancel/` | Cancel subscription |
| POST | `/subscriptions/<id>/toggle-renew/` | Toggle auto-renew |
| GET | `/payments/` | Payment history |
| GET | `/payments/<id>/invoice/` | Download invoice PDF |

### 3.5 Payment Webhooks

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/webhooks/razorpay/` | Razorpay webhook handler |

### 3.6 Support (`/support/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/help/` | Help center |
| GET | `/help/module/<code>/` | Module-specific help |
| GET | `/help/faq/` | FAQ list |
| GET/POST | `/support/tickets/` | My tickets / New ticket |
| GET/POST | `/support/tickets/<id>/` | Ticket detail / Reply |

### 3.7 Admin Panel (`/admin-panel/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin-panel/` | Dashboard stats |
| GET/POST | `/admin-panel/users/` | User list |
| GET/POST | `/admin-panel/users/<id>/` | User detail |
| POST | `/admin-panel/users/<id>/grant-access/` | Manual grant |
| POST | `/admin-panel/users/<id>/revoke-access/` | Manual revoke |
| GET/POST | `/admin-panel/modules/` | Module list |
| GET/POST | `/admin-panel/modules/<id>/pricing/` | Edit pricing |
| GET | `/admin-panel/subscriptions/` | All subscriptions |
| GET | `/admin-panel/payments/` | All payments |
| GET/POST | `/admin-panel/coupons/` | Coupon management |
| GET | `/admin-panel/datasets/` | Dataset list |
| POST | `/admin-panel/datasets/<id>/upload/` | Upload file |
| POST | `/admin-panel/datasets/<id>/publish/<job>/` | Publish version |
| POST | `/admin-panel/datasets/<id>/rollback/<v>/` | Rollback |
| GET | `/admin-panel/tickets/` | All tickets |
| GET/POST | `/admin-panel/tickets/<id>/` | Ticket reply |
| GET/POST | `/admin-panel/announcements/` | Announcements |
| GET | `/admin-panel/audit-log/` | Audit trail |

---

## 4. SERVICES ARCHITECTURE

### 4.1 Service Layer Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              VIEWS LAYER                                 │
│                    (Template views + API views)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            SERVICE LAYER                                 │
├────────────────┬────────────────┬────────────────┬─────────────────────┤
│                │                │                │                      │
│   OTPService   │ PaymentService │ Subscription   │ DatasetImport       │
│                │                │    Service     │    Service          │
│ • request_otp  │ • create_order │ • check_access │ • start_import      │
│ • verify_otp   │ • handle_webhook│ • start_sub   │ • validate          │
│ • resend_otp   │ • mark_success │ • renew        │ • parse_rows        │
│ • rate_limit   │ • mark_failed  │ • cancel       │ • publish_version   │
│                │ • refund       │ • sync_payment │ • rollback          │
└────────────────┴────────────────┴────────────────┴─────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            ACCESS CONTROL                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   can_access_module(user, module_slug) → (allowed, reason)              │
│   @require_module_access("module_slug")                                  │
│   ModuleAccessMiddleware                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              MODEL LAYER                                 │
│               (Django ORM with PostgreSQL + Indexes)                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          INFRASTRUCTURE                                  │
├────────────────┬────────────────┬────────────────┬─────────────────────┤
│    Redis       │   PostgreSQL   │      S3        │      Celery         │
│ • OTP storage  │ • Main DB      │ • File storage │ • Background jobs   │
│ • Rate limits  │ • Transactions │ • Invoices     │ • Expiry cron       │
│ • Cache        │ • Full-text    │ • Uploads      │ • Usage reset       │
│ • Sessions     │   search       │ • Backups      │ • Email queue       │
└────────────────┴────────────────┴────────────────┴─────────────────────┘
```

### 4.2 Service Files (Already Created)

| Service | Location | Purpose |
|---------|----------|---------|
| `OTPService` | `accounts/services/otp_service.py` | OTP generation, verification, rate limiting |
| `PaymentService` | `subscriptions/services/payment_service.py` | Razorpay integration, webhooks, invoices |
| `SubscriptionService` | `subscriptions/services/subscription_service.py` | Access control, lifecycle, usage tracking |
| `DatasetImportService` | `datasets/services/import_service.py` | Excel/CSV import, validation, versioning |

### 4.3 Access Control (Already Created)

| File | Purpose |
|------|---------|
| `subscriptions/access_control.py` | `can_access_module()`, `@require_module_access` |
| `subscriptions/middleware.py` | `ModuleAccessMiddleware`, `SubscriptionCacheMiddleware` |
| `subscriptions/decorators.py` | View decorators for access enforcement |

---

## 5. EDGE CASES CHECKLIST

### 5.1 Authentication

| Edge Case | Handling |
|-----------|----------|
| OTP expires before verification | Show "OTP expired" + auto-show resend button |
| User enters wrong OTP 5 times | Lock for 30 minutes, show countdown |
| User requests too many OTPs/hour | Rate limit (10/hour), show retry time |
| Session expires during form fill | Preserve form data, show login modal |
| Login from new device | Create new UserSession, notify via email |
| Concurrent logins from 10+ devices | Allow (track all), offer "logout all" |

### 5.2 Subscriptions

| Edge Case | Handling |
|-----------|----------|
| Subscription expires mid-task | Allow task completion, block new tasks |
| Payment fails after order created | Mark payment failed, don't activate |
| Double webhook delivery | Idempotent handling (event ID dedup) |
| User cancels then resubscribes | Create new subscription, reset usage |
| Upgrade during active period | Prorate or apply at renewal (configurable) |
| Admin grants access to banned user | Check user status first |
| Coupon used beyond limit | Validate at checkout, reject gracefully |

### 5.3 Dataset Imports

| Edge Case | Handling |
|-----------|----------|
| Excel has 100k rows | Process in chunks, show progress |
| Invalid characters in CSV | Detect encoding, try UTF-8/Latin-1 |
| Schema mismatch | Validate against dataset.schema, show errors |
| Import fails at row 5000 | Transaction rollback, show failed row |
| Two admins import simultaneously | Lock dataset during import |
| Rollback to version with deleted columns | Warn admin, require confirmation |

### 5.4 Concurrent Access

| Edge Case | Handling |
|-----------|----------|
| Race condition on usage count | Use F() expressions for atomic update |
| Two users save same project | Last write wins (or implement locking) |
| Admin disables module during use | Show "Module disabled" on next action |
| Price change during checkout | Use pricing_snapshot in Payment |

### 5.5 Security

| Edge Case | Handling |
|-----------|----------|
| CSRF token expired | Show message, auto-refresh token |
| API called without session | Return 401, redirect to login |
| Admin tries to access another org | Check org membership in view |
| File upload with malicious content | Validate file type, scan if possible |
| SQL injection attempts | Django ORM (parameterized queries) |
| XSS in support ticket | Sanitize HTML, escape output |

---

## 6. PHASED IMPLEMENTATION PLAN

### Phase 1: Core Auth & Profile (Week 1-2)
**Goal**: OTP login working, profile management

- [x] Create accounts app models
- [x] Create OTPService
- [x] Create auth views + templates
- [x] Create session tracking middleware
- [ ] Profile view + edit forms
- [ ] Change phone/email with OTP
- [ ] Active sessions management
- [ ] Basic responsive layout (Bootstrap 5)

**Deliverable**: Users can register, login via OTP, manage profile

### Phase 2: Subscriptions & Access Control (Week 3-4)
**Goal**: Module access enforcement, subscription management

- [x] Create subscriptions app models
- [x] Create SubscriptionService
- [x] Create PaymentService
- [x] Create access control utilities
- [x] Create middleware
- [ ] Pricing page (public)
- [ ] Checkout flow (Razorpay integration)
- [ ] My Subscriptions page
- [ ] Payment history + invoice download
- [ ] Trial activation flow

**Deliverable**: Users can subscribe, pay, access modules

### Phase 3: Admin Panel - User & Subscription Management (Week 5-6)
**Goal**: Admin can manage users and subscriptions

- [ ] Admin panel base layout
- [ ] Dashboard with stats (users, revenue, active subs)
- [ ] User list (search, filter, paginate)
- [ ] User detail (subscriptions, payments, sessions)
- [ ] Manual grant/revoke access
- [ ] Subscription list
- [ ] Payment list
- [ ] Coupon management

**Deliverable**: Admin has visibility and control over users

### Phase 4: Admin Panel - Datasets & Master Data (Week 7-8)
**Goal**: Admin can upload and manage master data

- [x] Create datasets app models
- [x] Create DatasetImportService
- [ ] Dataset list view
- [ ] Upload Excel/CSV with dry-run preview
- [ ] Import job status page
- [ ] Version history + rollback UI
- [ ] Audit log view
- [ ] Module management (create/edit/pricing)

**Deliverable**: Admin can update master data safely

### Phase 5: Support System (Week 9)
**Goal**: Help center and ticket system

- [x] Create support app models
- [ ] FAQ management (admin)
- [ ] Help guides (admin)
- [ ] Public help center
- [ ] Module-specific help pages
- [ ] Ticket creation (user)
- [ ] Ticket list + detail
- [ ] Admin ticket management
- [ ] Announcement system

**Deliverable**: Users can get help, admins can respond

### Phase 6: UI Polish & UX (Week 10-11)
**Goal**: Modern, premium look and feel

- [ ] Component library (buttons, cards, tables, modals)
- [ ] Redesign login/register
- [ ] Redesign dashboard
- [ ] Redesign module pages
- [ ] Redesign pricing page
- [ ] Redesign admin panel
- [ ] Mobile responsive testing
- [ ] Loading states + skeleton screens
- [ ] Toast notifications
- [ ] Dark mode (optional)

**Deliverable**: Professional SaaS appearance

### Phase 7: Production Hardening (Week 12)
**Goal**: Ready for 1000 users

- [ ] PostgreSQL migration
- [ ] Redis setup (OTP, cache, sessions)
- [ ] Celery + beat setup
- [ ] S3/DO Spaces for files
- [ ] Error tracking (Sentry)
- [ ] Logging + monitoring
- [ ] Security audit
- [ ] Load testing
- [ ] Backup strategy
- [ ] Deployment documentation

**Deliverable**: Production-ready deployment

---

## 7. CODE SCAFFOLDING OUTLINE

### 7.1 App Structure

```
h:\AEE Punjagutta\Versions\Windows x 1\
├── estimate_site/                 # Project settings
│   ├── settings.py               # ✅ Updated
│   ├── urls.py                   # ✅ Updated
│   └── celery.py                 # TODO: Celery config
│
├── accounts/                      # ✅ Created
│   ├── models.py                 # UserProfile, OTPToken, UserSession
│   ├── views.py                  # ✅ Auth views
│   ├── urls.py                   # ✅ URL patterns
│   ├── middleware.py             # ✅ SessionTracking
│   ├── signals.py                # ✅ Profile creation
│   ├── forms.py                  # TODO: Profile forms
│   ├── services/
│   │   └── otp_service.py        # ✅ OTP logic
│   └── templates/accounts/
│       ├── auth_base.html        # ✅ Auth layout
│       ├── login.html            # ✅ Login page
│       ├── register.html         # ✅ Register page
│       ├── verify_otp.html       # ✅ OTP entry
│       └── sessions.html         # ✅ Active sessions
│
├── subscriptions/                 # ✅ Created
│   ├── models.py                 # Module, Pricing, Subscription, Payment
│   ├── views.py                  # TODO: Subscription views
│   ├── urls.py                   # TODO: URL patterns
│   ├── middleware.py             # ✅ Access control
│   ├── access_control.py         # ✅ can_access_module
│   ├── decorators.py             # ✅ @module_required
│   ├── services/
│   │   ├── payment_service.py    # ✅ Razorpay
│   │   └── subscription_service.py # ✅ Lifecycle
│   └── templates/subscriptions/
│       ├── pricing.html          # TODO
│       ├── checkout.html         # TODO
│       ├── my_subscriptions.html # TODO
│       └── payment_history.html  # TODO
│
├── datasets/                      # ✅ Created
│   ├── models.py                 # Dataset, Version, ImportJob
│   ├── views.py                  # TODO: Admin views
│   ├── services/
│   │   └── import_service.py     # ✅ Import logic
│   └── templates/datasets/       # TODO
│
├── support/                       # ✅ Created
│   ├── models.py                 # FAQ, Ticket, HelpGuide
│   ├── views.py                  # TODO: Support views
│   └── templates/support/        # TODO
│
├── admin_panel/                   # TODO: Create
│   ├── views.py                  # Admin views
│   ├── urls.py                   # Admin URLs
│   └── templates/admin_panel/
│       ├── base.html             # Admin layout
│       ├── dashboard.html
│       ├── users/
│       ├── modules/
│       ├── datasets/
│       └── tickets/
│
├── core/                          # Existing app
│   ├── views.py                  # Module views (estimate, workslip, etc.)
│   ├── middleware.py             # OrganizationMiddleware
│   └── templates/core/           # Module templates
│
└── templates/                     # Global templates
    ├── base.html                 # Main layout (sidebar + topbar)
    ├── components/
    │   ├── _sidebar.html
    │   ├── _topbar.html
    │   ├── _modal.html
    │   ├── _toast.html
    │   └── _pagination.html
    └── errors/
        ├── 403.html
        ├── 404.html
        └── 500.html
```

### 7.2 Settings Configuration

```python
# estimate_site/settings.py additions

# Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    }
}

# Session
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# OTP Settings
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300  # 5 minutes
OTP_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_LOCKOUT_MINUTES = 30
OTP_HOURLY_LIMIT = 10

# Payment Gateway
PAYMENT_GATEWAY = 'razorpay'
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')

# Module Access
MODULE_PROTECTED_URLS = {
    'estimate': [r'^/estimate/', r'^/datas/'],
    'workslip': [r'^/workslip/'],
    'bill': [r'^/bill/'],
    'self_formatted': [r'^/self-formatted/'],
}

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
```

### 7.3 Middleware Order

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middleware
    'core.middleware.OrganizationMiddleware',
    'accounts.middleware.SessionTrackingMiddleware',
    'subscriptions.middleware.SubscriptionCacheMiddleware',
    'subscriptions.middleware.ModuleAccessMiddleware',
    'subscriptions.middleware.UsageTrackingMiddleware',
]
```

### 7.4 URL Structure

```python
# estimate_site/urls.py
from django.urls import path, include

urlpatterns = [
    # Django admin (for superusers only)
    path('django-admin/', admin.site.urls),
    
    # Authentication
    path('accounts/', include('accounts.urls')),
    
    # Subscriptions & Payments
    path('', include('subscriptions.urls')),
    
    # Support
    path('', include('support.urls')),
    
    # Admin Panel (custom)
    path('admin-panel/', include('admin_panel.urls')),
    
    # Core module views
    path('', include('core.urls')),
    
    # Webhooks
    path('webhooks/razorpay/', PaymentWebhookView.as_view(), name='razorpay_webhook'),
]
```

---

## 8. IMMEDIATE NEXT STEPS

Based on current progress, here's what to create next:

### Priority 1: Profile Management
```
- accounts/forms.py (ProfileForm, ChangePhoneForm, ChangeEmailForm)
- accounts/views.py (profile_view, change_phone_view, change_email_view)
- accounts/templates/accounts/profile.html
- accounts/templates/accounts/change_phone.html
- accounts/templates/accounts/change_email.html
```

### Priority 2: Subscriptions Views
```
- subscriptions/views.py (pricing_view, checkout_view, my_subscriptions_view)
- subscriptions/urls.py
- subscriptions/templates/subscriptions/pricing.html
- subscriptions/templates/subscriptions/checkout.html
- subscriptions/templates/subscriptions/my_subscriptions.html
```

### Priority 3: Dashboard
```
- core/views.py (dashboard_view)
- core/templates/core/dashboard.html
- templates/base.html (sidebar layout)
- templates/components/_sidebar.html
- templates/components/_topbar.html
```

---

## Summary

| Component | Status | Files |
|-----------|--------|-------|
| **accounts app** | ✅ 80% | models, views, urls, services, templates |
| **subscriptions app** | ✅ 60% | models, services, middleware, access_control |
| **datasets app** | ✅ 50% | models, import_service |
| **support app** | ✅ 30% | models only |
| **admin_panel app** | ❌ 0% | Not started |
| **UI/Templates** | ⚠️ 20% | Auth templates only |
| **Celery tasks** | ❌ 0% | Not started |
| **Production setup** | ❌ 0% | Not started |

**Next Command**: Say **"Create profile views"** to continue with profile management.
