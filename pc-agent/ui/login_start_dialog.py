"""Startup login panel without embedded WebEngine."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]

_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "resources" / "app-icon.png"
_APP_ICON_SIZE = 84


class LoginStartDialog(QWidget):
    """In-window login panel shown before launching browser OAuth."""

    login_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._refresh_texts()

    def set_error(self, message: str) -> None:
        msg = message.strip()
        self._error_label.setText(msg)
        self._error_label.setVisible(bool(msg))

    def refresh_texts(self) -> None:
        self._refresh_texts()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #0f172a; color: #f8fafc; }
            QLabel#eyeBadge {
                min-width: 92px; max-width: 92px;
                min-height: 92px; max-height: 92px;
                background: transparent;
            }
            QLabel#title { font-size: 42px; font-weight: 700; background: transparent; }
            QLabel#subtitle { color: #9caecb; font-size: 16px; background: transparent; }
            QLabel#terms { color: #94a3b8; font-size: 12px; background: transparent; }
            QLabel#termsCheckLabel { color: #cbd5e1; font-size: 13px; background: transparent; }
            QLabel#error { color: #ef4444; font-size: 12px; background: transparent; }
            QWidget#termsPanel {
                background: #111c33;
                border: 1px solid #28406f;
                border-radius: 10px;
            }
            QCheckBox { background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QPushButton#google {
                background: #ffffff; color: #111827; border: none;
                border-radius: 10px; padding: 10px 14px; font-size: 16px; font-weight: 700;
            }
            QPushButton#google:disabled { background: #a8b3c4; color: #4b5563; }
            QPushButton#google:hover:!disabled { background: #e5e7eb; }
            QPushButton#quit {
                background: transparent; color: #64748b; border: none;
                padding: 6px; font-size: 12px;
            }
            QPushButton#quit:hover { color: #cbd5e1; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 24, 48, 32)
        root.setSpacing(14)
        root.addSpacing(10)

        self._title = QLabel()
        self._title.setObjectName("title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._title)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("subtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        root.addSpacing(8)

        self._eye_badge = QLabel()
        self._eye_badge.setObjectName("eyeBadge")
        self._eye_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon = self._load_app_icon()
        if app_icon is not None:
            self._eye_badge.setPixmap(app_icon)
        root.addWidget(self._eye_badge, alignment=Qt.AlignmentFlag.AlignHCenter)

        root.addStretch()

        self._terms_panel = self._build_terms_panel()
        root.addWidget(self._terms_panel)

        self._login_btn = QPushButton()
        self._login_btn.setObjectName("google")
        self._login_btn.setEnabled(False)
        self._login_btn.clicked.connect(self.login_requested.emit)
        root.addWidget(self._login_btn)

        self._cancel_btn = QPushButton()
        self._cancel_btn.setObjectName("quit")
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        root.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addSpacing(6)

    def _refresh_texts(self) -> None:
        self._title.setText("ProgressEye")
        self._subtitle.setText(t("login_start_subtitle"))
        self._terms_check_label.setText(t("login_terms_check_label"))
        self._terms_html.setText(t("login_terms_html"))
        self._login_btn.setText(t("login_start_google"))
        self._cancel_btn.setText(t("login_start_cancel"))

    def _on_terms_changed(self) -> None:
        self._login_btn.setEnabled(self._terms_check.isChecked())

    def _load_app_icon(self) -> QPixmap | None:
        if not _APP_ICON_PATH.exists():
            return None
        pix = QPixmap(str(_APP_ICON_PATH))
        if pix.isNull():
            return None
        return pix.scaled(
            _APP_ICON_SIZE,
            _APP_ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _build_terms_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("termsPanel")
        terms_layout = QVBoxLayout(panel)
        terms_layout.setContentsMargins(12, 10, 12, 10)
        terms_layout.setSpacing(6)

        terms_check_row = QWidget()
        terms_check_row_layout = QHBoxLayout(terms_check_row)
        terms_check_row_layout.setContentsMargins(0, 0, 0, 0)
        terms_check_row_layout.setSpacing(8)

        self._terms_check = QCheckBox("")
        self._terms_check.setStyleSheet("padding-left: 2px;")
        self._terms_check.stateChanged.connect(self._on_terms_changed)

        self._terms_check_label = QLabel()
        self._terms_check_label.setObjectName("termsCheckLabel")
        self._terms_check_label.setWordWrap(True)
        self._terms_check_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        terms_check_row_layout.addWidget(
            self._terms_check, alignment=Qt.AlignmentFlag.AlignTop
        )
        terms_check_row_layout.addWidget(self._terms_check_label, stretch=1)
        terms_layout.addWidget(terms_check_row)

        self._terms_html = QLabel()
        self._terms_html.setObjectName("terms")
        self._terms_html.setTextFormat(Qt.TextFormat.RichText)
        self._terms_html.setOpenExternalLinks(True)
        self._terms_html.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._terms_html.setWordWrap(True)
        terms_layout.addWidget(self._terms_html)

        return panel
