"""OCR 기반 숫자(%) 인식 모듈.

pytesseract를 사용하여 이미지에서 숫자% 패턴을 탐지하고
바운딩 박스와 함께 반환한다.

필수 의존성:
  pip install pytesseract
  Tesseract OCR 설치: https://github.com/UB-Mannheim/tesseract/wiki
"""

import os
import re
import shutil
from dataclasses import dataclass
from PIL import Image as PILImage

from utils.logger import log

try:
    import pytesseract
    # Windows 기본 설치 경로 자동 탐지
    if shutil.which("tesseract") is None:
        _default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(_default):
            pytesseract.pytesseract.tesseract_cmd = _default
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


class OcrReader:
    """OCR 기반 숫자% 리더.

    pytesseract를 사용하여 이미지에서 숫자% 패턴을 찾는다.
    """

    _PERCENT_RE = re.compile(r"(\d+\.?\d*)\s*%")
    _NUMBER_RE = re.compile(r"(\d+\.?\d*)")

    def find_percentages(self, image: PILImage.Image) -> list[OcrResult]:
        """이미지에서 숫자% 패턴을 찾아 바운딩 박스와 함께 반환한다.

        pytesseract.image_to_data()로 단어별 바운딩 박스를 얻고,
        숫자% 패턴에 매칭되는 항목을 반환한다.

        "45%" 단일 단어와 "45" + "%" 분리 인식 모두 처리한다.
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
                config="--oem 3 --psm 6",
            )
        except Exception as e:
            log.error("OCR 실행 실패: %s", e)
            return []

        n_boxes = len(data["text"])
        results: list[OcrResult] = []
        i = 0

        while i < n_boxes:
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            if conf < 0 or not text:
                i += 1
                continue

            # Case 1: "45%" 또는 "45.5%" 단일 단어
            match = self._PERCENT_RE.fullmatch(text)
            if match:
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
                        progress=float(match.group(1)),
                    )
                )
                i += 1
                continue

            # Case 2: "45" + "%" 분리 인식
            num_match = self._NUMBER_RE.fullmatch(text)
            if num_match and i + 1 < n_boxes:
                next_text = data["text"][i + 1].strip()
                if next_text == "%":
                    # 두 단어 바운딩 박스 병합
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
                            progress=float(num_match.group(1)),
                        )
                    )
                    i += 2
                    continue

            i += 1

        log.info("OCR 탐지 완료: %d개 숫자%% 발견", len(results))
        return results

    def read_progress(self, image: PILImage.Image) -> float | None:
        """이미지에서 가장 신뢰도 높은 퍼센트 값을 반환한다.

        탐지 실패 시 None을 반환한다.
        """
        results = self.find_percentages(image)
        if not results:
            return None
        best = max(results, key=lambda r: r.confidence)
        return best.progress
