import test from "node:test";
import assert from "node:assert/strict";
import {escapeHTML, seconds, speedup, finite, routeFor} from "../src/hpc_forest/webapp/static/helpers.mjs";
import {layoutTree, forestMarkup} from "../src/hpc_forest/webapp/static/graph.mjs";
import {missionView, resultsView, trialPane} from "../src/hpc_forest/webapp/static/views.mjs";
import {searchControls,searchFormValues,searchSummary} from "../src/hpc_forest/webapp/static/search.mjs";

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

test("TabPFN is one optional adviser, preserving Luna and the existing policy",()=>{
  const base={model:"gpt-6-luna",reasoning_effort:"max",target:"cpu"};
  assert.deepEqual(searchFormValues(base).advisor,{enabled:false});
  const configured=searchFormValues({...base,tabpfn_advisor:"on"});
  assert.deepEqual(configured.advisor,{enabled:true});
  assert.equal(configured.model,"gpt-6-luna");
  assert.equal(configured.reasoning_effort,"max");
  assert.deepEqual(configured.search,{algorithm:"ab-mcts-a",distribution:"gaussian"});
  assert(searchControls(base,{}).includes('name="tabpfn_advisor" disabled'));
  const html=searchControls({...base,advisor:{enabled:true}},{connection:{advisor_targets:["cpu"]}});
  assert(html.includes('name="tabpfn_advisor" checked >'));
  const result=searchSummary({search_diagnostics:{policy:"ab-mcts-a",trees:[],models:[]},
    advisor:{enabled:true,scope:"treequest_parent_proposals",calls:2,reorders:1,seconds:1.2,last_status:"<script>"}});
  assert(result.includes("2 appels")&&result.includes("1 choix de parent modifiés"));
  assert(!result.includes("<script>"));
  assert(searchSummary({search_diagnostics:{policy:"ab-mcts-a",trees:[],models:[]},
    advisor:{enabled:true,calls:0}}).includes("Aucun avis émis"));
});
