"""Loopback HTTP API for the first application slice, with no implicit execution."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile

from .. import __version__
from ..core import FileLock
from ..model_policy import EFFORT, MODEL, catalog
from .campaigns import Campaigns
from .execution import Missions, public_mission
from .paths import MAX_FILE, MAX_FILES, MAX_UPLOAD, AppError, contained
from .projects import Projects, project_view
from .store import Store

LOGGER = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


class BodyTooLarge(Exception):
    pass


class LocalBoundary:
    """Reject cross-site writes, DNS rebinding and unbounded request bodies."""
    def __init__(self, app, allowed_hosts: set[str]):
        self.app, self.allowed_hosts = app, allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        try:
            hostname = urlsplit("//" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in self.allowed_hosts:
            return await JSONResponse({"error": "Hôte non autorisé."}, 403)(scope, receive, send)
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get(b"origin")
            if (headers.get(b"x-forest-request") != b"1"
                    or (origin is not None and origin.decode("latin1") not in {
                        "http://" + host, "https://" + host})):
                return await JSONResponse(
                    {"error": "Ouvrez l'application pour effectuer cette action."}, 403
                )(scope, receive, send)
        maximum = MAX_UPLOAD + 2 * 1024 * 1024
        if b"application/json" in headers.get(b"content-type", b""):
            maximum = 1024 * 1024
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = -1
        if declared < 0 or declared > maximum:
            return await JSONResponse({"error": "Requête trop volumineuse."}, 413)(scope, receive, send)
        received, started = 0, False

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > maximum:
                raise BodyTooLarge()
            return message

        async def protected_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"same-origin"),
                    (b"cache-control", b"no-store"),
                    (b"content-security-policy",
                     b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                     b"img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                     b"base-uri 'none'; form-action 'self'"),
                ]
            await send(message)

        try:
            await self.app(scope, bounded_receive, protected_send)
        except BodyTooLarge:
            if not started:
                await JSONResponse({"error": "Requête trop volumineuse."}, 413)(scope, receive, send)
            else:
                raise


def create_app(data_dir: Path, campaign_roots: list[Path] | None = None,
               *, allowed_hosts: set[str] | None = None) -> FastAPI:
    store = Store(data_dir)
    projects, campaigns = Projects(store), Campaigns(store)
    for root in campaign_roots or []:
        campaigns.register(root)
    missions = Missions(store, campaigns)

    @asynccontextmanager
    async def lifespan(_app):
        with FileLock(store.root / "application.lock"):
            task = asyncio.create_task(missions.monitor())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Forest - espace de travail", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.store, app.state.projects, app.state.campaigns = store, projects, campaigns
    app.state.missions = missions
    app.add_middleware(LocalBoundary, allowed_hosts=allowed_hosts or {"127.0.0.1", "localhost", "::1"})

    @app.exception_handler(AppError)
    async def application_error(_request, exc):
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.exception_handler(OSError)
    async def storage_error(_request, exc):
        LOGGER.warning("Application storage failure: %s", type(exc).__name__)
        return JSONResponse({"error": "Un fichier n'est plus accessible. Réessayez ou consultez les journaux."},
                            status_code=503)

    @app.get("/api/info")
    def info():
        return {
            "version": __version__, "model": MODEL, "effort": EFFORT, "models": catalog(), "execution_target": "ROMEO",
            "mode": "local", "submission_enabled": missions.availability()["configured"],
            "connection": missions.availability(),
            "submission_message": missions.availability()["message"],
            "capabilities": ["project_import", "contract", "prepared_bundle",
                             "campaign_read", "source_diff", "confirmed_download"],
            "limits": {"upload_bytes": MAX_UPLOAD, "file_count": MAX_FILES},
        }

    @app.get("/api/projects")
    def list_projects():
        return [project_view(record) for record in store.list("project")]

    @app.post("/api/projects", status_code=201)
    async def import_project(request: Request):
        async with request.form(max_files=MAX_FILES, max_fields=8) as form:
            uploads = form.getlist("files")
            if not uploads or any(not isinstance(file, UploadFile) for file in uploads):
                raise AppError("Ajoutez les fichiers du projet.")
            try:
                paths = json.loads(form.get("paths", "null"))
            except (ValueError, TypeError) as exc:
                raise AppError("Liste de chemins invalide.") from exc
            if paths is not None and (not isinstance(paths, list) or len(paths) != len(uploads)
                                      or any(not isinstance(path, str) for path in paths)):
                raise AppError("Les chemins ne correspondent pas aux fichiers.")
            values, total = [], 0
            for index, upload in enumerate(uploads):
                value = await upload.read(MAX_UPLOAD + 1)
                total += len(value)
                if total > MAX_UPLOAD:
                    raise AppError("Le dépôt dépasse 64 Mio.")
                values.append((paths[index] if paths is not None else upload.filename or "", value))
            name = form.get("name") or Path(uploads[0].filename or "Projet").stem
            if not isinstance(name, str):
                raise AppError("Nom de projet invalide.")
            return projects.import_files(name, values)

    @app.get("/api/projects/{identifier}")
    def get_project(identifier: str):
        return project_view(store.get(identifier, "project"))

    @app.put("/api/projects/{identifier}/contract")
    async def save_contract(identifier: str, request: Request):
        try:
            value = await request.json()
        except ValueError as exc:
            raise AppError("Le contrat doit être un document JSON.") from exc
        return projects.update(identifier, value)

    @app.post("/api/projects/{identifier}/attachments")
    async def attach_document(identifier: str, request: Request):
        async with request.form(max_files=1, max_fields=2) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile):
                raise AppError("Ajoutez un document.")
            return projects.attach(identifier, form.get("role", ""), file.filename or "",
                                   await file.read(MAX_FILE + 1))

    @app.post("/api/projects/{identifier}/prepare", status_code=201)
    def prepare_mission(identifier: str):
        return projects.prepare(identifier)

    @app.post("/api/projects/{identifier}/migrate", status_code=201)
    def migrate_project(identifier: str):
        return projects.migrate(identifier)

    @app.get("/api/prepared/{identifier}")
    def get_prepared(identifier: str):
        return store.get(identifier, "prepared")

    @app.post("/api/prepared/{identifier}/launch", status_code=202)
    async def launch_mission(identifier: str):
        return public_mission(missions.launch(identifier))

    @app.get("/api/missions")
    def list_missions():
        return [public_mission(r) for r in store.list("mission")]

    @app.get("/api/missions/{identifier}")
    def mission_status(identifier: str):
        return public_mission(missions.get(identifier))

    @app.post("/api/missions/{identifier}/stop", status_code=202)
    def stop_mission(identifier: str):
        return public_mission(missions.request_stop(identifier))

    @app.post("/api/missions/{identifier}/resume-tracking", status_code=202)
    def resume_tracking(identifier: str):
        return public_mission(missions.resume_tracking(identifier))

    @app.get("/api/prepared/{identifier}/download")
    def prepared_download(identifier: str):
        store.get(identifier, "prepared")
        return FileResponse(contained(store.root, f"prepared/{identifier}/input.zip"),
                            media_type="application/zip", filename="mission-romeo.zip")

    @app.get("/api/campaigns")
    def list_campaigns():
        return campaigns.list()

    @app.get("/api/campaigns/{identifier}")
    def get_campaign(identifier: str):
        return campaigns.snapshot(identifier)

    @app.get("/api/campaigns/{identifier}/trials/{trial_id}")
    def get_trial(identifier: str, trial_id: str):
        return campaigns.trial(identifier, trial_id)

    @app.get("/api/campaigns/{identifier}/trials/{trial_id}/source")
    def get_source(identifier: str, trial_id: str, path: str):
        return campaigns.source(identifier, trial_id, path)

    @app.get("/api/campaigns/{identifier}/download/{kind}")
    def download(identifier: str, kind: str):
        if kind == "csv":
            return Response(campaigns.csv(identifier), media_type="text/csv; charset=utf-8",
                            headers={"Content-Disposition": 'attachment; filename="mesures.csv"'})
        file = campaigns.download(identifier, kind)
        return FileResponse(file, filename="projet-confirme.zip" if kind == "code" else "rapport.md",
                            media_type="application/zip" if kind == "code" else "text/markdown")

    @app.get("/api/history")
    def history():
        running = store.list("mission")
        launched = {r["prepared_id"] for r in running}
        records = [r for r in campaigns.list() if not r.get("mission_id")] + [public_mission(r) for r in running]
        records += [r for r in store.list("prepared") if r["id"] not in launched]
        records += [{"id": p["id"], "name": p["name"], "kind": "project",
                     "state": project_view(p)["state"], "created": p["created"],
                     "updated": p["updated"], "target": p["contract"]["target"]}
                    for p in store.list("project")]
        return sorted(records, key=lambda r: r.get("updated", r["created"]), reverse=True)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    app.mount("/assets", StaticFiles(directory=STATIC), name="assets")
    return app
