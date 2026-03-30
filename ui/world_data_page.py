from __future__ import annotations

import json
from abc import abstractmethod
from pathlib import Path

from PySide6.QtGui import QShowEvent, QHideEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    SimpleCardWidget,
    SingleDirectionScrollArea,
    TitleLabel,
)

from game.world_io import resolve_latest_world_folder, read_world_json


class WorldDataPage(QWidget):
    """Base class for pages that display a list of world-data entities
    (quests, items, equipment) as scrollable cards."""

    def __init__(
        self,
        *,
        object_name: str,
        title: str,
        json_file: str,
        base_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self._base_path: Path = base_path or Path.cwd()
        self._world_folder: Path | None = None
        self._entries: list[dict] = []
        self._json_file = json_file
        self._title = title
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(TitleLabel(self._title))

        self.scroll_area = SingleDirectionScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch(1)
        self.scroll_area.setWidget(self.content_widget)

        layout.addWidget(self.scroll_area, 1)

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._load_entries()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self._save_entries()

    def refresh(self) -> None:
        """Reload from disk. Called when world data changes while page is visible."""
        self._load_entries()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_entries(self) -> None:
        self._world_folder = resolve_latest_world_folder(self._base_path)
        if self._world_folder is None:
            self._entries = []
        else:
            self._entries = read_world_json(self._world_folder, self._json_file, [])
        self._rebuild_cards()

    def _save_entries(self) -> None:
        if self._world_folder is None or not self._entries:
            return
        target = self._world_folder / self._json_file
        target.write_text(
            json.dumps(self._entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------

    def _rebuild_cards(self) -> None:
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for entry in self._entries:
            if isinstance(entry, dict):
                card = self._build_card(entry)
                self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    @abstractmethod
    def _build_card(self, entry: dict) -> SimpleCardWidget:
        ...

    def _remove_entry(self, entry: dict) -> None:
        self._entries = [e for e in self._entries if e is not entry]
        self._rebuild_cards()
