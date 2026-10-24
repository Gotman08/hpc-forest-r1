root=/scratch_p/nimarano/forest-reference-run-raytracer-7ca5c3544fff4475b27aef10e3f8c6a6
test ! -e "$root"
echo '01282db9aa9e4bce93d75635ce677dcb2d4d1f14ac2cff5c2182666ecb4eb090  /scratch_p/nimarano/forest-reference-run-raytracer-7ca5c3544fff4475b27aef10e3f8c6a6.tar.gz' | sha256sum -c -
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
