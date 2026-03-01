"""전체 화면 오버레이 베이스 클래스.

AreaSelector, RegionEditor, RegionViewer가 공통으로 사용하는
스크린 캡처, 윈도우 설정, 포커스 관리, 리소스 정리 로직을 제공한다.
"""

from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QGuiApplication, QPixmap
from PyQt6.QtWidgets import QWidget

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class OverlayBase(QWidget):
    """전체 화면 스크린샷 기반 오버레이의 공통 베이스.

    서브클래스는 ``__init__`` 에서 ``_capture_screen()`` →
    (필요 시 추가 초기화) → ``_setup_overlay()`` 순으로 호출한다.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._screenshot: QPixmap | None = None
        self._darkened: QPixmap | None = None
        self._virtual_geo: QRect = QRect(0, 0, 1920, 1080)

    # ── 스크린 캡처 (공통) ────────────────────────────────────

    def _capture_screen(self) -> None:
        """오버레이 표시 전에 전체 가상 화면을 캡처한다."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        self._virtual_geo = screen.virtualGeometry()

        # 전체 가상 데스크톱 스크린샷
        self._screenshot = screen.grabWindow(
            0,
            self._virtual_geo.x(),
            self._virtual_geo.y(),
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )

        # 어두운 버전 생성
        self._darkened = self._screenshot.copy()
        painter = QPainter(self._darkened)
        painter.fillRect(self._darkened.rect(), QColor(0, 0, 0, 120))
        painter.end()

        log.debug(
            "오버레이 스크린샷 캡처: %dx%d",
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )

    # ── 윈도우 설정 (공통) ────────────────────────────────────

    def _setup_overlay(
        self,
        *,
        cursor: Qt.CursorShape = Qt.CursorShape.ArrowCursor,
        mouse_tracking: bool = False,
    ) -> None:
        """프레임리스 전체 화면 오버레이 윈도우를 설정한다.

        Args:
            cursor: 기본 커서 모양.
            mouse_tracking: 마우스 트래킹 활성화 여부.
        """
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(cursor)
        self.setGeometry(self._virtual_geo)
        if mouse_tracking:
            self.setMouseTracking(True)

    # ── 포커스 관리 (공통) ────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        """표시 시 키보드 포커스를 강제 획득한다."""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        # Windows에서 포커스 획득이 지연될 수 있으므로 재시도
        QTimer.singleShot(100, self._ensure_focus)

    def _ensure_focus(self) -> None:
        """포커스가 없으면 다시 획득한다."""
        if not self.hasFocus():
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ── 리소스 정리 (공통) ────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        """리소스 정리: 대형 QPixmap을 해제한다."""
        self._screenshot = None
        self._darkened = None
        super().closeEvent(event)

    # ── 페인팅 헬퍼 (공통) ────────────────────────────────────

    def _draw_darkened_background(self, painter: QPainter) -> None:
        """어두운 스크린샷 또는 검정 배경을 그린다."""
        if self._darkened is not None:
            painter.drawPixmap(0, 0, self._darkened)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
