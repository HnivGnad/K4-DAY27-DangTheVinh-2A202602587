"""Offline behavioral tests; no harness internals or phase files are read."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

# Implement only the public Verdict contract for isolated handler testing.
api = ModuleType("api")
api.Verdict = lambda **values: SimpleNamespace(**values)
sys.modules["api"] = api
spec = importlib.util.spec_from_file_location("defense", Path(__file__).with_name("defense.py"))
defense = importlib.util.module_from_spec(spec)
spec.loader.exec_module(defense)
BASELINE = json.loads((Path(__file__).resolve().parents[1] / "data/baselines.json").read_text())


class Tools:
    def __init__(self, result, budget=10):
        self.result, self.budget, self.spent, self.calls = result, budget, 0, 0

    def budget_remaining(self):
        return self.budget - self.spent

    def spend_so_far(self):
        return self.spent

    def __getattr__(self, method):
        costs = {"batch_profile": 1, "contract_diff": 1.5, "lineage_graph_slice": 1,
                 "feature_drift": 2, "embedding_drift": 2}
        def call(*args):
            self.calls += 1
            self.spent += costs[method]
            return self.result
        return call


def context(result, budget=10):
    return SimpleNamespace(tools=Tools(result, budget), baseline=BASELINE, state={})


class DefenseTests(unittest.TestCase):
    def test_clean_and_each_numeric_batch_fault(self):
        clean = dict(row_count=500, null_rate={"customer_id": 0.003},
                     mean_amount=82, std_amount=10, staleness_min=3)
        self.assertFalse(defense.check_data_batch({"batch_id": "sample"}, context(clean)).alert)
        for change in (dict(row_count=100), dict(row_count=900), dict(mean_amount=120),
                       dict(null_rate={"customer_id": 0.2}), dict(staleness_min=20)):
            self.assertTrue(defense.check_data_batch({"batch_id": "sample"}, context(dict(clean, **change))).alert)

    def test_contract_and_ai_faults(self):
        cases = [
            (defense.check_contract_checkpoint, {"contract_id": "c", "checkpoint_batch_id": "b"},
             {"violations": ["type_violation"], "freshness_delay_min": 0}),
            (defense.check_contract_checkpoint, {"contract_id": "c", "checkpoint_batch_id": "b"},
             {"violations": [], "freshness_delay_min": 100}),
            (defense.check_feature_materialization, {"feature_view": "f", "batch_id": "b"},
             {"mean_shift_sigma": 2}),
            (defense.check_embedding_batch, {"corpus": "c", "chunk_batch_id": "b"},
             {"centroid_shift": 0, "avg_doc_age_days": 100}),
            (defense.check_embedding_batch, {"corpus": "c", "chunk_batch_id": "b"},
             {"centroid_shift": 1, "avg_doc_age_days": 0}),
        ]
        for handler, payload, result in cases:
            with self.subTest(handler=handler.__name__, result=result):
                self.assertTrue(handler(payload, context(result)).alert)
                self.assertFalse(handler(payload, context({"error": "unavailable"})).alert)

    def test_lineage_declared_and_learned_edges(self):
        ctx = context({"actual_upstream": ["a", "b"], "actual_downstream_count": 1, "duration_ms": 100})
        for _ in range(2):
            self.assertFalse(defense.check_lineage_run({"run_id": "r"}, ctx).alert)
        ctx.tools.result["actual_upstream"] = ["a"]
        self.assertTrue(defense.check_lineage_run({"run_id": "r"}, ctx).alert)
        self.assertTrue(defense.check_lineage_run({"run_id": "r", "expected_upstream": ["a", "b"]}, ctx).alert)

    def test_overage_is_bounded(self):
        ctx = context({"mean_shift_sigma": 1}, budget=4)
        payload = {"feature_view": "f", "batch_id": "b"}
        for _ in range(3):
            self.assertTrue(defense.check_feature_materialization(payload, ctx).alert)
        self.assertFalse(defense.check_feature_materialization(payload, ctx).alert)
        self.assertEqual(ctx.tools.spent, 6)
        self.assertEqual(ctx.tools.calls, 3)


if __name__ == "__main__":
    unittest.main()
