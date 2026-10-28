"""Controller-owned tree results, independent of the most recent model lesson."""
from __future__ import annotations

import json

from hpc_forest.source_diversity import diversity_counts

MEASURED = "json_extract(payload,'$.facts.outcome.correct')=1 AND json_extract(payload,'$.facts.outcome.mean_seconds')>0"


def _brief(row):
    if row is None:
        return None
    record = json.loads(row["payload"])
    outcome = record.get("facts", {}).get("outcome", {})
    interpretation = record.get("model_interpretation", {})
    return {"id": record["id"],
            **{key: outcome.get(key) for key in ("status", "correct", "mean_seconds")},
            "hypothesis_as_data": str(interpretation.get("hypothesis") or interpretation.get("claim") or "")[:240]}


def tree_overview(connection, scope, args, role):
    """Return bounded representatives, not a judgement that a whole topic failed."""
    where = scope + " AND role=?"
    params = [*args, role]
    counts = connection.execute(
        "SELECT count(*) AS records, sum(kind='experiment') AS trials, "
        "sum(kind='experiment' AND (" + MEASURED + ")) AS valid, "
        "sum(kind='experiment' AND json_extract(payload,'$.facts.outcome.correct')=0 "
        "AND json_extract(payload,'$.facts.outcome.status')='incorrect') AS incorrect "
        "FROM memory_facts WHERE " + where, params).fetchone()
    counts = {key: counts[key] or 0 for key in counts.keys()}
    counts["unmeasured"] = counts["trials"] - counts["valid"] - counts["incorrect"]
    experiments = "SELECT payload FROM memory_facts WHERE " + where + " AND kind='experiment'"
    latest = connection.execute(experiments + " ORDER BY created DESC,id LIMIT 1", params).fetchone()
    best = connection.execute(experiments + " AND (" + MEASURED + ") "
        "ORDER BY json_extract(payload,'$.facts.outcome.mean_seconds'),created DESC,id LIMIT 1", params).fetchone()
    alternative = None
    if best is not None:
        facts = json.loads(best["payload"])
        identity = facts["facts"].get("outcome", {}).get("tree_hash") or facts["facts"].get("commit") or facts["id"]
        # A slower distinct source version is useful evidence too. No top-k time filter.
        alternative = connection.execute(experiments + " AND (" + MEASURED + ") "
            "AND coalesce(json_extract(payload,'$.facts.outcome.tree_hash'), "
            "json_extract(payload,'$.facts.commit'),id)<>? ORDER BY created DESC,id LIMIT 1",
            [*params, identity]).fetchone()
    return {"records": counts.pop("records"), "results": counts,
            "source_diversity": diversity_counts(connection, where, params),
            "best": _brief(best), "latest": _brief(latest), "alternative": _brief(alternative)}
