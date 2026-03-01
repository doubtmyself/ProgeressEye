"""영역 선택 오버레이.

전체 화면 스크린샷을 찍어 어둡게 표시하고,
마우스 드래그로 선택한 영역만 원본 밝기로 보여준다.
Windows 호환성을 위해 투명 배경 대신 스크린샷 기반 접근 사용.
"""

from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtWidgets import QWidget

from ui.overlay_base import OverlayBase  # pyright: ignore[reportImplicitRelativeImport]
from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class AreaSelector(OverlayBase):
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

        self._capture_screen()
        self._setup_overlay(cursor=Qt.CursorShape.CrossCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        """어두운 배경 + 선택 영역(원본 밝기)을 그린다."""
        painter = QPainter(self)
        self._draw_darkened_background(painter)

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
