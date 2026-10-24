FOREST_CUDA_PREFIX=$(spack location -i /uxlsycgnldislqswr4gcj6hlc6u2pdxp)
test -f "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12"
export LD_LIBRARY_PATH="$FOREST_CUDA_PREFIX/lib64:${LD_LIBRARY_PATH:-}"
root=/scratch_p/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f
test ! -e "$root"
echo 'cffaafb79056d60c0291d074aac7d015e726794cf36f7d3799b661c884f0141e  /scratch_p/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f.tar.gz' | sha256sum -c -
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
