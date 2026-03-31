from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (InfoBar, InfoBarPosition, MessageBox,
                            SimpleCardWidget, SubtitleLabel, ToggleButton,
                            ToolButton)

from ui.world_data_page import WorldDataPage


class EquipmentPage(WorldDataPage):
    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__(
            object_name="equipmentPage",
            title="Equipments",
            json_file="equipment.json",
            base_path=base_path,
        )
        self._toggles: list[tuple[dict, ToggleButton]] = []

    def _rebuild_cards(self) -> None:
        self._toggles.clear()
        super()._rebuild_cards()

    def _build_card(self, entry: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(100)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(entry.get("名稱", ""))
        class_label = CaptionLabel(entry.get("分類", ""))
        purpose_label = BodyLabel(entry.get("用途", ""))
        purpose_label.setFont(QFont(purpose_label.font().family(), 12))
        purpose_label.setWordWrap(True)

        info_col.addWidget(name_label)
        info_col.addWidget(class_label)
        info_col.addWidget(purpose_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        is_equipped = entry.get("使用中", False)
        toggle = ToggleButton("裝備中" if is_equipped else "裝備")
        toggle.setChecked(is_equipped)
        toggle.setFixedWidth(80)
        toggle.toggled.connect(
            lambda checked, e=entry, t=toggle: self._on_toggle(e, t, checked)
        )

        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        trash_btn = ToolButton(FIF.DELETE, card)
        trash_btn.setFixedSize(32, 32)
        trash_btn.clicked.connect(lambda _, e=entry: self._on_delete(e))

        row.addWidget(trash_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._toggles.append((entry, toggle))
        return card

    def _on_delete(self, entry: dict) -> None:
        name = entry.get("名稱", "")
        dlg = MessageBox("確認丟棄", f"確定要丟掉 {name} 嗎?", self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._remove_entry(entry)

    def _on_toggle(self, entry: dict, toggle: ToggleButton, checked: bool) -> None:
        entry["使用中"] = checked
        name = entry.get("名稱", "")

        if checked:
            toggle.setText("裝備中")
            category = entry.get("分類", "")
            for other_eq, other_toggle in self._toggles:
                if other_eq is entry:
                    continue
                if other_eq.get("分類", "") == category and other_eq.get(
                    "使用中", False
                ):
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
