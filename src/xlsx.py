"""
A very small Excel writer.

The course works in Excel, so the results are shipped as a workbook as well
as CSV. There is no spreadsheet library installed and we did not want this
project to need one, so this writes the handful of XML parts that make up an
.xlsx file directly. It supports exactly what we need: several sheets, a bold
header row, text and numbers. Nothing else.
"""

import zipfile
from xml.sax.saxutils import escape


def col_letter(n):
    """1 -> A, 2 -> B, 27 -> AA."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, value, style=0):
    if value is None:
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>'
            f'{escape(str(value))}</t></is></c>')


def _sheet_xml(rows, header=True):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/'
           'spreadsheetml/2006/main"><sheetData>']
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{col_letter(c)}{r}", v, 1 if (header and r == 1) else 0)
            for c, v in enumerate(row, start=1))
        out.append(f'<row r="{r}">{cells}</row>')
    out.append("</sheetData></worksheet>")
    return "".join(out)


STYLES = '''<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf/></cellStyleXfs>
<cellXfs count="2"><xf xfId="0"/><xf xfId="0" fontId="1" applyFont="1"/></cellXfs>
</styleSheet>'''


def write(path, sheets):
    """
    sheets: list of (name, rows), where rows is a list of lists. The first
    row of each sheet is treated as a header and set in bold.
    """
    n = len(sheets)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        types = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<Types xmlns="http://schemas.openxmlformats.org/package/'
                 '2006/content-types">',
                 '<Default Extension="rels" ContentType="application/'
                 'vnd.openxmlformats-package.relationships+xml"/>',
                 '<Default Extension="xml" ContentType="application/xml"/>',
                 '<Override PartName="/xl/workbook.xml" ContentType="application/'
                 'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
                 '<Override PartName="/xl/styles.xml" ContentType="application/'
                 'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        for i in range(1, n + 1):
            types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                         'ContentType="application/vnd.openxmlformats-'
                         'officedocument.spreadsheetml.worksheet+xml"/>')
        types.append("</Types>")
        z.writestr("[Content_Types].xml", "".join(types))

        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" '
                   'Target="xl/workbook.xml"/></Relationships>')

        wb = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<workbook xmlns="http://schemas.openxmlformats.org/'
              'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
              'officeDocument/2006/relationships"><sheets>']
        rels = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships">']
        for i, (name, _) in enumerate(sheets, start=1):
            safe = escape(name[:31])
            wb.append(f'<sheet name="{safe}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.'
                        'openxmlformats.org/officeDocument/2006/relationships/'
                        f'worksheet" Target="worksheets/sheet{i}.xml"/>')
        rels.append(f'<Relationship Id="rId{n+1}" Type="http://schemas.'
                    'openxmlformats.org/officeDocument/2006/relationships/'
                    'styles" Target="styles.xml"/>')
        wb.append("</sheets></workbook>")
        rels.append("</Relationships>")
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        z.writestr("xl/styles.xml", STYLES)

        for i, (_, rows) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))
    return path
