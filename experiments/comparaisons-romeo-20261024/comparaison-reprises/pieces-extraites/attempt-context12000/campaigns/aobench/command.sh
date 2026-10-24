root=/scratch_p/nimarano/forest-reference-rerun-aobench-8d5fd594b21d42b0bea03575969b6251
test ! -e "$root"
echo 'd9905f378ec89fca463e835c71e56916db118c4249d19c0f14d85aa7104d0de0  /scratch_p/nimarano/forest-reference-rerun-aobench-8d5fd594b21d42b0bea03575969b6251.tar.gz' | sha256sum -c -
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
