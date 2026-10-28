"""Explicit local maintenance. No model calls, allocation or in-place migration."""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from .compatibility import RETIRED_SETTINGS, without_retired
from .config import config_from_data
from .core import ForestError, file_digest
from .storage.backups import backup_application, restore_application, verify_backup


def migrate_config(source: Path, destination: Path) -> dict:
    """Write a new config and receipt, keeping all old settings in the source."""
    raw = source.read_bytes()
    config = json.loads(raw) if source.suffix == ".json" else tomllib.loads(raw.decode("utf-8"))
    migrated = without_retired(config)
    config_from_data(migrated)
    receipt_path = destination.with_suffix(destination.suffix + ".migration.json")
    if destination.exists() or receipt_path.exists():
        raise FileExistsError("Migration requires new configuration and receipt paths")
    receipt = {"schema": "forest-config-migration-v1", "source": str(source.resolve()),
               "source_sha256": file_digest(source), "removed_settings": sorted(RETIRED_SETTINGS.intersection(config)),
               "new_campaign_required": True, "config": migrated}
    # Exclusive creation makes two concurrent migrations unable to overwrite.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(migrated, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump({k: v for k, v in receipt.items() if k != "config"}, stream, ensure_ascii=False, indent=2)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("backup", "restore", "migrate-config"):
        sub = commands.add_parser(command)
        sub.add_argument("source", type=Path)
        sub.add_argument("destination", type=Path)
    sub = commands.add_parser("verify-backup")
    sub.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-backup":
            result = verify_backup(args.source)
        else:
            operation = {"backup": backup_application, "restore": restore_application,
                         "migrate-config": migrate_config}[args.command]
            result = operation(args.source, args.destination)
        print(json.dumps({k: v for k, v in result.items() if k not in {"files", "config"}}, ensure_ascii=False, indent=2))
        return 0
    except (ForestError, OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
