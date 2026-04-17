"""
Watchdog file watcher for the Flask web app.

Invalidates the GrammarRegistry cache when YAML config files change on disk,
so the next request rebuilds the registry from fresh configs.
"""

from __future__ import annotations

from pathlib import Path
from venv import logger

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer, ObserverType
import streamlit as st


def start_watcher(config_dir: str, invalidate_keys: list[str]) -> ObserverType:
    """Start a watchdog observer that clears *cache* when YAML files change."""
    logger.info(f"Starting config watcher for directory: {config_dir} with invalidate_keys: {invalidate_keys}")
    handler = _YamlChangeHandler(config_dir, invalidate_keys=invalidate_keys)
    observer = Observer()
    observer.schedule(handler, str(config_dir), recursive=True)
    observer.daemon = True
    observer.start()
    return observer


class _YamlChangeHandler(FileSystemEventHandler):
    def __init__(self, config_dir: str, invalidate_keys: list[str]):
        logger.info(f"Starting file watcher for config directory: {config_dir}")
        self.config_dir = str(Path(config_dir))
        self.invalidate_keys = invalidate_keys

    def _invalidate(self, event: FileSystemEvent) -> None:
        """
        Invalidates the cache by popping keys from `st.session_state`.
        Only invalidates if a YAML file is modified, created, or deleted.
        """
        logger.debug(f"Received file system event: {event}")
        if event.is_directory:
            return
        if event.src_path.endswith((".yaml", ".yml", ".csv")):
            logger.info(f"File change detected: {event.src_path}. Invalidating cache...")
            for key in self.invalidate_keys:
                st.session_state.pop(key, None)

    on_modified = _invalidate  # type: ignore[assignment]
    on_created = _invalidate  # type: ignore[assignment]
    on_deleted = _invalidate  # type: ignore[assignment]
