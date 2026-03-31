from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, CheckBox,
                            ComboBox)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (IndeterminateProgressBar, InfoBar, InfoBarPosition,
                            LineEdit, ListWidget, PillPushButton,
                            PrimaryPushButton, ProgressBar, PushButton,
                            RadioButton, SearchLineEdit, SimpleCardWidget,
                            SingleDirectionScrollArea, Slider, SpinBox,
                            StrongBodyLabel, SubtitleLabel, SwitchButton,
                            TextEdit, TitleLabel, ToggleButton, ToolButton,
                            TransparentPushButton, TransparentToolButton)

from game.world_io import resolve_latest_world_folder

LIBRARY_REQUIRED_FILES = {
    "player.json",
    "skill.json",
    "equipment.json",
    "item.json",
    "npc.json",
}


def _demo_row(*widgets: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch(1)
    return row


def _section(title: str, *rows: QWidget) -> SimpleCardWidget:
    card = SimpleCardWidget()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(10)
    lay.addWidget(StrongBodyLabel(title))
    for row in rows:
        lay.addWidget(row)
    return card


class LibraryPage(QWidget):
    def __init__(self, base_path: Path) -> None:
        super().__init__()
        self.setObjectName("libraryPage")
        self._base_path = base_path
        self._build_layout()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(TitleLabel("Library"))

        self.scroll_area = SingleDirectionScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        self.content_layout.addStretch(1)
        self.scroll_area.setWidget(self.content_widget)

        layout.addWidget(self.scroll_area, 1)

        self._build_demo()

    def _build_demo(self) -> None:
        sections = [
            self._demo_labels(),
            self._demo_buttons(),
            self._demo_toggle_check(),
            self._demo_inputs(),
            self._demo_spinbox_slider(),
            self._demo_combobox(),
            self._demo_progress(),
            self._demo_pill(),
            self._demo_list(),
            self._demo_cards(),
            self._demo_infobar_trigger(),
        ]
        for s in sections:
            self.content_layout.insertWidget(self.content_layout.count() - 1, s)

    def _demo_labels(self) -> SimpleCardWidget:
        return _section(
            "Labels",
            _demo_row(CaptionLabel("CaptionLabel")),
            _demo_row(BodyLabel("BodyLabel")),
            _demo_row(StrongBodyLabel("StrongBodyLabel")),
            _demo_row(SubtitleLabel("SubtitleLabel")),
            _demo_row(TitleLabel("TitleLabel")),
        )

    def _demo_buttons(self) -> SimpleCardWidget:
        return _section(
            "Buttons",
            _demo_row(
                PushButton("PushButton"),
                PrimaryPushButton("PrimaryPushButton"),
                TransparentPushButton("TransparentPushButton"),
            ),
            _demo_row(
                ToolButton(FIF.EDIT),
                TransparentToolButton(FIF.EDIT),
            ),
        )

    def _demo_toggle_check(self) -> SimpleCardWidget:
        tb = ToggleButton("ToggleButton")
        sw = SwitchButton()
        ck = CheckBox("CheckBox")
        rb1 = RadioButton("RadioButton A")
        rb2 = RadioButton("RadioButton B")
        rb1.setChecked(True)
        return _section(
            "Toggle / Check / Radio / Switch",
            _demo_row(tb, sw),
            _demo_row(ck),
            _demo_row(rb1, rb2),
        )

    def _demo_inputs(self) -> SimpleCardWidget:
        le = LineEdit()
        le.setPlaceholderText("LineEdit")
        le.setFixedWidth(180)

        sl = SearchLineEdit()
        sl.setPlaceholderText("SearchLineEdit")
        sl.setFixedWidth(180)

        te = TextEdit()
        te.setPlaceholderText("TextEdit")
        te.setFixedHeight(72)
        te.setFixedWidth(220)

        return _section(
            "Inputs",
            _demo_row(le, sl),
            _demo_row(te),
        )

    def _demo_spinbox_slider(self) -> SimpleCardWidget:
        sb = SpinBox()
        sb.setRange(0, 100)
        sb.setValue(42)

        sld = Slider(Qt.Orientation.Horizontal)
        sld.setRange(0, 100)
        sld.setValue(60)
        sld.setFixedWidth(160)

        return _section("SpinBox / Slider", _demo_row(sb, sld))

    def _demo_combobox(self) -> SimpleCardWidget:
        cb = ComboBox()
        cb.addItems(["Option A", "Option B", "Option C"])
        return _section("ComboBox", _demo_row(cb))

    def _demo_progress(self) -> SimpleCardWidget:
        pb = ProgressBar()
        pb.setValue(65)
        pb.setFixedWidth(220)

        ipb = IndeterminateProgressBar()
        ipb.setFixedWidth(220)
        ipb.start()

        return _section(
            "ProgressBar / IndeterminateProgressBar",
            _demo_row(pb),
            _demo_row(ipb),
        )

    def _demo_pill(self) -> SimpleCardWidget:
        p1 = PillPushButton("PillPushButton (on)")
        p1.setChecked(True)
        p2 = PillPushButton("PillPushButton (off)")
        return _section("PillPushButton", _demo_row(p1, p2))

    def _demo_list(self) -> SimpleCardWidget:
        lw = ListWidget()
        lw.addItems(["ListWidget item 1", "ListWidget item 2", "ListWidget item 3"])
        lw.setFixedHeight(96)
        return _section("ListWidget", _demo_row(lw))

    def _demo_cards(self) -> SimpleCardWidget:
        inner = CardWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(12, 8, 12, 8)
        inner_lay.addWidget(BodyLabel("CardWidget (nested inside SimpleCardWidget)"))
        return _section("Cards", _demo_row(inner))

    def _demo_infobar_trigger(self) -> SimpleCardWidget:
        btn_info = PushButton("InfoBar — Info")
        btn_success = PushButton("InfoBar — Success")
        btn_warning = PushButton("InfoBar — Warning")
        btn_error = PushButton("InfoBar — Error")

        btn_info.clicked.connect(
            lambda: InfoBar.info(
                "Info",
                "This is an info bar.",
                parent=self,
                position=InfoBarPosition.TOP,
            )
        )
        btn_success.clicked.connect(
            lambda: InfoBar.success(
                "Success",
                "Operation completed.",
                parent=self,
                position=InfoBarPosition.TOP,
            )
        )
        btn_warning.clicked.connect(
            lambda: InfoBar.warning(
                "Warning",
                "Something looks off.",
                parent=self,
                position=InfoBarPosition.TOP,
            )
        )
        btn_error.clicked.connect(
            lambda: InfoBar.error(
                "Error",
                "Something went wrong.",
                parent=self,
                position=InfoBarPosition.TOP,
            )
        )

        return _section(
            "InfoBar",
            _demo_row(btn_info, btn_success),
            _demo_row(btn_warning, btn_error),
        )

    def refresh_from_latest_world(self, base_path: Path) -> None:
        pass  # demo page; no world file display
