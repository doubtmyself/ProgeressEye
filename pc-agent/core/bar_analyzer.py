"""진행바 막대 픽셀 분석 엔진.

슬라이딩 윈도우 전환점 탐지로 채움/빈 경계를 찾아 진행률(%)을 산출한다.
특정 색상 지정 없이 동작하며, 그라데이션 채움도 지원한다.

알고리즘:
  1. 열별 평균 색상 → 스무딩
  2. 슬라이딩 윈도우로 좌/우 색상 차이 계산
  3. 최대 전환점 = 채움/빈 경계
  4. 균일 바(전환 없음) → HSV 채도로 0%/100% 판정
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
    """진행바 전환점 기반 분석기.

    슬라이딩 윈도우로 열별 색상 변화를 추적하여
    채움 → 빈 전환점을 찾고, 해당 위치를 진행률로 환산한다.
    색상 지정 없이 동작하며 그라데이션도 지원한다.
    """

    def analyze(
        self,
        image: Image.Image,
        direction: str = "horizontal",
    ) -> AnalysisResult:
        """진행바 이미지를 분석하여 진행률을 산출한다.

        슬라이딩 윈도우 전환점 탐지 방식으로
        특정 색상 없이 채움/빈 경계를 찾는다.
        그라데이션 채움도 경계에서 급격한 색상 변화가
        발생하므로 정상 탐지된다.

        Args:
            image: 크롭된 진행바 PIL 이미지 (RGB).
            direction: "horizontal" 또는 "vertical".

        Returns:
            AnalysisResult — 진행률, 신뢰도, 채움/전체 열 수.
        """
        # 수직 바: 90° CW 회전 → 아래→위가 왼→오른쪽이 됨
        if direction == "vertical":
            image = image.transpose(Image.Transpose.ROTATE_270)

        if image.mode != "RGB":
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.float64)  # (H, W, 3)
        height, width, _ = pixels.shape

        if width < 3 or height < 1:
            log.warning("이미지가 너무 작아 분석 불가 (%dx%d)", width, height)
            return AnalysisResult(
                progress=0.0, confidence=0.0, filled_columns=0, total_columns=0
            )

        # 열별 평균 색상: (W, 3)
        col_means = pixels.mean(axis=0)

        # 스무딩 (노이즈 제거)
        k = max(3, width // 30)
        smoothed = self._smooth_columns(col_means, k)

        # 슬라이딩 윈도우 전환 점수
        window = max(3, width // 15)
        scores = self._transition_scores(smoothed, window)

        if len(scores) == 0:
            return self._judge_uniform(col_means, width)

        peak_idx = int(np.argmax(scores))
        peak_score = float(scores[peak_idx])

        # 전환점 열 위치
        transition_col = window + peak_idx

        # 유의미한 전환인지 판단 (노이즈 바닥 대비)
        median_score = float(np.median(scores))
        noise_floor = max(median_score * 3.0, 12.0)

        if peak_score < noise_floor:
            return self._judge_uniform(col_means, width)

        # ── 전환 방향 확인 ──
        # 왼쪽(채움)과 오른쪽(빈)의 색상 차이를 확인하여
        # 실제로 좌→우로 채워지는 바인지 검증한다.
        # 우→좌 채움(드문 경우)이면 반전 처리한다.
        left_avg = smoothed[:transition_col].mean(axis=0)
        right_avg = smoothed[transition_col:].mean(axis=0)

        # 왼쪽이 더 '채도가 높은' 쪽인지 확인
        left_sat = self._saturation(left_avg)
        right_sat = self._saturation(right_avg)

        if right_sat > left_sat + 15:
            # 오른쪽이 더 채도 높음 → 우→좌 채움 (반전)
            filled_count = width - transition_col
        else:
            filled_count = transition_col

        progress = round((filled_count / width) * 100, 1)
        confidence = round(min(peak_score / 80.0, 1.0), 2)

        log.debug(
            "전환점 분석: %.1f%% (전환 col=%d/%d, 점수=%.1f, 신뢰도=%.2f)",
            progress,
            transition_col,
            width,
            peak_score,
            confidence,
        )

        return AnalysisResult(
            progress=progress,
            confidence=confidence,
            filled_columns=filled_count,
            total_columns=width,
        )

    # ── 내부 유틸리티 ────────────────────────────────────

    @staticmethod
    def _smooth_columns(
        col_means: NDArray[np.float64],
        k: int,
    ) -> NDArray[np.float64]:
        """열 평균 색상을 이동평균으로 스무딩한다."""
        kernel = np.ones(k) / k
        smoothed = np.empty_like(col_means)
        for ch in range(col_means.shape[1]):
            smoothed[:, ch] = np.convolve(col_means[:, ch], kernel, mode="same")
        return smoothed

    @staticmethod
    def _transition_scores(
        smoothed: NDArray[np.float64],
        window: int,
    ) -> NDArray[np.float64]:
        """각 열 위치의 좌/우 윈도우 간 색상 차이를 계산한다.

        누적합으로 O(W) 시간에 윈도우 평균을 산출한다.
        """
        w = len(smoothed)
        if w < 2 * window + 1:
            return np.array([], dtype=np.float64)

        cumsum = np.zeros((w + 1, 3), dtype=np.float64)
        cumsum[1:] = np.cumsum(smoothed, axis=0)

        positions = np.arange(window, w - window)
        left_sums = cumsum[positions] - cumsum[positions - window]
        right_sums = cumsum[positions + window + 1] - cumsum[positions + 1]

        left_avgs = left_sums / window
        right_avgs = right_sums / window

        return np.sqrt(np.sum((left_avgs - right_avgs) ** 2, axis=1))

    @staticmethod
    def _saturation(rgb: NDArray[np.float64]) -> float:
        """RGB 평균 색상의 채도를 계산한다 (0~255 스케일)."""
        max_c = float(np.max(rgb))
        min_c = float(np.min(rgb))
        if max_c < 1.0:
            return 0.0
        return (max_c - min_c) / max_c * 255.0

    def _judge_uniform(
        self,
        col_means: NDArray[np.float64],
        width: int,
    ) -> AnalysisResult:
        """균일 바(전환점 없음)의 0%/100%를 판정한다.

        HSV 채도와 밝기로 판정:
        - 낮은 채도 (회색/흰색/검정) → 빈 바 → 0%
        - 높은 채도 (색상 있음) → 꽉 찬 바 → 100%
        """
        avg = col_means.mean(axis=0)
        saturation = self._saturation(avg)
        brightness = float(np.max(avg))

        # 열 간 색상 변동 (표준편차)
        col_std = float(
            np.std(np.sqrt(np.sum(np.diff(col_means, axis=0) ** 2, axis=1)))
        )

        if saturation < 25:
            # 무채색 (흰/회/검) → 빈 바 (0%)
            log.debug(
                "균일 바 → 무채색 (채도=%.1f, 밝기=%.0f) → 0%%",
                saturation,
                brightness,
            )
            return AnalysisResult(
                progress=0.0,
                confidence=0.7,
                filled_columns=0,
                total_columns=width,
            )

        # 유채색 → 꽉 찬 바 (100%)
        log.debug(
            "균일 바 → 유채색 (채도=%.1f, 밝기=%.0f, 변동=%.1f) → 100%%",
            saturation,
            brightness,
            col_std,
        )
        return AnalysisResult(
            progress=100.0,
            confidence=0.7,
            filled_columns=width,
            total_columns=width,
        )
