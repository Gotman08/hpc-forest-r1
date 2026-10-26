"""Join measured performance, consumed budgets and failures for all six families."""
import argparse
import csv
import json
from pathlib import Path


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


parser = argparse.ArgumentParser()
parser.add_argument("--results", type=Path, required=True)
args = parser.parse_args()
arms = {(r["case"], r["condition"]): r for r in read(args.results / "arms.csv")}
controls = {(r["case"], r["condition"]): r for r in read(args.results / "control-recovery.csv")}
registered = {r["case"]: r for r in read(args.results / "registered/common-comparison.csv")}
reserved = {r["case"]: r for r in read(args.results / "reserved/common-comparison.csv")}
closures = read(args.results / "closure-quality.csv")
if set(registered) != set(reserved) or set(registered) != {case for case, _ in arms}:
    raise ValueError("The measured distributions and search arms cover different families")
rows = []
for case in sorted(registered):
    row = {"case": case}
    for side in ("off", "on"):
        identity = (case, "advisor_" + side)
        arm, control = arms[identity], controls[identity]
        row[side + "_delivered"] = arm["pipeline_complete"]
        row[side + "_minutes"] = float(arm["elapsed_seconds"]) / 60
        row[side + "_research_trials"] = arm["research_trials"]
        row[side + "_correct_trials"] = arm["correct_trials"]
        row[side + "_stop_reason"] = arm["stop_reason"]
        row[side + "_error"] = arm["error"]
        row[side + "_initial_mother_error"] = control["initial_mother_error"]
        row[side + "_unavailable_analyst_jobs"] = arm["analyst_jobs_unavailable"]
        row[side + "_closed_with_unavailable_analysis"] = any(
            c["case"] == case and c["condition"] == identity[1] and c["closure_confirmed"] == "True"
            and bool(json.loads(c["unavailable_analyses"])) for c in closures)
        for distribution, data in (("registered", registered[case]), ("reserved", reserved[case])):
            for metric in ("status", "reason", "speedup", "seconds"):
                row[f"{side}_{distribution}_{metric}"] = data[side + "_" + metric]
    for distribution, data in (("registered", registered[case]), ("reserved", reserved[case])):
        row[distribution + "_on_over_off_speedup"] = data["on_over_off_speedup"]
    for metric in ("advisor_calls", "advisor_validated_calls", "advisor_reorders", "advisor_seconds"):
        row[metric] = arms[(case, "advisor_on")][metric]
    rows.append(row)
with (args.results / "comparison-summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps({"families": len(rows), "file": str(args.results / "comparison-summary.csv")}))
