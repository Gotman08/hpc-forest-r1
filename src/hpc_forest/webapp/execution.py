"""Durable application-to-ROMEO orchestration through the existing MCP connector."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import shutil
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from hpc_forest.search.policy import settings as search_settings

from ..codex_worker import RomeoFiles
from ..core import FileLock, ForestError, InfrastructureError, atomic_json, file_digest
from ..dsh_romeo import required as needs_dsh
from ..dsh_romeo import validate_remote as validate_dsh
from ..evolution_archive import settings as evolution_settings
from ..execution_validation import requirements as execution_requirements
from ..model_policy import generator_pool, require_identity
from .campaigns import Campaigns, _read
from .paths import AppError, contained, filesystem_path
from .projects import validate_contract
from .runner_support import editable_files, executable, extract_verified
from .store import Store

LOGGER = logging.getLogger(__name__)
TERMINAL = {"completed", "failed", "cancelled", "recovery_required"}


def public_mission(record: dict) -> dict:
    result = {k: v for k, v in record.items() if k not in {
        "connection", "launch", "remote_root", "plan_id", "bundle_sha256", "session_id"}}
    launch = record.get("launch") or {}
    try:
        result["execution_validation"] = execution_requirements(launch.get("execution_validation"))
    except ForestError:
        result["execution_validation"] = None
        result["execution_validation_error"] = "Contrat de validation enregistré invalide."
    return result


def dsh_connection(settings: dict, contract: dict) -> dict:
    if not needs_dsh(contract):
        return {}
    try:
        value = validate_dsh(settings.get("dsh_romeo"))
    except InfrastructureError as exc:
        raise AppError(str(exc)) from exc
    return {"dsh_romeo": value}


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
    validate_contract(selected["contract"])
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
    if "advisor_runtime" in profile:
        raise AppError("Le profil ROMEO contient advisor_runtime, retiré avec TabPFN. "
                       "Sauvegardez romeo.json puis retirez ce réglage pour les nouvelles missions.")
    pool = generator_pool(selected["contract"]) if selected["contract"].get("generator_pool") else []
    if search["algorithm"] == "ab-mcts-m" and "ab-mcts-m" not in profile.get("search_algorithms", []):
        raise AppError("AB-MCTS-M exige le profil optionnel sakana-m installé et déclaré sur ROMEO.")
    package = Path(__file__).resolve().parents[1]
    paths = [p for p in package.rglob("*") if p.is_file() and not p.is_symlink()
             and "__pycache__" not in p.parts and (p.suffix in {".py", ".js", ".mjs", ".html", ".css", ".svg"}
                                                   or "assets" in p.relative_to(package).parts)]
    manifest = {
        "schema": "forest-app-launch-v1", "id": mission["id"], "session_id": mission["session_id"],
        "operator_control": "drain_then_confirm-v1",
        "model": selected["model"], "effort": selected["reasoning_effort"],
        "search": search, "generator_pool": pool, "evolution": evolution_settings(selected["contract"]),
        "target": prepared["target"], "input_sha256": file_digest(source),
        "architecture": profile["architecture"], "codex": profile["codex"],
        "duration_minutes": selected["contract"]["duration_minutes"],
        "allocation_seconds": selected["contract"]["duration_minutes"] * 60 + 1800,
        "engine_files": {"hpc_forest/" + p.relative_to(package).as_posix(): file_digest(p) for p in paths},
        **dsh_connection(settings, selected["contract"]),
    }
    if selected["contract"].get("execution_validation"):
        manifest["execution_validation"] = selected["contract"]["execution_validation"]
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
        "unset OPENAI_API_KEY CODEX_API_KEY OPENAI_BASE_URL OPENAI_API_BASE "
        "ROMEO_LLM_KEY DSH_ROMEO_BASE_URL FOREST_STUDY_BROKER",
        f"cd {quote(root)}",
        f"{python} -u -m hpc_forest.webapp.remote_runner {quote(root)}",
    ])
    seconds = launch["allocation_seconds"]
    resources = launch.get("execution_validation") or {}
    return {"name": "fa-" + mission["id"][:20], "command": command,
            "arch": "x64cpu" if launch["target"] == "cpu" else "armgpu",
            "workdir": settings["base_dir"], "nodes": 1, "ntasks_per_node": 1,
            "cpus_per_task": resources.get("cpus_per_task", 2), "gpus_per_node": int(launch["target"] == "gpu"),
            "mem_gb": 8, "time_limit": f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:00",
            "spack_packages": profile.get("spack_packages", [])}


def _slurm_seconds(value: object) -> int | None:
    """Compare generated HH:MM:SS with SLURM's normalized D-HH:MM:SS."""
    if not isinstance(value, str) or len(value) > 32:
        return None
    match = re.fullmatch(r"(?:(\d+)-)?(\d+):([0-5]\d):([0-5]\d)", value)
    if match is None:
        return None
    days, hours, minutes, seconds = match.groups()
    return int(days or 0) * 86400 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def review_plan(plan: dict, arguments: dict) -> None:
    """Inspect the exact connector plan against this application's fixed resource contract."""
    resolved, script = plan.get("resolved", {}), plan.get("script", "")
    expected = {"arch": arguments["arch"], "workdir": arguments["workdir"],
                "total_cpus": arguments["cpus_per_task"], "total_gpus": arguments["gpus_per_node"],
                "mem_gb": arguments["mem_gb"]}
    duration = _slurm_seconds(arguments["time_limit"])
    if (plan.get("submittable") is not True or not isinstance(script, str)
            or duration is None or _slurm_seconds(resolved.get("time")) != duration
            or arguments["command"] not in script or any(resolved.get(k) != v for k, v in expected.items())
            or "#SBATCH --job-name=" + arguments["name"] + "\n" not in script):
        raise AppError("Le plan SLURM diffère de la mission demandée ; soumission refusée.")


class Missions:
    def __init__(self, store: Store, campaigns: Campaigns, *, connector=RomeoFiles):
        self.store, self.campaigns, self.connector = store, campaigns, connector
        self.settings_path = store.root / "romeo.json"
        self.wakeup, self.loop = asyncio.Event(), None
        with store.connect() as db:
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_launch_per_prepared
                ON records(json_extract(payload,'$.prepared_id')) WHERE kind='mission'""")

    def settings(self):
        return connection(self.settings_path)

    def wake(self):
        """Wake the monitor from any thread; asyncio.Event itself is not thread-safe."""
        loop = self.loop
        if loop is None or loop.is_closed():
            self.wakeup.set()
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self.wakeup.set()
            return
        try:
            loop.call_soon_threadsafe(self.wakeup.set)
        except RuntimeError:
            pass  # The monitor stopped; its next start reads the durable state anyway.

    def availability(self):
        try:
            value = self.settings()
            dsh = False
            if value and "dsh_romeo" in value:
                try:
                    validate_dsh(value["dsh_romeo"])
                    dsh = True
                except InfrastructureError:
                    pass
            return {"configured": bool(value), "targets": list(value["profiles"]) if value else [],
                    "dsh_romeo_configured": dsh,
                    "search_algorithms": {k: p.get("search_algorithms", []) for k, p in value["profiles"].items()}
                        if value else {},
                    "message": "Connecteur configuré ; l'accès au fournisseur choisi est vérifié sur le nœud au lancement."
                    if value else "Configurer romeo.json dans le stockage de l'application."}
        except (ValueError, KeyError, OSError, AppError):
            return {"configured": False, "targets": [], "message": "Configuration ROMEO à vérifier."}

    def get(self, identifier):
        return self.store.get(identifier, "mission")

    def request_stop(self, identifier):
        def stop(payload):
            if payload["state"] in TERMINAL:
                return payload
            if payload["state"] in {"staging", "planned"}:
                payload.update(state="cancelled", finished_at=time.time())
            elif not payload.get("launch", {}).get("operator_control"):
                raise AppError("Cette mission utilise un moteur historique sans arrêt propre. "
                               "Son job doit être géré explicitement sur ROMEO.")
            payload.setdefault("stop_requested_at", time.time())
            return payload
        result = self.store.mutate(identifier, stop, kind="mission")
        self.wake()
        return result

    async def deliver_stop(self, client, record):
        if not record.get("stop_requested_at") or record.get("stop_delivered_at"):
            return
        path = contained(self.store.root, "missions/" + record["id"] + "/stop-request.json")
        atomic_json(path, {"schema": "forest-operator-stop-v1", "mission_id": record["id"],
                          "session_id": record["session_id"], "requested_at": record["stop_requested_at"]})
        await client.upload(path, record["remote_root"] + "/stop-request.json")
        self.update(record["id"], stop_delivered_at=time.time())

    def resume_tracking(self, identifier):
        def resume(payload):
            if payload["state"] not in {"recovery_required", "failed"}:
                return payload
            if not payload.get("remote_root") or not payload.get("connection"):
                raise AppError("Aucune identité distante à réconcilier. Préparez une nouvelle mission ; "
                               "cette sauvegarde reste conservée.")
            payload.update(state="queued" if payload.get("job_id") else "submitting",
                           recovery_pending=False, attempts=0, last_attempt=0, last_error=None)
            return payload
        result = self.store.mutate(identifier, resume, kind="mission")
        self.wake()
        return result

    def update(self, identifier, **changes):
        return self.store.mutate(identifier, lambda payload: {**payload, **changes}, kind="mission")

    def launch(self, prepared_id: str):
        existing = self.store.find("mission", "prepared_id", prepared_id)
        if existing:
            return existing
        settings = self.settings()
        if not settings:
            raise AppError("Configurez le connecteur ROMEO avant le lancement.")
        prepared = self.store.get(prepared_id, "prepared")
        validate_contract(prepared["contract"]["contract"])
        if prepared["target"] not in settings["profiles"]:
            raise AppError("L'environnement pour cette cible n'est pas configuré.")
        if "advisor_runtime" in settings["profiles"][prepared["target"]]:
            raise AppError("Le profil ROMEO contient advisor_runtime, retiré avec TabPFN. "
                           "Sauvegardez romeo.json puis retirez ce réglage pour les nouvelles missions.")
        require_identity(prepared["contract"])
        dsh_connection(settings, prepared["contract"]["contract"])
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
            existing = self.store.find("mission", "prepared_id", prepared_id)
            if existing:
                return existing
            raise
        self.wake()
        return record

    async def start(self, client, record, settings):
        folder = contained(self.store.root, "missions/" + record["id"])
        with FileLock(folder / "dispatch.lock"):
            record = self.get(record["id"])
            if record["state"] not in {"staging", "planned"}:
                return
            await self._start_locked(client, record, settings)

    async def _start_locked(self, client, record, settings):
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
            if not self.store.transition(identifier, "staging", {"state": "planned", "plan_id": plan["plan_id"]}, kind="mission"):
                return
            record = self.get(identifier)
        if record["state"] == "planned":
            review_plan(json.loads((folder / "slurm-plan.json").read_text(encoding="utf8")),
                        job_arguments(record, settings, record["launch"], record["bundle_sha256"]))
            # Durable transition BEFORE the network write; an unknown outcome is never replayed.
            if not self.store.transition(identifier, "planned", {"state": "submitting"}, kind="mission"):
                return
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
        """Install a downloaded view once, keeping only the current copy and its predecessor."""
        digest = file_digest(archive)
        if digest == record.get("view_sha256") and record.get("campaign_id"):
            try:
                view = self.campaigns.snapshot(record["campaign_id"])
            except AppError:
                view = None  # The installed copy is no longer readable: install it again.
            if view is not None:
                self.update(record["id"], synced_at=time.time(), speedup=view.get("speedup"), sync_error=None)
                return view
        folder = filesystem_path(archive.parent / ("view-" + uuid.uuid4().hex))
        folder.mkdir()
        try:
            extract_verified(archive, folder)
            _read(folder)
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT payload FROM records WHERE id=? AND kind='mission'", (record["id"],)).fetchone()
                if row is None:
                    raise AppError("Mission introuvable.")
                current = json.loads(row["payload"])
                campaign_id = current.get("campaign_id") or uuid.uuid4().hex
                previous = db.execute("SELECT payload FROM records WHERE id=? AND kind='campaign'",
                                      (campaign_id,)).fetchone()
                payload = {"source_root": str(folder), "name": current["name"], "access": "read_only",
                           "mission_id": record["id"], "project_id": current["project_id"]}
                now = time.time()
                db.execute("INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                           "payload=excluded.payload,updated=excluded.updated",
                           (campaign_id, "campaign", now, now, json.dumps(payload)))
                current.update(campaign_id=campaign_id, synced_at=now)
                db.execute("UPDATE records SET payload=?,updated=? WHERE id=?",
                           (json.dumps(current), now, record["id"]))
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)  # Never referenced: the transaction rolled back.
            raise
        # The predecessor survives one more synchronization so a download served from it can finish.
        keep = {folder.name} | ({Path(json.loads(previous["payload"])["source_root"]).name} if previous else set())
        for stale in folder.parent.glob("view-*"):
            if stale.name not in keep and stale.is_dir():
                shutil.rmtree(stale, ignore_errors=True)  # Retried at the next installation.
        view = self.campaigns.snapshot(campaign_id)
        self.update(record["id"], campaign_id=campaign_id, synced_at=time.time(),
                    speedup=view.get("speedup"), sync_error=None, view_sha256=digest)
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
                # Extraction and hashing take seconds: keep the API responsive meanwhile.
                view = await asyncio.to_thread(self.install_view, current, archive)
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
                        # A queued job may not have extracted its directory yet. Keep
                        # monitoring it even while delivery of the stop file fails.
                        try:
                            await self.deliver_stop(client, record)
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self.update(record["id"], stop_delivery_error=type(exc).__name__ +
                                        ": arrêt en attente de transmission ; suivi maintenu.")
                        await self.refresh(client, record)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("ROMEO mission %s: %s", record["id"], type(exc).__name__)
                self.update(record["id"], last_error=str(exc)[:600] if isinstance(exc, AppError)
                            else type(exc).__name__ + ": connexion ROMEO à réessayer ; aucune nouvelle soumission implicite.",
                            attempts=record.get("attempts", 0) + 1, last_attempt=time.time())

    async def monitor(self):
        self.loop = asyncio.get_running_loop()
        while True:
            self.wakeup.clear()
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # A locked database or a full disk must not end tracking for the whole session.
                LOGGER.warning("Mission monitor: %s; retrying", type(exc).__name__)
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=15)
            except TimeoutError:
                pass

