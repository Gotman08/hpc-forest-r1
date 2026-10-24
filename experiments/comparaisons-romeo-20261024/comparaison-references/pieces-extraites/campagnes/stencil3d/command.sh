root=/scratch_p/nimarano/forest-reference-run-stencil3d-71716815d6684de2856c5861cd66df7f
test ! -e "$root"
echo '5770d8df39920b74953cd2a66e26a0319bdb3eb5cd19c3de621d4966794de752  /scratch_p/nimarano/forest-reference-run-stencil3d-71716815d6684de2856c5861cd66df7f.tar.gz' | sha256sum -c -
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
