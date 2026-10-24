#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_REFERENCE_SUITE:?}/gpu_driver" 2 "${FOREST_REFERENCE_SUITE:?}/references.so" ./build/solution 1 64 271 100 10 1
