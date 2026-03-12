"""원격 shutdown/sleep 명령 수신 시 PC 사용자에게 보여주는 확인 다이얼로그."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]


class RemoteCommandDialog(QDialog):
    """카운트다운 타이머가 있는 원격 명령 확인 다이얼로그.

    COUNTDOWN초 후 자동 수락, 취소 버튼으로 중단 가능.
    """

    COUNTDOWN = 30

    def __init__(self, cmd_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cmd_type = cmd_type
        self._remaining = self.COUNTDOWN

        is_shutdown = cmd_type == "shutdown"
        self.setWindowTitle(
            t("remote_shutdown_title") if is_shutdown else t("remote_sleep_title")
        )
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 16)

        self._body = QLabel()
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_body()
        layout.addWidget(self._body)

        buttons = QDialogButtonBox()
        self._btn_now = buttons.addButton(
            t("remote_cmd_now"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._btn_cancel = buttons.addButton(
            t("remote_cmd_cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _update_body(self) -> None:
        cmd_name = (
            t("remote_shutdown_title") if self._cmd_type == "shutdown"
            else t("remote_sleep_title")
        )
        self._body.setText(
            t("remote_cmd_body").format(cmd=cmd_name, n=self._remaining)
        )

    def _tick(self) -> None:
        self._remaining -= 1
        self._update_body()
        if self._remaining <= 0:
            self._timer.stop()
            self.accept()

    def reject(self) -> None:
        self._timer.stop()
        super().reject()
