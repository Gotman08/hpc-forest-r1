"""Read confirmed CPU winners while the remaining Base64 campaign continues."""
from pathlib import Path
import json
import subprocess
import tarfile

R = Path(__file__).resolve().parent
OLD = R.parent/'reference-study'
D = R/'source-review/previews'
for key in ['blackscholes', 'gemm_cpu', 'mandelbrot', 'stencil3d', 'utf8']:
    exports = []
    for period, parent in [('old', OLD), ('new', R)]:
        root = parent/'campaigns'/key
        if not (root/'results').exists():
            with tarfile.open(root/'results.tar.gz') as archive:
                archive.extractall(root/'results', filter='data')
        result = next(root.glob('results/results-*/results.json'))
        d = json.loads(result.read_text(encoding='utf8'))
        winner = d['best_confirmed']['commit']
        target = D/key/period/'candidate.cpp'
        target.parent.mkdir(parents=True, exist_ok=True)
        repo = result.parent/('reference-'+key)/'repo'
        target.write_bytes(subprocess.check_output(['git','-C',str(repo),'show',winner+':src/candidate.cpp']))
        exports.append(target)
    p = subprocess.run(['git','-c','core.autocrlf=false','diff','--no-index','--',*map(str,exports)],capture_output=True)
    assert p.returncode in [0,1]
    (R/'source-review'/(key+'.diff')).write_bytes(p.stdout)
    print(key, 'identical' if p.returncode == 0 else 'different', len(p.stdout), flush=True)
