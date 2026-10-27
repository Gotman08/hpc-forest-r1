"""Durable application-to-ROMEO orchestration through the existing MCP connector."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from ..advisor import runtime as advisor_runtime
from ..advisor import settings as advisor_settings
from ..codex_worker import RomeoFiles
from ..core import atomic_json, file_digest
from ..evolution_archive import settings as evolution_settings
from ..model_policy import generator_pool, require_identity
from ..search_policy import settings as search_settings
from .campaigns import Campaigns, _read
from .paths import AppError, contained
from .runner_support import editable_files, executable, extract_verified
from .store import Store

LOGGER = logging.getLogger(__name__)
TERMINAL = {"completed", "failed", "cancelled"}


def public_mission(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in {
        "connection", "launch", "remote_root", "plan_id", "bundle_sha256", "session_id"}}


def connection(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf8"))
    if not Path(data["codex_config"]).is_file():
        raise AppError("La configuration du connecteur ROMEO est introuvable.")
    for value in (data["base_dir"], data["codex_home"]):
        if not PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
            raise AppError("Chemin ROMEO invalide dans la configuration locale.")
    for key, profile in data["profiles"].items():
        if key not in {"cpu", "gpu"} or profile["architecture"] not in {"x86_64", "aarch64"}:
            raise AppError("Profil de calcul ROMEO invalide.")
        for field in ("python", "codex"):
            if not PurePosixPath(profile[field]).is_absolute():
                raise AppError("Le profil ROMEO exige des chemins absolus.")
    return data


def freeze_bundle(store: Store, mission: dict, settings: dict) -> tuple[Path, dict]:
    prepared = store.get(mission["prepared_id"], "prepared")
    selected = prepared["contract"]
    require_identity(selected)
    editable_files(selected)
    executable(selected["contract"])
    source = contained(store.root, "prepared/" + prepared["id"] + "/input.zip")
    with zipfile.ZipFile(source) as archive:
        if json.loads(archive.read("forest-project.json")) != selected:
            raise AppError("Le dossier préparé diffère de son contrat sauvegardé.")
    profile = settings["profiles"].get(prepared["target"])
    if profile is None:
        raise AppError("Le profil " + prepared["target"] + " n'est pas encore installé sur ROMEO.")
    search = search_settings(selected["contract"])
    advisor = advisor_settings(selected["contract"])
    provisioned = advisor_runtime({"advisor_runtime": profile.get("advisor_runtime", {})})
    if advisor["enabled"] and not provisioned:
        raise AppError("TabPFN doit être installé et ses poids vérifiés sur ROMEO avant activation.")
    pool = generator_pool(selected["contract"]) if selected["contract"].get("generator_pool") else []
    if search["algorithm"] == "ab-mcts-m" and "ab-mcts-m" not in profile.get("search_algorithms", []):
        raise AppError("AB-MCTS-M exige le profil optionnel sakana-m installé et déclaré sur ROMEO.")
    package = Path(__file__).resolve().parents[1]
    paths = [p for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    manifest = {
        "schema": "forest-app-launch-v1", "id": mission["id"], "session_id": mission["session_id"],
        "model": selected["model"], "effort": selected["reasoning_effort"],
        "search": search, "generator_pool": pool, "evolution": evolution_settings(selected["contract"]),
        "advisor": advisor, "advisor_runtime": provisioned if advisor["enabled"] else {},
        "target": prepared["target"], "input_sha256": file_digest(source),
        "architecture": profile["architecture"], "codex": profile["codex"],
        "duration_minutes": selected["contract"]["duration_minutes"],
        "allocation_seconds": selected["contract"]["duration_minutes"] * 60 + 1800,
        "engine_files": {"hpc_forest/" + p.relative_to(package).as_posix(): file_digest(p) for p in paths},
    }
    folder = contained(store.root, "missions/" + mission["id"])
    folder.mkdir(parents=True, exist_ok=True)
    atomic_json(folder / "launch.json", manifest)
    bundle = folder / "bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, "input.zip")
        archive.write(folder / "launch.json", "launch.json")
        for p in paths:
            archive.write(p, "engine/hpc_forest/" + p.relative_to(package).as_posix())
    return bundle, manifest


def job_arguments(mission: dict, settings: dict, launch: dict, bundle_sha: str) -> dict:
    quote = shlex.quote
    root = settings["base_dir"].rstrip("/") + "/forest-app-" + mission["id"]
    bundle = settings["base_dir"].rstrip("/") + "/forest-app-" + mission["id"] + ".zip"
    profile = settings["profiles"][launch["target"]]
    python = quote(profile["python"])
    extract = "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])"
    command = "\n".join([
        "set -eu", "umask 077",
        f"test ! -e {quote(root)}",
        f"printf '%s\\n' {quote(bundle_sha + '  ' + bundle)} | sha256sum -c -",
        f"mkdir -m 700 {quote(root)}",
        f"{python} -c {quote(extract)} {quote(bundle)} {quote(root)}",
        f"export PYTHONPATH={quote(root + '/engine')} PYTHONDONTWRITEBYTECODE=1",
        f"export CODEX_HOME={quote(settings['codex_home'])}",
        "export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1",
        "unset OPENAI_API_KEY CODEX_API_KEY FOREST_STUDY_BROKER",
        f"cd {quote(root)}",
        f"{python} -u -m hpc_forest.webapp.remote_runner {quote(root)}",
    ])
    seconds = launch["allocation_seconds"]
    return {"name": "fa-" + mission["id"][:20], "command": command,
            "arch": "x64cpu" if launch["target"] == "cpu" else "armgpu",
            "workdir": settings["base_dir"], "nodes": 1, "ntasks_per_node": 1,
            "cpus_per_task": 2, "gpus_per_node": int(launch["target"] == "gpu"),
            "mem_gb": 8, "time_limit": f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:00",
            "spack_packages": profile.get("spack_packages", [])}


def review_plan(plan: dict, arguments: dict) -> None:
    """Inspect the exact connector plan against this application's fixed resource contract."""
    resolved, script = plan.get("resolved", {}), plan.get("script", "")
    expected = {"arch": arguments["arch"], "workdir": arguments["workdir"],
                "total_cpus": arguments["cpus_per_task"], "total_gpus": arguments["gpus_per_node"],
                "time": arguments["time_limit"], "mem_gb": arguments["mem_gb"]}
    if (plan.get("submittable") is not True or not isinstance(script, str)
            or arguments["command"] not in script or any(resolved.get(k) != v for k, v in expected.items())
            or "#SBATCH --job-name=" + arguments["name"] + "\n" not in script):
        raise AppError("Le plan SLURM diffère de la mission demandée ; soumission refusée.")


class Missions:
    def __init__(self, store: Store, campaigns: Campaigns, *, connector=RomeoFiles):
        self.store, self.campaigns, self.connector = store, campaigns, connector
        self.settings_path = store.root / "romeo.json"
        self.wakeup = asyncio.Event()
        with store.connect() as db:
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_launch_per_prepared
                ON records(json_extract(payload,'$.prepared_id')) WHERE kind='mission'""")

    def settings(self):
        return connection(self.settings_path)

    def availability(self):
        try:
            value = self.settings()
            return {"configured": bool(value), "targets": list(value["profiles"]) if value else [],
                    "advisor_targets": [k for k, p in value["profiles"].items() if p.get("advisor_runtime")] if value else [],
                    "search_algorithms": {k: p.get("search_algorithms", []) for k, p in value["profiles"].items()}
                        if value else {},
                    "message": "Connecteur configuré ; OAuth est vérifié sur le nœud au lancement."
                    if value else "Configurer romeo.json dans le stockage de l'application."}
        except (ValueError, KeyError, OSError, AppError):
            return {"configured": False, "targets": [], "message": "Configuration ROMEO à vérifier."}

    def get(self, identifier):
        return self.store.get(identifier, "mission")

    def update(self, identifier, **changes):
        record = self.get(identifier)
        return self.store.update(identifier, {**self.store.payload(record), **changes}, kind="mission")

    def launch(self, prepared_id: str):
        for item in self.store.list("mission"):
            if item["prepared_id"] == prepared_id:
                return item
        settings = self.settings()
        if not settings:
            raise AppError("Configurez le connecteur ROMEO avant le lancement.")
        prepared = self.store.get(prepared_id, "prepared")
        if prepared["target"] not in settings["profiles"]:
            raise AppError("L'environnement pour cette cible n'est pas configuré.")
        require_identity(prepared["contract"])
        editable_files(prepared["contract"])
        executable(prepared["contract"]["contract"])
        try:
            record = self.store.create("mission", {
                "prepared_id": prepared_id, "project_id": prepared["project_id"], "name": prepared["name"],
                "session_id": uuid.uuid4().hex, "state": "staging", "target": prepared["target"],
                "model": prepared["contract"]["model"], "effort": prepared["contract"]["reasoning_effort"],
                "submitted": False, "attempts": 0, "last_error": None,
            })
        except sqlite3.IntegrityError:
            return next(m for m in self.store.list("mission") if m["prepared_id"] == prepared_id)
        self.wakeup.set()
        return record

    async def start(self, client, record, settings):
        identifier = record["id"]
        folder = contained(self.store.root, "missions/" + identifier)
        if not record.get("bundle_sha256"):
            bundle, manifest = freeze_bundle(self.store, record, settings)
            record = self.update(identifier, bundle_sha256=file_digest(bundle), launch=manifest,
                                 connection=settings, remote_root=settings["base_dir"] + "/forest-app-" + identifier)
        settings = record["connection"]
        if file_digest(folder / "bundle.zip") != record["bundle_sha256"]:
            raise AppError("Le moteur figé de la mission a changé.")
        if record["state"] == "staging":
            await client.upload(folder / "bundle.zip", record["remote_root"] + ".zip")
            arguments = job_arguments(record, settings, record["launch"], record["bundle_sha256"])
            plan = await client.call("job_prepare", **arguments)
            if not isinstance(plan.get("plan_id"), str):
                raise AppError("ROMEO n'a pas fourni de plan de soumission.")
            atomic_json(folder / "slurm-plan.json", plan)
            review_plan(plan, arguments)
            record = self.update(identifier, state="planned", plan_id=plan["plan_id"])
        if record["state"] == "planned":
            review_plan(json.loads((folder / "slurm-plan.json").read_text(encoding="utf8")),
                        job_arguments(record, settings, record["launch"], record["bundle_sha256"]))
            # Durable transition BEFORE the network write; an unknown outcome is never replayed.
            self.update(identifier, state="submitting")
            result = await client.call("job_submit", plan_id=record["plan_id"], confirm=True)
            job = str(result.get("job_id", ""))
            if not re.fullmatch(r"[0-9]+", job):
                raise AppError("Soumission incertaine : vérification du registre nécessaire.")
            self.update(identifier, job_id=job, state="queued", submitted=True, last_error=None,
                        submitted_at=time.time())

    async def reconcile(self, client, record):
        listing = await client.call("list_jobs", limit=100)
        matches = [v for v in listing.get("submitted_via_mcp", [])
                   if v.get("name") == "fa-" + record["id"][:20]]
        if len(matches) == 1 and re.fullmatch(r"\d+", str(matches[0].get("job_id", ""))):
            self.update(record["id"], state="queued", submitted=True,
                        job_id=str(matches[0]["job_id"]), last_error=None)
        else:
            self.update(record["id"], last_error="Soumission incertaine : aucun second job ne sera créé.",
                        uncertain_submission=True)

    def install_view(self, record, archive: Path):
        folder = archive.parent / ("view-" + uuid.uuid4().hex)
        folder.mkdir()
        extract_verified(archive, folder)
        _read(folder)
        campaign_id = record.get("campaign_id") or uuid.uuid4().hex
        payload = {"source_root": str(folder), "name": record["name"], "access": "read_only",
                   "mission_id": record["id"], "project_id": record["project_id"]}
        if record.get("campaign_id"):
            self.store.update(campaign_id, payload, kind="campaign")
        else:
            self.store.create("campaign", payload, campaign_id)
        view = self.campaigns.snapshot(campaign_id)
        self.update(record["id"], campaign_id=campaign_id, synced_at=time.time(),
                    speedup=view.get("speedup"), sync_error=None)
        return view

    async def refresh(self, client, record):
        scheduler = None
        try:
            scheduler = await client.call("job_status", job_id=record["job_id"])
            self.update(record["id"], scheduler=scheduler, observed_at=time.time())
        except Exception:
            # A scheduler read failure is not evidence that the job stopped.
            pass
        progress = None
        try:
            receipt = await client.call("read_remote_file", path=record["remote_root"] + "/progress.json",
                                        limit=1000, max_chars=40000)
            progress = json.loads(receipt["content"])
            if progress.get("job_id") != record["job_id"]:
                raise AppError("Le suivi distant appartient à un autre job.")
            self.update(record["id"], progress=progress,
                        state="collecting" if progress["state"] in {"completed", "failed"} else progress["state"],
                        last_error=progress.get("error"))
        except (ValueError, KeyError, OSError):
            raise
        except Exception:
            pass  # The file is absent while the allocation is queued or starting.
        if progress or (scheduler and scheduler.get("finished")):
            try:
                archive = contained(self.store.root, "missions/" + record["id"] + "/view.zip")
                await client.download(record["remote_root"] + "/view.zip", archive)
                current = self.get(record["id"])
                view = self.install_view(current, archive)
                if progress and progress.get("pipeline_complete") and view["downloads"]["code"]:
                    self.update(record["id"], state="completed", last_error=None, finished_at=time.time(),
                                recovery_pending=False)
                elif progress and progress["state"] == "failed":
                    self.update(record["id"], state="failed", finished_at=time.time(), recovery_pending=False)
            except Exception as exc:
                self.update(record["id"], sync_error=type(exc).__name__ + ": synchronisation à réessayer")
        if scheduler and scheduler.get("finished") and self.get(record["id"])["state"] not in TERMINAL:
            if not progress or progress.get("state") not in {"completed", "failed"}:
                self.update(record["id"], state="failed", recovery_pending=True,
                            last_error="Job terminé avant confirmation. Les preuves sont conservées.")
            elif progress.get("state") == "failed" and not self.get(record["id"]).get("campaign_id"):
                # Setup can fail before a registry exists. Keep retrying artifact collection separately.
                self.update(record["id"], state="failed", recovery_pending=True,
                            last_error=progress.get("error", "Préparation distante interrompue."))

    async def tick(self):
        pending = [r for r in self.store.list("mission") if (r["state"] not in TERMINAL or r.get("recovery_pending"))
                   and time.time() - r.get("last_attempt", 0) >= min(120, 15 * r.get("attempts", 0))]
        for record in pending:
            try:
                settings = record.get("connection") or self.settings()
                if not settings:
                    continue
                async with self.connector(Path(settings["codex_config"])) as client:
                    if record["state"] in {"staging", "planned"}:
                        await self.start(client, record, settings)
                    elif record["state"] == "submitting":
                        await self.reconcile(client, record)
                    else:
                        await self.refresh(client, record)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("ROMEO mission %s: %s", record["id"], type(exc).__name__)
                self.update(record["id"], last_error=str(exc)[:600],
                            attempts=record.get("attempts", 0) + 1, last_attempt=time.time())

    async def monitor(self):
        while True:
            self.wakeup.clear()
            await self.tick()
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=15)
            except TimeoutError:
                pass

