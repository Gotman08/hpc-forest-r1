#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_RENDER_SUITE:?}/render_driver" "$FOREST_RENDER_SUITE" aobench ./build/solution 512 271 4 bench
