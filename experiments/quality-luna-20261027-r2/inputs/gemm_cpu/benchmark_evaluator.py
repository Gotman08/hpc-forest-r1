import json, math
from pathlib import Path
from hpc_forest.evaluator import Evaluator
from hpc_forest.core import InfrastructureError,file_digest

class BenchmarkEvaluator(Evaluator):
    def _sample(self,item,index):
        outcome,variables,logs=item
        binary=Path(variables['binary'])
        if file_digest(binary)!=outcome.binary_sha256:raise InfrastructureError('Candidate changed after build')
        r=self._run('benchmark',variables,logs/f'sample-{index}.log')
        outcome.logs.append(r.log)
        if file_digest(binary)!=outcome.binary_sha256:raise InfrastructureError('Candidate changed during timing')
        if r.returncode==70:raise InfrastructureError('Benchmark infrastructure failed')
        if r.returncode or r.timed_out:
            outcome.status,outcome.correct,outcome.score='runtime_failed',False,0.0
            outcome.times.clear();return
        try:
            d=json.loads(Path(r.log).read_text())
            v=d['seconds']
            assert d['correct'] is True and d['metric']=='protected_kernel_seconds'
            assert isinstance(v,(int,float)) and math.isfinite(v) and v>0
            assert math.isclose(v,math.exp(sum(math.log(x['seconds']) for x in d['details'])/len(d['details'])),rel_tol=1e-10)
        except Exception as e:raise InfrastructureError('Malformed protected metric') from e
        outcome.times.append(v)
