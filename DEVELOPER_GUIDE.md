# Hamsvic Office — Developer Guide

## Project Overview

**Hamsvic Office** is a Django web application for government billing, estimates, and workslip management. It is server-side rendered (Django templates + inline JavaScript) — there is no separate frontend framework.

**Tech Stack:** Django 4.x, PostgreSQL (production), SQLite (local), openpyxl (Excel I/O), python-docx, Railway (deployment)

---

## Directory Structure

```
hamsvicoffice/
├── manage.py                    # Django management entry point
├── estimate_site/               # Django project settings & URL config
│   ├── settings.py
│   └── urls.py                  # All URL patterns (150+)
│
├── core/                        # Main application
│   ├── models.py                # 14 database models
│   ├── views/                   # View functions (split into modules)
│   │   ├── __init__.py          # Re-exports all views for backward compat
│   │   ├── utils.py             # Shared utilities & constants
│   │   ├── home_views.py        # Home page, letter settings
│   │   ├── workslip_views.py    # Workslip upload, process, download
│   │   ├── bill_parsing.py      # Excel parsing for bills/estimates
│   │   ├── bill_excel.py        # Bill Excel workbook generation
│   │   ├── bill_views.py        # Main bill generation handler
│   │   ├── estimate_excel.py    # Estimate Excel workbook builder
│   │   ├── amount_utils.py      # Amount extraction & template helpers
│   │   ├── document_views.py    # Bill document, LS forms, covering letters
│   │   ├── project_views.py     # Projects, SOR data, estimate download
│   │   ├── self_formatted_views.py    # OCR & self-formatted documents
│   │   ├── self_formatted_form_views.py  # Self-formatted form UI
│   │   ├── tempworks_views.py   # Temporary works module
│   │   ├── estimate_views.py    # Estimate module
│   │   └── amc_views.py         # AMC (Annual Maintenance Contract)
│   ├── saved_works_views.py     # Saved works, bill generation workflow
│   ├── bill_entry_views.py      # Bill entry UI & save logic
│   ├── auth_views.py            # Legacy authentication
│   ├── api_views.py             # API endpoints
│   ├── dashboard_views.py       # Dashboard
│   ├── template_views.py        # User document templates
│   ├── decorators.py            # @org_required, @role_required
│   ├── tasks.py                 # Async background tasks
│   ├── utils_excel.py           # Excel parsing utilities
│   └── templates/core/          # Django HTML templates
│
├── accounts/                    # OTP-based authentication app
├── admin_panel/                 # SaaS admin panel
├── subscriptions/               # Subscription & pricing
├── support/                     # Help center
├── datasets/                    # SOR rate management
├── estimates/                   # Estimate data files
│
├── scripts/                     # Utility scripts (not part of the app)
│   ├── tests/                   # Test scripts
│   ├── data/                    # Data migration & export scripts
│   └── utils/                   # Setup & fix scripts
│
├── docs/                        # Documentation
│   ├── architecture/            # Feature docs, design decisions
│   ├── deployment/              # Deployment guides
│   └── phases/                  # Development phase notes
│
├── requirements.txt             # Python dependencies
├── Procfile                     # Railway process definition
├── railway.json                 # Railway config
└── docker-compose.yml           # Docker setup
```

---

## Key Modules Explained

### Views Package (`core/views/`)

The views were split from a single 16,000-line file into logical modules. The `__init__.py` re-exports everything, so existing imports like `from core.views import bill` continue to work.

| Module | What it does | Key functions |
|--------|-------------|---------------|
| `utils.py` | Shared helpers | `_apply_print_settings`, `_format_indian_number`, `_number_to_words_rupees`, `get_org_from_request` |
| `workslip_views.py` | Workslip 3-panel UI | `workslip()`, `workslip_ajax_toggle_supp()` |
| `bill_parsing.py` | Parse Excel files | `parse_estimate_items()`, `parse_workslip_items()`, `_extract_header_data_fuzzy_from_wb()` |
| `bill_excel.py` | Build bill Excel files | `create_first_bill_sheet()`, `build_first_bill_wb()`, `build_nth_bill_wb()` |
| `bill_views.py` | Bill generation handler | `bill()` — handles 8 different bill actions |
| `document_views.py` | LS forms, covering letters | `bill_document()`, `self_formatted_document()` |
| `project_views.py` | SOR data browsing | `datas()`, `datas_groups()`, `datas_items()`, `download_output()` |
| `tempworks_views.py` | Temporary works | `tempworks_home()`, `temp_groups()`, `temp_items()` |
| `estimate_views.py` | Estimate module | `estimate()`, `download_specification_report()` |
| `amc_views.py` | AMC module | `amc_home()`, `amc_groups()`, `amc_items()` |

### Models (`core/models.py`)

| Model | Purpose |
|-------|---------|
| `Organization` | Multi-tenant organization |
| `Membership` | User ↔ Organization relationship |
| `Upload` | Uploaded Excel files |
| `Job` | Background processing jobs |
| `OutputFile` | Generated output files |
| `Project` | Saved project with estimate data |
| `Estimate` | Saved estimate records |
| `SavedWork` | Saved works (workslips, bills) |
| `LetterSettings` | User's letter/document settings |
| `SelfFormattedTemplate` | OCR document templates |
| `WorkFolder` | Folder organization for saved works |
| `UserDocumentTemplate` | User-uploaded covering letter templates |

---

## How to Find Code

**"Where is the bill generation logic?"**
→ `core/views/bill_views.py` (the `bill()` function)

**"Where does bill Excel get built?"**
→ `core/views/bill_excel.py` (`build_first_bill_wb`, `build_nth_bill_wb`)

**"Where is the workslip UI?"**
→ `core/views/workslip_views.py` and `core/templates/core/workslip.html`

**"Where are URL routes defined?"**
→ `estimate_site/urls.py`

**"Where is the bill entry form (sequential system)?"**
→ `core/bill_entry_views.py` and `core/templates/core/bill_entry_new.html`

**"Where are saved works managed?"**
→ `core/saved_works_views.py`

---

## Running Locally

```bash
pip install -r requirements.txt
set DJANGO_SECRET_KEY=your-secret-key
python manage.py migrate
python manage.py runserver
```

## Deployment

The app auto-deploys to Railway on `git push` to `main`. See `docs/deployment/` for detailed guides.
