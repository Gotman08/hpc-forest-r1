#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_RENDER_SUITE:?}/render_driver" "$FOREST_RENDER_SUITE" deferred ./build/solution 1280 271 4 bench
