"""색상 미리보기 및 수동 조정 다이얼로그.

영역 선택 후 감지된 채움/빈 색상을 보여주고,
사용자가 확인하거나 수동 조정할 수 있다.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QColorDialog,
    QFrame,
    QWidget,
)

from utils.logger import log


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
    확인/수동조정/재선택 옵션을 제공한다.
    """

    colors_confirmed = pyqtSignal(tuple, tuple)

    def __init__(
        self,
        image: QImage,
        fill_color: tuple[int, int, int],
        empty_color: tuple[int, int, int],
        detected_progress: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self._fill_color = fill_color
        self._empty_color = empty_color
        self._progress = detected_progress

        self.setWindowTitle("색상 감지 결과")
        self.setFixedWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 캡처 이미지 미리보기
        preview_label = QLabel()
        pixmap = QPixmap.fromImage(self._image)
        scaled = pixmap.scaledToWidth(
            min(340, pixmap.width()),
            Qt.TransformationMode.SmoothTransformation,
        )
        preview_label.setPixmap(scaled)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet(
            "border: 1px solid #ddd; padding: 4px; background: #f5f5f5;"
        )
        layout.addWidget(preview_label)

        # 채움 색상
        fill_row = QHBoxLayout()
        fill_row.addWidget(QLabel("채움 색상:"))
        self._fill_swatch = ColorSwatch(self._fill_color)
        fill_row.addWidget(self._fill_swatch)
        self._fill_hex = QLabel(self._color_hex(self._fill_color))
        self._fill_hex.setStyleSheet("font-family: 'Consolas'; color: #555;")
        fill_row.addWidget(self._fill_hex)
        fill_row.addStretch()
        layout.addLayout(fill_row)

        # 빈 색상
        empty_row = QHBoxLayout()
        empty_row.addWidget(QLabel("빈 색상:"))
        self._empty_swatch = ColorSwatch(self._empty_color)
        empty_row.addWidget(self._empty_swatch)
        self._empty_hex = QLabel(self._color_hex(self._empty_color))
        self._empty_hex.setStyleSheet("font-family: 'Consolas'; color: #555;")
        empty_row.addWidget(self._empty_hex)
        empty_row.addStretch()
        layout.addLayout(empty_row)

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

        # 버튼 영역
        btn_layout = QHBoxLayout()

        self._btn_adjust = QPushButton("색상 수동 조정")
        self._btn_adjust.clicked.connect(self._on_adjust_colors)
        btn_layout.addWidget(self._btn_adjust)

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

    def _on_confirm(self) -> None:
        """확인 버튼 클릭."""
        self.colors_confirmed.emit(self._fill_color, self._empty_color)
        self.accept()

    def _on_adjust_colors(self) -> None:
        """색상 수동 조정 버튼 클릭."""
        # 채움 색상 선택
        fill_qcolor = QColorDialog.getColor(
            QColor(*self._fill_color),
            self,
            "채움 색상 선택",
        )
        if fill_qcolor.isValid():
            self._fill_color = (
                fill_qcolor.red(),
                fill_qcolor.green(),
                fill_qcolor.blue(),
            )
            self._fill_swatch.set_color(self._fill_color)
            self._fill_hex.setText(self._color_hex(self._fill_color))

        # 빈 색상 선택
        empty_qcolor = QColorDialog.getColor(
            QColor(*self._empty_color),
            self,
            "빈 색상 선택",
        )
        if empty_qcolor.isValid():
            self._empty_color = (
                empty_qcolor.red(),
                empty_qcolor.green(),
                empty_qcolor.blue(),
            )
            self._empty_swatch.set_color(self._empty_color)
            self._empty_hex.setText(self._color_hex(self._empty_color))

        log.info("색상 수동 조정: 채움=%s, 빈=%s", self._fill_color, self._empty_color)

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
