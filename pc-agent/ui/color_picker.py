"""바 탐지 결과 미리보기 다이얼로그.

영역 선택 후 탐지된 진행바 영역과 분석된 진행률을 보여준다.
바 영역을 인터랙티브하게 편집하고, 편집 시 진행률을 재분석한다.
디버그 저장 기능 포함.
"""

from datetime import datetime
from enum import IntEnum, auto
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PIL import Image as PILImage

from core.bar_analyzer import BarAnalyzer
from core.bar_finder import BarRegion
from utils.i18n import t
from utils.logger import log


# ── 핸들 정의 ─────────────────────────────────────────────


class _Handle(IntEnum):
    """리사이즈 핸들 위치."""

    TOP_LEFT = auto()
    TOP_MID = auto()
    TOP_RIGHT = auto()
    MID_LEFT = auto()
    MID_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_MID = auto()
    BOTTOM_RIGHT = auto()


_HANDLE_CURSORS: dict[_Handle, Qt.CursorShape] = {
    _Handle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    _Handle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    _Handle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    _Handle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    _Handle.TOP_MID: Qt.CursorShape.SizeVerCursor,
    _Handle.BOTTOM_MID: Qt.CursorShape.SizeVerCursor,
    _Handle.MID_LEFT: Qt.CursorShape.SizeHorCursor,
    _Handle.MID_RIGHT: Qt.CursorShape.SizeHorCursor,
}

_HANDLE_SIZE = 8
_HANDLE_HALF = _HANDLE_SIZE // 2
_MIN_REGION = 4  # 원본 좌표 최소 크기 (px)


# ── InteractiveBarPreview ─────────────────────────────────


class InteractiveBarPreview(QWidget):
    """인터랙티브 바 영역 미리보기 위젯.

    이미지를 스케일 다운하여 표시하고,
    바 영역 사각형을 핸들로 편집할 수 있다.
    """

    bar_region_changed = pyqtSignal(object)  # new BarRegion emitted

    def __init__(
        self,
        qimage: QImage,
        bar_region: BarRegion | None,
        max_width: int = 340,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # 스케일 팩터 계산: display / original
        img_w = qimage.width() if qimage.width() > 0 else 1
        self._scale = min(1.0, max_width / img_w)
        self._display_w = int(qimage.width() * self._scale)
        self._display_h = int(qimage.height() * self._scale)
        self.setFixedSize(self._display_w, self._display_h)

        # 원본 이미지 + 스케일된 pixmap
        self._original_image = qimage
        self._pixmap = QPixmap.fromImage(qimage).scaled(
            self._display_w,
            self._display_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._bar_region = bar_region

        # 드래그 상태
        self._active_handle: _Handle | None = None
        self._dragging = False
        self._drag_origin = QPoint()
        self._rect_origin: tuple[int, int, int, int] = (0, 0, 0, 0)

        self.setMouseTracking(True)

    # ── 좌표 변환 ─────────────────────────────────────────

    def _to_display(self, x: int, y: int) -> tuple[int, int]:
        """원본 좌표 → 디스플레이 좌표."""
        return int(x * self._scale), int(y * self._scale)

    def _to_original(self, dx: int, dy: int) -> tuple[int, int]:
        """디스플레이 delta → 원본 delta."""
        if self._scale == 0:
            return 0, 0
        return int(dx / self._scale), int(dy / self._scale)

    def _region_display_rect(self) -> QRect | None:
        """바 영역을 디스플레이 좌표 QRect로 반환한다."""
        if self._bar_region is None:
            return None
        br = self._bar_region
        dx1, dy1 = self._to_display(br.left, br.top)
        dx2, dy2 = self._to_display(br.right, br.bottom)
        return QRect(dx1, dy1, dx2 - dx1, dy2 - dy1)

    # ── 핸들 계산 ─────────────────────────────────────────

    def _handle_rects(self) -> dict[_Handle, QRect]:
        """8개 핸들의 QRect를 디스플레이 좌표로 계산한다."""
        r = self._region_display_rect()
        if r is None:
            return {}
        cx = r.x() + r.width() // 2
        cy = r.y() + r.height() // 2
        h = _HANDLE_HALF

        return {
            _Handle.TOP_LEFT: QRect(
                r.left() - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.TOP_MID: QRect(cx - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.TOP_RIGHT: QRect(
                r.right() - h, r.top() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.MID_LEFT: QRect(r.left() - h, cy - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.MID_RIGHT: QRect(r.right() - h, cy - h, _HANDLE_SIZE, _HANDLE_SIZE),
            _Handle.BOTTOM_LEFT: QRect(
                r.left() - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.BOTTOM_MID: QRect(
                cx - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
            _Handle.BOTTOM_RIGHT: QRect(
                r.right() - h, r.bottom() - h, _HANDLE_SIZE, _HANDLE_SIZE
            ),
        }

    def _hit_handle(self, pos: QPoint) -> _Handle | None:
        """마우스 위치가 핸들 위에 있으면 해당 핸들을 반환한다."""
        margin = 3
        for handle, rect in self._handle_rects().items():
            expanded = rect.adjusted(-margin, -margin, margin, margin)
            if expanded.contains(pos):
                return handle
        return None

    # ── 페인팅 ────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        """스케일된 이미지 + 바 영역 사각형 + 핸들을 그린다."""
        painter = QPainter(self)

        # 1. 스케일된 이미지
        painter.drawPixmap(0, 0, self._pixmap)

        # 2. 바 영역 사각형 + 핸들
        r = self._region_display_rect()
        if r is not None:
            # 외곽: 빨간 2px
            pen_red = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen_red)
            painter.drawRect(r)

            # 내곽: 시안 2px
            inner = r.adjusted(2, 2, -2, -2)
            pen_cyan = QPen(QColor(0, 255, 255), 2)
            painter.setPen(pen_cyan)
            painter.drawRect(inner)

            # 8개 핸들 (흰색 8×8 + 파란 #0066CC 테두리 1px)
            handle_pen = QPen(QColor(0, 102, 204), 1)
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(handle_pen)
            for handle_rect in self._handle_rects().values():
                painter.drawRect(handle_rect)

        painter.end()

    # ── 마우스 이벤트 ──────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """드래그 시작 — 핸들 또는 영역 내부를 판별한다."""
        if event.button() != Qt.MouseButton.LeftButton or self._bar_region is None:
            return

        pos = event.pos()

        # 핸들 히트 체크
        handle = self._hit_handle(pos)
        if handle is not None:
            self._active_handle = handle
            self._dragging = True
            self._drag_origin = pos
            br = self._bar_region
            self._rect_origin = (br.left, br.top, br.right, br.bottom)
            return

        # 영역 내부 → 이동
        r = self._region_display_rect()
        if r is not None and r.contains(pos):
            self._active_handle = None
            self._dragging = True
            self._drag_origin = pos
            br = self._bar_region
            self._rect_origin = (br.left, br.top, br.right, br.bottom)
            return

        # 영역 밖 → 무시

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """드래그 중 — 리사이즈 또는 이동. 비드래그 — 커서 변경."""
        pos = event.pos()

        if self._dragging and self._bar_region is not None:
            dx = pos.x() - self._drag_origin.x()
            dy = pos.y() - self._drag_origin.y()

            # 디스플레이 delta → 원본 delta
            odx, ody = self._to_original(dx, dy)

            if self._active_handle is not None:
                self._resize_by_handle(self._active_handle, odx, ody)
            else:
                self._move_region(odx, ody)

            self.update()
            return

        # 커서 변경
        if self._bar_region is not None:
            handle = self._hit_handle(pos)
            if handle is not None:
                self.setCursor(_HANDLE_CURSORS[handle])
            else:
                r = self._region_display_rect()
                if r is not None and r.contains(pos):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """드래그 종료 → bar_region_changed 시그널 emit."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._active_handle = None
            if self._bar_region is not None:
                self.bar_region_changed.emit(self._bar_region)

    # ── 리사이즈 / 이동 ──────────────────────────────────

    def _resize_by_handle(self, handle: _Handle, odx: int, ody: int) -> None:
        """핸들 종류에 따라 바 영역을 리사이즈한다 (원본 좌표)."""
        if self._bar_region is None:
            return
        confidence = self._bar_region.confidence
        direction = self._bar_region.direction
        orig_left, orig_top, orig_right, orig_bottom = self._rect_origin
        img_w = self._original_image.width()
        img_h = self._original_image.height()

        left, top, right, bottom = orig_left, orig_top, orig_right, orig_bottom

        # 각 핸들이 움직이는 변
        if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
            top = orig_top + ody
        if handle in (_Handle.BOTTOM_LEFT, _Handle.BOTTOM_MID, _Handle.BOTTOM_RIGHT):
            bottom = orig_bottom + ody
        if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
            left = orig_left + odx
        if handle in (_Handle.TOP_RIGHT, _Handle.MID_RIGHT, _Handle.BOTTOM_RIGHT):
            right = orig_right + odx

        # 이미지 경계 클램프
        left = max(0, left)
        top = max(0, top)
        right = min(img_w, right)
        bottom = min(img_h, bottom)

        # 최소 크기 제한 (4×4 원본 픽셀)
        if right - left < _MIN_REGION:
            if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
                left = right - _MIN_REGION
            else:
                right = left + _MIN_REGION
        if bottom - top < _MIN_REGION:
            if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
                top = bottom - _MIN_REGION
            else:
                bottom = top + _MIN_REGION

        self._bar_region = BarRegion(
            top=top,
            left=left,
            bottom=bottom,
            right=right,
            confidence=confidence,
            direction=direction,
        )

    def _move_region(self, odx: int, ody: int) -> None:
        """바 영역을 이동한다 (이미지 경계 클램프, 원본 좌표)."""
        if self._bar_region is None:
            return
        confidence = self._bar_region.confidence
        direction = self._bar_region.direction
        orig_left, orig_top, orig_right, orig_bottom = self._rect_origin
        w = orig_right - orig_left
        h = orig_bottom - orig_top
        img_w = self._original_image.width()
        img_h = self._original_image.height()

        new_left = orig_left + odx
        new_top = orig_top + ody

        # 경계 클램프
        new_left = max(0, min(new_left, img_w - w))
        new_top = max(0, min(new_top, img_h - h))

        self._bar_region = BarRegion(
            top=new_top,
            left=new_left,
            bottom=new_top + h,
            right=new_left + w,
            confidence=confidence,
            direction=direction,
        )


# ── BarPreviewDialog ──────────────────────────────────────


class BarPreviewDialog(QDialog):
    """바 탐지 결과 미리보기 다이얼로그.

    탐지된 진행바 영역과 분석된 진행률을 보여주고,
    사용자가 확인 또는 재선택을 선택한다.
    바 영역을 인터랙티브하게 편집할 수 있으며,
    편집 시 진행률을 자동 재분석한다.
    디버그 저장 기능 포함.
    """

    def __init__(
        self,
        image: QImage,
        full_image: PILImage.Image,
        bar_image: PILImage.Image,
        detected_progress: float,
        bar_region: BarRegion | None = None,
        debug_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._debug_mode = debug_mode
        self._image = image  # 전체 캡처 QImage (미리보기용)
        self._full_image = full_image  # 전체 캡처 PIL Image
        self._bar_image = bar_image  # 크롭된 바 PIL Image
        self._progress = detected_progress
        self._bar_region = bar_region
        self._analyzer = BarAnalyzer()
        self.reselect_requested = False

        self.setWindowTitle(t("bar_preview_title"))
        self.setFixedWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 인터랙티브 바 영역 미리보기
        self._preview = InteractiveBarPreview(
            self._image, self._bar_region, max_width=340
        )
        self._preview.bar_region_changed.connect(self._on_bar_region_edited)
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # 방향 표시
        direction = (
            t("direction_horizontal")
            if self._direction == "horizontal"
            else t("direction_vertical")
        )
        dir_label = QLabel(t("bar_direction").format(direction=direction))
        dir_label.setStyleSheet("color: #888; font-size: 11px;")
        dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dir_label)

        # 감지된 진행률
        self._progress_label = QLabel(
            t("detected_progress").format(progress=f"{self._progress:.1f}")
        )
        self._progress_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self._progress_label)

        # 프로그레스바
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(int(self._progress * 10))
        self._progress_bar.setFormat(f"{self._progress:.1f}%")
        self._progress_bar.setFixedHeight(24)
        layout.addWidget(self._progress_bar)

        # 도구 행: 디버그 저장
        tools_row = QHBoxLayout()
        tools_row.addStretch()

        self._btn_debug_save = QPushButton(t("btn_debug_save"))
        self._btn_debug_save.setToolTip(t("tooltip_debug_save"))
        self._btn_debug_save.clicked.connect(self._on_debug_save)
        self._btn_debug_save.setVisible(self._debug_mode)
        tools_row.addWidget(self._btn_debug_save)

        layout.addLayout(tools_row)

        # 작업 이름 입력
        name_layout = QHBoxLayout()
        name_label = QLabel(t("task_name_label"))
        name_label.setStyleSheet("color: #888; font-size: 12px;")
        name_layout.addWidget(name_label)
        self._task_name_input = QLineEdit()
        self._task_name_input.setPlaceholderText(t("task_name_placeholder"))
        self._task_name_input.setStyleSheet(
            "QLineEdit { background: #1c1c30; border: 1px solid #2a2a45;"
            "border-radius: 4px; padding: 4px 8px; color: #ffffff; font-size: 12px; }"
            "QLineEdit:focus { border-color: #3b82f6; }"
        )
        name_layout.addWidget(self._task_name_input)
        layout.addLayout(name_layout)

        # 버튼 영역
        btn_layout = QHBoxLayout()

        self._btn_reselect = QPushButton(t("btn_reselect"))
        self._btn_reselect.clicked.connect(self._on_reselect)
        btn_layout.addWidget(self._btn_reselect)

        self._btn_confirm = QPushButton(t("btn_confirm"))
        self._btn_confirm.setDefault(True)
        self._btn_confirm.setStyleSheet(
            "QPushButton { background-color: #4285F4; color: white; "
            "padding: 6px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3367D6; }"
        )
        self._btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_confirm)

        layout.addLayout(btn_layout)

    def _on_reselect(self) -> None:
        """재선택 버튼 클릭 시 플래그 설정 후 reject."""
        self.reselect_requested = True
        self.reject()

    @property
    def _direction(self) -> str:
        """bar_region에서 자동 감지된 방향."""
        if self._bar_region is not None:
            return self._bar_region.direction
        return "horizontal"

    # ── 바 영역 편집 ─────────────────────────────────────

    def _on_bar_region_edited(self, new_region: BarRegion) -> None:
        """바 영역이 편집되면 진행률을 재분석한다."""
        self._bar_region = new_region

        # 바 이미지 재크롭
        bar_image = self._full_image.crop(new_region.bbox)
        self._bar_image = bar_image

        # 재분석
        result = self._analyzer.analyze(bar_image, direction=new_region.direction)
        self._progress = result.progress

        # UI 업데이트
        self._progress_label.setText(
            t("detected_progress").format(progress=f"{self._progress:.1f}")
        )
        self._progress_bar.setValue(int(self._progress * 10))
        self._progress_bar.setFormat(f"{self._progress:.1f}%")

        log.info(
            "바 영역 편집 → 재분석: (%d,%d)-(%d,%d) → %.1f%%",
            new_region.left,
            new_region.top,
            new_region.right,
            new_region.bottom,
            self._progress,
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

    # ── 프로퍼티 ─────────────────────────────────────────

    @property
    def progress(self) -> float:
        """감지된 진행률."""
        return self._progress

    @property
    def bar_region(self) -> BarRegion | None:
        """편집된 바 영역."""
        return self._bar_region

    @property
    def task_name(self) -> str | None:
        """입력된 작업 이름. 비어있으면 None."""
        text = self._task_name_input.text().strip()
        return text if text else None
