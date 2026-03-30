from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QShowEvent, QHideEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    SubtitleLabel,
    TitleLabel,
    ToggleButton,
    ToolButton,
)

from game.world_io import resolve_latest_world_folder, read_world_json


class EquipmentPage(QWidget):
    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__()
        self.setObjectName("equipmentPage")
        self._base_path: Path = base_path or Path.cwd()
        self._world_folder: Path | None = None
        self._equipment: list[dict] = []
        self._toggles: list[tuple[dict, ToggleButton]] = []
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(TitleLabel("Equipments"))

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
        self._load_equipment()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self._save_equipment()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_equipment(self) -> None:
        self._world_folder = resolve_latest_world_folder(self._base_path)
        if self._world_folder is None:
            self._equipment = []
        else:
            self._equipment = read_world_json(self._world_folder, "equipment.json", [])
        self._rebuild_cards()

    def _save_equipment(self) -> None:
        if self._world_folder is None or not self._equipment:
            return
        target = self._world_folder / "equipment.json"
        target.write_text(
            json.dumps(self._equipment, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------

    def _rebuild_cards(self) -> None:
        self._toggles.clear()
        # Remove all items except the trailing stretch
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for eq in self._equipment:
            if isinstance(eq, dict):
                card = self._build_card(eq)
                self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _build_card(self, eq: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(100)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        # Left: name + class + purpose
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(eq.get("名稱", ""))
        class_label = CaptionLabel(eq.get("分類", ""))
        purpose_label = BodyLabel(eq.get("用途", ""))
        purpose_label.setFont(QFont(purpose_label.font().family(), 12))
        purpose_label.setWordWrap(True)

        info_col.addWidget(name_label)
        info_col.addWidget(class_label)
        info_col.addWidget(purpose_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        # Right: toggle button
        is_equipped = eq.get("使用中", False)
        toggle = ToggleButton("裝備中" if is_equipped else "裝備")
        toggle.setChecked(is_equipped)
        toggle.setFixedWidth(80)
        toggle.toggled.connect(lambda checked, e=eq, t=toggle: self._on_toggle(e, t, checked))

        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        # Trash button
        trash_btn = ToolButton(FIF.DELETE, card)
        trash_btn.setFixedSize(32, 32)
        trash_btn.clicked.connect(lambda _, e=eq: self._on_delete(e))

        row.addWidget(trash_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._toggles.append((eq, toggle))
        return card

    def _on_delete(self, eq: dict) -> None:
        name = eq.get("名稱", "")
        dlg = MessageBox("確認丟棄", f"確定要丟掉 {name} 嗎?", self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._equipment = [e for e in self._equipment if e is not eq]
            self._rebuild_cards()

    def _on_toggle(self, eq: dict, toggle: ToggleButton, checked: bool) -> None:
        eq["使用中"] = checked
        name = eq.get("名稱", "")

        if checked:
            toggle.setText("裝備中")
            # Unequip any other item in the same 分類
            category = eq.get("分類", "")
            for other_eq, other_toggle in self._toggles:
                if other_eq is eq:
                    continue
                if other_eq.get("分類", "") == category and other_eq.get("使用中", False):
                    other_eq["使用中"] = False
                    other_toggle.blockSignals(True)
                    other_toggle.setChecked(False)
                    other_toggle.setText("裝備")
                    other_toggle.blockSignals(False)

            InfoBar.success(
                title="裝備",
                content=f"裝備了 {name}",
                parent=self,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
            )
        else:
            InfoBar.info(
                title="卸除",
                content=f"卸除了 {name}",
                parent=self,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
            )
