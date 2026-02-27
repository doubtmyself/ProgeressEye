"""samplePersent/ OCR 정확도 테스트.

각 이미지에 대해:
  1. OcrReader.find_percentages() — 탐지된 모든 결과 (bbox, 신뢰도, 텍스트)
  2. OcrReader.read_progress() — 최종 진행률
결과를 이미지 위에 표기하여 samplePersent/result/ 에 저장한다.
"""

import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.ocr_reader import OcrReader, OcrResult  # noqa: E402


# 기대값 (이미지 파일명 → 기대 퍼센트)
EXPECTED: dict[str, float] = {
    "image1.png": 40.0,
    "image2.png": 68.0,
    "image3.png": 91.0,
    "image4.png": 61.0,
}


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


def draw_result(
    image: Image.Image,
    results: list[OcrResult],
    progress: float | None,
    expected: float,
    elapsed_ms: float,
    filename: str,
) -> Image.Image:
    """OCR 결과를 이미지 위에 표기한다."""
    # 작은 이미지는 확대
    min_width = 600
    scale = 1
    if image.width < min_width:
        scale = max(2, min_width // image.width)
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )

    # 결과 패널 높이 계산
    line_h = 18
    header_h = 60
    detail_lines = max(len(results), 1)
    summary_h = 70
    panel_h = header_h + detail_lines * line_h + summary_h

    canvas_w = max(image.width, 650)
    canvas = Image.new("RGB", (canvas_w, image.height + panel_h), (15, 15, 26))

    # 이미지 중앙 배치
    x_offset = (canvas_w - image.width) // 2
    canvas.paste(image, (x_offset, panel_h))

    draw = ImageDraw.Draw(canvas)
    ft = get_font(16)
    fs = get_font(13)
    fb = get_font(11)

    # 헤더
    draw.text((10, 8), f"📄 {filename}", fill=(255, 255, 255), font=ft)
    draw.text(
        (10, 30),
        f"Expected: {expected:.1f}%   |   OCR Time: {elapsed_ms:.1f}ms",
        fill=(136, 136, 170),
        font=fs,
    )

    # 구분선
    draw.line([(0, header_h - 4), (canvas_w, header_h - 4)], fill=(42, 42, 69), width=1)

    # 탐지 결과 상세
    y = header_h
    if results:
        draw.text((10, y), "▶ 탐지 결과", fill=(59, 130, 246), font=fs)
        y += line_h
        for idx, r in enumerate(results):
            pct_tag = "(%)" if r.has_percent_sign else "(숫자)"
            color = (74, 222, 128) if r.has_percent_sign else (255, 200, 100)
            draw.text(
                (20, y),
                f'  #{idx + 1}  text="{r.text}"  progress={r.progress:.1f}%  '
                f"conf={r.confidence:.0f}  bbox={r.bbox}  {pct_tag}",
                fill=color,
                font=fb,
            )
            y += line_h
    else:
        draw.text((10, y), "▶ 탐지 결과: 없음", fill=(239, 68, 68), font=fs)
        y += line_h

    # 구분선
    y += 4
    draw.line([(0, y), (canvas_w, y)], fill=(42, 42, 69), width=1)
    y += 8

    # 최종 진행률
    draw.text((10, y), "▶ 최종 결과", fill=(59, 130, 246), font=fs)
    y += line_h + 2

    if progress is not None:
        error = abs(progress - expected)
        is_correct = error < 1.0
        result_color = (74, 222, 128) if is_correct else (239, 68, 68)
        status = "✅ PASS" if is_correct else "❌ FAIL"
        draw.text(
            (20, y),
            f"  read_progress() = {progress:.1f}%   오차: {error:.1f}%   {status}",
            fill=result_color,
            font=fs,
        )
    else:
        draw.text(
            (20, y),
            "  read_progress() = None   ❌ FAIL (인식 실패)",
            fill=(239, 68, 68),
            font=fs,
        )

    # 이미지 위에 bbox 그리기
    for r in results:
        bx, by, bw, bh = r.bbox
        bx, by, bw, bh = bx * scale, by * scale, bw * scale, bh * scale
        draw.rectangle(
            [
                (x_offset + bx, panel_h + by),
                (x_offset + bx + bw, panel_h + by + bh),
            ],
            outline=(59, 130, 246),
            width=2,
        )
        # bbox 위에 라벨
        label = f"{r.progress:.0f}%  (conf:{r.confidence:.0f})"
        draw.text(
            (x_offset + bx, panel_h + by - 14),
            label,
            fill=(59, 130, 246),
            font=fb,
        )

    # 하단 구분선
    draw.line([(0, panel_h - 2), (canvas_w, panel_h - 2)], fill=(42, 42, 69), width=2)

    return canvas


def main() -> None:
    sample_dir = ROOT / "samplePersent"
    result_dir = sample_dir / "result"
    result_dir.mkdir(exist_ok=True)

    reader = OcrReader()

    image_files = sorted(sample_dir.glob("image*.png"))
    if not image_files:
        print("테스트 이미지가 없습니다.")
        return

    print(f"OCR Accuracy Test — {len(image_files)} images\n")
    print(
        f"{'파일':<15} {'기대값':>8} {'결과':>8} {'오차':>8} {'시간':>10} {'판정':>8}"
    )
    print("-" * 65)

    pass_count = 0
    total_count = len(image_files)

    for img_path in image_files:
        image = Image.open(img_path).convert("RGB")
        filename = img_path.name
        expected = EXPECTED.get(filename, -1.0)

        # find_percentages — 상세 결과
        results = reader.find_percentages(image)

        # read_progress — 최종 진행률 + 시간 측정
        start = time.perf_counter()
        progress = reader.read_progress(image, region_id=filename)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 판정
        if progress is not None:
            error = abs(progress - expected)
            is_pass = error < 1.0
        else:
            error = expected
            is_pass = False

        if is_pass:
            pass_count += 1

        status = "✅ PASS" if is_pass else "❌ FAIL"
        prog_str = f"{progress:.1f}%" if progress is not None else "None"

        print(
            f"{filename:<15} "
            f"{expected:>7.1f}% "
            f"{prog_str:>7} "
            f"{error:>7.1f}% "
            f"{elapsed_ms:>9.1f}ms "
            f"{status:>8}"
        )

        # 결과 이미지 저장
        result_img = draw_result(
            image, results, progress, expected, elapsed_ms, filename
        )
        result_img.save(result_dir / filename)

    print(
        f"\n총 {total_count}개 중 {pass_count}개 통과 ({pass_count / total_count * 100:.0f}%)"
    )
    print(f"결과 저장 완료: {result_dir}/")


if __name__ == "__main__":
    main()
