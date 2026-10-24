root=/scratch_p/nimarano/forest-reference-run-popcount-5bfdb00d1f884b97b3ae9b0d10f7f1dd
test ! -e "$root"
echo '4f5b1f3a887d990ff1cc3c9261960fc762ebc9a8fb2f79c63d486b94fa70b40f  /scratch_p/nimarano/forest-reference-run-popcount-5bfdb00d1f884b97b3ae9b0d10f7f1dd.tar.gz' | sha256sum -c -
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
