"""Audit each assigned arm, retaining failed audit receipts instead of omitting arms."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Contains <case>-r<repeat>-<condition>-evidence.tar.gz")
    parser.add_argument("common_extracted", type=Path)
    args = parser.parse_args()
    reproduction = Path(__file__).resolve().parent
    study = reproduction.parent
    results = study / "results"
    arms = json.loads((study / "monitoring-paths.json").read_text(encoding="utf8"))

    def command(script, *arguments):
        result = subprocess.run([sys.executable, str(reproduction / script), *map(str, arguments)],
                                capture_output=True, text=True, encoding="utf8", errors="replace")
        return {"script": script, "arguments": list(map(str, arguments)),
                "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def arm_audit(arm):
        identity = f"{arm['case']}-r{arm['repeat']}-{arm['condition']}"
        archive = args.work / (identity + "-evidence.tar.gz")
        evidence = args.work / (identity + "-control-evidence")
        calls = []
        if not archive.is_file():
            return {"arm": identity, "valid": False, "error": "Missing preserved archive", "calls": []}
        calls.append(command("audit_model_invocations.py", archive,
                             results / (identity + "-model-invocations.json")))
        calls.append(command("export_control_calls.py", archive, evidence,
                             results / (identity + "-control-calls")))
        if calls[-1]["exit_code"] == 0:
            calls.append(command("audit_exploration.py", archive, evidence / "registry.sqlite3",
                                 results / (identity + "-exploration")))
            calls.append(command("export_exploration_curve.py", evidence / "registry.sqlite3",
                                 results / (identity + "-curve")))
            calls.append(command("audit_control_archive.py", archive, evidence / "registry.sqlite3",
                                 results / (identity + "-stop-timeline")))
        receipt = {"arm": identity, "valid": all(c["exit_code"] == 0 for c in calls), "calls": calls}
        (results / (identity + "-local-audit.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
        return receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(arm_audit, arms))
    extras = [command("export_adviser_preflight.py", results),
              command("export_configuration_timings.py", args.common_extracted, results)]
    if all(r["valid"] for r in receipts):
        extras.append(command("compare_exploration.py", study))
        if extras[-1]["exit_code"] == 0:
            extras.append(command("audit_transfers.py", args.work, study))
        if extras[-1]["exit_code"] == 0:
            extras.append(command("finalize_local_audit.py"))
    report = {"assigned_arms": len(arms), "arms": receipts, "additional_audits": extras,
              "valid": all(r["valid"] for r in receipts) and all(r["exit_code"] == 0 for r in extras)}
    (results / "local-audit-run.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"valid": report["valid"], "arms": [{"arm": r["arm"], "valid": r["valid"]} for r in receipts],
                      "additional_audits": [{"script": r["script"], "exit_code": r["exit_code"]} for r in extras]}))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
