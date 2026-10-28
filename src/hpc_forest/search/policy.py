"""Validated TreeQuest policies; legacy AB-MCTS-A keeps its exact defaults."""
from __future__ import annotations

import math

import treequest as tq

from hpc_forest.core import ForestError, InfrastructureError

ALGORITHMS = {
    "ab-mcts-a": "AB-MCTS-A (Sakana)",
    "ab-mcts-m": "AB-MCTS-M (Sakana, expérimental)",
    "standard-mcts": "MCTS classique (témoin)",
    "repeated-sampling": "Échantillonnage indépendant (témoin)",
    "sequential-refinement": "Raffinement séquentiel (témoin)",
}
DEFAULT = {"algorithm": "ab-mcts-a", "distribution": "gaussian", "reward_prior": None}


def settings(config: dict) -> dict:
    binary = config.get("binary_tree", {})
    if not isinstance(binary, dict) or type(binary.get("enabled", False)) is not bool:
        raise ForestError("binary_tree.enabled must be a boolean")
    value = config.get("search", {})
    if not isinstance(value, dict):
        raise ForestError("search must be an object")
    algorithm = value.get("algorithm", "ab-mcts-a")
    if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
        raise ForestError("Unknown search.algorithm")
    result = {"algorithm": algorithm}
    allowed = {"algorithm"}
    if algorithm.startswith("ab-mcts-"):
        allowed.add("reward_prior")
        prior = value.get("reward_prior")
        if prior is not None and (type(prior) not in (float, int)
                                  or not math.isfinite(prior) or not 0 < prior < 1):
            raise ForestError("search.reward_prior must be null or strictly between 0 and 1")
        result["reward_prior"] = prior
    if algorithm == "ab-mcts-a":
        allowed.add("distribution")
        distribution = value.get("distribution", "gaussian")
        if distribution not in ("gaussian", "beta"):
            raise ForestError("search.distribution must be gaussian or beta")
        result["distribution"] = distribution
    if algorithm == "standard-mcts":
        allowed.update(("samples_per_action", "exploration_weight"))
        samples, weight = value.get("samples_per_action", 2), value.get("exploration_weight", math.sqrt(2))
        if type(samples) is not int or not 1 <= samples <= 16:
            raise ForestError("search.samples_per_action must be between 1 and 16")
        if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 < weight <= 100:
            raise ForestError("search.exploration_weight must be finite and positive")
        result.update(samples_per_action=samples, exploration_weight=weight)
    if set(value) - allowed:
        raise ForestError("Unused or unknown search settings: " + ", ".join(sorted(set(value) - allowed)))
    if binary.get("enabled") and result != DEFAULT:
        raise ForestError("binary_tree and another search policy cannot be combined")
    return result


def make_algorithm(value: dict):
    algorithm = value["algorithm"]
    if algorithm == "ab-mcts-a":
        return tq.ABMCTSA(dist_type=value["distribution"], reward_average_priors=value["reward_prior"])
    if algorithm == "ab-mcts-m":
        try:
            # No joblib fan-out or pruning: one admitted trial per tree, with Forest's
            # existing budget/closure guards. The optional sampler is heavier than A.
            return tq.ABMCTSM(reward_average_priors=value["reward_prior"],
                             enable_pruning=False, max_process_workers=1)
        except ImportError as exc:
            raise InfrastructureError(
                "AB-MCTS-M requires the optional hpc-forest-r1[sakana-m] dependencies "
                "in the execution environment; no fallback was made"
            ) from exc
    if algorithm == "standard-mcts":
        return tq.StandardMCTS(samples_per_action=value["samples_per_action"],
                               exploration_weight=value["exploration_weight"])
    from hpc_forest.search.baselines import SamplingBaseline

    return SamplingBaseline(algorithm)


def label(config: dict) -> str:
    value = settings(config)
    if config.get("binary_tree", {}).get("enabled"):
        return "binary-greedy"
    return value["algorithm"] + ("/" + value["distribution"] if value["algorithm"] == "ab-mcts-a" else "")
