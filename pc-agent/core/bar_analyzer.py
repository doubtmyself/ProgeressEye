"""진행바 막대 픽셀 분석 엔진.

캡처된 진행바 이미지의 각 열(column)별 평균 색상을 분석하여
채움 비율 → 진행률(%)을 산출한다.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from utils.logger import log


@dataclass
class AnalysisResult:
    """분석 결과."""

    progress: float  # 0.0~100.0, 소수점 1자리
    confidence: float  # 0.0~1.0
    filled_columns: int  # 채워진 열 수
    total_columns: int  # 전체 열 수


class BarAnalyzer:
    """진행바 막대 픽셀 분석기.

    이미지의 각 열에 대해 평균 색상을 구하고,
    fill_color / empty_color 와의 유클리드 거리를 비교하여
    채움 여부를 판정한다.
    """

    @staticmethod
    def _color_distance(
        colors: NDArray[np.float64],
        target: tuple[int, int, int],
    ) -> NDArray[np.float64]:
        """색상 배열과 타겟 색상 간 유클리드 거리를 계산한다.

        Args:
            colors: (N, 3) 형태의 RGB 색상 배열.
            target: 비교 대상 RGB 색상.

        Returns:
            (N,) 형태의 거리 배열.
        """
        target_arr = np.array(target, dtype=np.float64)
        return np.sqrt(np.sum((colors - target_arr) ** 2, axis=1))

    def analyze(
        self,
        image: Image.Image,
        fill_color: tuple[int, int, int],
        empty_color: tuple[int, int, int],
        tolerance: int = 30,
    ) -> AnalysisResult:
        """진행바 이미지를 분석하여 진행률을 산출한다.

        Args:
            image: 캡처된 진행바 PIL 이미지 (RGB).
            fill_color: 채움 색상 (R, G, B).
            empty_color: 빈 색상 (R, G, B).
            tolerance: 색상 허용 오차 (유클리드 거리).

        Returns:
            AnalysisResult — 진행률, 신뢰도, 채움/전체 열 수.
        """
        # RGB 변환
        if image.mode != "RGB":
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.float64)  # (H, W, 3)
        height, width, _ = pixels.shape

        if width == 0 or height == 0:
            log.warning("빈 이미지 — 분석 불가")
            return AnalysisResult(
                progress=0.0, confidence=0.0, filled_columns=0, total_columns=0
            )

        # 열별 평균 색상: (W, 3)
        column_means = pixels.mean(axis=0)

        # 각 열과 fill/empty 색상 간 거리
        fill_distances = self._color_distance(column_means, fill_color)
        empty_distances = self._color_distance(column_means, empty_color)

        # 각 열이 채움인지 판정: fill에 더 가까우면 True
        is_filled = fill_distances < empty_distances

        # 좌→우 진행 방향: 연속된 채움 영역의 끝 찾기
        if is_filled.all():
            filled_count = width
        elif not is_filled.any():
            filled_count = 0
        else:
            # 첫 번째 False(빈) 열의 인덱스 = 채움 영역 끝
            # argmin on bool array: first False position
            filled_count = int(np.argmin(is_filled))
            # argmin이 0이면서 첫 열이 안 채워진 경우
            if filled_count == 0 and not is_filled[0]:
                filled_count = 0

        total_columns = width
        progress = round((filled_count / total_columns) * 100, 1)

        # 신뢰도: fill/empty 간 색상 거리가 클수록 높음
        confidence = self._calculate_confidence(
            fill_distances, empty_distances, is_filled, tolerance
        )

        log.debug(
            "분석 완료: %.1f%% (채움 %d/%d열, 신뢰도 %.2f)",
            progress,
            filled_count,
            total_columns,
            confidence,
        )

        return AnalysisResult(
            progress=progress,
            confidence=confidence,
            filled_columns=filled_count,
            total_columns=total_columns,
        )

    @staticmethod
    def _calculate_confidence(
        fill_distances: NDArray[np.float64],
        empty_distances: NDArray[np.float64],
        is_filled: NDArray[np.bool_],
        tolerance: int,
    ) -> float:
        """분석 신뢰도를 계산한다.

        채움 열은 fill_color에 가깝고 empty_color에 멀어야 하고,
        빈 열은 그 반대여야 신뢰도가 높다.
        """
        total = len(is_filled)
        if total == 0:
            return 0.0

        # 채움 열: fill과의 거리가 tolerance 이내인 비율
        filled_mask = is_filled
        empty_mask = ~is_filled

        scores = []

        if filled_mask.any():
            # 채움 열에서 fill_color까지 거리가 작을수록 좋음
            fill_close = (fill_distances[filled_mask] < tolerance).mean()
            scores.append(fill_close)

        if empty_mask.any():
            # 빈 열에서 empty_color까지 거리가 작을수록 좋음
            empty_close = (empty_distances[empty_mask] < tolerance).mean()
            scores.append(empty_close)

        if not scores:
            return 0.0

        # fill과 empty 색상 간 거리 — 색상이 충분히 다른지
        color_separation = np.sqrt(
            np.sum((np.mean(fill_distances) - np.mean(empty_distances)) ** 2)
        )
        # 정규화: 50 이상이면 충분히 구분됨
        separation_score = min(color_separation / 50.0, 1.0)

        raw_confidence = float(np.mean(scores)) * 0.7 + separation_score * 0.3
        return round(min(max(raw_confidence, 0.0), 1.0), 2)
