root=/scratch_p/nimarano/forest-reference-rerun-volume-6a87010d83a740aba87eac4724ba9e56
test ! -e "$root"
echo '783536558a644cfe88454ba7b2204cdf78957d6d8cc662db540f38dc8a90cba9  /scratch_p/nimarano/forest-reference-rerun-volume-6a87010d83a740aba87eac4724ba9e56.tar.gz' | sha256sum -c -
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
