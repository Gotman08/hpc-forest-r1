"""Global process counters must not enter a candidate's selection metrics."""

import json

from hpc_forest.core import Outcome
from hpc_forest.search import _extract_roofline


def test_search_ignores_legacy_rusage_and_retains_compiler_diagnostics(tmp_path):
    build = tmp_path / "build.log"
    build.write_text(json.dumps({"vectorization": ["loop optimized: yes", "loop missed: no"]}),
                     encoding="utf8")
    check = tmp_path / "correctness.log"
    check.write_text(json.dumps({"rusage": {
        "max_rss_kb": 999999, "minor_page_faults": 1234,
        "cpu_utilization_ratio": 3.9, "sys_seconds": 0.1, "user_seconds": 2.0,
    }}), encoding="utf8")
    assert _extract_roofline(Outcome("valid", logs=[str(build), str(check)])) == {
        "vec_optimized": 1, "vec_missed": 1}
