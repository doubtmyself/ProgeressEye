"""Tesseract OCR 번들 설치 스크립트.

배포용 exe 빌드 전, 또는 다른 개발 환경에서
pc-agent/tesseract/ 에 Tesseract OCR을 복사한다.

사용법:
    python setup_tesseract.py
"""

import shutil
import sys
from pathlib import Path

# 소스: Tesseract 시스템 설치 경로
SOURCE = Path(r"C:\Program Files\Tesseract-OCR")

# 대상: pc-agent/tesseract/
DEST = Path(__file__).resolve().parent / "tesseract"

# 필수 tessdata 파일
TESSDATA_FILES = ["eng.traineddata", "osd.traineddata"]


def main() -> None:
    if not SOURCE.is_dir():
        print(f"오류: Tesseract가 설치되지 않았습니다: {SOURCE}")
        print("https://github.com/UB-Mannheim/tesseract/wiki 에서 설치하세요.")
        sys.exit(1)

    # 대상 디렉토리 생성
    DEST.mkdir(exist_ok=True)
    tessdata_dest = DEST / "tessdata"
    tessdata_dest.mkdir(exist_ok=True)

    # tesseract.exe 복사
    copied = 0
    exe = SOURCE / "tesseract.exe"
    if exe.is_file():
        shutil.copy2(exe, DEST / "tesseract.exe")
        copied += 1

    # DLL 복사
    for dll in SOURCE.glob("*.dll"):
        shutil.copy2(dll, DEST / dll.name)
        copied += 1

    # tessdata 필수 파일 복사
    for name in TESSDATA_FILES:
        src = SOURCE / "tessdata" / name
        if src.is_file():
            shutil.copy2(src, tessdata_dest / name)
            copied += 1
        else:
            print(f"경고: {src} 파일을 찾을 수 없습니다.")

    print(f"완료: {copied}개 파일을 {DEST} 에 복사했습니다.")


if __name__ == "__main__":
    main()
