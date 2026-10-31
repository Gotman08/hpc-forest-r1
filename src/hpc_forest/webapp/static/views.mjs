import {escapeHTML as e, seconds, speedup, size, date, badge, short, routeFor, safeJSON} from "./helpers.mjs";
import {icon} from "./icons.mjs";
import {forestMarkup} from "./graph.mjs";
import {searchControls, searchSummary} from "./search.mjs";
import {historyPage, HISTORY_PAGE_SIZES} from "./history.mjs";
import {resultCharts} from "./result-charts.mjs";
import {modelLabel, modelFields, requiresDsh} from "./models.mjs";
import {validationControls, validationSummary} from "./validation.mjs";
export {modelLabel} from "./models.mjs";

const button=(label,action,symbol="arrow",cls="primary",extra="") =>
  '<button class="button '+cls+'" data-action="'+action+'" '+extra+'>'+icon(symbol)+e(label)+'</button>';
const link=(label,href,symbol="arrow",cls="secondary") =>
  '<a class="button '+cls+'" href="'+e(href)+'">'+icon(symbol)+e(label)+'</a>';
const note=(text,tone="blue") => '<div class="callout '+tone+'">'+icon("info")+'<div>'+text+'</div></div>';
const heading=(title,description,extra="") => '<div class="page-heading"><div><h1>'+title+'</h1><p>'+description+'</p></div>'+extra+'</div>';
const cardTitle=(title,extra="")=>'<div class="card-title"><h2>'+e(title)+'</h2>'+extra+'</div>';
const stat=(label,value,symbol="clock",cls="")=>'<div class="stat-card '+cls+'"><span class="stat-icon">'+icon(symbol)+'</span><div><p>'+label+'</p><strong>'+value+'</strong></div></div>';
export const empty=(title,message,action="")=>'<div class="empty-state">'+icon("folder")+'<h2>'+title+'</h2><p>'+message+'</p>'+action+'</div>';

export function shell(active,projectName="") {
  const items=[["project","Projet","folder"],["prepare","Préparation","file"],["mission","Mission","play"],
    ["results","Résultats","bars"],["history","Historique","clock"]];
  return [
    '<header class="topbar"><a class="brand" href="#/project"><span class="brand-icon">'+icon("grid")+'</span>Espace de travail</a>',
    '<div class="breadcrumb">'+(projectName?e(projectName)+'<span>/</span>':'')+e(items.find(i=>i[0]===active)?.[1]||"Paramètres")+'</div>',
    '<div class="header-actions"><button class="theme-toggle" type="button" data-action="toggle-theme" aria-label="Passer au thème clair" title="Passer au thème clair">'+icon("sun")+'<span>Mode clair</span></button></div></header>',
    '<aside class="sidebar"><nav aria-label="Navigation principale">'+items.map(([id,title,symbol])=>'<a href="#/'+id+'" class="nav-link '+(active===id?'active':'')+'" '+(active===id?'aria-current="page"':'')+'>'+icon(symbol)+'<span>'+title+'</span></a>').join("")+'</nav>',
    '<div class="sidebar-bottom"><div class="engine-note"><span class="engine-glyph">F</span><div><strong>Moteur Forest</strong><small>Espace personnel · v0.2</small></div></div>',
    '<a class="nav-link '+(active==="settings"?"active":"")+'" href="#/settings">'+icon("settings")+'<span>Paramètres</span></a></div></aside>',
    '<main id="main" tabindex="-1"></main>',
  ].join("");
}

function filesList(files,limit=12) {
  return '<ul class="file-list">'+files.slice(0,limit).map(f=>'<li>'+icon("file")+'<span>'+e(f.path||f.name)+'</span><small>'+size(f.bytes??f.size)+'</small></li>').join("")+'</ul>'+
    (files.length>limit?'<p class="muted tiny">Et '+(files.length-limit)+' autres fichiers.</p>':'');
}
export function projectView(project,uploads=[],allProjects=[]) {
  const select=allProjects.length?'<label class="project-picker">Projet sauvegardé<select id="project-picker"><option value="">Nouveau projet</option>'+allProjects.map(p=>'<option value="'+e(p.id)+'" '+(p.id===project?.id?'selected':'')+'>'+e(p.name)+'</option>').join("")+'</select></label>':'';
  const attachments=project?.attachments||[];
  return heading(project?"Votre projet":"Déposer votre projet","Votre code, vos tests et les informations utiles. Nous conservons une copie de l’original.",select)+
    '<div class="columns project-columns"><section class="column">'+
    (project?'<div class="card imported"><span class="big-icon">'+icon("folder")+'</span><div><h2>'+e(project.name)+'</h2><p>'+project.files.length+' fichiers · '+size(project.total_bytes)+'</p></div>'+badge("ready","Importé")+'</div>':
      '<div class="card import-card"><label class="field">Nom du projet<input id="project-name" placeholder="Mon projet" maxlength="100" autocomplete="off"></label><div id="dropzone" class="dropzone" tabindex="0" role="button" aria-label="Déposer ou choisir les fichiers du projet"><span class="drop-icon">'+icon("folder")+'</span><h2>Fichier, dossier ou ZIP</h2><p>Glissez votre projet ici</p><div class="button-row">'+button("Choisir des fichiers","choose-files","upload","secondary")+button("Choisir un dossier","choose-folder","folder","ghost")+'</div><small>Code C / C++ / CUDA · Jusqu’à 64 Mio</small></div><input id="files-input" type="file" multiple hidden><input id="folder-input" type="file" multiple webkitdirectory hidden></div>')+
    (project||uploads.length?'<section class="card">'+cardTitle("Contenu du projet",'<span class="count">'+(project?.files.length||uploads.length)+'</span>')+filesList(project?.files||uploads.map(f=>({path:f.relativePath||f.name,bytes:f.size})))+
    (project?.ignored_files?'<p class="muted tiny">'+project.ignored_files+' fichiers de cache ou métadonnées ignorés.</p>':'')+'</section>':'')+
    '<div class="action-bar">'+(project?link("Préparer le projet","#/prepare/"+project.id,"arrow","primary")+button("Nouveau projet","new-project","plus","secondary"):
      button("Importer le projet","import","arrow","primary",uploads.length?'':'disabled'))+'</div></section>'+
    '<aside class="column"><section class="card">'+cardTitle("Documents complémentaires")+'<p class="muted small">Cahier des charges et données de test.</p>'+
    ["statement","test_data"].map(role=>'<div class="attachment-row">'+icon(role==="statement"?"file":"server")+'<div><strong>'+(role==="statement"?"Cahier des charges":"Données de test")+'</strong><small>'+
      (project?"Facultatif":"Disponible après l’import")+'</small></div><button class="button ghost small-button" data-action="attach" data-role="'+role+'" '+(!project?'disabled':'')+'>Ajouter</button></div>').join("")+
    (attachments.length?'<ul class="attachment-list">'+attachments.map(a=>'<li>'+icon("check")+e(a.name)+' <small>'+size(a.bytes)+'</small></li>').join("")+'</ul>':'')+'<input id="attachment-input" type="file" hidden></section>'+
    '<section class="card">'+cardTitle("Votre mission")+'<dl class="key-values"><div><dt>'+icon("settings")+'Moteur</dt><dd>Forest</dd></div><div><dt>'+icon("chip")+'Modèle</dt><dd>'+e(modelLabel(project?.model,project?.effort))+'</dd></div><div><dt>'+icon("server")+'Calcul</dt><dd>ROMEO</dd></div></dl></section>'+
    '<div class="quiet-note">'+icon("lock")+'<p>Vos fichiers sont conservés dans votre espace local. L’import ne lance aucun calcul.</p></div></aside></div>';
}

function field(name,label,value,extra="",hint="",type="text") {
  const control=type==="textarea"?'<textarea name="'+name+'" '+extra+'>'+e(value)+'</textarea>':
    '<input type="'+type+'" name="'+name+'" value="'+e(value)+'" '+extra+'>';
  return '<label class="field">'+label+control+(hint?'<small>'+hint+'</small>':'')+'</label>';
}
export function prepareView(project,info={}) {
  const c=project.contract;
  if(project.missing?.some(m=>m.field==="migration")) return heading("Contrat historique",e(project.name))+
    note("Ce projet contient des réglages TabPFN retirés. L’original et ses missions restent consultables. Créez une copie avec le contrat courant pour préparer une nouvelle recherche.","amber")+
    button("Créer une copie sans conseiller","migrate-project","plus","primary");
  return heading("Préparer la mission","Définissez ce que le programme doit faire et comment vérifier son résultat.",badge(project.state))+
    (project.ready?note('<strong>Le contrat est complet.</strong><p>Vous pouvez figer un dossier de mission. Les commandes n’ont pas encore été exécutées.</p>',"green"):
      note('<strong>Vérification à compléter</strong><p>'+project.missing.map(m=>e(m.label)).join(" · ")+'</p>',"amber"))+
    '<form id="contract-form"><div class="columns preparation-columns"><div class="column"><section class="card">'+cardTitle("Contrat de vérification")+
    field("build_command","Compilation",c.build_command,'rows="3" spellcheck="false" required',"Une commande par ligne. Aucune commande n’est exécutée pendant la préparation.","textarea")+
    field("test_command","Tests de correction",c.test_command,'rows="2" spellcheck="false" required',"Commandes qui vérifient effectivement le résultat du programme.","textarea")+
    field("benchmark_command","Programme à mesurer",c.benchmark_command,'spellcheck="false" placeholder="./build/mon_programme ..." required',"Décrivez les arguments et entrées de la mesure.")+
    field("expected_result","Résultat attendu",c.expected_result,'rows="3" required placeholder="Sortie attendue, jeu de tests, tolérance numérique…"',"La correction doit être définie avant toute optimisation.","textarea")+'</section>'+
    '<section class="card">'+cardTitle("Périmètre des modifications")+
    field("editable_paths","Fichiers ou dossiers modifiables",c.editable_paths.join("\n"),'rows="2" spellcheck="false" required',"Un chemin relatif par ligne. Les tests et la validation restent protégés.","textarea")+
    '<p class="inline-note">'+icon("lock")+'Les fichiers originaux sont conservés.</p></section></div>'+
    '<aside class="column"><section class="card">'+cardTitle("Exécution")+
    '<label class="field">Cible<select name="target"><option value="cpu" '+(c.target==="cpu"?"selected":"")+'>ROMEO · CPU</option><option value="gpu" '+(c.target==="gpu"?"selected":"")+(!info.connection?.targets?.includes("gpu")?" disabled":"")+'>ROMEO · GPU (profil requis)</option></select></label>'+
    field("duration_minutes","Durée cible (minutes)",c.duration_minutes,'min="1" max="1440" required',"La répartition entre recherche, analyses et confirmation sera vérifiée avant exécution.","number")+
    modelFields(c,info)+
    '<div class="fixed-setting">'+icon("refresh")+'<div><strong>Mémoire neuve</strong><small>Pour chaque nouvelle mission</small></div></div></section>'+
    validationControls(c)+searchControls(c,info)+'<section class="card">'+cardTitle("Consignes du projet")+
    field("statement","Objectif et contraintes",c.statement,'rows="5" placeholder="Interfaces à préserver, limites mémoire, formats…"',"Précisez les fonctions à préserver et les limites à respecter.","textarea")+'</section>'+
    '<section class="card connection-card">'+icon("server")+'<h3>Soumission ROMEO</h3><p>Le dossier est figé avant la soumission. La recherche continue sur ROMEO même si cet onglet ou le PC est fermé. Une réserve de 30 minutes complète la durée cible pour finaliser.</p></section></aside></div>'+
    '<div class="sticky-actions"><span id="save-state" class="muted small">Contrat sauvegardé</span><div class="button-row"><button type="submit" class="button secondary">'+icon("check")+'Enregistrer le contrat</button>'+
    button("Préparer le dossier ROMEO","prepare","arrow","primary",project.ready?'type="button"':'type="button" disabled')+'</div></div></form>';
}

export function preparedView(mission,info={}) {
  const dsh=requiresDsh(mission.contract.contract||mission.contract,info.models);
  return heading("Mission préparée",e(mission.name),badge("prepared"))+
    note('<strong>Le dossier est sauvegardé. Aucun job n’a été soumis.</strong><p>Le code initial, les documents et le contrat sont figés dans une nouvelle mission. Vous pouvez maintenant lancer la campagne sur ROMEO.</p><p>Les commandes et le code s’exécuteront avec les droits de votre compte ROMEO. Importez uniquement du code de confiance ; cette version ne fournit pas de bac à sable contre du code hostile.</p>')+
    '<div class="columns"><section class="card">'+cardTitle("Prêt pour la prochaine étape")+
    validationSummary({required:mission.contract.contract?.execution_validation})+
    '<dl class="key-values"><div><dt>Modèle</dt><dd>'+e(modelLabel(mission.contract.model,mission.contract.reasoning_effort))+'</dd></div><div><dt>Cible</dt><dd>ROMEO · '+e(mission.target.toUpperCase())+'</dd></div><div><dt>Création</dt><dd>'+date(mission.created)+'</dd></div><div><dt>Mémoire</dt><dd>Nouvelle mission</dd></div></dl>'+
    '<p class="small">Recherche : '+e(mission.contract.contract?.search?.algorithm||"ab-mcts-a")+' · '+e(mission.contract.contract?.search?.distribution||"")+'<br>Générateurs : '+e((mission.contract.contract?.generator_pool||[]).map(m=>modelLabel(m.model,m.reasoning_effort)).join(", ")||"Modèle principal uniquement")+'<br>Archive de diversité : '+(mission.contract.contract?.evolution?.enabled?"activée":"désactivée")+'</p>'+
    (dsh?note(info.connection?.dsh_romeo_configured?"Le modèle DeepSeek et sa passerelle doivent déjà fonctionner sur ROMEO. Cette mission ne démarre ni n’arrête leur allocation.":"Configurez la connexion dsh-romeo dans romeo.json avant de lancer cette mission.","amber"):"")+
    '<div class="action-bar">'+button("Lancer sur ROMEO","launch","play","primary",info.submission_enabled&&info.connection?.targets?.includes(mission.target)&&(!dsh||info.connection?.dsh_romeo_configured)?"":"disabled")+link("Télécharger le dossier","/api/prepared/"+mission.id+"/download","download","secondary")+'</div></section>'+
    '<section class="card">'+cardTitle("Ce que contient le dossier")+'<ul class="check-list"><li>'+icon("check")+'Le code original et ses empreintes</li><li>'+icon("check")+'Le contrat de compilation et de vérification</li><li>'+icon("check")+'Les documents joints</li></ul><p class="muted">Il ne contient pas encore de code optimisé ni de résultat de mesure.</p>'+
    link("Revenir au projet","#/prepare/"+mission.project_id,"arrow","secondary")+'</section></div>';
}

const evidenceNote=campaign=>'<div class="evidence-bar"><span>'+icon("lock")+(campaign.mission_id?'Preuves synchronisées depuis ROMEO':'Campagne existante · consultation seule')+'</span><span>'+e(campaign.host||campaign.target)+' · '+date(campaign.started)+'</span></div>';
function stepper(c) {
  const complete=["confirmed","no_gain"].includes(c.state);
  return '<ol class="stepper">'+[["Préparation",true],["Recherche",c.trial_count>0],["Confirmation",complete]].map(([label,done],i)=>
    '<li class="'+(done?'done':'pending')+'"><span class="step-dot">'+(done?icon("check"):i+1)+'</span><div><strong>'+label+'</strong><small>'+(done?'Enregistrée':'Non confirmée')+'</small></div></li>').join("")+'</ol>';
}
export function missionView(campaign,selected=null,showActivity=true) {
  const completed=["confirmed","no_gain"].includes(campaign.state);
  const integration=campaign.integrations||[];
  return heading(completed?"Recherche terminée":"Suivi de la mission",e(campaign.name)+" · "+campaign.trial_count+" essais enregistrés",badge(campaign.state))+
    evidenceNote(campaign)+(campaign.truncated?note("Cette vue est limitée aux 3 000 premiers essais. Consultez le rapport complet pour la suite.","amber"):"")+stepper(campaign)+
    validationSummary(campaign.execution_validation)+
    '<div class="columns mission-columns"><section class="column"><section class="chalkboard"><header class="board-header"><div><h2>Arbres de recherche</h2><p>Chaque nœud correspond à un essai enregistré.</p></div><div class="zoom-controls"><button data-action="zoom-out" aria-label="Réduire">'+icon("minus")+'</button><span id="zoom-value">100 %</span><button data-action="zoom-in" aria-label="Agrandir">'+icon("plus")+'</button><button data-action="zoom-fit" aria-label="Réinitialiser le cadrage">'+icon("fit")+'</button></div></header><div class="forest-scroll"><div class="forest-canvas">'+forestMarkup(campaign,selected,showActivity)+'</div></div><footer class="board-legend"><span><i class="legend-node valid"></i>Correct</span><span><i class="legend-node active"></i>En cours</span><span><i class="legend-node"></i>Non confirmé</span><span><i class="legend-node invalid"></i>Incorrect</span><span><i class="legend-edge"></i>Parent d’un autre arbre ou d’une intégration</span><small>'+campaign.trees.length+' arbres</small></footer></section>'+
    (integration.length?'<section class="card integration-card">'+icon("code")+'<div><h3>Combinaisons et intégration</h3><p>Programmes évalués séparément des arbres.</p></div>'+integration.map(t=>'<button class="button ghost small-button" data-node="'+e(t.id)+'">'+e(t.role)+' · '+seconds(t.seconds)+icon("chevron")+'</button>').join("")+'</section>':'')+
    '<section id="trial-panel" class="card trial-panel">'+cardTitle("Preuves de la variante")+'<div class="empty-detail">'+icon("info")+'Sélectionnez un nœud pour lire son code, ses tests et ses mesures.</div></section></section>'+
    '<aside class="column"><section class="card">'+cardTitle("Activité enregistrée")+'<div class="activity-item"><span class="activity-dot green"></span><div><strong>'+campaign.trial_count+' essais</strong><small>'+campaign.trees.reduce((n,t)=>n+t.correct_count,0)+' variantes correctes dans les arbres</small></div></div><div class="activity-item"><span class="activity-dot '+(campaign.best_confirmed?"green":"gray")+'"></span><div><strong>Confirmation</strong><small>'+e(campaign.final_g_status||"Non renseignée")+'</small></div></div></section>'+
    searchSummary(campaign)+'<section class="card">'+cardTitle("Analystes",icon("users"))+'<strong class="analyst-count">'+campaign.analyses.length+' bilan'+(campaign.analyses.length>1?'s':'')+' disponible'+(campaign.analyses.length>1?'s':'')+'</strong><p class="muted small">'+(campaign.analyses.length?"Le dernier bilan enregistré de chaque arbre, avec ses preuves.":"Aucun bilan d’analyste actif disponible dans cette vue.")+'</p>'+
    (campaign.analyses.length?button("Lire les analyses","show-analyses","file","ghost"):'')+'</section>'+
    '<section class="card">'+cardTitle("Décisions et arrêt")+'<p class="decision-text">'+e(campaign.search_stop_reason==="budget_exhausted"?"Budget de recherche atteint":campaign.search_stop_reason||"Consultez les événements enregistrés.")+'</p><p class="muted small">'+campaign.decisions.length+' décision'+(campaign.decisions.length>1?'s':'')+' de pilotage enregistrée'+(campaign.decisions.length>1?'s':'')+'.</p>'+button("Voir les justifications","show-events","file","ghost")+'</section>'+
    '<section class="card compact-card"><dl class="key-values"><div><dt>Modèle enregistré</dt><dd>'+e(campaign.model||campaign.backend||"Non renseigné")+'</dd></div><div><dt>Effort</dt><dd>'+e(campaign.effort||"—")+'</dd></div><div><dt>Machine</dt><dd>'+e(campaign.host||"—")+'</dd></div></dl></section>'+
    link("Voir les résultats","#/results/"+campaign.id,"bars",campaign.best_confirmed?"primary":"secondary")+'</aside></div>'+
    '<section id="events-panel" class="card events-panel" hidden></section>';
}

export function trialPane(trial,source=null,tab="tests") {
  const tabs=[["code","Code"],["diff","Diff / référence"],["tests","Tests"],["measures","Mesures"],["analysis","Analyse"]];
  let body;
  if(tab==="code"||tab==="diff") {
    body=trial.files.length?'<label class="source-picker">Fichier<select id="source-file">'+trial.files.map(path=>'<option '+(source?.path===path?'selected':'')+'>'+e(path)+'</option>').join("")+'</select></label>'+
      '<pre class="source-code">'+(source?e(tab==="code"?source.content:source.diff_available===false?"La référence dépasse la limite de lecture ; comparaison indisponible.":source.diff||"Aucune différence avec la référence."):"Chargement du fichier…")+'</pre>'+
      (tab==="diff"&&source?.diff_truncated?'<p class="muted tiny">Différence tronquée à 256 Kio. Consultez les fichiers complets pour la suite.</p>':""):
      '<div class="empty-detail">Le code de cette variante n’est pas présent dans les preuves disponibles.</div>';
  } else if(tab==="tests") {
    body='<div class="detail-status">'+badge(trial.state)+'<span>'+e(trial.correct===true?"Correction vérifiée":trial.correct===false?"Le programme a échoué à la vérification":"Aucune correction confirmée")+'</span></div>'+
      (trial.reason?'<p class="reason">'+e(trial.reason)+'</p>':'')+
      validationSummary({required:trial.execution_validation?.allocation?.required,
        allocation:trial.execution_validation?.allocation,evidence:trial.execution_validation},"Validation de cette variante")+
      '<dl class="key-values small"><div><dt>Phase</dt><dd>'+e(trial.phase)+'</dd></div><div><dt>Commit</dt><dd><code>'+e(short(trial.commit)||"—")+'</code></dd></div></dl>'+
      (trial.evaluations.length?'<details><summary>Preuves de vérification ('+trial.evaluations.length+')</summary><pre>'+safeJSON(trial.evaluations)+'</pre></details>':'');
  } else if(tab==="measures") {
    body='<div class="mini-stats">'+stat("Temps moyen",seconds(trial.seconds))+stat("Échantillons",String(trial.times.length),"bars")+'</div>'+
      (trial.times.length?'<ol class="samples">'+trial.times.map(t=>'<li>'+seconds(t)+'</li>').join("")+'</ol>':'<p class="muted">Aucune mesure disponible pour cette variante.</p>')+
      '<p class="muted tiny">Ces mesures d’essai ne remplacent pas la confirmation finale.</p>';
  } else {
    body='<h3>Hypothèse du générateur</h3><p class="hypothesis">'+e(trial.hypothesis||"Aucune hypothèse enregistrée.")+'</p><details><summary>Origine du code, transformations et preuves</summary><pre>'+safeJSON({search_parent:trial.parent,delegation_parent:trial.delegation_parent,base_source_id:trial.base_source_id,base_commit:trial.base_commit,transformations:trial.transformations,sources:trial.sources,advice_ids:trial.advice_ids,control_decision_id:trial.control_decision_id})+'</pre></details><p class="muted tiny">Une hypothèse de génération n’est pas un rapport d’analyste.</p>';
  }
  return cardTitle("Variante "+short(trial.id),badge(trial.state))+
    (trial.generator?.model?'<p class="muted small">Générateur : '+e(modelLabel(trial.generator.model,trial.generator.reasoning_effort))+'</p>':'')+
    '<div class="tabs" role="tablist">'+tabs.map(([id,label])=>'<button role="tab" aria-selected="'+(tab===id)+'" class="'+(tab===id?'active':'')+'" data-tab="'+id+'">'+label+'</button>').join("")+'</div><div class="tab-content" role="tabpanel">'+body+'</div>';
}

export function resultsView(c) {
  const confirmed=!!c.best_confirmed;
  const noGain=c.state==="no_gain";
  const baseline=!!c.best_confirmed?.is_baseline;
  return heading("Votre résultat",e(c.name),badge(c.state))+
    validationSummary(c.execution_validation)+
    (confirmed?"":note('<strong>Aucun résultat final confirmé.</strong><p>Les essais restent consultables. Aucun gain ni code optimisé n’est annoncé.</p>',"amber"))+
    '<div class="stat-grid">'+stat("Temps de référence",seconds(c.reference_seconds))+stat("Version retenue",seconds(c.seconds),"clock",confirmed?"gain":"")+stat("Accélération",speedup(c.speedup),"bars",confirmed&&!noGain?"gain":"")+'</div>'+
    resultCharts(c)+
    '<div class="columns"><section class="card">'+cardTitle("Conditions de comparaison")+'<dl class="key-values"><div><dt>'+icon("server")+'Machine</dt><dd>'+e(c.host||"—")+'</dd></div><div><dt>'+icon("chip")+'Architecture</dt><dd>'+e(c.machine||"—")+'</dd></div><div><dt>'+icon("code")+'Compilateur</dt><dd>'+e(c.compiler||"—")+'</dd></div><div><dt>'+icon("bars")+'Confirmation</dt><dd>'+e(c.confirmation_repetitions||"—")+' répétitions prévues</dd></div></dl><details><summary>Identité du protocole</summary><code class="break">'+e(c.protocol_id||"—")+'</code></details><p class="muted tiny">Les temps sont comparables pour la même cible, les mêmes entrées et le même protocole.</p></section>'+
    '<section class="card">'+cardTitle("Livrables")+'<div class="download-list">'+
    (c.downloads.code?'<a href="/api/campaigns/'+c.id+'/download/code">'+icon("folder")+'<span><strong>'+(baseline?"Projet initial confirmé":"Projet confirmé")+'</strong><small>Archive du projet retenu</small></span>'+icon("download")+'</a>':'<div class="delivery-disabled">'+icon("lock")+'Aucun projet confirmé disponible</div>')+
    (c.downloads.report?'<a href="/api/campaigns/'+c.id+'/download/report">'+icon("file")+'<span><strong>Rapport de campagne</strong><small>Constats et contexte de mesure</small></span>'+icon("download")+'</a>':'')+
    (c.downloads.csv?'<a href="/api/campaigns/'+c.id+'/download/csv">'+icon("bars")+'<span><strong>Mesures CSV</strong><small>Essais, états et temps enregistrés</small></span>'+icon("download")+'</a>':'<p class="muted small">Consultez l’export Forest complet : plus de 3 000 essais.</p>')+'</div></section></div>'+
    '<div class="action-bar">'+(c.downloads.code?link(baseline?"Télécharger le code initial":"Télécharger le projet","/api/campaigns/"+c.id+"/download/code","download","primary"):'')+
    link("Examiner les variantes","#/mission/campaign/"+c.id,"code","secondary")+link("Nouvelle mission","#/project/new","plus","ghost")+'</div>';
}

function historyPagination(page) {
  const pageButton=(number,label,extra="")=>'<button class="button ghost small-button" type="button" data-action="history-page" data-page="'+number+'" '+extra+'>'+label+'</button>';
  const numbers=page.numbers.map((number,index)=>
    (index&&number>page.numbers[index-1]+1?'<span class="page-gap" aria-hidden="true">…</span>':"")+
    pageButton(number,String(number),'aria-label="Page '+number+'"'+(number===page.page?' aria-current="page"':""))).join("");
  return '<footer class="history-pagination"><p id="history-range" role="status">'+page.start+'–'+page.end+' sur '+page.total+
    ' résultat'+(page.total>1?'s':'')+'</p><label class="page-size">Par page <select id="history-page-size">'+
    HISTORY_PAGE_SIZES.map(size=>'<option value="'+size+'"'+(size===page.pageSize?' selected':"")+'>'+size+'</option>').join("")+
    '</select></label><nav aria-label="Pages de l’historique">'+
    pageButton(page.page-1,icon("chevron"), 'aria-label="Page précédente"'+(page.page===1?' disabled':""))+
    numbers+pageButton(page.page+1,icon("chevron"),'aria-label="Page suivante"'+(page.page===page.pages?' disabled':""))+'</nav></footer>';
}

export function historyView(records,filter="",query="",currentPage=1,pageSize=10) {
  const page=historyPage(records,filter,query,currentPage,pageSize), rows=page.rows;
  const filters=[["completed","Terminée"],["queued","En file ROMEO"],["running","Recherche en cours"],
    ["collecting","Récupération des résultats"],["failed","Interrompue"],["confirmed","Gain confirmé"],
    ["no_gain","Aucun gain confirmé"],["prepared","Prête à transférer"],["needs_input","À compléter"],
    ["ready","Contrat prêt"],["unconfirmed","Non confirmé"]];
  return heading("Historique des missions","Vos projets, leurs résultats et les preuves conservées.",link("Nouveau projet","#/project/new","plus","primary"))+
    '<div class="history-toolbar"><label class="search-field">'+icon("search")+'<input id="history-search" placeholder="Rechercher un projet" value="'+e(query)+'"></label><label class="sr-only" for="history-filter">Filtrer par état</label><select id="history-filter"><option value="">Tous les états</option>'+filters.map(([v,l])=>'<option value="'+v+'" '+(filter===v?'selected':'')+'>'+l+'</option>').join("")+'</select></div>'+
    (rows.length?'<section class="card table-card"><div class="table-scroll"><table><thead><tr><th>Projet</th><th>État</th><th>Origine</th><th>Résultat</th><th></th></tr></thead><tbody>'+rows.map(r=>'<tr><td><div class="project-cell">'+icon(r.kind==="project"?"folder":"file")+'<div><strong>'+e(r.name)+'</strong><small>'+date(r.started||r.created)+'</small></div></div></td><td>'+badge(r.state)+'</td><td><span class="muted small">'+(r.kind==="campaign"?e(r.host||"Campagne importée"):r.kind==="prepared"?"Dossier local · non soumis":r.kind==="mission"?"ROMEO · "+e(r.job_id||"soumission"):"Projet local")+'</span></td><td class="table-speed">'+speedup(r.speedup)+'</td><td><a class="button ghost small-button" href="'+routeFor(r)+'">'+(r.kind==="project"?"Compléter":"Ouvrir")+icon("chevron")+'</a></td></tr>').join("")+'</tbody></table></div>'+historyPagination(page)+'</section>':
      empty("Aucune mission trouvée",records.length?"Essayez un autre filtre.":"Importez votre premier projet pour préparer une mission.",link("Déposer un projet","#/project/new","plus","primary")))+
    '<p class="bottom-note">'+icon("refresh")+'Chaque nouvelle mission possède son propre dossier et sa mémoire. Les campagnes existantes sont consultées en lecture seule.</p>';
}

export function settingsView(info,campaignCount) {
  return heading("Paramètres","Modèle choisi par mission et connexion distante.")+
    '<div class="columns"><section class="card">'+cardTitle("Modèles disponibles")+
    '<ul class="model-list">'+(info.models||[]).map(m=>'<li>'+icon("chip")+'<div class="model-details"><strong>'+e(m.label)+'</strong><div class="model-efforts" aria-label="Efforts disponibles">'+m.efforts.map(effort=>'<span>'+e(effort)+'</span>').join("")+'</div></div></li>').join("")+'</ul><p class="muted small">Le choix et l’effort s’appliquent à tous les rôles de la mission.</p></section>'+
    '<section class="card">'+cardTitle("Exécution sur ROMEO")+'<dl class="key-values"><div><dt>Connexion</dt><dd>'+badge(info.submission_enabled?"ready":"needs_input",info.submission_enabled?"Configurée":"À configurer")+'</dd></div><div><dt>dsh-romeo</dt><dd>'+badge(info.connection?.dsh_romeo_configured?"ready":"needs_input",info.connection?.dsh_romeo_configured?"Configuré":"À configurer")+'</dd></div><div><dt>Campagnes consultables</dt><dd>'+campaignCount+'</dd></div><div><dt>Cibles configurées</dt><dd>'+e((info.connection?.targets||[]).join(", ")||"Aucune")+'</dd></div></dl><p>'+e(info.submission_message)+'</p><p class="muted small">DeepSeek : configurer la passerelle dsh-romeo et démarrer son modèle séparément. Forest ne réserve pas ses GPU.</p></section></div>'+
    note('<strong>Exécution indépendante du PC</strong><p>Après soumission, le contrôleur et les appels au modèle tournent dans le job ROMEO. Au retour dans l’application, le suivi reprend et récupère les résultats. Les identifiants des fournisseurs restent dans le stockage privé distant.</p>');
}

export function remoteMissionView(mission,campaign) {
  const p=mission.progress||{};
  return '<section class="card"><div class="card-title"><h2>'+e(mission.name)+'</h2>'+badge(mission.state)+'</div>'+
    '<dl class="key-values"><div><dt>Job ROMEO</dt><dd>'+e(mission.job_id||"En préparation")+'</dd></div><div><dt>Modèle</dt><dd>'+e(modelLabel(mission.model,mission.effort))+'</dd></div><div><dt>Machine</dt><dd>'+e(p.host||"En attente")+'</dd></div><div><dt>Dernière synchronisation</dt><dd>'+date(mission.synced_at)+'</dd></div></dl>'+
    (mission.last_error?note(e(mission.last_error),"amber"):"")+
    (mission.sync_error?note("Synchronisation retardée. Les dernières preuves reçues restent visibles ; une nouvelle récupération sera tentée automatiquement.","amber"):"")+
    '<div class="button-row">'+button("Actualiser","retry","refresh","secondary")+
    (["recovery_required","failed"].includes(mission.state)?button("Reprendre le suivi","resume-tracking","refresh","secondary"):"")+
    (!["completed","failed","cancelled","recovery_required"].includes(mission.state)?button(mission.stop_requested_at?"Arrêt demandé":"Arrêter et confirmer","stop","pause","secondary",mission.stop_requested_at?"disabled":""):"")+
    (mission.campaign_id?link("Voir les résultats","#/results/"+mission.campaign_id,"bars","secondary"):"")+'</div></section>'+
    (mission.stop_requested_at?note("La demande est conservée. Les essais déjà admis se terminent, puis Forest prépare et confirme le résultat. La livraison reste soumise à une confirmation réussie."):"")+
    (campaign?missionView(campaign,null,!["completed","failed","cancelled","recovery_required"].includes(mission.state)):
      validationSummary({required:mission.execution_validation})+
      empty("La mission est prise en charge","Le suivi est sauvegardé. Vous pouvez fermer cet écran ; le job continuera sur ROMEO une fois soumis."))+
    '<p class="bottom-note">Suivi automatique toutes les 10 secondes. La compilation, les tests et la confirmation utilisent le même contrat figé.</p>';
}

export function eventsView(c,analyses=false) {
  const data=analyses?c.analyses:[...(c.closure_history||[]),...c.decisions,...c.events];
  return cardTitle(analyses?"Rapports d’analyste":"Événements et décisions",button("Fermer","hide-events","close","ghost"))+
    (data.length?data.map((event,index)=>'<details class="event-item" '+(index===0?'open':'')+'><summary><span>'+e(event.kind||event.action||event.role||"Preuve enregistrée")+'</span><small>'+date(event.created||event.created_at)+'</small></summary><pre>'+safeJSON(event)+'</pre></details>').join(""):
      '<p class="muted">Aucune preuve de ce type dans cette campagne.</p>');
}
