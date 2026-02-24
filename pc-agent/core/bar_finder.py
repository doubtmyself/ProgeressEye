"""진행바 자동 탐지 모듈.

OpenCV Canny 에지 검출 + 윤곽(contour) 기반으로
이미지 내 가로/세로로 긴 직사각형 틀을 찾아
진행바의 바운딩 박스와 방향을 자동 판별한다.
"""

from dataclasses import dataclass

import cv2
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
    direction: str = "horizontal"  # "horizontal" 또는 "vertical"

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
    """OpenCV 기반 진행바 자동 탐지기.

    Grayscale → GaussianBlur → Canny Edge Detection
    → Morphological Closing → findContours
    → 직사각형 필터링 (종횡비 ≥ 2.0 또는 ≤ 0.5)

    종횡비로 수평/수직 방향을 자동 판별한다.
    """

    def __init__(
        self,
        min_area_ratio: float = 0.03,
        max_area_ratio: float = 0.95,
        min_rectangularity: float = 0.6,
        aspect_threshold: float = 2.0,
    ) -> None:
        """
        Args:
            min_area_ratio: 후보 최소 면적 비율 (이미지 대비).
            max_area_ratio: 후보 최대 면적 비율.
            min_rectangularity: 윤곽 면적 / 바운딩 박스 면적 최소 비율.
            aspect_threshold: 수평 판정 최소 종횡비 (수직은 역수).
        """
        self._min_area_ratio = min_area_ratio
        self._max_area_ratio = max_area_ratio
        self._min_rect = min_rectangularity
        self._aspect_th = aspect_threshold

    def find(self, image: Image.Image) -> BarRegion | None:
        """이미지에서 진행바 영역을 자동 탐지한다.

        Canny 에지 → 윤곽 → 직사각형 필터 → 방향 판별.
        탐지 실패 시 이미지 종횡비로 방향만 추정하여 반환.

        Args:
            image: 대략적으로 캡처된 영역 (RGB).

        Returns:
            BarRegion (탐지 성공 시 confidence > 0, 실패 시 confidence = 0).
            이미지가 너무 작으면 None.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        img = np.array(image)
        h, w = img.shape[:2]

        if h < 3 or w < 3:
            return None

        # 윤곽 기반 탐지 시도
        result = self._detect_by_contours(img, h, w)
        if result is not None:
            return result

        # 실패 시: 이미지 종횡비로 방향만 추정, 전체 영역 반환
        aspect = w / max(h, 1)
        direction = "vertical" if aspect < (1.0 / self._aspect_th) else "horizontal"
        log.info(
            "윤곽 미탐지 — 이미지 비율(%.1f)로 방향 추정: %s",
            aspect,
            direction,
        )
        return BarRegion(
            top=0,
            left=0,
            bottom=h,
            right=w,
            confidence=0.0,
            direction=direction,
        )

    def _detect_by_contours(
        self,
        img: np.ndarray,
        h: int,
        w: int,
    ) -> BarRegion | None:
        """Canny + 윤곽 기반 직사각형 탐지."""

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 적응형 Canny 임계값 (이미지 밝기 기반)
        median_val = int(np.median(blurred))
        lower = max(10, int(median_val * 0.33))
        upper = max(30, int(median_val * 0.67))

        edges = cv2.Canny(blurred, lower, upper)

        # 모폴로지 닫힘: 끊어진 에지 연결
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        img_area = h * w
        min_area = img_area * self._min_area_ratio
        max_area = img_area * self._max_area_ratio

        candidates: list[BarRegion] = []

        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            rect_area = bw * bh

            if rect_area < min_area or rect_area > max_area:
                continue

            contour_area = cv2.contourArea(contour)
            if contour_area < 1:
                continue

            rectangularity = contour_area / rect_area
            if rectangularity < self._min_rect:
                continue

            # 종횡비로 방향 판별
            aspect = bw / max(bh, 1)
            if aspect >= self._aspect_th:
                direction = "horizontal"
            elif aspect <= (1.0 / self._aspect_th):
                direction = "vertical"
            else:
                continue  # 바 형태가 아님 (너무 정사각형)

            candidates.append(
                BarRegion(
                    top=y,
                    left=x,
                    bottom=y + bh,
                    right=x + bw,
                    confidence=round(rectangularity, 2),
                    direction=direction,
                )
            )

        if not candidates:
            return None

        # 신뢰도 → 면적 순으로 최적 후보 선택
        best = max(candidates, key=lambda r: (r.confidence, r.width * r.height))

        log.info(
            "바 탐지 [%s]: (%d,%d)-(%d,%d) %dx%d 신뢰도=%.2f",
            best.direction,
            best.left,
            best.top,
            best.right,
            best.bottom,
            best.width,
            best.height,
            best.confidence,
        )
        return best
