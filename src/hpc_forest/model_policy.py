"""A frozen control identity and an explicitly authorized pool of generators."""
from .core import InfrastructureError

MODEL = "gpt-6-luna"
EFFORT = "max"
MODELS = {"gpt-6-luna": "GPT-6 Luna", "gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6-astra": "GPT-6 Astra"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")


def efforts(model: str) -> tuple[str, ...]:
    # Native Codex catalogue verified on ROMEO; Ultra is absent for Luna.
    return EFFORTS + (("ultra",) if model in {"gpt-6.1-sol", "gpt-6-astra"} else ())


def catalog() -> list[dict]:
    return [{"id": key, "label": label, "efforts": list(efforts(key))} for key, label in MODELS.items()]


def require_identity(value: dict) -> None:
    if (not isinstance(value, dict) or not isinstance(value.get("model"), str) or value.get("model") not in MODELS
            or value.get("reasoning_effort") not in efforts(value.get("model"))):
        raise InfrastructureError("Unsupported Forest model or reasoning effort; start a new campaign")


def identity(value: dict) -> dict:
    require_identity(value)
    return {k: value[k] for k in ("model", "reasoning_effort")}


def generator_pool(settings: dict) -> list[dict]:
    """Empty/absent means exactly the selected model; never enable mixing implicitly."""
    primary = identity(settings)
    pool = settings.get("generator_pool", [])
    if not isinstance(pool, list) or (pool and not 2 <= len(pool) <= len(MODELS)):
        raise InfrastructureError("generator_pool must be empty or contain two to three model identities")
    if any(not isinstance(p, dict) or set(p) != {"model", "reasoning_effort"} for p in pool):
        raise InfrastructureError("Invalid generator_pool identity")
    selected = [identity(p) for p in pool] if pool else [primary]
    if primary not in selected or len({p["model"] for p in selected}) != len(selected):
        raise InfrastructureError("generator_pool must contain the primary identity and distinct models")
    # Stable action order is part of the checkpoint contract.
    return sorted(selected, key=lambda p: p["model"])


def mission_identity(config: dict, mission) -> dict:
    settings = config["codex"]
    selected = mission.generator or identity(settings)
    if selected not in generator_pool(settings):
        raise InfrastructureError("The mission selected a generator outside the frozen pool")
    if (mission.role == "G" or mission.budget_phase != "search"
            or mission.kind != "research") and selected != identity(settings):
        raise InfrastructureError("Control and integration must retain the primary model")
    return identity(selected)


def require_request_identity(request: dict, settings: dict) -> None:
    """A pool permits research proposals only; persistent control keeps one model."""
    selected, primary = identity(request), identity(settings)
    if selected not in generator_pool(settings):
        raise InfrastructureError("Request model is outside the authorized generator pool")
    selection = request.get("generator_selection")
    if selected == primary and selection is None:
        return
    if (not isinstance(selection, dict) or selection.get("identity") != selected
            or not isinstance(selection.get("role"), str) or selection["role"] == "G"
            or selection.get("action") != selection["role"] + "|" + selected["model"] + "|" + selected["reasoning_effort"]
            or request.get("kind") != "source-proposal" or request.get("budget_phase") != "search"
            or any(key in request for key in ("conversation", "meta_role", "active_control", "observer"))):
        raise InfrastructureError("Mixed models are authorized only for isolated research proposals")
