"""Import projects as data; never execute uploaded build or test commands."""
from __future__ import annotations

import hashlib
import io
import json
import re
import shlex
import shutil
import stat
import uuid
import zipfile
from pathlib import Path

from ..advisor import settings as advisor_settings
from ..core import ForestError, InfrastructureError
from ..evolution_archive import settings as evolution_settings
from ..model_policy import EFFORT, MODEL, generator_pool, require_identity
from ..search_policy import settings as search_settings
from .paths import (
    MAX_EXPANDED,
    MAX_FILE,
    MAX_FILES,
    MAX_UPLOAD,
    AppError,
    contained,
    regular_zip_entry,
    relative_name,
)
from .store import Store

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cu", ".cuh"}
CONTRACT_FIELDS = {
    "build_command", "test_command", "benchmark_command", "expected_result",
    "editable_paths", "target", "duration_minutes", "statement",
    "model", "reasoning_effort", "search", "generator_pool", "evolution", "advisor",
}


def unpack(files: list[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], int]:
    if not files or len(files) > MAX_FILES:
        raise AppError(f"Importez entre 1 et {MAX_FILES} fichiers.")
    if sum(len(data) for _, data in files) > MAX_UPLOAD:
        raise AppError("Le dépôt dépasse la limite de 64 Mio.")
    if len(files) == 1 and files[0][0].lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(files[0][1])) as archive:
                members = archive.infolist()
                if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_EXPANDED:
                    raise AppError("L'archive décompressée dépasse les limites du projet.")
                unpacked = []
                for member in members:
                    mode = member.external_attr >> 16
                    if not regular_zip_entry(mode) or member.flag_bits & 1:
                        raise AppError("Les archives chiffrées ou contenant des liens sont refusées.")
                    if member.is_dir() or stat.S_ISDIR(mode):
                        directory = member.filename.replace("\\", "/").rstrip("/")
                        if not any(part.casefold() in IGNORED for part in directory.split("/")):
                            relative_name(directory)
                        continue
                    if member.file_size > MAX_FILE:
                        raise AppError("Un fichier de l'archive dépasse 32 Mio.")
                    with archive.open(member) as stream:
                        data = stream.read(MAX_FILE + 1)
                    if len(data) > MAX_FILE:
                        raise AppError("Un fichier décompressé dépasse 32 Mio.")
                    unpacked.append((member.filename, data))
                files = unpacked
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise AppError("Archive ZIP illisible ou non prise en charge.") from exc
    normalized, seen, ignored = [], set(), 0
    total = 0
    for name, data in files:
        if any(part.casefold() in IGNORED for part in name.replace("\\", "/").split("/")):
            ignored += 1
            continue
        name = relative_name(name)
        if len(data) > MAX_FILE:
            raise AppError("Un fichier dépasse la limite de 32 Mio.")
        total += len(data)
        if total > MAX_EXPANDED:
            raise AppError("Le projet décompressé dépasse 256 Mio.")
        if name.casefold() in seen:
            raise AppError("Deux fichiers ont le même nom, y compris après changement de casse.")
        seen.add(name.casefold())
        normalized.append((name, data))
    if not normalized:
        raise AppError("Aucun fichier de projet exploitable dans le dépôt.")
    # Unwrap the directory selected by a browser, or a ZIP's enclosing project folder.
    first = {name.split("/")[0] for name, _ in normalized}
    if (len(first) == 1 and all("/" in name for name, _ in normalized)
            and next(iter(first)).casefold() not in {"src", "include", "tests", "data", "validation"}):
        normalized = [(name.split("/", 1)[1], data) for name, data in normalized]
    # A file cannot also serve as the parent directory of another file.
    names = {name.casefold() for name, _ in normalized}
    for name in names:
        if any("/".join(name.split("/")[:i]) in names for i in range(1, len(name.split("/")))):
            raise AppError("Conflit entre un fichier et un dossier dans le projet.")
    return normalized, ignored


def infer_contract(files: list[tuple[str, bytes]]) -> dict:
    lookup = {name: data.decode("utf-8", errors="replace")[:200000]
              for name, data in files if Path(name).name in {"CMakeLists.txt", "Makefile"}}
    build, test = "", ""
    if "CMakeLists.txt" in lookup:
        build = "cmake -S . -B build\ncmake --build build"
        if any(re.search(r"\badd_test\s*\(", text, re.I) for text in lookup.values()):
            test = "ctest --test-dir build --output-on-failure --no-tests=error"
    elif "Makefile" in lookup:
        build = "make"
        if re.search(r"(?m)^test\s*:", lookup["Makefile"]):
            test = "make test"
    source = [name for name, _ in files if Path(name).suffix.lower() in SOURCE_SUFFIXES]
    editable = ["src/"] if any(name.startswith("src/") for name in source) else source[:100]
    return {
        "build_command": build, "test_command": test, "benchmark_command": "",
        "expected_result": "", "editable_paths": editable, "target": "cpu",
        "duration_minutes": 120, "statement": "",
        "model": MODEL, "reasoning_effort": EFFORT,
        "search": search_settings({}), "generator_pool": [],
        "evolution": evolution_settings({"evolution": {"enabled": True}}),
        "advisor": advisor_settings({}),
    }


def validate_contract(value: dict) -> dict:
    if isinstance(value, dict):
        value = {"model": MODEL, "reasoning_effort": EFFORT, "search": {}, "generator_pool": [], "evolution": {}, "advisor": {}, **value}
    if not isinstance(value, dict) or set(value) != CONTRACT_FIELDS:
        raise AppError("Le contrat contient des champs manquants ou non reconnus.")
    try:
        require_identity(value)
        pool = generator_pool(value)
        value = {**value, "search": search_settings(value),
                 "advisor": advisor_settings(value),
                 "evolution": evolution_settings(value),
                 "generator_pool": pool if value["generator_pool"] else []}
    except InfrastructureError as exc:
        raise AppError("Choisissez un modèle et un effort compatibles.") from exc
    except ForestError as exc:
        raise AppError("Paramètres de recherche invalides : " + str(exc)) from exc
    for key in ("build_command", "test_command", "benchmark_command", "expected_result", "statement"):
        if not isinstance(value[key], str) or len(value[key]) > (30000 if key == "statement" else 6000):
            raise AppError("Un champ du contrat est invalide ou trop long.")
    for key in ("build_command", "test_command", "benchmark_command"):
        try:
            for line in value[key].splitlines():
                if line.strip():
                    shlex.split(line)
        except ValueError as exc:
            raise AppError("Une commande contient des guillemets non fermés.") from exc
    minutes = value["duration_minutes"]
    if type(minutes) is not int or not 1 <= minutes <= 1440:
        raise AppError("La durée doit être comprise entre 1 et 1 440 minutes.")
    if not isinstance(value["target"], str) or value["target"] not in {"cpu", "gpu"}:
        raise AppError("Choisissez une cible CPU ou GPU sur ROMEO.")
    paths = value["editable_paths"]
    if not isinstance(paths, list) or len(paths) > 100:
        raise AppError("Le périmètre modifiable doit être une liste de chemins.")
    normalized = []
    for path in paths:
        if not isinstance(path, str):
            raise AppError("Chemin modifiable invalide.")
        path = relative_name(path.replace("\\", "/").rstrip("/"))
        if any(part.casefold() in {"test", "tests", "validation"} for part in path.split("/")):
            raise AppError("Les tests de référence doivent rester protégés.")
        normalized.append(path)
    return {key: val.strip() if isinstance(val, str) else val for key, val in
            {**value, "editable_paths": list(dict.fromkeys(normalized))}.items()}


def missing_fields(contract: dict, inventory: list[dict]) -> list[dict]:
    labels = {
        "build_command": "Commande de compilation",
        "test_command": "Commande de vérification",
        "benchmark_command": "Commande à mesurer",
        "expected_result": "Résultat attendu et critère de correction",
        "editable_paths": "Périmètre modifiable",
    }
    missing = [{"field": key, "label": label} for key, label in labels.items() if not contract[key]]
    if not any(Path(item["path"]).suffix.lower() in SOURCE_SUFFIXES for item in inventory):
        missing.append({"field": "source", "label": "Code C, C++ ou CUDA"})
    for name in contract["editable_paths"]:
        prefix = name.rstrip("/")
        if not any(item["path"] == prefix or item["path"].startswith(prefix + "/")
                   for item in inventory):
            missing.append({"field": "editable_paths", "label": f"Chemin absent : {name}"})
    return missing


def project_view(record: dict) -> dict:
    record = {**record, "contract": {"model": MODEL, "reasoning_effort": EFFORT,
                                    "search": search_settings({}), "generator_pool": [],
                                    "evolution": evolution_settings({}), **record["contract"]}}
    missing = missing_fields(record["contract"], record["files"])
    return {**record, "missing": missing, "ready": not missing,
            "model": record["contract"]["model"], "effort": record["contract"]["reasoning_effort"],
            "state": "needs_input" if missing else "ready"}


class Projects:
    def __init__(self, store: Store):
        self.store = store

    def _discard_created(self, folder: Path) -> None:
        """Remove only this operation's UUID directory within the application store."""
        verified = contained(self.store.root, folder.relative_to(self.store.root).as_posix())
        if verified.resolve() == self.store.root.resolve():
            raise AppError("Le dossier de l'application ne peut pas être supprimé.")
        shutil.rmtree(verified)

    def import_files(self, name: str, uploads: list[tuple[str, bytes]]) -> dict:
        if not name.strip() or len(name.strip()) > 100:
            raise AppError("Donnez au projet un nom de 1 à 100 caractères.")
        files, ignored = unpack(uploads)
        identifier = uuid.uuid4().hex
        root = contained(self.store.root, f"projects/{identifier}")
        root.mkdir(parents=True)
        inventory = []
        try:
            for relative, content in files:
                destination = contained(root / "source", relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                inventory.append({"path": relative, "bytes": len(content),
                                  "sha256": hashlib.sha256(content).hexdigest()})
            inventory.sort(key=lambda item: item["path"])
            record = self.store.create("project", {
                "name": name.strip(), "files": inventory, "ignored_files": ignored,
                "total_bytes": sum(item["bytes"] for item in inventory),
                "contract": infer_contract(files), "attachments": [],
                "language": "CUDA" if any(n.endswith((".cu", ".cuh")) for n, _ in files) else
                    "C / C++" if any(Path(n).suffix in SOURCE_SUFFIXES for n, _ in files) else "À préciser",
            }, identifier)
        except Exception:
            # This UUID folder was created by this operation, never an imported user directory.
            self._discard_created(root)
            raise
        return project_view(record)

    def update(self, identifier: str, contract: dict) -> dict:
        record = self.store.get(identifier, "project")
        payload = self.store.payload(record)
        payload["contract"] = validate_contract(contract)
        return project_view(self.store.update(identifier, payload, kind="project"))

    def attach(self, identifier: str, role: str, filename: str, data: bytes) -> dict:
        if role not in {"statement", "test_data"} or not data or len(data) > MAX_FILE:
            raise AppError("Document vide, trop volumineux ou de type inconnu.")
        name = relative_name(filename)
        if "/" in name:
            raise AppError("Le document doit avoir un nom de fichier simple.")
        record = self.store.get(identifier, "project")
        folder = contained(self.store.root, f"projects/{identifier}/attachments")
        folder.mkdir(exist_ok=True)
        stored = uuid.uuid4().hex + Path(name).suffix.lower()
        (folder / stored).write_bytes(data)
        payload = self.store.payload(record)
        payload["attachments"].append({"name": name, "role": role, "stored": stored,
                                       "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return project_view(self.store.update(identifier, payload, kind="project"))

    def prepare(self, identifier: str) -> dict:
        project = project_view(self.store.get(identifier, "project"))
        if not project["ready"]:
            raise AppError("Complétez le contrat de vérification avant de préparer la mission.")
        mission_id = uuid.uuid4().hex
        folder = contained(self.store.root, f"prepared/{mission_id}")
        folder.mkdir(parents=True)
        contract = {
            "schema": "forest-app-project-v1", "mission_id": mission_id,
            "name": project["name"], "model": project["model"], "reasoning_effort": project["effort"],
            "execution": "ROMEO", "memory": "fresh", "submitted": False,
            "verification": "not_run", "contract": project["contract"],
            "files": project["files"], "attachments": project["attachments"],
        }
        source = contained(self.store.root, f"projects/{identifier}")
        try:
            with zipfile.ZipFile(folder / "input.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("forest-project.json", json.dumps(contract, ensure_ascii=False, indent=2))
                archive.writestr("README.md", "# Mission préparée\n\n"
                    "Ce dossier contient le code initial et un contrat, pas un résultat optimisé.\n"
                    "Aucun job ROMEO n'a été soumis et aucune vérification n'a été exécutée.\n"
                    "Le connecteur de soumission et le profil d'évaluation devront être configurés "
                    "avant une exécution.\n")
                for item in project["files"]:
                    path = contained(source / "source", item["path"])
                    data = path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != item["sha256"]:
                        raise AppError("Le projet sauvegardé a changé ; importez une nouvelle copie.")
                    archive.writestr("source/" + item["path"], data)
                for item in project["attachments"]:
                    data = contained(source / "attachments", item["stored"]).read_bytes()
                    if hashlib.sha256(data).hexdigest() != item["sha256"]:
                        raise AppError("Un document sauvegardé a changé.")
                    archive.writestr("attachments/" + item["stored"], data)
            return self.store.create("prepared", {
                "name": project["name"], "project_id": identifier, "state": "prepared",
                "contract": contract, "target": project["contract"]["target"],
                "submitted": False,
            }, mission_id)
        except Exception:
            self._discard_created(folder)
            raise
