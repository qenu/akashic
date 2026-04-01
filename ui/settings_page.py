from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import ConfigItem, ExpandGroupSettingCard
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (InfoBar, InfoBarPosition, LineEdit, MessageBox,
                            OptionsConfigItem, OptionsSettingCard,
                            OptionsValidator, PushButton, PushSettingCard,
                            RangeConfigItem, RangeSettingCard, RangeValidator,
                            SettingCard, SettingCardGroup,
                            SingleDirectionScrollArea, SpinBox,
                            SwitchSettingCard, Theme, setTheme)

from app_config import AppConfig


class TextSettingCard(SettingCard):
    """Reusable setting card with a text editor and save button."""

    def __init__(
        self,
        icon,
        title: str,
        content: str | None = None,
        *,
        placeholder: str = "",
        password: bool = False,
        parent=None,
    ) -> None:
        super().__init__(icon, title, content, parent)
        self.editor = LineEdit(self)
        self.editor.setPlaceholderText(placeholder)
        self.editor.setMinimumWidth(260)
        self.editor.setClearButtonEnabled(True)
        if password:
            self.editor.setEchoMode(QLineEdit.EchoMode.Password)
        self.save_button = PushButton("Save", self)
        self.hBoxLayout.addWidget(self.editor, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class SettingsPage(QWidget):
    reset_story_requested = Signal()
    font_size_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("settingsPage")
        cfg = AppConfig.instance()
        self._qsettings = QSettings("erikH", "interactive-chat")

        saved_theme_mode = str(cfg.get("ui", "theme_mode", "Light"))
        if saved_theme_mode not in {"Light", "Dark", "Auto"}:
            saved_theme_mode = "Light"

        self.theme_mode_item = OptionsConfigItem(
            "App",
            "ThemeMode",
            saved_theme_mode,
            OptionsValidator(["Light", "Dark", "Auto"]),
        )

        saved_opacity = int(cfg.get("ui", "window_opacity", 100))
        self.window_opacity_item = RangeConfigItem(
            "App",
            "WindowOpacity",
            saved_opacity,
            RangeValidator(20, 100),
        )

        self.api_key_item = ConfigItem("App", "ApiKey", "")
        self.api_model_item = ConfigItem("App", "ApiModel", "grok-3-latest")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = SingleDirectionScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        _container = QWidget()
        _container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(_container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        group = SettingCardGroup("Settings", _container)

        self.theme_mode_card = OptionsSettingCard(
            self.theme_mode_item,
            FIF.PALETTE,
            "Theme",
            "Choose Light, Dark, or Auto mode",
            ["Light", "Dark", "Auto"],
            group,
        )
        self.opacity_card = RangeSettingCard(
            self.window_opacity_item,
            FIF.CONSTRACT,
            "Window Opacity",
            "Adjust overall window transparency",
            group,
        )
        self.ai_group_card = ExpandGroupSettingCard(
            FIF.ROBOT,
            "AI Settings",
            "API key, endpoint and model configuration",
            group,
        )
        self.api_key_card = TextSettingCard(
            FIF.CERTIFICATE,
            "AI API Key",
            "Used for assistant API requests",
            placeholder="Enter API key",
            password=True,
        )
        self.api_base_url_card = TextSettingCard(
            FIF.LINK,
            "AI API Base URL",
            "Base endpoint for chat completion API",
            placeholder="Enter base host or URL (e.g. api.x.ai)",
        )
        self.api_model_card = TextSettingCard(
            FIF.ROBOT,
            "AI API Model",
            "Model used for assistant API requests",
            placeholder="Enter model name (e.g. grok-3-latest)",
        )
        self.api_reasoning_model_card = TextSettingCard(
            FIF.SEARCH,
            "World Creation Model",
            "Model used for the world builder (init) turn",
            placeholder="Enter model name (e.g. grok-3-mini)",
        )
        saved_log_raw_io = bool(cfg.get("ai", "log_raw_io", False))
        self.log_raw_io_item = ConfigItem("App", "LogRawIO", saved_log_raw_io)
        self.log_raw_io_card = SwitchSettingCard(
            FIF.DOCUMENT,
            "Log Raw API I/O",
            "Log full request and response payloads to the log file",
            self.log_raw_io_item,
        )
        self.log_raw_io_card.setChecked(saved_log_raw_io)

        saved_font_size = int(cfg.get("ui", "font_size", 14))
        self.font_size_card = SettingCard(
            FIF.FONT,
            "Font Size",
            "Adjust chat font size",
            group,
        )
        self._font_spinbox = SpinBox(self.font_size_card)
        self._font_spinbox.setRange(10, 32)
        self._font_spinbox.setValue(saved_font_size)
        self._font_spinbox.setFixedWidth(160)
        self.font_size_card.hBoxLayout.addWidget(
            self._font_spinbox, 0, Qt.AlignmentFlag.AlignRight
        )
        self.font_size_card.hBoxLayout.addSpacing(16)

        self.reset_story_card = PushSettingCard(
            "Reset",
            FIF.DELETE,
            "Reset Story",
            "Clear chat history and story progress",
            group,
        )

        # Populate editors from config
        saved_api_key = str(self._qsettings.value("ai/api_key", "", type=str))
        self.api_key_item.value = saved_api_key
        self.api_key_card.editor.setText(saved_api_key)

        saved_api_model = (
            str(cfg.get("ai", "model", "grok-3-latest")).strip() or "grok-3-latest"
        )
        self.api_model_item.value = saved_api_model
        self.api_model_card.editor.setText(saved_api_model)

        saved_reasoning_model = (
            str(cfg.get("ai", "reasoning_model", "grok-3-mini")).strip()
            or "grok-3-mini"
        )
        self.api_reasoning_model_card.editor.setText(saved_reasoning_model)

        saved_base_url = (
            str(cfg.get("ai", "base_url", "api.x.ai")).strip() or "api.x.ai"
        )
        self.api_base_url_card.editor.setText(saved_base_url)

        self.ai_group_card.addGroupWidget(self.api_key_card)
        self.ai_group_card.addGroupWidget(self.api_base_url_card)
        self.ai_group_card.addGroupWidget(self.api_model_card)
        self.ai_group_card.addGroupWidget(self.api_reasoning_model_card)
        self.ai_group_card.addGroupWidget(self.log_raw_io_card)

        group.addSettingCards(
            [
                self.theme_mode_card,
                self.opacity_card,
                self.font_size_card,
                self.ai_group_card,
                self.reset_story_card,
            ]
        )

        theme_map = {
            "Light": Theme.LIGHT,
            "Dark": Theme.DARK,
            "Auto": Theme.AUTO,
        }

        def apply_theme_mode(option: str) -> None:
            setTheme(theme_map.get(option, Theme.LIGHT))
            AppConfig.instance().set("ui", "theme_mode", option)

        def apply_window_opacity(value: int) -> None:
            AppConfig.instance().set("ui", "window_opacity", value)
            window = self.window()
            if window is not None:
                window.setWindowOpacity(value / 100.0)

        def save_api_key() -> None:
            value = self.api_key_card.editor.text()
            self.api_key_item.value = value
            self._qsettings.setValue("ai/api_key", value)
            InfoBar.success(
                title="Saved",
                content="API key saved",
                duration=1500,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

        def save_api_model() -> None:
            value = self.api_model_card.editor.text().strip() or "grok-3-latest"
            self.api_model_item.value = value
            self.api_model_card.editor.setText(value)
            AppConfig.instance().set("ai", "model", value)
            InfoBar.success(
                title="Saved",
                content="API model saved",
                duration=1500,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

        def save_api_base_url() -> None:
            value = self.api_base_url_card.editor.text().strip() or "api.x.ai"
            self.api_base_url_card.editor.setText(value)
            AppConfig.instance().set("ai", "base_url", value)
            InfoBar.success(
                title="Saved",
                content="API base URL saved",
                duration=1500,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

        def save_reasoning_model() -> None:
            value = self.api_reasoning_model_card.editor.text().strip() or "grok-3-mini"
            self.api_reasoning_model_card.editor.setText(value)
            AppConfig.instance().set("ai", "reasoning_model", value)
            InfoBar.success(
                title="Saved",
                content="World creation model saved",
                duration=1500,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

        def toggle_log_raw_io(checked: bool) -> None:
            AppConfig.instance().set("ai", "log_raw_io", checked)

        def request_reset_story() -> None:
            dialog = MessageBox(
                "Reset Story",
                "This will clear all story history and chat messages. Continue?",
                self.window(),
            )
            dialog.yesButton.setText("Reset")
            dialog.cancelButton.setText("Cancel")
            if not dialog.exec():
                return
            self.reset_story_requested.emit()
            InfoBar.success(
                title="Story Reset",
                content="Story history cleared",
                duration=1500,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

        def apply_font_size(value: int) -> None:
            AppConfig.instance().set("ui", "font_size", value)
            self.font_size_changed.emit(value)

        self.theme_mode_item.valueChanged.connect(apply_theme_mode)
        self.window_opacity_item.valueChanged.connect(apply_window_opacity)
        self._font_spinbox.valueChanged.connect(apply_font_size)
        self.api_key_card.save_button.clicked.connect(save_api_key)
        self.api_base_url_card.save_button.clicked.connect(save_api_base_url)
        self.api_model_card.save_button.clicked.connect(save_api_model)
        self.api_reasoning_model_card.save_button.clicked.connect(save_reasoning_model)
        self.log_raw_io_item.valueChanged.connect(toggle_log_raw_io)
        self.reset_story_card.clicked.connect(request_reset_story)

        apply_theme_mode(self.theme_mode_item.value)
        apply_window_opacity(self.window_opacity_item.value)

        layout.addWidget(group)
        layout.addStretch(1)
        self._scroll.setWidget(_container)
        outer_layout.addWidget(self._scroll)
