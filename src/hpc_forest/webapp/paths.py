"""Bounded, portable paths for user-supplied projects and evidence files."""
from __future__ import annotations

import re
import stat
from pathlib import Path, PurePosixPath

MAX_FILES = 2000
MAX_UPLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.I)


class AppError(ValueError):
    """An actionable error safe to show to the application user."""


def relative_name(value: str) -> str:
    """Reject traversal, Windows alternate streams and ambiguous filenames."""
    value = value.replace("\\", "/")
    parts = value.split("/")
    if (not value or len(value) > 400 or len(parts) > 20 or value.startswith("/")
            or any(part in {"", ".", ".."} or part.endswith((" ", "."))
                   or any(ord(c) < 32 or c in ':<>|?*"\x7f' for c in part)
                   or RESERVED.fullmatch(part) for part in parts)):
        raise AppError("Chemin de fichier invalide dans le projet.")
    if any(part.casefold() == ".git" for part in parts):
        raise AppError("Importez le code sans le dossier .git.")
    return PurePosixPath(*parts).as_posix()


def contained(root: Path, name: str) -> Path:
    relative = relative_name(name)
    target = root.joinpath(*relative.split("/"))
    if not target.resolve().is_relative_to(root.resolve()):
        raise AppError("Le fichier demandé sort du dossier autorisé.")
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise AppError("Les liens symboliques ne sont pas pris en charge.")
    return target


def regular_zip_entry(mode: int) -> bool:
    kind = stat.S_IFMT(mode)
    return kind in {0, stat.S_IFREG, stat.S_IFDIR}
