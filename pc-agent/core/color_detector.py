"""색상 자동 감지 모듈.

선택된 영역에서 채움 색상과 빈 색상을 자동으로 판별한다.
좌측 1/4 → 채움 색상, 우측 1/4 → 빈 색상으로 추정.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

from utils.logger import log


@dataclass
class ColorDetectionResult:
    """색상 감지 결과."""

    fill_color: tuple[int, int, int]  # 채움 색상 (RGB)
    empty_color: tuple[int, int, int]  # 빈 색상 (RGB)
    confidence: float  # 감지 신뢰도 (0.0~1.0)


class ColorDetector:
    """진행바 채움/빈 색상 자동 감지기.

    이미지 좌측 1/4에서 주요 색상(채움)을,
    우측 1/4에서 주요 색상(빈)을 추출한다.
    """

    def __init__(self, quantize_bits: int = 5) -> None:
        """
        Args:
            quantize_bits: 색상 양자화 비트 수 (낮을수록 거칠게 양자화).
                           기본 5 → 2^5=32단계로 양자화.
        """
        self._shift = 8 - quantize_bits

    def detect(self, image: Image.Image) -> ColorDetectionResult:
        """이미지에서 채움/빈 색상을 자동 감지한다.

        Args:
            image: 캡처된 진행바 PIL 이미지 (RGB).

        Returns:
            ColorDetectionResult — 감지된 채움/빈 색상과 신뢰도.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.uint8)  # (H, W, 3)
        height, width, _ = pixels.shape

        if width < 4 or height < 1:
            log.warning("이미지가 너무 작아 색상 감지 불가 (w=%d, h=%d)", width, height)
            return ColorDetectionResult(
                fill_color=(128, 128, 128),
                empty_color=(200, 200, 200),
                confidence=0.0,
            )

        # 좌측 1/4 영역 → 채움 색상 후보
        left_quarter = pixels[:, : width // 4, :]
        fill_color = self._dominant_color(left_quarter)

        # 우측 1/4 영역 → 빈 색상 후보
        right_quarter = pixels[:, width * 3 // 4 :, :]
        empty_color = self._dominant_color(right_quarter)

        # 신뢰도: 두 색상이 얼마나 다른지
        color_diff = np.sqrt(
            float(
                (fill_color[0] - empty_color[0]) ** 2
                + (fill_color[1] - empty_color[1]) ** 2
                + (fill_color[2] - empty_color[2]) ** 2
            )
        )
        # 차이가 50 이상이면 충분히 구분됨 → 신뢰도 1.0
        confidence = round(min(color_diff / 50.0, 1.0), 2)

        if confidence < 0.3:
            log.warning(
                "채움/빈 색상 차이가 작음 — 균일 색상일 가능성 (diff=%.1f)",
                color_diff,
            )

        log.info(
            "색상 감지 완료: 채움=%s, 빈=%s, 신뢰도=%.2f",
            fill_color,
            empty_color,
            confidence,
        )

        return ColorDetectionResult(
            fill_color=fill_color,
            empty_color=empty_color,
            confidence=confidence,
        )

    def _dominant_color(self, region: np.ndarray) -> tuple[int, int, int]:
        """영역에서 가장 빈번한 색상을 찾는다.

        히스토그램 기반: 색상을 양자화한 후 가장 빈번한 색상 반환.

        Args:
            region: (H, W, 3) 형태의 uint8 배열.

        Returns:
            (R, G, B) 주요 색상.
        """
        # 양자화
        quantized = (region >> self._shift) << self._shift
        # (H*W, 3)으로 평탄화
        flat = quantized.reshape(-1, 3)

        # 각 색상을 단일 정수로 인코딩: R*65536 + G*256 + B
        encoded = (
            flat[:, 0].astype(np.uint32) * 65536
            + flat[:, 1].astype(np.uint32) * 256
            + flat[:, 2].astype(np.uint32)
        )

        # 가장 빈번한 색상 찾기
        values, counts = np.unique(encoded, return_counts=True)
        dominant_encoded = values[np.argmax(counts)]

        # 다시 RGB로 디코딩
        r = int((dominant_encoded >> 16) & 0xFF)
        g = int((dominant_encoded >> 8) & 0xFF)
        b = int(dominant_encoded & 0xFF)

        return (r, g, b)
