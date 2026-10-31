import test from "node:test";
import assert from "node:assert/strict";
import {escapeHTML, seconds, speedup, finite, routeFor} from "../src/hpc_forest/webapp/static/helpers.mjs";
import {layoutTree, forestMarkup} from "../src/hpc_forest/webapp/static/graph.mjs";
import {missionView, resultsView, trialPane, preparedView} from "../src/hpc_forest/webapp/static/views.mjs";
import {modelFields,effortSelection,requiresDsh} from "../src/hpc_forest/webapp/static/models.mjs";
import {searchControls,searchFormValues,searchSummary} from "../src/hpc_forest/webapp/static/search.mjs";
import {historyPage} from "../src/hpc_forest/webapp/static/history.mjs";
import {timeComparison,trialOutcomes,outcomeChart} from "../src/hpc_forest/webapp/static/result-charts.mjs";

test("Source and user text cannot become executable markup",()=>{
  assert.equal(escapeHTML('<script x="a">&'),"&lt;script x=&quot;a&quot;&gt;&amp;");
  const html=trialPane({id:"a",state:"valid",files:["src/main.cpp"]},
    {path:"src/main.cpp",content:'<script>alert("bad")</script>'},"code");
  assert(!html.includes("<script>"));
  assert(html.includes("&lt;script&gt;"));
});

test("Missing or invalid measurements never become a speedup",()=>{
  for(const value of [null,undefined,NaN,Infinity,false,"1.2"]) {
    assert.equal(seconds(value),"—"); assert.equal(speedup(value),"—"); assert(!finite(value));
  }
  assert.equal(seconds(0),"0 µs");
  assert.equal(speedup(2),"2 ×");
});

test("Tree edges follow search parents, not delegation parents",()=>{
  const nodes=[{id:"a",trial_id:"qa",parent:null,delegation_parent:"R/T1"},
    {id:"b",trial_id:"qb",parent:"qa"},{id:"c",trial_id:"qc",parent:"outside"}];
  const layout=layoutTree(nodes);
  assert.equal(layout.points[1].parentId,"a");
  assert(layout.points[1].y>layout.points[0].y);
  assert(layout.points[2].missingParent);
  assert.equal(layout.points[2].parentId,null);
  const noAliases=layoutTree([{id:"a"},{id:"b"}]);
  assert(noAliases.points.every(n=>n.parentId===null));
});

test("Malformed cycles terminate, and empty trees invent no trials",()=>{
  const cycle=layoutTree([{id:"a",parent:"b"},{id:"b",parent:"a"}]);
  assert(cycle.warnings.includes("cycle"));
  assert(!forestMarkup({trees:[]}).includes("data-node"));
  assert(!forestMarkup({trees:[{id:"T1",subject:"test",nodes:[],correct_count:0}]}).includes("data-node"));
});

test("Dense tree levels reserve nonoverlapping labels, including long timings",()=>{
  const nodes=Array.from({length:30},(_,i)=>({id:"n"+i,parent:i<10?null:"n"+(i%10),
    seconds:[.004131,.000001,1234567.891,null][i%4]}));
  const layout=layoutTree(nodes);
  for(const point of layout.points) {
    assert(point.x-point.labelWidth/2>=0);
    assert(point.x+point.labelWidth/2<=layout.width);
    assert(point.y+41<=layout.height);
    for(const other of layout.points) {
      if(point.y===other.y&&point.x<other.x)
        assert(point.x+point.labelWidth/2<other.x-other.labelWidth/2);
    }
  }
  const html=forestMarkup({trees:[{id:"T",subject:"dense",nodes,correct_count:0}]});
  assert(html.includes("min-width:"+layout.width+"px"));
});

test("History pages cover every match exactly once and clamp stale page numbers",()=>{
  const records=Array.from({length:53},(_,i)=>({id:String(i),name:"Projet "+i,
    state:i%2?"confirmed":"no_gain"}));
  const pages=Array.from({length:6},(_,i)=>historyPage(records,"","",i+1).rows);
  assert.deepEqual(pages.flat().map(r=>r.id),records.map(r=>r.id));
  const last=historyPage(records,"","",99);
  assert.equal(last.page,6); assert.equal(last.start,51); assert.equal(last.end,53);
  const filtered=historyPage(records,"confirmed","  PROJET 1  ",1);
  assert.deepEqual(filtered.rows.map(r=>r.id),["1","11","13","15","17","19"]);
  assert.equal(filtered.total,6);
  assert.equal(historyPage(records,"confirmed","missing",10).start,0);
  assert.equal(historyPage(records,"","",NaN).page,1);
  assert.equal(historyPage(records,"","",1,25).rows.length,25);
  assert.equal(historyPage(records,"","",1,50).rows.length,50);
});

test("Comparison charts require confirmed finite measurements and expose slowdowns",()=>{
  const confirmed={best_confirmed:{},reference_seconds:.02,seconds:.01};
  const html=timeComparison(confirmed);
  assert(html.includes("50 % de temps en moins"));
  assert(html.includes('width:50%'));
  assert(timeComparison({...confirmed,seconds:.03}).includes("50 % de temps en plus"));
  assert(timeComparison({...confirmed,seconds:.02}).includes("Durée identique"));
  assert(timeComparison({...confirmed,best_confirmed:{is_baseline:true}}).includes("Code initial conservé"));
  for(const invalid of [{...confirmed,best_confirmed:null},{...confirmed,seconds:Infinity},
    {...confirmed,reference_seconds:0},{...confirmed,seconds:null}]) {
    assert(!timeComparison(invalid).includes('class="comparison-bar '));
  }
});

test("Trial charts keep absent verdicts separate and disclose truncated evidence",()=>{
  const campaign={trial_count:7,trees:[{nodes:[
    {id:"a",correct:true},{id:"b",correct:false},{id:"c",correct:null},
    {id:"d",state:"infrastructure_error"}]}],integrations:[{id:"a",correct:true}]};
  const {counts,total,recorded}=trialOutcomes(campaign);
  assert.deepEqual(counts.map(c=>c.count),[1,1,2]);
  assert.equal(total,4); assert.equal(recorded,7);
  assert(outcomeChart(campaign).includes("Aperçu : 4 essais sur 7"));
  assert(!outcomeChart({trees:[]}).includes("<circle"));
});

test("Campaign view distinguishes no analyst evidence and no final gain",()=>{
  const campaign={id:"a",name:"case",state:"unconfirmed",trial_count:0,trees:[],integrations:[],
    analyses:[],decisions:[],downloads:{code:false,report:false,csv:true}};
  assert(missionView(campaign).includes("Aucun bilan d’analyste actif"));
  const html=resultsView(campaign);
  assert(html.includes("Aucun résultat final confirmé"));
  assert(!html.includes("/download/code"));
  assert(!html.includes("Gain confirmé par"));
});

test("Project preparation never links to a running campaign",()=>{
  assert.equal(routeFor({id:"one",kind:"project"}),"#/prepare/one");
  assert.equal(routeFor({id:"two",kind:"prepared"}),"#/mission/prepared/two");
  assert.equal(routeFor({id:"three",kind:"campaign"}),"#/mission/campaign/three");
});

test("Mixing is explicit and preserves primary model effort",()=>{
  const base={model:"gpt-6-luna",reasoning_effort:"max",search_policy:"ab-mcts-a/beta"};
  assert.deepEqual(searchFormValues(base).generator_pool,[]);
  const mixed=searchFormValues({...base,mix_generators:"on","generator_gpt-6.1-sol":"on",
    "generator_effort_gpt-6.1-sol":"high",diversity_archive:"on"});
  assert.deepEqual(mixed.generator_pool,[{model:"gpt-6-luna",reasoning_effort:"max"},
    {model:"gpt-6.1-sol",reasoning_effort:"high"}]);
  assert.deepEqual(mixed.search,{algorithm:"ab-mcts-a",distribution:"beta"});
  assert.equal(mixed.evolution.enabled,true);
  assert(!("mix_generators" in mixed));
  assert.throws(()=>searchFormValues({...base,mix_generators:"on"}),/autre modèle/);
});

test("Optional sampler stays disabled without remote prerequisites and diagnostics escape data",()=>{
  const controls=searchControls({model:"gpt-6-luna",target:"cpu"},{});
  assert(controls.includes('value="ab-mcts-m" disabled'));
  assert(!controls.includes('name="mix_generators" checked'));
  const html=searchSummary({search_diagnostics:{policy:"<script>",trees:[],models:[
    {model:"<img onerror=alert(1)>",admitted:2,correct:1,unscored:1,best_seconds:0.2}]}});
  assert(!html.includes("<script>")&&!html.includes("<img"));
  assert(html.includes("&lt;script&gt;"));
});

test("Retired TabPFN has no controls; historical evidence remains readable",()=>{
  const base={model:"gpt-6-luna",reasoning_effort:"max",target:"cpu"};
  const configured=searchFormValues(base);
  assert(!Object.hasOwn(configured,"advisor"));
  assert.equal(configured.model,"gpt-6-luna");
  assert.equal(configured.reasoning_effort,"max");
  assert.deepEqual(configured.search,{algorithm:"ab-mcts-a",distribution:"gaussian"});
  assert(!searchControls(base,{}).includes('name="tabpfn_advisor"'));
  const html=searchControls({...base,advisor:{enabled:true}},{connection:{advisor_targets:["cpu"]}});
  assert(!html.includes('name="tabpfn_advisor"'));
  const result=searchSummary({search_diagnostics:{policy:"ab-mcts-a",trees:[],models:[]},
    advisor:{enabled:true,scope:"treequest_parent_proposals",calls:2,reorders:1,seconds:1.2,last_status:"<script>"}});
  assert(result.includes("2 appels")&&result.includes("1 choix de parent modifiés"));
  assert(!result.includes("<script>"));
  assert(searchSummary({search_diagnostics:{policy:"ab-mcts-a",trees:[],models:[]},
    advisor:{enabled:true,calls:0}}).includes("Aucun avis émis"));
});

const deepseek="dsh-deepseek-v4.1-flash-1017-1m";
const newModels=[
  {id:"gpt-6.1-terra",label:"GPT-6.1 Terra",efforts:["low","high","max","ultra"],provider:"openai",default_effort:"max"},
  {id:deepseek,label:"DeepSeek · ROMEO",efforts:["none","low","high","max"],provider:"dsh-romeo",default_effort:"max"}
];
test("Model controls use provider-specific efforts and preserve compatible selections",()=>{
  assert.equal(effortSelection(deepseek,"ultra",newModels).value,"max");
  assert.equal(effortSelection(deepseek,"none",newModels).value,"none");
  assert.equal(effortSelection("gpt-6.1-terra","high",newModels).value,"high");
  const html=modelFields({model:deepseek,reasoning_effort:"none"},{models:newModels});
  assert(html.includes('optgroup label="ROMEO · dsh-romeo"'));
  assert(html.includes('value="none" selected'));
  assert(!html.includes('value="ultra"'));
  assert(html.includes("dsh_romeo.base_url"));
});
test("New models participate in the generator pool without a hardcoded list",()=>{
  const data=searchFormValues({model:deepseek,reasoning_effort:"none",mix_generators:"on",
    "generator_gpt-6.1-terra":"on","generator_effort_gpt-6.1-terra":"ultra"});
  assert.deepEqual(data.generator_pool,[{model:deepseek,reasoning_effort:"none"},
    {model:"gpt-6.1-terra",reasoning_effort:"ultra"}]);
  assert(!("generator_gpt-6.1-terra" in data));
  assert(requiresDsh(data,newModels));
  assert(requiresDsh({...data,model:"gpt-6.1-terra"},newModels));
});
test("Prepared DeepSeek mission requires the gateway configuration before launch",()=>{
  const contract={model:deepseek,reasoning_effort:"high",generator_pool:[]};
  const mission={id:"one",name:"Fixture",project_id:"project",target:"cpu",contract:{...contract,contract}};
  const info={models:newModels,submission_enabled:true,connection:{targets:["cpu"]}};
  assert(preparedView(mission,info).includes('data-action="launch" disabled'));
  assert(preparedView(mission,info).includes("Configurez la connexion dsh-romeo"));
  info.connection.dsh_romeo_configured=true;
  assert(!preparedView(mission,info).includes('data-action="launch" disabled'));
});
