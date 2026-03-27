from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
    isDarkTheme,
    PushButton,
    qconfig,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    TransparentToolButton,
)

from app_config import AppConfig


class SectionsPage(QWidget):
    user_message_sent = Signal(str)
    assistant_message_received = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sectionsPage")
        self._font_size = int(AppConfig.instance().get("ui", "font_size", 14))
        self._max_chars = 150
        self._is_waiting = False
        self._options_available = True
        self._over_word_limit = False
        self._last_counter_overflow_state = False
        self._word_count_base_color = "#6a6a6a"
        self._stream_bubble: SimpleCardWidget | None = None
        self._stream_segments: list[tuple[QLabel, str]] = []
        self._stream_segment_idx = 0
        self._stream_char_idx = 0
        self._stream_on_done = None
        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(60)
        self._stream_timer.timeout.connect(self._stream_tick)
        self._option_placeholders = ["Option 1", "Option 2", "Option 3", "Option 4"]
        self._auto_scroll_enabled = True
        self._programmatic_scroll = False
        self._bottom_threshold = 6
        self._thinking_frames = ["thinking.", "thinking..", "thinking..."]
        self._thinking_index = 0
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(360)
        self._thinking_timer.timeout.connect(self._advance_thinking_indicator)
        self._build_layout()
        self._configure_scrollbar_behavior()
        self._bind_events()
        qconfig.themeChanged.connect(lambda _theme: self._apply_chat_theme_styles())
        self._apply_chat_theme_styles()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        chat_label = BodyLabel("Chat Area Section")

        self.chat_area = SingleDirectionScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_area.setStyleSheet("background: transparent; border: none;")

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch(1)
        self.chat_area.setWidget(self.chat_container)

        options_row = self._build_option_buttons()
        self.thinking_label = BodyLabel("")
        self.thinking_label.setMinimumHeight(24)
        self.thinking_label.setContentsMargins(12, 0, 0, 0)

        self.input_container = QWidget()
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(0)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type here...")
        self.input_box.setMinimumHeight(40)
        self.input_box.setFrame(False)
        self.input_box.returnPressed.connect(self._on_submit)
        self.input_box.textChanged.connect(self._on_input_text_changed)

        self.send_button = TransparentToolButton(FIF.SEND, self)
        self.send_button.setIconSize(self.send_button.iconSize() * 1.15)
        self.send_button.setMinimumHeight(40)
        self.send_button.setMinimumWidth(40)
        self.send_button.setStyleSheet(
            "background: transparent; border: none; padding: 0px; margin: 0px;"
        )
        self.send_button.clicked.connect(self._on_submit)

        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_button)

        self.word_count_label = BodyLabel("0/150 chars")
        self.word_count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._apply_word_count_style(force=True)

        input_meta_row = QWidget()
        input_meta_layout = QHBoxLayout(input_meta_row)
        input_meta_layout.setContentsMargins(0, 0, 0, 0)
        input_meta_layout.addStretch(1)
        input_meta_layout.addWidget(self.word_count_label)

        layout.addWidget(chat_label)
        layout.addWidget(self.chat_area, 1)
        layout.addWidget(self.thinking_label)
        layout.addWidget(self.input_container)
        layout.addWidget(input_meta_row)
        layout.addWidget(options_row)
        self._on_input_text_changed(self.input_box.text())

    def _build_option_buttons(self) -> QWidget:
        container = QWidget()
        button_layout = QHBoxLayout(container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.option_buttons = []
        for option_text in self._option_placeholders:
            button = PushButton(option_text)
            button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, btn=button: self._send_option(
                    str(btn.property("option_payload") or "")
                )
            )
            button_layout.addWidget(button)
            self.option_buttons.append(button)

        button_layout.addStretch(1)
        return container

    def _send_option(self, option_text: str) -> None:
        if not option_text:
            return
        self._handle_send(option_text)

    def set_option_candidates(self, options: list[str]) -> None:
        clean_options = [str(item).strip() for item in options if str(item).strip()]
        for index, button in enumerate(self.option_buttons):
            if index < len(clean_options):
                button.setProperty("option_payload", clean_options[index])
                button.setText(f"選項 {index + 1}")
                button.setVisible(True)
            else:
                button.setProperty("option_payload", "")
                button.setText(self._option_placeholders[index])
                button.setVisible(False)
                button.setEnabled(False)
        self._refresh_option_buttons_enabled()

    def _configure_scrollbar_behavior(self) -> None:
        self._scrollbar = self.chat_area.verticalScrollBar()
        self._scrollbar.valueChanged.connect(self._on_scroll_value_changed)
        self.chat_area.viewport().installEventFilter(self)
        self._scrollbar.installEventFilter(self)

        self._scrollbar_hide_timer = QTimer(self)
        self._scrollbar_hide_timer.setSingleShot(True)
        self._scrollbar_hide_timer.setInterval(900)
        self._scrollbar_hide_timer.timeout.connect(self._hide_scrollbar)

        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(16)
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)
        self._auto_scroll_timer.start()

    def _bind_events(self) -> None:
        self.user_message_sent.connect(self._on_user_message)
        self.assistant_message_received.connect(self._on_assistant_message)

    def _create_message_label(self, text: str, *, is_user: bool) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        label.setProperty("is_user_message", is_user)
        label.setStyleSheet(self._message_style(is_user))
        return label

    def _create_status_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        label.setProperty("is_status_label", True)
        label.setStyleSheet(self._status_label_style())
        return label

    def _status_label_style(self) -> str:
        color = "#909090" if isDarkTheme() else "#757575"
        size = max(10, self._font_size - 2)
        return (
            f"font-family: 'Consolas', 'Courier New', monospace;"
            f" font-size: {size}px; color: {color};"
            " background: transparent; border: none;"
        )

    def _message_style(self, is_user: bool) -> str:
        if isDarkTheme():
            color = "#bdbdbd" if is_user else "#f1f1f1"
        else:
            color = "#6a6a6a" if is_user else "#2f2f2f"
        size = self._font_size - 2 if is_user else self._font_size
        return f"font-size: {size}px; color: {color}; background: transparent; border: none;"

    def _apply_chat_theme_styles(self) -> None:
        if isDarkTheme():
            input_bg = "#3a3a3a"
            input_text = "#f3f3f3"
            placeholder = "#a0a0a0"
            thinking = "#b8b8b8"
        else:
            input_bg = "#e8e8e8"
            input_text = "#2f2f2f"
            placeholder = "#7a7a7a"
            thinking = "#6a6a6a"

        self.input_container.setStyleSheet(
            f"background-color: {input_bg}; border-radius: 12px; padding: 8px;"
        )
        self.input_box.setStyleSheet(
            "QLineEdit {"
            f"background: transparent; border: none; font-size: {self._font_size}px; padding: 0px 8px; color: {input_text};"
            "}"
            "QLineEdit:disabled {"
            f"color: {placeholder};"
            "}"
            "QLineEdit::placeholder {"
            f"color: {placeholder};"
            "}"
        )
        self.thinking_label.setStyleSheet(f"color: {thinking};")
        self._word_count_base_color = "#a8a8a8" if isDarkTheme() else "#6a6a6a"
        self._update_word_count_label(self._char_count(self.input_box.text()))

        for i in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if widget is None:
                continue
            for label in widget.findChildren(QLabel):
                if label.property("is_status_label"):
                    label.setStyleSheet(self._status_label_style())
                    continue
                is_user = label.property("is_user_message")
                if isinstance(is_user, bool):
                    label.setStyleSheet(self._message_style(is_user))

    def _add_user_text_message(self, text: str) -> None:
        user_container = QWidget()
        user_layout = QVBoxLayout(user_container)
        user_layout.setContentsMargins(12, 0, 0, 0)
        user_layout.setSpacing(0)
        user_layout.addWidget(self._create_message_label(text, is_user=True))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, user_container)
        self._request_scroll_to_bottom()

    def _add_assistant_message(self, text: str, status_line: str = "", changes_text: str = "", options: list[str] | None = None) -> None:
        bubble = SimpleCardWidget()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(6)
        bubble_layout.addWidget(self._create_message_label(text, is_user=False))
        if status_line:
            bubble_layout.addWidget(self._create_status_label(status_line))
        if changes_text:
            bubble_layout.addWidget(self._create_status_label(changes_text))
        if options:
            option_lines = [f"{i}. {opt}" for i, opt in enumerate(options, start=1)]
            options_text = "你決定...\n" + "\n".join(option_lines)
            bubble_layout.addWidget(self._create_message_label(options_text, is_user=False))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._request_scroll_to_bottom()

    def start_stream(self, text: str, *, status_line: str = "", changes_text: str = "", options: list[str] | None = None, on_done=None) -> None:
        self._stream_timer.stop()
        self._thinking_timer.stop()
        self.thinking_label.clear()
        self._stream_on_done = on_done
        self._stream_segments = []
        self._stream_segment_idx = 0
        self._stream_char_idx = 0

        self._stream_bubble = SimpleCardWidget()
        bubble_layout = QVBoxLayout(self._stream_bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(6)

        narrative_label = self._create_message_label("", is_user=False)
        bubble_layout.addWidget(narrative_label)
        self._stream_segments.append((narrative_label, text))

        if status_line:
            status_label = self._create_status_label("")
            bubble_layout.addWidget(status_label)
            self._stream_segments.append((status_label, status_line))

        if changes_text:
            changes_label = self._create_status_label("")
            bubble_layout.addWidget(changes_label)
            self._stream_segments.append((changes_label, changes_text))

        if options:
            option_lines = [f"{i}. {opt}" for i, opt in enumerate(options, start=1)]
            options_text = "你決定...\n" + "\n".join(option_lines)
            options_label = self._create_message_label("", is_user=False)
            bubble_layout.addWidget(options_label)
            self._stream_segments.append((options_label, options_text))

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._stream_bubble)
        self._stream_timer.start()

    def _stream_tick(self) -> None:
        if self._stream_segment_idx >= len(self._stream_segments):
            self._stream_timer.stop()
            self._stream_bubble = None
            self._stream_segments = []
            if self._stream_on_done is not None:
                self._stream_on_done()
                self._stream_on_done = None
            return

        label, text = self._stream_segments[self._stream_segment_idx]
        self._stream_char_idx += 1
        label.setText(text[: self._stream_char_idx])
        self._request_scroll_to_bottom()

        if self._stream_char_idx >= len(text):
            self._stream_segment_idx += 1
            self._stream_char_idx = 0

    def _is_near_bottom(self) -> bool:
        return (self._scrollbar.maximum() - self._scrollbar.value()) <= self._bottom_threshold

    def _request_scroll_to_bottom(self) -> None:
        if self._auto_scroll_enabled:
            self._auto_scroll_tick()

    def _auto_scroll_tick(self) -> None:
        if not self._auto_scroll_enabled:
            return
        target = self._scrollbar.maximum()
        current = self._scrollbar.value()
        delta = target - current
        if delta <= 0:
            return
        step = max(1, delta // 4)
        next_value = current + step
        if target - next_value <= self._bottom_threshold:
            next_value = target
        self._programmatic_scroll = True
        self._scrollbar.setValue(next_value)
        self._programmatic_scroll = False

    def _show_scrollbar_temporarily(self) -> None:
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scrollbar_hide_timer.start()

    def _hide_scrollbar(self) -> None:
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        manual_scroll_events = {
            QEvent.Type.Wheel,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.KeyPress,
        }
        if event_type in manual_scroll_events:
            self._show_scrollbar_temporarily()
        return super().eventFilter(watched, event)

    def _on_scroll_value_changed(self, _value: int) -> None:
        if self._programmatic_scroll:
            return
        self._auto_scroll_enabled = self._is_near_bottom()
        self._show_scrollbar_temporarily()

    def _on_submit(self) -> None:
        user_input = self.input_box.text().strip()
        if not user_input:
            return
        if self._char_count(user_input) > self._max_chars:
            return
        self.input_box.clear()
        self._handle_send(user_input)

    def _handle_send(self, user_input: str) -> None:
        self.user_message_sent.emit(user_input)

    def _char_count(self, text: str) -> int:
        return len(text)

    def _set_counter_overflow_state(self, is_over_limit: bool) -> None:
        if is_over_limit == self._last_counter_overflow_state:
            return
        self._last_counter_overflow_state = is_over_limit
        self._apply_word_count_style()

    def _apply_word_count_style(self, force: bool = False) -> None:
        color = "#d84a4a" if self._over_word_limit else self._word_count_base_color
        wc_size = max(9, self._font_size - 3)
        self.word_count_label.setStyleSheet(f"font-size: {wc_size}px; color: {color};")

    def _update_word_count_label(self, count: int) -> None:
        self.word_count_label.setText(f"{count}/{self._max_chars} chars")

    def _refresh_send_enabled(self) -> None:
        self.send_button.setEnabled((not self._is_waiting) and (not self._over_word_limit))

    def _refresh_option_buttons_enabled(self) -> None:
        enabled = (not self._is_waiting) and self._options_available
        for button in self.option_buttons:
            if button.isHidden() or not str(button.property("option_payload") or ""):
                button.setEnabled(False)
                continue
            button.setEnabled(enabled)

    def set_options_available(self, is_available: bool) -> None:
        self._options_available = is_available
        self._refresh_option_buttons_enabled()

    def _on_input_text_changed(self, text: str) -> None:
        count = self._char_count(text)
        self._over_word_limit = count > self._max_chars
        self._set_counter_overflow_state(self._over_word_limit)
        self._update_word_count_label(count)
        self._refresh_send_enabled()

    def _advance_thinking_indicator(self) -> None:
        self.thinking_label.setText(self._thinking_frames[self._thinking_index])
        self._thinking_index = (self._thinking_index + 1) % len(self._thinking_frames)

    def set_waiting(self, is_waiting: bool) -> None:
        self._is_waiting = is_waiting
        if is_waiting:
            self._thinking_index = 0
            self._advance_thinking_indicator()
            self._thinking_timer.start()
        else:
            self._thinking_timer.stop()
            self.thinking_label.clear()

        self.input_box.setEnabled(not is_waiting)
        self._refresh_send_enabled()
        self._refresh_option_buttons_enabled()

        if not is_waiting:
            self.input_box.setFocus()

    def _on_user_message(self, user_input: str) -> None:
        self._add_user_text_message(user_input)

    def _on_assistant_message(self, assistant_text: str) -> None:
        self._add_assistant_message(assistant_text)

    def add_history_message(self, *, text: str, is_user: bool, status_line: str = "", options: list[str] | None = None) -> None:
        if is_user:
            self._add_user_text_message(text)
        else:
            self._add_assistant_message(text, status_line, "", options)

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        self._apply_chat_theme_styles()
        self._apply_word_count_style(force=True)

    def clear_story_ui(self) -> None:
        self._stream_timer.stop()
        self._stream_bubble = None
        self._stream_segments = []
        self._stream_segment_idx = 0
        self._stream_char_idx = 0
        self._stream_on_done = None

        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        self.input_box.clear()
        self.set_option_candidates([])
        self.set_waiting(False)
        self._scrollbar.setValue(0)
