import test from "node:test";
import assert from "node:assert/strict";
import {validationControls,validationFormValues,validationSummary} from "../src/hpc_forest/webapp/static/validation.mjs";
import {remoteMissionView} from "../src/hpc_forest/webapp/static/views.mjs";

test("Prepared missions show requirements without claiming observed execution",()=>{
  const html=remoteMissionView({name:"A",state:"prepared_custom",execution_validation:{nodes:1,
    sockets_per_node:2,cpus_per_task:192,required_threads:32,parallelism:"gnu_openmp_required",
    omp_proc_bind:"close",omp_places:"cores",omp_wait_policy:"active"}},null);
  assert.match(html,/192 CPU réservés/);
  assert.match(html,/32 requis/);
  assert.match(html,/preuve en attente/);
  assert.doesNotMatch(html,/Parallélisme observé/);
});

test("Old campaigns never acquire a validation badge from available resources",()=>{
  const html=validationSummary({});
  assert.match(html,/Parallélisme non vérifié/);
  assert.doesNotMatch(html,/Parallélisme observé/);
});
test("Form values preserve the distinction between reserved CPUs and required workers",()=>{
  const result=validationFormValues({target:"cpu",validation_enabled:"yes",validation_nodes:"1",
    validation_cpus_per_task:"192",validation_required_threads:"32",validation_sockets_per_node:"2",
    validation_parallelism:"gnu_openmp_required"});
  assert.equal(result.target,"cpu");
  assert.equal(result.execution_validation.cpus_per_task,192);
  assert.equal(result.execution_validation.required_threads,32);
  assert.equal(result.execution_validation.sockets_per_node,2);
  assert.equal(Object.keys(result).some(k=>k.startsWith("validation_")),false);
  assert.equal(validationFormValues({validation_enabled:"no"}).execution_validation,null);
});
test("Configuration and evidence remain escaped and distinct",()=>{
  const html=validationSummary({required:{nodes:1,sockets_per_node:2,cpus_per_task:192,
    required_threads:192,parallelism:"gnu_openmp_required",omp_proc_bind:'<img src=x>',omp_places:"cores",omp_wait_policy:"active"},
    allocation:{status:"passed",allowed_cpus:Array(192),physical_cores:192,sockets:[0,1]}});
  assert.match(html,/192 CPU réservés/);
  assert.match(html,/preuve en attente/);
  assert.doesNotMatch(html,/<img/);
  assert.match(html,/&lt;img/);
});
test("A baseline exemption is not reported as proof of parallel execution",()=>{
  const html=validationSummary({winner:{parallelism:{status:"reference_only"}}});
  assert.match(html,/Original de référence/);
  assert.doesNotMatch(html,/Parallélisme observé/);
});
test("Validation controls are configurable and opt in for old contracts",()=>{
  assert.match(validationControls({}),/data-validation-fields disabled/);
  const html=validationControls({execution_validation:{cpus_per_task:64,required_threads:32}});
  assert.match(html,/name="validation_cpus_per_task" value="64"/);
  assert.match(html,/name="validation_required_threads" value="32"/);
});
