import {escapeHTML as e, seconds, stateName, short} from "./helpers.mjs";
import {icon} from "./icons.mjs";

export function layoutTree(nodes) {
  const aliases = new Map();
  for (const node of nodes) {
    aliases.set(node.id,node.id);
    if(node.trial_id!=null) aliases.set(node.trial_id,node.id);
  }
  const lookup = new Map(nodes.map(n=>[n.id,n]));
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
  const labelWidths=new Map(nodes.map(n=>[n.id,Math.max(54,seconds(n.seconds).length*8+20)]));
  const gap=24, margin=24, step=88;
  const levelWidths=new Map([...levels].map(([d,level])=>
    [d,level.reduce((sum,id)=>sum+labelWidths.get(id),0)+Math.max(0,level.length-1)*gap]));
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
  const points = nodes.map(node=>{
    return {...node, x:positions.get(node.id),labelWidth:labelWidths.get(node.id),
      y:42+depths.get(node.id)*step, parentId:aliases.get(node.parent)??null,
      missingParent:node.parent!=null&&!aliases.has(node.parent)};
  });
  return {width,height,points,warnings};
}
const palette=["#b9df75","#91cef2","#ebce8d","#c5a5e9","#efb5bb"];
export function forestMarkup(campaign, selected=null) {
  if (!campaign.trees.length) return '<div class="empty-board">'+icon("code")+'<h3>Aucun arbre enregistré</h3><p>Le graphe apparaîtra lorsque Forest aura créé son plan.</p></div>';
  return campaign.trees.map((tree,index)=>{
    const {width,height,points,warnings}=layoutTree(tree.nodes);
    const map=new Map(points.map(p=>[p.id,p]));
    const root={x:width/2,y:42};
    const filter="chalk-"+index;
    const edges=points.map(p=>{
      const parent=p.parentId?map.get(p.parentId):root;
      if(!parent || p.missingParent || warnings.length) return "";
      const mid=(parent.y+p.y)/2;
      return '<path class="chalk-edge" d="M '+parent.x+' '+parent.y+' Q '+(parent.x+2)+' '+mid+' '+p.x+' '+p.y+'"/>';
    }).join("");
    const marks=points.map(p=>{
      const pending=["pending","generating","running","reserved"].includes(p.state);
      const status=p.correct===false?"incorrect":p.state;
      const cls=p.correct===true?"valid":p.correct===false?"invalid":pending?"pending":"unknown";
      const label=seconds(p.seconds);
      return '<g class="node '+cls+(p.id===selected?' selected':'')+'" role="button" tabindex="0" data-node="'+e(p.id)+'" aria-label="'+e(short(p.id)+" · "+stateName(status)+" · "+label)+'" transform="translate('+p.x+' '+p.y+')"><title>'+e(short(p.id)+" · "+stateName(status)+" · "+label)+'</title><circle class="selection-ring" r="15"/><circle class="node-circle" r="9" style="filter:url(#'+filter+')"/><rect class="node-time-bg" x="'+(-p.labelWidth/2)+'" y="18" width="'+p.labelWidth+'" height="23" rx="5"/><text class="node-time" y="33">'+e(label)+'</text></g>';
    }).join("");
    return '<article class="tree" style="--chalk:'+palette[index%palette.length]+";min-width:"+width+"px"+'"><header><h3>Arbre '+e(tree.id)+'</h3><p title="'+e(tree.subject)+'">'+e(tree.subject)+'</p></header><svg class="tree-svg" viewBox="0 0 '+width+' '+height+'" aria-label="'+e("Arbre "+tree.id)+ '"><defs><filter id="'+filter+'" x="-15%" y="-15%" width="130%" height="130%"><feTurbulence type="fractalNoise" baseFrequency=".055" numOctaves="2" seed="12" result="grain"/><feDisplacementMap in="SourceGraphic" in2="grain" scale="1.8"/></filter></defs><g style="filter:url(#'+filter+')">'+edges+'</g><g class="baseline" transform="translate('+root.x+' '+root.y+')"><circle r="9"/><text y="-19">Départ</text></g>'+marks+'</svg><footer><strong>'+tree.nodes.length+' essai'+(tree.nodes.length>1?'s':'')+'</strong><span>'+tree.correct_count+' correct'+(tree.correct_count>1?'s':'')+'</span></footer></article>';
  }).join("");
}
