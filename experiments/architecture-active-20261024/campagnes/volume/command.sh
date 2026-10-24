root=/scratch_p/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3
test ! -e "$root"
echo 'e7f2f88f5a16ef97b2bff1b6fd3ee889f2fc0a2bb0519e3c438b649498e64b6e  /scratch_p/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3.tar.gz' | sha256sum -c -
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
