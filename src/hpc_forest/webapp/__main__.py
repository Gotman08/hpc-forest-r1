"""Run the personal application on loopback and resume its authorized missions."""
from __future__ import annotations

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Application personnelle Forest")
    parser.add_argument("--data", type=Path, default=Path.home() / ".hpc-forest" / "application")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--campaign", type=Path, action="append", default=[],
                        help="Register an existing local Forest campaign for read-only consultation")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")
    try:
        import uvicorn

        from .api import create_app
    except ImportError as exc:
        parser.error(f"Install the web extra first: pip install -e '.[web]' ({exc})")
    app = create_app(args.data, args.campaign)
    print(f"Forest application: http://127.0.0.1:{args.port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
