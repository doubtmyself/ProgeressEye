"""영역 편집 오버레이 (모니터별 오버레이)."""

from __future__ import annotations

import threading
from enum import IntEnum, auto
from typing import Callable

from PyQt6 import sip
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication, QPixmap, QImage
from PyQt6.QtWidgets import QWidget

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


def _to_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


class _Handle(IntEnum):
    TOP_LEFT = auto()
    TOP_MID = auto()
    TOP_RIGHT = auto()
    MID_LEFT = auto()
    MID_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_MID = auto()
    BOTTOM_RIGHT = auto()


_HANDLE_CURSORS: dict[_Handle, Qt.CursorShape] = {
    _Handle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    _Handle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    _Handle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    _Handle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    _Handle.TOP_MID: Qt.CursorShape.SizeVerCursor,
    _Handle.BOTTOM_MID: Qt.CursorShape.SizeVerCursor,
    _Handle.MID_LEFT: Qt.CursorShape.SizeHorCursor,
    _Handle.MID_RIGHT: Qt.CursorShape.SizeHorCursor,
}

_HANDLE_SIZE = 8
_HANDLE_HALF = _HANDLE_SIZE // 2
_MIN_W = 10
_MIN_H = 5


class _EditorPane(QWidget):
    def __init__(
        self, owner: "RegionEditor", geo: QRect, shot: QPixmap, dark: QPixmap
    ) -> None:
        super().__init__()
        self._owner = owner
        self._geo = geo
        self._shot = shot
        self._dark = dark
        self._sx = max(1, shot.width()) / max(1, geo.width())
        self._sy = max(1, shot.height()) / max(1, geo.height())

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self.setGeometry(geo)

    def paintEvent(self, a0) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.drawPixmap(
            self.rect(),
            self._dark,
            QRect(0, 0, self._shot.width(), self._shot.height()),
        )

        rr = self._owner._selection_global.intersected(self._geo)
        if not rr.isEmpty():
            target = QRect(
                rr.x() - self._geo.x(), rr.y() - self._geo.y(), rr.width(), rr.height()
            )
            src = QRect(
                int(target.x() * self._sx),
                int(target.y() * self._sy),
                max(1, int(target.width() * self._sx)),
                max(1, int(target.height() * self._sy)),
            )
            src = src.intersected(QRect(0, 0, self._shot.width(), self._shot.height()))
            if not src.isEmpty():
                painter.drawPixmap(target, self._shot, src)

        # selection border
        if not rr.isEmpty():
            local = QRect(
                rr.x() - self._geo.x(), rr.y() - self._geo.y(), rr.width(), rr.height()
            )
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(local)

        # handles
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(0, 102, 204), 1))
        for hr in self._owner._handle_rects_global().values():
            ir = hr.intersected(self._geo)
            if ir.isEmpty():
                continue
            painter.drawRect(
                QRect(
                    hr.x() - self._geo.x(),
                    hr.y() - self._geo.y(),
                    hr.width(),
                    hr.height(),
                )
            )

        # detected bar region (red fill + border)
        bar_global = self._owner._detected_bar_global
        if bar_global is not None:
            bar_rr = bar_global.intersected(self._geo)
            if not bar_rr.isEmpty():
                bar_local = QRect(
                    bar_rr.x() - self._geo.x(),
                    bar_rr.y() - self._geo.y(),
                    bar_rr.width(),
                    bar_rr.height(),
                )
                painter.setPen(QPen(QColor(255, 60, 60), 2))
                painter.setBrush(QColor(255, 0, 0, 50))
                painter.drawRect(bar_local)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._owner._hint_geo == self._geo:
            self._owner._draw_hud(painter, self._geo)

        painter.end()

    def mousePressEvent(self, a0) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner._mouse_press_global(a0)

    def mouseMoveEvent(self, a0) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner._mouse_move_global(a0)

    def mouseReleaseEvent(self, a0) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner._mouse_release_global(a0)

    def keyPressEvent(self, a0) -> None:  # noqa: N802
        if a0 is None:
            return
        self._owner._key_press_global(a0)


class RegionEditor(QWidget):
    area_edited = pyqtSignal(str, dict)
    cancelled = pyqtSignal()

    def __init__(
        self,
        region_id: str,
        area: dict[str, object],
        bar_detect_fn: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._region_id = region_id
        self._area = area
        self._bar_detect_fn = bar_detect_fn
        self._detected_bar_global: QRect | None = None
        self._panes: list[_EditorPane] = []
        self._hint_geo: QRect | None = None

        self._bar_detect_timer = QTimer(self)
        self._bar_detect_timer.setSingleShot(True)
        self._bar_detect_timer.setInterval(300)
        self._bar_detect_timer.timeout.connect(self._run_bar_detection)

        primary = QGuiApplication.primaryScreen()
        self._virtual_geo = (
            primary.virtualGeometry()
            if primary is not None
            else QRect(0, 0, 1920, 1080)
        )

        from ui.screen_mapper import mss_to_qt_widget  # pyright: ignore[reportImplicitRelativeImport]

        area_for_map: dict[str, int] = {
            "monitor": _to_int(self._area.get("monitor", 0), 0),
            "x": _to_int(self._area.get("x", 0), 0),
            "y": _to_int(self._area.get("y", 0), 0),
            "width": _to_int(self._area.get("width", 1), 1),
            "height": _to_int(self._area.get("height", 1), 1),
        }
        if self._area.get("abs_x") is not None and self._area.get("abs_y") is not None:
            area_for_map["abs_x"] = _to_int(self._area["abs_x"], area_for_map["x"])
            area_for_map["abs_y"] = _to_int(self._area["abs_y"], area_for_map["y"])

        selection_widget = mss_to_qt_widget(area_for_map, self._virtual_geo)
        self._selection_global = selection_widget.translated(
            self._virtual_geo.topLeft()
        )

        self._dragging = False
        self._active_handle: _Handle | None = None
        self._drag_origin = QPoint()
        self._rect_origin = QRect()

        self._capture_panes()

    def _capture_panes(self) -> None:
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
            self._panes.append(_EditorPane(self, geo, shot, dark))
        if self._panes:
            self._hint_geo = self._panes[0].geometry()

    def show(self) -> None:  # noqa: A003
        for pane in self._panes:
            pane.show()
            pane.raise_()
            pane.activateWindow()
        if self._panes:
            self._panes[0].setFocus()
        if self._bar_detect_fn is not None:
            self._bar_detect_timer.start()

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

    def _update_panes(self) -> None:
        for pane in self._panes:
            pane.update()

    def _handle_rects_global(self) -> dict[_Handle, QRect]:
        r = self._selection_global
        cx = r.x() + r.width() // 2
        cy = r.y() + r.height() // 2
        h = _HANDLE_HALF
        return {
            _Handle.TOP_LEFT: QRect(
                r.left() - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.TOP_MID: QRect(cx - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.TOP_RIGHT: QRect(
                r.right() - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.MID_LEFT: QRect(r.left() - h, cy - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.MID_RIGHT: QRect(r.right() - h, cy - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.BOTTOM_LEFT: QRect(
                r.left() - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.BOTTOM_MID: QRect(
                cx - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.BOTTOM_RIGHT: QRect(
                r.right() - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
        }

    def _hit_handle(self, pos_global: QPoint) -> _Handle | None:
        margin = 3
        for handle, rect in self._handle_rects_global().items():
            if rect.adjusted(-margin, -margin, margin, margin).contains(pos_global):
                return handle
        return None

    def _mouse_press_global(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.globalPosition().toPoint()
        handle = self._hit_handle(pos)
        if handle is not None:
            self._active_handle = handle
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = QRect(self._selection_global)
            self._bar_detect_timer.stop()
            self._detected_bar_global = None
            return
        if self._selection_global.contains(pos):
            self._active_handle = None
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = QRect(self._selection_global)
            self._bar_detect_timer.stop()
            self._detected_bar_global = None

    def _mouse_move_global(self, event) -> None:
        pos = event.globalPosition().toPoint()
        if self._dragging:
            dx = pos.x() - self._drag_origin.x()
            dy = pos.y() - self._drag_origin.y()
            if self._active_handle is not None:
                self._resize_by_handle(self._active_handle, dx, dy)
            else:
                self._move_selection(dx, dy)
            self._update_panes()
            return

        handle = self._hit_handle(pos)
        cursor = Qt.CursorShape.ArrowCursor
        if handle is not None:
            cursor = _HANDLE_CURSORS[handle]
        elif self._selection_global.contains(pos):
            cursor = Qt.CursorShape.SizeAllCursor
        for pane in self._panes:
            pane.setCursor(cursor)

    def _mouse_release_global(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._active_handle = None
            if self._bar_detect_fn is not None:
                self._bar_detect_timer.start()

    def _run_bar_detection(self) -> None:
        """현재 선택 영역에서 바를 탐지하고 결과를 오버레이에 표시한다 (백그라운드)."""
        if self._bar_detect_fn is None:
            return
        sel = self._selection_global
        # 선택 영역을 포함하는 첫 번째 패인 찾기
        pane_data = None
        for pane in self._panes:
            rr = sel.intersected(pane._geo)
            if not rr.isEmpty():
                pane_data = (pane, rr)
                break
        if pane_data is None:
            return
        pane, rr = pane_data
        # 패인 스크린샷에서 선택 영역 크롭
        src = QRect(
            int((rr.x() - pane._geo.x()) * pane._sx),
            int((rr.y() - pane._geo.y()) * pane._sy),
            max(1, int(rr.width() * pane._sx)),
            max(1, int(rr.height() * pane._sy)),
        )
        src = src.intersected(QRect(0, 0, pane._shot.width(), pane._shot.height()))
        if src.isEmpty():
            return
        cropped = pane._shot.copy(src)
        qimage = cropped.toImage().convertToFormat(QImage.Format.Format_RGB888)
        w, h = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.bytesPerLine() * h)
        raw = bytes(ptr)
        sx, sy = pane._sx, pane._sy
        rx, ry = rr.x(), rr.y()
        fn = self._bar_detect_fn

        def _detect() -> None:
            try:
                from PIL import Image as PILImage  # pyright: ignore[reportImplicitRelativeImport]
                pil_img = PILImage.frombuffer("RGB", (w, h), raw)
                result = fn(pil_img)
            except Exception:
                result = None
            detected: QRect | None = None
            if result is not None:
                detected = QRect(
                    int(rx + result.left / sx),
                    int(ry + result.top / sy),
                    max(1, int((result.right - result.left) / sx)),
                    max(1, int((result.bottom - result.top) / sy)),
                )
            QTimer.singleShot(0, lambda: self._apply_bar_result(detected))

        threading.Thread(target=_detect, daemon=True).start()

    def _apply_bar_result(self, detected: QRect | None) -> None:
        self._detected_bar_global = detected
        self._update_panes()

    def _key_press_global(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm_edit()

    def _resize_by_handle(self, handle: _Handle, dx: int, dy: int) -> None:
        orig = self._rect_origin
        left, top, right, bottom = orig.left(), orig.top(), orig.right(), orig.bottom()
        if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
            top = orig.top() + dy
        if handle in (_Handle.BOTTOM_LEFT, _Handle.BOTTOM_MID, _Handle.BOTTOM_RIGHT):
            bottom = orig.bottom() + dy
        if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
            left = orig.left() + dx
        if handle in (_Handle.TOP_RIGHT, _Handle.MID_RIGHT, _Handle.BOTTOM_RIGHT):
            right = orig.right() + dx

        if right - left < _MIN_W:
            if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
                left = right - _MIN_W
            else:
                right = left + _MIN_W
        if bottom - top < _MIN_H:
            if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
                top = bottom - _MIN_H
            else:
                bottom = top + _MIN_H

        vg = self._virtual_geo
        left = max(vg.left(), left)
        top = max(vg.top(), top)
        right = min(vg.right(), right)
        bottom = min(vg.bottom(), bottom)
        self._selection_global = QRect(
            QPoint(left, top), QPoint(right, bottom)
        ).normalized()

    def _move_selection(self, dx: int, dy: int) -> None:
        vg = self._virtual_geo
        w = self._rect_origin.width()
        h = self._rect_origin.height()
        new_x = self._rect_origin.x() + dx
        new_y = self._rect_origin.y() + dy
        new_x = max(vg.left(), min(new_x, vg.right() - w + 1))
        new_y = max(vg.top(), min(new_y, vg.bottom() - h + 1))
        self._selection_global = QRect(new_x, new_y, w, h)

    def _draw_hud(self, painter: QPainter, geo: QRect) -> None:
        r = QRect(
            self._selection_global.x() - geo.x(),
            self._selection_global.y() - geo.y(),
            self._selection_global.width(),
            self._selection_global.height(),
        )
        w = r.width()
        h = r.height()
        label_text = f"{w}×{h}"
        painter.setFont(QFont("Segoe UI", 11))
        label_x = r.right() + 8
        label_y = r.bottom() + 6
        if label_x + 80 > geo.width():
            label_x = r.left() + 4
        if label_y + 22 > geo.height():
            label_y = r.top() - 24
        painter.fillRect(QRect(label_x - 4, label_y, 76, 22), QColor(0, 0, 0, 160))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(label_x, label_y + 16, label_text)

        hint = t("hint_edit_region")
        painter.setFont(QFont("Segoe UI", 12))
        hint_w = 460
        hint_rect = QRect(0, 8, geo.width(), 36)
        painter.fillRect(
            (geo.width() - hint_w) // 2, 6, hint_w, 32, QColor(0, 0, 0, 180)
        )
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)

    def _confirm_edit(self) -> None:
        from ui.screen_mapper import qt_widget_to_mss  # pyright: ignore[reportImplicitRelativeImport]

        selection_widget = self._selection_global.translated(
            -self._virtual_geo.topLeft()
        )
        result = qt_widget_to_mss(selection_widget, self._virtual_geo)
        log.info(
            "영역 편집 완료: %s → %dx%d @ (%d, %d) 모니터=%d",
            self._region_id,
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
        if hasattr(self, "_pending_result"):
            self.area_edited.emit(self._region_id, self._pending_result)
        self.close()

    def _cancel(self) -> None:
        log.info("영역 편집 취소: %s", self._region_id)
        self.hide()
        self.cancelled.emit()
        self.close()
