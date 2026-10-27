"""Deterministic pre-generation source and measured trajectory features.

These are bounded static signals, not a claim that TabPFN understands C++.
No proposed child's source, benchmark, or later sibling result enters a row.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

LEXICAL = ["files", "characters", "lines", "tokens", "for", "while", "if", "switch",
           "return", "float", "double", "int", "const", "restrict", "pragma", "omp",
           "simd", "cuda", "intrinsics", "allocations", "memory_ops", "arithmetic",
           "indexing", "depth", "transformations", "parent_log_ratio"]
STRUCTURE = ["max_brace_depth", "bitwise", "comparisons", "numeric_literals", "vector128",
             "vector256", "vector512", "omp_parallel", "omp_schedule", "alignment",
             *[f"token_bigram_{i}" for i in range(32)]]
HISTORY = ["parent_score", "parent_correct", "best_score_before", "completed_before",
           "tree_completed_before", "parent_children_before", "child_valid_fraction",
           "child_gain_mean", "child_gain_best", "child_gain_last", "child_infra_fraction",
           "remaining_fraction"]
FEATURES = LEXICAL + STRUCTURE + HISTORY


def feature_vector(files, mission, parent_log_ratio=0.0):
    code = "\n".join(files[name] for name in sorted(files))
    clean = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                   " ", code, flags=re.S)
    words = re.findall(r"[A-Za-z_]\w*", clean)
    counts = [words.count(word) for word in LEXICAL[4:13]]
    values = [len(files), len(clean), len(clean.splitlines()), len(words), *counts,
              len(re.findall(r"\b(?:restrict|__restrict__?)\b", clean)),
              len(re.findall(r"#\s*pragma\b", clean)), words.count("omp"), words.count("simd"),
              sum(w.startswith(("cuda", "__global__", "__shared__")) for w in words),
              sum(w.startswith(("_mm", "__builtin_")) for w in words),
              sum(w in {"malloc", "calloc", "realloc", "new"} for w in words),
              sum(w in {"memcpy", "memset", "memmove"} for w in words),
              len(re.findall(r"[+*/%-]", clean)), clean.count("["), mission.depth,
              len(mission.transformations), float(parent_log_ratio)]
    depth = maximum = 0
    for char in clean:
        depth = max(0, depth + (1 if char == "{" else -1 if char == "}" else 0))
        maximum = max(maximum, depth)
    values += [maximum, len(re.findall(r"<<|>>|[&|^~]", clean)),
               len(re.findall(r"<=|>=|==|!=|[<>]", clean)),
               len(re.findall(r"\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)\b", clean)),
               sum(w.startswith("_mm_") or w.startswith("__m128") for w in words),
               sum(w.startswith("_mm256_") or w.startswith("__m256") for w in words),
               sum(w.startswith("_mm512_") or w.startswith("__m512") for w in words),
               len(re.findall(r"\bomp\s+parallel\b", clean)),
               len(re.findall(r"\bschedule\s*\(", clean)),
               sum(w in {"alignas", "aligned_alloc", "__builtin_assume_aligned"} for w in words)]
    # A fixed signed hash captures token/operator neighborhoods instead of only
    # totals. Identifiers/numbers are normalized; spelling cannot encode rewards.
    tokens = re.findall(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|<<|>>|==|!=|&&|\|\||[^\s]", clean)
    keywords = set(LEXICAL[4:13]) | {"else", "break", "continue", "static", "sizeof", "omp", "parallel"}
    tokens = [t if t in keywords or not re.match(r"[A-Za-z_0-9]", t) else
              "vector" if t.startswith(("_mm", "__m128", "__m256", "__m512")) else
              "number" if t[0].isdigit() else "identifier" for t in tokens]
    buckets = [0.0] * 32
    for left, right in zip(tokens, tokens[1:], strict=False):
        raw = hashlib.sha256((left + "\0" + right).encode()).digest()
        buckets[raw[0] % 32] += 1 if raw[1] & 1 else -1
    values += [v / max(1, len(tokens) - 1) for v in buckets]
    return [float(v) for v in values] + [0.0] * len(HISTORY)


def trajectory(db, mission, baseline, remaining_fraction):
    rows = []
    for row in db.rows("SELECT id,mission,result FROM trials WHERE epoch=? AND state<>'pending' ORDER BY created,id",
                       (mission.epoch,)):
        rows.append((row["id"], json.loads(row["mission"]), json.loads(row["result"] or "{}")))
    parent = next((result for identity, _, result in rows if identity == mission.parent_id), {})
    if not parent:
        parent = next((result for _, _, result in reversed(rows)
                       if result.get("commit") == mission.base_commit and result.get("score") is not None), {})
    epoch = db.one("SELECT base_commit FROM epochs WHERE id=?", (mission.epoch,))
    is_baseline = bool(epoch and mission.base_commit == epoch["base_commit"])
    score = parent.get("score", 0.5 if is_baseline else 0.0)
    score = float(score) if type(score) in (int, float) and math.isfinite(score) else 0.0
    children = [r for _, m, r in rows if m["parent_id"] == mission.parent_id and m["tree_id"] == mission.tree_id]
    scored = [r for r in children if type(r.get("score")) in (int, float) and math.isfinite(r["score"])]
    gains = [r["score"] - score for r in scored]
    measured = parent.get("mean_seconds", baseline if is_baseline else None)
    ratio = math.log(measured / baseline) if (type(measured) in (int, float) and measured > 0
                                              and baseline and baseline > 0) else 0.0
    values = [score, float(parent.get("correct", is_baseline) is True),
              max([0.5] + [r["score"] for _, _, r in rows if type(r.get("score")) in (int, float)]),
              len(rows), sum(m["tree_id"] == mission.tree_id for _, m, _ in rows), len(children),
              sum(r.get("correct") is True for r in scored) / max(1, len(scored)),
              sum(gains) / max(1, len(gains)), max(gains, default=0.0), gains[-1] if gains else 0.0,
              sum(r.get("status") == "infrastructure_error" for r in children) / max(1, len(children)),
              remaining_fraction]
    return ratio, [float(v) for v in values]
