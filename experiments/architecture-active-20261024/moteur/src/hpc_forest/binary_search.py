"""Optional greedy binary search. This policy is distinct from AB-MCTS-A."""

from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field

from treequest.algos.tree import Tree
from treequest.trial import Trial

from .core import ForestError

VERSION = "binary-greedy-v3"


class SearchExhausted(ForestError):
    """A local tree has no eligible parent left to expand."""


def enabled(config: dict) -> bool:
    return config.get("binary_tree", {}).get("enabled", False)


@dataclass
class BinaryState:
    tree: Tree = field(default_factory=Tree.with_root_node)
    active_parent: int = -1
    pending: Trial | None = None
    stopped: bool = False
    decisions: list[dict] = field(default_factory=list)


class BinaryGreedy:
    """Evaluate two siblings, then expand only the faster correct sibling."""

    def init_tree(self) -> BinaryState:
        return BinaryState()

    def check_admission(self, state: BinaryState, max_depth: int) -> None:
        if state.stopped:
            raise SearchExhausted("Neither sibling has a correct finite measured result")
        parent = state.tree.get_node(state.active_parent)
        if max_depth > 0 and parent.depth >= max_depth:
            raise SearchExhausted("Binary tree reached the configured maximum depth")

    def ask(self, state: BinaryState, actions: list[str]):
        if len(actions) != 1:
            raise ForestError("Binary search requires a separate tree for each role")
        self.check_admission(state, 0)
        if state.pending is not None:
            raise ForestError("A binary sibling is already pending")
        state = copy.deepcopy(state)
        parent = state.tree.get_node(state.active_parent)
        if len(parent.children) >= 2:
            raise ForestError("A binary parent cannot have more than two children")
        trial = Trial(trial_id="binary-" + uuid.uuid4().hex,
                      node_to_expand=parent.expand_idx, action=actions[0],
                      parent_state=parent.state)
        state.pending = trial
        return state, trial

    def tell(self, state: BinaryState, trial_id: str, result):
        if state.pending is None or state.pending.trial_id != trial_id:
            raise ForestError("Unknown pending binary trial")
        state = copy.deepcopy(state)
        parent = state.tree.get_node(state.pending.node_to_expand)
        data, score = result
        data = {**data, "side": "left" if not parent.children else "right", "pruned": False}
        # An infrastructure error/duplicate retains an absent score, never a fabricated zero.
        state.tree.add_node((data, score), parent, trial_id, validate_score_range=False)
        state.pending = None
        if len(parent.children) == 2:
            candidates = [node for node in parent.children if self._eligible(node)]
            # Python's stable min makes the left child win an exact tie.
            winner = min(candidates, key=lambda node: node.state["mean_seconds"], default=None)
            for child in parent.children:
                child.state["pruned"] = child is not winner
            state.stopped = winner is None
            if winner is not None:
                state.active_parent = winner.expand_idx
            state.decisions.append({
                "parent_id": parent.state["experiment_id"] if parent.state else None,
                "left_id": parent.children[0].state["experiment_id"],
                "right_id": parent.children[1].state["experiment_id"],
                "winner_id": winner.state["experiment_id"] if winner else None,
                "pruned_ids": [n.state["experiment_id"] for n in parent.children if n is not winner],
                "reason": "fastest_correct_child" if winner else "no_eligible_child",
            })
        return state

    @staticmethod
    def _eligible(node) -> bool:
        data = node.state
        seconds = data.get("mean_seconds")
        return (data.get("status") == "valid" and data.get("correct") is True
                and node.score is not None and node.score > 0
                and type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0)
