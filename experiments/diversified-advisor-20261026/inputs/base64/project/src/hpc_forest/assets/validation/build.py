import sys
from pathlib import Path

from hpc_forest.toolchain import build

if __name__ == "__main__":
    raise SystemExit(build(Path(sys.argv[1]), Path(sys.argv[2])))
