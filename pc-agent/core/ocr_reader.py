"""OCR 기반 숫자 인식 모듈.

pytesseract를 사용하여 이미지에서 숫자(%) 패턴을 탐지하고
바운딩 박스와 함께 반환한다.

숫자% (예: "45%") 뾿 아니라 단독 숫자 (예: "45")도 감지한다.

성능 최적화:
  - --oem 1 (LSTM only) — Legacy+LSTM 대비 가벼움
  - 변화 감지: 이전 캐콉과 픽셀 차이가 없으면 OCR 스킵
"""

import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

from utils.logger import log


def _find_tesseract_cmd() -> str | None:
    """Tesseract 실행 파일 경로를 탐색한다.

    우선순위:
    1. 번들된 tesseract (pc-agent/tesseract/tesseract.exe)
    2. 시스템 PATH
    3. Windows 기본 설치 경로
    """
    # 1. 번들 경로 (exe 배포 또는 개발 환경)
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent

    bundled = base / "tesseract" / "tesseract.exe"
    if bundled.is_file():
        return str(bundled)

    # 2. 시스템 PATH
    if shutil.which("tesseract") is not None:
        return None  # pytesseract 기본값 사용

    # 3. Windows 기본 설치 경로
    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(default):
        return default

    return None


try:
    import pytesseract

    _cmd = _find_tesseract_cmd()
    if _cmd is not None:
        pytesseract.pytesseract.tesseract_cmd = _cmd
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    log.warning(
        "pytesseract가 설치되지 않았습니다. "
        "OCR 기능을 사용하려면 'pip install pytesseract'와 "
        "Tesseract OCR을 설치하세요."
    )


@dataclass
class OcrResult:
    """OCR 탐지 결과."""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    progress: float  # 추출된 퍼센트 값 (0-100)
    has_percent_sign: bool  # "%" 기호가 포함된 결과인지 여부


class OcrReader:
    """OCR 기반 숫자 리더.

    pytesseract를 사용하여 이미지에서 숫자(%) 패턴을 찾는다.
    "%" 기호가 없는 단독 숫자(0~100 범위)도 감지한다.

    성능 최적화:
      - Tesseract LSTM-only 모드 (프로세스 내 연산 감소)
      - 변화 감지: 이전 캐콉과 픽셀 차이가 없으면 OCR 스킵
    """

    _PERCENT_RE = re.compile(r"(\d+\.?\d*)\s*%")
    _NUMBER_RE = re.compile(r"(\d+\.?\d*)")

    # Tesseract 최적화 설정
    # --oem 1: LSTM only (Legacy+LSTM 대비 빠르고 가벼움)
    # --psm 6: 블록 모드 (다양한 레이아웃 호환성 유지)
    # whitelist 미사용: regex로 숫자+% 필터링 (화면 캐콉에 비숫자 요소 포함 가능)
    _TESSERACT_CONFIG = "--oem 1 --psm 6"

    # 변화 감지 임계값 (0~255 픽셀 평균 차이)
    _CHANGE_THRESHOLD = 2.0

    def __init__(self) -> None:
        # 변화 감지용 이전 캐콉 해시 (region_id → hash)
        self._prev_hashes: dict[str, str] = {}
        # 변화 감지용 이전 결과 캐시 (region_id → progress)
        self._prev_results: dict[str, float | None] = {}
    def find_percentages(self, image: PILImage.Image) -> list[OcrResult]:
        """이미지에서 숫자(%) 패턴을 찾아 바운딩 박스와 함께 반환한다.
        앞뒤에 문자가 붙어있어도 숫자(%)를 추출한다.
        예: '진행률45%완료' → 45%, '45%done' → 45%
        탐지 우선순위:
        1. '45%', '진행률45%완료' — 숫자+% 포함 단어 (search)
        2. '45' + '%' — 분리 인식
        3. '45', '진행률45' — 단독 숫자 (0~100 범위)
        """
        if pytesseract is None:
            log.error("pytesseract가 설치되지 않아 OCR을 수행할 수 없습니다.")
            return []

        # 그레이스케일 변환 — OCR 정확도 향상
        gray = image.convert("L")

        try:
            data = pytesseract.image_to_data(
                gray,
                output_type=pytesseract.Output.DICT,
                config=self._TESSERACT_CONFIG,
            )
        except Exception as e:
            log.error("OCR 실행 실패: %s", e)
            return []

        n_boxes = len(data["text"])
        results: list[OcrResult] = []
        used: set[int] = set()  # 이미 처리된 인덱스
        i = 0

        while i < n_boxes:
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            if conf < 0 or not text:
                i += 1
                continue

            # Case 1: "45%" 또는 "45.5%" 단일 단어
            match = self._PERCENT_RE.search(text)
            if match:
                value = float(match.group(1))
                results.append(
                    OcrResult(
                        text=text,
                        confidence=conf,
                        bbox=(
                            data["left"][i],
                            data["top"][i],
                            data["width"][i],
                            data["height"][i],
                        ),
                        progress=value,
                        has_percent_sign=True,
                    )
                )
                used.add(i)
                i += 1
                continue

            # Case 2: "45" + "%" 분리 인식
            num_match = self._NUMBER_RE.search(text)
            if num_match and i + 1 < n_boxes:
                next_text = data["text"][i + 1].strip()
                if "%" in next_text:
                    value = float(num_match.group(1))
                    x1 = data["left"][i]
                    y1 = min(data["top"][i], data["top"][i + 1])
                    x2 = max(
                        data["left"][i] + data["width"][i],
                        data["left"][i + 1] + data["width"][i + 1],
                    )
                    y2 = max(
                        data["top"][i] + data["height"][i],
                        data["top"][i + 1] + data["height"][i + 1],
                    )
                    next_conf = float(data["conf"][i + 1])
                    results.append(
                        OcrResult(
                            text=f"{text}%",
                            confidence=min(conf, next_conf if next_conf >= 0 else conf),
                            bbox=(x1, y1, x2 - x1, y2 - y1),
                            progress=value,
                            has_percent_sign=True,
                        )
                    )
                    used.add(i)
                    used.add(i + 1)
                    i += 2
                    continue

            i += 1

        # Case 3: 단독 숫자 (0~100 범위) — Case 1, 2에서 처리되지 않은 것만
        for j in range(n_boxes):
            if j in used:
                continue
            text = data["text"][j].strip()
            conf = float(data["conf"][j])
            if conf < 0 or not text:
                continue
            num_match = self._NUMBER_RE.search(text)
            if num_match:
                value = float(num_match.group(1))
                if 0.0 <= value <= 100.0:
                    results.append(
                        OcrResult(
                            text=text,
                            confidence=conf,
                            bbox=(
                                data["left"][j],
                                data["top"][j],
                                data["width"][j],
                                data["height"][j],
                            ),
                            progress=value,
                            has_percent_sign=False,
                        )
                    )

        log.info("OCR 탐지 완료: %d개 숫자 발견", len(results))
        return results

    def read_progress(
        self, image: PILImage.Image, region_id: str = "",
    ) -> float | None:
        """이미지에서 가장 적합한 퍼센트 값을 반환한다.

        변화 감지: region_id가 지정되면 이전 캐콉과 픽셀 비교 후
        변화가 없으면 OCR을 스킵하고 캐시된 결과를 반환한다.

        Args:
            image: 캐콉된 PIL 이미지.
            region_id: 영역 ID (변화 감지용, 비어있으면 항상 OCR 실행).

        Returns:
            퍼센트 값 (0.0~100.0) 또는 None.
        """
        # 변화 감지 (성능 최적화)
        if region_id:
            img_hash = self._compute_hash(image)
            prev_hash = self._prev_hashes.get(region_id)
            if prev_hash == img_hash:
                cached = self._prev_results.get(region_id)
                log.debug("[%s] OCR 스킵 (변화 없음) → %.1f%%",
                          region_id, cached if cached is not None else 0.0)
                return cached
            self._prev_hashes[region_id] = img_hash

        results = self.find_percentages(image)
        if not results:
            if region_id:
                self._prev_results[region_id] = None
            return None

        # "%" 포함 결과 우선
        with_pct = [r for r in results if r.has_percent_sign]
        if with_pct:
            best = max(with_pct, key=lambda r: r.confidence)
            progress = best.progress
        else:
            # 단독 숫자 중 신뢰도 최고
            best = max(results, key=lambda r: r.confidence)
            progress = best.progress

        if region_id:
            self._prev_results[region_id] = progress
        return progress

    def reset_cache(self, region_id: str) -> None:
        """특정 영역의 변화 감지 캐시를 초기화한다."""
        self._prev_hashes.pop(region_id, None)
        self._prev_results.pop(region_id, None)

    @staticmethod
    def _compute_hash(image: PILImage.Image) -> str:
        """이미지의 픽셀 기반 해시를 계산한다.

        성능을 위해 이미지를 소형(32x32)으로 축소한 후 해싱한다.
        미세한 픽셀 노이즈는 무시하고 실제 내용 변화만 감지한다.
        """
        small = image.resize((32, 32), PILImage.Resampling.LANCZOS).convert("L")
        pixels = np.array(small, dtype=np.uint8)
        return hashlib.md5(pixels.tobytes()).hexdigest()
