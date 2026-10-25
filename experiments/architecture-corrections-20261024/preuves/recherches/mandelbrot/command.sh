root=/scratch_p/nimarano/forest-active-corrected-v2-mandelbrot-network-retry3-e816a499f69d417e81c47a972fbe423e
test ! -e "$root"
echo '231f25974f0896ba0bccbd2d9a6fd169c126b72ee81bd448bd76cd3311edc125  /scratch_p/nimarano/forest-active-corrected-v2-mandelbrot-network-retry3-e816a499f69d417e81c47a972fbe423e.tar.gz' | sha256sum -c -
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
