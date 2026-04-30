# Hamsvic Office — User Guide & Walkthrough Script

This guide is written so any user can read it from top to bottom and understand
every module, every feature, how each one works, and how input files must be
formatted.

It is structured as a narration script: read it section by section and you will
have toured the entire website.

---

## 1. What Hamsvic Office Is

Hamsvic Office is a web application for government works estimating, billing,
and document generation. It is used by engineers and office staff to:

- Prepare **Estimates** from the Schedule of Rates (SOR) of their state.
- Generate **Workslips** and progressive **Bills** (1st bill, 2nd bill, … Final).
- Produce **Specification Reports**, **Forwarding Letters**, **LS Forms**, and
  **Covering Letters**.
- Manage **Temporary Works** and **Annual Maintenance Contracts (AMC)**.
- Create **Self-Formatted documents** by scanning an existing Word/PDF format
  (OCR-based template reuse).
- Save and resume any work later, organize works in **folders**, and track
  everything per project.

It is multi-tenant (organizations) and supports multiple Indian states
(Telangana, Andhra Pradesh, etc.). Access to advanced modules is controlled by
**module-wise subscriptions**.

---

## 2. Logging In

1. Open the website. You will land on the public landing page.
2. Click **Login**. Enter your **phone number or email**.
3. The system sends a **6-digit OTP** (valid for 5 minutes) via SMS or email.
4. Enter the OTP and click verify.
5. If logging in from a new device, you may be asked to **confirm the device**.
6. After login you land on the **Dashboard**.

If you don't have an account yet, click **Register**, enter phone/email, verify
with OTP, and complete your profile (name, company, designation, address, GSTIN
if applicable). GSTIN must be exactly 15 characters.

You can manage active sessions at **Account → Sessions**, revoke any individual
device, or **Logout from all devices** in one click.

---

## 3. The Dashboard

After login the Dashboard shows:

- **Module tiles** — every module the website offers (New Estimate, Workslip,
  Bill, Self-Formatted, Temporary Works, AMC).
- **Subscription state** for each module — Free / Trial / Active / Expired.
- **Announcements** — system-wide messages from the admin.
- Quick links to **My Estimates**, **My Projects**, **Saved Works**, and
  **Profile**.

Click any module tile to enter that module. If your subscription is not active,
you will see a "Start Trial" or "Subscribe" prompt.

---

## 4. Letter Settings (Do This First)

Before generating any document, go to **Letter Settings** (top menu).

Here you fill in details that get printed on every generated document:

- Office name and address (letterhead)
- Officer name(s) and designation(s) (e.g., AE, AEE, EE)
- Division / sub-division name
- Footer text
- Default signing authority

These values are saved to your profile and auto-populate into estimates,
forwarding letters, covering letters, and LS forms. You only need to set them
once and update when something changes.

---

## 5. Module: New Estimate

**Purpose:** Build a fresh estimate by picking items from your state's Schedule
of Rates and entering quantities. The system computes amounts and produces a
ready-to-print Excel estimate.

### How to use it

1. From Dashboard, click **New Estimate**. You arrive at the work-type screen.
2. Choose **Original Work** or **Repair Work**.
3. Choose the trade — **Electrical** or **Civil**.
4. You now see the **Groups** screen — every group of items in the SOR
   (e.g., "Earthwork", "Concrete", "Wiring", "Switchgear").
5. Click a group → you see all **Items** in that group with their unit, rate,
   and per (e.g., per cum, per sqm, per Rmt).
6. Tick the items you need. For each ticked item, type its **Quantity** in the
   quantity box. The amount auto-calculates as `Qty × Rate`.
7. Selected items appear in the **Output panel** on the right. You can:
   - Drag-drop to reorder.
   - Edit quantity inline.
   - Remove an item.
   - See the **Grand Total** update live.
8. Click **Save Project** to store the estimate so you can resume it later, or
   **Download** to get the final Excel file.
9. From the same screen you can also generate:
   - **Specification Report** (PDF) — the technical specifications of every
     selected item.
   - **Forwarding Letter** (PDF) — the official cover letter forwarding the
     estimate for sanction.

### Adding custom (non-SOR) items

If a particular item is not in the SOR, click **Upload Custom Items** and
upload an Excel (`.xlsx`) file with these columns in row 1:

| Item Name | Quantity | Unit | Rate | Amount |
|-----------|----------|------|------|--------|
| Sample item description | 10 | sqm | 250 | 2500 |

- `Item Name` — text description of the work item.
- `Quantity` — number.
- `Unit` — `sqm`, `cum`, `Rmt`, `nos`, `kg`, etc.
- `Rate` — decimal number, the unit rate.
- `Amount` — Qty × Rate (the system will recompute if blank).

Headers are case-insensitive. The first sheet of the workbook is read.

### Where the rates come from

Rates are loaded from the **SOR Backend Excel** for your selected state
(loaded by the admin through the Admin Panel). If your office uses a different
state's SOR, switch your state preference under **Account → Backend Preferences**.

---

## 6. Module: Workslip

**Purpose:** A workslip lists the actual quantities executed on site against
each estimate item — it is the bridge between the Estimate and the Bill.

### Two ways to make a workslip

**A) From a saved estimate (recommended)**

1. Go to **Saved Works**, open your estimate, click **Generate Workslip**.
2. The Workslip 3-panel screen opens — *Groups | Items | Output*.
3. Each estimate item is pre-loaded. Enter the **executed quantity** for each.
4. Add **supplementary items** (extras outside the original estimate) using the
   "Add Supp" button — pick from SOR groups on the left.
5. Click **Save** → workslip is stored against the parent estimate.

**B) By uploading an existing estimate Excel**

1. Go to **Workslip** from the Dashboard.
2. Upload your **estimate Excel file** (`.xlsx`).
3. The system parses item rows automatically using the standard column layout
   (see below).
4. Edit executed quantities, save or download.

### Required Excel layout for upload

The workbook should contain at least one item sheet with this row layout
(from row 1 or after a header band — the parser is fuzzy and tolerates
header rows above):

| Sl.No | Quantity | Unit | Item Description | Rate | Per | Unit | Amount |
|-------|----------|------|------------------|------|-----|------|--------|
| 1 | 10 | cum | Earthwork in excavation … | 250 | 1 | cum | 2500 |
| 2 | 50 | sqm | PCC 1:4:8 … | 600 | 1 | sqm | 30000 |

The system also reads **header fields** from anywhere on the sheet, recognizing
labels like:

- **Name of work** (also "Name of the work", "Work name")
- **Estimate Amount** / **ECV**
- **Administrative Sanction** (Admin Sanction)
- **Technical Sanction** (Tech Sanction)
- **Agreement** (also "Agt", "Agrmt")
- **Agency** (also "Contractor", "Firm")
- **MB Details** (M.B.No / Measurement Book)

You don't need them in any specific cell — type them with their label
(e.g., `Name of work : Improvements to road from X to Y`) and the system
finds them.


### Workslip output

When saved, you can download the workslip Excel which includes:

- The original estimate items with original and executed quantities side by side.
- Supplementary items in a separate band.
- Computed deviations and totals.
- The header band (Name of work, Agreement, Agency, MB Details, etc.).

---

## 7. Module: Bill

**Purpose:** Generate progressive bills — **1st Bill**, **2nd Bill**, … up to
**Final Bill** — based on the workslip. The Bill module produces the formal
Excel bill workbook plus the supporting documents.

### How to use it

1. From **Saved Works**, open the work, click **Generate Bill**.
2. Choose the **bill number**: 1st, 2nd, 3rd … or Final.
3. The Bill Entry screen opens. For each item it shows:
   - Estimated quantity
   - Quantity executed up to previous bill (auto from history)
   - Up-to-date quantity (you enter)
   - Quantity since previous bill (auto-calculated)
   - Rate, amount, deductions
4. Enter bill-level details:
   - Name of work, Agreement, Agency, MB details
   - Date of measurement, Date of bill
   - Recoveries, deductions, retention, IT/GST/labour cess
5. Click **Save Bill**. The system stores it against the work.
6. Click **Download Bill** to get the multi-sheet Excel:
   - Cover page
   - Abstract
   - Detailed measurement
   - Deductions sheet
   - Recoveries

### Sequential Bill System

Each bill is linked to the previous one. The 2nd bill picks up "up-to-previous"
values from the 1st bill automatically. **Never edit a previous bill after a
later one is created** — the chain depends on it. If you need to correct, use
**Duplicate** and start a new chain.

### Bill Document menu (LS Forms & covering letters)

From the Bill page, **Bill Document** generates:

- **LS Form** (Lump Sum payment form)
- **Movement Slip** (file-movement slip)
- **Covering Letter** for forwarding the bill

These use the templates uploaded under **Templates** (see section 11).

---

## 8. Module: Self-Formatted (OCR Templates)

**Purpose:** When your office uses a custom Word/PDF format that the system
doesn't natively support, upload it once. The OCR engine reads its layout,
detects placeholders, and lets you reuse it as a template.

### How to use it

1. From Dashboard, click **Self-Formatted**.
2. Click **Upload Document**. Accepted formats: `.docx`, `.pdf`.
3. The OCR engine processes the file and shows you the **detected
   placeholders** — words that look like fields (e.g., `Name of work`,
   `Estimate amount`, `Date`).
4. **Map** each detected placeholder to one of:
   - A built-in field (Name of work, Agency, MB No, etc.)
   - A custom placeholder (you give it a name).
5. Save the format. It now appears under **My Templates**.
6. To generate a document, click **Use** on a template. Fill the field values.
   Download the merged document.

You can **lock** a template (no further edits) and **restore from backup** if
the file is accidentally overwritten — the system keeps a database backup of
every saved template.

### Document placeholder syntax (for templates you write yourself)

Inside the Word file, write placeholders in double curly braces:

```
{{officer_name}}
{{officer_designation}}
{{work_name}}
{{estimate_amount}}
{{agreement_no}}
{{agency_name}}
{{mb_no}}
{{date}}
```

Custom placeholders may use any name in `{{snake_case}}`. Avoid spaces inside
the braces.

---

## 9. Module: Temporary Works

**Purpose:** Manage temporary, day-rate items used on site (e.g., temporary
electrical connections, scaffolding hire, dewatering pumps). Different SOR
backend with its own day-rates.

### How to use it

1. Dashboard → **Temporary Works**.
2. Choose **Electrical** or **Civil**.
3. Pick a group → pick items.
4. For each item enter:
   - **Quantity** of units (e.g., 2 pumps)
   - **Number of days** (or weeks/months) the item is required
5. The system computes amount as `Qty × Days × Day Rate`.
6. Save state, download Excel, or generate Specification Report and
   Forwarding Letter.

The day-rate sheet for debugging is at **Day Rates** (admin/debug view).

### Backend file format (admin uploads)

`temp_electrical.xlsx` and `temp_civil.xlsx` follow the same shape as the
main SOR but include a **Day Rate** column instead of a flat Rate.

---

## 10. Module: AMC (Annual Maintenance Contract)

**Purpose:** Build AMC schedules — items billed monthly/quarterly/annually
across a maintenance period.

### How to use it

1. Dashboard → **AMC**.
2. Choose Electrical or Civil.
3. Pick groups → pick items.
4. For each item enter the AMC quantity and the maintenance period.
5. Output panel shows the periodic and annual amounts.
6. Download Excel, or generate Specification Report and Forwarding Letter.

The AMC backend Excel files are `amc_electrical.xlsx` and `amc_civil.xlsx`,
loaded by admin under **Admin Panel → Data**.

---

## 11. Templates (Covering Letters & Movement Slips)

**Purpose:** Upload your office's official letter formats once and reuse them
for every bill and estimate.

### How to use it

1. Go to **Templates** (top menu).
2. Click **Upload Template**. Choose:
   - Template type — **Covering Letter** or **Movement Slip**.
   - File — a Word document (`.docx`) containing placeholders.
3. Save. The template appears in your list.
4. Click **Set Active** on the template you want used by default.
5. **Download** to grab a copy. **Delete** to remove.

When you generate a covering letter or movement slip from any module, the
active template of that type is used automatically.

### Required placeholders

The Word document may use any of these placeholders. Missing placeholders are
ignored; unmapped placeholders are left as-is.

```
{{work_name}}            {{estimate_amount}}
{{agreement_no}}         {{agency_name}}
{{mb_no}}                {{date}}
{{officer_name}}         {{officer_designation}}
{{office_name}}          {{office_address}}
{{bill_number}}          {{bill_amount}}
{{division}}             {{sub_division}}
```

The two reference files in the repo (`self_formatted/covering_letter.docx`
and `self_formatted/Q.C_Work_Memo.docx`) are good starting points.

---

## 12. Saved Works & Folders

**Purpose:** Save any in-progress work (Estimate, Workslip, Bill) and resume
it later. Organize works in folders.

### What you can do

- **Saved Works list** — every work you started or saved.
- **Resume** — opens the work where you left off.
- **Update** — overwrite an existing saved work.
- **Duplicate** — make a copy (start a new bill chain, for example).
- **Delete** — remove permanently.
- **Generate Workslip / Generate Bill** — promote an estimate forward.
- **Folders** — create, rename, delete, color-code. Drag works between folders.
- **Batch action** — bulk move, delete, or download.

Each saved work stores its full state as JSON in the database, so quantities,
items, and headers all come back exactly when you resume.

---

## 13. My Estimates & My Projects

- **My Estimates** — every completed estimate. Click to view, re-download, or
  delete. Estimates store a **rate snapshot** so amounts don't change even if
  the SOR is updated later.
- **My Projects** — earlier saved projects (the lighter, project-only save).
  Use **Load** to bring a project back into the Estimate workflow. Use
  **Create Project** to start a new empty project.

---

## 14. Subscriptions & Pricing

**Purpose:** Most modules require an active subscription. Free tier users get
limited usage; paid tiers are unlimited for the chosen duration.

### How to subscribe

1. Go to **Pricing** (or click "Subscribe" on a module tile).
2. Choose a **module** (Estimate, Workslip, Bill, Self-Formatted, Temporary
   Works, AMC) **or** a **Bundle** (all modules at a discount).
3. Choose a **duration**: 1 / 3 / 6 / 12 months.
4. Apply a **Coupon code** if you have one.
5. Review GST and total. Click **Pay**.
6. Razorpay opens. Pay by UPI, card, or net-banking.
7. On success you get an **Invoice** (downloadable from **My Invoices**) and
   the module activates instantly.

### Free trial

Most modules offer a **1-day free trial** (configurable per module). Click
**Start Trial** on a module tile to activate it once.

### My Subscription page

Lists each module, its status (Trial / Active / Expired), expiry date, and
usage so far in the current period.

---

## 15. Help Center & Support Tickets

**Purpose:** Get answers and contact support without leaving the app.

### What you'll find

- **/help/** — Help home page.
- **FAQs** — organized by category (billing, technical, data, account, etc.).
  Use the search box, mark answers helpful or not.
- **Help Guides** — long-form articles, tutorials, and release notes.
- **My Tickets** — your open and past support tickets.

### Raising a ticket

1. **Help → New Ticket**.
2. Fill: Subject, Category (general / billing / technical / bug / feature /
   account / data), Priority (low / medium / high / urgent), Description, and
   optionally the related module.
3. Attach screenshots if needed.
4. Submit. You get a unique **ticket number**.
5. Replies from support appear in the ticket conversation. You'll be notified.
6. When resolved, **rate** the support (1-5 stars) and optionally leave
   feedback.

---

## 16. Account Settings

Available under your name menu (top-right):

- **Profile** — view your details.
- **Edit Profile** — change company name, designation, address, GSTIN.
- **Change Phone** — request OTP to your new number.
- **Change Email** — request OTP to your new email.
- **Active Sessions** — list of devices you're logged in on; revoke any.
- **Logout from all devices** — single click to kill every session.
- **Backend Preferences** — choose which state's SOR to use per module.

---

## 17. Admin Panel (Admin users only)

The Admin Panel lives at **/admin-panel/** and is gated by a separate
password (set the first time at /admin-panel/security/setup/). After unlocking,
admins can:

- **Dashboard & Analytics** — total users, paying users, module usage,
  payment metrics. Per-user analytics drill-down. Export to CSV/Excel.
- **Data Management** — upload/replace/preview/download every SOR backend
  Excel (electrical, civil, temp electrical, temp civil, amc electrical, amc
  civil) per state. Auto-creates a backup before every replace.
- **Users** — list, view, edit, enable/disable, change role.
- **Modules** — edit module name, description, icon, color, trial duration,
  free-tier limit, backend file mapping.
- **Pricing** — set 1/3/6/12-month base price, sale price, GST percent,
  popular flag for each module and bundle.
- **Subscriptions** — view all active subscriptions, **grant** a free
  subscription to a user, **revoke** a subscription.
- **Tickets** — list of all tickets, assign to admin, reply, mark resolved,
  add internal notes (not visible to user).
- **Announcements** — create/edit/schedule banner or modal announcements,
  target by audience (free/paid/admin/all) or by module.
- **FAQ Management** — add/edit FAQ categories and items.
- **Payments** — full payment history with Razorpay IDs.
- **Coupons** — create discount codes (percent or flat amount), set max uses,
  validity window.
- **Lock** — relock the admin panel.

### Backend Excel file shape (what admins upload)

Each backend file is an `.xlsx` with these sheets:

**Sheet "Master Datas"** — the items database:

| Item Code | Item Description | Unit | Rate | Per |
|-----------|------------------|------|------|-----|
| E001 | Wire 4 sqmm copper FRLS | Rmt | 18.50 | Rmt |
| E002 | PVC conduit 20mm ISI | Rmt | 26.00 | Rmt |

**Sheet "Groups"** — which item belongs to which group:

| Group Name | Group Code | Item Code | Item Description |
|------------|------------|-----------|------------------|
| Wiring | GRP01 | E001 | Wire 4 sqmm copper FRLS |
| Wiring | GRP01 | E002 | PVC conduit 20mm ISI |

The Admin Panel previews the file before saving and warns if columns are
missing.

---

## 18. Multi-State Support

The website supports SOR data from multiple states. Each module can have
multiple **backends** (one per state, financial year, or work-type variant).
Admins mark one as **Default** per module.

Users override the default at **Account → Backend Preferences** by choosing
their preferred state per module.

The active backend determines which Master Datas / Groups are shown in every
module screen.

---

## 19. Quick End-to-End Walkthrough Script

Read this aloud while clicking through; you'll have used every major feature
in under ten minutes.

1. Login with phone and OTP.
2. Open **Letter Settings** and fill office and officer details. Save.
3. Click **New Estimate** → Original → Electrical → pick a group → tick five
   items → enter quantities → click **Save Project** → name it "Demo Estimate".
4. Click **Download** to grab the estimate Excel.
5. Go to **Saved Works** → open Demo Estimate → click **Generate Workslip**.
6. Enter executed quantities → click **Save**.
7. From the same record, click **Generate Bill** → choose **1st Bill** → fill
   bill header (Agreement, Agency, MB No, dates) → enter up-to-date quantities
   → **Save** → **Download Bill**.
8. From the bill page, click **Bill Document → Covering Letter** → Word file
   downloads using your active template.
9. Click **Self-Formatted** → upload an existing Word format → map placeholders
   → save template → click **Use** → fill values → download merged document.
10. Visit **Help** to browse FAQs. Submit a test ticket. Visit **My
    Subscription** to confirm module access.
11. Logout from **Account → Sessions → Logout from all devices**.

That covers every user-facing module.

---

## 20. Glossary

- **SOR** — Schedule of Rates. The official rate book published by the state
  PWD/government for standard work items.
- **ECV** — Estimated Contract Value.
- **Workslip** — record of executed quantities per estimate item.
- **LS Form** — Lump Sum payment form.
- **MB** — Measurement Book; the field record. "MB No" = the page reference
  in that book.
- **Supplementary Item** — work item executed but not in the original
  estimate; added during workslip/bill stage.
- **AMC** — Annual Maintenance Contract.
- **Backend (file)** — the SOR Excel that powers a module for a state.
- **Saved Work** — any in-progress estimate / workslip / bill kept for later.
- **Bundle** — a single subscription that unlocks all modules.

---

## 21. Where to Get Help

- In-app Help Center: **/help/**
- Raise a ticket: **/help/tickets/new/**
- Email: **support@hamsvic.com**

Read this guide once and you have toured the entire website. Keep it handy
when training new staff.
