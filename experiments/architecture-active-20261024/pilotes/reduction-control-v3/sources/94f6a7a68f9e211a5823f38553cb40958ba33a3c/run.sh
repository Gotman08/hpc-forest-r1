#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_TORCH_PYTHON:?}" "${FOREST_REFERENCE_SUITE:?}/gpu_extra_driver.py" reduction ./build/solution 4194304 271 bench
