"""설정 다이얼로그.

모니터링 간격, 언어 설정을 제공한다.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QPushButton,
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


class SettingsDialog(QDialog):
    """설정 다이얼로그.

    모니터링 간격과 언어를 설정한다.
    """

    def __init__(
        self,
        interval_seconds: int = 30,
        language: str = "ko",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._interval = interval_seconds
        self._language = language

        self.setWindowTitle(t("settings_window_title"))
        self.setFixedWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(f"QDialog {{ background: {APP_BG}; }}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── 타이틀 ──
        title = QLabel(t("settings_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TITLE_TEXT}; background: transparent;")
        layout.addWidget(title)

        # ── 공통 스타일 ──
        label_style = (
            f"color: {SUBTITLE_TEXT}; font-size: 12px; background: transparent;"
        )
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

        # ── 모니터링 간격 ──
        interval_label = QLabel(t("settings_interval"))
        interval_label.setStyleSheet(label_style)
        layout.addWidget(interval_label)

        interval_row = QHBoxLayout()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 600)
        self._interval_spin.setValue(self._interval)
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
        current_index = 0
        for i, (code, name) in enumerate(LANGUAGES):
            self._lang_combo.addItem(name, code)
            if code == self._language:
                current_index = i
        self._lang_combo.setCurrentIndex(current_index)
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
        btn_cancel = QPushButton(t("btn_cancel"))
        btn_cancel.setStyleSheet(btn_style_cancel)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

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
        btn_save = QPushButton(t("btn_save"))
        btn_save.setStyleSheet(btn_style_save)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    # ── 프로퍼티 ──

    @property
    def interval_seconds(self) -> int:
        """설정된 모니터링 간격 (초)."""
        return self._interval_spin.value()

    @property
    def language(self) -> str:
        """설정된 언어 코드 ('ko' 또는 'en')."""
        return self._lang_combo.currentData()
