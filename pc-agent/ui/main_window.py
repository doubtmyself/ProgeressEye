"""메인 윈도우 모듈.

모니터링 상태, 등록된 영역의 진행률을 표시하고
영역 추가, 모니터링 시작/정지 기능을 제공한다.
"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QFrame,
    QCheckBox,
)

from utils.logger import log


class RegionCard(QFrame):
    """모니터링 영역 카드 위젯."""

    toggled = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)

    def __init__(
        self, region_id: str, label: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.region_id = region_id
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(
            "RegionCard { background: white; border: 1px solid #e0e0e0; "
            "border-radius: 8px; padding: 12px; margin: 4px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 체크박스 + 라벨 (헤더 행)
        header_row = QHBoxLayout()
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.stateChanged.connect(self._on_check_changed)
        header_row.addWidget(self._checkbox)

        self._label = QLabel(label)
        self._label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header_row.addWidget(self._label, stretch=1)
        layout.addLayout(header_row)

        # 프로그레스바 + 퍼센트
        progress_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(20)
        self._progress_bar.setTextVisible(False)
        progress_row.addWidget(self._progress_bar, stretch=1)

        self._percent_label = QLabel("0.0%")
        self._percent_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._percent_label.setMinimumWidth(55)
        self._percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        progress_row.addWidget(self._percent_label)
        layout.addLayout(progress_row)

        # 마지막 업데이트 시간
        self._time_label = QLabel("대기 중")
        self._time_label.setStyleSheet("color: #888; font-size: 11px;")
        # 편집 버튼 (시간 라벨 옆)
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._time_label)
        bottom_row.addStretch()

        self._btn_edit = QPushButton("✏️ 편집")
        self._btn_edit.setFixedHeight(24)
        self._btn_edit.setStyleSheet(
            "QPushButton { background: #f0f0f0; border: 1px solid #ccc; "
            "border-radius: 4px; padding: 0 10px; font-size: 11px; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        self._btn_edit.clicked.connect(
            lambda: self.edit_requested.emit(self.region_id)
        )
        bottom_row.addWidget(self._btn_edit)
        layout.addLayout(bottom_row)

    def _on_check_changed(self, state: int) -> None:
        """체크박스 상태 변경 시 시그널을 발생시킨다."""
        enabled = state == Qt.CheckState.Checked.value
        self.toggled.emit(self.region_id, enabled)

    def update_progress(self, progress: float) -> None:
        """진행률을 업데이트한다."""
        self._progress_bar.setValue(int(progress * 10))
        self._percent_label.setText(f"{progress:.1f}%")
        self._time_label.setText(f"업데이트: {datetime.now().strftime('%H:%M:%S')}")

    def set_label(self, label: str) -> None:
        """라벨을 변경한다."""
        self._label.setText(label)

    def set_checked(self, checked: bool) -> None:
        """체크박스 상태를 설정한다."""
        self._checkbox.setChecked(checked)


class MainWindow(QMainWindow):
    """ProgressEye 메인 윈도우.

    모니터링 상태와 등록 영역의 진행률을 표시한다.
    """

    select_area_requested = pyqtSignal()
    toggle_monitoring_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    region_toggled = pyqtSignal(str, bool)
    region_edit_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._monitoring = False
        self._region_cards: dict[str, RegionCard] = {}

        self.setWindowTitle("ProgressEye")
        self.setMinimumSize(400, 350)
        self.resize(420, 500)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 헤더
        title = QLabel("ProgressEye")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("진행률 모니터링")
        subtitle.setStyleSheet("color: #666; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # 상태 표시
        self._status_label = QLabel("● 대기 중")
        self._status_label.setStyleSheet(
            "color: #888; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(self._status_label)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(line)

        # 영역 목록 (스크롤)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._region_container = QWidget()
        self._region_layout = QVBoxLayout(self._region_container)
        self._region_layout.setSpacing(8)
        self._region_layout.setContentsMargins(0, 0, 0, 0)

        # 빈 상태 라벨
        self._empty_label = QLabel(
            "등록된 모니터링 영역이 없습니다.\n아래 '영역 추가' 버튼을 눌러 시작하세요."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #aaa; padding: 40px; font-size: 13px;")
        self._region_layout.addWidget(self._empty_label)

        self._region_layout.addStretch()
        scroll.setWidget(self._region_container)
        layout.addWidget(scroll, stretch=1)

        # 버튼 영역
        btn_layout = QHBoxLayout()

        self._btn_add = QPushButton("영역 추가")
        self._btn_add.setFixedHeight(36)
        self._btn_add.clicked.connect(self.select_area_requested.emit)
        btn_layout.addWidget(self._btn_add)

        self._btn_toggle = QPushButton("모니터링 시작")
        self._btn_toggle.setFixedHeight(36)
        self._btn_toggle.setStyleSheet(
            "QPushButton { background-color: #4285F4; color: white; "
            "border-radius: 4px; font-weight: bold; padding: 0 20px; }"
            "QPushButton:hover { background-color: #3367D6; }"
        )
        self._btn_toggle.clicked.connect(self.toggle_monitoring_requested.emit)
        btn_layout.addWidget(self._btn_toggle)

        layout.addLayout(btn_layout)

    def add_region_display(
        self, region_id: str, label: str, enabled: bool = True
    ) -> None:
        """영역 카드를 추가한다."""
        if region_id in self._region_cards:
            return

        # 빈 상태 라벨 숨김
        self._empty_label.hide()

        card = RegionCard(region_id, label)
        card.set_checked(enabled)
        card.toggled.connect(self.region_toggled)
        card.edit_requested.connect(self.region_edit_requested)
        self._region_cards[region_id] = card
        # addStretch 앞에 삽입
        self._region_layout.insertWidget(self._region_layout.count() - 1, card)
        log.info("영역 카드 추가: %s (%s)", region_id, label)

    def update_progress(self, region_id: str, progress: float, label: str = "") -> None:
        """영역의 진행률을 업데이트한다."""
        if region_id not in self._region_cards:
            self.add_region_display(region_id, label or region_id)

        card = self._region_cards[region_id]
        card.update_progress(progress)
        if label:
            card.set_label(label)

    def set_monitoring_state(self, active: bool) -> None:
        """모니터링 상태 UI를 변경한다."""
        self._monitoring = active
        if active:
            self._status_label.setText("● 모니터링 중")
            self._status_label.setStyleSheet(
                "color: #34A853; font-size: 13px; font-weight: bold;"
            )
            self._btn_toggle.setText("모니터링 정지")
            self._btn_toggle.setStyleSheet(
                "QPushButton { background-color: #EA4335; color: white; "
                "border-radius: 4px; font-weight: bold; padding: 0 20px; }"
                "QPushButton:hover { background-color: #C5221F; }"
            )
        else:
            self._status_label.setText("● 대기 중")
            self._status_label.setStyleSheet(
                "color: #888; font-size: 13px; font-weight: bold;"
            )
            self._btn_toggle.setText("모니터링 시작")
            self._btn_toggle.setStyleSheet(
                "QPushButton { background-color: #4285F4; color: white; "
                "border-radius: 4px; font-weight: bold; padding: 0 20px; }"
                "QPushButton:hover { background-color: #3367D6; }"
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """닫기 → 트레이로 최소화 (종료하지 않음)."""
        event.ignore()
        self.hide()
        log.info("메인 창 트레이로 최소화")
