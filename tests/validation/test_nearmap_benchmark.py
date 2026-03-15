"""
Nearmap Counterfactual Governance Benchmark
==============================================
Active benchmark: test_nearmap_benchmark_v2.py (two-gate architecture)
Prior art: test_nearmap_benchmark_v1_prior_art.py (single composite score)

This file is a stub. The active benchmark has moved to v2 which uses
per-tool centroids from canonical Nearmap API documentation (Gate 1)
and behavioral boundary scoring (Gate 2).

Historical context:
    v1 (single composite): 82.6% accuracy, 75.1% ESCALATE, 44.6% FP
    v2 (two-gate): see test_nearmap_benchmark_v2.py for current metrics
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="Moved to test_nearmap_benchmark_v2.py (two-gate architecture). "
           "Prior art preserved at test_nearmap_benchmark_v1_prior_art.py."
)


# Stub class to preserve pytest collection without failures.
# The real tests are in test_nearmap_benchmark_v2.py.
class TestDecisionAccuracy:
    def test_see_v2(self):
        pass

class TestAdversarialRobustness:
    def test_see_v2(self):
        pass
