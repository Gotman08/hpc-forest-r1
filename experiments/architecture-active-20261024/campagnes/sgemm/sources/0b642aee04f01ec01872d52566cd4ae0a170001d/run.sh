#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_REFERENCE_SUITE:?}/gpu_driver" 0 "${FOREST_REFERENCE_SUITE:?}/references.so" ./build/solution 1 4096 271 20 5 1
