# Multi-State SOR Rate System

## Overview

This document describes the implementation of the multi-state SOR (Schedule of Rates) system that allows the application to support different rate books for different Indian states (Telangana, Andhra Pradesh, etc.).

## Architecture

### New Models (datasets app)

#### 1. State
Represents an Indian state that can have its own SOR rates.

```python
class State(models.Model):
    code = models.CharField(max_length=10, unique=True)  # 'TS', 'AP', 'KA'
    name = models.CharField(max_length=100)              # 'Telangana'
    full_name = models.CharField(max_length=200)         # 'State of Telangana'
    display_order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)      # Only one can be default
```

#### 2. SORRateBook
State-specific SOR rate books (Excel files with Master Datas and Groups sheets).

```python
class SORRateBook(models.Model):
    code = models.CharField(max_length=50, unique=True)  # 'TS_ELEC_2024'
    state = models.ForeignKey(State)
    name = models.CharField(max_length=255)
    work_type = models.CharField()  # 'electrical', 'civil', etc.
    financial_year = models.CharField()  # '2024-25'
    file = models.FileField()  # Excel file
    status = models.CharField()  # 'draft', 'published', 'archived'
    is_default = models.BooleanField()  # Default for this state+work_type
```

#### 3. ModuleDatasetConfig
Links modules (estimate, workslip, etc.) to specific SOR rate books.

```python
class ModuleDatasetConfig(models.Model):
    module_code = models.CharField()     # 'estimate', 'workslip', 'amc'
    work_type = models.CharField()       # 'electrical', 'civil'
    state = models.ForeignKey(State)
    sor_rate_book = models.ForeignKey(SORRateBook, null=True)
    custom_file = models.FileField(null=True)  # Override file
    is_default = models.BooleanField()
```

#### 4. UserStatePreference
Stores user's preferred state for SOR rates.

```python
class UserStatePreference(models.Model):
    user = models.OneToOneField(User)
    preferred_state = models.ForeignKey(State, null=True)
    module_states = models.JSONField()  # {"estimate": "AP", "workslip": "TS"}
```

### Updated Models (core app)

#### BackendWorkbook (Enhanced)
Now supports state-based filtering:

```python
class BackendWorkbook(models.Model):
    category = models.CharField()
    file = models.FileField()
    state = models.ForeignKey('datasets.State', null=True)  # NEW
    name = models.CharField(blank=True)                      # NEW
    financial_year = models.CharField(blank=True)            # NEW
    is_default = models.BooleanField(default=False)          # NEW
```

## Backend Loading Priority

The `load_backend()` function in `core/utils_excel.py` follows this priority order:

1. **ModuleDatasetConfig** - If module_code and state_code provided
2. **SORRateBook** - If state_code provided (direct state-based lookup)
3. **Module.backend_sheet_file** - For special modules like AMC
4. **BackendWorkbook** - Legacy system, now with state support
5. **Static file_map** - Fallback to `core/data/*.xlsx` files

```python
def load_backend(category, base_dir, state_code=None, module_code=None, user=None):
    # ... resolution logic ...
    return items_list, groups_map, units_map, ws_data, filepath
```

## API Endpoints

### GET /datasets/api/states/
Returns available states for a module/work type.

**Query Parameters:**
- `module_code` - e.g., 'estimate', 'workslip'
- `work_type` - e.g., 'electrical', 'civil'

**Response:**
```json
{
    "states": [
        {"code": "TS", "name": "Telangana", "is_default": true},
        {"code": "AP", "name": "Andhra Pradesh", "is_default": false}
    ],
    "user_preference": "TS",
    "default": "TS"
}
```

### POST /datasets/api/states/set/
Set user's state preference.

**Request Body:**
```json
{
    "state_code": "AP",
    "module_code": "estimate"  // optional
}
```

### GET /datasets/api/states/preference/
Get user's current state preferences.

### GET /datasets/api/sor-books/
Get available SOR rate books filtered by state and work type.

## Admin Panel

### New Admin Sections

1. **States** (`/admin/datasets/state/`)
   - Add/edit Indian states
   - Set default state
   - Activate/deactivate states

2. **SOR Rate Books** (`/admin/datasets/sorratebook/`)
   - Upload Excel files for each state/work type
   - Set financial year and validity dates
   - Publish/archive rate books
   - Set default for state+work_type combination

3. **Module Dataset Configs** (`/admin/datasets/moduledatasetconfig/`)
   - Link modules to specific SOR rate books
   - Override with custom files
   - Configure per-module defaults

4. **User State Preferences** (`/admin/datasets/userstatepreference/`)
   - View/edit user preferences

### Enhanced BackendWorkbook Admin
- Now shows state, name, financial_year columns
- Filter by state
- Set default per category

## Usage in Views

### Getting User's State
```python
from datasets.models import UserStatePreference, State

# Get user's preferred state for a module
pref = UserStatePreference.get_or_create_for_user(request.user)
state = pref.get_state_for_module('estimate')
state_code = state.code  # 'TS' or 'AP'
```

### Loading Backend with State
```python
from core.utils_excel import load_backend

# With explicit state
items_list, groups_map, units_map, ws_data, filepath = load_backend(
    category='electrical',
    base_dir=settings.BASE_DIR,
    state_code='AP',
    module_code='estimate'
)

# With user preference (auto-detect state)
items_list, groups_map, units_map, ws_data, filepath = load_backend(
    category='electrical',
    base_dir=settings.BASE_DIR,
    user=request.user,
    module_code='estimate'
)
```

### Getting Available States
```python
from core.utils_excel import get_available_states_for_category

states = get_available_states_for_category('electrical', module_code='estimate')
# [{'code': 'TS', 'name': 'Telangana', 'is_default': True}, ...]
```

## Frontend Integration

### State Selector Component
Include in templates:

```html
<script src="{% static 'js/state_selector.js' %}"></script>
<div id="state-selector"></div>
<script>
    StateSelector.init({
        moduleCode: 'estimate',
        workType: 'electrical',
        onStateChange: function(newState, oldState) {
            // Reload data with new state
            location.reload();
        }
    });
</script>
```

### State Selection Page
`/datasets/settings/state/` - Full page for selecting preferred state.

## Migration Steps

1. Run migrations:
   ```bash
   python manage.py migrate datasets
   python manage.py migrate core
   ```

2. Seed initial states (automatic via migration 0003_seed_states):
   - Telangana (TS) - Active, Default
   - Andhra Pradesh (AP) - Active
   - Other states - Inactive (for future)

3. Upload SOR rate books via admin:
   - `/admin/datasets/sorratebook/add/`
   - Select state, work type, financial year
   - Upload Excel file
   - Publish

4. Configure module datasets (optional):
   - `/admin/datasets/moduledatasetconfig/add/`
   - Link specific rate books to modules

## Adding a New State

1. **Admin Panel:**
   - Go to `/admin/datasets/state/`
   - Add new state with code, name
   - Set `is_active = True`

2. **Upload SOR Rate Book:**
   - Go to `/admin/datasets/sorratebook/add/`
   - Select the new state
   - Upload Excel file with `Master Datas` and `Groups` sheets
   - Publish the rate book

3. **Configure Modules (Optional):**
   - Go to `/admin/datasets/moduledatasetconfig/add/`
   - Create configs for each module + work_type + state combination

## File Format Requirements

SOR Excel files must contain:

1. **Sheet: "Master Datas"**
   - Item blocks marked with yellow background + red text headings
   - Columns A-J for item data
   - Column J for rates

2. **Sheet: "Groups"**
   - Column A: Item Name
   - Column B: Group Name
   - Column C: Prefix
   - Column D: Unit

## Backward Compatibility

- Existing `load_backend()` calls without state parameters continue to work
- Falls back to default state (Telangana) or static files
- Existing BackendWorkbook entries are treated as default (no state)
- No changes required to existing views unless state selection is desired

## Security Considerations

- All API endpoints require authentication (`@login_required`)
- CSRF protection on POST endpoints
- State preferences are user-specific
- Admin-only access to SOR rate book management
