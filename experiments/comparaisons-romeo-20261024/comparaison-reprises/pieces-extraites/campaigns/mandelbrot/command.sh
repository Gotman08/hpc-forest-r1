root=/scratch_p/nimarano/forest-reference-rerun-mandelbrot-85126462b5254bf2b01433944dcb04e9
test ! -e "$root"
echo '4a1e8b0f4d1a1dbf0e31f6ba1cd2d9e6c01f5c0d360310739b0f5ac99bd1e777  /scratch_p/nimarano/forest-reference-rerun-mandelbrot-85126462b5254bf2b01433944dcb04e9.tar.gz' | sha256sum -c -
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
