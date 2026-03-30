from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QFont, QShowEvent, QHideEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    MessageBox,
    PushButton,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    SubtitleLabel,
    TitleLabel,
)

from game.world_io import resolve_latest_world_folder, read_world_json


class QuestPage(QWidget):
    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__()
        self.setObjectName("questPage")
        self._base_path: Path = base_path or Path.cwd()
        self._world_folder: Path | None = None
        self._quests: list[dict] = []
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(TitleLabel("Quests"))

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
        self._load_quests()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self._save_quests()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_quests(self) -> None:
        self._world_folder = resolve_latest_world_folder(self._base_path)
        if self._world_folder is None:
            self._quests = []
        else:
            self._quests = read_world_json(self._world_folder, "quest.json", [])
        self._rebuild_cards()

    def _save_quests(self) -> None:
        if self._world_folder is None or not self._quests:
            return
        target = self._world_folder / "quest.json"
        target.write_text(
            json.dumps(self._quests, ensure_ascii=False, indent=2),
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

        for quest in self._quests:
            if isinstance(quest, dict):
                card = self._build_card(quest)
                self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _build_card(self, quest: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(110)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        # Left: name + description + progress
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(quest.get("名稱", ""))
        desc_label = BodyLabel(quest.get("敘述", ""))
        desc_label.setFont(QFont(desc_label.font().family(), 12))
        desc_label.setWordWrap(True)
        progress_label = CaptionLabel(f"完成進度：{quest.get('完成進度', '0%')}")

        info_col.addWidget(name_label)
        info_col.addWidget(desc_label)
        info_col.addWidget(progress_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        # Abandon button
        abandon_btn = PushButton("放棄任務")
        abandon_btn.setFixedWidth(90)
        abandon_btn.clicked.connect(lambda _, q=quest: self._on_abandon(q))

        row.addWidget(abandon_btn)

        return card

    def _on_abandon(self, quest: dict) -> None:
        name = quest.get("名稱", "")
        dlg = MessageBox("放棄任務", f"確定要放棄 {name} 嗎?", self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._quests = [q for q in self._quests if q is not quest]
            self._rebuild_cards()
