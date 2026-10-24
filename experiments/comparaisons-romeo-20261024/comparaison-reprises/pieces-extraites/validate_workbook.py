"""Read-only validation of exported XLSX formula caches against independent JSON."""
import csv
import datetime
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/comparaison-reprises'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
data = json.loads((O / 'RESULTATS.json').read_text(encoding='utf8'))
path = O / 'COMPARAISON.xlsx'
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    sheets = {}
    for s in workbook.findall('m:sheets/m:sheet', NS):
        target = targets[s.attrib[REL]]
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheets[s.attrib['name']] = ET.fromstring(archive.read(target))
    assert list(sheets) == ['Comparaison', 'Forest', 'Arbres', 'Essais', 'Mesures']
    cells = {c.attrib['r']: c for c in sheets['Comparaison'].findall('.//m:c', NS)}
    compared = 0
    for index, row in enumerate(data['rows'], 6):
        keys = ['published_speedup', 'previous_reference_speedup', 'reference_speedup',
                'previous_forest_speedup', 'old_selected_speedup', 'new_selected_speedup',
                'new_vs_old', 'new_vs_reference']
        for col, key in zip('BCDEFGHI', keys):
            if row[key] is None:
                continue
            observed = float(cells[col + str(index)].find('m:v', NS).text)
            assert math.isfinite(observed) and math.isclose(observed, row[key], rel_tol=1e-10, abs_tol=1e-12), (index, col)
            compared += 1
    formulas = []
    for name, sheet in sheets.items():
        for c in sheet.findall('.//m:c', NS):
            assert c.attrib.get('t') != 'e', (name, c.attrib['r'])
            if c.find('m:f', NS) is not None:
                value = c.find('m:v', NS)
                assert value is not None and math.isfinite(float(value.text)), (name, c.attrib['r'])
                formulas.append((name, c.attrib['r']))
    assert len(formulas) == 315
with (O / 'COMPARAISON.csv').open(encoding='utf-8-sig', newline='') as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == len(data['rows']) == 35
for actual, expected in zip(rows, data['rows']):
    assert actual['id'] == expected['id']
    for key in ['reference_speedup', 'old_selected_speedup', 'new_selected_speedup', 'new_vs_old']:
        assert math.isclose(float(actual[key]), expected[key], rel_tol=1e-12)
runtime = json.loads((R / 'workbook-preview/validation.json').read_text())
assert runtime['all_primary_ratios_match_independent_python']
assert runtime['all_secondary_ratios_match_independent_python']
assert json.loads((R / 'workbook-preview/errors.json').read_text()) == []
report = {**runtime, 'xlsx_zip_integrity': True, 'exported_formula_cells_with_numeric_cache': len(formulas),
          'exported_primary_values_compared': compared, 'csv_rows_verified': len(rows),
          'formula_error_cells': 0, 'xlsx_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Artifact-tool live calculation and rendering; independent XLSX XML/cache and CSV checks. Native Microsoft Excel was not launched.'}
(O / 'VALIDATION-CLASSEUR.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps(report, ensure_ascii=False))
