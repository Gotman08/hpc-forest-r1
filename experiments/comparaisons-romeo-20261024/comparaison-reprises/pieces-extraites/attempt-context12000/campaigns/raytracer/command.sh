root=/scratch_p/nimarano/forest-reference-rerun-raytracer-0909a312a10a496c8bc0653ba0e449ee
test ! -e "$root"
echo '1e442b268c26871cf4d6931666081b1a5ae4af749a8c7f26eeec6b439b288a6b  /scratch_p/nimarano/forest-reference-rerun-raytracer-0909a312a10a496c8bc0653ba0e449ee.tar.gz' | sha256sum -c -
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
