# Sequential Bill & Workslip Entry System - Implementation Guide

## Overview

This document describes the new sequential bill and workslip creation system that allows users to generate bills and workslips directly through the UI without file uploads. All data flows through a clean, intuitive interface with proper linking between estimates, workslips, and bills.

## System Architecture

### Workflow Chain: Estimate → Workslip → Bill

```
┌─────────────────────────────────────────────────────┐
│                  ESTIMATE (E)                        │
│  ┌─────────────────────────────────────────────┐    │
│  │  - Items with quantities & rates             │    │
│  │  - Category & metadata                       │    │
│  └─────────────────────────────────────────────┘    │
│           │                                          │
│           ▼ (parent relationship)                    │
│  ┌─────────────────────────────────────────────┐    │
│  │  WORKSLIP-1, 2, 3... (W1, W2, W3...)        │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │ - W1: Executed quantities for items  │   │    │
│  │  │ - W2: Additional quantities (extends │   │    │
│  │  │       work beyond W1)                │   │    │
│  │  │ - Temporary Works (T.P.) percentage  │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
│           │                                          │
│           ▼ (parent relationship)                    │
│  ┌─────────────────────────────────────────────┐    │
│  │  BILL-1, 2, 3... (B1, B2, B3...)            │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │ - B1: From W1 quantities              │   │    │
│  │  │ - B2: From W2 + deductions from B1   │   │    │
│  │  │ - Measurement book details            │   │    │
│  │  │ - Dates (DOI, DOC, DOMR, DOBR)       │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Key Features

### 1. Workslip Entry (Sequential without file uploads)

**Route**: `/workslip/entry/<estimate_id>/`

**Features**:
- Load estimate items automatically
- Enter executed quantities for each item
- Set Temporary Works (T.P.) percentage (Excess/Deduct)
- Measurement book details (optional)
- Real-time calculation of amounts
- Support for multiple workslips (W1, W2, W3, ...)

**Data Structure** (`SavedWork.work_data`):
```json
{
  "workslip_number": 1,
  "ws_estimate_rows": [
    {
      "key": "item_1",
      "item_name": "Excavation",
      "desc": "Excavation 1 meter",
      "unit": "m",
      "qty_est": 100.0,
      "rate": 50.0
    }
  ],
  "ws_exec_map": {
    "item_1": 50.0  // Executed quantity
  },
  "ws_rate_map": {
    "item_1": 50.0  // Unit rate
  },
  "ws_tp_percent": 15,  // Temporary Works %
  "ws_tp_type": "Excess",
  "ws_metadata": { /* ... */ },
  "ws_source_estimate_id": 123
}
```

### 2. Bill Entry (Sequential without file uploads)

**Route**: `/bill/entry/<workslip_id>/`

**Features**:
- Load workslip items automatically
- Enter quantities (or Till Date quantities for B2+)
- Deduction tracking from previous bills
- Measurement book details
- Important dates (DOI, DOC, DOMR, DOBR)
- Real-time calculations with deductions

**Data Structure** (`SavedWork.work_data`):
```json
{
  "bill_number": 1,
  "bill_type": "first_part",
  "bill_ws_rows": [ /* workslip items */ ],
  "bill_ws_exec_map": {
    "item_1": 50.0  // Billed quantity
  },
  "bill_deduct_map": {
    "item_1": 0.0  // Deduction from previous bill
  },
  "mb_no": "MB-001",
  "mb_from_page": "1",
  "mb_to_page": "5",
  "doi": "2026-03-01",
  "doc": "2026-03-05",
  "domr": "2026-03-06",
  "dobr": "2026-03-07",
  "source_workslip_id": 456
}
```

## File Structure

### New Files Created

1. **`core/bill_entry_views.py`** - View handlers for bill and workslip entry
   - `bill_entry()` - Display bill entry form
   - `bill_entry_save()` - Save bill data
   - `workslip_entry()` - Display workslip entry form
   - `workslip_entry_save()` - Save workslip data
   - Helper functions for workflow management

2. **`core/templates/core/bill_entry.html`** - Bill entry UI
   - Workflow breadcrumb showing Estimate → Workslip → Bill
   - Measurement book details form
   - Important dates form
   - Quantities table with deduction columns (B2+)
   - Summary box with calculations
   - Real-time amount calculation

3. **`core/templates/core/workslip_entry.html`** - Workslip entry UI
   - Workflow breadcrumb showing Estimate → Workslip
   - T.P. (Temporary Works) input
   - Measurement book details (optional)
   - Quantities table with previous workslip comparison
   - Real-time calculation with T.P. percentage

- **Modified Files**: Changed to link to new entry forms
  - `estimate_site/urls.py` - New URL routes
  - `core/templates/core/saved_works/detail.html` - Updated navigation

## URL Routes

```python
# Workslip Entry
path('workslip/entry/<int:work_id>/', bill_entry_views.workslip_entry, name='workslip_entry'),
path('workslip/entry/<int:work_id>/save/', bill_entry_views.workslip_entry_save, name='workslip_entry_save'),
path('workslip/start/<int:work_id>/', bill_entry_views.start_workslip_creation, name='start_workslip_creation'),

# Bill Entry
path('bill/entry/<int:work_id>/', bill_entry_views.bill_entry, name='bill_entry'),
path('bill/entry/<int:work_id>/save/', bill_entry_views.bill_entry_save, name='bill_entry_save'),
path('bill/start/<int:work_id>/', bill_entry_views.start_bill_creation, name='start_bill_creation'),
```

## User Workflow

### Creating Workslip-1 from Estimate

1. **User Navigation**:
   - Opens saved estimate
   - Clicks "W" button (Workslip)
   - Redirected to `/workslip/entry/{estimate_id}/`

2. **Entry Form**:
   - Form shows all estimate items
   - User enters executed quantities for each item
   - Sets T.P. percentage (optional)
   - Enters measurement book details (optional)
   - User clicks "Save & Continue"

3. **Data Persistence**:
   - New `SavedWork` created with:
     - `work_type="workslip"`
     - `workslip_number=1`
     - `parent=estimate`
     - Complete `work_data` with quantities
   - User redirected to saved work detail

### Creating Bill-1 from Workslip-1

1. **User Navigation**:
   - Opens saved Workslip-1
   - Clicks "B" button (Bill)
   - Redirected to `/bill/entry/{workslip_id}/`

2. **Entry Form**:
   - Form shows all Workslip-1 items with executed quantities
   - User enters bill quantities (same as workslip by default)
   - Enters measurement book details
   - Enters important dates
   - User clicks "Save & Continue"

3. **Data Persistence**:
   - New `SavedWork` created with:
     - `work_type="bill"`
     - `bill_number=1`
     - `parent=workslip`
     - Complete `work_data` with bill quantities and dates

### Creating Bill-2 from Workslip-2

1. **Workslip-2 Creation**:
   - From Workslip-1 detail, click "W" to create Workslip-2
   - Shows previous workslip data for reference
   - User enters additional quantities

2. **Bill-2 Creation**:
   - From Workslip-2 detail, click "B" to create Bill-2
   - Shows both:
     - Till date quantities (from Workslip-2)
     - Deductions column showing Bill-1 quantities
   - User enters new quantities, system automatically calculates deductions
   - Net amount = Till Date Qty - Deduction Qty

## Form Data Flow

### JavaScript Serialization

Both forms use JavaScript to:
1. Collect all quantity inputs
2. Build maps: `{item_key: quantity}`
3. Serialize to JSON
4. Store in hidden form fields
5. Submit via POST

**Example**:
```javascript
const execMap = {
  "item_1": 50.0,
  "item_2":  30.5,
  "item_3": 100.0
};

// Serialized and submitted as:
// POST data: ws_exec_map = JSON.stringify(execMap)
```

### Backend Processing

1. **Parse JSON** from POST:
   ```python
   ws_exec_map = json.loads(request.POST.get('ws_exec_map', '{}'))
   ```

2. **Validate** quantities:
   - At least one quantity > 0
   - Valid numeric values

3. **Build SavedWork** with complete data:
   ```python
   saved_work = SavedWork.objects.create(
       parent=source_estimate,
       work_type='workslip',
       work_data={
           'ws_estimate_rows': rows,
           'ws_exec_map': exec_map,
           ...
       }
   )
   ```

## UI Components

### Workflow Breadcrumb
Shows the workflow chain:
```
[Estimate] → [Workslip-1] → [Bill-1] (current)
```
- Color-coded by type (blue=estimate, green=workslip, red=bill)
- Last item is always the current form

### Summary Box
Displays in real-time:
- **Items Count**: Number of items with quantities > 0
- **Total Amount**: Sum of (quantity × rate)
- **Total Deductions**: (For B2+) Sum of deduction amounts
- **Net Bill Amount**: Total - Deductions (for bills)
- **Grand Total**: With T.P. percentage (for workslips)

### Quantities Table
- **SL**: Serial number
- **Item**: Description with unit
- **Unit**: Unit of measurement
- **Previous Qty**: (Workslip 2+) Previous workslip quantity (read-only)
- **Rate**: Unit rate
- **Till Date Qty / Exec Qty**: Input field for quantities
- **Amount**: Auto-calculated (Qty × Rate)
- **Deduct Prev**: (Bill 2+) Previous bill deduction (read-only)

## Search & Filter

Users can easily find related works through the Saved Works list:
- Filter by work type (Estimate, Workslip, Bill)
- Filter by status (In Progress, Completed, Archived)
- Search by name
- Folder organization

## Error Handling

### Validation

1. **Source Work Validation**:
   - Estimate must have items
   - Workslip must have executed quantities
   - Parent relationships must be valid

2. **Form Validation**:
   - At least one quantity must be > 0
   - Valid numeric inputs
   - JSON serialization success

3. **User Feedback**:
   - Error messages via Django messages framework
   - Form validation on client-side (browser)
   - Server-side validation for security

### Edge Cases

1. **Missing Previous Bill**: 
   - System searches for previous bill by number
   - If not found, deduction columns disabled

2. **Orphan Workslips/Bills**:
   - System detects in `saved_work_detail` view
   - Automatically fixes parent relationships
   - Fallback: Match by name

3. **Deleted Parent**:
   - Child still accessible via SavedWork detail
   - View shows workflow chain if parent missing

## Data Integrity

### Foreign Key Relationships
```
Estimate (SavedWork)
  ├── Workslip-1 (SavedWork, parent=Estimate)
  │   ├── Bill-1 (SavedWork, parent=Workslip-1)
  │   ├── Bill-2 (SavedWork, parent=Workslip-1)
  │   └── (references for deduction: prev_bill_number)
  ├── Workslip-2 (SavedWork, parent=Estimate)
  │   ├── Bill-1 (alt, parent=Workslip-2)
  │   └── (references for comparison: workslip_number)
  └── Workslip-3 (SavedWork, parent=Estimate)
```

### Data Retention
- All `work_data` JSON stored with SavedWork
- No file uploads required
- Complete audit trail in database
- Version history via `updated_at` timestamp

## Integration Points

### Existing Systems

1. **Estimate Module**:
   - Loads estimate items via `fetched_items` in work_data
   - Uses existing SOR rate data

2. **Saved Works**:
   - Uses existing SavedWork model
   - Extends with workslip_number, bill_number fields
   - Parent-child relationships via parent FK

3. **Bill Generation** (Future):
   - Can export to Excel using saved data
   - Use existing bill generation templates
   - No file parsing required

## Future Enhancements

### Phase 2: Bill Preview & Export
- [ ] Generate PDF preview before saving
- [ ] Export to Excel with proper formatting
- [ ] LS Form generation
- [ ] Covering letter generation

### Phase 3: Advanced Features
- [ ] Bulk quantity entry
- [ ] Template copying for similar bills
- [ ] Batch bill generation
- [ ] Multi-workslip bill generation

### Phase 4: Analytics & Reporting
- [ ] Work progress tracking
- [ ] Bill summary reports
- [ ] Quantity tracking across workslips
- [ ] Deduction audit trail

## Testing Checklist

- [ ] Create estimate
- [ ] Load estimate items
- [ ] Create Workslip-1 with quantities
- [ ] View Workslip-1 detail
- [ ] Create Bill-1 from Workslip-1
- [ ] Create Workslip-2 with additional quantities
- [ ] Create Bill-2, verify deductions from Bill-1
- [ ] Edit existing bill quantities
- [ ] Verify calculations (with/without T.P.)
- [ ] Test responsive design (mobile, tablet, desktop)
- [ ] Test error cases (missing quantities, invalid data)

## API Documentation

### POST `/workslip/entry/<work_id>/save/`

**Parameters**:
- `action`: "save_workslip_data"
- `ws_exec_map`: JSON {item_key: qty}
- `ws_rate_map`: JSON {item_key: rate}
- `ws_tp_percent`: Percentage (0-100)
- `ws_tp_type`: "Excess" or "Deduct"
- `mb_no`: Measurement book number
- `mb_from_page`: From page number
- `mb_to_page`: To page number

**Response**:
```json
{
  "success": true,
  "work_id": 123,
  "redirect_url": "/saved-works/123/",
  "message": "Workslip-1 saved!"
}
```

### POST `/bill/entry/<work_id>/save/`

**Parameters**:
- `action`: "save_bill_data"
- `bill_exec_map`: JSON {item_key: qty}
- `bill_deduct_map`: JSON {item_key: deduct_qty}
- `bill_rate_map`: JSON {item_key: rate}
- `mb_no`: Measurement book number
- `mb_from_page`: From page number
- `mb_to_page`: To page number
- `doi`: Date of Issue (YYYY-MM-DD)
- `doc`: Date of Completion (YYYY-MM-DD)
- `domr`: Date of Measurement Report (YYYY-MM-DD)
- `dobr`: Date of Bill Raising (YYYY-MM-DD)

**Response**:
```json
{
  "success": true,
  "work_id": 124,
  "redirect_url": "/saved-works/124/",
  "message": "Bill-1 saved!"
}
```

## Conclusion

This sequential bill and workslip entry system provides a complete, intuitive workflow for users to generate bills and workslips through a clean UI without file uploads. All data is properly persisted, linked, and available for future export or processing.
