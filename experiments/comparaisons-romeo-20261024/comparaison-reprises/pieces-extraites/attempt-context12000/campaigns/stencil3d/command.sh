root=/scratch_p/nimarano/forest-reference-rerun-stencil3d-c19d6b446d3648c780a6232e7f7173a7
test ! -e "$root"
echo '2975823e4639b35b4c59a8d20616e828e7205832035d6ac8455ff80f678ae789  /scratch_p/nimarano/forest-reference-rerun-stencil3d-c19d6b446d3648c780a6232e7f7173a7.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-cpu-suite-20261023/cpu_driver.py
mkdir -p "$root/cache"
echo '{"reference_phase_job":"781157","architecture":"x86_64"}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt engine-exit-code.txt
exit "$rc"
