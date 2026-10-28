import {escapeHTML as e, seconds} from "./helpers.mjs";

export const searchChoices = [
  ["ab-mcts-a/gaussian","AB-MCTS-A · gaussien (défaut)"],
  ["ab-mcts-a/beta","AB-MCTS-A · bêta"],
  ["ab-mcts-m","AB-MCTS-M · expérimental"],
  ["standard-mcts","MCTS classique · témoin"],
  ["repeated-sampling","Essais indépendants · témoin"],
  ["sequential-refinement","Raffinement séquentiel · témoin"]
];

export function searchControls(contract,info) {
  const policy=contract.search||{algorithm:"ab-mcts-a",distribution:"gaussian"};
  const selected=policy.algorithm+(policy.algorithm==="ab-mcts-a"?"/"+policy.distribution:"");
  const pool=contract.generator_pool||[], models=info.models||[{id:"gpt-6-luna",label:"GPT-6 Luna",efforts:["max"]}];
  const canM=info.connection?.search_algorithms?.[contract.target]?.includes("ab-mcts-m");
  return '<section class="card"><h2>Stratégie de recherche</h2><label class="field">Exploration<select name="search_policy">'+
    searchChoices.map(([id,label])=>'<option value="'+id+'" '+(id===selected?'selected ':'')+(id==="ab-mcts-m"&&!canM?'disabled':'')+'>'+label+(id==="ab-mcts-m"&&!canM?' · profil requis':'')+'</option>').join("")+'</select><small>TreeQuest de Sakana AI. Le défaut conserve la recherche actuelle.</small></label>'+
    '<label class="pool-toggle"><input type="checkbox" name="mix_generators" '+(pool.length?'checked':'')+'> Choix adaptatif entre plusieurs modèles</label>'+
    '<p class="muted small">Désactivé : le modèle principal fait tout. Activé : seuls les générateurs changent de modèle ; Mother et les analystes gardent le modèle principal.</p>'+
    '<div id="generator-options" '+(pool.length?'':'hidden')+'>'+models.map(m=>{
      const choice=pool.find(p=>p.model===m.id), primary=contract.model===m.id;
      return '<div class="generator-option"><label><input type="checkbox" name="generator_'+e(m.id)+'" data-generator="'+e(m.id)+'" '+(choice||primary?'checked':'')+'> '+e(m.label)+'</label>'+
        '<select name="generator_effort_'+e(m.id)+'" aria-label="Effort '+e(m.label)+'">'+m.efforts.map(v=>'<option '+(v===(choice?.reasoning_effort||"max")?'selected':'')+'>'+e(v)+'</option>').join("")+'</select></div>';
    }).join("")+'<small>Le modèle principal est inclus avec son effort. Choisissez au moins un autre modèle.</small></div>'+
    '<label class="pool-toggle"><input type="checkbox" name="diversity_archive" '+(contract.evolution?.enabled?'checked':'')+'> Conserver des variantes différentes</label>'+
    '<p class="muted small">Garder des codes corrects variés, même moins rapides, comme pistes pour les analyses et combinaisons.</p></section>';
}

export function searchFormValues(data) {
  const [algorithm,distribution]=(data.search_policy||"ab-mcts-a/gaussian").split("/");
  const search={algorithm,...(algorithm==="ab-mcts-a"?{distribution}:{} )};
  const generator_pool=[];
  if(data.mix_generators) {
    generator_pool.push({model:data.model,reasoning_effort:data.reasoning_effort});
    for(const model of ["gpt-6-luna","gpt-6.1-sol","gpt-6-astra"]) {
      if(model!==data.model&&data["generator_"+model]) generator_pool.push({model,reasoning_effort:data["generator_effort_"+model]});
    }
    if(generator_pool.length<2) throw new Error("Choisissez au moins un autre modèle pour activer le mélange.");
  }
  const clean=Object.fromEntries(Object.entries(data).filter(([key])=>
    key!=="search_policy"&&key!=="mix_generators"&&!key.startsWith("generator_")&&key!=="__checks"&&key!=="diversity_archive"));
  return {...clean,search,generator_pool,evolution:{enabled:!!data.diversity_archive}};
}

export function syncGeneratorControls(form) {
  if(!form) return;
  const enabled=form.elements.namedItem("mix_generators")?.checked;
  const options=form.querySelector("#generator-options");
  if(!options) return;
  options.hidden=!enabled;
  for(const item of options.querySelectorAll("input,select")) item.disabled=!enabled;
  const primary=form.elements.namedItem("model").value;
  const chosen=options.querySelector('[data-generator="'+primary+'"]');
  if(chosen) { chosen.checked=true; chosen.disabled=true; }
  const effort=form.elements.namedItem("generator_effort_"+primary);
  if(effort) { effort.value=form.elements.namedItem("reasoning_effort").value; effort.disabled=true; }
}

export function searchSummary(campaign) {
  const d=campaign.search_diagnostics;
  if(!d) return "";
  const trees=d.trees||[], total=key=>trees.reduce((n,t)=>n+(t[key]||0),0);
  return '<section class="card"><h2>Exploration mesurée</h2><p><strong>'+e(d.policy)+'</strong></p>'+
    '<dl class="key-values small"><div><dt>Essais depuis la racine</dt><dd>'+total("root_trials")+'</dd></div><div><dt>Essais depuis un parent</dt><dd>'+total("refinements")+'</dd></div><div><dt>Profondeur maximale</dt><dd>'+Math.max(0,...trees.map(t=>t.max_depth))+'</dd></div></dl>'+
    '<details><summary>Générateurs utilisés</summary>'+d.models.map(m=>'<p class="small"><strong>'+e(m.model)+(m.effort?' · '+e(m.effort):'')+'</strong><br>'+m.admitted+' essais · '+m.correct+' corrects · '+m.unscored+' sans score<br>Meilleur essai : '+seconds(m.best_seconds)+'</p>').join("")+'</details>'+
    '<p class="muted tiny">Essais admis, y compris les échecs. Les générateurs n’ont pas reçu les mêmes programmes : ce tableau ne les classe pas.</p>'+
    (campaign.advisor?.enabled?'<p class="small"><strong>Conseiller TabPFN — historique archivé</strong><br>'+Number(campaign.advisor.calls||0)+' appels · '+Number(campaign.advisor.reorders||0)+(campaign.advisor.scope==="treequest_parent_proposals"?' choix de parent modifiés · ':' priorités modifiées · ')+seconds(campaign.advisor.seconds||0)+'<br>État : '+e(campaign.advisor.last_status||"Aucun avis émis")+'</p>':'')+'</section>';
}
