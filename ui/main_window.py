from pathlib import Path

from PySide6.QtCore import Signal
from qfluentwidgets import DotInfoBadge, FluentIcon as FIF, FluentWindow, InfoBadgePosition, NavigationItemPosition

from ui.chat_page import SectionsPage
from ui.library_page import LibraryPage
from ui.settings_page import SettingsPage
from ui.quest_page import QuestPage
from ui.item_page import ItemPage
from ui.equipment_page import EquipmentPage


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
        quest_page = QuestPage(self._base_path)
        item_page = ItemPage(self._base_path)
        equipment_page = EquipmentPage(self._base_path)

        self.addSubInterface(sections_page, FIF.CHAT, "Chat Area")
        self.addSubInterface(
            library_page, FIF.FOLDER, "Library",
            position=NavigationItemPosition.SCROLL,
        )
        self.addSubInterface(
            quest_page, FIF.BOOK_SHELF, "Quest",
            position=NavigationItemPosition.SCROLL,
        )
        self.addSubInterface(
            item_page, FIF.SHOPPING_CART, "Item",
            position=NavigationItemPosition.SCROLL,
        )
        self.addSubInterface(
            equipment_page, FIF.GAME, "Equipment",
            position=NavigationItemPosition.SCROLL,
        )
        self.addSubInterface(
            settings_page, FIF.SETTING, "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

        settings_page.reset_story_requested.connect(self.reset_story_requested.emit)
        settings_page.font_size_changed.connect(sections_page.set_font_size)

        self._chat_badge: DotInfoBadge | None = None

    def show_chat_badge(self) -> None:
        """Show an attention dot on the Chat nav item."""
        if self._chat_badge is not None:
            return
        nav_item = self.navigationInterface.widget("sectionsPage")
        if nav_item is None:
            return
        self._chat_badge = DotInfoBadge.attension(
            parent=nav_item,
            target=nav_item,
            position=InfoBadgePosition.NAVIGATION_ITEM,
        )

    def clear_chat_badge(self) -> None:
        """Remove the attention dot from the Chat nav item."""
        if self._chat_badge is not None:
            self._chat_badge.deleteLater()
            self._chat_badge = None
