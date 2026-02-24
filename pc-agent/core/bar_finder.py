"""진행바 자동 탐지 모듈.

대략적으로 선택된 영역에서 실제 진행바의 범위를 자동으로 찾아
불필요한 여백을 제거한다. 수평/수직 바 모두 지원.

코너 색상이 서로 다를 때 (예: 상단 흰색 + 하단 검정)
클러스터링으로 배경 후보를 분리하여 각각 시도한다.
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

        배경 후보가 여러 개면 각각 시도하여
        가장 높은 신뢰도의 결과를 반환한다.

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

        bg_candidates = self._estimate_backgrounds(pixels)

        best: BarRegion | None = None
        for bg in bg_candidates:
            dist = np.sqrt(np.sum((pixels - bg) ** 2, axis=2))

            if direction == "vertical":
                result = self._find_vertical_bar(dist, h, w)
            else:
                result = self._find_horizontal_bar(dist, h, w)

            if result is not None:
                if best is None or result.confidence > best.confidence:
                    best = result

        return best

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

    # -- 배경 추정 --

    def _estimate_backgrounds(
        self,
        pixels: np.ndarray,
    ) -> list[np.ndarray]:
        """배경색 후보를 반환한다.

        4개 코너 색상이 유사하면 하나의 배경색을 반환.
        코너가 두 그룹으로 갈리면 (예: 상단 흰색, 하단 검정)
        양쪽 모두 후보로 반환하여 각각 시도할 수 있게 한다.
        """
        h, w, _ = pixels.shape
        cs = max(2, min(8, h // 6, w // 6))

        corner_avgs = np.array(
            [
                pixels[:cs, :cs].reshape(-1, 3).mean(axis=0),  # top-left
                pixels[:cs, -cs:].reshape(-1, 3).mean(axis=0),  # top-right
                pixels[-cs:, :cs].reshape(-1, 3).mean(axis=0),  # bottom-left
                pixels[-cs:, -cs:].reshape(-1, 3).mean(axis=0),  # bottom-right
            ]
        )  # (4, 3)

        # 코너 간 pairwise 거리
        pair_dists = []
        pair_indices = []
        for i in range(4):
            for j in range(i + 1, 4):
                d = float(np.sqrt(np.sum((corner_avgs[i] - corner_avgs[j]) ** 2)))
                pair_dists.append(d)
                pair_indices.append((i, j))

        max_dist = max(pair_dists)

        if max_dist < 60:
            # 모든 코너가 유사 → 단일 배경
            return [np.median(corner_avgs, axis=0)]

        # 코너가 갈림 → 2-그룹 클러스터링
        # 가장 먼 두 코너를 시드로 사용
        farthest = pair_indices[pair_dists.index(max_dist)]
        seed_a = corner_avgs[farthest[0]]
        seed_b = corner_avgs[farthest[1]]

        group_a: list[np.ndarray] = []
        group_b: list[np.ndarray] = []
        for avg in corner_avgs:
            da = float(np.sqrt(np.sum((avg - seed_a) ** 2)))
            db = float(np.sqrt(np.sum((avg - seed_b) ** 2)))
            if da <= db:
                group_a.append(avg)
            else:
                group_b.append(avg)

        bg_a = np.mean(group_a, axis=0)
        bg_b = np.mean(group_b, axis=0)

        log.debug(
            "코너 분리 감지: 그룹A=%s (%d개), 그룹B=%s (%d개), 거리=%.1f",
            bg_a.astype(int).tolist(),
            len(group_a),
            bg_b.astype(int).tolist(),
            len(group_b),
            max_dist,
        )

        return [bg_a, bg_b]

    # -- 범위 탐색 --

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
