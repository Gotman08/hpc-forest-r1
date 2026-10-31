import {escapeHTML as e, safeJSON} from "./helpers.mjs";

const number=(name,label,value,extra="")=>'<label class="field">'+e(label)+
  '<input type="number" name="validation_'+name+'" value="'+e(value??"")+'" '+extra+'></label>';
const select=(name,label,value,choices)=>'<label class="field">'+e(label)+
  '<select name="validation_'+name+'">'+choices.map(([key,text])=>'<option value="'+e(key)+'" '+
    (key===value?'selected':'')+'>'+e(text)+'</option>').join("")+'</select></label>';

export function validationControls(contract) {
  const c=contract.execution_validation||{};
  return '<section class="card execution-validation"><h2>Configuration et validation</h2>'+
    select("enabled","Contrôler la configuration",contract.execution_validation?"yes":"no",
      [["no","Profil existant · parallélisme non vérifié"],["yes","Définir un contrat de validation"]])+
    '<fieldset data-validation-fields '+(contract.execution_validation?'':'disabled')+'>'+
    '<p class="small muted">Ces exigences sont figées pour chaque nouvelle campagne. Le contrôle actuel prend en charge une allocation CPU sur un nœud.</p>'+
    number("nodes","Nœuds",c.nodes??1,'min="1" max="1" required')+
    number("sockets_per_node","Processeurs physiques par nœud",c.sockets_per_node,'min="1" max="64" placeholder="Non imposé"')+
    number("cpus_per_task","CPU réservés",c.cpus_per_task??2,'min="1" max="4096" required')+
    number("threads_per_core","Threads matériels maximum par cœur",c.threads_per_core??1,'min="1" max="8" required')+
    select("parallelism","Parallélisme du programme",c.parallelism||"not_required",
      [["not_required","Ressources seules · nombre de threads non imposé"],
       ["gnu_openmp_required","Exiger du calcul parallèle · OpenMP GNU"]])+
    number("required_threads","Threads de calcul attendus",c.required_threads??c.cpus_per_task??2,'min="1" max="4096" required')+
    select("omp_proc_bind","Placement",c.omp_proc_bind||"close",[["close","Proches (close)"],["spread","Répartis (spread)"]])+
    select("omp_places","Placement sur",c.omp_places||"cores",[["cores","Cœurs physiques"],["threads","Threads matériels"]])+
    select("omp_wait_policy","Attente OpenMP",c.omp_wait_policy||"active",[["active","Active"],["passive","Passive"]])+
    '<details><summary>Critères du contrôle de calcul</summary>'+
    number("min_work_cpu_ns","Travail CPU minimum par thread (ns)",c.min_work_cpu_ns??5000,'min="1000" max="1000000000" required')+
    number("min_parallel_cpu_ratio","Rapport minimum CPU de calcul / durée",c.min_parallel_cpu_ratio??1.01,'min="1.001" max="4096" step="any" required')+
    '<p class="small muted">Le contrôle observe les équipes OpenMP GNU, le temps CPU hors synchronisations interceptées et leur placement. Une exécution instrumentée distincte sert de preuve ; elle ne participe pas au score. Du travail artificiel reste à exclure par revue du code.</p></details>'+
    '</fieldset></section>';
}

export function syncValidationControls(form) {
  if(!form) return;
  const enabled=form.querySelector('[name="validation_enabled"]');
  const fields=form.querySelector('[data-validation-fields]');
  if(fields&&enabled) fields.disabled=enabled.value!=="yes";
}

export function validationFormValues(values) {
  const result={...values}, config={};
  const numbers=new Set(["nodes","sockets_per_node","cpus_per_task","threads_per_core",
    "required_threads","min_work_cpu_ns","min_parallel_cpu_ratio"]);
  for(const [key,value] of Object.entries(values)) {
    if(!key.startsWith("validation_")) continue;
    delete result[key];
    const field=key.slice(11);
    if(field!=="enabled") config[field]=numbers.has(field)?(value===""?null:Number(value)):value;
  }
  result.execution_validation=values.validation_enabled==="yes"?config:null;
  return result;
}

export function validationSummary(value={},title="Configuration et validation") {
  const required=value?.required, allocation=value?.allocation;
  const proof=value?.winner||value?.evidence, parallel=proof?.parallelism;
  const region=parallel?.regions?.find(r=>r.passed)||parallel?.regions?.slice(-1)[0];
  const resourceText=required ? required.nodes+' nœud · '+(required.sockets_per_node??"nombre non imposé de")+
    ' processeur(s) · '+required.cpus_per_task+' CPU réservés' : 'Contrat de ressources non enregistré';
  const states={passed:"Parallélisme observé",failed:"Validation refusée",reference_only:"Original de référence · parallélisme non validé",
    not_required:"Parallélisme non exigé"};
  const status=parallel?.status ? states[parallel.status]||"Preuve non reconnue" :
    required?.parallelism==="gnu_openmp_required"?"Parallélisme requis · preuve en attente":"Parallélisme non vérifié";
  return '<section class="card execution-validation"><h2>'+e(title)+'</h2><dl class="key-values">'+
    '<div><dt>Demandé</dt><dd>'+e(resourceText)+'</dd></div>'+
    (required?'<div><dt>Threads de calcul</dt><dd>'+e(required.parallelism==="gnu_openmp_required"?
      required.required_threads+' requis':'Non imposés')+'</dd></div><div><dt>Placement</dt><dd>'+e(required.omp_proc_bind+' / '+required.omp_places+' / '+required.omp_wait_policy)+'</dd></div>':'')+
    '<div><dt>Allocation</dt><dd>'+e(allocation?.status==="passed"?
      allocation.allowed_cpus.length+' CPU · '+allocation.physical_cores+' cœurs · '+allocation.sockets.length+' processeur(s) observés':
      allocation?.status==="failed"?'Non conforme':'Non vérifiée')+'</dd></div>'+
    '<div><dt>Calcul</dt><dd>'+e(status)+'</dd></div>'+
    (region?'<div><dt>Participation</dt><dd>'+e(region.active_threads+' threads avec travail CPU · '+region.distinct_cpus+' CPU distincts')+'</dd></div>':'')+
    '</dl><p class="small muted">CPU réservés et threads de calcul sont vérifiés séparément. La justesse reste soumise aux tests protégés.</p>'+
    (parallel?.limitations?'<p class="small muted">La mesure du travail CPU ne prouve pas à elle seule sa contribution au résultat ; une revue du code reste nécessaire.</p>':'')+
    '<details><summary>Contrat et preuves enregistrées</summary><pre>'+safeJSON(value||{})+'</pre></details></section>';
}
