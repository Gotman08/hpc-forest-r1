#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_TORCH_PYTHON:?}" "${FOREST_REFERENCE_SUITE:?}/gpu_extra_driver.py" softmax ./build/solution 4096 271 bench
