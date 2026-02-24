"""샘플 이미지 탐지 테스트.

sample/ 폴더의 이미지에 대해 bar_finder + bar_analyzer를 실행하고,
결과를 sample/result/에 시각화하여 저장한다.

사각형 표시:
  - 빨간색: 탐지된 바 전체 영역 (bar_finder)
  - 시안색: 채워진 부분 영역 (bar_analyzer 결과)
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from core.bar_finder import BarFinder
from core.bar_analyzer import BarAnalyzer


def main() -> None:
    sample_dir = Path("sample")
    result_dir = sample_dir / "result"
    result_dir.mkdir(exist_ok=True)

    finder = BarFinder()
    analyzer = BarAnalyzer()

    files = sorted(f for f in sample_dir.iterdir() if f.suffix == ".png")

    for img_path in files:
        print(f"\n{'=' * 60}")
        print(f"[{img_path.name}]")

        pil_img = Image.open(img_path)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        w, h = pil_img.size
        print(f"  크기: {w}x{h}")

        # ── bar_finder ──
        bar_region = finder.find(pil_img)
        if bar_region is None:
            print("  바 탐지 실패 (이미지 너무 작음)")
            continue

        print(
            f"  바 영역: ({bar_region.left},{bar_region.top})-"
            f"({bar_region.right},{bar_region.bottom}) "
            f"{bar_region.width}x{bar_region.height} "
            f"신뢰도={bar_region.confidence:.2f} "
            f"방향={bar_region.direction}"
        )

        # ── bar_analyzer ──
        bar_image = pil_img.crop(bar_region.bbox)
        result = analyzer.analyze(bar_image, direction=bar_region.direction)
        print(
            f"  진행률: {result.progress:.1f}%  "
            f"신뢰도={result.confidence:.2f}  "
            f"채움={result.filled_columns}/{result.total_columns}열"
        )

        # ── 시각화 ──
        vis = np.array(pil_img)
        vis = cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)

        # 빨간 사각형: 바 전체 영역
        cv2.rectangle(
            vis,
            (bar_region.left, bar_region.top),
            (bar_region.right - 1, bar_region.bottom - 1),
            (0, 0, 255),  # BGR red
            2,
        )

        # 시안 사각형: 채워진 부분
        if result.total_columns > 0 and result.filled_columns > 0:
            fill_ratio = result.filled_columns / result.total_columns
            if bar_region.direction == "horizontal":
                fill_right = bar_region.left + int(bar_region.width * fill_ratio)
                cv2.rectangle(
                    vis,
                    (bar_region.left + 2, bar_region.top + 2),
                    (fill_right - 1, bar_region.bottom - 3),
                    (255, 255, 0),  # BGR cyan
                    2,
                )
            else:
                fill_bottom = bar_region.bottom - int(bar_region.height * fill_ratio)
                cv2.rectangle(
                    vis,
                    (bar_region.left + 2, fill_bottom),
                    (bar_region.right - 3, bar_region.bottom - 3),
                    (255, 255, 0),
                    2,
                )

        # 텍스트 오버레이
        label = f"{result.progress:.1f}% (conf={result.confidence:.2f})"
        text_y = max(bar_region.top - 8, 16)
        cv2.putText(
            vis,
            label,
            (bar_region.left, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

        # 저장
        out_path = result_dir / img_path.name
        cv2.imwrite(str(out_path), vis)
        print(f"  저장: {out_path}")

    print(f"\n{'=' * 60}")
    print(f"결과 저장 완료: {result_dir}")


if __name__ == "__main__":
    main()
