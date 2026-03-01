"""영역 선택 오버레이.

전체 화면 스크린샷을 찍어 어둡게 표시하고,
마우스 드래그로 선택한 영역만 원본 밝기로 보여준다.
Windows 호환성을 위해 투명 배경 대신 스크린샷 기반 접근 사용.
"""

from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QGuiApplication,
    QPixmap,
    QScreen,
    QRegion,
)
from PyQt6.QtWidgets import QWidget


from utils.i18n import t
from utils.logger import log


class AreaSelector(QWidget):
    """전체 화면 스크린샷 기반 영역 선택기.

    스크린샷을 찍어 어둡게 표시하고,
    선택 영역만 원본 밝기로 보여준다.
    """

    area_selected = pyqtSignal(dict)
    cancelled = pyqtSignal()

    MIN_WIDTH = 10
    MIN_HEIGHT = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._start_pos: QPoint | None = None
        self._current_pos: QPoint | None = None
        self._selection: QRect | None = None

        # 스크린샷 (오버레이 표시 전에 캡처)
        self._screenshot: QPixmap | None = None
        self._darkened: QPixmap | None = None
        self._virtual_geo: QRect = QRect(0, 0, 1920, 1080)

        self._capture_screen()
        self._setup_window()

    def showEvent(self, event) -> None:  # noqa: N802
        """표시 시 키보드 포커스를 강제 획득한다."""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        # Windows에서 포커스 획득이 지연될 수 있으므로 재시도
        QTimer.singleShot(100, self._ensure_focus)

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
            "스크린샷 캡처: %dx%d",
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )
    def _ensure_focus(self) -> None:
        """포커스가 없으면 다시 획득한다."""
        if not self.hasFocus():
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _setup_window(self) -> None:
        """윈도우 속성을 설정한다."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(self._virtual_geo)

    def paintEvent(self, event) -> None:  # noqa: N802
        """어두운 배경 + 선택 영역(원본 밝기)을 그린다."""
        painter = QPainter(self)

        # 어두운 스크린샷을 배경으로
        if self._darkened is not None:
            painter.drawPixmap(0, 0, self._darkened)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))

        if self._start_pos is not None and self._current_pos is not None:
            rect = QRect(self._start_pos, self._current_pos).normalized()

            # 선택 영역: 원본 밝은 스크린샷으로 그리기
            if self._screenshot is not None:
                painter.drawPixmap(rect, self._screenshot, rect)

            # 선택 영역 테두리 (빨간 외곽 + 시안 내곽 2줄)
            pen_red = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen_red)
            painter.drawRect(rect)
            inner = rect.adjusted(2, 2, -2, -2)
            pen_cyan = QPen(QColor(0, 255, 255), 2)
            painter.setPen(pen_cyan)
            painter.drawRect(inner)

            # 크기 표시 라벨
            w = rect.width()
            h = rect.height()
            label_text = f"{w}×{h}"

            font = QFont("Segoe UI", 11)
            painter.setFont(font)

            # 라벨 배경 (읽기 쉽게)
            label_x = rect.right() + 8
            label_y = rect.bottom() + 6
            if label_x + 80 > self.width():
                label_x = rect.left() + 4
            if label_y + 22 > self.height():
                label_y = rect.top() - 24

            bg_rect = QRect(label_x - 4, label_y, 76, 22)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 160))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_x, label_y + 16, label_text)

            # 안내 텍스트 (상단 중앙)
            hint = t("hint_select_area")
            painter.setFont(QFont("Segoe UI", 12))
            hint_rect = QRect(0, 8, self.width(), 36)
            painter.fillRect(
                (self.width() - 420) // 2,
                6,
                420,
                32,
                QColor(0, 0, 0, 180),
            )
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)

        else:
            # 아직 드래그 시작 전 — 안내 표시
            painter.setFont(QFont("Segoe UI", 13))
            painter.setPen(QColor(255, 255, 255))
            hint_rect = QRect(0, 0, self.width(), self.height())
            painter.fillRect(
                (self.width() - 420) // 2,
                (self.height() - 36) // 2,
                420,
                36,
                QColor(0, 0, 0, 180),
            )
            painter.drawText(
                hint_rect,
                Qt.AlignmentFlag.AlignCenter,
                t("hint_select_area"),
            )

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """드래그 시작."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """드래그 중."""
        if self._start_pos is not None:
            self._current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """드래그 종료 — 영역 확정."""
        if event.button() == Qt.MouseButton.LeftButton and self._start_pos is not None:
            self._current_pos = event.pos()
            rect = QRect(self._start_pos, self._current_pos).normalized()

            if rect.width() < self.MIN_WIDTH or rect.height() < self.MIN_HEIGHT:
                log.info(
                    "선택 영역이 너무 작음 (%dx%d) — 무시",
                    rect.width(),
                    rect.height(),
                )
                self._start_pos = None
                self._current_pos = None
                self.update()
                return

            self._selection = rect
            self._confirm_selection()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """키보드 이벤트 처리."""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selection is not None:
                self._confirm_selection()

    def _confirm_selection(self) -> None:
        """선택을 확정하고 시그널을 발생시킨다."""
        if self._selection is None:
            return
        from ui.screen_mapper import qt_widget_to_mss  # pyright: ignore[reportImplicitRelativeImport]

        result = qt_widget_to_mss(self._selection, self._virtual_geo)
        log.info(
            "영역 선택 완료: %dx%d @ (%d, %d) 모니터=%d",
            result["width"],
            result["height"],
            result["x"],
            result["y"],
            result["monitor"],
        )
        self._pending_result = result
        self.hide()
        QTimer.singleShot(300, self._emit_and_close)

    def _emit_and_close(self) -> None:
        """오버레이 숨김 후 시그널을 발생시키고 닫는다."""
        if hasattr(self, "_pending_result"):
            self.area_selected.emit(self._pending_result)
        self.close()

    def _cancel(self) -> None:
        """선택을 취소한다."""
        log.info("영역 선택 취소")
        self.hide()
        self.cancelled.emit()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        """리소스 정리: 대형 QPixmap을 해제한다."""
        self._screenshot = None
        self._darkened = None
        super().closeEvent(event)
