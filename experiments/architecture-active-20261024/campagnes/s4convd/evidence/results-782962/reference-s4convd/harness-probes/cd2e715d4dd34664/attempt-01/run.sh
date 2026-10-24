#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_TORCH_PYTHON:?}" "${FOREST_REFERENCE_SUITE:?}/gpu_extra_driver.py" s4convd ./build/solution 16384 271 bench
