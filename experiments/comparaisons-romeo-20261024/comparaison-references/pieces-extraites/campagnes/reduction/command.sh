root=/scratch_p/nimarano/forest-reference-run-reduction-a987e665bcbb4df2b15f8e8ddb5affa0
test ! -e "$root"
echo '4efa09c41cc137a7a41bf7e452473eac53d8da6627d453b85153adcbc04dc390  /scratch_p/nimarano/forest-reference-run-reduction-a987e665bcbb4df2b15f8e8ddb5affa0.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-gpu-extra-20261023/gpu_extra_driver.py
mkdir -p "$root/cache"
echo '{"reference_phase_job":"781161","architecture":"aarch64"}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
nvidia-smi -q > "$root/allocation-gpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt allocation-gpu.txt engine-exit-code.txt
exit "$rc"
