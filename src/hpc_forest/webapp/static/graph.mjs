import {escapeHTML as e, seconds, stateName, short} from "./helpers.mjs";
import {icon} from "./icons.mjs";

const pendingStates=new Set(["pending","generating","running","reserved"]);
const inProgress=(node,active)=>active&&node.correct==null&&pendingStates.has(node.state);
const nodeLabel=(node,active)=>inProgress(node,active)?"En cours":seconds(node.seconds);

export function layoutTree(nodes,{parents=new Map(),active=false}={}) {
  const aliases = new Map();
  for (const node of nodes) {
    aliases.set(node.id,node.id);
    if(node.trial_id!=null) aliases.set(node.trial_id,node.id);
  }
  const lookup = new Map(nodes.map(n=>[n.id,n]));
  // A search parent outside this tree is an origin reference, not another trial.
  // Keep it distinct from the root and from delegation/integration provenance.
  const origins=new Map();
  const originId=node=>node.parent==null?null:(parents.get(node.parent)?.id??node.parent);
  if(!nodes.length) origins.set(null,{id:null,label:"Départ",detail:"",source:null});
  for(const node of nodes) {
    if(aliases.has(node.parent)) continue;
    const id=originId(node), source=id==null?null:parents.get(node.parent);
    origins.set(id,{id,source,external:id!=null,
      label:id==null?"Départ":source?"Parent "+(source.role||short(source.id)):"Parent hors vue",
      detail:id==null?"":source?short(source.id)+" · "+seconds(source.seconds):short(id)});
  }
  const anchors=[...origins.values()].map(origin=>({...origin,
    labelWidth:Math.max(76,origin.label.length*7+20,origin.detail.length*6+20)}));
  const depths = new Map();
  const warnings = [];
  function depth(id, stack=new Set()) {
    if (depths.has(id)) return depths.get(id);
    if (stack.has(id)) { warnings.push("cycle"); return 1; }
    stack.add(id);
    const node=lookup.get(id);
    const parent=aliases.get(node.parent);
    const d = parent && lookup.has(parent) ? depth(parent,stack)+1 : 1;
    depths.set(id,d);
    return d;
  }
  for (const node of nodes) depth(node.id);
  const levels = new Map();
  for (const node of nodes) {
    const d=depths.get(node.id);
    if (!levels.has(d)) levels.set(d,[]);
    levels.get(d).push(node.id);
  }
  // Reserve the full label footprint; the board scrolls instead of squeezing it.
  const labelWidths=new Map(nodes.map(n=>[n.id,Math.max(54,nodeLabel(n,active).length*8+20)]));
  const gap=24, margin=24, step=88;
  const levelWidths=new Map([...levels].map(([d,level])=>
    [d,level.reduce((sum,id)=>sum+labelWidths.get(id),0)+Math.max(0,level.length-1)*gap]));
  levelWidths.set(0,anchors.reduce((sum,a)=>sum+a.labelWidth,0)+Math.max(0,anchors.length-1)*gap);
  const width=Math.max(280,...[...levelWidths.values()].map(w=>w+margin*2));
  const height=Math.max(240,(Math.max(1,...depths.values())+1)*step+30);
  const positions=new Map();
  for(const [d,level] of levels) {
    let cursor=(width-levelWidths.get(d))/2;
    for(const id of level) {
      positions.set(id,cursor+labelWidths.get(id)/2);
      cursor+=labelWidths.get(id)+gap;
    }
  }
  let originCursor=(width-levelWidths.get(0))/2;
  for(const anchor of anchors) {
    anchor.x=originCursor+anchor.labelWidth/2;
    anchor.y=42;
    originCursor+=anchor.labelWidth+gap;
  }
  const points = nodes.map(node=>{
    return {...node, x:positions.get(node.id),labelWidth:labelWidths.get(node.id),
      y:42+depths.get(node.id)*step, parentId:aliases.get(node.parent)??null,
      originId:originId(node),
      missingParent:node.parent!=null&&!aliases.has(node.parent)};
  });
  return {width,height,points,anchors,warnings};
}
const palette=["#b9df75","#91cef2","#ebce8d","#c5a5e9","#efb5bb"];
export function forestMarkup(campaign, selected=null,showActivity=true) {
  if (!campaign.trees.length) return '<div class="empty-board">'+icon("code")+'<h3>Aucun arbre enregistré</h3><p>Le graphe apparaîtra lorsque Forest aura créé son plan.</p></div>';
  const parents=new Map();
  const sources=[...campaign.trees.flatMap(t=>t.nodes.map(n=>({...n,role:n.role||t.id}))),
    ...(campaign.integrations||[])];
  for(const source of sources) {
    parents.set(source.id,source);
    if(source.trial_id!=null) parents.set(source.trial_id,source);
  }
  const active=showActivity&&["running","confirming"].includes(campaign.state)&&!campaign.pipeline_complete;
  return campaign.trees.map((tree,index)=>{
    const {width,height,points,anchors,warnings}=layoutTree(tree.nodes,{parents,active});
    const map=new Map(points.map(p=>[p.id,p]));
    const originMap=new Map(anchors.map(a=>[a.id,a]));
    const filter="chalk-"+index;
    const edges=points.map(p=>{
      const parent=p.parentId?map.get(p.parentId):originMap.get(p.originId);
      if(!parent || warnings.length) return "";
      const mid=(parent.y+p.y)/2;
      return '<path class="chalk-edge'+(parent.external?' external-edge':'')+'" d="M '+parent.x+' '+parent.y+' Q '+(parent.x+2)+' '+mid+' '+p.x+' '+p.y+'"/>';
    }).join("");
    const originMarks=anchors.map(a=>{
      const title=a.external?(a.source?"Parent de recherche · "+(a.source.role||short(a.source.id))+" · "+a.source.id+" · "+seconds(a.source.seconds):"Parent de recherche hors de cette vue · "+a.id):"Départ de la recherche";
      const action=a.source?' role="button" tabindex="0" data-node="'+e(a.source.id)+'"':'';
      return '<g class="baseline'+(a.external?' external-parent':'')+(a.source?' parent-link':'')+'"'+action+' aria-label="'+e(title)+'" transform="translate('+a.x+' '+a.y+')"><title>'+e(title)+'</title><circle r="9"/><text y="'+(a.external?-25:-19)+'">'+e(a.label)+'</text>'+(a.detail?'<text class="parent-detail" y="-11">'+e(a.detail)+'</text>':'')+'</g>';
    }).join("");
    const marks=points.map(p=>{
      const pending=pendingStates.has(p.state), working=inProgress(p,active);
      const status=p.correct===false?"incorrect":p.state;
      const cls=p.correct===true?"valid":p.correct===false?"invalid":pending?"pending":"unknown";
      const label=nodeLabel(p,active), description=short(p.id)+" · "+(working?"Essai en cours":stateName(status))+" · "+label;
      return '<g class="node '+cls+(working?' active':'')+(p.id===selected?' selected':'')+'" role="button" tabindex="0" data-node="'+e(p.id)+'" aria-label="'+e(description)+'" transform="translate('+p.x+' '+p.y+')"><title>'+e(description)+'</title><circle class="selection-ring" r="17"/><circle class="node-circle" r="9" style="filter:url(#'+filter+')"/>'+(working?'<circle class="node-spinner" r="13" aria-hidden="true"/>':'')+'<rect class="node-time-bg" x="'+(-p.labelWidth/2)+'" y="18" width="'+p.labelWidth+'" height="23" rx="5"/><text class="node-time" y="33">'+e(label)+'</text></g>';
    }).join("");
    return '<article class="tree" style="--chalk:'+palette[index%palette.length]+";min-width:"+width+"px"+'"><header><h3>Arbre '+e(tree.id)+'</h3><p title="'+e(tree.subject)+'">'+e(tree.subject)+'</p></header><svg class="tree-svg" viewBox="0 0 '+width+' '+height+'" aria-label="'+e("Arbre "+tree.id)+ '"><defs><filter id="'+filter+'" x="-15%" y="-15%" width="130%" height="130%"><feTurbulence type="fractalNoise" baseFrequency=".055" numOctaves="2" seed="12" result="grain"/><feDisplacementMap in="SourceGraphic" in2="grain" scale="1.8"/></filter></defs><g style="filter:url(#'+filter+')">'+edges+'</g>'+originMarks+marks+'</svg><footer><strong>'+tree.nodes.length+' essai'+(tree.nodes.length>1?'s':'')+'</strong><span>'+tree.correct_count+' correct'+(tree.correct_count>1?'s':'')+'</span></footer></article>';
  }).join("");
}
