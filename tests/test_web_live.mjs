import test from "node:test";
import assert from "node:assert/strict";
import {createMissionPoller} from "../src/hpc_forest/webapp/static/mission-poll.mjs";

const deferred=()=>{
  let resolve,reject;
  const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  return {promise,resolve,reject};
};
const ticket=()=>({id:"one",navigation:1,selection:1,route:"#/mission/run/one"});

test("Live refresh leaves the displayed tree intact until both reads finish and never overlaps",async()=>{
  const mission=deferred(),campaign=deferred(),requests=[],shown=[];
  const poll=createMissionPoller({current:ticket,load:path=>{
    requests.push(path); return requests.length===1?mission.promise:campaign.promise;
  },display:(...args)=>shown.push(args),failed:assert.fail});
  const running=poll();
  await poll();
  assert.deepEqual(requests,["/missions/one"]);
  assert.deepEqual(shown,[]);
  mission.resolve({id:"one",campaign_id:"tree"});
  await Promise.resolve();
  assert.deepEqual(requests,["/missions/one","/campaigns/tree"]);
  assert.deepEqual(shown,[]);
  campaign.resolve({id:"tree",trial_count:27});
  await running;
  assert.deepEqual(shown,[[{id:"one",campaign_id:"tree"},{id:"tree",trial_count:27}]]);
});

test("Navigation discards an old observation before requesting its campaign",async()=>{
  const response=deferred(),requests=[],shown=[];
  let visible=ticket();
  const poll=createMissionPoller({current:()=>visible,load:path=>{
    requests.push(path); return response.promise;
  },display:value=>shown.push(value),failed:assert.fail});
  const running=poll();
  visible={...visible,navigation:2,id:"two",route:"#/mission/run/two"};
  response.resolve({id:"one",campaign_id:"old"});
  await running;
  assert.deepEqual(requests,["/missions/one"]);
  assert.deepEqual(shown,[]);
});

for(const change of [value=>({...value,selection:2}),()=>null]) {
  test("A selection or action during loading prevents replacement of the user's view",async()=>{
    const response=deferred(),shown=[];
    let visible=ticket();
    const poll=createMissionPoller({current:()=>visible,
      load:async path=>path.startsWith("/missions/")?{id:"one",campaign_id:"tree"}:response.promise,
      display:value=>shown.push(value),failed:assert.fail});
    const running=poll();
    await Promise.resolve();
    visible=change(visible);
    response.resolve({id:"tree"});
    await running;
    assert.deepEqual(shown,[]);
  });
}

test("A failed refresh retains the old view, reports once, and allows recovery",async()=>{
  let unavailable=true;
  const shown=[],errors=[];
  const poll=createMissionPoller({current:ticket,load:async()=>{
    if(unavailable) throw new Error("temporary connection failure");
    return {id:"one",campaign_id:null};
  },display:(...args)=>shown.push(args),failed:error=>errors.push(error.message)});
  await poll(); await poll();
  assert.deepEqual(shown,[]);
  assert.deepEqual(errors,["temporary connection failure"]);
  unavailable=false;
  await poll();
  assert.deepEqual(shown,[[{id:"one",campaign_id:null},null]]);
  unavailable=true;
  await poll();
  assert.equal(errors.length,2);
});

test("Inactive pages do not issue requests, and old-page failures do not appear on the new page",async()=>{
  let visible=null;
  const response=deferred(),requests=[];
  const poll=createMissionPoller({current:()=>visible,load:path=>{
    requests.push(path);return response.promise;
  },display:assert.fail,failed:assert.fail});
  await poll();
  assert.deepEqual(requests,[]);
  visible=ticket();
  const running=poll();
  visible=null;
  response.reject(new Error("old page failure"));
  await running;
});
