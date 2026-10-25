root=/scratch_p/nimarano/forest-active-corrected-v2-utf8-network-retry2-3a080761406c41a088ddcfdc1c0cccf2
test ! -e "$root"
echo '59a66a1d693e7f6b4b0bcc8b179867f98db136ad952db0b1824c7068ccc61d27  /scratch_p/nimarano/forest-active-corrected-v2-utf8-network-retry2-3a080761406c41a088ddcfdc1c0cccf2.tar.gz' | sha256sum -c -
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
