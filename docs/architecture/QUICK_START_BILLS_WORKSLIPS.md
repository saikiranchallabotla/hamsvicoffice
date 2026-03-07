# Sequential Bill & Workslip Entry - Quick Start Guide

## For Users: How to Create Workslips and Bills

### Step 1: Create a Workslip from an Estimate

```
📊 Estimate (E)
    ↓ Click "W" button
📝 Workslip Entry Form
    ↓ Enter quantities & T.P.
✅ Workslip-1 Created
```

**Process**:
1. Go to your saved estimate in "Saved Works"
2. Look for the bold **"W"** button in the workflow section
3. You'll be taken to the Workslip Entry form
4. Enter:
   - **Executed Quantities**: How much work was done for each item
   - **Temporary Works %**: Any temporary charges (e.g., scaffolding) as %
   - **Measurement Book** (optional): Reference details
5. Click **"Save & Continue"**
6. Done! Workslip-1 is now saved

### Step 2: Create a Bill from a Workslip

```
📝 Workslip-1 (W1)
    ↓ Click "B" button
💳 Bill Entry Form
    ↓ Enter bill quantities & dates
✅ Bill-1 Created
```

**Process**:
1. Go to your saved Workslip-1
2. Look for the bold **"B"** button
3. You'll be taken to the Bill Entry form
4. Enter:
   - **Billed Quantities**: Same as workslip (or less)
   - **Measurement Book Details**: M.B. reference
   - **Important Dates**:
     - DOI: Date of Issue
     - DOC: Date of Completion
     - DOMR: Date of Measurement Report
     - DOBR: Date of Bill Raising
5. Click **"Save & Continue"**
6. Done! Bill-1 is now saved

### Step 3: Create Workslip-2 & Bill-2

```
📝 Workslip-1
    ↓ Click "W" in the workflow
📝 Workslip-2 Entry Form
    ↓ Shows Workslip-1 quantities
    ↓ Enter additional quantities
✅ Workslip-2 Created
    ↓ Click "B"
💳 Bill-2 Entry Form
    ↓ Shows Bill-1 deductions automatically
    ↓ Enter new quantities
✅ Bill-2 Created
```

**Key Difference**:
- **Workslip-2**: Shows previous Workslip-1 data for reference
- **Bill-2**: Automatically shows Bill-1 deductions (what was already billed)
  - Formula: Bill-2 Amount = (Workslip-2 Qty - Bill-1 Qty) × Rate

## Understanding Deductions

### What are Deductions?

Deductions show how much of each item was already billed in the previous bill.

**Example**:
- Item "Excavation": 100m
- Bill-1: Billed 60m
- Bill-2: Till Date Qty = 90m
- **Deduction = 60m** (already billed)
- **New Billed Qty = 90m - 60m = 30m**
- **New Bill Amount = 30m × Rate**

### Automatic Deduction Calculation

When you create Bill-2:
- System pulls all items from Bill-1
- Shows quantities in "Deduct from Bill-1" column (read-only)
- Amounts are automatically calculated
- You only enter the till-date quantities

## Form Fields Explained

### Workslip Form

| Field | What It Is | Example |
|-------|-----------|---------|
| **Executed Qty** | How many units of work completed | 50 m (50 meters) |
| **T.P. %** | Temporary works charge (scaffolding, staging) | 15% |
| **M.B. No.** | Measurement book reference | MB-001 |
| **M.B. Pages** | Which pages in the M.B. | From: 1, To: 5 |

### Bill Form

| Field | What It Is | Format | Example |
|-------|-----------|--------|---------|
| **Bill Qty** | Quantity to invoice | Number | 50.00 |
| **Deduct Prev** | Auto-filled from last bill | Auto | 30.00 |
| **M.B. No.** | Measurement book | Text | MB-001 |
| **DOI** | Date bill was issued | Date | 01-Mar-2026 |
| **DOC** | Date work completed | Date | 05-Mar-2026 |
| **DOMR** | Date measurement report made | Date | 06-Mar-2026 |
| **DOBR** | Date bill was raised | Date | 07-Mar-2026 |

## Common Questions

### Q: Do I need to upload files?
**A**: No! Just enter quantities and details in the form. No file uploads needed.

### Q: Can I edit quantities after saving?
**A**: Yes! Click the bill/workslip from saved works and quantities will be editable.

### Q: What if I made a mistake?
**A**: Go to Saved Works, find the item, and click it to view/edit details.

### Q: Can I create Bill-2 before Workslip-2?
**A**: No. The system ensures:
- Estimate → Workslip → Bill → Workslip-2 → Bill-2

### Q: What's Temporary Works (T.P.)?
**A**: Extra charges for temporary structures (scaffolding, shoring, etc.)
- **Excess**: Add to bill amount
- **Deduct**: Subtract from bill amount

### Q: Are deductions calculated automatically?
**A**: Yes! For Bill-2+ onwards, deductions are auto-filled from the previous bill.

## Tips & Tricks

✅ **Always enter "Till Date Qty"** for Bill-2+
- Don't enter "new qty" - the system calculates it for you

✅ **Keep Measurement Book details consistent**
- Reference same M.B. across related bills for clarity

✅ **Use meaningful names** when saving works
- "Project A - Workslip-1" instead of "WS1"

✅ **Check the summary** before saving
- Make sure totals look correct

✅ **Dates matter**:
- DOI ≤ DOC ≤ DOMR ≤ DOBR (in chronological order)

## Visual Overview

### Workflow Breadcrumb (at top of forms)

```
[Estimate] → [Workslip-1] → [Bill-1]  ← You are here
```

- Shows which step you're on
- Color-coded for clarity
- Indicates progress through workflow

### Quantities Table

**Workslip Form**:
```
┌─────┬──────────────────┬──────┬────────┬──────┬──────────┐
│ SL  │ Item             │ Unit │ Prev   │ Rate │ Amount   │
├─────┼──────────────────┼──────┼────────┼──────┼──────────┤
│  1  │ Excavation       │ m    │ 50.00  │ 50   │ ₹ 2500   │
│  2  │ Filling          │ m³   │ 30.00  │ 100  │ ₹ 3000   │
└─────┴──────────────────┴──────┴────────┴──────┴──────────┘
        ← Enter these quantities
```

**Bill Form**:
```
┌─────┬──────────────────┬──────┬──────┬──────────────┬──────┐
│ SL  │ Item             │ Unit │ Rate │ Deduct Prev  │ Amt  │
├─────┼──────────────────┼──────┼──────┼──────────────┼──────┤
│  1  │ Excavation       │ m    │ 50   │ 50.00 (auto) │ 0 ₹  │
│  2  │ Filling          │ m³   │ 100  │ 30.00 (auto) │ ?    │
└─────┴──────────────────┴──────┴──────┴──────────────┴──────┘
        ← Enter these qty
              (auto-calculated)
```

## Support

- For technical issues: Check the system logs
- For questions: Refer to the detailed System Documentation
- For bugs: Contact your system administrator

---

**Remember**: The system guides you through the workflow. Just follow the form fields and click "Save & Continue"!
