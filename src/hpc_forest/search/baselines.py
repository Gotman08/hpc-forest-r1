"""Simple comparison policies from the AB-MCTS paper, not AB-MCTS algorithms."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
from treequest.algos.tree import Tree
from treequest.trial import TrialStore


@dataclass
class SamplingState:
    tree: Tree = field(default_factory=Tree.with_root_node)
    trial_store: TrialStore = field(default_factory=TrialStore)
    last_node: int = -1


class SamplingBaseline:
    def __init__(self, policy: str):
        self.policy = policy

    def init_tree(self):
        return SamplingState()

    def ask(self, state, actions):
        state = copy.deepcopy(state)
        parent = state.tree.get_node(-1 if self.policy == "repeated-sampling" else state.last_node)
        # Uniform generator selection in these baselines, never described as Thompson sampling.
        action = actions[0] if len(actions) == 1 else str(np.random.choice(actions))
        return state, state.trial_store.create_trial(parent, action)

    def tell(self, state, trial_id, result):
        state = copy.deepcopy(state)
        trial = state.trial_store.get_finished_trial(trial_id, result[1])
        if trial is not None:
            parent = state.tree.get_node(trial.node_to_expand)
            node = state.tree.add_node(result, parent, trial.action)
            state.last_node = node.expand_idx
        return state
