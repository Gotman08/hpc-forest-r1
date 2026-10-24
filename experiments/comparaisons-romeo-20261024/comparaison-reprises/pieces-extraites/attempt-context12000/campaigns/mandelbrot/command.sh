root=/scratch_p/nimarano/forest-reference-rerun-mandelbrot-37b7e33da63b4c89bd6a8179fc856cf6
test ! -e "$root"
echo 'b6553256aeafa60ad83181b07e2353329e51f04aee62bedc4a1b7bf7464f5a3c  /scratch_p/nimarano/forest-reference-rerun-mandelbrot-37b7e33da63b4c89bd6a8179fc856cf6.tar.gz' | sha256sum -c -
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
