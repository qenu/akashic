from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    ConfigItem,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    OptionsConfigItem,
    ComboBoxSettingCard,
    OptionsSettingCard,
    OptionsValidator,
    PushButton,
    PushSettingCard,
    RangeConfigItem,
    RangeSettingCard,
    RangeValidator,
    SettingCard,
    SettingCardGroup,
    Theme,
    setTheme,
)


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
        self._settings = QSettings("erikH", "interactive-chat")

        saved_theme_mode = str(self._settings.value("ui/theme_mode", "Light", type=str))
        if saved_theme_mode not in {"Light", "Dark", "Auto"}:
            saved_theme_mode = "Light"

        self.theme_mode_item = OptionsConfigItem(
            "App", "ThemeMode", saved_theme_mode,
            OptionsValidator(["Light", "Dark", "Auto"]),
        )
        self.window_opacity_item = RangeConfigItem(
            "App", "WindowOpacity", 100, RangeValidator(20, 100),
        )
        self.api_key_item = ConfigItem("App", "ApiKey", "")
        self.api_model_item = ConfigItem("App", "ApiModel", "grok-3-latest")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        group = SettingCardGroup("Settings", self)

        self.theme_mode_card = OptionsSettingCard(
            self.theme_mode_item, FIF.PALETTE, "Theme",
            "Choose Light, Dark, or Auto mode",
            ["Light", "Dark", "Auto"], group,
        )
        self.opacity_card = RangeSettingCard(
            self.window_opacity_item, FIF.CONSTRACT, "Window Opacity",
            "Adjust overall window transparency", group,
        )
        self.api_key_card = TextSettingCard(
            FIF.CERTIFICATE, "AI API Key", "Used for assistant API requests",
            placeholder="Enter API key", password=True, parent=group,
        )
        self.api_base_url_card = TextSettingCard(
            FIF.LINK, "AI API Base URL", "Base endpoint for chat completion API",
            placeholder="Enter base host or URL (e.g. api.x.ai)", parent=group,
        )
        self.api_model_card = TextSettingCard(
            FIF.ROBOT, "AI API Model", "Model used for assistant API requests",
            placeholder="Enter model name (e.g. grok-3-latest)", parent=group,
        )
        self.api_reasoning_model_card = TextSettingCard(
            FIF.SEARCH, "World Creation Model", "Model used for the world builder (init) turn",
            placeholder="Enter model name (e.g. grok-3-mini)", parent=group,
        )
        font_size_options = ["14", "15", "16", "17", "18", "19", "20"]
        saved_font_size = str(self._settings.value("ui/font_size", "14", type=str))
        if saved_font_size not in font_size_options:
            saved_font_size = "14"
        self.font_size_item = OptionsConfigItem(
            "App", "FontSize", saved_font_size,
            OptionsValidator(font_size_options),
        )
        self.font_size_card = ComboBoxSettingCard(
            self.font_size_item, FIF.FONT, "Font Size",
            "Adjust chat font size",
            font_size_options, group,
        )

        self.reset_story_card = PushSettingCard(
            "Reset", FIF.DELETE, "Reset Story",
            "Clear chat history and story progress", group,
        )

        saved_api_key = str(self._settings.value("ai/api_key", "", type=str))
        self.api_key_item.value = saved_api_key
        self.api_key_card.editor.setText(saved_api_key)

        saved_api_model = str(self._settings.value("ai/model", "grok-3-latest", type=str)).strip()
        if not saved_api_model:
            saved_api_model = "grok-3-latest"
        self.api_model_item.value = saved_api_model
        self.api_model_card.editor.setText(saved_api_model)

        saved_reasoning_model = str(self._settings.value("ai/reasoning_model", "grok-3-mini", type=str)).strip()
        if not saved_reasoning_model:
            saved_reasoning_model = "grok-3-mini"
        self.api_reasoning_model_card.editor.setText(saved_reasoning_model)

        saved_base_url = str(self._settings.value("ai/base_url", "api.x.ai", type=str)).strip()
        if not saved_base_url:
            saved_base_url = "api.x.ai"
        self.api_base_url_card.editor.setText(saved_base_url)

        group.addSettingCards([
            self.theme_mode_card,
            self.opacity_card,
            self.font_size_card,
            self.api_key_card,
            self.api_base_url_card,
            self.api_model_card,
            self.api_reasoning_model_card,
            self.reset_story_card,
        ])

        theme_map = {
            "Light": Theme.LIGHT,
            "Dark": Theme.DARK,
            "Auto": Theme.AUTO,
        }

        def apply_theme_mode(option: str) -> None:
            setTheme(theme_map.get(option, Theme.LIGHT))
            self._settings.setValue("ui/theme_mode", option)

        def apply_window_opacity(value: int) -> None:
            window = self.window()
            if window is not None:
                window.setWindowOpacity(value / 100.0)

        def save_api_key() -> None:
            value = self.api_key_card.editor.text()
            self.api_key_item.value = value
            self._settings.setValue("ai/api_key", value)
            InfoBar.success(
                title="Saved", content="API key saved", duration=1500,
                position=InfoBarPosition.TOP, parent=self.window(),
            )

        def save_api_model() -> None:
            value = self.api_model_card.editor.text().strip() or "grok-3-latest"
            self.api_model_item.value = value
            self.api_model_card.editor.setText(value)
            self._settings.setValue("ai/model", value)
            InfoBar.success(
                title="Saved", content="API model saved", duration=1500,
                position=InfoBarPosition.TOP, parent=self.window(),
            )

        def save_api_base_url() -> None:
            value = self.api_base_url_card.editor.text().strip() or "api.x.ai"
            self.api_base_url_card.editor.setText(value)
            self._settings.setValue("ai/base_url", value)
            InfoBar.success(
                title="Saved", content="API base URL saved", duration=1500,
                position=InfoBarPosition.TOP, parent=self.window(),
            )

        def save_reasoning_model() -> None:
            value = self.api_reasoning_model_card.editor.text().strip() or "grok-3-mini"
            self.api_reasoning_model_card.editor.setText(value)
            self._settings.setValue("ai/reasoning_model", value)
            InfoBar.success(
                title="Saved", content="World creation model saved", duration=1500,
                position=InfoBarPosition.TOP, parent=self.window(),
            )

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
                title="Story Reset", content="Story history cleared", duration=1500,
                position=InfoBarPosition.TOP, parent=self.window(),
            )

        def apply_font_size(value: str) -> None:
            self._settings.setValue("ui/font_size", value)
            self.font_size_changed.emit(int(value))

        self.theme_mode_item.valueChanged.connect(apply_theme_mode)
        self.window_opacity_item.valueChanged.connect(apply_window_opacity)
        self.font_size_item.valueChanged.connect(apply_font_size)
        self.api_key_card.save_button.clicked.connect(save_api_key)
        self.api_base_url_card.save_button.clicked.connect(save_api_base_url)
        self.api_model_card.save_button.clicked.connect(save_api_model)
        self.api_reasoning_model_card.save_button.clicked.connect(save_reasoning_model)
        self.reset_story_card.clicked.connect(request_reset_story)

        apply_theme_mode(self.theme_mode_item.value)
        apply_window_opacity(self.window_opacity_item.value)

        layout.addWidget(group)
        layout.addStretch(1)
