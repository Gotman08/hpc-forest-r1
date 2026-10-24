"""Standalone scientific figure from verified paired timings; no search feedback."""
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parents[1] / 'outputs/architecture-active'
STYLES = {
    'gain': ('#007f67', 'o', 'Actif plus rapide dans chaque bloc'),
    'loss': ('#c45122', 's', 'Ancien plus rapide dans chaque bloc'),
    'mixed': ('#536579', 'D', 'Écart dans la variabilité / code identique'),
}


def main():
    data = json.loads((OUTPUT / 'RESULTATS.json').read_text(encoding='utf8'))
    unique = {}
    for row in data['rows']:
        if row.get('new_vs_old') is None:
            continue
        key = tuple(row.get(k) for k in ['comparison_job', 'case_id', 'n', 'threads', 'pattern'])
        if key in unique:
            for field in ['new_vs_old_min', 'new_vs_old_max', 'verdict']:
                assert unique[key][field] == row[field], (key, field)
        else:
            unique[key] = row
    group_order = {'cpu': 0, 'clang': 0, 'render': 1, 'gpu': 2, 'extra': 2}
    rows = sorted(unique.values(), key=lambda r: (group_order.get(r['group'], 3), r['case_id'], r['threads'], r['n'], r['pattern'], r['group']))
    assert len(rows) == data['summary']['distinct_old_new_comparisons']
    if not rows:
        raise RuntimeError('No verified comparison available')
    height = max(6.5, .37 * len(rows) + 3.6)
    fig, ax = plt.subplots(figsize=(12.4, height))
    fig.patch.set_facecolor('#fafbfd')
    ax.set_facecolor('#fafbfd')
    labels = []
    for index, row in enumerate(rows):
        verdict = row['verdict']
        style = 'gain' if verdict.startswith('Nouveau plus') else 'loss' if verdict.startswith('Ancien plus') else 'mixed'
        color, marker, _ = STYLES[style]
        low, high, center = [float(row[k]) for k in ['new_vs_old_min', 'new_vs_old_max', 'new_vs_old']]
        assert all(math.isfinite(v) and v > 0 for v in [low, high, center])
        assert low <= high
        ax.hlines(index, low, high, color=color, lw=2.1)
        ax.plot([low, high], [index, index], '|', color=color, markersize=8)
        ax.plot(center, index, marker, color=color, markersize=6.5)
        ax.text(1.015, index, f'{center:.4g} ×', transform=ax.get_yaxis_transform(), va='center', fontsize=10, color=color)
        target = f"{row['threads']} thread(s)" if row['threads'] is not None else 'GPU GH200'
        label = f"{row['case_id']} · n={row['n']:,} · {target}"
        if row['case_id'] == 'argmin':
            label += ' · décroissant' if row['pattern'] else ' · aléatoire'
        if row['case_id'] == 'popcount':
            label += ' · Clang' if 'clang' in row['group'].lower() or 'clang' in row['id'].lower() else ' · GCC'
        if row['aggregation'] != 'median':
            label += ' · ' + {'min': 'minimum', 'mean': 'moyenne'}[row['aggregation']]
        labels.append(label)
        if index % 2 == 0:
            ax.axhspan(index - .48, index + .48, color='#e9eef4', alpha=.55, zorder=-5)
    ax.set_xscale('log')
    lower = min(r['new_vs_old_min'] for r in rows)
    upper = max(r['new_vs_old_max'] for r in rows)
    ax.set_xlim(min(lower * .75, .7), max(upper * 1.25, 1.4))
    ticks = [.1, .2, .25, .5, 1, 2, 4, 8, 16, 32, 64]
    ax.set_xticks([t for t in ticks if ax.get_xlim()[0] <= t <= ax.get_xlim()[1]])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}×'))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda *_: ''))
    ax.axvline(1, color='#25354d', lw=1.2, ls='--')
    ax.set_yticks(range(len(rows)), labels, fontsize=9.5)
    ax.set_ylim(len(rows) - .4, -.6)
    ax.grid(axis='x', alpha=.18)
    ax.set_xlabel('Temps ancien / temps actif — échelle logarithmique\n< 1 : ancien plus rapide     |     > 1 : actif plus rapide', fontsize=11, labelpad=12)
    for side in ['top', 'right', 'left']:
        ax.spines[side].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=9)
    fig.suptitle('Forest actif : gains et régressions sur ROMEO', x=.05, ha='left', y=1-.2/height, fontsize=18, fontweight='bold', color='#182239')
    summary = data['summary']
    state = 'Résultats complets' if summary['measured_rows'] == 57 and summary['new_finished'] == 21 else 'Résultats partiels'
    fig.text(.05, 1-.7/height, f"{state} · {len(rows)} comparaisons distinctes · {summary['measured_rows']}/57 lignes remesurées", fontsize=11, color='#536579')
    legend = [Line2D([], [], marker=marker, color=color, lw=1.5, label=label) for color, marker, label in STYLES.values()]
    fig.legend(handles=legend, loc='upper left', bbox_to_anchor=(.045, 1-.88/height), frameon=False, ncol=1, fontsize=10)
    fig.subplots_adjust(left=.35, right=.88, top=1-1.9/height, bottom=1.65/height)
    fig.text(.05, .18/height, 'Points : rapport des médianes, sauf indication. Barres : min–max par bloc (pas un intervalle de confiance).\nMême allocation, mêmes entrées et compilateur pour chaque paire ; 7 blocs CPU, 9 blocs GPU.\nUne recherche retenue par programme : ces mesures ne prouvent pas un effet causal de l’architecture.', fontsize=9, color='#536579')
    for suffix in ['png', 'svg', 'pdf']:
        fig.savefig(OUTPUT / f'GAINS-REGRESSIONS.{suffix}', dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({'comparisons': len(rows), 'matplotlib': matplotlib.__version__, 'state': state}, ensure_ascii=False))


if __name__ == '__main__':
    main()
