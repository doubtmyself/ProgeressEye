"""탐지된 바 영역 전체 화면 뷰어.

등록된 영역을 원본 밝기로, 탐지된 바를 빨간 사각형으로 표시하는
읽기 전용 전체 화면 오버레이. AreaSelector와 동일한 스크린샷 기반 패턴.
"""

from PyQt6.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QGuiApplication,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from utils.i18n import t
from utils.logger import log



class RegionViewer(QWidget):
    """전체 화면 오버레이로 탐지된 바 영역을 표시한다.

    어두운 배경 위에 등록된 영역을 밝게 표시하고,
    그 안에서 탐지된 프로그래스 바를 빨간 사각형으로 표시한다.
    """

    closed = pyqtSignal()

    def __init__(
        self,
        region_rect: QRect,
        bar_rect: QRect | None,
        progress: float,
        region_type: str = "bar",
        parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            region_rect: 등록된 영역 (Qt 위젯 좌표).
            bar_rect: 탐지된 바 영역 (Qt 위젯 좌표, 절대). None이면 바 미탐지.
            progress: 현재 진행률 (%).
            region_type: 영역 타입 ("bar" 또는 "ocr").
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._region_rect = region_rect
        self._bar_rect = bar_rect
        self._progress = progress
        self._region_type = region_type

        # 스크린샷 (오버레이 표시 전에 캡처)
        self._screenshot: QPixmap | None = None
        self._darkened: QPixmap | None = None
        self._virtual_geo: QRect = QRect(0, 0, 1920, 1080)

        self._capture_screen()
        self._setup_window()

    # ── 초기화 ─────────────────────────────────────────────

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
            "RegionViewer 스크린샷 캡처: %dx%d",
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )
    def _setup_window(self) -> None:
        """윈도우 속성을 설정한다."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setGeometry(self._virtual_geo)

    # ── 이벤트: 표시/포커스 ──────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        """표시 시 키보드 포커스를 강제 획득한다."""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        QTimer.singleShot(100, self._ensure_focus)

    def _ensure_focus(self) -> None:
        """포커스가 없으면 다시 획득한다."""
        if not self.hasFocus():
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ── 페인팅 ────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        """어두운 배경 + 등록 영역(원본 밝기) + 바 영역(빨간 사각형)을 그린다."""
        painter = QPainter(self)

        # 어두운 스크린샷을 배경으로
        if self._darkened is not None:
            painter.drawPixmap(0, 0, self._darkened)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))

        r = self._region_rect

        # 등록 영역: 원본 밝은 스크린샷으로 그리기
        if self._screenshot is not None:
            painter.drawPixmap(r, self._screenshot, r)

        # 등록 영역 테두리: 흰색 1px
        pen_white = QPen(QColor(255, 255, 255, 180), 1)
        painter.setPen(pen_white)
        painter.drawRect(r)

        # 바 영역: 빨간(255,0,0) 2px + 시안(0,255,255) 2px 이중 사각형
        if self._bar_rect is not None:
            pen_red = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen_red)
            painter.drawRect(self._bar_rect)

            inner = self._bar_rect.adjusted(2, 2, -2, -2)
            pen_cyan = QPen(QColor(0, 255, 255), 2)
            painter.setPen(pen_cyan)
            painter.drawRect(inner)

        elif self._region_type != "ocr":
            # 바 미탐지 — 영역 중앙에 안내 (OCR은 표시 안 함)
            painter.setFont(QFont("Segoe UI", 12))
            painter.setPen(QColor(255, 100, 100))
            no_bar_text = t("no_bar_detected")
            no_bar_rect = QRect(r.left(), r.bottom() + 8, 280, 26)
            if no_bar_rect.bottom() > self.height():
                no_bar_rect = QRect(r.left(), r.top() - 28, 280, 26)
            painter.fillRect(no_bar_rect, QColor(0, 0, 0, 200))
            painter.drawText(
                no_bar_rect.left() + 4, no_bar_rect.top() + 19, no_bar_text
            )

        # 안내 텍스트 (상단 중앙): "클릭 또는 ESC로 닫기"
        hint = t("hint_click_or_esc")
        painter.setFont(QFont("Segoe UI", 12))
        hint_w = 260
        hint_rect = QRect(0, 8, self.width(), 36)
        painter.fillRect(
            (self.width() - hint_w) // 2,
            6,
            hint_w,
            32,
            QColor(0, 0, 0, 180),
        )
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)

        painter.end()

    # ── 입력 이벤트 ───────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """아무 곳 클릭 → 닫기."""
        self._close_viewer()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """ESC → 닫기."""
        if event.key() == Qt.Key.Key_Escape:
            self._close_viewer()

    def _close_viewer(self) -> None:
        """뷰어를 닫고 시그널을 발생시킨다."""
        self.hide()
        self.closed.emit()
        self.close()
