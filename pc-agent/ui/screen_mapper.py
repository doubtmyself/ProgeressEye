"""프라이머리 모니터 DPI 기반 Qt ↔ mss 좌표 변환.

Qt 오버레이 위젯은 **프라이머리 모니터의 DPI**로 렌더링된다.
따라서 위젯 좌표 × primaryScreen().devicePixelRatio() = 물리(mss) 좌표이다.
모니터마다 배율이 달라도 오버레이 안에서는 단일 DPR만 적용된다.
"""

from __future__ import annotations

import mss as mss_lib
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QGuiApplication

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


def _primary_dpr() -> float:
    """프라이머리 화면의 devicePixelRatio를 반환한다."""
    primary = QGuiApplication.primaryScreen()
    if primary is None:
        return 1.0
    return primary.devicePixelRatio()


def _mss_full() -> dict[str, int]:
    """mss 전체 데스크톱(monitors[0]) 바운드를 반환한다."""
    with mss_lib.mss() as sct:
        return dict(sct.monitors[0])


# ── Qt 위젯 → mss 좌표 변환 ─────────────────────────────


def qt_widget_to_mss(selection: QRect, virtual_geo: QRect) -> dict[str, int]:
    """Qt 위젯 좌표를 mss 로컬 물리 좌표로 변환한다.

    위젯 좌표에 프라이머리 DPR을 곱해 물리 데스크톱 좌표를 구한 뒤,
    해당 지점이 포함된 mss 모니터를 찾아 로컬 좌표로 변환한다.

    Args:
        selection: 위젯 내 선택 영역 (논리 픽셀).
        virtual_geo: 위젯이 커버하는 가상 데스크톱 영역 (사용하지 않지만 API 호환).

    Returns:
        ``{"x", "y", "width", "height", "monitor"}`` — mss 로컬 좌표.
    """
    dpr = _primary_dpr()

    try:
        with mss_lib.mss() as sct:
            full = sct.monitors[0]

            # 위젯 좌표 → 물리 데스크톱 절대 좌표
            phys_x = int(selection.x() * dpr) + full["left"]
            phys_y = int(selection.y() * dpr) + full["top"]
            phys_w = max(1, int(selection.width() * dpr))
            phys_h = max(1, int(selection.height() * dpr))

            # 중심점으로 모니터 판별
            cx = phys_x + phys_w // 2
            cy = phys_y + phys_h // 2

            for i, mon in enumerate(sct.monitors[1:], 1):
                if (
                    mon["left"] <= cx < mon["left"] + mon["width"]
                    and mon["top"] <= cy < mon["top"] + mon["height"]
                ):
                    local_x = phys_x - mon["left"]
                    local_y = phys_y - mon["top"]

                    log.debug(
                        "Qt→mss: widget(%d,%d %dx%d) → phys(%d,%d %dx%d) mon=%d dpr=%.2f",
                        selection.x(),
                        selection.y(),
                        selection.width(),
                        selection.height(),
                        local_x,
                        local_y,
                        phys_w,
                        phys_h,
                        i,
                        dpr,
                    )

                    return {
                        "x": local_x,
                        "y": local_y,
                        "width": phys_w,
                        "height": phys_h,
                        "monitor": i,
                    }

            # 모니터 매칭 실패 — 전체 데스크톱 기준 반환
            log.warning(
                "모니터 매칭 실패 — 전체 데스크톱 좌표 사용: phys(%d,%d)",
                phys_x,
                phys_y,
            )
            return {
                "x": phys_x,
                "y": phys_y,
                "width": phys_w,
                "height": phys_h,
                "monitor": 0,
            }

    except Exception as exc:
        log.warning("qt_widget_to_mss 실패: %s — 단순 변환 사용", exc)
        return {
            "x": int(selection.x() * dpr),
            "y": int(selection.y() * dpr),
            "width": max(1, int(selection.width() * dpr)),
            "height": max(1, int(selection.height() * dpr)),
            "monitor": 0,
        }


# ── mss → Qt 위젯 좌표 변환 ──────────────────────────────


def mss_to_qt_widget(area: dict[str, int], virtual_geo: QRect | None = None) -> QRect:
    """mss 로컬 물리 좌표를 Qt 위젯 좌표로 변환한다.

    mss 로컬 좌표를 물리 데스크톱 절대 좌표로 변환한 뒤,
    프라이머리 DPR로 나누어 위젯 좌표를 구한다.

    Args:
        area: ``{"x", "y", "width", "height", "monitor"}`` — mss 로컬 좌표.
        virtual_geo: 사용하지 않지만 API 호환을 위해 유지.

    Returns:
        Qt 위젯 좌표의 ``QRect``.
    """
    dpr = _primary_dpr()
    mon_idx = area.get("monitor", 0)

    try:
        with mss_lib.mss() as sct:
            full = sct.monitors[0]

            if 1 <= mon_idx < len(sct.monitors):
                mon = sct.monitors[mon_idx]
                # 로컬 물리 → 데스크톱 절대 물리
                phys_x = area["x"] + mon["left"]
                phys_y = area["y"] + mon["top"]
            else:
                # monitor=0 이면 이미 데스크톱 절대
                phys_x = area["x"]
                phys_y = area["y"]

            # 물리 데스크톱 → 위젯 좌표
            wx = int((phys_x - full["left"]) / dpr)
            wy = int((phys_y - full["top"]) / dpr)
            ww = max(1, int(area["width"] / dpr))
            wh = max(1, int(area["height"] / dpr))

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

    except Exception as exc:
        log.warning("mss_to_qt_widget 실패: %s — 단순 변환 사용", exc)
        return QRect(
            int(area["x"] / dpr),
            int(area["y"] / dpr),
            max(1, int(area["width"] / dpr)),
            max(1, int(area["height"] / dpr)),
        )
