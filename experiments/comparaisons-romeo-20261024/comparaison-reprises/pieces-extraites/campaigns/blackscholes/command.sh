root=/scratch_p/nimarano/forest-reference-rerun-blackscholes-bd9d055509ce4800848ea3dbbb81a1f9
test ! -e "$root"
echo '2e09fe24b7abd3e3465bf38e565e7065d445e468634b3eb023671d3b7f5425be  /scratch_p/nimarano/forest-reference-rerun-blackscholes-bd9d055509ce4800848ea3dbbb81a1f9.tar.gz' | sha256sum -c -
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
