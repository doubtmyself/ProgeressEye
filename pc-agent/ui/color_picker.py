"""바 탐지 결과 미리보기 다이얼로그.

영역 선택 후 탐지된 진행바 영역과 분석된 진행률을 보여준다.
영역 체크(빨간 사각형), 디버그 저장 기능 포함.
"""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PIL import Image as PILImage

from core.bar_finder import BarRegion
from utils.logger import log


class ImagePreview(QLabel):
    """이미지 미리보기 위젯 (크기 조절)."""

    def __init__(
        self, qimage: QImage, max_width: int = 340, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._qimage = qimage
        self._max_width = max_width
        self._apply_pixmap(qimage)

    def _apply_pixmap(self, qimage: QImage) -> None:
        """QImage를 표시 크기에 맞춰 설정한다."""
        pixmap = QPixmap.fromImage(qimage)
        display_w = min(self._max_width, pixmap.width())

        if pixmap.width() > display_w:
            displayed = pixmap.scaledToWidth(
                display_w, Qt.TransformationMode.SmoothTransformation
            )
        else:
            displayed = pixmap

        self.setPixmap(displayed)
        self.setFixedSize(displayed.size())

    def set_display_image(self, qimage: QImage) -> None:
        """표시 이미지를 변경한다."""
        self._apply_pixmap(qimage)


class BarPreviewDialog(QDialog):
    """바 탐지 결과 미리보기 다이얼로그.

    탐지된 진행바 영역과 분석된 진행률을 보여주고,
    사용자가 확인 또는 재선택을 선택한다.
    영역 체크(빨간 사각형), 디버그 저장 기능 포함.
    """

    def __init__(
        self,
        image: QImage,
        full_image: PILImage.Image,
        bar_image: PILImage.Image,
        detected_progress: float,
        bar_region: BarRegion | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image  # 전체 캡처 QImage (미리보기용)
        self._full_image = full_image  # 전체 캡처 PIL Image
        self._bar_image = bar_image  # 크롭된 바 PIL Image
        self._progress = detected_progress
        self._bar_region = bar_region

        self.setWindowTitle("바 탐지 결과")
        self.setFixedWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 이미지 미리보기
        self._preview = ImagePreview(self._image, max_width=340)
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # 방향 표시
        direction = "수평" if self._direction == "horizontal" else "수직"
        dir_label = QLabel(f"방향: {direction}")
        dir_label.setStyleSheet("color: #888; font-size: 11px;")
        dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dir_label)

        # 감지된 진행률
        self._progress_label = QLabel(f"감지된 진행률: {self._progress:.1f}%")
        self._progress_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self._progress_label)

        # 프로그레스바
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(int(self._progress * 10))
        self._progress_bar.setFormat(f"{self._progress:.1f}%")
        self._progress_bar.setFixedHeight(24)
        layout.addWidget(self._progress_bar)

        # 도구 행: 영역 체크 + 디버그 저장
        tools_row = QHBoxLayout()
        tools_row.addStretch()

        self._btn_area_check = QPushButton("🔍 영역 체크")
        self._btn_area_check.setToolTip("탐지된 바 영역을 빨간 사각형으로 표시")
        self._btn_area_check.clicked.connect(self._on_area_check)
        tools_row.addWidget(self._btn_area_check)

        self._btn_debug_save = QPushButton("💾 디버그 저장")
        self._btn_debug_save.setToolTip("temp/ 폴더에 디버그 이미지 저장")
        self._btn_debug_save.clicked.connect(self._on_debug_save)
        tools_row.addWidget(self._btn_debug_save)

        layout.addLayout(tools_row)

        # 버튼 영역
        btn_layout = QHBoxLayout()

        self._btn_reselect = QPushButton("재선택")
        self._btn_reselect.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_reselect)

        self._btn_confirm = QPushButton("확인")
        self._btn_confirm.setDefault(True)
        self._btn_confirm.setStyleSheet(
            "QPushButton { background-color: #4285F4; color: white; "
            "padding: 6px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3367D6; }"
        )
        self._btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_confirm)

        layout.addLayout(btn_layout)

    @property
    def _direction(self) -> str:
        """bar_region에서 자동 감지된 방향."""
        if self._bar_region is not None:
            return self._bar_region.direction
        return "horizontal"

    # ── 영역 체크 (빨간+시안 2줄 사각형 오버레이) ─────────────────
    def _on_area_check(self) -> None:
        """탐지된 바 영역을 빨간+시안 2줄 사각형으로 표시한다."""
        if self._bar_region is None:
            log.warning("탐지된 바 영역 없음 — 영역 체크 불가")
            return
        overlay = self._image.copy()
        painter = QPainter(overlay)
        br = self._bar_region
        # 외곽: 빨간 (255, 0, 0) 2px
        pen_red = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen_red)
        painter.drawRect(br.left, br.top, br.width, br.height)
        # 내곽: 시안 (0, 255, 255) 2px — 빨간보다 2px 안쪽
        pen_cyan = QPen(QColor(0, 255, 255), 2)
        painter.setPen(pen_cyan)
        painter.drawRect(br.left + 2, br.top + 2, br.width - 4, br.height - 4)
        painter.end()

        self._preview.set_display_image(overlay)
        log.info(
            "영역 체크 표시: (%d,%d)-(%d,%d) [%s]",
            br.left,
            br.top,
            br.right,
            br.bottom,
            br.direction,
        )

    # ── 디버그 저장 ──────────────────────────────────────

    def _on_debug_save(self) -> None:
        """디버그 이미지를 temp/ 폴더에 저장한다."""
        temp_dir = Path(__file__).resolve().parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        full_path = temp_dir / f"{ts}_full.png"
        self._full_image.save(str(full_path))

        bar_path = temp_dir / f"{ts}_bar.png"
        self._bar_image.save(str(bar_path))

        info_path = temp_dir / f"{ts}_info.txt"
        lines = [
            f"timestamp: {ts}",
            f"direction: {self._direction}",
            f"progress: {self._progress:.1f}%",
            f"bar_region: {self._bar_region}",
            f"full_size: {self._full_image.size}",
            f"bar_size: {self._bar_image.size}",
        ]
        info_path.write_text("\n".join(lines), encoding="utf-8")

        log.info("디버그 저장 완료: %s", temp_dir / ts)

    @property
    def progress(self) -> float:
        """감지된 진행률."""
        return self._progress
