"""
Zone / Project-Location policy for estimates.

An estimate's "Project Location" is a two-level choice: a Zone (1-3) and,
within it, a location category (GHMC, Rural Area, ...). That pair drives two
things in every rate calculation:

  * **Labour rates** -- the backend workbooks store Zone-1 labour rates only.
    Zone 2 and Zone 3 rates are derived by subtracting a flat per-day amount
    (see ``ZONE_LABOUR_DEDUCTION``) rather than by keeping duplicate rate
    tables.
  * **Area allowance** -- the "Add GHMC allowance @ N%" row inside an item
    block. The applicable percentage comes from the admin-uploaded Area
    Allowance sheet (:class:`core.models.AreaAllowanceUpload`), looked up by
    (zone, location).

Both are carried through the existing estimate plumbing as a single opaque
string -- the value already stored in ``session["project_area"]``,
``job.result["project_area"]`` and ``work_data["project_area"]`` -- encoded as
``"<zone_code>:<location_code>"``, e.g. ``"zone_2:industrial_area"``.

The two legacy values remain valid and keep their exact original meaning, so
estimates saved before this feature existed still reproduce byte-identical
rates:

  ``"municipal"``      -> Zone 1, workbook's baked-in allowance percentage
  ``"non_municipal"``  -> Zone 1, allowance zeroed out
"""

import re
import time

# ---------------------------------------------------------------------------
# Zone / location catalogue
# ---------------------------------------------------------------------------

# Mirrors the SOR Area Allowance table: three zones, two location categories
# each. ``group`` is the sheet's intermediate heading (merged across both
# categories) and is only used when reading an uploaded sheet. ``aliases``
# are extra spellings accepted from an upload.
ZONES = [
    {
        "code": "zone_1",
        "label": "Zone 1",
        "locations": [
            {"code": "ghmc", "label": "GHMC",
             "group": "Municipal Corporation", "aliases": []},
            {"code": "other_than_ghmc", "label": "Other than GHMC",
             "group": "Municipal Corporation", "aliases": []},
        ],
    },
    {
        "code": "zone_2",
        "label": "Zone 2",
        "locations": [
            {"code": "municipal_area", "label": "Municipal Area or District HQ",
             "group": "", "aliases": ["Municipal Area", "District HQ"]},
            {"code": "industrial_area", "label": "Industrial Area",
             "group": "", "aliases": []},
        ],
    },
    {
        "code": "zone_3",
        "label": "Zone 3",
        "locations": [
            {"code": "upto_16_kms", "label": "Agency or Tribal Area (Upto 16 Kms)",
             "group": "Agency or Tribal Area",
             "aliases": ["Upto 16 Kms", "Up to 16 Km", "Rural Area"]},
            {"code": "beyond_16_kms", "label": "Agency or Tribal Area (Beyond 16 Kms)",
             "group": "Agency or Tribal Area",
             "aliases": ["Beyond 16 Kms", "Beyond 16 Km", "Tribal Area"]},
        ],
    },
]

# Flat rupee amount deducted from every Zone-1 labour rate in the backend.
ZONE_LABOUR_DEDUCTION = {
    "zone_1": 0.0,
    "zone_2": 40.0,
    "zone_3": 80.0,
}

DEFAULT_ZONE = "zone_1"
DEFAULT_LOCATION = "ghmc"
# What a fresh estimate starts on. Resolves identically to the legacy
# "municipal" value until an Area Allowance sheet is uploaded.
DEFAULT_AREA = "zone_1:ghmc"

# Legacy session values that predate zone selection.
LEGACY_MUNICIPAL = "municipal"
LEGACY_NON_MUNICIPAL = "non_municipal"

_ZONE_BY_CODE = {z["code"]: z for z in ZONES}
_LOCATION_LABELS = {
    loc["code"]: loc["label"] for z in ZONES for loc in z["locations"]
}
_ZONE_OF_LOCATION = {
    loc["code"]: z["code"] for z in ZONES for loc in z["locations"]
}


def zone_label(zone_code):
    z = _ZONE_BY_CODE.get(zone_code)
    return z["label"] if z else ""


def location_label(location_code):
    return _LOCATION_LABELS.get(location_code, "")


def locations_for_zone(zone_code):
    z = _ZONE_BY_CODE.get(zone_code)
    return list(z["locations"]) if z else []


def is_valid_pair(zone_code, location_code):
    return _ZONE_OF_LOCATION.get(location_code) == zone_code


def encode(zone_code, location_code):
    """Build the opaque ``project_area`` string for a zone/location pair."""
    return f"{zone_code}:{location_code}"


def split(area_value):
    """
    Decode a ``project_area`` value into ``(zone_code, location_code)``.

    Legacy values map onto Zone 1; ``"non_municipal"`` has no location
    category of its own and yields ``(zone_1, None)``.
    """
    value = (area_value or "").strip()
    if not value or value == LEGACY_MUNICIPAL:
        return DEFAULT_ZONE, DEFAULT_LOCATION
    if value == LEGACY_NON_MUNICIPAL:
        return DEFAULT_ZONE, None
    if ":" in value:
        zone_code, _, location_code = value.partition(":")
        if is_valid_pair(zone_code, location_code):
            return zone_code, location_code
    # Unrecognised -- fall back to today's default rather than raising, so a
    # stale saved work can still be reopened.
    return DEFAULT_ZONE, DEFAULT_LOCATION


# ---------------------------------------------------------------------------
# Parsing the admin-uploaded Area Allowance sheet
# ---------------------------------------------------------------------------

# Column headings the upload must provide (matched case/space-insensitively).
AREA_ALLOWANCE_COLUMNS = {
    "zone": ("zone",),
    "location": ("projectlocationcategory", "locationcategory", "projectlocation", "location"),
    "percent": ("areaallowancepercentage", "areaallowancepercent", "areaallowance",
                "allowancepercentage", "allowancepercent", "percentage", "percent"),
}

_ROMAN_ZONES = {"i": "zone_1", "ii": "zone_2", "iii": "zone_3"}


def _squash(text):
    """Lowercase and drop everything that isn't a letter or digit."""
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def normalize_header(text):
    """Map a spreadsheet column heading onto 'zone'/'location'/'percent'."""
    key = _squash(text)
    for field, aliases in AREA_ALLOWANCE_COLUMNS.items():
        if key in aliases:
            return field
    return None


def normalize_zone(text):
    """'Zone 1' / 'zone-1' / 'Zone-I' / '1' -> 'zone_1'. None if unrecognised."""
    key = _squash(text)
    if not key:
        return None
    if key in _ZONE_BY_CODE:
        return key
    m = re.fullmatch(r"zone(\d+)", key) or re.fullmatch(r"(\d+)", key)
    if m:
        code = f"zone_{m.group(1)}"
        return code if code in _ZONE_BY_CODE else None
    m = re.fullmatch(r"zone([ivx]+)", key) or re.fullmatch(r"([ivx]+)", key)
    if m:
        return _ROMAN_ZONES.get(m.group(1))
    return None


def _build_location_index():
    """Every spelling that resolves to a location code: the code itself, its
    display label, its ``group`` + label combined (how a cross-tab sheet
    stacks them), and any explicit aliases."""
    index = {}
    for zone in ZONES:
        for loc in zone["locations"]:
            group = loc.get("group") or ""
            spellings = [loc["code"], loc["label"]] + list(loc.get("aliases") or [])
            for alias in list(spellings):
                if group:
                    spellings.append(f"{group} {alias}")
            for spelling in spellings:
                index.setdefault(_squash(spelling), loc["code"])
    return index


_LOCATION_BY_SQUASHED = _build_location_index()


def normalize_location(text):
    """'Other than GHMC' / 'other_than_ghmc' -> 'other_than_ghmc'. None if unrecognised."""
    return _LOCATION_BY_SQUASHED.get(_squash(text))


def location_group(location_code):
    """The sheet's intermediate heading above this category, if it has one."""
    for zone in ZONES:
        for loc in zone["locations"]:
            if loc["code"] == location_code:
                return loc.get("group") or ""
    return ""


def normalize_percent(value):
    """
    Read an allowance percentage from a cell.

    Accepts ``40``, ``"40%"``, ``"40 %"`` and ``0.4`` (what pandas returns for
    a percentage-formatted cell). Values at or below 1 are read as fractions,
    which is safe here because these allowances are always tens of percent.
    Returns None when the cell holds no usable number.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        had_percent = "%" in text
        try:
            number = float(text.replace("%", "").replace(",", "").strip())
        except ValueError:
            return None
        if not had_percent and 0 < number <= 1:
            number *= 100
        return number
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if 0 < number <= 1:
        number *= 100
    return number


def expected_pairs():
    """Every (zone_code, location_code) an upload is expected to cover."""
    return [(z["code"], loc["code"]) for z in ZONES for loc in z["locations"]]


def build_row(zone_code, location_code, percent):
    return {
        "zone": zone_code,
        "zone_label": zone_label(zone_code),
        "location": location_code,
        "location_label": location_label(location_code),
        "percent": float(percent),
    }


# ---------------------------------------------------------------------------
# Area-allowance lookup (admin-uploaded sheet), with a short-lived cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 60
_allowance_cache = {"expires": 0.0, "map": {}, "loaded": False}


def invalidate_area_allowance_cache():
    """Called after an admin uploads/clears the Area Allowance sheet."""
    _allowance_cache["expires"] = 0.0
    _allowance_cache["map"] = {}
    _allowance_cache["loaded"] = False


def area_allowance_map():
    """
    ``{(zone_code, location_code): percent}`` from the latest uploaded sheet.
    Empty dict when nothing has been uploaded (or the DB isn't reachable).
    """
    now = time.time()
    if _allowance_cache["loaded"] and now < _allowance_cache["expires"]:
        return _allowance_cache["map"]
    try:
        from core.models import AreaAllowanceUpload
        current = AreaAllowanceUpload.current()
        mapping = current.percent_map() if current else {}
    except Exception:
        mapping = {}
    _allowance_cache["map"] = mapping
    _allowance_cache["expires"] = now + _CACHE_TTL_SECONDS
    _allowance_cache["loaded"] = True
    return mapping


def has_area_allowance_data():
    return bool(area_allowance_map())


def allowance_version():
    """
    A cheap fingerprint of the current allowance figures, for inclusion in
    rate-cache keys so an admin upload invalidates memoised rates.
    """
    mapping = area_allowance_map()
    if not mapping:
        return "none"
    return "|".join(f"{z}:{l}={p}" for (z, l), p in sorted(mapping.items()))


def area_allowance_percent(zone_code, location_code):
    """
    The uploaded allowance percentage for this pair, or ``None`` when the
    admin hasn't provided one.
    """
    if not location_code:
        return None
    return area_allowance_map().get((zone_code, location_code))


# ---------------------------------------------------------------------------
# Policy resolution
# ---------------------------------------------------------------------------

def resolve(area_value):
    """
    Turn a ``project_area`` string into the numbers the rate maths needs::

        {
          'zone':               'zone_2',
          'location':           'industrial_area' or None,
          'labour_deduction':   40.0,      # rupees off each Zone-1 labour rate
          'allowance_percent':  25.0,      # or None = keep the workbook's own
        }

    ``allowance_percent is None`` means "leave the block's baked-in
    percentage alone", which is what reproduces today's Municipal behaviour.
    """
    zone_code, location_code = split(area_value)
    deduction = ZONE_LABOUR_DEDUCTION.get(zone_code, 0.0)

    percent = area_allowance_percent(zone_code, location_code)
    if percent is None:
        # No uploaded figure for this pair. Zone 1 + GHMC keeps the workbook's
        # own baked-in percentage (the historical "Municipal" behaviour);
        # every other combination -- including the legacy "non_municipal" --
        # gets no allowance rather than an unrelated one.
        if zone_code == DEFAULT_ZONE and location_code == DEFAULT_LOCATION:
            percent = None
        else:
            percent = 0.0

    return {
        "zone": zone_code,
        "location": location_code,
        "labour_deduction": float(deduction),
        "allowance_percent": percent,
    }


def describe(area_value):
    """Human-readable label, e.g. ``"Zone 2 - Industrial Area"``."""
    zone_code, location_code = split(area_value)
    if location_code is None:
        return "Non-Municipal Area"
    return f"{zone_label(zone_code)} - {location_label(location_code)}"
