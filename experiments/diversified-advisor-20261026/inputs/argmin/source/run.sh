#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_PYTHON:-python3}" "${FOREST_REFERENCE_SUITE:?}/cpu_driver.py" argmin ./build/solution 4093 1204 1 bench 1
