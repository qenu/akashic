from pathlib import Path

from PySide6.QtCore import Signal
from qfluentwidgets import FluentIcon as FIF, FluentWindow, NavigationItemPosition

from ui.chat_page import SectionsPage
from ui.library_page import LibraryPage
from ui.settings_page import SettingsPage


class MainWindow(FluentWindow):
    reset_story_requested = Signal()

    def __init__(self, base_path: Path | None = None) -> None:
        super().__init__()
        self._base_path = base_path or Path.cwd()
        self.setWindowTitle("Interface")
        self.resize(900, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        sections_page = SectionsPage()
        library_page = LibraryPage(self._base_path)
        settings_page = SettingsPage()

        self.addSubInterface(sections_page, FIF.CHAT, "Chat Area")
        self.addSubInterface(
            library_page, FIF.FOLDER, "Library",
            position=NavigationItemPosition.SCROLL,
        )
        self.addSubInterface(
            settings_page, FIF.SETTING, "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

        settings_page.reset_story_requested.connect(self.reset_story_requested.emit)
        settings_page.font_size_changed.connect(sections_page.set_font_size)
