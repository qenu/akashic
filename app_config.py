from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AppConfig:
    """Singleton JSON-backed config store for config/config.json.

    All reads/writes go through ``get`` / ``set``.  Every write is
    flushed to disk immediately so the file is always current.

    Usage::

        # once, at startup:
        AppConfig.init(base_path)

        # anywhere afterwards:
        cfg = AppConfig.instance()
        val = cfg.get("ai", "api_key", "")
        cfg.set("ai", "api_key", new_key)
    """

    _instance: AppConfig | None = None

    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Singleton helpers
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, base_path: Path) -> AppConfig:
        """Create (or replace) the singleton from *base_path*/config/settings.json."""
        cls._instance = cls(base_path / "config" / "settings.json")
        return cls._instance

    @classmethod
    def instance(cls) -> AppConfig:
        if cls._instance is None:
            raise RuntimeError(
                "AppConfig.init(base_path) must be called before AppConfig.instance()"
            )
        return cls._instance

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict):
                    self._data = {}
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Return ``data[section][key]``, or *default* if absent."""
        section_data = self._data.get(section)
        if not isinstance(section_data, dict):
            return default
        value = section_data.get(key)
        return value if value is not None else default

    def set(self, section: str, key: str, value: Any) -> None:
        """Set ``data[section][key] = value`` and flush to disk."""
        if section not in self._data or not isinstance(self._data[section], dict):
            self._data[section] = {}
        self._data[section][key] = value
        self._save()

    def get_section(self, section: str) -> dict[str, Any]:
        """Return a shallow copy of an entire section (empty dict if missing)."""
        data = self._data.get(section)
        return dict(data) if isinstance(data, dict) else {}
