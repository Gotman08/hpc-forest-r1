root=/scratch_p/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0
test ! -e "$root"
echo '3459187aae99c34eabced3a5cf94ee70b3c4907f384be22e9fd81d3b27b9023a  /scratch_p/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0.tar.gz' | sha256sum -c -
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
