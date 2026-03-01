"""전체 화면 오버레이 베이스 클래스.

AreaSelector, RegionEditor, RegionViewer가 공통으로 사용하는
스크린 캡처, 윈도우 설정, 포커스 관리, 리소스 정리 로직을 제공한다.
"""

import mss as mss_lib
from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QGuiApplication, QPixmap, QImage
from PyQt6.QtWidgets import QWidget
from typing import Any

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
        self._screen_layers: list[dict[str, Any]] = []
        self._virtual_geo: QRect = QRect(0, 0, 1920, 1080)

    # ── 스크린 캡처 (공통) ────────────────────────────────────

    def _capture_screen(self) -> None:
        """오버레이 표시 전에 전체 가상 화면을 모니터별로 캡처한다."""
        primary = QGuiApplication.primaryScreen()
        if primary is None:
            return

        self._virtual_geo = primary.virtualGeometry()
        self._screen_layers = []
        qt_screens = QGuiApplication.screens()
        if not qt_screens:
            return

        qt_ranked: list[tuple[int, int, Any]] = []
        for screen in qt_screens:
            geo = screen.geometry()
            rank_x = sum(1 for other in qt_screens if other.geometry().x() < geo.x())
            rank_y = sum(1 for other in qt_screens if other.geometry().y() < geo.y())
            qt_ranked.append((rank_x, rank_y, screen))

        try:
            with mss_lib.mss() as sct:
                monitors = sct.monitors[1:]
                for mon in monitors:
                    mon_rank_x = sum(
                        1 for other in monitors if other["left"] < mon["left"]
                    )
                    mon_rank_y = sum(
                        1 for other in monitors if other["top"] < mon["top"]
                    )

                    best_screen = qt_screens[0]
                    best_score: float | None = None
                    mon_ratio = mon["width"] / max(1, mon["height"])
                    for rank_x, rank_y, screen in qt_ranked:
                        geo = screen.geometry()
                        screen_ratio = geo.width() / max(1, geo.height())
                        rank_error = abs(rank_x - mon_rank_x) + abs(rank_y - mon_rank_y)
                        ratio_error = abs(screen_ratio - mon_ratio)
                        score = (rank_error * 10_000.0) + (ratio_error * 100.0)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_screen = screen

                    geo = best_screen.geometry()
                    widget_rect = QRect(
                        geo.x() - self._virtual_geo.x(),
                        geo.y() - self._virtual_geo.y(),
                        geo.width(),
                        geo.height(),
                    )

                    shot_raw = sct.grab(mon)
                    qimg = QImage(
                        shot_raw.rgb,
                        shot_raw.width,
                        shot_raw.height,
                        shot_raw.width * 3,
                        QImage.Format.Format_RGB888,
                    ).copy()
                    shot = QPixmap.fromImage(qimg)
                    dark = shot.copy()
                    painter = QPainter(dark)
                    painter.fillRect(dark.rect(), QColor(0, 0, 0, 120))
                    painter.end()

                    pix_w = max(1, shot.width())
                    pix_h = max(1, shot.height())
                    sx = pix_w / max(1, widget_rect.width())
                    sy = pix_h / max(1, widget_rect.height())

                    self._screen_layers.append(
                        {
                            "screen_name": best_screen.name(),
                            "widget_rect": widget_rect,
                            "shot": shot,
                            "dark": dark,
                            "pix_w": pix_w,
                            "pix_h": pix_h,
                            "sx": sx,
                            "sy": sy,
                        }
                    )
        except Exception as exc:
            log.warning("mss 오버레이 캡처 실패: %s", exc)

        # 하위 호환(기존 체크 로직)
        if self._screen_layers:
            self._screenshot = self._screen_layers[0]["shot"]
            self._darkened = self._screen_layers[0]["dark"]
        else:
            self._screenshot = None
            self._darkened = None

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
        self._screen_layers.clear()
        super().closeEvent(event)

    # ── 페인팅 헬퍼 (공통) ────────────────────────────────────

    def _draw_darkened_background(self, painter: QPainter) -> None:
        """어두운 스크린샷 또는 검정 배경을 그린다."""
        if self._screen_layers:
            for layer in self._screen_layers:
                target: QRect = layer["widget_rect"]
                source = QRect(0, 0, layer["pix_w"], layer["pix_h"])
                painter.drawPixmap(target, layer["dark"], source)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))

    def _draw_screenshot_region(self, painter: QPainter, rect: QRect) -> None:
        """선택 영역을 원본 밝기로 그린다 (모니터별 DPR 보정)."""
        if not self._screen_layers:
            return

        for layer in self._screen_layers:
            target = rect.intersected(layer["widget_rect"])
            if target.isEmpty():
                continue

            local_x = target.x() - layer["widget_rect"].x()
            local_y = target.y() - layer["widget_rect"].y()
            shot: QPixmap = layer["shot"]

            sx = layer["sx"]
            sy = layer["sy"]
            src_x = int(local_x * sx)
            src_y = int(local_y * sy)
            src_w = int(target.width() * sx)
            src_h = int(target.height() * sy)

            # source clamp (검은 띠/빈 영역 방지)
            pix_w = layer["pix_w"]
            pix_h = layer["pix_h"]
            src_x = max(0, min(src_x, pix_w - 1))
            src_y = max(0, min(src_y, pix_h - 1))
            src_w = max(1, min(src_w, pix_w - src_x))
            src_h = max(1, min(src_h, pix_h - src_y))

            source = QRect(
                src_x,
                src_y,
                src_w,
                src_h,
            )
            painter.drawPixmap(target, shot, source)
