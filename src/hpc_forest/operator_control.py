"""An operator stop closes admissions, then drains and confirms admitted work."""
from __future__ import annotations

import json
import time

from .core import InfrastructureError


def stop_requested(controller) -> bool:
    db, config = controller.db, controller.config
    key = f"operator_stop:{db.get('current_epoch', 1)}"
    if db.get(key):
        return True
    if not config.get("app_protocol"):
        return False
    path = controller.root.parent / "stop-request.json"
    if not path.exists():
        return False
    try:
        if path.stat().st_size > 4096:
            raise ValueError("Oversized request")
        request = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False  # No partial upload is acted upon.
    if (request.get("schema") != "forest-operator-stop-v1"
            or config.get("problem") != "app-" + str(request.get("mission_id"))
            or request.get("session_id") != config.get("codex", {}).get("session_id")):
        raise InfrastructureError("Operator stop belongs to another mission")
    receipt = {"requested_at": request.get("requested_at"), "accepted_at": time.time(),
               "policy": "drain_then_confirm"}
    with db.connection:
        db.connection.execute("INSERT INTO metadata VALUES(?,?)", (key, json.dumps(receipt)))
        db.connection.execute("INSERT INTO events(kind,payload,created) VALUES(?,?,?)",
                              ("operator_stop_accepted", json.dumps(receipt), time.time()))
    return True
