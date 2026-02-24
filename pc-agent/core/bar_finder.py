"""진행바 자동 탐지 모듈.

다중 전략으로 이미지 내 진행바 영역을 찾아낸다:
  1. Canny 에지 + 수직 모폴로지 — 테두리 있는 바
  2. 적응형 이진화 — 미세한 대비 차
  3. HSV 채도 분할 — 채색된 fill 영역 직접 탐지
  4. 배경 제거 — 코너 색상 기준 비-배경 영역
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


# ── 최소 두께: 이보다 얇은 후보는 에지 아티팩트로 간주 ──
_MIN_THICKNESS = 6


class BarFinder:
    """다중 전략 기반 진행바 자동 탐지기."""

    def __init__(
        self,
        min_area_ratio: float = 0.01,
        max_area_ratio: float = 0.95,
        min_rectangularity: float = 0.40,
        aspect_threshold: float = 2.0,
    ) -> None:
        self._min_area_ratio = min_area_ratio
        self._max_area_ratio = max_area_ratio
        self._min_rect = min_rectangularity
        self._aspect_th = aspect_threshold

    # ── 공개 API ─────────────────────────────────────────

    def find(self, image: Image.Image) -> BarRegion | None:
        """이미지에서 진행바 영역을 탐지한다.

        탐지 실패 시에도 전체 영역을 fallback으로 반환.
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

        # fallback
        aspect = w / max(h, 1)
        direction = "vertical" if aspect < (1.0 / self._aspect_th) else "horizontal"
        log.info("윤곽 미탐지 — fallback (전체 이미지, 방향=%s)", direction)
        return BarRegion(
            top=0,
            left=0,
            bottom=h,
            right=w,
            confidence=0.0,
            direction=direction,
        )

    # ── 핵심 탐지 ────────────────────────────────────────

    def _detect(self, img: np.ndarray, h: int, w: int) -> BarRegion | None:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        candidates: list[BarRegion] = []

        # ── 전략 1: Canny + Otsu (수직 모폴로지로 에지 브릿지) ──
        otsu_val, _ = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        for factor in (0.5, 0.33):
            lower = max(10, int(otsu_val * factor))
            upper = max(30, int(otsu_val * factor * 2))
            edges = cv2.Canny(blurred, lower, upper)

            # 작은 커널 (기존)
            k_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k_small, iterations=1)
            contours, _ = cv2.findContours(
                closed,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            candidates.extend(self._filter_contours(contours, h, w))

            # 큰 수직 커널 — 상/하 에지를 브릿지하여 바 본체 형성
            kh = max(7, h // 6)
            k_tall = cv2.getStructuringElement(cv2.MORPH_RECT, (3, kh))
            bridged = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k_tall, iterations=1)
            contours, _ = cv2.findContours(
                bridged,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            candidates.extend(self._filter_contours(contours, h, w))

        # ── 전략 2: 적응형 이진화 ──
        block_size = max(15, (min(h, w) // 10) | 1)
        binary = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=block_size,
            C=3,
        )
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        candidates.extend(self._filter_contours(contours, h, w))

        # ── 전략 3: HSV 채도 분할 (fill 색상 영역) ──
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        sat_mask = ((hsv[:, :, 1] > 30) & (hsv[:, :, 2] > 30)).astype(np.uint8) * 255
        k_color = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        sat_cleaned = cv2.morphologyEx(sat_mask, cv2.MORPH_CLOSE, k_color, iterations=2)
        sat_cleaned = cv2.morphologyEx(
            sat_cleaned, cv2.MORPH_OPEN, k_color, iterations=1
        )
        contours, _ = cv2.findContours(
            sat_cleaned,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        # fill 영역 → 트랙 확장 시도
        for cnt in contours:
            expanded = self._expand_to_track(img, cnt, h, w)
            if expanded is not None:
                candidates.append(expanded)

        # ── 전략 4: 배경 제거 (코너 기반) ──
        bg = self._estimate_background(img)
        diff = np.sqrt(
            np.sum((img.astype(np.float64) - bg.astype(np.float64)) ** 2, axis=2)
        )
        fg_mask = (diff > 25).astype(np.uint8) * 255
        k_fg = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg_cleaned = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k_fg, iterations=2)
        fg_cleaned = cv2.morphologyEx(fg_cleaned, cv2.MORPH_OPEN, k_fg, iterations=1)
        contours, _ = cv2.findContours(
            fg_cleaned,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        candidates.extend(self._filter_contours(contours, h, w))

        if not candidates:
            return None

        candidates = self._deduplicate(candidates)
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

    # ── 컨투어 필터링 ────────────────────────────────────

    def _filter_contours(
        self,
        contours: list,
        h: int,
        w: int,
    ) -> list[BarRegion]:
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

    # ── 트랙 확장 (fill → 전체 바 영역) ──────────────────
    def _expand_to_track(
        self,
        img: np.ndarray,
        fill_contour: np.ndarray,
        h: int,
        w: int,
    ) -> BarRegion | None:
        """fill 영역에서 Sobel 경계 + 배경 제거로 전체 바 트랙을 복원한다.

        1단계: Sobel-x(수직 에지)로 fill 좌우의 트랙 경계를 탐지
        2단계: 배경 제거로 추가 확장 (경계 없는 pill 바 대응)
        3단계: 두 결과 중 넓은 쪽 채택
        """
        x, y, bw, bh = cv2.boundingRect(fill_contour)
        if bw * bh < h * w * self._min_area_ratio:
            return None

        y_start = max(y + 1, 0)
        y_end = min(y + bh - 1, h)
        if y_end <= y_start:
            y_start, y_end = y, min(y + bh, h)
        fill_left = x
        fill_right = x + bw

        # ── 1단계: Sobel-x 경계 탐지 ──
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        # fill 행 범위의 median 프로파일
        profile = np.median(sobel_x[y_start:y_end, :], axis=0)
        edge_th = max(float(np.percentile(profile, 70)), 10.0)
        strong = np.where(profile > edge_th)[0]

        # fill 좌측 이내의 에지 → 좌측 경계
        left_edges = strong[strong <= fill_left + 5]
        grad_left = int(left_edges[0]) if len(left_edges) > 0 else fill_left

        # fill 우측 이후의 에지 → 우측 경계 (최우측 채택)
        right_edges = strong[strong >= fill_right - 5]
        grad_right = (
            int(right_edges[-1]) + 1
            if len(right_edges) > 0
            else fill_right
        )

        # ── 2단계: 배경 제거 기반 확장 ──
        cy = y + bh // 2
        if 0 <= cy < h:
            bg = self._estimate_background(img)
            row = img[cy].astype(np.float64)
            row_diff = np.sqrt(
                np.sum((row - bg.astype(np.float64)) ** 2, axis=1)
            )
            fill_diff = float(row_diff[x:x + bw].mean())
            threshold = max(fill_diff * 0.15, 10.0)
            non_bg = np.where(row_diff > threshold)[0]
            if len(non_bg) > 0:
                bg_left = int(non_bg[0])
                bg_right = int(non_bg[-1]) + 1
            else:
                bg_left, bg_right = fill_left, fill_right
        else:
            bg_left, bg_right = fill_left, fill_right

        # ── 3단계: 두 결과 중 넓은 쪽 채택 ──
        track_left = min(grad_left, bg_left)
        track_right = max(grad_right, bg_right)

        # 이미지 거의 전체면 과확장 — fill 기준으로 제한
        if (track_right - track_left) > w * 0.97:
            track_left = fill_left
            track_right = fill_right
        track_width = track_right - track_left
        if track_width < bh * self._aspect_th:
            return None
        aspect = track_width / max(bh, 1)
        if aspect >= self._aspect_th:
            direction = "horizontal"
        elif aspect <= (1.0 / self._aspect_th):
            direction = "vertical"
        else:
            return None
        return BarRegion(
            top=y, left=track_left, bottom=y + bh, right=track_right,
            confidence=0.65, direction=direction,
        )

    # ── 배경 추정 ────────────────────────────────────────

    @staticmethod
    def _estimate_background(img: np.ndarray) -> np.ndarray:
        """이미지 4개 코너의 중앙값으로 배경색을 추정한다."""
        h, w = img.shape[:2]
        patch = max(3, min(h // 8, w // 8, 10))
        corners = [
            img[:patch, :patch],
            img[:patch, -patch:],
            img[-patch:, :patch],
            img[-patch:, -patch:],
        ]
        all_pixels = np.concatenate(
            [c.reshape(-1, 3) for c in corners],
            axis=0,
        )
        return np.median(all_pixels, axis=0).astype(np.uint8)

    # ── 스코어링 ─────────────────────────────────────────

    @staticmethod
    def _bar_score(region: BarRegion) -> tuple[float, float]:
        """바 후보의 점수: elongation × 두께 보정, 면적.

        에지 아티팩트(6px 미만)를 크게 감점한다.
        """
        longer = max(region.width, region.height)
        shorter = max(min(region.width, region.height), 1)
        elongation = longer / shorter

        # 헤어라인 감점: 6px 미만이면 점수 1/10
        thickness_factor = min(shorter / _MIN_THICKNESS, 1.0)

        return (elongation * thickness_factor, region.width * region.height)

    # ── 중복 제거 ────────────────────────────────────────

    @staticmethod
    def _deduplicate(
        candidates: list[BarRegion],
        iou_threshold: float = 0.5,
    ) -> list[BarRegion]:
        if len(candidates) <= 1:
            return candidates

        scored = sorted(
            candidates,
            key=lambda r: (
                max(r.width, r.height)
                / max(min(r.width, r.height), 1)
                * min(min(r.width, r.height) / _MIN_THICKNESS, 1.0),
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
