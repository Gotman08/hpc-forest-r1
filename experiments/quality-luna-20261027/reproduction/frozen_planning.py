"""Study-only initial-plan control using real, separate native Mother turns.

No conversation receipt is fabricated or copied. Mother acknowledges the common
model-authored plan in her own first turn; later steering remains unrestricted.
"""
import copy
import json

from hpc_forest.core import InfrastructureError, digest


def install(plan_record):
    from hpc_forest import mother

    original_render, original_validate = mother.render_plan, mother.validated_plan
    plan = original_validate(copy.deepcopy(plan_record["plan"]), choose_trees=True)
    if plan_record["plan_sha256"] != digest(plan):
        raise InfrastructureError("Frozen Mother plan digest mismatch")

    def render(phase, sources, statement, observed, **kwargs):
        result = original_render(phase, sources, statement, observed, **kwargs)
        if phase == "preparation" and kwargs.get("choose_trees"):
            result["messages"][0]["content"] += (
                " Controlled experiment: an independent GPT-6 Luna Max Mother has already "
                "authored the common initial plan below from this same naive source and contract. "
                "For this initial turn, return that exact JSON plan verbatim, including analysis, "
                "children and G. Do not revise it or generate a different decomposition. "
                "This establishes YOUR independent conversation; no previous research results "
                "or candidates are imported. Later steering decisions remain yours and use only "
                "this campaign's measured evidence. The common plan is an initial experimental "
                "condition, not evidence that any proposed optimization works.")
            payload = json.loads(result["messages"][1]["content"])
            payload["frozen_initial_plan_as_data"] = plan
            result["messages"][1]["content"] = json.dumps(payload, ensure_ascii=False)
        return result

    def validate(value, roles=None, *, choose_trees=False):
        result = original_validate(value, roles, choose_trees=choose_trees)
        if choose_trees and result != plan:
            raise InfrastructureError("Mother changed the frozen initial plan; research must not start")
        return result

    mother.render_plan, mother.validated_plan = render, validate

    def restore():
        mother.render_plan, mother.validated_plan = original_render, original_validate
    return restore
