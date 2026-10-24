#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_TORCH_PYTHON:?}" "${FOREST_REFERENCE_SUITE:?}/gpu_extra_driver.py" sumabs ./build/solution 268435456 271 bench
