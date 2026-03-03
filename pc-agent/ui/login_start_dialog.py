"""Startup login panel without embedded WebEngine."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]


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
            QWidget { background: #101622; color: #f8fafc; }
            QLabel#title { font-size: 42px; font-weight: 700; }
            QLabel#subtitle { color: #94a3b8; font-size: 16px; }
            QLabel#terms { color: #94a3b8; font-size: 12px; }
            QLabel#error { color: #ef4444; font-size: 12px; }
            QCheckBox { color: #cbd5e1; font-size: 13px; }
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
        root.setContentsMargins(48, 36, 48, 36)
        root.setSpacing(14)
        root.addStretch()

        self._title = QLabel()
        self._title.setObjectName("title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._title)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("subtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        self._terms_check = QCheckBox()
        self._terms_check.stateChanged.connect(self._on_terms_changed)
        root.addWidget(self._terms_check, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._terms_html = QLabel()
        self._terms_html.setObjectName("terms")
        self._terms_html.setTextFormat(Qt.TextFormat.RichText)
        self._terms_html.setOpenExternalLinks(True)
        self._terms_html.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._terms_html.setWordWrap(True)
        root.addWidget(self._terms_html)

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

        root.addStretch()

    def _refresh_texts(self) -> None:
        self._title.setText("ProgressEye")
        self._subtitle.setText(t("login_start_subtitle"))
        self._terms_check.setText(t("login_start_message"))
        self._terms_html.setText(t("login_terms_html"))
        self._login_btn.setText(t("login_start_google"))
        self._cancel_btn.setText(t("login_start_cancel"))

    def _on_terms_changed(self) -> None:
        self._login_btn.setEnabled(self._terms_check.isChecked())
