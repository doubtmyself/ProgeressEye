"""다운스케일 정확도 비교 테스트.

sample/ 폴더의 이미지를 3가지 모드로 분석하고,
결과를 이미지 위에 표기하여 result1/ 폴더에 저장한다.

모드:
  1. Original (100%) — 원본 크기
  2. Downscale (50%) — 50% 축소
  3. Smart — 50% 시도 → 신뢰도 < 0.5면 원본으로 fallback
"""

import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.bar_finder import BarFinder
from core.bar_analyzer import BarAnalyzer

CONFIDENCE_THRESHOLD = 0.5


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """사용 가능한 폰트를 반환한다."""
    font_paths = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgungbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for fp in font_paths:
        if os.path.isfile(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def run_analysis(
    image: Image.Image,
    finder: BarFinder,
    analyzer: BarAnalyzer,
    downscale: float = 1.0,
) -> dict:
    """이미지를 분석하고 결과를 반환한다."""
    start = time.perf_counter()
    bar_region = finder.find(image, downscale=downscale)
    bar_image = image.crop(bar_region.bbox) if bar_region else image
    direction = bar_region.direction if bar_region else "horizontal"
    result = analyzer.analyze(bar_image, direction=direction, downscale=downscale)
    elapsed = time.perf_counter() - start

    return {
        "progress": result.progress,
        "confidence": result.confidence,
        "bar_region": bar_region,
        "elapsed_ms": elapsed * 1000,
        "fallback": False,
    }


def run_smart_analysis(
    image: Image.Image,
    finder: BarFinder,
    analyzer: BarAnalyzer,
    downscale: float = 0.5,
) -> dict:
    """스마트 분석: 다운스케일 시도 → 신뢰도 낮으면 원본 fallback."""
    start = time.perf_counter()

    # 1차: 다운스케일 시도
    bar_region = finder.find(image, downscale=downscale)
    bar_image = image.crop(bar_region.bbox) if bar_region else image
    direction = bar_region.direction if bar_region else "horizontal"
    result = analyzer.analyze(bar_image, direction=direction, downscale=downscale)

    used_fallback = False

    # 2차: fallback 조건
    # - 신뢰도가 임계값 미만
    # - uniform bar 판정(0%/100%)이면서 신뢰도가 낮음 (다운스케일 아티팩트 가능성)
    needs_fallback = (
        result.confidence < CONFIDENCE_THRESHOLD
        or (result.confidence <= 0.7 and result.progress in (0.0, 100.0))
    )
    if needs_fallback:
        bar_region = finder.find(image, downscale=1.0)
        bar_image = image.crop(bar_region.bbox) if bar_region else image
        direction = bar_region.direction if bar_region else "horizontal"
        result = analyzer.analyze(bar_image, direction=direction, downscale=1.0)
        used_fallback = True

    elapsed = time.perf_counter() - start

    return {
        "progress": result.progress,
        "confidence": result.confidence,
        "bar_region": bar_region,
        "elapsed_ms": elapsed * 1000,
        "fallback": used_fallback,
    }


def draw_result_on_image(
    image: Image.Image,
    original: dict,
    downscaled: dict,
    smart: dict,
    filename: str,
) -> Image.Image:
    """분석 결과를 이미지 위에 표기한다."""
    # 이미지가 너무 작으면 확대
    min_width = 600
    scale = 1
    if image.width < min_width:
        scale = max(2, min_width // image.width)
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )

    # 상단에 결과 패널 추가
    panel_h = 160
    canvas_w = max(image.width, 700)
    canvas = Image.new("RGB", (canvas_w, image.height + panel_h), (15, 15, 26))
    # 이미지 중앙 배치
    x_offset = (canvas_w - image.width) // 2
    canvas.paste(image, (x_offset, panel_h))

    draw = ImageDraw.Draw(canvas)
    font_title = get_font(16)
    font_body = get_font(13)
    font_small = get_font(11)

    # 제목
    draw.text(
        (10, 6),
        f"{filename}  ({image.width}x{image.height})",
        fill=(255, 255, 255),
        font=font_title,
    )

    # 3열 레이아웃
    col_w = canvas_w // 3
    cols = [
        ("Original (100%)", (74, 222, 128), original),
        ("Downscale (50%)", (59, 130, 246), downscaled),
        ("Smart (fallback)", (255, 200, 50), smart),
    ]

    y_start = 28
    for i, (label, color, data) in enumerate(cols):
        x = 10 + i * col_w

        draw.text((x, y_start), f"▶ {label}", fill=color, font=font_body)

        prog_text = f"  Progress: {data['progress']:.1f}%"
        draw.text((x, y_start + 18), prog_text, fill=(255, 255, 255), font=font_small)

        conf_text = f"  Confidence: {data['confidence']:.2f}"
        conf_color = (74, 222, 128) if data["confidence"] >= 0.5 else (239, 68, 68)
        draw.text((x, y_start + 33), conf_text, fill=conf_color, font=font_small)

        time_text = f"  Time: {data['elapsed_ms']:.1f}ms"
        draw.text((x, y_start + 48), time_text, fill=(136, 136, 170), font=font_small)

        if data.get("fallback"):
            draw.text(
                (x, y_start + 63),
                "  → Fallback to 100%",
                fill=(239, 68, 68),
                font=font_small,
            )

    # 하단 요약 라인
    y_summary = y_start + 82
    diff_ds = abs(original["progress"] - downscaled["progress"])
    diff_sm = abs(original["progress"] - smart["progress"])
    speedup_ds = (
        original["elapsed_ms"] / downscaled["elapsed_ms"]
        if downscaled["elapsed_ms"] > 0
        else 0
    )
    speedup_sm = (
        original["elapsed_ms"] / smart["elapsed_ms"] if smart["elapsed_ms"] > 0 else 0
    )

    # 결과 요약
    ds_color = (74, 222, 128) if diff_ds < 1.0 else (239, 68, 68)
    sm_color = (74, 222, 128) if diff_sm < 1.0 else (239, 68, 68)

    summary = (
        f"Δ Downscale: {diff_ds:.1f}% ({speedup_ds:.1f}x faster)  |  "
        f"Δ Smart: {diff_sm:.1f}% ({speedup_sm:.1f}x faster)"
    )

    # Draw each part with different colors
    draw.text(
        (10, y_summary),
        f"Δ Downscale: {diff_ds:.1f}% ({speedup_ds:.1f}x faster)",
        fill=ds_color,
        font=font_small,
    )
    draw.text(
        (10 + col_w + col_w // 2, y_summary),
        f"Δ Smart: {diff_sm:.1f}% ({speedup_sm:.1f}x faster)",
        fill=sm_color,
        font=font_small,
    )

    # 구분선
    draw.line([(0, panel_h - 2), (canvas_w, panel_h - 2)], fill=(42, 42, 69), width=2)

    return canvas


def main() -> None:
    sample_dir = ROOT / "sampleBar"
    result_dir = ROOT / "sampleBar" / "result1"
    result_dir.mkdir(exist_ok=True)

    finder = BarFinder()
    analyzer = BarAnalyzer()

    image_files = sorted(sample_dir.glob("image*.png"))
    if not image_files:
        print("sample/ 폴더에 이미지가 없습니다.")
        return

    print(f"테스트 이미지 {len(image_files)}개 발견")
    print(f"신뢰도 임계값: {CONFIDENCE_THRESHOLD}\n")
    header = (
        f"{'파일':<15} "
        f"{'원본%':>8} {'50%%':>8} {'Smart%':>8} "
        f"{'Δ50%':>7} {'ΔSm':>7} "
        f"{'원본ms':>9} {'50%ms':>9} {'Smms':>9} "
        f"{'FB':>4}"
    )
    print(header)
    print("-" * 100)

    total_orig_ms = 0.0
    total_ds_ms = 0.0
    total_sm_ms = 0.0
    max_diff_ds = 0.0
    max_diff_sm = 0.0

    for img_path in image_files:
        image = Image.open(img_path).convert("RGB")
        filename = img_path.name

        # 3가지 분석
        orig = run_analysis(image, finder, analyzer, downscale=1.0)
        ds50 = run_analysis(image, finder, analyzer, downscale=0.5)
        smart = run_smart_analysis(image, finder, analyzer, downscale=0.5)

        diff_ds = abs(orig["progress"] - ds50["progress"])
        diff_sm = abs(orig["progress"] - smart["progress"])

        total_orig_ms += orig["elapsed_ms"]
        total_ds_ms += ds50["elapsed_ms"]
        total_sm_ms += smart["elapsed_ms"]
        max_diff_ds = max(max_diff_ds, diff_ds)
        max_diff_sm = max(max_diff_sm, diff_sm)

        fb = "YES" if smart["fallback"] else "-"

        print(
            f"{filename:<15} "
            f"{orig['progress']:>7.1f}% "
            f"{ds50['progress']:>7.1f}% "
            f"{smart['progress']:>7.1f}% "
            f"{diff_ds:>6.1f}% "
            f"{diff_sm:>6.1f}% "
            f"{orig['elapsed_ms']:>8.1f} "
            f"{ds50['elapsed_ms']:>8.1f} "
            f"{smart['elapsed_ms']:>8.1f} "
            f"{fb:>4}"
        )

        # 결과 이미지 생성 + 저장
        result_img = draw_result_on_image(image, orig, ds50, smart, filename)
        result_img.save(result_dir / filename)

    print("-" * 100)
    speedup_ds = total_orig_ms / total_ds_ms if total_ds_ms > 0 else 0
    speedup_sm = total_orig_ms / total_sm_ms if total_sm_ms > 0 else 0
    print(
        f"{'합계':<15} "
        f"{'':>8} {'':>8} {'':>8} "
        f"{max_diff_ds:>6.1f}% "
        f"{max_diff_sm:>6.1f}% "
        f"{total_orig_ms:>8.1f} "
        f"{total_ds_ms:>8.1f} "
        f"{total_sm_ms:>8.1f} "
        f"{'':>4}"
    )
    print(f"\n속도: 50% = {speedup_ds:.1f}x faster | Smart = {speedup_sm:.1f}x faster")
    print(f"최대 오차: 50% = {max_diff_ds:.1f}% | Smart = {max_diff_sm:.1f}%")
    print(f"\n결과 저장 완료: {result_dir}")


if __name__ == "__main__":
    main()
