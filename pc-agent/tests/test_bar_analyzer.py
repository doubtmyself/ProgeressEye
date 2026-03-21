"""BarAnalyzer 단위 테스트.

PIL 이미지를 직접 생성하여 알고리즘의 핵심 동작을 검증한다.
"""

import numpy as np
import pytest
from PIL import Image

from core.bar_analyzer import BarAnalyzer, AnalysisResult


def make_bar_image(width: int, height: int, filled_ratio: float, fill_color=(70, 130, 180), bg_color=(220, 220, 220)) -> Image.Image:
    """지정된 비율만큼 채워진 수평 진행바 이미지를 생성한다."""
    arr = np.full((height, width, 3), bg_color, dtype=np.uint8)
    filled_cols = int(width * filled_ratio)
    if filled_cols > 0:
        arr[:, :filled_cols] = fill_color
    return Image.fromarray(arr, "RGB")


def make_uniform_image(width: int, height: int, color: tuple) -> Image.Image:
    """단색 이미지를 생성한다."""
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


class TestBarAnalyzerBasic:
    def setup_method(self):
        self.analyzer = BarAnalyzer()

    def test_50_percent_bar(self):
        img = make_bar_image(200, 20, 0.5)
        result = self.analyzer._analyze_internal(img)
        assert 40.0 <= result.progress <= 60.0

    def test_0_percent_uniform_gray(self):
        img = make_uniform_image(100, 20, (200, 200, 200))
        result = self.analyzer._analyze_internal(img)
        assert result.progress == 0.0

    def test_100_percent_uniform_colored(self):
        img = make_uniform_image(100, 20, (70, 130, 180))
        result = self.analyzer._analyze_internal(img)
        assert result.progress == 100.0

    def test_result_progress_in_valid_range(self):
        for ratio in (0.1, 0.3, 0.5, 0.7, 0.9):
            img = make_bar_image(200, 20, ratio)
            result = self.analyzer._analyze_internal(img)
            assert 0.0 <= result.progress <= 100.0

    def test_confidence_in_valid_range(self):
        img = make_bar_image(200, 20, 0.5)
        result = self.analyzer._analyze_internal(img)
        assert 0.0 <= result.confidence <= 1.0

    def test_total_columns_matches_image_width(self):
        img = make_bar_image(200, 20, 0.5)
        result = self.analyzer._analyze_internal(img)
        assert result.total_columns == 200

    def test_too_small_image_returns_zero(self):
        img = make_uniform_image(2, 1, (100, 150, 200))
        result = self.analyzer._analyze_internal(img)
        assert result.progress == 0.0
        assert result.confidence == 0.0
        assert result.total_columns == 0


class TestBarAnalyzerVertical:
    def setup_method(self):
        self.analyzer = BarAnalyzer()

    def test_vertical_bar_50_percent(self):
        """수직 바는 회전 후 분석한다."""
        arr = np.full((200, 20, 3), (220, 220, 220), dtype=np.uint8)
        arr[:100, :] = (70, 130, 180)  # 위쪽 50% 채움
        img = Image.fromarray(arr, "RGB")
        result = self.analyzer._analyze_internal(img, direction="vertical")
        assert 35.0 <= result.progress <= 65.0


class TestTransitionScores:
    def test_empty_when_too_narrow(self):
        col_means = np.zeros((5, 3), dtype=np.float64)
        scores = BarAnalyzer._transition_scores(col_means, window=5)
        assert len(scores) == 0

    def test_high_score_at_transition_point(self):
        """색상이 급격히 바뀌는 지점에서 점수가 높아야 한다."""
        w = 100
        col_means = np.zeros((w, 3), dtype=np.float64)
        col_means[:50] = [70, 130, 180]   # 파란색
        col_means[50:] = [220, 220, 220]  # 회색
        scores = BarAnalyzer._transition_scores(col_means, window=10)
        peak_idx = int(np.argmax(scores))
        # 전환점(50 - window=10 = 40번 인덱스)
        assert 35 <= peak_idx <= 45


class TestSaturation:
    def test_gray_has_zero_saturation(self):
        gray = np.array([150.0, 150.0, 150.0])
        assert BarAnalyzer._saturation(gray) == 0.0

    def test_colored_has_nonzero_saturation(self):
        blue = np.array([70.0, 130.0, 180.0])
        assert BarAnalyzer._saturation(blue) > 0.0

    def test_black_has_zero_saturation(self):
        black = np.array([0.0, 0.0, 0.0])
        assert BarAnalyzer._saturation(black) == 0.0


class TestSmoothColumns:
    def test_output_shape_matches_input(self):
        col_means = np.random.rand(100, 3)
        smoothed = BarAnalyzer._smooth_columns(col_means, k=5)
        assert smoothed.shape == col_means.shape

    def test_uniform_signal_unchanged_after_smoothing(self):
        col_means = np.ones((50, 3)) * 100.0
        smoothed = BarAnalyzer._smooth_columns(col_means, k=5)
        np.testing.assert_allclose(smoothed[5:-5], col_means[5:-5], atol=1.0)
