"""진행바 자동 탐지 모듈.

대략적으로 선택된 영역에서 실제 진행바의 범위를 자동으로 찾아
불필요한 여백을 제거한다. 수평/수직 바 모두 지원.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

from utils.logger import log


@dataclass
class BarRegion:
    """탐지된 진행바 영역 (PIL crop 호환)."""

    top: int
    left: int
    bottom: int  # exclusive
    right: int  # exclusive
    confidence: float

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """PIL Image.crop() 형식: (left, upper, right, lower)."""
        return (self.left, self.top, self.right, self.bottom)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class BarFinder:
    """대략적 선택 영역에서 진행바를 자동 탐지한다.

    코너 픽셀로 배경색을 추정한 뒤, 배경과 구분되는
    밴드(진행바)의 경계를 찾아 크롭 좌표를 반환한다.

    - 수평 바: 상/하 여백 제거 (좌/우 보존)
    - 수직 바: 좌/우 여백 제거 (상/하 보존)
    """

    def __init__(self, bg_threshold: float = 25.0) -> None:
        """
        Args:
            bg_threshold: 배경 구분 최소 색상 거리 (유클리드).
        """
        self._bg_threshold = bg_threshold

    def find(
        self,
        image: Image.Image,
        direction: str = "horizontal",
    ) -> BarRegion | None:
        """이미지에서 진행바 영역을 탐지한다.

        Args:
            image: 대략적으로 캡처된 영역 (RGB).
            direction: "horizontal" (수평 바) 또는 "vertical" (수직 바).

        Returns:
            BarRegion 또는 None (탐지 실패/불필요).
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.float64)
        h, w, _ = pixels.shape

        if h < 3 or w < 3:
            return None

        bg = self._estimate_background(pixels)
        dist = np.sqrt(np.sum((pixels - bg) ** 2, axis=2))

        if direction == "vertical":
            return self._find_vertical_bar(dist, h, w)
        return self._find_horizontal_bar(dist, h, w)

    # -- 수평 바: 상/하 여백 제거 --

    def _find_horizontal_bar(
        self,
        dist: np.ndarray,
        h: int,
        w: int,
    ) -> BarRegion | None:
        top, bottom = self._find_extent_by_rows(dist, h)
        if top is None or bottom is None:
            return None
        if (bottom - top) >= h * 0.85:
            return None

        bar_dist = dist[top:bottom, :]
        non_bg = float((bar_dist > self._bg_threshold).mean())
        confidence = round(min(non_bg * 2.0, 1.0), 2)

        region = BarRegion(
            top=top,
            left=0,
            bottom=bottom,
            right=w,
            confidence=confidence,
        )
        log.info(
            "수평 바 탐지: y=%d~%d (%dpx/%dpx, 신뢰도=%.2f)",
            top,
            bottom,
            bottom - top,
            h,
            confidence,
        )
        return region

    # -- 수직 바: 좌/우 여백 제거 --

    def _find_vertical_bar(
        self,
        dist: np.ndarray,
        h: int,
        w: int,
    ) -> BarRegion | None:
        left, right = self._find_extent_by_cols(dist, w)
        if left is None or right is None:
            return None
        if (right - left) >= w * 0.85:
            return None

        bar_dist = dist[:, left:right]
        non_bg = float((bar_dist > self._bg_threshold).mean())
        confidence = round(min(non_bg * 2.0, 1.0), 2)

        region = BarRegion(
            top=0,
            left=left,
            bottom=h,
            right=right,
            confidence=confidence,
        )
        log.info(
            "수직 바 탐지: x=%d~%d (%dpx/%dpx, 신뢰도=%.2f)",
            left,
            right,
            right - left,
            w,
            confidence,
        )
        return region

    # -- 내부 메서드 --

    def _estimate_background(self, pixels: np.ndarray) -> np.ndarray:
        """네 꼭짓점의 색상으로 배경색을 추정한다."""
        h, w, _ = pixels.shape
        cs = max(2, min(8, h // 6, w // 6))
        corners = np.concatenate(
            [
                pixels[:cs, :cs].reshape(-1, 3),
                pixels[:cs, -cs:].reshape(-1, 3),
                pixels[-cs:, :cs].reshape(-1, 3),
                pixels[-cs:, -cs:].reshape(-1, 3),
            ]
        )
        return np.median(corners, axis=0)

    def _find_extent_by_rows(
        self,
        dist: np.ndarray,
        h: int,
    ) -> tuple[int | None, int | None]:
        """배경이 아닌 행의 연속 범위를 찾는다."""
        row_ratio = (dist > self._bg_threshold).mean(axis=1)
        content = row_ratio > 0.15
        indices = np.where(content)[0]
        if len(indices) == 0:
            return None, None
        best = self._largest_contiguous(indices)
        if best is None:
            return None, None
        return max(0, best[0] - 1), min(h, best[1] + 1)

    def _find_extent_by_cols(
        self,
        dist: np.ndarray,
        w: int,
    ) -> tuple[int | None, int | None]:
        """배경이 아닌 열의 연속 범위를 찾는다."""
        col_ratio = (dist > self._bg_threshold).mean(axis=0)
        content = col_ratio > 0.15
        indices = np.where(content)[0]
        if len(indices) == 0:
            return None, None
        best = self._largest_contiguous(indices)
        if best is None:
            return None, None
        return max(0, best[0] - 1), min(w, best[1] + 1)

    @staticmethod
    def _largest_contiguous(indices: np.ndarray) -> tuple[int, int] | None:
        """정렬된 인덱스 배열에서 가장 긴 연속 블록을 찾는다.

        Returns:
            (start, end) — end는 exclusive.
        """
        if len(indices) == 0:
            return None

        diffs = np.diff(indices)
        breaks = np.where(diffs > 1)[0]
        starts = np.concatenate([[0], breaks + 1])
        ends = np.concatenate([breaks, [len(indices) - 1]])
        lengths = ends - starts + 1

        best_i = int(np.argmax(lengths))
        return (int(indices[starts[best_i]]), int(indices[ends[best_i]]) + 1)
