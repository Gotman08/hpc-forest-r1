root=/scratch_p/nimarano/forest-active-transpose-ef1b1be6b496410cbc59aa3cacf9f5e9
test ! -e "$root"
echo 'f97f9b3a13e568f1440ee14e6272bf18e0d1c11f8d5c08ddadac56ab705a3d90  /scratch_p/nimarano/forest-active-transpose-ef1b1be6b496410cbc59aa3cacf9f5e9.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-gpu-suite-20261023/gpu_driver
mkdir -p "$root/cache"
echo '{"architecture":"aarch64","retained_protected_suite":true}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
nvidia-smi -q > "$root/allocation-gpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt allocation-gpu.txt engine-exit-code.txt
exit "$rc"
