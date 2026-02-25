"""설정 오버레이 패널.

MainWindow 내부 반투명 배경 + 중앙 카드 형태의 설정 UI를 제공한다.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import t

# ── Color Palette ──
APP_BG = "#0f0f1a"
CARD_BG = "#1c1c30"
CARD_BORDER = "#2a2a45"
TITLE_TEXT = "#ffffff"
SUBTITLE_TEXT = "#8888aa"
CHECKBOX_BLUE = "#3b82f6"

# ── 언어 ──
LANGUAGES = [
    ("ko", "한국어"),
    ("en", "English"),
]


class SettingsOverlay(QWidget):
    """MainWindow 내부 오버레이 설정 패널."""

    saved = pyqtSignal(int, str)  # (interval_seconds, language)
    logout_requested = pyqtSignal()
    closed = pyqtSignal()  # 취소/배경클릭

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._welcome_mode = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0, 0, 0, 150);")
        self.hide()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        # ── 중앙 배치용 외부 레이아웃 ──
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        card_row = QHBoxLayout()
        card_row.addStretch()

        # ── 카드 위젯 ──
        self._card = QWidget()
        self._card.setFixedWidth(360)
        self._card.setStyleSheet(
            f"background: {APP_BG};border: 1px solid {CARD_BORDER};border-radius: 16px;"
        )

        layout = QVBoxLayout(self._card)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── 타이틀 ──
        title = QLabel(t("settings_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {TITLE_TEXT}; background: transparent; border: none;"
        )
        layout.addWidget(title)

        # ── 웰컴 서브타이틀 ──
        self._welcome_subtitle = QLabel(t("welcome_subtitle"))
        self._welcome_subtitle.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        self._welcome_subtitle.setVisible(False)
        layout.addWidget(self._welcome_subtitle)

        # ── 공통 스타일 ──
        label_style = f"color: {SUBTITLE_TEXT}; font-size: 12px; background: transparent; border: none;"
        input_style = (
            f"QSpinBox, QComboBox {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 6px 10px;"
            f"  color: {TITLE_TEXT};"
            f"  font-size: 13px;"
            f"}}"
            f"QSpinBox:focus, QComboBox:focus {{"
            f"  border-color: {CHECKBOX_BLUE};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 24px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  color: {TITLE_TEXT};"
            f"  selection-background-color: {CHECKBOX_BLUE};"
            f"}}"
        )

        # ── 계정 구분선 ──
        account_line = QFrame()
        account_line.setFrameShape(QFrame.Shape.HLine)
        account_line.setStyleSheet(f"color: {CARD_BORDER};")
        layout.addWidget(account_line)

        account_label = QLabel(t("settings_account"))
        account_label.setStyleSheet(label_style)
        layout.addWidget(account_label)

        account_row = QHBoxLayout()
        self._email_label = QLabel("")
        self._email_label.setStyleSheet(
            f"color: {TITLE_TEXT}; font-size: 13px; background: transparent; border: none;"
        )
        account_row.addWidget(self._email_label)
        account_row.addStretch()

        btn_style_logout = (
            "QPushButton {"
            "  background: transparent;"
            "  border: 1px solid #ef4444;"
            "  color: #ef4444;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  background: #ef4444;"
            "  color: #ffffff;"
            "}"
        )
        self._btn_logout = QPushButton(t("btn_logout"))
        self._btn_logout.setStyleSheet(btn_style_logout)
        self._btn_logout.clicked.connect(self._on_logout_clicked)
        account_row.addWidget(self._btn_logout)

        layout.addLayout(account_row)

        # ── 모니터링 간격 ──
        interval_label = QLabel(t("settings_interval"))
        interval_label.setStyleSheet(label_style)
        layout.addWidget(interval_label)

        interval_row = QHBoxLayout()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 600)
        self._interval_spin.setValue(30)
        self._interval_spin.setSuffix(t("settings_interval_suffix"))
        self._interval_spin.setStyleSheet(input_style)
        self._interval_spin.setFixedHeight(36)
        interval_row.addWidget(self._interval_spin, stretch=1)
        layout.addLayout(interval_row)

        # ── 언어 ──
        lang_label = QLabel(t("settings_language"))
        lang_label.setStyleSheet(label_style)
        layout.addWidget(lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.setStyleSheet(input_style)
        self._lang_combo.setFixedHeight(36)
        for code, name in LANGUAGES:
            self._lang_combo.addItem(name, code)
        layout.addWidget(self._lang_combo)

        layout.addSpacing(8)

        # ── 버튼 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_style_cancel = (
            f"QPushButton {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 8px 20px;"
            f"  color: {SUBTITLE_TEXT};"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton:hover {{ background: {CARD_BORDER}; }}"
        )
        self._btn_cancel = QPushButton(t("btn_cancel"))
        self._btn_cancel.setStyleSheet(btn_style_cancel)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self._btn_cancel)

        btn_style_save = (
            f"QPushButton {{"
            f"  background: {CHECKBOX_BLUE};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 8px 20px;"
            f"  color: #ffffff;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background: #2563eb; }}"
        )
        self._btn_save = QPushButton(t("btn_save"))
        self._btn_save.setStyleSheet(btn_style_save)
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self._btn_save)

        layout.addLayout(btn_row)

        card_row.addWidget(self._card)
        card_row.addStretch()
        outer.addLayout(card_row)
        outer.addStretch()

    # ── 공개 메서드 ──

    def show_settings(
        self,
        interval: int,
        language: str,
        email: str,
        welcome_mode: bool = False,
    ) -> None:
        """설정값을 세팅하고 오버레이를 표시한다."""
        self._welcome_mode = welcome_mode
        self._interval_spin.setValue(interval)
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == language:
                self._lang_combo.setCurrentIndex(i)
                break
        self._email_label.setText(t("settings_logged_in_as").format(email=email))
        self._btn_logout.setVisible(not welcome_mode)
        self._btn_cancel.setVisible(not welcome_mode)
        self._btn_save.setText(t("btn_start_app") if welcome_mode else t("btn_save"))
        self._welcome_subtitle.setVisible(welcome_mode)
        self.show()
        self.raise_()

    @property
    def interval_seconds(self) -> int:
        """설정된 모니터링 간격 (초)."""
        return self._interval_spin.value()

    @property
    def language(self) -> str:
        """설정된 언어 코드 ('ko' 또는 'en')."""
        return self._lang_combo.currentData()

    # ── 내부 핸들러 ──

    def _on_save_clicked(self) -> None:
        self.saved.emit(self.interval_seconds, self.language)
        self.hide()

    def _on_cancel_clicked(self) -> None:
        self.closed.emit()
        self.hide()

    def _on_logout_clicked(self) -> None:
        self.logout_requested.emit()
        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """배경(카드 바깥) 클릭 시 닫기. 웰컴 모드에서는 무시."""
        if self._welcome_mode:
            return
        if not self._card.geometry().contains(event.pos()):
            self.closed.emit()
            self.hide()
