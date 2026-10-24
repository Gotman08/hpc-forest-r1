root=/scratch_p/nimarano/forest-reference-rerun-deferred-831795d6e19f429d8c1e2e3eb9e8ac8c
test ! -e "$root"
echo '11d7e0f0be8c91932cc59da69d3379d4bc80ee17846857a79c777da7e41b30c8  /scratch_p/nimarano/forest-reference-rerun-deferred-831795d6e19f429d8c1e2e3eb9e8ac8c.tar.gz' | sha256sum -c -
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
