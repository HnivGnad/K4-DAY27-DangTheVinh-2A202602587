"""Streaming pipeline defenses using only the documented, metered API.

One measurement per event; no schedule, seed, answer-key or filesystem access.
Published three-sigma bounds anchor every numeric check.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def measure(ctx, method, cost, *args):
    # Reserve a bounded overage for coverage: abruptly stopping at zero leaves
    # all later events unobserved. Still cap the maximum penalty at 10 points.
    if "initial_budget" not in ctx.state:
        ctx.state["initial_budget"] = ctx.tools.budget_remaining()
    if ctx.tools.spend_so_far() + cost > 1.5 * ctx.state["initial_budget"]:
        return None
    result = getattr(ctx.tools, method)(*args)
    if not isinstance(result, dict) or "error" in result:
        return None
    return result


def outside(value, low, high):
    return value < low or value > high


def check_data_batch(payload, ctx):
    p = measure(ctx, "batch_profile", 1.0, payload["batch_id"])
    if p is None:
        return Verdict(alert=False, pillar="checks")
    b = ctx.baseline
    alert = (
        outside(p["row_count"], b["row_count_min"], b["row_count_max"])
        or outside(p["mean_amount"], b["mean_amount_min"], b["mean_amount_max"])
        or p["null_rate"]["customer_id"] > b["null_rate_max"]
        or p["staleness_min"] > b["staleness_min_max"]
    )
    # Two independent moderate deviations can corroborate a weak fault.
    # Convert the published mean +/- 3 sigma intervals to absolute z scores.
    z_scores = []
    for field, low, high in (
        ("row_count", b["row_count_min"], b["row_count_max"]),
        ("mean_amount", b["mean_amount_min"], b["mean_amount_max"]),
    ):
        z_scores.append(abs(p[field] - (low + high) / 2) / ((high - low) / 6))
    alert = alert or all(z > 2.0 for z in z_scores)
    return Verdict(alert=bool(alert), pillar="checks")


def check_contract_checkpoint(payload, ctx):
    p = measure(ctx, "contract_diff", 1.5,
                payload["contract_id"], payload["checkpoint_batch_id"])
    alert = p is not None and (
        bool(p["violations"])
        or p["freshness_delay_min"] > ctx.baseline["freshness_delay_max_min"]
    )
    return Verdict(alert=bool(alert), pillar="contracts")


def check_lineage_run(payload, ctx):
    p = measure(ctx, "lineage_graph_slice", 1.0, payload["run_id"])
    if p is None:
        return Verdict(alert=False, pillar="lineage")
    upstream = set(p["actual_upstream"])
    expected = payload.get("expected_upstream")
    # Prefer a declared graph. Otherwise learn the usual upstream cardinality
    # online, per named transform; a mode resists occasional faulty runs.
    key = payload.get("transform", payload.get("job_name", payload.get("job", "default")))
    history = ctx.state.setdefault("lineage_counts", {}).setdefault(str(key), {})
    usual_count = max(history, key=lambda count: (history[count], count)) if history else None
    missing = (not set(expected).issubset(upstream)) if expected is not None else (
        not upstream or (sum(history.values()) >= 2 and len(upstream) < usual_count)
    )
    alert = (
        missing or p["actual_downstream_count"] < 1
        or p["duration_ms"] > ctx.baseline["lineage_duration_ms_max"]
    )
    history[len(upstream)] = history.get(len(upstream), 0) + 1
    return Verdict(alert=bool(alert), pillar="lineage")


def check_feature_materialization(payload, ctx):
    p = measure(ctx, "feature_drift", 2.0, payload["feature_view"], payload["batch_id"])
    alert = p is not None and (
        abs(p["mean_shift_sigma"]) > ctx.baseline["feature_mean_shift_sigma_max"]
    )
    return Verdict(alert=bool(alert), pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    p = measure(ctx, "embedding_drift", 2.0, payload["corpus"], payload["chunk_batch_id"])
    alert = p is not None and (
        p["centroid_shift"] > ctx.baseline["embedding_centroid_shift_max"]
        or p["avg_doc_age_days"] > ctx.baseline["corpus_avg_doc_age_days_max"]
    )
    return Verdict(alert=bool(alert), pillar="ai_infra")
