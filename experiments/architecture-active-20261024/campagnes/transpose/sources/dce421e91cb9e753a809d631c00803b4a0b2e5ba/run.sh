#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_REFERENCE_SUITE:?}/gpu_driver" 1 "${FOREST_REFERENCE_SUITE:?}/references.so" ./build/solution 1 1024 271 100 10 1
