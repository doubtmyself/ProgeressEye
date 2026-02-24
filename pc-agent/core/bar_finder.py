"""진행바 자동 탐지 모듈.

OpenCV 기반으로 이미지 내 가로/세로로 긴 직사각형 틀을 찾아
진행바의 바운딩 박스와 방향을 자동 판별한다.

다중 전략: Canny (Otsu 기반) + 적응형 이진화를 병행하여
배경이 복잡한 이미지에서도 안정적으로 탐지한다.
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

    1. Grayscale → GaussianBlur
    2. 다중 Canny 임계값 (Otsu 기반) + 적응형 이진화로 에지 탐지
    3. Morphological Closing → findContours
    4. 직사각형 필터링 (종횡비, rectangularity)
    5. 가장 "바 형태"인 후보 선택 (elongation 우선)

    종횡비로 수평/수직 방향을 자동 판별한다.
    """

    def __init__(
        self,
        min_area_ratio: float = 0.02,
        max_area_ratio: float = 0.95,
        min_rectangularity: float = 0.5,
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

        다중 전략으로 에지를 탐지하고, 가장 바 형태에 가까운
        직사각형 윤곽을 선택한다. 방향은 종횡비로 자동 판별.

        Args:
            image: 대략적으로 캡처된 영역 (RGB).

        Returns:
            BarRegion. 탐지 실패 시에도 전체 영역을 fallback으로 반환.
            이미지가 너무 작으면 None.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        img = np.array(image)
        h, w = img.shape[:2]

        if h < 3 or w < 3:
            return None

        result = self._detect(img, h, w)
        if result is not None:
            return result

        # fallback: 이미지 종횡비로 방향만 추정
        aspect = w / max(h, 1)
        direction = "vertical" if aspect < (1.0 / self._aspect_th) else "horizontal"
        log.info("윤곽 미탐지 — 방향 추정: %s (비율=%.1f)", direction, aspect)
        return BarRegion(
            top=0,
            left=0,
            bottom=h,
            right=w,
            confidence=0.0,
            direction=direction,
        )

    def _detect(
        self,
        img: np.ndarray,
        h: int,
        w: int,
    ) -> BarRegion | None:
        """다중 전략으로 직사각형 탐지를 시도한다."""

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        candidates: list[BarRegion] = []

        # ── 전략 1: Canny + Otsu 기반 임계값 ──
        otsu_val, _ = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        # Otsu 기반으로 여러 감도 시도
        for factor in (0.5, 0.33):
            lower = max(10, int(otsu_val * factor))
            upper = max(30, int(otsu_val * factor * 2))
            edges = cv2.Canny(blurred, lower, upper)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

            contours, _ = cv2.findContours(
                closed,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            candidates.extend(self._filter_contours(contours, h, w))

        # ── 전략 2: 적응형 이진화 (국소 대비로 미세한 테두리 탐지) ──
        binary = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=15,
            C=3,
        )
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        candidates.extend(self._filter_contours(contours, h, w))

        if not candidates:
            return None

        # 중복 제거 (겹치는 영역 병합)
        candidates = self._deduplicate(candidates)

        # 가장 "바 형태"인 후보 선택: elongation(얼마나 길쭉한지) 우선
        best = max(candidates, key=self._bar_score)

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

    def _filter_contours(
        self,
        contours: list[np.ndarray],
        h: int,
        w: int,
    ) -> list[BarRegion]:
        """윤곽 목록에서 바 후보를 필터링한다."""

        img_area = h * w
        min_area = img_area * self._min_area_ratio
        max_area = img_area * self._max_area_ratio

        results: list[BarRegion] = []

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

            aspect = bw / max(bh, 1)
            if aspect >= self._aspect_th:
                direction = "horizontal"
            elif aspect <= (1.0 / self._aspect_th):
                direction = "vertical"
            else:
                continue

            results.append(
                BarRegion(
                    top=y,
                    left=x,
                    bottom=y + bh,
                    right=x + bw,
                    confidence=round(rectangularity, 2),
                    direction=direction,
                )
            )

        return results

    @staticmethod
    def _bar_score(region: BarRegion) -> tuple[float, float]:
        """바 후보의 점수를 계산한다.

        elongation(길쭉한 정도)이 높을수록, 면적이 클수록 높은 점수.
        단순히 큰 직사각형이 아니라, "바 형태"를 우선 선택한다.
        """
        longer = max(region.width, region.height)
        shorter = max(min(region.width, region.height), 1)
        elongation = longer / shorter  # 높을수록 바 형태
        return (elongation, region.width * region.height)

    @staticmethod
    def _deduplicate(
        candidates: list[BarRegion],
        iou_threshold: float = 0.6,
    ) -> list[BarRegion]:
        """겹치는 후보를 병합한다 (IoU 기반)."""
        if len(candidates) <= 1:
            return candidates

        # bar_score 높은 순 정렬
        scored = sorted(
            candidates,
            key=lambda r: (
                max(r.width, r.height) / max(min(r.width, r.height), 1),
                r.width * r.height,
            ),
            reverse=True,
        )

        kept: list[BarRegion] = []
        for region in scored:
            overlap = False
            for existing in kept:
                if _iou(region, existing) > iou_threshold:
                    overlap = True
                    break
            if not overlap:
                kept.append(region)

        return kept


def _iou(a: BarRegion, b: BarRegion) -> float:
    """두 영역의 IoU(Intersection over Union)를 계산한다."""
    x1 = max(a.left, b.left)
    y1 = max(a.top, b.top)
    x2 = min(a.right, b.right)
    y2 = min(a.bottom, b.bottom)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area_a = a.width * a.height
    area_b = b.width * b.height
    union = area_a + area_b - intersection

    return intersection / max(union, 1)
