"""Compact public telemetry; never print model reasoning or full prompts."""
from pathlib import Path
import json
import time
from engine_study import CONDITIONS, STUDY, OUT, read, write

def snapshot():
    rows = []
    for key in CONDITIONS:
        artifact = STUDY / key
        if not (artifact / "authorization.json").exists():
            continue
        auth = read(artifact / "authorization.json")
        requests = []
        for path in sorted((artifact / "worker").glob("*/downloaded-request.json")):
            data = read(path)
            folder = path.parent
            request = {"nonce":folder.name, "mission_id":data.get("mission_id"), "role":data.get("meta_role"),
                       "phase":data.get("conversation",{}).get("phase",data.get("budget_phase")), "created":data.get("created_at"),
                       "claimed":(folder / "generation-claimed.json").exists(),
                       "returned":(folder / "response.json").exists(),
                       "delivered":(folder / "delivered.json").exists()}
            if request["returned"]:
                response = read(folder / "response.json")
                request.update(status=response.get("status"),error=response.get("error"),
                               response_keys=list(response))
            requests.append(request)
        beat = artifact / "worker/worker-heartbeat.json"
        failure = artifact / "relay-failure.json"
        row = {"condition":key,"job_id":auth["job_id"],"requests":len(requests),
               "returned":sum(r["returned"] for r in requests),"delivered":sum(r["delivered"] for r in requests),
               "active":sum(r["claimed"] and not r["returned"] for r in requests),
               "heartbeat_age":round(time.time()-read(beat)["alive_at"],1) if beat.exists() else None,
               "relay_failed":failure.exists(),"finished":(artifact / "worker-finished.json").exists()}
        if (artifact / "worker/forest-plan.json").exists():
            row["forest_width"] = read(artifact / "worker/forest-plan.json").get("parallelism")
        if failure.exists():
            row["error_tail"] = read(failure)["traceback"][-1200:]
        write(OUT / "data" / key / "native-call-status.json", requests)
        rows.append(row)
    write(OUT / "data/live-status.json", {"at":time.time(),"conditions":rows})
    print(json.dumps(rows, ensure_ascii=True))

if __name__ == "__main__":
    snapshot()
