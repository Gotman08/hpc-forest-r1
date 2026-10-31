import test from "node:test";
import assert from "node:assert/strict";
import {layoutTree,forestMarkup} from "../src/hpc_forest/webapp/static/graph.mjs";
import {remoteMissionView} from "../src/hpc_forest/webapp/static/views.mjs";

const tree=(id,nodes)=>({id,subject:"Recherche",nodes,correct_count:nodes.filter(n=>n.correct===true).length});

test("Cross-tree refinements show their actual parent without adding a trial or a baseline edge",()=>{
  const source={id:"original",trial_id:"trial-original",role:"T5",parent:null,state:"valid",correct:true,seconds:9.6};
  const children=[{id:"first",parent:"original"},{id:"second",parent:"trial-original"}];
  const parents=new Map([[source.id,source],[source.trial_id,source]]);
  const layout=layoutTree(children,{parents});
  assert.equal(layout.points.length,2);
  assert.equal(layout.anchors.length,1);
  assert.equal(layout.anchors[0].source.id,"original");
  assert(layout.points.every(p=>p.originId==="original"&&p.parentId===null));
  const html=forestMarkup({trees:[tree("T5",[source]),tree("T6",children)]});
  const t6=html.split("<article")[2];
  assert.equal((t6.match(/class="chalk-edge external-edge"/g)||[]).length,2);
  assert(t6.includes("Parent T5")&&t6.includes('data-node="original"'));
  assert(!t6.includes("Départ"));
  assert(t6.includes("2 essais"));
});

test("Roots, local search parents, integration parents and unknown parents remain distinct",()=>{
  const integrated={id:"combined",role:"Gm1",seconds:.1};
  const nodes=[{id:"a",parent:null,delegation_parent:"R/T9",base_source_id:"combined"},
    {id:"b",parent:"a"},{id:"c",parent:"combined"},{id:"d",parent:"unavailable"}];
  const layout=layoutTree(nodes,{parents:new Map([[integrated.id,integrated]])});
  assert.equal(layout.points[1].parentId,"a");
  assert.deepEqual(layout.anchors.map(a=>a.label),["Départ","Parent Gm1","Parent hors vue"]);
  const html=forestMarkup({trees:[tree("T9",nodes)],integrations:[integrated]});
  assert.equal((html.match(/class="chalk-edge"/g)||[]).length,2);
  assert.equal((html.match(/class="chalk-edge external-edge"/g)||[]).length,2);
  assert(html.includes('data-node="combined"'));
  assert(!html.includes('data-node="unavailable"'));
  assert(!html.includes("R/T9"));
  assert(html.includes("4 essais"));
});

test("Multiple external parents reserve space for both labels and identify the right origin",()=>{
  const sources=Array.from({length:5},(_,i)=>({id:"source-"+i,role:"T"+i,seconds:1234567.89}));
  const nodes=sources.map(s=>({id:"child-"+s.id,parent:s.id}));
  const layout=layoutTree(nodes,{parents:new Map(sources.map(s=>[s.id,s]))});
  assert.equal(layout.anchors.length,5);
  for(let i=0;i<layout.anchors.length;i++) {
    const a=layout.anchors[i];
    assert.equal(layout.points[i].originId,a.id);
    assert(a.x-a.labelWidth/2>=0&&a.x+a.labelWidth/2<=layout.width);
    if(i) assert(layout.anchors[i-1].x+layout.anchors[i-1].labelWidth/2<a.x-a.labelWidth/2);
  }
});

test("Active trials get a loading ring and a readable status until their evaluation completes",()=>{
  const nodes=["pending","generating","running","reserved"].map(state=>({id:state,state,correct:null}));
  const campaign={state:"running",trees:[tree("T7",nodes)]};
  const html=forestMarkup(campaign);
  assert.equal((html.match(/class="node-spinner"/g)||[]).length,4);
  assert.equal((html.match(/class="node-time" y="33">En cours/g)||[]).length,4);
  assert(layoutTree(nodes,{active:true}).points.every(p=>p.labelWidth>=84));
  nodes[0]={...nodes[0],state:"valid",correct:true,seconds:.036};
  const completed=forestMarkup(campaign);
  assert.equal((completed.match(/class="node-spinner"/g)||[]).length,3);
  assert(completed.includes('class="node-time" y="33">36 ms'));
});

test("Stopped campaigns and trials with a verdict never appear to be still computing",()=>{
  const nodes=[{id:"pending",state:"pending"},{id:"invalid",state:"pending",correct:false},
    {id:"valid",state:"pending",correct:true},{id:"infra",state:"infrastructure_error"}];
  const trees=[tree("T1",nodes)];
  for(const state of ["failed","cancelled","confirmed","no_gain","unconfirmed","completed"]) {
    assert(!forestMarkup({state,trees}).includes('class="node-spinner"'));
  }
  assert(!forestMarkup({state:"running",pipeline_complete:true,trees}).includes('class="node-spinner"'));
  const active=forestMarkup({state:"running",trees});
  assert.equal((active.match(/class="node-spinner"/g)||[]).length,1);
});

test("External parent labels and identifiers are escaped, including unknown references",()=>{
  const parent={id:'p" onclick="alert(1)',role:"<script>bad</script>"};
  const html=forestMarkup({trees:[tree("T",[{id:"child",parent:parent.id},{id:"orphan",parent:"<img>"}])],
    integrations:[parent]});
  assert(!html.includes("<script>")&&!html.includes("<img>")&&!html.includes(' onclick="'));
  assert(html.includes("&lt;script&gt;")&&html.includes("&lt;img&gt;"));
});

test("A terminal mission does not animate pending trials from its last running snapshot",()=>{
  const campaign={state:"running",trial_count:1,trees:[tree("T1",[{id:"pending",state:"pending"}])],
    integrations:[],analyses:[],decisions:[]};
  assert(remoteMissionView({state:"running"},campaign).includes('class="node-spinner"'));
  for(const state of ["failed","cancelled","completed","recovery_required"])
    assert(!remoteMissionView({state},campaign).includes('class="node-spinner"'));
});
