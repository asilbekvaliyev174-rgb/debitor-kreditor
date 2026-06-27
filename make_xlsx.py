import csv, zipfile, datetime

CSV = 'debitor_kreditor_umumiy.csv'
OUT = 'debitor_kreditor_umumiy.xlsx'

rows = list(csv.reader(open(CSV, encoding='utf-8-sig')))
header = rows[0]
data = [r for r in rows[1:] if r and any(c.strip() for c in r)]

def esc(s):
    return (s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
             .replace('"','&quot;'))

def colref(c):
    s = ''
    c += 1
    while c:
        c, rem = divmod(c-1, 26)
        s = chr(65+rem) + s
    return s

def num(x):
    x = (x or '').strip()
    try:
        f = float(x)
        return f
    except:
        return None

# styles: 0 default, 1 header, 2 text+border, 3 int№+border center, 4 number+border
def cell(c, r, value, style, is_number):
    ref = f'{colref(c)}{r}'
    if is_number and value is not None:
        v = repr(value) if isinstance(value, float) and value != int(value) else str(int(value)) if value == int(value) else repr(value)
        return f'<c r="{ref}" s="{style}"><v>{v}</v></c>'
    else:
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{esc(str(value))}</t></is></c>'

# build sheet rows
sheet_rows = []
# header row 1
cells = ''.join(cell(i, 1, header[i], 1, False) for i in range(len(header)))
sheet_rows.append(f'<row r="1" ht="30" customHeight="1">{cells}</row>')

r = 2
sum_d = 0.0
sum_k = 0.0
for rec in data:
    no = num(rec[0])
    inn = rec[1]
    name = rec[2]
    d = num(rec[3]); k = num(rec[4])
    if d: sum_d += d
    if k: sum_k += k
    cells = ''
    cells += cell(0, r, no if no is not None else rec[0], 3, no is not None)
    cells += cell(1, r, inn, 2, False)            # INN as text
    cells += cell(2, r, name, 2, False)
    cells += cell(3, r, d if d is not None else rec[3], 4, d is not None)
    cells += cell(4, r, k if k is not None else rec[4], 4, k is not None)
    sheet_rows.append(f'<row r="{r}">{cells}</row>')
    r += 1

# totals row
cells = ''
cells += cell(0, r, '', 5, False)
cells += cell(1, r, '', 5, False)
cells += cell(2, r, 'ЖАМИ / ИТОГО', 5, False)
cells += cell(3, r, round(sum_d, 2), 6, True)
cells += cell(4, r, round(sum_k, 2), 6, True)
sheet_rows.append(f'<row r="{r}">{cells}</row>')
last_row = r

dim = f'A1:{colref(len(header)-1)}{last_row}'
sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<dimension ref="{dim}"/>
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>
<col min="1" max="1" width="5" customWidth="1"/>
<col min="2" max="2" width="13" customWidth="1"/>
<col min="3" max="3" width="60" customWidth="1"/>
<col min="4" max="4" width="22" customWidth="1"/>
<col min="5" max="5" width="22" customWidth="1"/>
</cols>
<sheetData>
{''.join(sheet_rows)}
</sheetData>
<autoFilter ref="A1:{colref(len(header)-1)}{last_row-1}"/>
</worksheet>'''

styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1">
<numFmt numFmtId="164" formatCode="#,##0.##;[Red]-#,##0.##"/>
</numFmts>
<fonts count="3">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF305496"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="7">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="49" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
<xf numFmtId="164" fontId="2" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>'''

root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>'''

workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Умумий контрагентлар" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''

workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Дебитор ва кредиторда умумий контрагентлар</dc:title>
<dc:creator>Kiro</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
</cp:coreProperties>'''

with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml', content_types)
    z.writestr('_rels/.rels', root_rels)
    z.writestr('docProps/core.xml', core_xml)
    z.writestr('xl/workbook.xml', workbook_xml)
    z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
    z.writestr('xl/styles.xml', styles_xml)
    z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

print('Wrote', OUT)
print('Rows:', len(data), '| sum_d=', round(sum_d,2), '| sum_k=', round(sum_k,2))
