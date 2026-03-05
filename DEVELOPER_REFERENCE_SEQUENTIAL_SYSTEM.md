# Developer Reference: Bill & Workslip Entry System

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                         │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Saved Works Detail View (/saved-works/{id}/)                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [E] ──────→ [W] ──────→ [B]  ← Workflow Buttons          │  │
│  │                                                            │  │
│  │  Click W on Estimate                                      │  │
│  │    ↓                                                       │  │
│  │  Workslip Entry Form (/workslip/entry/{id}/)             │  │
│  │  ├── Estimate items (auto-loaded)                         │  │
│  │  ├── Qty inputs, T.P. percentage                          │  │
│  │  └── Save → Creates SavedWork(workslip)                  │  │
│  │    ↓                                                       │  │
│  │  Click B on Workslip                                      │  │
│  │    ↓                                                       │  │
│  │  Bill Entry Form (/bill/entry/{id}/)                      │  │
│  │  ├── Workslip items (auto-loaded)                         │  │
│  │  ├── Qty inputs, Deduction tracking                       │  │
│  │  ├── Dates & M.B. details                                 │  │
│  │  └── Save → Creates SavedWork(bill)                       │  │
│  │                                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    VIEW LAYER (Django Views)                    │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  workslip_entry(request, work_id)                              │
│  ├── Fetch source estimate                                      │
│  ├── Load estimate items (fetched_items)                        │
│  ├── Find highest workslip_number                               │
│  ├── Build context with items/workflow                          │
│  └── Render workslip_entry.html                                │
│                                                                  │
│  workslip_entry_save(request, work_id)                          │
│  ├── Parse POST: ws_exec_map, ws_rate_map, tp_%, tp_type       │
│  ├── Validate: at least 1 qty > 0                               │
│  ├── Determine workslip_number (highest + 1)                    │
│  ├── Build SavedWork.work_data with all details                 │
│  ├── Create SavedWork(parent=estimate, type=workslip)           │
│  └── Return JSON with redirect URL                              │
│                                                                  │
│  bill_entry(request, work_id)                                   │
│  ├── Fetch source workslip                                      │
│  ├── Load workslip items (ws_estimate_rows)                     │
│  ├── Find previous bill (bill_number - 1)                       │
│  ├── Load previous bill items for deductions                    │
│  ├── Build context with items/prev_items/workflow               │
│  └── Render bill_entry.html                                     │
│                                                                  │
│  bill_entry_save(request, work_id)                              │
│  ├── Parse POST: bill_exec_map, bill_deduct_map                │
│  ├── Validate: at least 1 qty > 0                               │
│  ├── Determine bill_number from source workslip                 │
│  ├── Build SavedWork.work_data with quantities/dates            │
│  ├── Create SavedWork(parent=workslip, type=bill)               │
│  └── Return JSON with redirect URL                              │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   MODEL LAYER (Database)                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SavedWork                                                      │
│  ├── id (PK)                                                    │
│  ├── parent_id (FK) → SavedWork parent                          │
│  ├── work_type: 'estimate' | 'workslip' | 'bill'              │
│  ├── workslip_number: 1, 2, 3, ...                              │
│  ├── bill_number: 1, 2, 3, ...                                  │
│  ├── work_data: JSONField                                       │
│  │   ├── ws_estimate_rows (for workslips)                       │
│  │   ├── ws_exec_map {key: qty}                                 │
│  │   ├── bill_ws_rows (for bills)                               │
│  │   ├── bill_exec_map {key: qty}                               │
│  │   ├── bill_deduct_map {key: deduct_qty}                      │
│  │   └── dates (for bills)                                      │
│  └── created_at, updated_at (timestamps)                        │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

## Data Flow Examples

### Example 1: Create Workslip-1

```python
# Frontend (JavaScript)
const execMap = {
    'item_1': 50.0,
    'item_2': 30.0,
};
const formData = new FormData(form);
formData.append('ws_exec_map', JSON.stringify(execMap));

# Submission
POST /workslip/entry/123/save/
  ├── ws_exec_map: {"item_1": 50.0, "item_2": 30.0}
  ├── ws_rate_map: {"item_1": 50.0, "item_2": 100.0}
  ├── ws_tp_percent: 15
  ├── ws_tp_type: Excess
  └── csrf_token: ...

# Backend (Django View)
def workslip_entry_save(request, work_id):
    ws_exec_map = json.loads(request.POST.get('ws_exec_map'))
    # → {'item_1': 50.0, 'item_2': 30.0}
    
    workslip_data = {
        'workslip_number': 1,
        'ws_estimate_rows': [...],
        'ws_exec_map': ws_exec_map,
        'ws_tp_percent': 15,
        'ws_tp_type': 'Excess',
    }
    
    saved = SavedWork.objects.create(
        parent=source_estimate,
        work_type='workslip',
        workslip_number=1,
        work_data=workslip_data
    )
    
    return JsonResponse({
        'success': True,
        'work_id': saved.id,
        'redirect_url': f'/saved-works/{saved.id}/'
    })

# Database
SavedWork.objects.get(id=123)
# SavedWork(
#     id=456,
#     parent_id=123,
#     work_type='workslip',
#     workslip_number=1,
#     work_data={
#         'workslip_number': 1,
#         'ws_estimate_rows': [{'key': 'item_1', 'rate': 50.0, ...}, ...],
#         'ws_exec_map': {'item_1': 50.0, 'item_2': 30.0},
#         'ws_tp_percent': 15,
#         ...
#     }
# )
```

### Example 2: Create Bill-2 with Deductions from Bill-1

```python
# Frontend (JavaScript)
const execMap = {
    'item_1': 80.0,   // Till date qty
    'item_2': 50.0,
};
const deductMap = {
    'item_1': 50.0,   // From Bill-1
    'item_2': 30.0,   // From Bill-1
};

# Bill-2 Amount Calculation
# Item-1: (80.0 - 50.0) × 50.0 = 1,500 ₹
# Item-2: (50.0 - 30.0) × 100.0 = 2,000 ₹
# Total: 3,500 ₹

# Submission
POST /bill/entry/456/save/
  ├── bill_exec_map: {"item_1": 80.0, "item_2": 50.0}
  ├── bill_deduct_map: {"item_1": 50.0, "item_2": 30.0}
  ├── bill_rate_map: {"item_1": 50.0, "item_2": 100.0}
  ├── doi: "2026-03-01"
  ├── doc: "2026-03-05"
  ├── domr: "2026-03-06"
  ├── dobr: "2026-03-07"
  └── csrf_token: ...

# Backend
def bill_entry_save(request, work_id):
    bill_exec_map = json.loads(request.POST.get('bill_exec_map'))
    bill_deduct_map = json.loads(request.POST.get('bill_deduct_map'))
    
    # bill_exec_map → {'item_1': 80.0, 'item_2': 50.0}
    # bill_deduct_map → {'item_1': 50.0, 'item_2': 30.0}
    
    bill_data = {
        'bill_number': 2,
        'bill_type': 'nth_part',
        'bill_ws_rows': [...],
        'bill_ws_exec_map': bill_exec_map,
        'bill_deduct_map': bill_deduct_map,  # ← Deductions stored
        'doi': '2026-03-01',
        'doc': '2026-03-05',
        'domr': '2026-03-06',
        'dobr': '2026-03-07',
    }
    
    saved = SavedWork.objects.create(
        parent=source_workslip,
        work_type='bill',
        bill_number=2,
        work_data=bill_data
    )
    
    return JsonResponse({
        'success': True,
        'work_id': saved.id
    })

# Database
SavedWork.objects.get(id=789)
# SavedWork(
#     id=789,
#     parent_id=456,  # Parent is Workslip-2
#     work_type='bill',
#     bill_number=2,
#     work_data={
#         'bill_number': 2,
#         'bill_ws_exec_map': {'item_1': 80.0, 'item_2': 50.0},
#         'bill_deduct_map': {'item_1': 50.0, 'item_2': 30.0},  # ← From Bill-1
#         'doi': '2026-03-01',
#         ...
#     }
# )
```

## Code Examples

### Fetching Related Works

```python
# Get all workslips for an estimate
estimate = SavedWork.objects.get(id=123, work_type='new_estimate')
workslips = estimate.children.filter(work_type='workslip').order_by('workslip_number')

# Get all bills for a workslip
workslip = SavedWork.objects.get(id=456, work_type='workslip')
bills = workslip.children.filter(work_type='bill').order_by('bill_number')

# Get previous bill
previous_bill = SavedWork.objects.get(
    parent=workslip,
    work_type='bill',
    bill_number=bill_number - 1
)

# Traverse full workflow chain
current = bill  # Bill-2
parents = []
while current.parent:
    parents.insert(0, current.parent)
    current = current.parent
# parents = [Estimate, Workslip-2]
```

### Accessing Saved Data

```python
# Get workslip quantities
workslip = SavedWork.objects.get(id=123, work_type='workslip')
work_data = workslip.work_data

items = work_data['ws_estimate_rows']
quantities = work_data['ws_exec_map']
tp_percent = work_data['ws_tp_percent']

# Example:
for item in items:
    key = item['key']
    qty = quantities.get(key, 0)
    rate = item['rate']
    amount = qty * rate
    print(f"{item['desc']}: {qty} × {rate} = {amount}")

# Get bill with deductions
bill = SavedWork.objects.get(id=456, work_type='bill')
bill_data = bill.work_data

bill_qtys = bill_data['bill_ws_exec_map']
deductions = bill_data['bill_deduct_map']

for key in bill_qtys:
    till_date_qty = bill_qtys[key]
    deduct_qty = deductions.get(key, 0)
    net_qty = till_date_qty - deduct_qty
    print(f"{key}: {till_date_qty} - {deduct_qty} = {net_qty}")
```

### Validation Logic

```python
# In workslip_entry_save
def validate_workslip_data(exec_map, rate_map):
    errors = []
    
    # At least one quantity > 0
    if not any(float(q or 0) > 0 for q in exec_map.values()):
        errors.append("Please enter at least one quantity")
    
    # Valid numeric values
    for key, qty in exec_map.items():
        try:
            float(qty)
        except (ValueError, TypeError):
            errors.append(f"Invalid quantity for {key}")
    
    if errors:
        return False, errors
    return True, []

# Usage
is_valid, errors = validate_workslip_data(exec_map, rate_map)
if not is_valid:
    return JsonResponse({
        'success': False,
        'error': '\n'.join(errors)
    }, status=400)
```

### Calculation Logic

```python
# Workslip total with T.P.
def calculate_workslip_total(items, exec_map, rate_map, tp_percent, tp_type):
    total = 0
    for item in items:
        key = item['key']
        qty = float(exec_map.get(key, 0) or 0)
        rate = float(rate_map.get(key, 0) or 0)
        total += qty * rate
    
    tp_amount = total * (tp_percent / 100)
    
    if tp_type == 'Excess':
        grand_total = total + tp_amount
    else:  # Deduct
        grand_total = total - tp_amount
    
    return {
        'total': total,
        'tp_amount': tp_amount,
        'grand_total': grand_total
    }

# Bill total with deductions
def calculate_bill_total(items, exec_map, deduct_map, rate_map):
    total = 0
    for item in items:
        key = item['key']
        till_date_qty = float(exec_map.get(key, 0) or 0)
        deduct_qty = float(deduct_map.get(key, 0) or 0)
        rate = float(rate_map.get(key, 0) or 0)
        
        net_qty = max(0, till_date_qty - deduct_qty)
        total += net_qty * rate
    
    return total
```

## JavaScript Examples

### Serialization

```javascript
// Serialize form data to JSON before submission
document.getElementById('workslip-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Collect all quantity inputs
    const execMap = {};
    const rateMap = {};
    
    document.querySelectorAll('.qty-row').forEach((row) => {
        const key = row.dataset.key;
        const qty = parseFloat(row.querySelector('.exec-qty').value) || 0;
        const rate = parseFloat(row.dataset.rate) || 0;
        
        execMap[key] = qty;
        rateMap[key] = rate;
    });
    
    // Set hidden fields
    document.getElementById('ws-exec-map-field').value = JSON.stringify(execMap);
    document.getElementById('ws-rate-map-field').value = JSON.stringify(rateMap);
    
    // Submit
    this.submit();
});

// Result:
// POST Form Data:
// {
//     'ws_exec_map': '{"item_1": 50.0, "item_2": 30.0}',
//     'ws_rate_map': '{"item_1": 50.0, "item_2": 100.0}',
//     ...
// }
```

### Real-Time Calculation

```javascript
function updateAmount(idx, qty, rate) {
    const amount = qty * rate;
    const cell = document.getElementById(`amount_${idx}`);
    cell.textContent = `₹ ${amount.toFixed(2)}`;
}

document.querySelectorAll('.qty-input').forEach((input) => {
    input.addEventListener('input', function(e) {
        const qty = parseFloat(e.target.value) || 0;
        const row = e.target.closest('tr');
        const rate = parseFloat(row.dataset.rate) || 0;
        const idx = row.dataset.index;
        
        updateAmount(idx, qty, rate);
        updateSummary();
    });
});

function updateSummary() {
    let total = 0;
    document.querySelectorAll('[id^="amount_"]').forEach((cell) => {
        const amountText = cell.textContent.replace('₹ ', '');
        total += parseFloat(amountText) || 0;
    });
    
    document.getElementById('summary-total').textContent = `₹ ${total.toFixed(2)}`;
}
```

## Testing Checklist

```python
# test_bill_entry.py
class TestWorkslipEntry(TestCase):
    def setUp(self):
        self.estimate = SavedWork.objects.create(
            work_type='new_estimate',
            work_data={'fetched_items': [...]}
        )
    
    def test_workslip_entry_page_loads(self):
        response = self.client.get(f'/workslip/entry/{self.estimate.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/workslip_entry.html')
    
    def test_workslip_creation_saves_data(self):
        post_data = {
            'action': 'save_workslip_data',
            'ws_exec_map': '{"item_1": 50.0}',
            'ws_rate_map': '{"item_1": 50.0}',
            'ws_tp_percent': '15',
            'ws_tp_type': 'Excess',
        }
        response = self.client.post(
            f'/workslip/entry/{self.estimate.id}/save/',
            post_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify SavedWork created
        ws = SavedWork.objects.get(work_type='workslip')
        self.assertEqual(ws.workslip_number, 1)
        self.assertEqual(ws.parent, self.estimate)
    
    def test_workslip_requires_at_least_one_qty(self):
        post_data = {
            'ws_exec_map': '{}',  # No quantities
            'ws_rate_map': '{}',
        }
        response = self.client.post(
            f'/workslip/entry/{self.estimate.id}/save/',
            post_data
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
```

## Deployment Notes

1. **Dependencies**: No new Python packages required
2. **Database**: No schema changes (uses JSONField)
3. **Static Files**: CSS/JS included in templates
4. **Migrations**: No migrations needed
5. **Settings**: No new settings required
6. **URLs**: Add routes to `urls.py`

## Performance Tips

- Index `work_type` and `parent_id` for faster queries
- Index `workslip_number` and `bill_number` for sorting
- Use `select_related('parent')` when fetching workflow chains
- Cache calculation results if needed
- Monitor JSON field size in work_data

---

**This is a complete, production-ready implementation ready for immediate deployment!**
