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

    # 스무딩 커널 크기 = width // _SMOOTH_DIVISOR (최소 3)
    # 값이 클수록 강한 스무딩 → 노이즈에 강하지만 경계 뭉개짐
    _SMOOTH_DIVISOR = 30

    # 슬라이딩 윈도우 크기 = width // _WINDOW_DIVISOR (최소 3)
    # 값이 클수록 넓은 윈도우 → 경계를 더 넓게 탐지
    _WINDOW_DIVISOR = 15

    # 노이즈 바닥 = max(median * _NOISE_MEDIAN_MULT, _NOISE_ABS_MIN)
    # 피크 점수가 이 값 미만이면 전환점 없음(균일 바)으로 판정
    _NOISE_MEDIAN_MULT = 3.0
    _NOISE_ABS_MIN = 12.0

    # 채도 차이가 이 값 이상이면 우→좌 채움으로 판정
    _FILL_DIRECTION_SAT_THRESHOLD = 15

    # 피크 점수를 신뢰도(0~1)로 정규화하는 기준값
    _CONFIDENCE_NORMALIZER = 80.0

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
        k = max(3, width // self._SMOOTH_DIVISOR)
        smoothed = self._smooth_columns(col_means, k)

        # 슬라이딩 윈도우 전환 점수
        window = max(3, width // self._WINDOW_DIVISOR)
        scores = self._transition_scores(smoothed, window)

        if len(scores) == 0:
            return self._judge_uniform(col_means, width)

        peak_idx = int(np.argmax(scores))
        peak_score = float(scores[peak_idx])

        # 전환점 열 위치
        transition_col = window + peak_idx

        # 유의미한 전환인지 판단 (노이즈 바닥 대비)
        median_score = float(np.median(scores))
        noise_floor = max(median_score * self._NOISE_MEDIAN_MULT, self._NOISE_ABS_MIN)

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

        if right_sat > left_sat + self._FILL_DIRECTION_SAT_THRESHOLD:
            # 오른쪽이 더 채도 높음 → 우→좌 채움 (반전)
            filled_count = width - transition_col
        else:
            filled_count = transition_col

        progress = round((filled_count / width) * 100, 1)
        confidence = round(min(peak_score / self._CONFIDENCE_NORMALIZER, 1.0), 2)

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
        """열 평균 색상을 이동평균으로 스무딩한다.

        각 채널에 독립적으로 1D 컨볼루션을 적용한다.
        k 값이 클수록 강한 스무딩 → 노이즈에 강하지만 경계가 뭉개질 수 있다.
        mode="same"으로 출력 크기를 입력과 동일하게 유지한다.
        """
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
        """각 열 위치의 좌/우 윈도우 간 색상 차이(유클리드 거리)를 계산한다.

        누적합(cumsum)으로 슬라이딩 윈도우 평균을 O(W)에 산출한다.
        반환값이 클수록 해당 위치에서 색상 변화가 급격함 → 채움/빈 경계 후보.
        유효 탐지 범위: [window, W-window) — 양 끝단 window 크기만큼 제외.
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

    def analyze_by_color(
        self,
        bar_image: Image.Image,
        target_color: tuple[int, int, int],
        direction: str = "horizontal",
        tolerance: int = 25,
    ) -> AnalysisResult:
        """특정 색상 기준으로 진행률을 분석한다.

        target_color와 tolerance 이내의 픽셀들이 차지하는
        바 내 가장 먼 위치를 진행률로 환산한다.

        Args:
            bar_image: 크롭된 진행바 PIL 이미지 (RGB).
            target_color: 총 진행도를 나타내는 RGB 색상.
            direction: "horizontal" 또는 "vertical".
            tolerance: 색상 매칭 허용 거리 (0~255, 유클리드).
        """
        if direction == "vertical":
            bar_image = bar_image.transpose(Image.Transpose.ROTATE_270)

        if bar_image.mode != "RGB":
            bar_image = bar_image.convert("RGB")

        pixels = np.array(bar_image, dtype=np.float32)  # (H, W, 3)
        h, w, _ = pixels.shape

        target = np.array(target_color, dtype=np.float32)
        dists = np.sqrt(np.sum((pixels - target) ** 2, axis=2))  # (H, W)
        matches = dists <= tolerance  # (H, W) bool

        # 열(column) 기준으로 매칭 비율 계산
        col_match_ratio = matches.mean(axis=0)  # (W,)

        # adaptive threshold: 최대 매칭 비율의 30%를 임계값으로 사용
        peak = float(col_match_ratio.max())
        log.info(
            "색상 분석 [target=RGB%s tol=%d]: 이미지=%dx%d peak=%.3f",
            target_color, tolerance, w, h, peak,
        )
        if peak < 1.0 / h:  # 매칭 픽셀이 사실상 없음
            log.info("색상 기반 분석: 매칭 픽셀 없음 → 0%%")
            return AnalysisResult(progress=0.0, confidence=0.8, filled_columns=0, total_columns=w)

        threshold = peak * 0.3
        col_filled = col_match_ratio >= threshold
        filled_indices = np.where(col_filled)[0]

        if len(filled_indices) == 0:
            log.info("색상 기반 분석: filled 열 없음 → 0%%")
            return AnalysisResult(progress=0.0, confidence=0.8, filled_columns=0, total_columns=w)

        rightmost = int(filled_indices[-1]) + 1
        progress = round(rightmost / w * 100, 1)
        confidence = round(float(col_match_ratio[filled_indices].mean()), 2)

        log.info(
            "색상 기반 분석: %.1f%% (rightmost=%d/%d, peak=%.3f, threshold=%.3f)",
            progress, rightmost, w, peak, threshold,
        )
        return AnalysisResult(
            progress=progress,
            confidence=confidence,
            filled_columns=rightmost,
            total_columns=w,
        )


def detect_dominant_colors(
    bar_image: Image.Image,
    max_colors: int = 4,
    min_ratio: float = 0.05,
    min_saturation: int = 30,
) -> list[tuple[tuple[int, int, int], float]]:
    """바 이미지에서 지배적인 색상 목록을 반환한다.

    채도가 충분한 픽셀만 대상으로 클러스터링하여
    색상별 점유 비율을 반환한다.

    Args:
        bar_image: 크롭된 진행바 PIL 이미지 (RGB).
        max_colors: 최대 반환 색상 수.
        min_ratio: 이 비율 미만의 색상은 제외.
        min_saturation: HSV 채도 최솟값 (0~255).

    Returns:
        [(rgb_tuple, ratio), ...] — 비율 내림차순 정렬.
    """
    img = bar_image.convert("RGB")
    arr = np.array(img, dtype=np.float32)  # (H, W, 3)
    h, w, _ = arr.shape

    # 개별 픽셀 기반 색상 감지 (열 평균 대신 실제 픽셀 사용)
    # 성능을 위해 최대 2000픽셀로 균등 샘플링
    pixels_flat = arr.reshape(-1, 3).astype(np.uint8)  # (H*W, 3)
    total_px = len(pixels_flat)
    if total_px > 2000:
        step = total_px // 2000
        pixels_flat = pixels_flat[::step]

    # HSV 채도 필터 — 무채색(배경/트랙) 제거
    hsv_img = Image.fromarray(pixels_flat.reshape(1, -1, 3), "RGB").convert("HSV")
    hsv_arr = np.array(hsv_img)[0]  # (N, 3)
    colored_mask = (hsv_arr[:, 1] >= min_saturation) & (hsv_arr[:, 2] >= 30)
    colored_cols = pixels_flat[colored_mask]  # (N, 3)

    if len(colored_cols) < 3:
        return []

    # 단순 k-means (numpy만 사용, k=max_colors)
    k = min(max_colors, len(colored_cols))
    rng = np.random.default_rng(42)
    # 초기 중심: 픽셀 중 균등 간격으로 선택
    indices = np.linspace(0, len(colored_cols) - 1, k, dtype=int)
    centers = colored_cols[indices].astype(np.float32)

    for _ in range(20):  # max iterations
        dists = np.sqrt(
            np.sum((colored_cols[:, None, :].astype(np.float32) - centers[None, :, :]) ** 2, axis=2)
        )  # (N, k)
        labels = np.argmin(dists, axis=1)
        new_centers = np.array([
            colored_cols[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
            for i in range(k)
        ], dtype=np.float32)
        if np.allclose(centers, new_centers, atol=1.0):
            break
        centers = new_centers

    total = len(colored_cols)
    result: list[tuple[tuple[int, int, int], float]] = []
    for i in range(k):
        count = int(np.sum(labels == i))
        ratio = count / total
        if ratio >= min_ratio:
            rgb = tuple(int(c) for c in centers[i])
            result.append(((rgb[0], rgb[1], rgb[2]), round(ratio, 3)))

    result.sort(key=lambda x: -x[1])
    return result
