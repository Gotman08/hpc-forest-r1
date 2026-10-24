#!/usr/bin/env bash
set -euo pipefail
exec "${FOREST_RENDER_SUITE:?}/render_driver" "$FOREST_RENDER_SUITE" raytracer ./build/solution 900 271 4 bench
