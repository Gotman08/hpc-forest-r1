"""Build a filtered Excel companion; CSV/JSON remain the complete evidence."""
import csv
import json
import math
import re
from pathlib import Path

import openpyxl
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/architecture-active'
PATH = O / 'COMPARAISON-ROMEO.xlsx'
SHEETS = [('COMPARAISON', 'Donnees comparaison'), ('REFERENCES-LES-PLUS-RAPIDES', 'References les plus rapides'), ('CAMPAGNES', 'Campagnes'),
          ('ARBRES', 'Arbres'), ('ESSAIS', 'Essais'), ('DECISIONS', 'Decisions'),
          ('APPELS-ANALYSTES-MOTHER', 'Appels'), ('DUREES-PHASES', 'Durees phases'),
          ('ENVIRONNEMENTS', 'Environnements'), ('RESSOURCES-SLURM', 'Ressources SLURM'),
          ('MESURES-BRUTES', 'Mesures brutes'), ('TENTATIVES-PREALABLES', 'Tentatives'),
          ('CHRONOLOGIE', 'Chronologie')]


def rows(name):
    with (O / (name + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def value(key, text):
    if text == '':
        return None
    identifier = key == 'id' or key.endswith(('_id', '_sha256', '_commit')) or key in {'comparison_job', 'job', 'id'}
    if not identifier and re.fullmatch(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', text):
        number = float(text)
        if math.isfinite(number) and abs(number) < 1e15:
            return number
    return text


def main():
    data = json.loads((O / 'RESULTATS.json').read_text(encoding='utf8'))
    wb = xlsxwriter.Workbook(PATH, {'strings_to_formulas': False, 'strings_to_urls': False})
    wb.set_properties({'title': 'Forest actif — comparaison ROMEO', 'author': 'HPC Forest',
                       'comments': 'Imported evidence with formula-based speedup calculations. See RAPPORT.md and CSV/JSON for complete provenance.'})
    wb.set_calc_mode('auto')
    title = wb.add_format({'font_name': 'Arial', 'font_size': 19, 'bold': True, 'font_color': '#152239'})
    normal = wb.add_format({'font_name': 'Arial', 'font_size': 10})
    wrap = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'text_wrap': True, 'valign': 'top'})
    numeric = wb.add_format({'font_name': 'Arial', 'num_format': '0.0000', 'font_size': 10})
    ratio = wb.add_format({'font_name': 'Arial', 'num_format': '0.0000" ×"', 'font_size': 10})
    first = wb.add_worksheet('Lire')
    summary = wb.add_worksheet('Comparaison')
    first.hide_gridlines(2)
    first.set_column('A:A', 3)
    first.set_column('B:B', 100)
    first.write('B2', 'Forest actif — mesures sur ROMEO', title)
    intro = [
        'Ce classeur accompagne RAPPORT.md et ANALYSE.md. Il conserve les valeurs sources dans les onglets de données et calcule les speedups de la comparaison par formules.',
        f"État à la génération : {data['summary']['new_finished']} / 21 campagnes complètes ; {data['summary']['measured_rows']} / 57 lignes remesurées, sur 62 lignes documentaires.",
        'Le rapport ancien / actif est supérieur à 1 si le nouveau programme est plus rapide. Les barres min–max décrivent les blocs de mesure, pas un intervalle de confiance.',
        'Une comparaison peut apparaître sur plusieurs lignes documentaires : ces lignes ne sont pas des expériences indépendantes. Les cinq références sans sources ou données exactes restent sans valeur remesurée.',
        'Les mesures old/new sont faites dans la même allocation ROMEO. Les speedups publiés sur un autre matériel restent séparés. Voir les compilateurs, empreintes, contrôles et limites dans les onglets et le rapport.',
        'Une recherche complète retenue par programme ne prouve pas un effet causal de l’architecture. Les essais ratés et les coûts connus sont conservés séparément. Les usages manquants ne valent pas zéro.',
        'Chaque onglet de données vient du CSV homonyme, avec filtres et en-têtes figés. Les identifiants restent textuels. Aucun texte importé n’est interprété comme une formule.',
        'Les temps des phases peuvent se chevaucher : ne pas additionner leurs durées pour reconstituer le temps mural. Les GPU-heures réservées ne sont pas une mesure d’utilisation du GPU.',
    ]
    for i, text in enumerate(intro, 4):
        first.write(i, 1, text, wrap)
        first.set_row(i, 45)
    first.write_url('B15', "internal:'Comparaison'!A1", string='Ouvrir la comparaison des speedups')
    clipped = []
    counts = {}
    for stem, name in SHEETS:
        table = rows(stem)
        fields = list(table[0]) if table else []
        ws = wb.add_worksheet(name)
        ws.freeze_panes(1, 2)
        ws.set_default_row(24)
        ws.set_row(0, 40)
        ws.hide_gridlines(2)
        for j, field in enumerate(fields):
            ws.set_column(j, j, 26 if len(field) < 30 else 42, normal)
        for i, record in enumerate(table, 1):
            for j, key in enumerate(fields):
                val = value(key, record[key])
                if isinstance(val, str) and len(val) > 32000:
                    clipped.append({'sheet': name, 'row': i+1, 'column': key, 'characters': len(val)})
                    val = val[:31930] + '\n[Suite dans le CSV/JSON complet ; limite de cellule Excel.]'
                ws.write(i, j, val, numeric if isinstance(val, float) else normal)
        if fields:
            ws.add_table(0, 0, len(table), len(fields)-1,
                         {'name': 'Evidence'+str(len(counts)+1), 'style': 'Table Style Medium 2',
                          'columns': [{'header': f} for f in fields]})
        counts[name] = len(table)

    fields = [('id', 'Observation'), ('label', 'Description'), ('n', 'Taille n'), ('threads', 'Threads'),
              ('published_hardware', 'Matériel publié'), ('hardware', 'Matériel ROMEO'),
              ('published_speedup', 'Speedup publié'), ('baseline_ms', 'Naïf (ms)'),
              ('reference_ms', 'Référence (ms)'), ('old_selected_ms', 'Ancien Forest (ms)'),
              ('new_selected_ms', 'Forest actif (ms)'), ('reference_speedup', 'Speedup référence'),
              ('old_selected_speedup', 'Speedup ancien'), ('new_selected_speedup', 'Speedup actif'),
              ('new_vs_old', 'Ancien / actif'), ('new_vs_old_min', 'Rapport min par bloc'),
              ('new_vs_old_max', 'Rapport max par bloc'), ('verdict', 'Constat')]
    formula_ratios = {'reference_speedup': ('baseline_ms', 'reference_ms'),
                      'old_selected_speedup': ('baseline_ms', 'old_selected_ms'),
                      'new_selected_speedup': ('baseline_ms', 'new_selected_ms'),
                      'new_vs_old': ('old_selected_ms', 'new_selected_ms')}
    source = rows('COMPARAISON')
    positions = {key: j for j, (key, _) in enumerate(fields)}
    summary.hide_gridlines(2)
    summary.freeze_panes(1, 2)
    summary.set_column(0, 0, 27, normal)
    summary.set_column(1, 1, 42, wrap)
    summary.set_column(2, 3, 13, normal)
    summary.set_column(4, 5, 34, wrap)
    summary.set_column(6, 16, 21, numeric)
    summary.set_column(17, 17, 51, wrap)
    summary.set_row(0, 42)
    formula_count = 0
    for i, record in enumerate(source, 1):
        summary.set_row(i, 48)
        for j, (key, _) in enumerate(fields):
            val = value(key, record[key])
            if key in formula_ratios:
                numerator, denominator = formula_ratios[key]
                a, b = [xl_rowcol_to_cell(i, positions[k]) for k in (numerator, denominator)]
                formula = f'=IF(AND(ISNUMBER({a}),ISNUMBER({b}),{b}>0),{a}/{b},"")'
                summary.write_formula(i, j, formula, ratio, '' if val is None else val)
                formula_count += 1
            else:
                fmt = ratio if key in {'published_speedup', 'new_vs_old_min', 'new_vs_old_max'} else numeric if isinstance(val, float) else wrap
                summary.write(i, j, val, fmt)
    summary.add_table(0, 0, len(source), len(fields)-1, {'name': 'Speedups', 'style': 'Table Style Medium 2',
                      'columns': [{'header': label} for _, label in fields]})
    for text, color in [('Nouveau plus rapide', '#DFF3EC'), ('Ancien plus rapide', '#FCE6DC')]:
        fmt = wb.add_format({'bg_color': color})
        summary.conditional_format(1, 17, len(source), 17, {'type': 'text', 'criteria': 'containing', 'value': text, 'format': fmt})
    first.write('B17', f'Cellules raccourcies pour la limite Excel : {len(clipped)}. Les fichiers CSV et JSON conservent tout le texte.', wrap)
    first.set_row(16, 35)
    wb.close()
    result = {'sheets': counts, 'summary_rows': len(source), 'formula_count': formula_count,
              'clipped_cells': clipped, 'path': str(PATH), 'recalculated': False}
    (R / 'workbook-validation.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k != 'clipped_cells'}))


def verify():
    wb = openpyxl.load_workbook(PATH, read_only=True, data_only=True)
    formulas = openpyxl.load_workbook(PATH, read_only=True, data_only=False)
    source = rows('COMPARAISON')
    checked = 0
    for i, record in enumerate(source, 2):
        for column, key in [(12, 'reference_speedup'), (13, 'old_selected_speedup'),
                            (14, 'new_selected_speedup'), (15, 'new_vs_old')]:
            val = wb['Comparaison'].cell(i, column).value
            assert formulas['Comparaison'].cell(i, column).data_type == 'f'
            if record[key] == '':
                assert val in {None, ''}, (i, key, val)
            else:
                assert math.isclose(float(val), float(record[key]), rel_tol=1e-10), (i, key, val, record[key])
            checked += 1
    for sheet in wb:
        for row in sheet:
            for cell in row:
                assert cell.data_type != 'e', (sheet.title, cell.coordinate, cell.value)
    receipt = json.loads((R / 'workbook-validation.json').read_text(encoding='utf8'))
    receipt.update(recalculated=True, recalculation_engine='Microsoft Excel CalculateFullRebuild',
                   verified_formula_results=checked, spreadsheet_error_cells=0)
    (R / 'workbook-validation.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps({'formula_results_verified': checked, 'error_cells': 0}))


if __name__ == '__main__':
    import sys
    verify() if '--verify' in sys.argv else main()
