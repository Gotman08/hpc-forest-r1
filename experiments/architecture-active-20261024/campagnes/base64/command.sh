root=/scratch_p/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e
test ! -e "$root"
echo 'e7262db949a861c1bcd81181cc6ec65cb81c7a2bc5e28bafd5eccca67f5119c9  /scratch_p/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e.tar.gz' | sha256sum -c -
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
