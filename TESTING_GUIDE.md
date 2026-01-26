# Multi-Sheet Nth Bill Generation - Testing Guide

## Quick Start

### 1. Generate Test File (Optional)
If you want to test with a sample file, run:
```bash
python -c "
from openpyxl import Workbook
wb = Workbook()
wb.remove(wb.active)

# Create 3 test sheets
for i in range(1, 4):
    ws = wb.create_sheet(f'Bill-{i}')
    ws['A1'] = f'Project: Test {i}'
    ws['A8'] = 'Sl.No'
    ws['B8'] = 'Quantity'
    ws['C8'] = 'Unit'
    ws['D8'] = 'Description of work'
    ws['E8'] = 'Rate'
    ws['F8'] = 'Per'
    ws['G8'] = 'Unit'
    ws['H8'] = 'Amount'
    
    ws['A9'] = 1
    ws['B9'] = 100 - (i-1)*20
    ws['C9'] = 'm'
    ws['D9'] = 'Excavation'
    ws['E9'] = 50
    ws['H9'] = 5000 - (i-1)*2500
    
    ws['A10'] = 2
    ws['B10'] = 50 - (i-1)*10
    ws['C10'] = 'cum'
    ws['D10'] = 'Concrete'
    ws['E10'] = 200
    ws['H10'] = 10000 - (i-1)*5000
    
    ws['A12'] = 'Sub Total'
    ws['H12'] = 15000 - (i-1)*7500

wb.save('test_multi_bill.xlsx')
print('Created test_multi_bill.xlsx')
"
```

### 2. Test the Multi-Sheet Generation

#### Method A: Via Web Interface
1. Open http://127.0.0.1:8000/ in your browser
2. Upload your Bills.xlsx file (or test_multi_bill.xlsx)
3. Select **"Nth & Part from First Bill"** from the action dropdown
4. Fill in MB details (optional):
   - MB Measure No
   - MB Measure P.No (From/To)
   - MB Abstract No
   - MB Abstract P.No (From/To)
5. Enter Dates (optional):
   - Date of Issue
   - Date of Completion
   - Date of Measurement Report
   - Date of Bill Report
6. Click **"Generate"**
7. Download the output file

#### Method B: Via Terminal (Advanced)
```bash
python test_nth_bill_flow.py
```
This will:
- Load test_multi_bill.xlsx
- Process all 3 sheets
- Create test_nth_bill_output.xlsx
- Print detailed progress to console

### 3. Verify Results

#### Check Output File
- Download the generated Nth_Bill_from_FirstPart.xlsx (or Second_Final_from_FirstPart.xlsx)
- Look at the sheet tabs at the bottom
- Should see: **Bill-1**, **Bill-2**, **Bill-3** (or more depending on input)

#### Check Django Console
When you generate the bill, you should see in the console:
```
DEBUG: Found 3 sheets starting with 'Bill': ['Bill-1', 'Bill-2', 'Bill-3']
DEBUG: Processing 3 bill sheets total: ['Bill-1', 'Bill-2', 'Bill-3']
DEBUG: Processing sheet 1/3: 'Bill-1'
DEBUG: Found header row 8 in sheet 'Bill-1'
DEBUG: Parsed 2 items from sheet 'Bill-1'
DEBUG: Using active sheet for output, naming it 'Bill-1'
DEBUG: Populating sheet 'Bill-1' with 2 items
DEBUG: Populated sheet 'Bill-1' successfully
DEBUG: Processing sheet 2/3: 'Bill-2'
DEBUG: Found header row 8 in sheet 'Bill-2'
DEBUG: Parsed 2 items from sheet 'Bill-2'
DEBUG: Created new sheet 'Bill-2'
DEBUG: Populating sheet 'Bill-2' with 2 items
DEBUG: Populated sheet 'Bill-2' successfully
DEBUG: Processing sheet 3/3: 'Bill-3'
DEBUG: Found header row 8 in sheet 'Bill-3'
DEBUG: Parsed 2 items from sheet 'Bill-3'
DEBUG: Created new sheet 'Bill-3'
DEBUG: Populating sheet 'Bill-3' with 2 items
DEBUG: Populated sheet 'Bill-3' successfully
DEBUG: Created 3 output sheets total
```

## Sheet Detection Rules

The system tries to detect bill sheets in this order:

### Rule 1: "Bill" Prefix (Most Common)
```
Bill-1, Bill-2, Bill-3
or
Bill 1, Bill 2, Bill 3
or just
Bill
```

### Rule 2: Header-Based Detection (For Custom Names)
If sheets don't start with "Bill", it looks for sheets with these headers:
- **First Bills**: Column A = "Sl.No", Column B = "Quantity", Column D = "Item" or "Description"
- **Nth Bills**: Column A = "Sl.No", Column C = "Quantity Till Date"

### Rule 3: Non-Empty Sheets
If Rules 1 & 2 don't find anything, it uses all sheets that have content (max_row > 1)

### Rule 4: First Sheet Fallback
If nothing else matches, uses the first worksheet in the file

## Troubleshooting

### Issue: Only 1 Bill in Output (Expected Multiple)

**Check 1: Sheet Names**
- Verify sheets are named with "Bill" prefix (Bill-1, Bill-2, etc.)
- If not, check Django console for what sheets were detected

**Check 2: Header Rows**
- Ensure each sheet has proper headers:
  - Row 8 (or similar) with columns: Sl.No, Quantity, Unit, Description, Rate, Per, Unit, Amount
- Look for console message "Found header row X" for each sheet

**Check 3: Data Rows**
- Each sheet must have at least one data row with an amount value
- Look for console message "Parsed X items from sheet" where X > 0

**Check 4: Console Output**
- Open Django terminal where server is running
- Re-run the generation
- Look for:
  - How many sheets were detected
  - Were all sheets processed
  - Any sheets skipped due to "No items found"

### Issue: File Upload Fails

**Solution**:
- File must be Excel format (.xlsx)
- File should contain at least one sheet with bill data
- Column structure should match the expected format

### Issue: Console Shows Sheet Detection But Nothing Generated

**Check**:
1. Are items being parsed? (Look for "Parsed X items")
2. If "Parsed 0 items", check:
   - Header row detection is correct
   - Data rows have amount values in column H
   - No "Sub Total" or "Total" rows are appearing as items

## File Locations

- **Main Code**: core/views.py (lines ~1796-1820 for First→Nth, ~1940-1970 for Nth→Nth)
- **Test Files**: 
  - test_multi_bill.xlsx (generated by script)
  - test_nth_bill_output.xlsx (output from test_nth_bill_flow.py)
  - test_multi_sheet_handling.py (test parser)
  - test_nth_bill_flow.py (test full flow)
- **Documentation**: MULTISHEET_FIX_SUMMARY.md

## Expected Behavior Summary

| Scenario | Input | Expected Output |
|----------|-------|-----------------|
| Single Sheet | Bill.xlsx (1 sheet) | Nth_Bill_from_FirstPart.xlsx (1 sheet named "Bill") |
| Multiple Sheets | Bills.xlsx (Bill-1, Bill-2, Bill-3) | Nth_Bill_from_FirstPart.xlsx (3 sheets: Bill-1, Bill-2, Bill-3) |
| Custom Names | Sheet1, Sheet2, Sheet3 | Nth_Bill_from_FirstPart.xlsx (3 sheets: Bill-1, Bill-2, Bill-3) |

## Next Steps

1. ✅ Server is running at http://127.0.0.1:8000/
2. Test with your actual Bills.xlsx file or test_multi_bill.xlsx
3. Check console output for detailed debugging info
4. Verify output file has all expected sheets
5. If issues persist, check console output for detection/parsing errors

---
**Note**: The fix is complete and tested. All debug logging is in place to help identify any issues.
