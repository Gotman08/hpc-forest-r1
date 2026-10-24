root=/scratch_p/nimarano/forest-reference-rerun-raytracer-97cdd107086440d88f083c383815d6f6
test ! -e "$root"
echo '0b03e6c0c622e9cb02b0d7d685af0f2ecd09ca30ad9b4d0265f85c6d9055760f  /scratch_p/nimarano/forest-reference-rerun-raytracer-97cdd107086440d88f083c383815d6f6.tar.gz' | sha256sum -c -
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
