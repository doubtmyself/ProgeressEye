"""색상 미리보기 및 클릭 지정 다이얼로그.

영역 선택 후 감지된 채움/빈 색상을 보여주고,
스크린샷을 클릭하여 색상을 직접 지정할 수 있다.
영역 체크(빨간 사각형), 디버그 저장 기능 포함.
방향(수평/수직)은 BarFinder가 자동 판별한다.
"""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PIL import Image as PILImage

from core.bar_analyzer import BarAnalyzer
from core.bar_finder import BarRegion
from utils.logger import log


class ClickablePreview(QLabel):
    """클릭으로 픽셀 색상을 추출하는 이미지 미리보기.

    좌클릭 → 채움 색상, 우클릭 → 빈 색상을 해당 픽셀에서 추출한다.
    표시 이미지와 색상 추출 이미지를 분리하여
    빨간 사각형 오버레이 시에도 원본 색상을 추출할 수 있다.
    """

    fill_picked = pyqtSignal(int, int, int)  # r, g, b
    empty_picked = pyqtSignal(int, int, int)  # r, g, b

    def __init__(
        self, qimage: QImage, max_width: int = 340, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._qimage = qimage  # 색상 추출용 원본
        self._max_width = max_width

        self._apply_pixmap(qimage)
        self.setCursor(Qt.CursorShape.CrossCursor)

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

        self._scale_x = self._qimage.width() / max(displayed.width(), 1)
        self._scale_y = self._qimage.height() / max(displayed.height(), 1)

        self.setPixmap(displayed)
        self.setFixedSize(displayed.size())

    def set_display_image(self, qimage: QImage) -> None:
        """표시 이미지만 변경한다 (색상 추출은 원본 유지)."""
        self._apply_pixmap(qimage)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """클릭 위치의 픽셀 색상을 추출하여 시그널로 전달한다."""
        pos = event.pos()

        orig_x = max(0, min(int(pos.x() * self._scale_x), self._qimage.width() - 1))
        orig_y = max(0, min(int(pos.y() * self._scale_y), self._qimage.height() - 1))

        pixel = self._qimage.pixelColor(orig_x, orig_y)
        r, g, b = pixel.red(), pixel.green(), pixel.blue()

        if event.button() == Qt.MouseButton.LeftButton:
            self.fill_picked.emit(r, g, b)
        elif event.button() == Qt.MouseButton.RightButton:
            self.empty_picked.emit(r, g, b)


class ColorSwatch(QFrame):
    """색상 표시 스와치 위젯."""

    def __init__(
        self, color: tuple[int, int, int], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._color = color
        self._update_style()

    def set_color(self, color: tuple[int, int, int]) -> None:
        """색상을 변경한다."""
        self._color = color
        self._update_style()

    def _update_style(self) -> None:
        r, g, b = self._color
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); "
            f"border: 1px solid #666; border-radius: 4px;"
        )

    @property
    def color(self) -> tuple[int, int, int]:
        return self._color


class ColorPreviewDialog(QDialog):
    """색상 미리보기 및 조정 다이얼로그.

    감지된 채움/빈 색상과 진행률을 보여주고,
    스크린샷 클릭으로 색상을 직접 지정할 수 있다.
    영역 체크, 디버그 저장 기능 포함.
    """

    colors_confirmed = pyqtSignal(tuple, tuple)

    def __init__(
        self,
        image: QImage,
        full_image: PILImage.Image,
        pil_image: PILImage.Image,
        fill_color: tuple[int, int, int],
        empty_color: tuple[int, int, int],
        detected_progress: float,
        bar_region: BarRegion | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image  # 전체 캡처 QImage (미리보기용)
        self._full_image = full_image  # 전체 캡처 PIL Image
        self._pil_image = pil_image  # 크롭된 바 PIL Image
        self._fill_color = fill_color
        self._empty_color = empty_color
        self._progress = detected_progress
        self._bar_region = bar_region

        self._analyzer = BarAnalyzer()

        self.setWindowTitle("색상 감지 결과")
        self.setFixedWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    @property
    def _direction(self) -> str:
        """bar_region에서 자동 감지된 방향."""
        if self._bar_region is not None:
            return self._bar_region.direction
        return "horizontal"

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 클릭 가능한 이미지 미리보기
        self._preview = ClickablePreview(self._image, max_width=340)
        self._preview.fill_picked.connect(self._on_fill_picked)
        self._preview.empty_picked.connect(self._on_empty_picked)
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # 클릭 안내
        hint = QLabel("좌클릭: 채움 색상 지정  |  우클릭: 빈 색상 지정")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # 채움/빈 색상 — 같은 행에 컴팩트하게
        color_row = QHBoxLayout()

        color_row.addWidget(QLabel("채움:"))
        self._fill_swatch = ColorSwatch(self._fill_color)
        color_row.addWidget(self._fill_swatch)
        self._fill_hex = QLabel(self._color_hex(self._fill_color))
        self._fill_hex.setStyleSheet(
            "font-family: 'Consolas'; color: #555; font-size: 11px;"
        )
        color_row.addWidget(self._fill_hex)

        color_row.addSpacing(12)

        color_row.addWidget(QLabel("빈:"))
        self._empty_swatch = ColorSwatch(self._empty_color)
        color_row.addWidget(self._empty_swatch)
        self._empty_hex = QLabel(self._color_hex(self._empty_color))
        self._empty_hex.setStyleSheet(
            "font-family: 'Consolas'; color: #555; font-size: 11px;"
        )
        color_row.addWidget(self._empty_hex)

        color_row.addStretch()
        layout.addLayout(color_row)

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
        self._btn_confirm.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._btn_confirm)

        layout.addLayout(btn_layout)

    # ── 색상 클릭 핸들러 ─────────────────────────────────

    def _on_fill_picked(self, r: int, g: int, b: int) -> None:
        """이미지 좌클릭 — 채움 색상 지정."""
        self._fill_color = (r, g, b)
        self._fill_swatch.set_color(self._fill_color)
        self._fill_hex.setText(self._color_hex(self._fill_color))
        log.info("채움 색상 지정: %s", self._fill_color)
        self._re_analyze()

    def _on_empty_picked(self, r: int, g: int, b: int) -> None:
        """이미지 우클릭 — 빈 색상 지정."""
        self._empty_color = (r, g, b)
        self._empty_swatch.set_color(self._empty_color)
        self._empty_hex.setText(self._color_hex(self._empty_color))
        log.info("빈 색상 지정: %s", self._empty_color)
        self._re_analyze()

    # ── 영역 체크 (빨간 사각형 오버레이) ─────────────────

    def _on_area_check(self) -> None:
        """탐지된 바 영역을 빨간 사각형으로 표시한다."""
        if self._bar_region is None:
            log.warning("탐지된 바 영역 없음 — 영역 체크 불가")
            return

        overlay = self._image.copy()
        painter = QPainter(overlay)
        pen = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen)

        br = self._bar_region
        painter.drawRect(br.left, br.top, br.width, br.height)
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
        self._pil_image.save(str(bar_path))

        info_path = temp_dir / f"{ts}_info.txt"
        lines = [
            f"timestamp: {ts}",
            f"direction: {self._direction}",
            f"fill_color: {self._fill_color}",
            f"empty_color: {self._empty_color}",
            f"progress: {self._progress:.1f}%",
            f"bar_region: {self._bar_region}",
            f"full_size: {self._full_image.size}",
            f"bar_size: {self._pil_image.size}",
        ]
        info_path.write_text("\n".join(lines), encoding="utf-8")

        log.info("디버그 저장 완료: %s", temp_dir / ts)

    # ── 재분석 ───────────────────────────────────────────

    def _re_analyze(self) -> None:
        """변경된 색상으로 진행률을 재분석한다."""
        result = self._analyzer.analyze(
            self._pil_image,
            self._fill_color,
            self._empty_color,
            direction=self._direction,
        )
        self._progress = result.progress
        self._progress_label.setText(f"감지된 진행률: {self._progress:.1f}%")
        self._progress_bar.setValue(int(self._progress * 10))
        self._progress_bar.setFormat(f"{self._progress:.1f}%")

    # ── 확인/취소 ────────────────────────────────────────

    def _on_confirm(self) -> None:
        """확인 버튼 클릭."""
        self.colors_confirmed.emit(self._fill_color, self._empty_color)
        self.accept()

    @staticmethod
    def _color_hex(color: tuple[int, int, int]) -> str:
        """RGB 튜플을 hex 문자열로 변환한다."""
        return f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"

    @property
    def fill_color(self) -> tuple[int, int, int]:
        return self._fill_color

    @property
    def empty_color(self) -> tuple[int, int, int]:
        return self._empty_color
