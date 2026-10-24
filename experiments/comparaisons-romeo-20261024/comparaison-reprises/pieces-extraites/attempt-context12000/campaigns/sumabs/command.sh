root=/scratch_p/nimarano/forest-reference-rerun-sumabs-c9268d504e21474db6b4a48b72a73a24
test ! -e "$root"
echo 'd0fd557650c081d5a7c71341260ba982f36e1825d3201ed28d8419037821e1f1  /scratch_p/nimarano/forest-reference-rerun-sumabs-c9268d504e21474db6b4a48b72a73a24.tar.gz' | sha256sum -c -
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
