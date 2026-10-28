"""Freeze decision/data contracts so an engine upgrade cannot silently alter a run."""
from .active_contract import VERSION as ACTIVE_VERSION
from .active_contract import enabled
from .compatibility import require_current
from .core import InfrastructureError
from .evolution_archive import VERSION as EVOLUTION_VERSION
from .evolution_archive import settings as evolution_settings


def contracts(config):
    return {**({"active": ACTIVE_VERSION} if enabled(config) else {}),
            **({"evolution": EVOLUTION_VERSION} if evolution_settings(config)["enabled"] else {})}


def verify(db, config):
    require_current(config)
    expected = contracts(config)
    recorded = db.get("control_contracts", {})
    if any(recorded.get(k) != v for k, v in expected.items()):
        raise InfrastructureError("Forest control/data contract changed; start a new campaign with fresh memory. "
                                  "Existing results remain readable with their recorded evidence.")
