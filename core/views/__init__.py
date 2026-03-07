"""
core/views/ package - split from monolithic views.py for maintainability.

Module organization:
  utils.py                  - Shared utility functions & constants
  home_views.py             - Home page, letter settings
  workslip_views.py         - Workslip module (upload, process, download)
  bill_parsing.py           - Excel parsing utilities for bills/estimates
  bill_excel.py             - Bill Excel workbook generation
  bill_views.py             - Bill view (main bill generation handler)
  estimate_excel.py         - Estimate Excel workbook builder
  amount_utils.py           - Amount extraction & template filling
  document_views.py         - Bill document, LS forms, covering letters
  project_views.py          - Projects, SOR data browsing, estimate download
  self_formatted_views.py   - OCR & self-formatted document system
  self_formatted_form_views.py - Self-formatted form UI & management
  tempworks_views.py        - Temporary works module
  estimate_views.py         - Estimate module views
  amc_views.py              - AMC (Annual Maintenance Contract) module
"""

import importlib as _importlib

# Dynamically import ALL names (including _underscore-prefixed) from sub-modules
_submodules = [
    'utils',
    'home_views',
    'workslip_views',
    'bill_parsing',
    'bill_excel',
    'bill_views',
    'estimate_excel',
    'amount_utils',
    'document_views',
    'project_views',
    'self_formatted_views',
    'self_formatted_form_views',
    'tempworks_views',
    'estimate_views',
    'amc_views',
]

for _mod_name in _submodules:
    _mod = _importlib.import_module(f'.{_mod_name}', __name__)
    for _attr in dir(_mod):
        if not _attr.startswith('__'):
            globals()[_attr] = getattr(_mod, _attr)

