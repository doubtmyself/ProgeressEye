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

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


# ── 화면 탐색 헬퍼 ──────────────────────────────────────


def _screen_at(global_logical: QPoint) -> QScreen:
    """글로벌 논리 좌표에 해당하는 Qt 화면을 반환한다."""
    target = QGuiApplication.screenAt(global_logical)
    if target is not None:
        return target
    primary = QGuiApplication.primaryScreen()
    assert primary is not None
    return primary


def _qt_screen_for_mss(mss_idx: int) -> QScreen:
    """mss 모니터 인덱스에 대응하는 Qt 화면을 반환한다.

    인덱스 매칭(mss[i] = Qt screens[i-1])을 우선 시도하고,
    실패 시 물리 해상도로 fallback 매칭한다.
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

            # 1) 인덱스 기반 매칭
            qi = mss_idx - 1
            if qi < len(screens):
                s = screens[qi]
                dpr = s.devicePixelRatio()
                sw = int(s.geometry().width() * dpr)
                sh = int(s.geometry().height() * dpr)
                if abs(sw - mon["width"]) <= 10 and abs(sh - mon["height"]) <= 10:
                    return s

            # 2) 해상도 기반 fallback
            for s in screens:
                dpr = s.devicePixelRatio()
                sw = int(s.geometry().width() * dpr)
                sh = int(s.geometry().height() * dpr)
                if abs(sw - mon["width"]) <= 10 and abs(sh - mon["height"]) <= 10:
                    return s
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
    # 글로벌 논리 좌표 (위젯 좌표 + virtualGeo offset)
    center = QPoint(
        selection.center().x() + virtual_geo.x(),
        selection.center().y() + virtual_geo.y(),
    )
    target = _screen_at(center)
    dpr = target.devicePixelRatio()
    geo = target.geometry()

    # 화면 내 논리 좌표 → 물리 좌표
    in_x = (selection.x() + virtual_geo.x()) - geo.x()
    in_y = (selection.y() + virtual_geo.y()) - geo.y()
    phys_x = int(in_x * dpr)
    phys_y = int(in_y * dpr)
    phys_w = max(1, int(selection.width() * dpr))
    phys_h = max(1, int(selection.height() * dpr))

    try:
        with mss_lib.mss() as sct:
            # Qt 화면 인덱스 → mss 모니터 인덱스
            screens = QGuiApplication.screens()
            qi = screens.index(target) if target in screens else 0
            mi = qi + 1

            # 인덱스 검증 (해상도 일치 확인)
            if mi < len(sct.monitors):
                mon = sct.monitors[mi]
                expected_w = int(geo.width() * dpr)
                expected_h = int(geo.height() * dpr)
                if (
                    abs(mon["width"] - expected_w) <= 10
                    and abs(mon["height"] - expected_h) <= 10
                ):
                    # 모니터 경계에 클램프
                    phys_x = max(0, min(phys_x, mon["width"] - 1))
                    phys_y = max(0, min(phys_y, mon["height"] - 1))
                    phys_w = min(phys_w, mon["width"] - phys_x)
                    phys_h = min(phys_h, mon["height"] - phys_y)

                    log.debug(
                        "Qt→mss: widget(%d,%d %dx%d) → phys(%d,%d %dx%d) mon=%d dpr=%.2f",
                        selection.x(),
                        selection.y(),
                        selection.width(),
                        selection.height(),
                        phys_x,
                        phys_y,
                        phys_w,
                        phys_h,
                        mi,
                        dpr,
                    )
                    return {
                        "x": phys_x,
                        "y": phys_y,
                        "width": phys_w,
                        "height": phys_h,
                        "monitor": mi,
                    }

            # 인덱스 매칭 실패 → 해상도 기반 fallback
            for i, mon in enumerate(sct.monitors[1:], 1):
                expected_w = int(geo.width() * dpr)
                expected_h = int(geo.height() * dpr)
                if (
                    abs(mon["width"] - expected_w) <= 10
                    and abs(mon["height"] - expected_h) <= 10
                ):
                    phys_x = max(0, min(phys_x, mon["width"] - 1))
                    phys_y = max(0, min(phys_y, mon["height"] - 1))
                    phys_w = min(phys_w, mon["width"] - phys_x)
                    phys_h = min(phys_h, mon["height"] - phys_y)

                    log.debug(
                        "Qt→mss (fallback): widget(%d,%d %dx%d) → phys(%d,%d %dx%d) mon=%d dpr=%.2f",
                        selection.x(),
                        selection.y(),
                        selection.width(),
                        selection.height(),
                        phys_x,
                        phys_y,
                        phys_w,
                        phys_h,
                        i,
                        dpr,
                    )
                    return {
                        "x": phys_x,
                        "y": phys_y,
                        "width": phys_w,
                        "height": phys_h,
                        "monitor": i,
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

    mon_idx = area.get("monitor", 0)
    qt_screen = _qt_screen_for_mss(mon_idx)
    dpr = qt_screen.devicePixelRatio()
    geo = qt_screen.geometry()

    # 물리 → 논리 (화면 내)
    logical_x = area["x"] / dpr
    logical_y = area["y"] / dpr
    logical_w = area["width"] / dpr
    logical_h = area["height"] / dpr

    # 글로벌 논리 → 위젯 좌표
    wx = int(geo.x() + logical_x - virtual_geo.x())
    wy = int(geo.y() + logical_y - virtual_geo.y())
    ww = max(1, int(logical_w))
    wh = max(1, int(logical_h))

    log.debug(
        "mss→Qt: phys(%d,%d %dx%d) mon=%d → widget(%d,%d %dx%d) dpr=%.2f",
        area["x"],
        area["y"],
        area["width"],
        area["height"],
        mon_idx,
        wx,
        wy,
        ww,
        wh,
        dpr,
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
                    }

            return {
                "x": mss_x,
                "y": mss_y,
                "width": mss_w,
                "height": mss_h,
                "monitor": 0,
            }
    except Exception:
        return {
            "x": selection.x(),
            "y": selection.y(),
            "width": selection.width(),
            "height": selection.height(),
            "monitor": 0,
        }
