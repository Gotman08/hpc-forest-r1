"""One explicit model identity for the current Forest experiment series."""
from .core import InfrastructureError

MODEL = "gpt-6-luna"
EFFORT = "max"


def require_identity(value: dict) -> None:
    if value.get("model") != MODEL or value.get("reasoning_effort") != EFFORT:
        raise InfrastructureError("Forest requires exactly GPT-6 Luna Max; start a new campaign")
