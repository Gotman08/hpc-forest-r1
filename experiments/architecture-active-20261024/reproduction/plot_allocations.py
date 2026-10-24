"""Plot observed allocation durations; never equate reservations with GPU activity."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/architecture-active'


def main():
    data = json.loads((O/'RESULTATS.json').read_text(encoding='utf8'))
    records = json.loads((O/'RESSOURCES-SLURM.json').read_text(encoding='utf8'))['records']
    engines = {e['case_id']: e for e in data['engines'] if e['period']=='new' and e['pipeline_complete']}
    cases = sorted(engines)
    assert len(cases)==21
    def durations(scope):
        result = {}
        for row in records:
            if row['scope'] != scope:
                continue
            assert row['elapsed_seconds'] is not None
            result[row['case_id']] = result.get(row['case_id'],0) + row['elapsed_seconds']/60
        return result
    old = durations('historical_search')
    new = durations('active_search_selected')
    failed = durations('active_search_failed')
    assert set(old)==set(new)==set(cases)
    fig, ax = plt.subplots(figsize=(11.8,11.5))
    fig.patch.set_facecolor('#fafbfd'); ax.set_facecolor('#fafbfd')
    for i, case in enumerate(cases):
        ax.barh(i-.18,old[case],height=.3,color='#5477a2')
        ax.barh(i+.18,new[case],height=.3,color='#008371')
        extra=failed.get(case,0)
        if extra:
            ax.barh(i+.18,extra,left=new[case],height=.3,color='#f3d2b7',edgecolor='#9e5426',hatch='////',linewidth=.5)
        ax.plot(engines[case]['target_seconds']/60,i,'|',color='#17253a',markersize=26,markeredgewidth=1.4)
        ax.text(new[case]+extra+1.5,i+.18,f'{new[case]:.1f}'+(f' + {extra:.1f}' if extra else ''),va='center',fontsize=9,color='#006e60')
        if i%2==0:
            ax.axhspan(i-.48,i+.48,color='#e9eef4',alpha=.55,zorder=-5)
    ax.set_yticks(range(len(cases)),cases,fontsize=10)
    ax.set_ylim(len(cases)-.4,-.6)
    ax.set_xlim(0,max(max(old.values()),max(new[c]+failed.get(c,0) for c in cases),120)+23)
    ax.set_xlabel('Minutes d’allocation, hors attente dans la file SLURM',fontsize=11,labelpad=12)
    ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True);ax.tick_params(axis='y',length=0,pad=9)
    for side in ['top','right','left']:
        ax.spines[side].set_visible(False)
    fig.suptitle('Durées des campagnes retenues et des reprises nouvelles',x=.05,ha='left',y=.98,fontsize=16,fontweight='bold',color='#182239')
    handles=[Patch(facecolor='#5477a2',label='Ancienne campagne retenue'),
             Patch(facecolor='#008371',label='Nouvelle campagne retenue'),
             Patch(facecolor='#f3d2b7',edgecolor='#9e5426',hatch='////',label='Échecs de la série active : temps additionnel'),
             Line2D([],[],marker='|',linestyle='None',color='#17253a',markersize=13,label='Budget nominal de recherche, pour chaque tentative')]
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.045,.947),frameon=False,fontsize=10)
    fig.subplots_adjust(left=.16,right=.95,top=.80,bottom=.13)
    fig.text(.05,.025,
        'Source : comptabilité SLURM. Durées d’allocation incluant préparation, attente des modèles et confirmation.\n'
        'Les chiffres verts indiquent la tentative retenue + ses échecs additionnels, en minutes.\n'
        'Pilotes, veille préalable et éventuels échecs historiques exclus de ce graphique ; voir RESSOURCES-SLURM.csv.\n'
        'Ces durées ne mesurent ni l’activité GPU ni la vitesse du code livré. Ne pas additionner les programmes comme temps mural.',
        fontsize=9,color='#536579')
    for extension in ['png','svg','pdf']:
        fig.savefig(O/('DUREES-CAMPAGNES.'+extension),dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({'cases':len(cases),'scope':'observed allocations, not GPU utilization or kernel latency'}))


if __name__=='__main__':
    main()
