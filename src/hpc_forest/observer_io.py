"""Observation-only persistence, tolerant of transient Windows reader locks."""
import time

from .core import atomic_json


def save(path, value):
    for attempt in range(6):
        try:
            atomic_json(path, value)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (2 ** attempt))
