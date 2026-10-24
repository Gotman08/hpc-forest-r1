root=/scratch_p/nimarano/forest-reference-rerun-s4convd-bfc4348b9b1a48c695ec8fcbab28518e
test ! -e "$root"
echo 'b91997cd97482985600fb9bf6e3d646a88bf4fcec448a944296d73cf67fc1888  /scratch_p/nimarano/forest-reference-rerun-s4convd-bfc4348b9b1a48c695ec8fcbab28518e.tar.gz' | sha256sum -c -
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
