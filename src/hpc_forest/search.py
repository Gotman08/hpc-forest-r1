"""Transactional search persistence; AB-MCTS-A by default, optional binary policy."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import pickle
import time
import uuid
from dataclasses import asdict

import numpy as np
import treequest as tq

from .binary_search import VERSION as BINARY_VERSION
from .binary_search import BinaryGreedy, enabled
from .core import ForestError, InfrastructureError, Mission, Outcome, canonical
from .registry import Registry

VERSION = importlib.metadata.version("treequest")


def pack(state, rng) -> bytes:
    return pickle.dumps((state, rng), protocol=5)


def unpack(blob: bytes, sha: str | None = None):
    if sha is not None and hashlib.sha256(blob).hexdigest() != sha:
        raise InfrastructureError("Corrupt local TreeQuest checkpoint")
    # Local controller database only. Never unpickle checkpoints supplied by an agent or a URL.
    return pickle.loads(blob)


class Search:
    def __init__(self, db: Registry):
        self.db = db
        self.binary = enabled(db.get("config", {}))
        self.algo = BinaryGreedy() if self.binary else tq.ABMCTSA()
        self.version = BINARY_VERSION if self.binary else VERSION

    def initialize(self, epoch: int, role: str, seed: int) -> str:
        tree_id = f"e{epoch}:{role}"
        existing = self.db.one("SELECT version FROM trees WHERE id=?", (tree_id,))
        if existing:
            if existing["version"] != self.version:
                raise InfrastructureError("Search policy/version changed; create a new campaign")
            return tree_id
        blob = pack(self.algo.init_tree(), np.random.RandomState(seed).get_state())
        with self.db.connection:
            self.db.connection.execute(
                "INSERT INTO trees(id,epoch,role,checkpoint,sha256,version) VALUES(?,?,?,?,?,?)",
                (tree_id, epoch, role, blob, hashlib.sha256(blob).hexdigest(), self.version),
            )
        return tree_id

    def _tree(self, tree_id: str):
        row = self.db.one("SELECT * FROM trees WHERE id=?", (tree_id,))
        if not row or row["stopped"]:
            raise ForestError(f"Search unavailable: {tree_id}")
        if row["version"] != self.version:
            raise InfrastructureError("Search policy/version changed; create a new campaign")
        return row, unpack(row["checkpoint"], row["sha256"])

    def check_admission(self, tree_id: str, max_depth: int) -> None:
        if self.binary:
            _, (state, _) = self._tree(tree_id)
            self.algo.check_admission(state, max_depth)

    def snapshot(self) -> dict:
        labels = {}
        for row in self.db.rows("SELECT mission FROM trials ORDER BY created,id"):
            mission = json.loads(row["mission"])
            labels[mission["id"]] = mission["role"] + str(mission["ordinal"])
        trees, scored, max_depth, max_children = [], 0, 0, 0
        for row in self.db.rows("SELECT id,role FROM trees ORDER BY role"):
            _, (state, _) = self._tree(row["id"])
            nodes = []
            for node in state.tree.get_nodes():
                node_id = node.state["experiment_id"] if node.state else row["id"]
                parent_id = (node.parent.state["experiment_id"] if node.parent
                             and node.parent.state else row["id"] if node.parent else None)
                item = {"id": node_id, "label": labels.get(node_id, row["role"]),
                        "parent": parent_id, "depth": node.depth, "score": node.score,
                        "child_count": len(node.children)}
                if self.binary and node.state:
                    item.update(side=node.state["side"], pruned=node.state["pruned"])
                nodes.append(item)
                scored += int(node.state is not None and node.score is not None)
                max_depth = max(max_depth, node.depth)
                max_children = max(max_children, len(node.children))
            tree = {"role": row["role"], "nodes": nodes}
            if self.binary:
                tree.update(decisions=state.decisions, stopped=state.stopped)
            trees.append(tree)
        return {"policy": "binary-greedy" if self.binary else "ab-mcts-a",
                "scored_nodes": scored, "max_depth": max_depth,
                "max_children": max_children, "trees": trees}

    def ask(
        self,
        tree_id: str,
        actions: list[str],
        epoch: int,
        base: str,
        ordinal: int,
        worktree: str,
        slot_id: str,
    ) -> Mission:
        if self.db.one("SELECT id FROM trials WHERE tree_id=? AND state='pending'", (tree_id,)):
            raise ForestError("Only one pending trial per local tree; parallelize across trees")
        row, (state, rng) = self._tree(tree_id)
        global_rng = np.random.get_state()
        try:
            np.random.set_state(rng)
            state, trial = self.algo.ask(state, actions)
            next_rng = np.random.get_state()
        finally:
            np.random.set_state(global_rng)
        parent = trial.parent_state
        mission = Mission(
            id=uuid.uuid4().hex[:16],
            tree_id=tree_id,
            trial_id=str(trial.trial_id),
            epoch=epoch,
            role=trial.action,
            base_commit=parent["commit"] if parent else base,
            parent_id=parent["experiment_id"] if parent else None,
            delegation_parent=f"R/{trial.action}",
            depth=parent["depth"] + 1 if parent else 1,
            ordinal=ordinal,
            worktree=worktree,
        )
        blob = pack(state, next_rng)
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE trees SET checkpoint=?,sha256=? WHERE id=?",
                (blob, hashlib.sha256(blob).hexdigest(), tree_id),
            )
            self.db.connection.execute(
                "INSERT INTO trials VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    mission.id,
                    tree_id,
                    mission.trial_id,
                    epoch,
                    mission.role,
                    slot_id,
                    canonical(asdict(mission)),
                    row["checkpoint"],
                    "pending",
                    None,
                    time.time(),
                ),
            )
        return mission

    def update_mission(self, mission: Mission) -> None:
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE trials SET mission=? WHERE id=? AND state='pending'",
                (canonical(asdict(mission)), mission.id),
            )

    def finish(self, mission: Mission, outcome: Outcome) -> bool:
        row = self.db.one("SELECT * FROM trials WHERE id=?", (mission.id,))
        if row is None:
            raise ForestError("Unknown trial")
        if row["state"] != "pending":
            return False  # Idempotence is enforced above TreeQuest and its database write.
        _, (state, rng) = self._tree(mission.tree_id)
        if outcome.score is not None or self.binary:
            if outcome.score is not None and not 0 <= outcome.score <= 1:
                raise ForestError("TreeQuest reward outside [0,1]")
            node = {
                "experiment_id": mission.id,
                "commit": outcome.commit or mission.base_commit,
                "depth": mission.depth,
            }
            if self.binary:
                node.update(status=outcome.status, correct=outcome.correct,
                            mean_seconds=outcome.mean_seconds)
            if not mission.trial_id.startswith("enumeration-"):
                state = self.algo.tell(state, mission.trial_id, (node, outcome.score))
            status = "completed" if outcome.score is not None else outcome.status
        else:
            # Public TreeQuest has no cancellation API. Roll back the unobserved ask, retain RNG
            # progress and the cancellation receipt, and never substitute a synthetic zero reward.
            state, _ = unpack(row["before_state"])
            status = outcome.status
        blob = pack(state, rng)
        result = canonical(asdict(outcome))
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE trees SET checkpoint=?,sha256=? WHERE id=?",
                (blob, hashlib.sha256(blob).hexdigest(), mission.tree_id),
            )
            self.db.connection.execute(
                "UPDATE trials SET state=?,result=?,mission=? WHERE id=?",
                (status, result, canonical(asdict(mission)), mission.id),
            )
            if outcome.status != "duplicate":
                self.db.connection.execute(
                    "INSERT OR IGNORE INTO evaluations(experiment_id,epoch,phase,cache_key,payload,created)"
                    " VALUES(?,?,'search',?,?,?)",
                    (mission.id, mission.epoch, outcome.cache_key, result, time.time()),
                )
            if mission.role == "G":
                self.db.connection.execute(
                    "INSERT OR REPLACE INTO interactions VALUES(?,?,?)",
                    (mission.id, canonical(mission.sources), result),
                )
        return True

    def ask_enumeration(
        self, tree_id: str, epoch: int, base: str, ordinal: int, worktree: str, slot_id: str
    ) -> Mission:
        row, _ = self._tree(tree_id)
        mission = Mission(
            uuid.uuid4().hex[:16],
            tree_id,
            f"enumeration-{ordinal}",
            epoch,
            "G",
            base,
            None,
            "R/G",
            1,
            ordinal,
            worktree,
        )
        with self.db.connection:
            self.db.connection.execute(
                "INSERT INTO trials VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    mission.id,
                    tree_id,
                    mission.trial_id,
                    epoch,
                    "G",
                    slot_id,
                    canonical(asdict(mission)),
                    row["checkpoint"],
                    "pending",
                    None,
                    time.time(),
                ),
            )
        return mission

    def recover_pending(self) -> int:
        pending = self.db.rows("SELECT * FROM trials WHERE state='pending' ORDER BY created")
        for row in pending:
            mission = Mission(**json.loads(row["mission"]))
            self.finish(
                mission,
                Outcome("cancelled_interrupted", reason="Interrupted mission; slot retained"),
            )
            config = self.db.get("config")
            self.db.settle_tokens(row["slot_id"], 0 if config["backend"] == "recipe" else None)
            self.db.event("recovered_cancellation", {"experiment_id": mission.id})
        return len(pending)
