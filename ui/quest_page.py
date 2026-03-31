from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (BodyLabel, CaptionLabel, MessageBox, PushButton,
                            SimpleCardWidget, SubtitleLabel)

from ui.world_data_page import WorldDataPage


class QuestPage(WorldDataPage):
    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__(
            object_name="questPage",
            title="Quests",
            json_file="quest.json",
            base_path=base_path,
        )

    def _build_card(self, entry: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(110)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(entry.get("名稱", ""))
        desc_label = BodyLabel(entry.get("敘述", ""))
        desc_label.setFont(QFont(desc_label.font().family(), 12))
        desc_label.setWordWrap(True)
        progress_label = CaptionLabel(f"完成進度：{entry.get('進度', '')}")

        info_col.addWidget(name_label)
        info_col.addWidget(desc_label)
        info_col.addWidget(progress_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        is_completed = entry.get("進度", "") == "已完成"
        abandon_btn = PushButton("封存任務" if is_completed else "放棄任務")
        abandon_btn.setFixedWidth(90)
        abandon_btn.clicked.connect(lambda _, e=entry: self._on_abandon(e))

        row.addWidget(abandon_btn)

        return card

    def _on_abandon(self, entry: dict) -> None:
        name = entry.get("名稱", "")
        is_completed = entry.get("進度", "") == "已完成"
        title = "封存任務" if is_completed else "放棄任務"
        body = f"確定要封存 {name} 嗎?" if is_completed else f"確定要放棄 {name} 嗎?"
        dlg = MessageBox(title, body, self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._remove_entry(entry)
