"""OCR 최적화 전후 비교 테스트.

sample/ 이미지를 구버전(--oem 3 --psm 6) vs 신버전(--oem 1 --psm 7 + whitelist)으로 분석하고,
변화 감지(skip) 효과도 측정한다.
결과를 이미지 위에 표기하여 result1/ 폴더에 저장한다.
"""

import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pytesseract  # noqa: E402
from core.ocr_reader import OcrReader  # noqa: E402


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for fp in [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.isfile(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def ocr_with_config(image: Image.Image, config: str) -> tuple[str, float, float]:
    """지정 config로 OCR을 실행하고 (결과텍스트, 소요시간ms, 진행률)을 반환."""
    gray = image.convert("L")
    start = time.perf_counter()
    try:
        data = pytesseract.image_to_data(
            gray,
            output_type=pytesseract.Output.DICT,
            config=config,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return f"ERROR: {e}", elapsed, -1.0
    elapsed = (time.perf_counter() - start) * 1000

    # 텍스트 추출
    texts = []
    for i, t in enumerate(data["text"]):
        t = t.strip()
        if t and float(data["conf"][i]) > 0:
            texts.append(t)
    raw_text = " ".join(texts)

    # 진행률 추출
    import re

    m = re.search(r"(\d+\.?\d*)\s*%", raw_text)
    if m:
        return raw_text, elapsed, float(m.group(1))
    m = re.search(r"(\d+\.?\d*)", raw_text)
    if m:
        val = float(m.group(1))
        if 0 <= val <= 100:
            return raw_text, elapsed, val
    return raw_text, elapsed, -1.0


def test_change_detection(image: Image.Image) -> tuple[float, float]:
    """변화 감지 테스트: 동일 이미지 2회 호출 시 2번째 skip 시간."""
    reader = OcrReader()

    # 1회차: 실제 OCR
    start = time.perf_counter()
    reader.read_progress(image, region_id="test_region")
    first_ms = (time.perf_counter() - start) * 1000

    # 2회차: 변화 없음 → skip
    start = time.perf_counter()
    reader.read_progress(image, region_id="test_region")
    second_ms = (time.perf_counter() - start) * 1000

    return first_ms, second_ms


def draw_ocr_result(
    image: Image.Image,
    old_result: tuple[str, float, float],
    new_result: tuple[str, float, float],
    change_times: tuple[float, float],
    filename: str,
) -> Image.Image:
    """OCR 결과를 이미지 위에 표기."""
    min_width = 700
    scale = 1
    if image.width < min_width:
        scale = max(2, min_width // image.width)
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )

    panel_h = 180
    canvas_w = max(image.width, 750)
    canvas = Image.new("RGB", (canvas_w, image.height + panel_h), (15, 15, 26))
    x_offset = (canvas_w - image.width) // 2
    canvas.paste(image, (x_offset, panel_h))

    draw = ImageDraw.Draw(canvas)
    ft = get_font(16)
    fs = get_font(12)
    fb = get_font(11)

    draw.text((10, 6), f"{filename}", fill=(255, 255, 255), font=ft)

    # Old config
    y = 28
    draw.text((10, y), "▶ Before (--oem 3 --psm 6)", fill=(239, 68, 68), font=fs)
    draw.text(
        (10, y + 17), f"  Text: {old_result[0][:50]}", fill=(200, 200, 200), font=fb
    )
    draw.text(
        (10, y + 32),
        f"  Progress: {old_result[2]:.1f}%"
        if old_result[2] >= 0
        else "  Progress: N/A",
        fill=(255, 255, 255),
        font=fb,
    )
    draw.text(
        (10, y + 47), f"  Time: {old_result[1]:.1f}ms", fill=(136, 136, 170), font=fb
    )

    # New config
    x2 = canvas_w // 2
    draw.text((x2, y), "▶ After (--oem 1 --psm 7 +WL)", fill=(74, 222, 128), font=fs)
    draw.text(
        (x2, y + 17), f"  Text: {new_result[0][:50]}", fill=(200, 200, 200), font=fb
    )
    draw.text(
        (x2, y + 32),
        f"  Progress: {new_result[2]:.1f}%"
        if new_result[2] >= 0
        else "  Progress: N/A",
        fill=(255, 255, 255),
        font=fb,
    )
    draw.text(
        (x2, y + 47), f"  Time: {new_result[1]:.1f}ms", fill=(136, 136, 170), font=fb
    )

    # Speed comparison
    speedup = old_result[1] / new_result[1] if new_result[1] > 0 else 0
    draw.text(
        (x2, y + 62),
        f"  → {speedup:.1f}x faster",
        fill=(74, 222, 128) if speedup > 1 else (239, 68, 68),
        font=fb,
    )

    # Change detection
    y2 = y + 85
    draw.text(
        (10, y2), "▶ Change Detection (동일 이미지 2회)", fill=(59, 130, 246), font=fs
    )
    draw.text(
        (10, y2 + 17),
        f"  1st call (OCR): {change_times[0]:.1f}ms",
        fill=(136, 136, 170),
        font=fb,
    )
    draw.text(
        (10, y2 + 32),
        f"  2nd call (skip): {change_times[1]:.3f}ms",
        fill=(74, 222, 128),
        font=fb,
    )
    skip_ratio = change_times[0] / change_times[1] if change_times[1] > 0 else 0
    draw.text(
        (10, y2 + 47),
        f"  → {skip_ratio:.0f}x faster (skip)",
        fill=(74, 222, 128),
        font=fb,
    )

    draw.line([(0, panel_h - 2), (canvas_w, panel_h - 2)], fill=(42, 42, 69), width=2)
    return canvas


def main() -> None:
    # OCR 테스트용 이미지 수집 (samplePersent + sampleBar 중 텍스트 포함 이미지)
    result_dir = ROOT / "sampleBar" / "result1"
    result_dir.mkdir(exist_ok=True)

    OLD_CONFIG = "--oem 3 --psm 6"
    NEW_CONFIG = "--oem 1 --psm 6"

    image_files: list[Path] = []
    # samplePersent 폴더
    sp = ROOT / "samplePersent"
    if sp.exists():
        image_files.extend(sorted(sp.glob("image*.png")))
    # sampleBar 폴더 (텍스트 포함 이미지들도 OCR 테스트)
    sb = ROOT / "sampleBar"
    if sb.exists():
        image_files.extend(sorted(sb.glob("image*.png")))

    if not image_files:
        print("테스트 이미지가 없습니다.")
        return

    print(f"OCR optimization test - {len(image_files)} images\n")
    print(
        f"{'파일':<15} {'Old text':>20} {'Old ms':>9} {'New text':>20} {'New ms':>9} {'속도':>7} {'Skip ms':>10}"
    )
    print("-" * 100)

    for img_path in image_files:
        image = Image.open(img_path).convert("RGB")
        filename = img_path.name

        old = ocr_with_config(image, OLD_CONFIG)
        new = ocr_with_config(image, NEW_CONFIG)
        change_times = test_change_detection(image)

        speedup = old[1] / new[1] if new[1] > 0 else 0

        print(
            f"{filename:<15} "
            f"{old[0][:20]:>20} "
            f"{old[1]:>8.1f} "
            f"{new[0][:20]:>20} "
            f"{new[1]:>8.1f} "
            f"{speedup:>6.1f}x "
            f"{change_times[1]:>9.3f}"
        )

        # OCR 결과 이미지는 _ocr 접미사로 저장
        result_img = draw_ocr_result(image, old, new, change_times, filename)
        result_img.save(result_dir / f"ocr_{filename}")

    print(f"\n결과 저장 완료: {result_dir}/ocr_*.png")


if __name__ == "__main__":
    main()
