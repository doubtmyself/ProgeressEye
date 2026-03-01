"""영역 선택 오버레이.

혼합 DPI 환경에서 단일 가상 데스크톱 위젯의 스케일 왜곡을 피하기 위해
모니터별 오버레이 윈도우를 생성해 선택 UI를 렌더링한다.
"""

from __future__ import annotations

from typing import Any

from PyQt6 import sip
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QGuiApplication,
    QPixmap,
    QMouseEvent,
    QKeyEvent,
)
from PyQt6.QtWidgets import QWidget

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class _SelectorPane(QWidget):
    """모니터 1개를 담당하는 오버레이 창."""

    def __init__(
        self,
        owner: "AreaSelector",
        screen_geo: QRect,
        shot: QPixmap,
        dark: QPixmap,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._geo = screen_geo
        self._shot = shot
        self._dark = dark
        self._sx = max(1, shot.width()) / max(1, screen_geo.width())
        self._sy = max(1, shot.height()) / max(1, screen_geo.height())

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(screen_geo)

    def paintEvent(self, a0) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.drawPixmap(
            self.rect(),
            self._dark,
            QRect(0, 0, self._shot.width(), self._shot.height()),
        )

        sel_global = self._owner.selection_global
        if sel_global is not None:
            local_sel = sel_global.intersected(self._geo)
            if not local_sel.isEmpty():
                target = QRect(
                    local_sel.x() - self._geo.x(),
                    local_sel.y() - self._geo.y(),
                    local_sel.width(),
                    local_sel.height(),
                )
                src_x = int(target.x() * self._sx)
                src_y = int(target.y() * self._sy)
                src_w = max(1, int(target.width() * self._sx))
                src_h = max(1, int(target.height() * self._sy))
                src_x = max(0, min(src_x, self._shot.width() - 1))
                src_y = max(0, min(src_y, self._shot.height() - 1))
                src_w = min(src_w, self._shot.width() - src_x)
                src_h = min(src_h, self._shot.height() - src_y)
                painter.drawPixmap(
                    target, self._shot, QRect(src_x, src_y, src_w, src_h)
                )

        # selection border/hint는 시작 pane에서만 표시
        if self._owner.active_hint_geo == self._geo:
            self._owner.draw_hud(painter, self._geo)

        painter.end()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        if a0.button() == Qt.MouseButton.LeftButton:
            self._owner.on_press(a0.globalPosition().toPoint())

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner.on_move(a0.globalPosition().toPoint())

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        if a0.button() == Qt.MouseButton.LeftButton:
            self._owner.on_release(a0.globalPosition().toPoint())

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner.on_key(a0.key())


class AreaSelector(QWidget):
    """모니터별 오버레이 기반 영역 선택기."""

    area_selected = pyqtSignal(dict)
    cancelled = pyqtSignal()

    MIN_WIDTH = 10
    MIN_HEIGHT = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._virtual_geo = QRect(0, 0, 1920, 1080)
        self._panes: list[_SelectorPane] = []
        self._start_global: QPoint | None = None
        self._current_global: QPoint | None = None
        self._pending_result: dict[str, Any] | None = None
        self._active_hint_geo: QRect | None = None
        self._capture_layers()

    @property
    def selection_global(self) -> QRect | None:
        if self._start_global is None or self._current_global is None:
            return None
        start = self._start_global
        current = self._current_global
        return QRect(start, current).normalized()

    @property
    def active_hint_geo(self) -> QRect | None:
        return self._active_hint_geo

    def _capture_layers(self) -> None:
        primary = QGuiApplication.primaryScreen()
        if primary is None:
            return
        self._virtual_geo = primary.virtualGeometry()

        for screen in QGuiApplication.screens():
            geo = screen.geometry()
            shot = QPixmap.fromImage(
                screen.grabWindow(
                    sip.voidptr(0), 0, 0, geo.width(), geo.height()
                ).toImage()
            )
            dark = shot.copy()
            p = QPainter(dark)
            p.fillRect(dark.rect(), QColor(0, 0, 0, 120))
            p.end()
            pane = _SelectorPane(self, geo, shot, dark)
            self._panes.append(pane)

        log.debug(
            "모니터별 영역 선택 오버레이 생성: screens=%d virtual=%dx%d",
            len(self._panes),
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )

    def show(self) -> None:  # noqa: A003
        for pane in self._panes:
            pane.show()
            pane.raise_()
            pane.activateWindow()
        if self._panes:
            self._panes[0].setFocus()

    def hide(self) -> None:  # noqa: A003
        for pane in self._panes:
            pane.hide()

    def close(self) -> bool:  # noqa: A003
        for pane in self._panes:
            pane.close()
        return True

    def deleteLater(self) -> None:  # noqa: N802
        for pane in self._panes:
            pane.deleteLater()
        super().deleteLater()

    def on_press(self, pos_global: QPoint) -> None:
        self._start_global = pos_global
        self._current_global = pos_global
        self._active_hint_geo = self._pane_geo_for_point(pos_global)
        self._update_panes()

    def on_move(self, pos_global: QPoint) -> None:
        if self._start_global is None:
            return
        self._current_global = pos_global
        self._update_panes()

    def on_release(self, pos_global: QPoint) -> None:
        if self._start_global is None:
            return
        self._current_global = pos_global
        sel = self.selection_global
        if sel is None:
            return
        if sel.width() < self.MIN_WIDTH or sel.height() < self.MIN_HEIGHT:
            log.info("선택 영역이 너무 작음 (%dx%d) — 무시", sel.width(), sel.height())
            self._start_global = None
            self._current_global = None
            self._update_panes()
            return

        self._confirm_selection(sel)

    def on_key(self, key: int) -> None:
        if key == Qt.Key.Key_Escape:
            self._cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            sel = self.selection_global
            if sel is not None:
                self._confirm_selection(sel)

    def _pane_geo_for_point(self, pos_global: QPoint) -> QRect | None:
        for pane in self._panes:
            if pane.geometry().contains(pos_global):
                return pane.geometry()
        return self._panes[0].geometry() if self._panes else None

    def _update_panes(self) -> None:
        for pane in self._panes:
            pane.update()

    def draw_hud(self, painter: QPainter, geo: QRect) -> None:
        sel = self.selection_global
        if sel is not None:
            rect = QRect(
                sel.x() - geo.x(),
                sel.y() - geo.y(),
                sel.width(),
                sel.height(),
            )
            pen_red = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen_red)
            painter.drawRect(rect)
            inner = rect.adjusted(2, 2, -2, -2)
            pen_cyan = QPen(QColor(0, 255, 255), 2)
            painter.setPen(pen_cyan)
            painter.drawRect(inner)

            w = rect.width()
            h = rect.height()
            label_text = f"{w}×{h}"
            painter.setFont(QFont("Segoe UI", 11))

            label_x = rect.right() + 8
            label_y = rect.bottom() + 6
            if label_x + 80 > geo.width():
                label_x = rect.left() + 4
            if label_y + 22 > geo.height():
                label_y = rect.top() - 24

            bg_rect = QRect(label_x - 4, label_y, 76, 22)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 160))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_x, label_y + 16, label_text)

            hint = t("hint_select_area")
            painter.setFont(QFont("Segoe UI", 12))
            hint_rect = QRect(0, 8, geo.width(), 36)
            painter.fillRect((geo.width() - 420) // 2, 6, 420, 32, QColor(0, 0, 0, 180))
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)
        else:
            painter.setFont(QFont("Segoe UI", 13))
            painter.setPen(QColor(255, 255, 255))
            hint_rect = QRect(0, 0, geo.width(), geo.height())
            painter.fillRect(
                (geo.width() - 420) // 2,
                (geo.height() - 36) // 2,
                420,
                36,
                QColor(0, 0, 0, 180),
            )
            painter.drawText(
                hint_rect, Qt.AlignmentFlag.AlignCenter, t("hint_select_area")
            )

    def _confirm_selection(self, sel_global: QRect) -> None:
        from ui.screen_mapper import qt_widget_to_mss  # pyright: ignore[reportImplicitRelativeImport]

        sel_widget = sel_global.translated(-self._virtual_geo.topLeft())
        result = qt_widget_to_mss(sel_widget, self._virtual_geo)
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
        QTimer.singleShot(150, self._emit_and_close)

    def _emit_and_close(self) -> None:
        if self._pending_result is not None:
            self.area_selected.emit(self._pending_result)
        self.close()

    def _cancel(self) -> None:
        log.info("영역 선택 취소")
        self.hide()
        self.cancelled.emit()
        self.close()
