"""OCR 숫자(%) 탐지 결과 미리보기 다이얼로그.

영역 선택 후 OCR로 탐지된 숫자를 사각형으로 표시하고
추출된 진행률을 보여준다.
"""

from PyQt6.QtCore import Qt
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

from core.ocr_reader import OcrResult
from utils.i18n import t


class OcrPreviewDialog(QDialog):
    """OCR 탐지 결과 미리보기 다이얼로그.

    탐지된 숫자% 영역을 사각형으로 표시하고,
    추출된 진행률을 보여준다.
    사용자가 확인 또는 재선택을 선택한다.
    """

    def __init__(
        self,
        image: QImage,
        ocr_results: list[OcrResult],
        detected_progress: float | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self._ocr_results = ocr_results
        self._progress = detected_progress if detected_progress is not None else 0.0
        self.reselect_requested = False

        self.setWindowTitle(t("ocr_preview_title"))
        self.setFixedWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 탐지 결과가 그려진 미리보기 이미지
        annotated = self._draw_detections()
        max_width = 340
        img_w = annotated.width() if annotated.width() > 0 else 1
        scale = min(1.0, max_width / img_w)
        display_w = int(annotated.width() * scale)
        display_h = int(annotated.height() * scale)

        pixmap = QPixmap.fromImage(annotated).scaled(
            display_w,
            display_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)

        # 탐지 상태 텍스트
        if self._ocr_results:
            texts = [
                f"{r.text}{'%' if not r.has_percent_sign else ''}"
                for r in self._ocr_results
            ]
            detect_label = QLabel(t("ocr_detected_text").format(texts=", ".join(texts)))
        else:
            detect_label = QLabel(t("ocr_no_detection"))
        detect_label.setStyleSheet("color: #888; font-size: 11px;")
        detect_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detect_label)

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

    def _draw_detections(self) -> QImage:
        """OCR 결과에 사각형을 그린 이미지를 반환한다.

        프로그래스바 탐지와 동일하게 빨간+시안 2줄 사각형을 사용한다.
        """
        result = self._image.copy()
        painter = QPainter(result)

        for ocr_result in self._ocr_results:
            x, y, w, h = ocr_result.bbox

            # 외곽: 빨간 2px
            pen_red = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen_red)
            painter.drawRect(x, y, w, h)

            # 내곽: 시안 2px
            pen_cyan = QPen(QColor(0, 255, 255), 2)
            painter.setPen(pen_cyan)
            painter.drawRect(x + 2, y + 2, w - 4, h - 4)

        painter.end()
        return result

    @property
    def progress(self) -> float:
        """감지된 진행률."""
        return self._progress

    @property
    def task_name(self) -> str | None:
        """입력된 작업 이름. 비어있으면 None."""
        text = self._task_name_input.text().strip()
        return text if text else None
