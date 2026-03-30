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
    PushButton,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    SubtitleLabel,
    TitleLabel,
    ToolButton,
)

from game.world_io import resolve_latest_world_folder, read_world_json


class ItemPage(QWidget):
    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__()
        self.setObjectName("itemPage")
        self._base_path: Path = base_path or Path.cwd()
        self._world_folder: Path | None = None
        self._items: list[dict] = []
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(TitleLabel("Items"))

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
        self._load_items()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self._save_items()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_items(self) -> None:
        self._world_folder = resolve_latest_world_folder(self._base_path)
        if self._world_folder is None:
            self._items = []
        else:
            self._items = read_world_json(self._world_folder, "item.json", [])
        self._rebuild_cards()

    def _save_items(self) -> None:
        if self._world_folder is None or not self._items:
            return
        target = self._world_folder / "item.json"
        target.write_text(
            json.dumps(self._items, ensure_ascii=False, indent=2),
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

        for item in self._items:
            if isinstance(item, dict):
                card = self._build_card(item)
                self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _build_card(self, item: dict) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card.setFixedHeight(100)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        # Left: name + purpose + quantity
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = SubtitleLabel(item.get("名稱", ""))
        purpose_label = BodyLabel(item.get("用途", ""))
        purpose_label.setFont(QFont(purpose_label.font().family(), 12))
        purpose_label.setWordWrap(True)
        qty = item.get("數量", 0)
        qty_label = CaptionLabel(f"數量：{qty}")

        info_col.addWidget(name_label)
        info_col.addWidget(purpose_label)
        info_col.addWidget(qty_label)
        info_col.addStretch(1)

        row.addLayout(info_col, 1)

        # Use button
        use_btn = PushButton("使用")
        use_btn.setFixedWidth(64)
        use_btn.clicked.connect(lambda _, i=item, ql=qty_label: self._on_use(i, ql))

        row.addWidget(use_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Trash button
        trash_btn = ToolButton(FIF.DELETE, card)
        trash_btn.setFixedSize(32, 32)
        trash_btn.clicked.connect(lambda _, i=item: self._on_delete(i))

        row.addWidget(trash_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return card

    def _on_use(self, item: dict, qty_label: CaptionLabel) -> None:
        qty = int(item.get("數量", 0))
        if qty <= 0:
            return
        qty -= 1
        item["數量"] = qty
        qty_label.setText(f"數量：{qty}")
        name = item.get("名稱", "")
        InfoBar.success(
            title="使用",
            content=f"使用了 {name}（剩余 {qty}）",
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
        )
        if qty == 0:
            self._items = [e for e in self._items if e is not item]
            self._rebuild_cards()

    def _on_delete(self, item: dict) -> None:
        name = item.get("名稱", "")
        dlg = MessageBox("確認丟棄", f"確定要丟掉 {name} 嗎?", self)
        dlg.yesButton.setText("確認")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            self._items = [e for e in self._items if e is not item]
            self._rebuild_cards()
