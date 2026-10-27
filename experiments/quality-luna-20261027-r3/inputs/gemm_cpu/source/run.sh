#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_PYTHON:-python3}" "${FOREST_REFERENCE_SUITE:?}/cpu_driver.py" gemm_cpu ./build/solution 384 1204 4 bench 1
