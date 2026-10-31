import {escapeHTML as e} from "./helpers.mjs";

const fallback=[{id:"gpt-6-luna",label:"GPT-6 Luna",efforts:["max"],provider:"openai",default_effort:"max"}];
let known=fallback;
export function setModelCatalog(models) { known=models?.length?models:fallback; }
export function modelLabel(model="gpt-6-luna",effort="max") {
  return (known.find(m=>m.id===model)?.label||model)+" · "+effort;
}
export function effortSelection(model,wanted,models=known) {
  const entry=models.find(m=>m.id===model), values=entry?.efforts||["max"];
  const preferred=entry?.default_effort||"max";
  return {values,value:values.includes(wanted)?wanted:values.includes(preferred)?preferred:values[0]};
}
export function modelHelp(model,info) {
  const entry=info.models?.find(m=>m.id===model);
  if(entry?.provider==="dsh-romeo") return info.connection?.dsh_romeo_configured?
    "DeepSeek sur ROMEO : la passerelle et le modèle doivent déjà fonctionner. Forest vérifie leur accès au lancement. none désactive la réflexion.":
    "DeepSeek sur ROMEO : renseignez dsh_romeo.base_url et dsh_romeo.api_key_file dans romeo.json. Utilisez une passerelle accessible depuis les nœuds de calcul. none désactive la réflexion.";
  return "OpenAI via votre connexion ChatGPT sur ROMEO. La disponibilité du modèle est vérifiée au lancement.";
}
export function requiresDsh(contract,models=known) {
  return [contract,...(contract.generator_pool||[])].some(p=>
    models.find(m=>m.id===p.model)?.provider==="dsh-romeo");
}
export function modelFields(contract,info) {
  const models=info.models?.length?info.models:fallback;
  const providers=[...new Set(models.map(m=>m.provider||"openai"))];
  const effort=effortSelection(contract.model,contract.reasoning_effort,models);
  return '<label class="field">Modèle<select name="model" id="model-choice">'+providers.map(provider=>
    '<optgroup label="'+(provider==="dsh-romeo"?'ROMEO · dsh-romeo':'OpenAI · ChatGPT')+'">'+
    models.filter(m=>(m.provider||"openai")===provider).map(m=>'<option value="'+e(m.id)+'" '+
      (contract.model===m.id?'selected':'')+'>'+e(m.label)+'</option>').join("")+'</optgroup>').join("")+
    '</select><small id="model-help">'+e(modelHelp(contract.model,info))+'</small></label>'+
    '<label class="field">Effort<select name="reasoning_effort" id="effort-choice">'+effort.values.map(v=>
      '<option value="'+e(v)+'" '+(effort.value===v?'selected':'')+'>'+e(v)+'</option>').join("")+
    '</select><small>Modèle principal pour tous les rôles, sauf générateurs explicitement ajoutés ci-dessous. Figé au lancement.</small></label>';
}
