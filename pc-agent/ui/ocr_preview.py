"""OCR 숫자 탐지 결과 미리보기 다이얼로그."""

from enum import IntEnum, auto

from PIL import Image as PILImage
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.ocr_reader import OcrReader, OcrResult
from utils.i18n import t


class _Handle(IntEnum):
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
_MIN_REGION = 8


class InteractiveOcrPreview(QWidget):
    """Editable OCR ROI preview: white ROI + red detected-value box."""

    region_changed = pyqtSignal(tuple)

    def __init__(
        self,
        qimage: QImage,
        roi: tuple[int, int, int, int],
        max_width: int = 340,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        img_w = qimage.width() if qimage.width() > 0 else 1
        self._scale = min(1.0, max_width / img_w)
        self._display_w = int(qimage.width() * self._scale)
        self._display_h = int(qimage.height() * self._scale)
        self.setFixedSize(self._display_w, self._display_h)

        self._original_image = qimage
        self._pixmap = QPixmap.fromImage(qimage).scaled(
            self._display_w,
            self._display_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._roi = roi
        self._detected_bbox: tuple[int, int, int, int] | None = None

        self._active_handle: _Handle | None = None
        self._dragging = False
        self._drag_origin = QPoint()
        self._rect_origin: tuple[int, int, int, int] = (0, 0, 0, 0)

        self.setMouseTracking(True)

    def set_roi(self, roi: tuple[int, int, int, int]) -> None:
        self._roi = roi
        self.update()

    def set_detected_bbox(self, bbox: tuple[int, int, int, int] | None) -> None:
        self._detected_bbox = bbox
        self.update()

    def _to_display(self, x: int, y: int) -> tuple[int, int]:
        return int(x * self._scale), int(y * self._scale)

    def _to_original(self, dx: int, dy: int) -> tuple[int, int]:
        if self._scale == 0:
            return 0, 0
        return int(dx / self._scale), int(dy / self._scale)

    def _roi_display_rect(self) -> QRect:
        left, top, right, bottom = self._roi
        dx1, dy1 = self._to_display(left, top)
        dx2, dy2 = self._to_display(right, bottom)
        return QRect(dx1, dy1, dx2 - dx1, dy2 - dy1)

    def _detected_display_rect(self) -> QRect | None:
        if self._detected_bbox is None:
            return None
        x, y, w, h = self._detected_bbox
        dx1, dy1 = self._to_display(x, y)
        dx2, dy2 = self._to_display(x + w, y + h)
        return QRect(dx1, dy1, dx2 - dx1, dy2 - dy1)

    def _handle_rects(self) -> dict[_Handle, QRect]:
        r = self._roi_display_rect()
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
        margin = 3
        for handle, rect in self._handle_rects().items():
            expanded = rect.adjusted(-margin, -margin, margin, margin)
            if expanded.contains(pos):
                return handle
        return None

    def paintEvent(self, a0: QPaintEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        roi = self._roi_display_rect()
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(roi)

        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for handle_rect in self._handle_rects().values():
            painter.drawRect(handle_rect)

        detected = self._detected_display_rect()
        if detected is not None:
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(detected)

        painter.end()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        if a0.button() != Qt.MouseButton.LeftButton:
            return
        pos = a0.pos()
        handle = self._hit_handle(pos)
        if handle is not None:
            self._active_handle = handle
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = self._roi
            return

        if self._roi_display_rect().contains(pos):
            self._active_handle = None
            self._dragging = True
            self._drag_origin = pos
            self._rect_origin = self._roi

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        pos = a0.pos()
        if self._dragging:
            dx = pos.x() - self._drag_origin.x()
            dy = pos.y() - self._drag_origin.y()
            odx, ody = self._to_original(dx, dy)
            if self._active_handle is not None:
                self._resize_by_handle(self._active_handle, odx, ody)
            else:
                self._move_region(odx, ody)
            self.update()
            return

        handle = self._hit_handle(pos)
        if handle is not None:
            self.setCursor(_HANDLE_CURSORS[handle])
        elif self._roi_display_rect().contains(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        if a0 is None:
            return
        if a0.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._active_handle = None
            self.region_changed.emit(self._roi)

    def _resize_by_handle(self, handle: _Handle, odx: int, ody: int) -> None:
        left, top, right, bottom = self._rect_origin
        img_w = self._original_image.width()
        img_h = self._original_image.height()

        if handle in (_Handle.TOP_LEFT, _Handle.TOP_MID, _Handle.TOP_RIGHT):
            top += ody
        if handle in (_Handle.BOTTOM_LEFT, _Handle.BOTTOM_MID, _Handle.BOTTOM_RIGHT):
            bottom += ody
        if handle in (_Handle.TOP_LEFT, _Handle.MID_LEFT, _Handle.BOTTOM_LEFT):
            left += odx
        if handle in (_Handle.TOP_RIGHT, _Handle.MID_RIGHT, _Handle.BOTTOM_RIGHT):
            right += odx

        left = max(0, left)
        top = max(0, top)
        right = min(img_w, right)
        bottom = min(img_h, bottom)

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

        self._roi = (left, top, right, bottom)

    def _move_region(self, odx: int, ody: int) -> None:
        left, top, right, bottom = self._rect_origin
        w = right - left
        h = bottom - top
        img_w = self._original_image.width()
        img_h = self._original_image.height()

        new_left = max(0, min(left + odx, img_w - w))
        new_top = max(0, min(top + ody, img_h - h))
        self._roi = (new_left, new_top, new_left + w, new_top + h)


class OcrPreviewDialog(QDialog):
    """OCR 탐지 결과 미리보기 + 모드/ROI 편집 다이얼로그."""

    def __init__(
        self,
        image: QImage,
        full_image: PILImage.Image,
        ocr_reader: OcrReader,
        ocr_results: list[OcrResult],
        detected_progress: float | None,
        ocr_region: tuple[int, int, int, int] | None = None,
        detection_mode: str = "percent",
        target_value: float = 100.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self._full_image = full_image
        self._ocr_reader = ocr_reader
        self._all_results = ocr_results
        self._progress = detected_progress if detected_progress is not None else 0.0
        self._detected_value = self._progress
        self._ocr_region = self._normalized_region(
            ocr_region,
            full_image.width,
            full_image.height,
        )
        self._mode = "value" if detection_mode == "value" else "percent"
        self._target_value = max(1.0, float(target_value))
        self._detected_bbox: tuple[int, int, int, int] | None = None
        self.reselect_requested = False

        self.setWindowTitle(t("ocr_preview_title"))
        self.setFixedWidth(420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()
        self._refresh_detection_from_roi()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._preview = InteractiveOcrPreview(
            self._image, self._ocr_region, max_width=380
        )
        self._preview.region_changed.connect(self._on_roi_edited)
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        mode_row = QHBoxLayout()
        self._chk_percent = QCheckBox(t("ocr_mode_percent"))
        self._chk_value = QCheckBox(t("ocr_mode_max_value"))
        self._chk_percent.setChecked(self._mode == "percent")
        self._chk_value.setChecked(self._mode == "value")
        self._chk_percent.stateChanged.connect(self._on_mode_changed)
        self._chk_value.stateChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._chk_percent)
        mode_row.addWidget(self._chk_value)
        mode_row.addStretch()
        mode_row.addWidget(QLabel(t("ocr_target_input_label")))
        self._target_input = QLineEdit(f"{self._target_value:3.1f}")
        self._target_input.setFixedWidth(88)
        self._target_input.editingFinished.connect(self._on_target_changed)
        mode_row.addWidget(self._target_input)
        layout.addLayout(mode_row)

        self._sync_mode_controls()

        self._detect_label = QLabel()
        self._detect_label.setStyleSheet("color: #888; font-size: 11px;")
        self._detect_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._detect_label)

        self._progress_label = QLabel()
        self._progress_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setFixedHeight(24)
        layout.addWidget(self._progress_bar)

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

    def _mode_settings(self) -> tuple[bool, float]:
        prefer_percent = self._mode == "percent"
        max_value = 100.0 if prefer_percent else max(1.0, self._target_value)
        return prefer_percent, max_value

    def _sync_mode_controls(self) -> None:
        is_percent_mode = self._mode == "percent"
        self._target_input.setEnabled(not is_percent_mode)

    def _on_mode_changed(self) -> None:
        sender = self.sender()
        if sender is self._chk_percent and self._chk_percent.isChecked():
            self._chk_value.setChecked(False)
            self._mode = "percent"
        elif sender is self._chk_value and self._chk_value.isChecked():
            self._chk_percent.setChecked(False)
            self._mode = "value"
        elif not self._chk_percent.isChecked() and not self._chk_value.isChecked():
            self._chk_percent.setChecked(True)
            self._mode = "percent"
        self._sync_mode_controls()
        self._refresh_detection_from_roi()

    def _on_target_changed(self) -> None:
        if self._mode == "percent":
            # Keep the previously entered target value unchanged while in percent mode.
            self._target_input.setText(f"{self._target_value:3.1f}")
            return
        try:
            parsed = float(self._target_input.text().strip())
        except ValueError:
            parsed = self._target_value
        self._target_value = max(1.0, parsed)
        self._target_input.setText(f"{self._target_value:3.1f}")
        self._refresh_detection_from_roi()

    def _retarget_roi_for_mode(self) -> None:
        left, top, right, bottom = self._ocr_region
        h = max(1, bottom - top)
        center_x = (left + right) // 2

        target_chars = self._target_char_count()
        char_w = max(6, int(h * 0.55))
        pad = max(8, int(char_w * 0.8))
        target_w = max(char_w * target_chars + pad * 2, right - left)

        new_left = center_x - target_w // 2
        new_right = center_x + target_w // 2
        self._ocr_region = self._normalized_region(
            (new_left, top, new_right, bottom),
            self._full_image.width,
            self._full_image.height,
        )
        self._preview.set_roi(self._ocr_region)

    def _target_char_count(self) -> int:
        if self._mode == "percent":
            return max(1, len(f"{self._target_value:3.1f}".replace(".", "")) + 1)
        if self._target_value.is_integer():
            return max(1, len(str(int(self._target_value))))
        return max(1, len(str(self._target_value).replace(".", "")))

    def _on_roi_edited(self, roi: tuple[int, int, int, int]) -> None:
        self._ocr_region = self._normalized_region(
            roi,
            self._full_image.width,
            self._full_image.height,
        )
        self._refresh_detection_from_roi()

    def _refresh_detection_from_roi(self) -> None:
        left, top, right, bottom = self._ocr_region
        crop = self._full_image.crop((left, top, right, bottom))
        prefer_percent, max_value = self._mode_settings()
        results = self._ocr_reader.find_percentages(
            crop,
            min_value=0.0,
            max_value=max_value,
        )
        if self._mode == "value":
            results = [r for r in results if not r.has_percent_sign]

        if not results:
            self._detected_bbox = None
            self._preview.set_detected_bbox(None)
            self._detect_label.setText(t("ocr_no_detection"))
            self._detected_value = 0.0
            self._progress = 0.0
            self._update_progress_display()
            return

        best = self._ocr_reader.select_best_result(
            results,
            prefer_percent_sign=prefer_percent,
        )
        x, y, w, h = best.bbox
        self._detected_bbox = (left + x, top + y, w, h)
        self._preview.set_detected_bbox(self._detected_bbox)

        shown_text = f"{best.text}{'' if best.has_percent_sign else ('%' if self._mode == 'percent' else '')}"
        self._detect_label.setText(t("ocr_detected_text").format(texts=shown_text))

        self._detected_value = best.progress
        if self._mode == "percent":
            self._progress = self._detected_value
        else:
            self._progress = min(100.0, (self._detected_value / max_value) * 100.0)
        self._update_progress_display()

    def _update_progress_display(self) -> None:
        if self._mode == "percent":
            self._progress_label.setText(
                t("detected_progress").format(progress=f"{self._progress:3.1f}")
            )
            self._progress_bar.setRange(0, 1000)
            self._progress_bar.setValue(int(self._progress * 10))
            self._progress_bar.setFormat(f"{self._progress:3.1f}%")
        else:
            self._progress_label.setText(
                t("detected_value").format(
                    value=f"{self._detected_value:3.1f} / {self._target_value:3.1f}"
                )
            )
            self._progress_bar.setRange(0, 1000)
            self._progress_bar.setValue(int(self._progress * 10))
            self._progress_bar.setFormat(f"{self._progress:3.1f}%")

    def _on_reselect(self) -> None:
        self.reselect_requested = True
        self.reject()

    @staticmethod
    def _normalized_region(
        region: tuple[int, int, int, int] | None,
        img_w: int,
        img_h: int,
    ) -> tuple[int, int, int, int]:
        if img_w <= 0 or img_h <= 0:
            return (0, 0, 1, 1)
        if region is None:
            return (0, 0, img_w, img_h)
        left, top, right, bottom = region
        left = max(0, min(left, img_w - 1))
        top = max(0, min(top, img_h - 1))
        right = max(left + 1, min(right, img_w))
        bottom = max(top + 1, min(bottom, img_h))
        return (left, top, right, bottom)

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def task_name(self) -> str | None:
        text = self._task_name_input.text().strip()
        return text if text else None

    @property
    def ocr_region(self) -> tuple[int, int, int, int]:
        return self._ocr_region

    @property
    def detection_mode(self) -> str:
        return self._mode

    @property
    def target_value(self) -> float:
        return self._target_value
