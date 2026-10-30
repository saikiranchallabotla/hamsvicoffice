"""
Store calculated values next to the formulas in generated .xlsx files.

openpyxl writes formulas without their results, relying on the spreadsheet
app to recalculate when the file is opened. Desktop Excel does, but phone
viewers (iOS Files / Quick Look, WhatsApp and Gmail previews, Google Drive
preview, most Android viewers) only show the stored result, so rates,
amounts and totals appeared blank, 0 or wrong on phones.

fill_cached_values() evaluates every formula with pycel and writes each
result into the cell's <v> element. The formulas themselves are untouched
and the workbook keeps fullCalcOnLoad, so Excel still recalculates. Any
failure returns the original bytes unchanged - never a broken download.
"""
import io
import logging
import numbers
import posixpath
import zipfile

from lxml import etree

logger = logging.getLogger(__name__)

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

_NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_NS_PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
_EXCEL_ERRORS = {'#NULL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!', '#N/A'}

# Skip absurdly large workbooks rather than delay the download.
MAX_FORMULAS = 50000


def _sheet_paths(zf):
    """Map sheet name -> path of its XML part inside the zip."""
    wb = etree.fromstring(zf.read('xl/workbook.xml'))
    rels = etree.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    targets = {
        r.get('Id'): r.get('Target')
        for r in rels.iter('{%s}Relationship' % _NS_PKG_REL)
    }
    paths = {}
    for sheet in wb.iter('{%s}sheet' % _NS_MAIN):
        target = targets.get(sheet.get('{%s}id' % _NS_REL))
        if not target:
            continue
        if target.startswith('/'):
            path = target.lstrip('/')
        else:
            path = posixpath.normpath(posixpath.join('xl', target))
        paths[sheet.get('name')] = path
    return paths


def _missing_value_cells(root):
    """Formula cells in a sheet XML that have no stored value yet."""
    cells = []
    for c in root.iter('{%s}c' % _NS_MAIN):
        if c.find('{%s}f' % _NS_MAIN) is None:
            continue
        v = c.find('{%s}v' % _NS_MAIN)
        if v is None or v.text in (None, ''):
            cells.append(c)
    return cells


def _set_value(cell, value):
    """Write a pycel result into <c>. Returns False if it can't be stored."""
    if isinstance(value, bool):
        t, text = 'b', '1' if value else '0'
    elif isinstance(value, numbers.Real):
        value = float(value)
        if value != value or value in (float('inf'), float('-inf')):
            return False
        t, text = None, repr(value)
        if text.endswith('.0'):
            text = text[:-2]
    elif isinstance(value, str):
        if value in _EXCEL_ERRORS:
            return False  # leave errors for the spreadsheet app to work out
        t, text = 'str', value
    elif value is None:
        t, text = None, '0'  # Excel shows a formula pointing at an empty cell as 0
    else:
        return False

    v = cell.find('{%s}v' % _NS_MAIN)
    if v is None:
        v = etree.SubElement(cell, '{%s}v' % _NS_MAIN)
    v.text = text
    if t:
        cell.set('t', t)
    elif 't' in cell.attrib:
        del cell.attrib['t']
    return True


def fill_cached_values(data):
    """Return xlsx bytes with formula results stored; original bytes on any problem."""
    try:
        return _fill(data)
    except Exception:
        logger.warning('Could not store formula results in workbook', exc_info=True)
        return data


def _fill(data):
    zin = zipfile.ZipFile(io.BytesIO(data))
    sheet_paths = _sheet_paths(zin)

    roots, todo, total = {}, {}, 0
    for name, path in sheet_paths.items():
        if path not in zin.namelist():
            continue
        root = etree.fromstring(zin.read(path))
        cells = _missing_value_cells(root)
        if cells:
            roots[path] = root
            todo[name] = (path, cells)
            total += len(cells)
    if not total:
        return data
    if total > MAX_FORMULAS:
        logger.info('Skipping formula results: %d formulas', total)
        return data

    # Imported here so a missing package never breaks module import.
    from pycel import ExcelCompiler
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data))
    compiler = ExcelCompiler(excel=wb)

    filled = 0
    for name, (path, cells) in todo.items():
        quoted = "'%s'" % name.replace("'", "''")
        for cell in cells:
            ref = cell.get('r')
            if not ref:
                continue
            try:
                value = compiler.evaluate('%s!%s' % (quoted, ref))
            except Exception:
                continue
            if _set_value(cell, value):
                filled += 1
    if not filled:
        return data

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in roots:
                payload = etree.tostring(roots[item.filename], xml_declaration=True,
                                         encoding='UTF-8', standalone=True)
            else:
                payload = zin.read(item.filename)
            zout.writestr(item, payload)
    return out.getvalue()


class XlsxCachedValuesMiddleware:
    """Apply fill_cached_values() to every .xlsx the app sends back."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get('Content-Type', '') or ''
        if not content_type.startswith(XLSX_CONTENT_TYPE) or response.status_code != 200:
            return response

        if getattr(response, 'streaming', False):
            original = b''.join(response.streaming_content)
        else:
            original = response.content

        updated = fill_cached_values(original)
        if response.streaming:
            response.streaming_content = [updated]
        else:
            response.content = updated
        response['Content-Length'] = str(len(updated))
        return response
