root=/scratch_p/nimarano/forest-reference-rerun-volume-49a2eb4289c64af3ba3c8edb21bb9f08
test ! -e "$root"
echo '70f6186d3ccc175e71fb82abaf66b69a729c514fe14404c356a2ecbcdac73f51  /scratch_p/nimarano/forest-reference-rerun-volume-49a2eb4289c64af3ba3c8edb21bb9f08.tar.gz' | sha256sum -c -
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
