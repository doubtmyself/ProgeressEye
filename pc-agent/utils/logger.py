"""ProgressEye 로깅 유틸리티."""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "progresseye", level: int = logging.INFO) -> logging.Logger:
    """애플리케이션 로거를 설정한다.

    Args:
        name: 로거 이름.
        level: 로깅 레벨.

    Returns:
        설정된 Logger 인스턴스.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (AppData)
    log_dir = Path.home() / "AppData" / "Local" / "ProgressEye" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "progresseye.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


log = setup_logger()