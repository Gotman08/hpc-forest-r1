"""Entry point that selects an explicitly authorized native model once."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .native_matrix import install_identity


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dependency-receipt", type=Path, required=True)
    args, _ = parser.parse_known_args()
    identity = json.loads(args.dependency_receipt.read_text(encoding="utf8"))
    install_identity(identity["model"], identity["effort"], args.dependency_receipt)
    from .codex_worker import main as run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
