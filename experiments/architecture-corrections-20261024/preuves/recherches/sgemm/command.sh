FOREST_CUDA_PREFIX=$(spack location -i /uxlsycgnldislqswr4gcj6hlc6u2pdxp)
test -f "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12"
export LD_LIBRARY_PATH="$FOREST_CUDA_PREFIX/lib64:${LD_LIBRARY_PATH:-}"
root=/scratch_p/nimarano/forest-active-corrected-v2-sgemm-410747676bbb4389b9f1ffc82f0453ca
test ! -e "$root"
echo 'a5a5a38c316001d309a62628c7d58d2974b3c615362d7da367817b091636e077  /scratch_p/nimarano/forest-active-corrected-v2-sgemm-410747676bbb4389b9f1ffc82f0453ca.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-gpu-suite-20261023/gpu_driver
mkdir -p "$root/cache"
echo '{"architecture":"aarch64","retained_protected_suite":true}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
nvidia-smi -q > "$root/allocation-gpu.txt"
sha256sum "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12" > "$root/allocation-cublas.txt"
cd "$root"
set +e
/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt allocation-gpu.txt allocation-cublas.txt engine-exit-code.txt
exit "$rc"
