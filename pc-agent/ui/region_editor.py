"""영역 편집 오버레이.

등록된 모니터링 영역을 전체 화면 위에 표시하고,
파워포인트 스타일의 8개 리사이즈 핸들로 크기 조절/이동을 지원한다.
AreaSelector와 동일한 스크린샷 기반 접근 방식 사용.
"""

from enum import IntEnum, auto

import mss as mss_lib
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QGuiApplication,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from utils.logger import log


class _Handle(IntEnum):
    """리사이즈 핸들 위치."""

    TOP_LEFT = auto()
    TOP_MID = auto()
    TOP_RIGHT = auto()
    MID_LEFT = auto()
    MID_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_MID = auto()
    BOTTOM_RIGHT = auto()


# 핸들별 커서 매핑
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

# 핸들 크기 (px)
_HANDLE_SIZE = 8
_HANDLE_HALF = _HANDLE_SIZE // 2

# 영역 최소 크기 (px)
_MIN_W = 10
_MIN_H = 5


class RegionEditor(QWidget):
    """등록된 영역의 위치/크기를 편집하는 전체 화면 오버레이.

    AreaSelector와 동일하게 스크린샷을 캡처하여 배경으로 사용하고,
    편집 대상 영역만 원본 밝기로 표시한다.
    8개 리사이즈 핸들로 크기 조절, 영역 내부 드래그로 이동 가능.
    """

    area_edited = pyqtSignal(str, dict)
    cancelled = pyqtSignal()

    def __init__(
        self,
        region_id: str,
        area: dict,
        parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            region_id: 편집 대상 영역 ID.
            area: 영역 정보 (monitor, x, y, width, height).
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._region_id = region_id
        self._area = area

        # 스크린샷 (오버레이 표시 전에 캡처)
        self._screenshot: QPixmap | None = None
        self._darkened: QPixmap | None = None
        self._virtual_geo: QRect = QRect(0, 0, 1920, 1080)

        # 편집 중인 선택 영역 (Qt 위젯 좌표)
        self._selection: QRect = QRect()

        # 드래그 상태
        self._dragging = False
        self._active_handle: _Handle | None = None
        self._drag_origin: QPoint = QPoint()
        self._rect_origin: QRect = QRect()

        self._capture_screen()
        self._init_selection()
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
            "RegionEditor 스크린샷 캡처: %dx%d",
            self._virtual_geo.width(),
            self._virtual_geo.height(),
        )

    def _init_selection(self) -> None:
        """mss 좌표 → Qt 위젯 좌표로 역변환하여 초기 선택 영역을 설정한다."""
        try:
            with mss_lib.mss() as sct:
                full = sct.monitors[0]  # mss 전체 가상 데스크톱
                mon_idx = self._area.get("monitor", 0)

                # mss 로컬 좌표 → mss 전역 좌표
                if mon_idx > 0 and mon_idx < len(sct.monitors):
                    mon = sct.monitors[mon_idx]
                    mss_global_x = self._area["x"] + mon["left"]
                    mss_global_y = self._area["y"] + mon["top"]
                else:
                    mss_global_x = self._area["x"]
                    mss_global_y = self._area["y"]

                # mss 전역 → Qt 위젯 좌표
                scale_x = self._virtual_geo.width() / full["width"]
                scale_y = self._virtual_geo.height() / full["height"]
                qt_x = int((mss_global_x - full["left"]) * scale_x)
                qt_y = int((mss_global_y - full["top"]) * scale_y)
                qt_w = int(self._area["width"] * scale_x)
                qt_h = int(self._area["height"] * scale_y)

        except Exception as e:
            log.warning("mss 역변환 실패: %s — fallback", e)
            qt_x = self._area["x"]
            qt_y = self._area["y"]
            qt_w = self._area["width"]
            qt_h = self._area["height"]

        self._selection = QRect(qt_x, qt_y, qt_w, qt_h)
        log.debug(
            "초기 선택 영역 (Qt): %d,%d %dx%d",
            qt_x,
            qt_y,
            qt_w,
            qt_h,
        )

    def _setup_window(self) -> None:
        """윈도우 속성을 설정한다."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setGeometry(self._virtual_geo)
        self.setMouseTracking(True)

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

    # ── 핸들 히트 테스트 ──────────────────────────────────────

    def _handle_rects(self) -> dict[_Handle, QRect]:
        """8개 핸들의 QRect를 계산한다."""
        r = self._selection
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

    def _hit_handle(self, pos: QPoint) -> _Handle | None:
        """마우스 위치가 핸들 위에 있으면 해당 핸들을 반환한다."""
        # 히트 판정을 약간 넉넉하게 (±3px)
        margin = 3
        for handle, rect in self._handle_rects().items():
            expanded = rect.adjusted(-margin, -margin, margin, margin)
            if expanded.contains(pos):
                return handle
        return None

    # ── 페인팅 ────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        """어두운 배경 + 선택 영역(원본 밝기) + 핸들을 그린다."""
        painter = QPainter(self)

        # 어두운 스크린샷을 배경으로
        if self._darkened is not None:
            painter.drawPixmap(0, 0, self._darkened)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))

        r = self._selection

        # 선택 영역: 원본 밝은 스크린샷으로 그리기
        if self._screenshot is not None:
            painter.drawPixmap(r, self._screenshot, r)

        # 테두리: 빨간 외곽 2px + 시안 내곽 2px
        pen_red = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen_red)
        painter.drawRect(r)

        inner = r.adjusted(2, 2, -2, -2)
        pen_cyan = QPen(QColor(0, 255, 255), 2)
        painter.setPen(pen_cyan)
        painter.drawRect(inner)

        # 8개 핸들 그리기 (흰색 정사각형 + 파란 테두리)
        handle_pen = QPen(QColor(0, 102, 204), 1)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(handle_pen)
        for rect in self._handle_rects().values():
            painter.drawRect(rect)

        # 크기 표시 라벨 (우측 하단)
        w = r.width()
        h = r.height()
        label_text = f"{w}\u00d7{h}"

        font = QFont("Segoe UI", 11)
        painter.setFont(font)

        label_x = r.right() + 8
        label_y = r.bottom() + 6
        if label_x + 80 > self.width():
            label_x = r.left() + 4
        if label_y + 22 > self.height():
            label_y = r.top() - 24

        bg_rect = QRect(label_x - 4, label_y, 76, 22)
        painter.fillRect(bg_rect, QColor(0, 0, 0, 160))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(label_x, label_y + 16, label_text)

        # 안내 텍스트 (상단 중앙)
        hint = "드래그로 이동/크기 조절  |  Enter: 확정  |  ESC: 취소"
        painter.setFont(QFont("Segoe UI", 12))
        hint_w = 460
        hint_rect = QRect(0, 8, self.width(), 36)
        painter.fillRect(
            (self.width() - hint_w) // 2,
            6,
            hint_w,
            32,
            QColor(0, 0, 0, 180),
        )
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignHCenter, hint)

        painter.end()

    # ── 마우스 이벤트 ──────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """드래그 시작 — 핸들 또는 영역 내부를 판별한다."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()

        # 핸들 히트 체크
        handle = self._hit_handle(pos)
        if handle is not None:
            self._active_handle = handle
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = QRect(self._selection)
            return

        # 영역 내부 → 이동
        if self._selection.contains(pos):
            self._active_handle = None
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = QRect(self._selection)
            return

        # 영역 밖 → 무시

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """드래그 중 — 리사이즈 또는 이동."""
        pos = event.pos()

        if self._dragging:
            dx = pos.x() - self._drag_origin.x()
            dy = pos.y() - self._drag_origin.y()

            if self._active_handle is not None:
                self._resize_by_handle(self._active_handle, dx, dy)
            else:
                self._move_selection(dx, dy)

            self.update()
            return

        # 드래그 중이 아닐 때: 커서 변경
        handle = self._hit_handle(pos)
        if handle is not None:
            self.setCursor(_HANDLE_CURSORS[handle])
        elif self._selection.contains(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """드래그 종료."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._active_handle = None

    # ── 키보드 이벤트 ─────────────────────────────────────────

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """키보드 이벤트 처리."""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm_edit()

    # ── 리사이즈 / 이동 ──────────────────────────────────────

    def _resize_by_handle(self, handle: _Handle, dx: int, dy: int) -> None:
        """핸들 종류에 따라 선택 영역을 리사이즈한다."""
        orig = self._rect_origin

        left = orig.left()
        top = orig.top()
        right = orig.right()
        bottom = orig.bottom()

        # 각 핸들이 움직이는 변
        if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
            top = orig.top() + dy
        if handle in (_Handle.BOTTOM_LEFT, _Handle.BOTTOM_MID, _Handle.BOTTOM_RIGHT):
            bottom = orig.bottom() + dy
        if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
            left = orig.left() + dx
        if handle in (_Handle.TOP_RIGHT, _Handle.MID_RIGHT, _Handle.BOTTOM_RIGHT):
            right = orig.right() + dx

        # 최소 크기 제한
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

        self._selection = QRect(
            QPoint(left, top),
            QPoint(right, bottom),
        )

    def _move_selection(self, dx: int, dy: int) -> None:
        """영역을 이동한다 (화면 밖 방지)."""
        new_x = self._rect_origin.x() + dx
        new_y = self._rect_origin.y() + dy
        w = self._rect_origin.width()
        h = self._rect_origin.height()

        # 화면 경계 클램프
        max_x = self.width() - w
        max_y = self.height() - h
        new_x = max(0, min(new_x, max_x))
        new_y = max(0, min(new_y, max_y))

        self._selection = QRect(new_x, new_y, w, h)

    # ── 확정 / 취소 ──────────────────────────────────────────

    def _confirm_edit(self) -> None:
        """편집을 확정하고 mss 좌표로 변환하여 시그널을 발생시킨다."""
        # Qt 위젯 좌표 → mss 물리 좌표 변환 (AreaSelector._confirm_selection 동일 로직)
        try:
            with mss_lib.mss() as sct:
                full = sct.monitors[0]

                scale_x = full["width"] / self._virtual_geo.width()
                scale_y = full["height"] / self._virtual_geo.height()

                mss_x = int(self._selection.x() * scale_x) + full["left"]
                mss_y = int(self._selection.y() * scale_y) + full["top"]
                mss_w = max(1, int(self._selection.width() * scale_x))
                mss_h = max(1, int(self._selection.height() * scale_y))

                # 중심점이 속한 mss 모니터 찾기
                cx = mss_x + mss_w // 2
                cy = mss_y + mss_h // 2

                monitor_idx = 0
                local_x = mss_x
                local_y = mss_y

                for i, mon in enumerate(sct.monitors[1:], 1):
                    if (
                        mon["left"] <= cx < mon["left"] + mon["width"]
                        and mon["top"] <= cy < mon["top"] + mon["height"]
                    ):
                        monitor_idx = i
                        local_x = mss_x - mon["left"]
                        local_y = mss_y - mon["top"]
                        break

        except Exception as e:
            log.warning("mss 좌표 변환 실패: %s — fallback", e)
            monitor_idx = self._area.get("monitor", 0)
            local_x = self._selection.x() + self._virtual_geo.x()
            local_y = self._selection.y() + self._virtual_geo.y()
            mss_w = self._selection.width()
            mss_h = self._selection.height()

        result = {
            "x": local_x,
            "y": local_y,
            "width": mss_w,
            "height": mss_h,
            "monitor": monitor_idx,
        }
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
        QTimer.singleShot(300, self._emit_and_close)

    def _emit_and_close(self) -> None:
        """오버레이 숨김 후 시그널을 발생시키고 닫는다."""
        if hasattr(self, "_pending_result"):
            self.area_edited.emit(self._region_id, self._pending_result)
        self.close()

    def _cancel(self) -> None:
        """편집을 취소한다."""
        log.info("영역 편집 취소: %s", self._region_id)
        self.hide()
        self.cancelled.emit()
        self.close()
