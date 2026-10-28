"""Bounded structured reads of native SQLite timelines, without arbitrary SQL."""
from __future__ import annotations

import json
import math
import sqlite3
import time


def sqlite_page(path, table=None, columns=None, equals=None, order_by=None, descending=False,
                offset=0, limit=40):
    if (type(offset) is not int or not 0 <= offset <= 1000000 or type(limit) is not int
            or not 1 <= limit <= 100 or type(descending) is not bool):
        raise ValueError("Invalid table pagination")
    with path.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ValueError("This artifact is not a SQLite timeline")
    # An immutable report, never a live campaign DB. No ATTACH, extensions, SQL
    # expressions, views, joins or arbitrary predicates are exposed to models.
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    deadline = time.monotonic() + 2
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    def quote(name):
        return '"' + name.replace('"', '""') + '"'
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        tables = [row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND upper(sql) NOT LIKE 'CREATE VIRTUAL%' ORDER BY name")]
        if table is None:
            return {"tables": tables[offset:offset + limit],
                    "next_offset": offset + limit if offset + limit < len(tables) else None}
        if table not in tables:
            raise ValueError("Unknown native timeline table")
        metadata = [dict(row) for row in connection.execute("PRAGMA table_info(" + quote(table) + ")")]
        known = {c["name"] for c in metadata}
        selected = columns if columns is not None else [c["name"] for c in metadata][:16]
        if (not isinstance(selected, list) or not 1 <= len(selected) <= 16
                or any(not isinstance(c, str) or c not in known for c in selected)
                or order_by is not None and (not isinstance(order_by, str) or order_by not in known)):
            raise ValueError("Unknown timeline columns")
        equals = {} if equals is None else equals
        if (not isinstance(equals, dict) or len(equals) > 8 or any(k not in known for k in equals)
                or any(not (v is None or type(v) in {str, int, float})
                       or isinstance(v, str) and len(v) > 512
                       or type(v) is int and not -(2**63) <= v < 2**63
                       or isinstance(v, float) and not math.isfinite(v) for v in equals.values())):
            raise ValueError("Invalid equality filters")
        query = "SELECT " + ",".join(quote(c) for c in selected) + " FROM " + quote(table)
        if equals:
            query += " WHERE " + " AND ".join(quote(k) + " IS ?" for k in equals)
        if order_by:
            query += " ORDER BY " + quote(order_by) + (" DESC" if descending else " ASC")
        query += " LIMIT ? OFFSET ?"
        rows = connection.execute(query, [*equals.values(), limit + 1, offset]).fetchall()
        output, truncated, size = [], False, 0
        for row in rows[:limit]:
            item = {}
            for name, value in dict(row).items():
                if isinstance(value, bytes):
                    item[name] = {"binary_bytes": len(value), "omitted": True}
                elif isinstance(value, str) and len(value) > 1000:
                    item[name] = {"text": value[:1000], "truncated": True}
                    truncated = True
                else:
                    item[name] = value
            item_size = len(json.dumps(item, ensure_ascii=False))
            if size + item_size > 24000:
                break
            output.append(item)
            size += item_size
        return {"table": table, "columns": metadata, "rows": output, "truncated_cells": truncated,
                "next_offset": offset + len(output) if len(rows) > len(output) else None,
                "page_truncated": len(output) < min(len(rows), limit),
                "units": "Native table fields; inspect the producer schema, do not assume a universal unit",
                "ordering": order_by or "native table order; specify a unique ordering column for stable pages"}
    except sqlite3.Error as exc:
        raise ValueError("Native timeline read failed or exceeded its query budget: " + str(exc)) from exc
    finally:
        connection.close()
