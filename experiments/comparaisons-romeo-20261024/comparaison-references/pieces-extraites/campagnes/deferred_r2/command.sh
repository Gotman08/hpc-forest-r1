root=/scratch_p/nimarano/forest-reference-run-deferred_r2-11b642a5459447db894e178b4a06ba70
test ! -e "$root"
echo '7ad93c8b9374d37bd6ef8bdd7eff7f1d3fced7f4eb64b75ffa4c77ea6b988a30  /scratch_p/nimarano/forest-reference-run-deferred_r2-11b642a5459447db894e178b4a06ba70.tar.gz' | sha256sum -c -
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
