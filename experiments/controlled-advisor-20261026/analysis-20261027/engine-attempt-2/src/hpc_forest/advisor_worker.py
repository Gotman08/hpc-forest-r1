"""One bounded local TabPFN invocation; never downloads weights during a campaign."""
from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path

from .advisor import FEATURES, MODEL_VERSION, PACKAGE_VERSION, VERSION
from .core import atomic_json, digest, file_digest


def ranking_accuracy(expected, predicted):
    pairs = [(i, j) for i in range(len(expected)) for j in range(i)
             if abs(expected[i] - expected[j]) > 0.005]
    if not pairs:
        return None
    return sum(1.0 if (expected[i] - expected[j]) * (predicted[i] - predicted[j]) > 0
               else 0.5 if predicted[i] == predicted[j] else 0 for i, j in pairs) / len(pairs)


def predict(request):
    from .advisor_validation import POLICY, decision_validation, validation_split

    policy = request.get("validation_policy", "gain_rank_v2")
    if policy not in ("gain_rank_v2", POLICY):
        raise ValueError("Unknown validation policy")
    if (request["schema"] != VERSION or request["feature_names"] != FEATURES
            or request["model_version"] != MODEL_VERSION or request["package_version"] != PACKAGE_VERSION
            or importlib.metadata.version("tabpfn") != PACKAGE_VERSION):
        raise ValueError("TabPFN package/feature contract mismatch")
    checkpoint = Path(request["runtime"]["model_path"])
    if (not checkpoint.is_file() or checkpoint.suffix != ".safetensors"
            or file_digest(checkpoint) != request["runtime"]["model_sha256"]):
        raise ValueError("TabPFN weights missing or changed; provision them before launch")
    import numpy as np
    import torch
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    context, candidates = request["context"], request["candidates"]
    cutoff = min(e["captured_at"] for e in candidates)
    if any(e["observed_at"] >= cutoff or e["captured_at"] > e["observed_at"] for e in context):
        raise ValueError("Future outcomes cannot be used as admission context")
    x = np.asarray([e["features"] for e in context], dtype=float)
    y = np.asarray([e["target"] for e in context], dtype=float)
    z = np.asarray([e["features"] for e in candidates], dtype=float)
    if (len(context) < 8 or not len(candidates) or x.shape[1] != len(FEATURES)
            or z.shape[1] != len(FEATURES) or not all(np.isfinite(a).all() for a in (x, y, z))):
        raise ValueError("Malformed measured context")
    model = TabPFNRegressor.create_default_for_version(
        ModelVersion.V3_5, model_path=checkpoint, device="cpu", n_estimators=4,
        n_preprocessing_jobs=1, random_state=request["seed"], fit_mode="fit_preprocessors")
    response = {"request_sha256": digest(request), "model_version": MODEL_VERSION,
                "validation": {}, "status": "validation_rejected", "predictions": []}
    if policy == POLICY:
        roles = {e["role"] for e in candidates}
        if len(roles) != 1:
            raise ValueError("Decision validation needs a single candidate tree")
        fit, held, info = validation_split(context, roles.pop())
        response["validation"] = info
        if info.get("reason"):
            return response
        model.fit(x[fit], y[fit])
        info = decision_validation([context[i] for i in held], model.predict(x[held]), info)
        response["validation"] = info
        if info.get("reason"):
            return response
        model.fit(x, y)
        predictions = model.predict(z)
        if not np.isfinite(predictions).all():
            raise ValueError("Non-finite TabPFN predictions")
        response.update(status="validated", predictions=predictions.tolist())
        return response
    # Hold out the most recent measurements. Never validate on the rows fitted,
    # future results, a random mixture of descendants, or the candidates to rank.
    holdout = max(3, len(y) // 4)
    validation_cutoff = min(e["captured_at"] for e in context[-holdout:])
    fit_indices = [i for i, e in enumerate(context[:-holdout]) if e["observed_at"] < validation_cutoff]
    if len(fit_indices) < 5:
        response["validation"] = {"reason": "insufficient_strictly_earlier_context"}
        return response
    model.fit(x[fit_indices], y[fit_indices])
    validation_prediction = model.predict(x[-holdout:])
    if not np.isfinite(validation_prediction).all():
        raise ValueError("Non-finite validation predictions")
    accuracy = ranking_accuracy(y[-holdout:], validation_prediction)
    validation = {"fit_ids": [context[i]["id"] for i in fit_indices],
                  "held_out_ids": [e["id"] for e in context[-holdout:]],
                  "pairwise_accuracy": accuracy,
                  "mae_score_gain": float(np.mean(np.abs(validation_prediction - y[-holdout:]))),
                  "cutoff": validation_cutoff}
    response["validation"] = validation
    if accuracy is None or accuracy <= 0.5:
        return response
    model.fit(x, y)
    predictions = model.predict(z)
    if not np.isfinite(predictions).all():
        raise ValueError("Non-finite TabPFN predictions")
    response.update(status="validated", predictions=predictions.tolist())
    return response


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    try:
        response = predict(request)
    except Exception as exc:
        # Dependency/authentication diagnostics stay local; never print tokens.
        atomic_json(Path(sys.argv[2]), {"status": "unavailable", "error_type": type(exc).__name__})
        print("TabPFN unavailable: " + type(exc).__name__, flush=True)
        return 1
    atomic_json(Path(sys.argv[2]), response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
