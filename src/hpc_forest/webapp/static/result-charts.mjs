import {escapeHTML as e, finite, seconds} from "./helpers.mjs";

const percentage=n=>new Intl.NumberFormat("fr-FR",{maximumFractionDigits:1}).format(n)+" %";

export function timeComparison(campaign) {
  const reference=campaign.reference_seconds, retained=campaign.seconds;
  const available=!!campaign.best_confirmed&&finite(reference)&&reference>0&&finite(retained)&&retained>0;
  const title='<figcaption><h2 id="comparison-title">Temps d’exécution</h2><p>Un temps plus court est meilleur.</p></figcaption>';
  if(!available) return '<figure class="card result-chart" aria-labelledby="comparison-title">'+title+
    '<p class="chart-empty">La comparaison apparaîtra après la confirmation du résultat final.</p></figure>';
  const maximum=Math.max(reference,retained), change=(reference-retained)/reference;
  const baseline=!!campaign.best_confirmed.is_baseline;
  const summary=baseline?"Code initial conservé":change===0?"Durée identique au code initial":percentage(Math.abs(change)*100)+
    (change>0?" de temps en moins":" de temps en plus");
  const tone=baseline?"unchanged":change>0?"faster":change<0?"slower":"unchanged";
  const bars=[["Code initial",reference,"reference"],["Version retenue",retained,tone]];
  return '<figure class="card result-chart" aria-labelledby="comparison-title">'+title+
    '<p class="chart-headline '+tone+'">'+e(summary)+'</p><div class="comparison-bars">'+
    bars.map(([label,value,kind])=>'<div class="comparison-row"><div class="comparison-label"><span>'+label+
      '</span><strong>'+e(seconds(value))+'</strong></div><div class="comparison-track" aria-hidden="true">'+
      '<span class="comparison-bar '+kind+'" style="width:'+(value/maximum*100)+'%"></span></div></div>').join("")+
    '</div><div class="comparison-scale" aria-hidden="true"><span>0</span><span>'+e(seconds(maximum))+"</span></div>"+
    '<p class="chart-footnote">Temps enregistrés lors de la confirmation finale.</p></figure>';
}

export function trialOutcomes(campaign) {
  const nodes=[...(campaign.trees||[]).flatMap(t=>t.nodes||[]),...(campaign.integrations||[])];
  const trials=[...new Map(nodes.map(n=>[n.id,n])).values()];
  const counts=[{label:"Corrects",kind:"correct",count:0},
    {label:"Incorrects",kind:"incorrect",count:0},{label:"Sans verdict",kind:"unscored",count:0}];
  for(const trial of trials) counts[trial.correct===true?0:trial.correct===false?1:2].count++;
  return {counts,total:trials.length,recorded:Math.max(trials.length,campaign.trial_count||0)};
}

export function outcomeChart(campaign) {
  const {counts,total,recorded}=trialOutcomes(campaign);
  const title='<figcaption><h2 id="outcomes-title">Bilan des essais</h2><p>Recherche et intégrations enregistrées.</p></figcaption>';
  if(!total) return '<figure class="card result-chart" aria-labelledby="outcomes-title">'+title+
    '<p class="chart-empty">Aucun essai enregistré pour le moment.</p></figure>';
  let offset=0;
  const segments=counts.filter(item=>item.count).map(item=>{
    const length=item.count/total*100;
    const segment='<circle class="outcome-segment '+item.kind+'" cx="80" cy="80" r="60" pathLength="100" '+
      'stroke-dasharray="'+length+' '+(100-length)+'" stroke-dashoffset="'+(-offset)+'"/>';
    offset+=length; return segment;
  }).join("");
  return '<figure class="card result-chart" aria-labelledby="outcomes-title">'+title+
    '<div class="outcomes-body"><svg class="outcome-donut" viewBox="0 0 160 160" aria-hidden="true">'+
    '<g transform="rotate(-90 80 80)">'+segments+'</g><text class="outcome-total" x="80" y="78">'+total+
    '</text><text class="outcome-caption" x="80" y="100">essai'+(total>1?'s':'')+'</text></svg>'+
    '<dl class="outcome-legend">'+counts.map(item=>'<div><dt><i class="outcome-key '+item.kind+'"></i>'+item.label+
      '</dt><dd><strong>'+item.count+'</strong><span>'+percentage(item.count/total*100)+'</span></dd></div>').join("")+
    '</dl></div><p class="chart-footnote">'+(recorded>total?'Aperçu : '+total+' essais sur '+recorded+'. ':'')+
    'Sans verdict : en attente ou interrompu avant une conclusion de correction.</p></figure>';
}

export const resultCharts=campaign=>'<div class="columns result-charts">'+timeComparison(campaign)+outcomeChart(campaign)+'</div>';
