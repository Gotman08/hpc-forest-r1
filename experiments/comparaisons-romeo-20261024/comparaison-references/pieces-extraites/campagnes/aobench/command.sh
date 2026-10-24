root=/scratch_p/nimarano/forest-reference-run-aobench-2f3347c7faed418cb33de843a52eff90
test ! -e "$root"
echo '03ac90185c35550f0922703c6115d91266c20ae2c68093f84df80d493c563aa2  /scratch_p/nimarano/forest-reference-run-aobench-2f3347c7faed418cb33de843a52eff90.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-render-20261023/render_driver
mkdir -p "$root/cache"
echo '{"reference_phase_job":"781186","architecture":"x86_64"}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt engine-exit-code.txt
exit "$rc"
