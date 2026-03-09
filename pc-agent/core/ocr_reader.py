"""OCR-based numeric reader powered by ONNX Runtime OCR.

This module extracts progress numbers (e.g. "45%", "11.0") from cropped UI images.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass
from typing import Any

np = importlib.import_module("numpy")
cv2 = importlib.import_module("cv2")
PILImage = importlib.import_module("PIL.Image")
log = importlib.import_module("utils.logger").log

_rapidocr_import_error: Exception | None = None
try:
    from rapidocr_onnxruntime import RapidOCR as RapidOCREngine
except ImportError as exc:
    RapidOCREngine = None  # type: ignore[assignment]
    _rapidocr_import_error = exc


@dataclass
class OcrResult:
    """Single OCR candidate."""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    progress: float
    has_percent_sign: bool


class OcrReader:
    """ONNX Runtime OCR-based progress reader with lightweight frame caching."""

    _PERCENT_RE = re.compile(r"(\d+(?:[\.,]\d+)?)\s*%")
    _NUMBER_RE = re.compile(r"(\d+(?:[\.,]\d+)?)")
    _CHAR_FIX_TABLE = str.maketrans(
        {
            "O": "0",
            "D": "0",
            "I": "1",
            "L": "1",
            "|": "1",
            "S": "5",
            "B": "8",
        }
    )

    def __init__(self) -> None:
        self._prev_hashes: dict[str, str] = {}
        self._prev_results: dict[str, float | None] = {}
        self._backend = "none"
        self._ocr = self._init_ocr()

    @property
    def backend(self) -> str:
        return self._backend

    def _init_ocr(self):
        if RapidOCREngine is not None:
            try:
                ocr = RapidOCREngine()
                self._backend = "rapidocr"
                log.info("RapidOCR (ONNX Runtime) initialized")
                return ocr
            except Exception as exc:
                log.warning("RapidOCR initialization failed: %s", exc)

        detail = repr(_rapidocr_import_error) if _rapidocr_import_error else "unknown"
        log.error("OCR backend init failed: RapidOCR unavailable (%s)", detail)
        return None

    def _extract_raw_lines(self, image_bgr: Any) -> list[tuple[Any, str, float]]:
        if self._ocr is None:
            return []
        try:
            raw = self._ocr(image_bgr, use_det=True, use_cls=False, use_rec=True)
            if isinstance(raw, tuple) and len(raw) >= 1:
                raw = raw[0]
        except Exception as exc:
            try:
                raw = self._ocr(image_bgr)
                if isinstance(raw, tuple) and len(raw) >= 1:
                    raw = raw[0]
            except Exception as retry_exc:
                log.error("RapidOCR execution failed: %s", retry_exc)
                return []

        return self._normalize_raw_output(raw)

    @staticmethod
    def _normalize_raw_output(raw: Any) -> list[tuple[Any, str, float]]:
        """Normalize OCR outputs across format variants.

        Supported shapes:
        - ocr(): [[[points], (text, score)], ...]
        - predict()/wrapper dict: {"res": {"dt_polys": ..., "rec_texts": ..., "rec_scores": ...}}
        - direct dict: {"dt_polys": ..., "rec_texts": ..., "rec_scores": ...}
        """

        def collect_from_dict(payload: Any) -> list[tuple[Any, str, float]]:
            if not isinstance(payload, dict):
                return []

            res_obj = payload.get("res")
            if isinstance(res_obj, dict):
                res = res_obj
            else:
                res = payload
            dt_polys = res.get("dt_polys")
            rec_texts = res.get("rec_texts")
            rec_scores = res.get("rec_scores")

            if not isinstance(dt_polys, list) or not isinstance(rec_texts, list):
                return []

            rows: list[tuple[Any, str, float]] = []
            for idx, points in enumerate(dt_polys):
                if idx >= len(rec_texts):
                    break
                text = str(rec_texts[idx]).strip()
                if not text:
                    continue
                score_raw = 0.0
                if isinstance(rec_scores, list) and idx < len(rec_scores):
                    score_raw = rec_scores[idx]
                try:
                    confidence = float(score_raw)
                except (TypeError, ValueError):
                    confidence = 0.0
                rows.append((points, text, confidence))
            return rows

        normalized: list[tuple[Any, str, float]] = []
        if raw is None:
            return normalized

        dict_rows = collect_from_dict(raw)
        if dict_rows:
            return dict_rows

        if not isinstance(raw, list):
            return normalized

        def is_xy_point(value: Any) -> bool:
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                return False
            return isinstance(value[0], (int, float)) and isinstance(
                value[1], (int, float)
            )

        # Legacy ocr() result usually wraps per image as [lines].
        base = raw
        if raw and isinstance(raw[0], list):
            first = raw[0]
            if first and isinstance(first[0], (list, tuple)):
                maybe_line = first[0]
                if (
                    isinstance(maybe_line, (list, tuple))
                    and len(maybe_line) >= 2
                    and not is_xy_point(maybe_line[1])
                ):
                    base = first

        for item in base:
            item_dict_rows = collect_from_dict(item)
            if item_dict_rows:
                normalized.extend(item_dict_rows)
                continue

            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue

            points = item[0]
            recog = item[1]

            # RapidOCR common shape: [points, text, score]
            if isinstance(recog, str):
                text = recog.strip()
                if not text:
                    continue
                score_raw = item[2] if len(item) >= 3 else 0.0
                try:
                    confidence = float(score_raw)
                except (TypeError, ValueError):
                    confidence = 0.0
                normalized.append((points, text, confidence))
                continue

            if not isinstance(recog, (list, tuple)) or len(recog) < 2:
                continue

            text = str(recog[0]).strip()
            if not text:
                continue

            try:
                confidence = float(recog[1])
            except (TypeError, ValueError):
                confidence = 0.0
            normalized.append((points, text, confidence))

        return normalized

    @staticmethod
    def _build_variants(image_bgr: Any) -> list[tuple[Any, float]]:
        variants: list[tuple[Any, float]] = [(image_bgr, 1.0)]

        h, w = image_bgr.shape[:2]
        if min(h, w) < 220:
            upscaled = cv2.resize(
                image_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC
            )
            variants.append((upscaled, 2.0))

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        thresholded = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9,
        )
        variants.append((cv2.cvtColor(thresholded, cv2.COLOR_GRAY2BGR), 1.0))

        return variants

    def find_percentages(
        self,
        image: Any,
        *,
        min_value: float = 0.0,
        max_value: float = 100.0,
    ) -> list[OcrResult]:
        """Return all numeric OCR candidates from an image."""
        if self._ocr is None:
            return []

        rgb = image.convert("RGB")
        img_np = np.array(rgb)

        # OCR engines here expect OpenCV/BGR ndarray.
        bgr_np = img_np[:, :, ::-1]

        results: list[OcrResult] = []
        for variant, scale in self._build_variants(bgr_np):
            lines = self._extract_raw_lines(variant)
            if not lines:
                continue

            for points, text, raw_conf in lines:
                try:
                    x_vals = [int(float(p[0]) / scale) for p in points]
                    y_vals = [int(float(p[1]) / scale) for p in points]
                except Exception:
                    continue

                conf = raw_conf * 100.0 if raw_conf <= 1.0 else raw_conf
                x = max(0, min(x_vals))
                y = max(0, min(y_vals))
                w = max(1, max(x_vals) - x)
                h = max(1, max(y_vals) - y)

                extracted = self._extract_progress_values(text)
                if not extracted:
                    continue

                for value, has_percent in extracted:
                    if min_value <= value <= max_value:
                        results.append(
                            OcrResult(
                                text=text,
                                confidence=conf,
                                bbox=(x, y, w, h),
                                progress=value,
                                has_percent_sign=has_percent,
                            )
                        )

        results = self._dedupe_results(results)
        log.info("OCR detection complete: %d numeric candidates", len(results))
        return results

    def _dedupe_results(self, results: list[OcrResult]) -> list[OcrResult]:
        """Remove near-duplicate OCR candidates from multi-variant passes."""
        if len(results) <= 1:
            return results

        def score(r: OcrResult) -> tuple[int, int, float]:
            return (
                1 if r.has_percent_sign else 0,
                self._numeric_digit_count(r.text),
                r.confidence,
            )

        deduped: list[OcrResult] = []
        for candidate in sorted(results, key=score, reverse=True):
            is_duplicate = False
            for kept in deduped:
                if abs(candidate.progress - kept.progress) > 0.2:
                    continue

                iou = self._bbox_iou(candidate.bbox, kept.bbox)
                center_dist = self._bbox_center_distance(candidate.bbox, kept.bbox)

                # Strong overlap or almost same center means duplicated detection.
                if iou >= 0.65 or center_dist <= 4.0:
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduped.append(candidate)

        return deduped

    def read_progress(
        self,
        image: Any,
        region_id: str = "",
        *,
        min_value: float = 0.0,
        max_value: float = 100.0,
        prefer_percent_sign: bool = True,
        allow_percent_sign: bool = True,
    ) -> float | None:
        """Return the best progress value from OCR candidates."""
        if region_id:
            img_hash = self._compute_hash(image)
            prev_hash = self._prev_hashes.get(region_id)
            if prev_hash == img_hash:
                prev_result = self._prev_results.get(region_id)
                if prev_result is not None:
                    return prev_result
            self._prev_hashes[region_id] = img_hash

        results = self.find_percentages(
            image,
            min_value=min_value,
            max_value=max_value,
        )
        if not allow_percent_sign:
            results = [r for r in results if not r.has_percent_sign]
        if not results:
            if region_id:
                self._prev_results[region_id] = None
            return None

        best = self.select_best_result(results, prefer_percent_sign=prefer_percent_sign)
        progress = best.progress

        if region_id:
            self._prev_results[region_id] = progress
        return progress

    def select_best_result(
        self,
        results: list[OcrResult],
        *,
        prefer_percent_sign: bool = True,
    ) -> OcrResult:
        """Choose the final OCR result candidate.

        Priority:
        1) has '%'
        2) digit count (11 > 1)
        3) confidence
        """
        if not results:
            raise ValueError("results is empty")

        with_pct = [r for r in results if r.has_percent_sign]
        pool = with_pct if (prefer_percent_sign and with_pct) else results

        def score(r: OcrResult) -> tuple[int, int, float]:
            return (
                1 if r.has_percent_sign else 0,
                self._numeric_digit_count(r.text),
                r.confidence,
            )

        return max(pool, key=score)

    def reset_cache(self, region_id: str) -> None:
        self._prev_hashes.pop(region_id, None)
        self._prev_results.pop(region_id, None)

    @staticmethod
    def _compute_hash(image: Any) -> str:
        small = image.resize((32, 32), PILImage.Resampling.LANCZOS).convert("L")
        pixels = np.array(small, dtype=np.uint8)
        return hashlib.md5(pixels.tobytes()).hexdigest()

    @staticmethod
    def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh

        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0

        area_a = max(1, aw) * max(1, ah)
        area_b = max(1, bw) * max(1, bh)
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter / union

    @staticmethod
    def _bbox_center_distance(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int]
    ) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        acx = ax + aw / 2.0
        acy = ay + ah / 2.0
        bcx = bx + bw / 2.0
        bcy = by + bh / 2.0
        dx = acx - bcx
        dy = acy - bcy
        return (dx * dx + dy * dy) ** 0.5

    @staticmethod
    def _numeric_digit_count(text: str) -> int:
        m = re.search(r"(\d+(?:[\.,]\d+)?)", text)
        if not m:
            return 0
        return len(m.group(1).replace(".", "").replace(",", ""))

    @classmethod
    def _extract_progress_values(cls, text: str) -> list[tuple[float, bool]]:
        candidates: list[tuple[float, bool]] = []
        seen: set[tuple[float, bool]] = set()

        base = text.strip()
        variants = [
            base,
            base.upper(),
            base.upper().translate(cls._CHAR_FIX_TABLE),
            base.upper().replace(" ", "").translate(cls._CHAR_FIX_TABLE),
        ]

        for variant in variants:
            for m in cls._PERCENT_RE.finditer(variant):
                raw = m.group(1).replace(",", ".")
                try:
                    value = float(raw)
                except ValueError:
                    continue
                key = (value, True)
                if key not in seen:
                    seen.add(key)
                    candidates.append(key)

            for m in cls._NUMBER_RE.finditer(variant):
                raw = m.group(1).replace(",", ".")
                try:
                    value = float(raw)
                except ValueError:
                    continue
                key = (value, ("%" in variant))
                if key not in seen:
                    seen.add(key)
                    candidates.append(key)

        return candidates
