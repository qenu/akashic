from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    MessageBox,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
    ToolButton,
)

from ui.world_data_page import WorldDataPage


class ItemPage(WorldDataPage):
    item_used = Signal(str)  # emits item name when player uses an item

    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__(
            object_name="itemPage",
            title="Items",
            json_file="item.json",
            base_path=base_path,
        )

    def _build_card(self, entry: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(100)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(entry.get("名稱", ""))
        purpose_label = BodyLabel(entry.get("用途", ""))
        purpose_label.setFont(QFont(purpose_label.font().family(), 12))
        purpose_label.setWordWrap(True)
        qty = entry.get("數量", 0)
        qty_label = CaptionLabel(f"數量：{qty}")

        info_col.addWidget(name_label)
        info_col.addWidget(purpose_label)
        info_col.addWidget(qty_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        use_btn = PushButton("使用")
        use_btn.setFixedWidth(64)
        use_btn.clicked.connect(lambda _, e=entry, ql=qty_label: self._on_use(e, ql))

        row.addWidget(use_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        trash_btn = ToolButton(FIF.DELETE, card)
        trash_btn.setFixedSize(32, 32)
        trash_btn.clicked.connect(lambda _, e=entry: self._on_delete(e))

        row.addWidget(trash_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return card

    def set_frozen(self, frozen: bool) -> None:
        """Disable or re-enable all use and delete buttons on every card."""
        for i in range(self.content_layout.count() - 1):
            item = self.content_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is None:
                continue
            for btn in widget.findChildren(PushButton):
                btn.setEnabled(not frozen)
            for btn in widget.findChildren(ToolButton):
                btn.setEnabled(not frozen)

    def _on_use(self, entry: dict, qty_label: CaptionLabel) -> None:
        qty = int(entry.get("數量", 0))
        if qty <= 0:
            return
        name = entry.get("名稱", "")
        self.item_used.emit(name)

    def _on_delete(self, entry: dict) -> None:
        name = entry.get("名稱", "")
        dlg = MessageBox("確認丟棄", f"確定要丟掉 {name} 嗎?", self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._remove_entry(entry)
