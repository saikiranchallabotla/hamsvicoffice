# Workslip Module - Quick Testing Guide

## ✅ Server Status
**Status**: Django development server is **RUNNING** on http://127.0.0.1:8000/

## 🧪 How to Test the Workslip Module

### Step 1: Access the Workslip Page
Open your browser and navigate to:
```
http://127.0.0.1:8000/workslip/
```

You should see:
- **Left Panel**: "Groups (Supplemental)" with a list of available groups
- **Middle Panel**: "Items in [Group Name]" with items from the selected group
- **Right Panel**: "Workslip Preview" with upload form and table

### Step 2: Generate a Test Estimate File
Run this command to create a sample Excel estimate file:
```bash
python -c "
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = 'Estimate'

# Header row at row 3
ws['A3'] = 'Sl.No'
ws['B3'] = 'Quantity'
ws['C3'] = 'Unit'
ws['D3'] = 'Description of work'
ws['E3'] = 'Rate'
ws['F3'] = 'Per'
ws['G3'] = 'Unit'
ws['H3'] = 'Amount'

# Item 1
ws['A4'] = 1
ws['B4'] = 100
ws['C4'] = 'm'
ws['D4'] = 'Excavation'
ws['E4'] = 50
ws['H4'] = 5000

# Item 2
ws['A5'] = 2
ws['B5'] = 50
ws['C5'] = 'cum'
ws['D5'] = 'Concrete'
ws['E5'] = 200
ws['H5'] = 10000

wb.save('test_estimate.xlsx')
print('Created test_estimate.xlsx')
"
```

### Step 3: Upload the Estimate
1. Go to the "Workslip Preview" panel (right side)
2. Click "Choose File" button in the "Upload Estimate Excel" section
3. Select your test_estimate.xlsx file
4. Click "Upload Estimate" button
5. **Expected Result**: A table appears with 2 items:
   - Row 1: Excavation | m | Qty: 100 | Rate: 50
   - Row 2: Concrete | cum | Qty: 50 | Rate: 200

### Step 4: Edit Quantities
1. In the table, find the "Qty (Executed)" column
2. Click on an empty cell and enter a number (e.g., 80)
3. **Expected Result**: The "Amount" cell updates automatically (qty * rate)
4. The "Total Executed Amount" at the bottom updates

### Step 5: Configure Tender Premium
1. Find the "T.P %" input field above the table
2. Enter a percentage (e.g., 5.5)
3. Select "Excess" or "Less" from the dropdown
4. **Expected Result**: Values are saved when you submit

### Step 6: Add Supplemental Items
1. Select a group from the left panel (e.g., "Structural")
2. Check items from the "Items in [Group]" panel
3. Click "➕ Add Supplemental Items"
4. **Expected Result**: Selected items appear in the table with a "Supplemental Items" heading

### Step 7: Clear All
1. Click "Clear All" button at the bottom right
2. **Expected Result**: Table empties, TP resets to 0, all data cleared

## 📊 Test Scenarios

### Scenario 1: Single Item Upload
- Create estimate with just 1 item
- Upload and verify it appears in table

### Scenario 2: Multiple Items
- Create estimate with 5+ items
- Upload and verify all appear correctly
- Edit various quantities
- Verify amounts calculate correctly

### Scenario 3: Supplemental Items
- Upload estimate with items
- Add supplemental items from groups
- Verify items appear with "Supplemental Items" heading
- Edit quantities for both estimate and supplemental items

### Scenario 4: Session Persistence
- Upload estimate and enter quantities
- Refresh the page (F5 or Ctrl+R)
- **Expected Result**: All data should still be there (saved in session)

### Scenario 5: Different File Formats
- Try with multi-sheet Excel file
- Try with different sheet names
- Verify it still parses correctly

## 🐛 Troubleshooting

### Server Not Running?
```bash
cd "c:\Users\HP\Documents\Windows x 1"
python manage.py runserver
```

### Changes Not Showing?
- Hard refresh: Ctrl+F5 (clears browser cache)
- Clear Django session: Delete from DB or wait for timeout

### Upload Errors?
- Check file format is .xlsx
- Verify header row is at row 3 with correct column names
- Check for non-numeric data in qty/rate columns

### Amount Not Calculating?
- Open browser console: F12 → Console tab
- Check for JavaScript errors
- Verify the qty input field has a number

## 📝 Session Data

All workslip data is stored in Django sessions:
- `ws_preview_rows` - Item list displayed in table
- `ws_estimate_rows` - Raw estimate data
- `ws_tp_percent` - Tender Premium percentage
- `ws_tp_type` - Tender Premium type (Excess/Less)
- `ws_supp_items_selected` - Added supplemental items
- `ws_exec_map` - User-entered executed quantities

Session expires after inactivity (default: 2 weeks).

## ✅ What Works

- [x] GET /workslip/ displays UI with backend groups/items
- [x] Upload Excel estimate files
- [x] Parse items (description, qty, rate, unit)
- [x] Display items in preview table
- [x] Edit executed quantities
- [x] Client-side amount calculation
- [x] Configure Tender Premium
- [x] Session persistence (data survives refresh)
- [x] Clear All functionality

## ⏳ Not Yet Implemented

- [ ] Download Workslip Excel
- [ ] Add Nth Bill generation from workslip
- [ ] Supplemental item rate lookup
- [ ] Row edit/delete functionality

## 💾 Test Files

Run automated tests:
```bash
# Unit test: Estimate parsing
python test_workslip_upload.py

# Integration test: View handler
python test_workslip_view.py

# End-to-end test: Complete flow
python test_workslip_complete_flow.py
```

All tests should pass with:
```
✓ ALL TESTS PASSED
```

## 🎯 Success Indicators

✓ Groups/items load in left panel
✓ Upload form works
✓ Table populates after upload
✓ Quantities update with correct items
✓ Amounts calculate (qty * rate)
✓ Total updates dynamically
✓ Tender Premium controls work
✓ Data persists on page refresh
✓ Clear All resets everything
✓ No browser console errors

## 📞 Questions?

Check these files:
- `WORKSLIP_IMPLEMENTATION_COMPLETE.md` - Technical details
- `WORKSLIP_STATUS.md` - Status and next steps
- `core/views.py` (lines 85-285) - workslip() function
- `core/templates/core/workslip.html` - Frontend template
