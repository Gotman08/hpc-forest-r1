#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_PYTHON:-python3}" "${FOREST_REFERENCE_SUITE:?}/cpu_driver.py" base64 ./build/solution 16384 1204 1 bench 1
