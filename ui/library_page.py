import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SimpleCardWidget, SingleDirectionScrollArea

from game.world_io import resolve_latest_world_folder

LIBRARY_REQUIRED_FILES = {
    "player.json",
    "skill.json",
    "equipment.json",
    "item.json",
    "npc.json",
}


class LibraryPage(QWidget):
    def __init__(self, base_path: Path) -> None:
        super().__init__()
        self.setObjectName("libraryPage")
        self._base_path = base_path
        self._build_layout()
        self.refresh_from_latest_world(base_path)

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = BodyLabel("Library Section")
        self.status_label = BodyLabel("Loading world files...")

        self.scroll_area = SingleDirectionScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch(1)
        self.scroll_area.setWidget(self.content_widget)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.scroll_area, 1)

    def _clear_content(self) -> None:
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _create_section_card(self, title: str, content: str) -> SimpleCardWidget:
        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        section_title = BodyLabel(title)
        body = QLabel(content)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        card_layout.addWidget(section_title)
        card_layout.addWidget(body)
        return card

    def _read_json_file_as_text(self, file_path: Path) -> str:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            return json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception as exc:
            return f"Failed to load {file_path.name}: {exc}"

    def refresh_from_latest_world(self, base_path: Path) -> None:
        self._clear_content()

        world_folder = resolve_latest_world_folder(base_path, LIBRARY_REQUIRED_FILES)
        if world_folder is None:
            self.status_label.setText("No generated world files found yet.")
            return

        self.status_label.setText(f"Showing: {world_folder.name}")

        file_sections = [
            ("Player", "player.json"),
            ("Skill", "skill.json"),
            ("Equipment", "equipment.json"),
            ("Item", "item.json"),
            ("NPC", "npc.json"),
        ]
        for section_title, file_name in file_sections:
            file_path = world_folder / file_name
            content_text = self._read_json_file_as_text(file_path)
            self.content_layout.insertWidget(
                self.content_layout.count() - 1,
                self._create_section_card(section_title, content_text),
            )
