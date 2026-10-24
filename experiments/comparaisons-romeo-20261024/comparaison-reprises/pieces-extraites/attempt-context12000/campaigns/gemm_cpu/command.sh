root=/scratch_p/nimarano/forest-reference-rerun-gemm_cpu-3a96a1d1c8084342806e8c8cf296c3c6
test ! -e "$root"
echo '24af3803d17f5f4bc5d817f469bfcbbb2ee466f4d5288c3095035034897cb041  /scratch_p/nimarano/forest-reference-rerun-gemm_cpu-3a96a1d1c8084342806e8c8cf296c3c6.tar.gz' | sha256sum -c -
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
