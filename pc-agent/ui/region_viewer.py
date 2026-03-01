"""탐지된 바 영역 전체 화면 뷰어 (모니터별 오버레이)."""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication, QPixmap
from PyQt6.QtWidgets import QWidget

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]


class _ViewerPane(QWidget):
    def __init__(
        self, owner: "RegionViewer", geo: QRect, shot: QPixmap, dark: QPixmap
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
        self.setGeometry(geo)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, a0) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.drawPixmap(
            self.rect(),
            self._dark,
            QRect(0, 0, self._shot.width(), self._shot.height()),
        )

        rr = self._owner._region_rect_global.intersected(self._geo)
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

        # 영역 테두리
        if not rr.isEmpty():
            local_rr = QRect(
                rr.x() - self._geo.x(), rr.y() - self._geo.y(), rr.width(), rr.height()
            )
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.drawRect(local_rr)

        # 바 테두리
        if self._owner._bar_rect_global is not None:
            br = self._owner._bar_rect_global.intersected(self._geo)
            if not br.isEmpty():
                local_br = QRect(
                    br.x() - self._geo.x(),
                    br.y() - self._geo.y(),
                    br.width(),
                    br.height(),
                )
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawRect(local_br)
                inner = local_br.adjusted(2, 2, -2, -2)
                painter.setPen(QPen(QColor(0, 255, 255), 2))
                painter.drawRect(inner)

        if self._owner._hint_geo == self._geo:
            hint = t("hint_click_or_esc")
            painter.setFont(QFont("Segoe UI", 12))
            hint_w = 260
            hint_rect = QRect(0, 8, self.width(), 36)
            painter.fillRect(
                (self.width() - hint_w) // 2, 6, hint_w, 32, QColor(0, 0, 0, 180)
            )
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)

        painter.end()

    def mousePressEvent(self, a0) -> None:  # noqa: N802
        self._owner._close_viewer()

    def keyPressEvent(self, a0) -> None:  # noqa: N802
        if a0 is not None and a0.key() == Qt.Key.Key_Escape:
            self._owner._close_viewer()


class RegionViewer(QWidget):
    closed = pyqtSignal()

    def __init__(
        self,
        region_rect: QRect,
        bar_rect: QRect | None,
        progress: float,
        region_type: str = "bar",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        del progress
        del region_type

        primary = QGuiApplication.primaryScreen()
        virtual_geo = (
            primary.virtualGeometry()
            if primary is not None
            else QRect(0, 0, 1920, 1080)
        )
        self._region_rect_global = region_rect.translated(virtual_geo.topLeft())
        self._bar_rect_global = (
            bar_rect.translated(virtual_geo.topLeft()) if bar_rect is not None else None
        )
        self._hint_geo: QRect | None = None
        self._panes: list[_ViewerPane] = []

        for screen in QGuiApplication.screens():
            geo = screen.geometry()
            shot = QPixmap.fromImage(
                screen.grabWindow(
                    sip.voidptr(0), 0, 0, geo.width(), geo.height()
                ).toImage()
            )
            dark = shot.copy()
            painter = QPainter(dark)
            painter.fillRect(dark.rect(), QColor(0, 0, 0, 120))
            painter.end()
            self._panes.append(_ViewerPane(self, geo, shot, dark))

        if self._panes:
            self._hint_geo = self._panes[0].geometry()

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

    def _close_viewer(self) -> None:
        self.hide()
        self.closed.emit()
        self.close()
