import {api, escapeHTML as e} from "./helpers.mjs";
import {searchFormValues, syncGeneratorControls} from "./search.mjs";
import {shell, empty, projectView, prepareView, preparedView, missionView, trialPane,
  resultsView, historyView, settingsView, eventsView, remoteMissionView, modelLabel} from "./views.mjs";

const app = document.querySelector("#app");
const state = {info:null, projects:[], campaigns:[], project:null, campaign:null, prepared:null,
  uploads:[], uploadName:"", trial:null, source:null, tab:"tests", zoom:1, history:[],
  filter:"", query:"", attachmentRole:"statement", busy:false, dirty:false, drafts:new Map(),context:null, mission:null};
let navigation = 0, selection = 0, notificationTimer;
const remembered = key => { try { return localStorage.getItem(key); } catch { return null; } };
const remember = (key,value) => { try { localStorage.setItem(key,value); } catch { /* Optional. */ } };
try {
  const saved=JSON.parse(remembered("forest.context"));
  if(saved&&["new","project","prepared","campaign","mission"].includes(saved.kind)&&typeof saved.id==="string") state.context=saved;
} catch { /* No saved selection. */ }
const context = (kind,id) => { state.context={kind,id}; remember("forest.context",JSON.stringify(state.context)); };
const notify = (message,error=false) => {
  const el=document.querySelector("#notice");
  el.textContent=message; el.className="notice visible"+(error?" error":"");
  clearTimeout(notificationTimer); notificationTimer=setTimeout(()=>el.classList.remove("visible"),6500);
};
const go = hash => { if(location.hash===hash) render(); else location.hash=hash; };
const main = () => document.querySelector("#main");
const projectId = () => state.project?.id || remembered("forest.project");
const campaignId = () => state.context?.kind==="campaign"?state.context.id:
  state.context?null:remembered("forest.campaign")||state.campaigns[0]?.id;
const selectProject = value => { state.project=value; remember("forest.project",value.id); context("project",value.id); };
function effortOptions(model, wanted) {
  const field=document.querySelector("#effort-choice");
  const values=state.info.models.find(m=>m.id===model)?.efforts||["max"];
  field.innerHTML=values.map(v=>'<option value="'+e(v)+'">'+e(v)+'</option>').join("");
  field.value=values.includes(wanted)?wanted:"max";
}

async function catalog() {
  [state.info,state.projects,state.campaigns]=await Promise.all([
    api("/info"),api("/projects"),api("/campaigns")]);
}

async function render() {
  const token=++navigation; ++selection; state.dirty=false;
  let [,page="project",kind,id]=(location.hash||"#/project").split("/");
  if(!["project","prepare","mission","results","history","settings"].includes(page)) page="project";
  app.innerHTML=shell(page);
  main().innerHTML='<div class="loading-state"><span class="spinner"></span>Chargement de votre espace…</div>';
  try {
    await catalog();
    if(token!==navigation) return;
    let html,name="";
    if(page==="project") {
      if(kind==="new") { state.project=null; context("new",""); }
      else {
        const chosen=kind||projectId();
        if(chosen && state.projects.some(p=>p.id===chosen)) {
          const record=await api("/projects/"+chosen); if(token!==navigation) return; selectProject(record);
        }
        else state.project=null;
      }
      name=state.project?.name||"";
      html=projectView(state.project,state.uploads,state.projects);
    } else if(page==="prepare") {
      const chosen=kind||projectId();
      if(chosen) {
        const record=await api("/projects/"+chosen); if(token!==navigation) return;
        selectProject(record); name=state.project.name;
        html=prepareView(state.project,state.info);
      } else html=empty("Commencez par votre projet","Déposez le code avant de préparer sa vérification.",
        '<a class="button primary" href="#/project/new">Déposer un projet</a>');
    } else if(page==="mission") {
      if(!kind&&state.context?.kind==="prepared") { kind="prepared"; id=state.context.id; }
      if(!kind&&state.context?.kind==="mission") { kind="run"; id=state.context.id; }
      if(kind==="run"&&id) {
        const mission=await api("/missions/"+id); if(token!==navigation) return;
        state.mission=mission; context("mission",id); name=mission.name; state.trial=null;
        state.campaign=mission.campaign_id?await api("/campaigns/"+mission.campaign_id):null;
        html=remoteMissionView(mission,state.campaign);
      } else if(kind==="prepared"&&id) {
        const record=await api("/prepared/"+id); if(token!==navigation) return;
        state.prepared=record; name=state.prepared.name; context("prepared",id);
        html=preparedView(state.prepared,state.info);
      } else {
        const chosen=kind==="campaign"?id:campaignId();
        if(chosen) {
          const record=await api("/campaigns/"+chosen); if(token!==navigation) return;
          state.campaign=record;
          remember("forest.campaign",chosen); context("campaign",chosen); state.trial=null; state.source=null; state.zoom=1;
          name=state.campaign.name; html=missionView(state.campaign);
        } else html=empty("Aucune campagne lancée pour ce projet","Préparez son dossier, ou consultez une autre campagne dans l’historique.",
          '<a class="button primary" href="#/prepare">Préparer le projet</a>');
      }
    } else if(page==="results") {
      let chosen=kind||campaignId();
      if(!chosen&&state.context?.kind==="mission") {
        const mission=await api("/missions/"+state.context.id); chosen=mission.campaign_id;
      }
      if(chosen) {
        const record=await api("/campaigns/"+chosen); if(token!==navigation) return;
        state.campaign=record; remember("forest.campaign",chosen);
        if(record.mission_id) {
          state.mission=await api("/missions/"+record.mission_id); context("mission",record.mission_id);
        } else context("campaign",chosen);
        name=state.campaign.name; html=resultsView(state.campaign);
      } else html=empty("Aucun résultat pour ce projet","Aucune campagne n’a été confirmée pour le projet sélectionné. Les campagnes existantes restent dans l’historique.",
        '<a class="button secondary" href="#/history">Voir l’historique</a>');
    } else if(page==="history") {
      state.history=await api("/history"); html=historyView(state.history,state.filter,state.query);
    } else html=settingsView(state.info,state.campaigns.length);
    if(token!==navigation) return;
    const selected=state.context?.kind==="mission"?state.mission:state.context?.kind==="campaign"?state.campaign:state.context?.kind==="prepared"?{model:state.prepared?.contract.model,effort:state.prepared?.contract.reasoning_effort}:state.project;
    app.innerHTML=shell(page,name,modelLabel(selected?.model,selected?.effort)); main().innerHTML=html;
    const draft=page==="prepare"&&state.drafts.get(state.project?.id);
    if(draft) {
      const form=document.querySelector("#contract-form");
      effortOptions(draft.model,draft.reasoning_effort);
      for(const [key,value] of Object.entries(draft)) {
        const field=form.elements.namedItem(key);
        if(field&&field.type!=="checkbox") field.value=value;
      }
      for(const [key,value] of Object.entries(draft.__checks||{})) {
        const field=form.elements.namedItem(key); if(field) field.checked=value;
      }
      state.dirty=true;
      document.querySelector("#save-state").textContent="Brouillon restauré · à enregistrer";
      document.querySelector('[data-action="prepare"]').disabled=true;
    }
    syncGeneratorControls(document.querySelector("#contract-form"));
    if(page==="project"&&!state.project) document.querySelector("#project-name").value=state.uploadName;
    document.title=(name?name+" · ":"")+"Forest — Espace de travail";
  } catch(error) {
    if(token!==navigation) return;
    main().innerHTML=empty("Cet écran n’est pas disponible",e(error.message),
      '<button class="button primary" data-action="retry">Réessayer</button>');
  }
}

async function operation(callback) {
  if(state.busy) return;
  state.busy=true; app.setAttribute("aria-busy","true"); document.body.classList.add("working");
  try { await callback(); }
  catch(error) { notify(error.message,true); }
  finally { state.busy=false; app.removeAttribute("aria-busy"); document.body.classList.remove("working"); }
}

function acceptFiles(files) {
  const ignored=new Set([".git",".venv","node_modules","__pycache__",".pytest_cache",".ruff_cache"]);
  const chosen=files.filter(file=>!(file.relativePath||file.webkitRelativePath||file.name)
    .replaceAll("\\","/").split("/").some(p=>ignored.has(p.toLowerCase())));
  if(!chosen.length) throw new Error("Aucun fichier de projet à importer.");
  if(chosen.length>state.info.limits.file_count) throw new Error("Le projet dépasse 2 000 fichiers.");
  if(chosen.reduce((n,f)=>n+f.size,0)>state.info.limits.upload_bytes) throw new Error("Le dépôt dépasse 64 Mio.");
  state.uploadName=document.querySelector("#project-name")?.value||state.uploadName;
  state.uploads=chosen;
  main().innerHTML=projectView(null,chosen,state.projects);
  document.querySelector("#project-name").value=state.uploadName;
}

async function droppedFiles(transfer) {
  const roots=[...transfer.items].filter(i=>i.kind==="file").map(i=>i.webkitGetAsEntry?.());
  if(!roots.length || roots.some(r=>!r)) return [...transfer.files];
  const files=[];
  async function visit(entry,prefix="",depth=0) {
    if(depth>20||files.length>2000) throw new Error("Ce dossier dépasse les limites d’import.");
    if([".git",".venv","node_modules","__pycache__"].includes(entry.name.toLowerCase())) return;
    if(entry.isFile) {
      const file=await new Promise((resolve,reject)=>entry.file(resolve,reject));
      file.relativePath=prefix+file.name; files.push(file);
    } else {
      const reader=entry.createReader();
      while(true) {
        const entries=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));
        if(!entries.length) break;
        for(const child of entries) await visit(child,prefix+entry.name+"/",depth+1);
      }
    }
  }
  for(const root of roots) await visit(root);
  return files;
}

function formContract() {
  const form=document.querySelector("#contract-form");
  if(!form.reportValidity()) return null;
  const data=searchFormValues(Object.fromEntries(new FormData(form)));
  data.duration_minutes=Number(data.duration_minutes);
  data.editable_paths=data.editable_paths.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  return data;
}
async function saveContract() {
  const value=formContract(); if(!value) return false;
  selectProject(await api("/projects/"+state.project.id+"/contract",{method:"PUT",body:JSON.stringify(value)}));
  state.drafts.delete(state.project.id); state.dirty=false; return true;
}

async function selectTrial(id) {
  const token=++selection, route=navigation;
  state.source=null;
  const trial=await api("/campaigns/"+state.campaign.id+"/trials/"+encodeURIComponent(id));
  if(token!==selection||route!==navigation) return;
  state.trial=trial;
  document.querySelectorAll(".node").forEach(n=>n.classList.toggle("selected",n.dataset.node===id));
  await showTrialTab(state.tab);
}
async function showTrialTab(tab,path) {
  if(!state.trial) return;
  const token=++selection, route=navigation, trial=state.trial;
  state.tab=tab;
  const panel=document.querySelector("#trial-panel"); if(!panel) return;
  panel.innerHTML=trialPane(trial,state.source,tab);
  if(["code","diff"].includes(tab)&&trial.files.length) {
    const name=path||state.source?.path||trial.files[0];
    const result=await api("/campaigns/"+state.campaign.id+"/trials/"+trial.id+"/source?path="+encodeURIComponent(name));
    if(token!==selection||route!==navigation) return;
    state.source=result; panel.innerHTML=trialPane(trial,result,tab);
  }
}

app.addEventListener("click",event=>{
  const node=event.target.closest("[data-node]");
  if(node) { operation(()=>selectTrial(node.dataset.node)); return; }
  const tab=event.target.closest("[data-tab]");
  if(tab) { operation(()=>showTrialTab(tab.dataset.tab)); return; }
  const action=event.target.closest("[data-action]");
  if(!action||action.disabled) return;
  event.preventDefault();
  const name=action.dataset.action;
  if(name==="choose-files"||name==="choose-folder") {
    document.querySelector(name==="choose-files"?"#files-input":"#folder-input").click(); return;
  }
  if(name==="new-project") { state.uploads=[]; state.uploadName=""; go("#/project/new"); return; }
  if(name==="attach") { state.attachmentRole=action.dataset.role; document.querySelector("#attachment-input").click(); return; }
  if(name.startsWith("zoom-")) {
    state.zoom=name==="zoom-fit"?1:Math.max(.5,Math.min(2,state.zoom+(name==="zoom-in"?.15:-.15)));
    document.querySelector(".forest-canvas").style.zoom=state.zoom;
    document.querySelector("#zoom-value").textContent=Math.round(state.zoom*100)+" %"; return;
  }
  if(name==="show-events"||name==="show-analyses") {
    const panel=document.querySelector("#events-panel"); panel.hidden=false;
    panel.innerHTML=eventsView(state.campaign,name==="show-analyses"); panel.scrollIntoView({behavior:"smooth",block:"start"}); return;
  }
  if(name==="hide-events") { document.querySelector("#events-panel").hidden=true; return; }
  operation(async()=>{
    if(name==="retry") await render();
    else if(name==="import") {
      const form=new FormData();
      for(const file of state.uploads) form.append("files",file,file.name);
      form.append("paths",JSON.stringify(state.uploads.map(f=>f.relativePath||f.webkitRelativePath||f.name)));
      form.append("name",document.querySelector("#project-name").value.trim()||state.uploads[0]?.name||"Projet");
      selectProject(await api("/projects",{method:"POST",body:form})); state.uploads=[];
      notify("Projet importé. Complétez son contrat de vérification."); go("#/prepare/"+state.project.id);
    } else if(name==="migrate-project") {
      selectProject(await api("/projects/"+state.project.id+"/migrate",{method:"POST"}));
      notify("Nouvelle copie créée ; l’original est conservé."); go("#/prepare/"+state.project.id);
    } else if(name==="resume-tracking") {
      state.mission=await api("/missions/"+state.mission.id+"/resume-tracking",{method:"POST"});
      notify("Réconciliation du job existant demandée."); await render();
    } else if(name==="stop") {
      state.mission=await api("/missions/"+state.mission.id+"/stop",{method:"POST"});
      notify("Demande d’arrêt sauvegardée."); await render();
    } else if(name==="launch") {
      const mission=await api("/prepared/"+state.prepared.id+"/launch",{method:"POST"});
      state.mission=mission; context("mission",mission.id);
      notify("Mission prise en charge. Le suivi est sauvegardé."); go("#/mission/run/"+mission.id);
    } else if(name==="prepare") {
      if(!await saveContract()) return;
      const mission=await api("/projects/"+state.project.id+"/prepare",{method:"POST"});
      state.prepared=mission; context("prepared",mission.id); notify("Le dossier de mission est sauvegardé."); go("#/mission/prepared/"+mission.id);
    }
  });
});

app.addEventListener("submit",event=>{
  if(event.target.id!=="contract-form") return;
  event.preventDefault(); operation(async()=>{
    if(await saveContract()) { main().innerHTML=prepareView(state.project,state.info); syncGeneratorControls(document.querySelector("#contract-form")); notify("Contrat sauvegardé."); }
  });
});
app.addEventListener("input",event=>{
  if(event.target.id==="model-choice") {
    effortOptions(event.target.value,document.querySelector("#effort-choice").value);
  }
  if(event.target.closest("#contract-form")) {
    const form=document.querySelector("#contract-form");
    syncGeneratorControls(form);
    state.dirty=true;
    state.drafts.set(state.project.id,{...Object.fromEntries(new FormData(form)),
      __checks:Object.fromEntries([...form.querySelectorAll('input[type="checkbox"]')].map(el=>[el.name,el.checked]))});
    document.querySelector("#save-state").textContent="Modifications à enregistrer";
    // Saving validates readiness; preparing remains disabled until that validation.
    document.querySelector('[data-action="prepare"]').disabled=true;
  }
  if(event.target.id==="project-name") state.uploadName=event.target.value;
  if(event.target.id==="history-search") {
    state.query=event.target.value;
    const start=event.target.selectionStart;
    main().innerHTML=historyView(state.history,state.filter,state.query);
    const search=document.querySelector("#history-search"); search.focus(); search.setSelectionRange(start,start);
  }
});
app.addEventListener("change",event=>operation(async()=>{
  const el=event.target;
  if(["files-input","folder-input"].includes(el.id)) {
    if(el.files.length) acceptFiles([...el.files]);
  } else if(el.id==="project-picker") go(el.value?"#/project/"+el.value:"#/project/new");
  else if(el.id==="source-file") await showTrialTab(state.tab,el.value);
  else if(el.id==="history-filter") { state.filter=el.value; main().innerHTML=historyView(state.history,state.filter,state.query); }
  else if(el.id==="attachment-input"&&el.files.length) {
    const form=new FormData(); form.append("file",el.files[0]); form.append("role",state.attachmentRole);
    selectProject(await api("/projects/"+state.project.id+"/attachments",{method:"POST",body:form}));
    main().innerHTML=projectView(state.project,[],state.projects); notify("Document ajouté au projet.");
  }
}));
app.addEventListener("keydown",event=>{
  if(!["Enter"," "].includes(event.key)) return;
  if(event.target.matches("[data-node]")) { event.preventDefault(); operation(()=>selectTrial(event.target.dataset.node)); }
  else if(event.target.id==="dropzone") { event.preventDefault(); document.querySelector("#files-input").click(); }
});
app.addEventListener("dragover",event=>{
  const zone=event.target.closest("#dropzone");
  if(zone) { event.preventDefault(); zone.classList.add("dragging"); }
});
app.addEventListener("dragleave",event=>event.target.closest("#dropzone")?.classList.remove("dragging"));
app.addEventListener("drop",event=>{
  if(!event.target.closest("#dropzone")) return;
  event.preventDefault();
  // Capture entries while the browser's DataTransfer is still readable.
  const files=droppedFiles(event.dataTransfer);
  operation(async()=>acceptFiles(await files));
});
window.addEventListener("hashchange",render);
document.querySelector(".skip-link").addEventListener("click",event=>{ event.preventDefault(); main()?.focus(); });
window.addEventListener("beforeunload",event=>{ if(state.drafts.size) { event.preventDefault(); event.returnValue=""; } });
render();
setInterval(()=>{
  const following=location.hash.startsWith("#/mission/run/") ||
    (location.hash==="#/mission"&&state.context?.kind==="mission");
  if(following&&!state.busy&&!state.trial&&state.mission?.state!=="completed") render();
},10000);
