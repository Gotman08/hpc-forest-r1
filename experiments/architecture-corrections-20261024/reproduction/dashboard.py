"""Build an offline viewer of the audited measurements, with no external assets."""
import json
from pathlib import Path

R=Path(__file__).resolve().parent
O=R.parents[1]/'outputs/forest-corrections-20261024'

HTML='''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forest — corrections et comparaison ROMEO</title>
<style>
:root{font:16px/1.55 system-ui,sans-serif;color:#172b43;background:#f4f6f9;color-scheme:light}
*{box-sizing:border-box}body{margin:0}main{max-width:1180px;margin:auto;padding:44px 24px 70px}
header{border-bottom:2px solid #b8c7d9;padding-bottom:28px}h1{font-size:clamp(28px,4vw,42px);line-height:1.15;margin:10px 0 16px}
h2{font-size:23px;margin-top:34px}p{max-width:920px}small,.muted{color:#4e627a}.eyebrow{letter-spacing:.14em;text-transform:uppercase;font-weight:700;font-size:12px}
.tags,.tabs{display:flex;gap:10px;flex-wrap:wrap}.tag,button{border:1px solid #b8c7d9;border-radius:8px;background:white;padding:9px 14px;font:inherit}
.tag{font-size:14px}.tabs{margin:28px 0 18px}button{cursor:pointer;color:#193d6c}button[aria-pressed=true]{background:#193d6c;color:white;border-color:#193d6c}button:focus-visible,a:focus-visible{outline:3px solid #bd6500;outline-offset:3px}
.panel{background:white;border:1px solid #d2dae5;border-radius:12px;padding:22px;margin:18px 0}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid #dce3ec;vertical-align:top}th{font-weight:650;color:#41556e}td.num,th.num{text-align:right;white-space:nowrap}
.gain{font-weight:750}.good{color:#146a42}.bad{color:#a22a32}.notice{border-left:4px solid #bd6500;padding:12px 18px;background:#fff7e6;font-size:14px}.links{display:flex;gap:20px;flex-wrap:wrap}a{color:#164f92}details{margin:18px 0}summary{cursor:pointer;font-weight:650}.caption{font-size:13px;margin:10px 0 0}
@media(max-width:640px){main{padding:24px 12px}.panel{padding:14px}th,td{padding:10px 7px}h2{font-size:21px}}
</style><main>
<header><div class="eyebrow">Forest · preuves ROMEO</div><h1>Corrections des analyses<br>et des décisions d’arrêt</h1>
<p>Le moteur est corrigé par Codex. <strong>GPT-6 Luna, effort max</strong>, exécute tous les rôles : Mother, arbres, JEV et intégration.</p>
<div class="tags"><span class="tag" id="tests"></span><span class="tag">Mémoire neuve par programme</span><span class="tag">Comparaisons sur la même allocation par cas</span></div></header>
<nav class="tabs" aria-label="Programme"><button data-case="sgemm" aria-pressed="true">SGEMM</button><button data-case="utf8" aria-pressed="false">UTF-8</button><button data-case="mandelbrot" aria-pressed="false">Mandelbrot</button></nav>
<div class="notice">Un seul tirage de recherche achevé par programme et par architecture. Les blocs répétés vérifient la stabilité des temps ; ils ne prouvent pas une supériorité statistique de la stratégie.</div>
<section class="panel"><h2 style="margin-top:0">Vitesse des programmes livrés</h2><p class="muted">Temps plus petit = programme plus rapide. Gain = temps précédent ÷ temps corrigé.</p><div class="table-wrap"><table><thead><tr><th>Configuration</th><th class="num">Historique</th><th class="num">Active précédente</th><th class="num">Corrigée</th><th class="num">Gain</th></tr></thead><tbody id="timings"></tbody></table></div><p class="caption" id="hardware"></p></section>
<p class="notice" id="case-note"></p>
<section class="panel"><h2 style="margin-top:0">Recherche et arrêts</h2><div class="table-wrap"><table><thead><tr><th>Version</th><th class="num">Durée moteur</th><th class="num">Validés / essais</th><th class="num">Arbres initiaux + créés</th><th>Motif final</th></tr></thead><tbody id="engines"></tbody></table></div><p class="caption" id="closure"></p></section>
<section class="panel"><h2 style="margin-top:0">Travail des JEV</h2><div class="table-wrap"><table><thead><tr><th>Version</th><th class="num">Appels</th><th class="num">Bilans terminés</th><th class="num">Bilans citant du code</th><th class="num">Citations vérifiées</th></tr></thead><tbody id="analysts"></tbody></table></div><p class="caption">Une citation vérifiée prouve la provenance des lignes, pas la justesse de l’interprétation. Les erreurs de raisonnement observées sont décrites dans le rapport.</p></section>
<details><summary>Speedups publiés et remesurés pour ce programme</summary><div class="table-wrap"><table><thead><tr><th>Ligne documentaire</th><th class="num">Publié</th><th class="num">Référence ROMEO</th><th class="num">Historique</th><th class="num">Active précédente</th><th class="num">Corrigée</th></tr></thead><tbody id="speedups"></tbody></table></div><p class="caption">Les valeurs publiées proviennent d’autres machines. Pour UTF-8, le naïf documentaire est incorrect sur certaines chaînes mal formées ; Forest utilise une base réparée. Voir les audits et les dénominateurs dans le rapport.</p></details>
<h2>Mesures et limites à vérifier</h2><p>Compilation, contrôle et chronométrage sur ROMEO ; inférence via Codex et son relais local. Les tentatives interrompues par l’infrastructure sont archivées séparément et ne sont pas choisies selon leur vitesse.</p>
<div class="links"><a href="RAPPORT.md">Rapport détaillé</a><a href="comparaison.csv">CSV des comparaisons</a><a href="stops.csv">Décisions d’arrêt</a><a href="analyst_reports.csv">Bilans JEV</a><a href="RESULTATS.json">Données complètes</a></div>
</main><script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent);
const labels={historical:'Historique',previous:'Active précédente',corrected:'Corrigée'};
const stops={reviewed_closure:'Fermeture revue',final_reserve_or_deadline:'Réserve finale / échéance',no_admissible_work_after_idle_review:'Aucun travail admissible après revue',mother_closure:'Fermeture simple de Mother'};
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(x,n=2)=>x==null?'—':Number(x).toLocaleString('fr-FR',{minimumFractionDigits:n,maximumFractionDigits:n});
const duration=x=>x==null?'—':`${num(x/60,1)} min`;
const latency=x=>x==null?'—':x<.001?`${num(x*1e6,3)} µs`:`${num(x*1e3,3)} ms`;
const cell=(x,n=false)=>`<td${n?' class="num"':''}>${esc(x)}</td>`;
function render(c){
 document.querySelectorAll('[data-case]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.case===c)));
 const rows=D.rows.filter(r=>r.case_id===c);
 const selected=rows.filter(r=>['gpu_sgemm_10','CPU_UTF8_MEAN','CPU_ISPC_MANDELBROT_1C','CPU_ISPC_MANDELBROT_4C'].includes(r.id));
 document.getElementById('timings').innerHTML=selected.map(r=>'<tr>'+cell(c==='mandelbrot'?`${r.threads} thread(s)`:c==='sgemm'?'4096 × 4096':'65 536 octets')+['historical','previous','corrected'].map(p=>cell(latency(r[p].seconds),true)).join('')+`<td class="num gain ${r.corrected_vs_previous>=1?'good':'bad'}">${num(r.corrected_vs_previous)}×</td></tr>`).join('');
 document.getElementById('hardware').textContent=c==='sgemm'?'NVIDIA GH200 · 9 blocs · FP32 · même graine entre variantes au sein de chaque bloc.':c==='utf8'?'AMD EPYC 9654 · 7 blocs · un thread · entrée identifiée par empreinte.':'AMD EPYC 9654 · 7 blocs · 1536 × 1024 pixels, 512 itérations · objectif de recherche : moyenne géométrique 1 et 4 threads.';
 const engines=D.engines.filter(e=>e.case_id===c);
 document.getElementById('case-note').textContent={sgemm:'Le gain provient du programme tuilé avec copies asynchrones. Une fermeture périmée a été rejetée ; l’arrêt final vient de la réserve. Le résultat reste en retrait de la référence optimisée et de cuBLAS.',utf8:'Le gagnant passe 101 205 cas supplémentaires. Le JEV a signalé un vrai défaut dans une autre variante (314 erreurs). La dernière revue de fermeture échoue cependant sur des références présentes dans le dossier mais exclues de sa liste autorisée.',mandelbrot:'Pas de gain sur la version active précédente et environ trois fois plus lent que le meilleur historique. La boucle de récurrence reste non vectorisée ; les protections ont prolongé l’exploration sans résoudre ce défaut.'}[c];
 document.getElementById('engines').innerHTML=engines.map(e=>'<tr>'+cell(labels[e.period])+cell(duration(e.elapsed_seconds),true)+cell(`${e.correct_trials} / ${e.total_trials}`,true)+cell(`${e.initial_trees} + ${e.created_trees}`,true)+cell(stops[e.stop_reason]||e.stop_reason||'Non instrumenté')+'</tr>').join('');
 const e=engines.find(e=>e.period==='corrected');
 document.getElementById('closure').textContent=`Version corrigée : première demande de fermeture acceptée à ${duration(e.first_close_request_seconds)} ; confirmation de fermeture à ${duration(e.confirmed_close_seconds)}. Une demande n’est pas un arrêt effectif. Les arbres créés incluent les intégrations intermédiaires.`;
 document.getElementById('analysts').innerHTML=engines.filter(e=>e.period!=='historical').map(e=>'<tr>'+cell(labels[e.period])+['analyst_calls','completed_analyses','analyses_with_code','verified_source_citations'].map(k=>cell(e[k],true)).join('')+'</tr>').join('');
 document.getElementById('speedups').innerHTML=rows.map(r=>'<tr>'+cell(r.label)+['published_speedup','reference_speedup','historical_speedup','previous_speedup','corrected_speedup'].map(k=>cell(num(r[k])+'×',true)).join('')+'</tr>').join('');
}
document.getElementById('tests').textContent=`${D.software_validation.tests} tests réussis · Ruff validé`;
document.querySelectorAll('[data-case]').forEach(b=>b.addEventListener('click',()=>render(b.dataset.case)));
render('sgemm');
</script></html>'''


def main():
    data=json.loads((O/'RESULTATS.json').read_text(encoding='utf8'))
    fields=['case_id','period','elapsed_seconds','correct_trials','total_trials',
            'initial_trees','created_trees','stop_reason','first_close_request_seconds',
            'confirmed_close_seconds','analyst_calls','completed_analyses',
            'analyses_with_code','verified_source_citations']
    compact={'software_validation':data['software_validation'],'rows':data['rows'],
             'engines':[{key:engine[key] for key in fields} for engine in data['engines']]}
    # Scripts are fixed; report/model text is embedded as inert JSON, then escaped.
    payload=json.dumps(compact,ensure_ascii=False).replace('<','\\u003c')
    (O/'TABLEAU-DE-BORD.html').write_text(HTML.replace('__DATA__',payload),encoding='utf8')
    print(O/'TABLEAU-DE-BORD.html')


if __name__=='__main__':main()
