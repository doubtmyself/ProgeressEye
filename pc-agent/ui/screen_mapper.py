"""모니터별 DPI를 고려한 Qt ↔ mss 좌표 변환.

Qt 오버레이 위젯은 virtualGeometry() 크기로 전체 데스크톱을 커버한다.
위젯 좌표는 Qt 논리 좌표이며, 각 모니터의 devicePixelRatio(DPR)에
따라 물리(mss) 좌표로 변환해야 한다.

모니터1(100%) 위의 위젯 1px = 물리 1px,
모니터2(150%) 위의 위젯 1px = 물리 1.5px.
"""

from __future__ import annotations

import mss as mss_lib
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QGuiApplication, QScreen
from typing import Any

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


# ── 화면 탐색 헬퍼 ──────────────────────────────────────


def _screen_at(global_logical: QPoint) -> QScreen:
    """글로벌 논리 좌표에 해당하는 Qt 화면을 반환한다."""
    for screen in QGuiApplication.screens():
        if screen.geometry().contains(global_logical):
            return screen
    target = QGuiApplication.screenAt(global_logical)
    if target is not None:
        return target
    primary = QGuiApplication.primaryScreen()
    assert primary is not None
    return primary


def _screen_for_selection(selection: QRect, virtual_geo: QRect) -> QScreen:
    """선택 사각형과 가장 많이 겹치는 Qt 화면을 반환한다."""
    global_rect = selection.translated(virtual_geo.topLeft())
    best_screen: QScreen | None = None
    best_area = -1
    for screen in QGuiApplication.screens():
        overlap = global_rect.intersected(screen.geometry())
        area = max(0, overlap.width()) * max(0, overlap.height())
        if area > best_area:
            best_area = area
            best_screen = screen

    if best_screen is not None and best_area > 0:
        return best_screen
    return _screen_at(global_rect.center())


def _mss_monitor_for_qt_screen(
    target: QScreen,
    sct: Any,
) -> tuple[int, dict[str, int]] | None:
    """Qt 화면에 가장 잘 대응하는 mss 모니터를 반환한다.

    단순 인덱스 매칭 대신 (물리 해상도 + 화면 배치 순서) 기반으로 점수화한다.
    """
    monitors = sct.monitors[1:]
    if not monitors:
        return None

    screens = QGuiApplication.screens()
    if not screens:
        return None

    geo = target.geometry()
    target_ratio = geo.width() / max(1, geo.height())

    target_rank_x = sum(1 for s in screens if s.geometry().x() < geo.x())
    target_rank_y = sum(1 for s in screens if s.geometry().y() < geo.y())

    best_score: int | None = None
    best_pair: tuple[int, dict[str, int]] | None = None
    for idx, mon in enumerate(monitors, 1):
        mon_rank_x = sum(1 for m in monitors if m["left"] < mon["left"])
        mon_rank_y = sum(1 for m in monitors if m["top"] < mon["top"])

        mon_ratio = mon["width"] / max(1, mon["height"])
        ratio_error = abs(mon_ratio - target_ratio)
        rank_error = abs(mon_rank_x - target_rank_x) + abs(mon_rank_y - target_rank_y)
        score = (rank_error * 10_000.0) + (ratio_error * 100.0)

        if best_score is None or score < best_score:
            best_score = score
            best_pair = (idx, mon)

    return best_pair


def _qt_screen_for_mss(mss_idx: int) -> QScreen:
    """mss 모니터 인덱스에 대응하는 Qt 화면을 반환한다.

    인덱스가 뒤섞이는 환경(배율/배치 변경)에서도 안정적으로 동작하도록
    화면 배치 순서(rank) + 종횡비 유사도로 매칭한다.
    """
    screens = QGuiApplication.screens()
    primary = QGuiApplication.primaryScreen()
    assert primary is not None

    if not screens or mss_idx < 1:
        return primary

    try:
        with mss_lib.mss() as sct:
            if mss_idx >= len(sct.monitors):
                return primary
            mon = sct.monitors[mss_idx]
            monitors = sct.monitors[1:]
            target_rank_x = sum(1 for m in monitors if m["left"] < mon["left"])
            target_rank_y = sum(1 for m in monitors if m["top"] < mon["top"])
            mon_ratio = mon["width"] / max(1, mon["height"])

            best_score: float | None = None
            best_screen: QScreen | None = None
            for s in screens:
                geo = s.geometry()
                rank_x = sum(1 for other in screens if other.geometry().x() < geo.x())
                rank_y = sum(1 for other in screens if other.geometry().y() < geo.y())
                screen_ratio = geo.width() / max(1, geo.height())

                rank_error = abs(rank_x - target_rank_x) + abs(rank_y - target_rank_y)
                ratio_error = abs(screen_ratio - mon_ratio)
                score = (rank_error * 10_000.0) + (ratio_error * 100.0)
                if best_score is None or score < best_score:
                    best_score = score
                    best_screen = s

            if best_screen is not None:
                return best_screen
    except Exception as exc:
        log.warning("Qt 화면 매칭 실패: %s", exc)

    return primary


# ── Qt 위젯 → mss 좌표 변환 ─────────────────────────────


def qt_widget_to_mss(selection: QRect, virtual_geo: QRect) -> dict[str, int]:
    """Qt 위젯 좌표를 mss 로컬 물리 좌표로 변환한다.

    위젯 좌표를 글로벌 논리 좌표로 변환한 뒤, 해당 지점의
    Qt 화면 DPR을 사용하여 물리 좌표를 산출한다.

    Args:
        selection: 위젯 내 선택 영역 (논리 픽셀).
        virtual_geo: 위젯이 커버하는 가상 데스크톱 영역.

    Returns:
        ``{"x", "y", "width", "height", "monitor"}`` — mss 로컬 좌표.
    """
    # 선택 영역 겹침 기준으로 대상 화면 결정
    target = _screen_for_selection(selection, virtual_geo)
    geo = target.geometry()

    # 화면 내 논리 좌표
    in_x = (selection.x() + virtual_geo.x()) - geo.x()
    in_y = (selection.y() + virtual_geo.y()) - geo.y()

    try:
        with mss_lib.mss() as sct:
            if log.isEnabledFor(10):
                q_screens = QGuiApplication.screens()
                for i, s in enumerate(q_screens):
                    g = s.geometry()
                    log.debug(
                        "Qt screen[%d]: name=%s geo=(%d,%d %dx%d) dpr=%.2f",
                        i,
                        s.name(),
                        g.x(),
                        g.y(),
                        g.width(),
                        g.height(),
                        s.devicePixelRatio(),
                    )
                for i, mon in enumerate(sct.monitors):
                    log.debug(
                        "mss monitor[%d]: left=%d top=%d %dx%d",
                        i,
                        mon["left"],
                        mon["top"],
                        mon["width"],
                        mon["height"],
                    )

            match = _mss_monitor_for_qt_screen(target, sct)
            if match is not None:
                mi, mon = match

                # 모니터별 물리/논리 스케일 (Qt DPR 대신 mss 물리 해상도 기준)
                sx = mon["width"] / max(1, geo.width())
                sy = mon["height"] / max(1, geo.height())

                phys_x = int(in_x * sx)
                phys_y = int(in_y * sy)
                phys_w = max(1, int(selection.width() * sx))
                phys_h = max(1, int(selection.height() * sy))

                # 모니터 경계에 클램프
                phys_x = max(0, min(phys_x, mon["width"] - 1))
                phys_y = max(0, min(phys_y, mon["height"] - 1))
                phys_w = min(phys_w, mon["width"] - phys_x)
                phys_h = min(phys_h, mon["height"] - phys_y)

                log.debug(
                    "Qt→mss: screen=%s scale=(%.3f,%.3f) widget(%d,%d %dx%d) -> phys(%d,%d %dx%d) mon=%d",
                    target.name(),
                    sx,
                    sy,
                    selection.x(),
                    selection.y(),
                    selection.width(),
                    selection.height(),
                    phys_x,
                    phys_y,
                    phys_w,
                    phys_h,
                    mi,
                )
                return {
                    "x": phys_x,
                    "y": phys_y,
                    "width": phys_w,
                    "height": phys_h,
                    "monitor": mi,
                    "abs_x": mon["left"] + phys_x,
                    "abs_y": mon["top"] + phys_y,
                }

    except Exception as exc:
        log.warning("qt_widget_to_mss mss 접근 실패: %s", exc)

    # 최종 fallback — 글로벌 비율
    return _fallback_qt_to_mss(selection, virtual_geo)


# ── mss → Qt 위젯 좌표 변환 ──────────────────────────────


def mss_to_qt_widget(area: dict[str, int], virtual_geo: QRect | None = None) -> QRect:
    """mss 로컬 물리 좌표를 Qt 위젯 좌표로 변환한다.

    mss 모니터에 대응하는 Qt 화면을 찾아 DPR로 나누어
    논리 좌표를 구한 뒤, 위젯 좌표로 변환한다.

    Args:
        area: ``{"x", "y", "width", "height", "monitor"}`` — mss 로컬 좌표.
        virtual_geo: 위젯의 가상 데스크톱 영역. ``None``이면 현재 값 조회.

    Returns:
        Qt 위젯 좌표의 ``QRect``.
    """
    primary = QGuiApplication.primaryScreen()
    if primary is None:
        return QRect(area["x"], area["y"], area["width"], area["height"])

    if virtual_geo is None:
        virtual_geo = primary.virtualGeometry()
    assert virtual_geo is not None

    mon_idx = int(area.get("monitor", 0))
    local_x = int(area.get("x", 0))
    local_y = int(area.get("y", 0))
    mon_w = 0
    mon_h = 0

    try:
        with mss_lib.mss() as sct:
            if log.isEnabledFor(10):
                q_screens = QGuiApplication.screens()
                for i, s in enumerate(q_screens):
                    g = s.geometry()
                    log.debug(
                        "Qt screen[%d]: name=%s geo=(%d,%d %dx%d) dpr=%.2f",
                        i,
                        s.name(),
                        g.x(),
                        g.y(),
                        g.width(),
                        g.height(),
                        s.devicePixelRatio(),
                    )
                for i, mon in enumerate(sct.monitors):
                    log.debug(
                        "mss monitor[%d]: left=%d top=%d %dx%d",
                        i,
                        mon["left"],
                        mon["top"],
                        mon["width"],
                        mon["height"],
                    )

            # 절대 물리 좌표가 있으면 중심점으로 모니터를 재판정 (인덱스 불일치 보정)
            if "abs_x" in area and "abs_y" in area:
                abs_x = int(area["abs_x"])
                abs_y = int(area["abs_y"])
                cx = abs_x + max(1, int(area["width"])) // 2
                cy = abs_y + max(1, int(area["height"])) // 2
                for i, mon in enumerate(sct.monitors[1:], 1):
                    if (
                        mon["left"] <= cx < mon["left"] + mon["width"]
                        and mon["top"] <= cy < mon["top"] + mon["height"]
                    ):
                        mon_idx = i
                        local_x = abs_x - mon["left"]
                        local_y = abs_y - mon["top"]
                        break

            if 1 <= mon_idx < len(sct.monitors):
                mon = sct.monitors[mon_idx]
                mon_w = max(1, int(mon["width"]))
                mon_h = max(1, int(mon["height"]))
            else:
                mon_w = max(1, int(sct.monitors[0]["width"]))
                mon_h = max(1, int(sct.monitors[0]["height"]))
    except Exception as exc:
        log.warning("mss_to_qt_widget mss 접근 실패: %s", exc)

    qt_screen = _qt_screen_for_mss(mon_idx)
    geo = qt_screen.geometry()
    sx = mon_w / max(1, geo.width())
    sy = mon_h / max(1, geo.height())

    # 물리 → 논리 (화면 내)
    logical_x = local_x / sx
    logical_y = local_y / sy
    logical_w = int(area.get("width", 1)) / sx
    logical_h = int(area.get("height", 1)) / sy

    # 글로벌 논리 → 위젯 좌표
    wx = int(geo.x() + logical_x - virtual_geo.x())
    wy = int(geo.y() + logical_y - virtual_geo.y())
    ww = max(1, int(logical_w))
    wh = max(1, int(logical_h))

    log.debug(
        "mss→Qt: phys(%d,%d %dx%d) mon=%d -> widget(%d,%d %dx%d) scale=(%.3f,%.3f)",
        area["x"],
        area["y"],
        area["width"],
        area["height"],
        mon_idx,
        wx,
        wy,
        ww,
        wh,
        sx,
        sy,
    )

    return QRect(wx, wy, ww, wh)


# ── fallback (기존 글로벌 비율 방식) ──────────────────────


def _fallback_qt_to_mss(
    selection: QRect,
    virtual_geo: QRect,
) -> dict[str, int]:
    """per-screen 매칭 실패 시 글로벌 비율을 사용하는 fallback."""
    try:
        with mss_lib.mss() as sct:
            full = sct.monitors[0]
            sx = full["width"] / max(1, virtual_geo.width())
            sy = full["height"] / max(1, virtual_geo.height())

            mss_x = int(selection.x() * sx) + full["left"]
            mss_y = int(selection.y() * sy) + full["top"]
            mss_w = max(1, int(selection.width() * sx))
            mss_h = max(1, int(selection.height() * sy))

            cx = mss_x + mss_w // 2
            cy = mss_y + mss_h // 2

            for i, mon in enumerate(sct.monitors[1:], 1):
                if (
                    mon["left"] <= cx < mon["left"] + mon["width"]
                    and mon["top"] <= cy < mon["top"] + mon["height"]
                ):
                    return {
                        "x": mss_x - mon["left"],
                        "y": mss_y - mon["top"],
                        "width": mss_w,
                        "height": mss_h,
                        "monitor": i,
                        "abs_x": mss_x,
                        "abs_y": mss_y,
                    }

            return {
                "x": mss_x,
                "y": mss_y,
                "width": mss_w,
                "height": mss_h,
                "monitor": 0,
                "abs_x": mss_x,
                "abs_y": mss_y,
            }
    except Exception:
        return {
            "x": selection.x(),
            "y": selection.y(),
            "width": selection.width(),
            "height": selection.height(),
            "monitor": 0,
        }
